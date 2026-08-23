"""
Google OAuth 2.0 and Google Calendar Integration Service for Clinica.

Features:
- Google OAuth 2.0 authorization URL generation & token exchange
- Secure token storage with auto-refresh mechanism
- Idempotent Calendar event operations (Create, Update, Delete)
- Multi-party synchronization (patient & doctor calendars)
- Localhost dev mode fallback when Google API credentials are not yet configured
- Robust error handling for background job retry execution
"""
import logging
import urllib.parse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.logger import log_event
from app.models import (
    User,
    DoctorProfile,
    Appointment,
    AppointmentStatus,
    UserGoogleAccount,
    BackgroundJob,
)

logger = logging.getLogger(__name__)

GOOGLE_AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


class GoogleCalendarService:

    # ── OAuth 2.0 Flow ──────────────────────────────────────────────────────────

    @staticmethod
    def get_authorization_url(state: str = "login", redirect_uri: Optional[str] = None) -> str:
        """
        Generate the Google OAuth 2.0 authorization consent URL for localhost development.
        """
        cb_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI or "http://localhost:5173/auth/google/callback"
        
        if not settings.GOOGLE_CLIENT_ID:
            # Localhost dev fallback URL when credentials are not configured yet
            params = {
                "code": f"mock_dev_code_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                "state": state,
                "dev_mode": "true",
            }
            return f"{cb_uri}?{urllib.parse.urlencode(params)}"

        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": cb_uri,
            "response_type": "code",
            "scope": settings.GOOGLE_OAUTH_SCOPES,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "include_granted_scopes": "true",
        }
        return f"{GOOGLE_AUTH_BASE_URL}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def exchange_code_for_tokens(
        code: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Exchange the authorization code for Google access token, refresh token, and user info.
        """
        cb_uri = redirect_uri or settings.GOOGLE_REDIRECT_URI or "http://localhost:5173/auth/google/callback"

        # Check for dev mode fallback
        if not settings.GOOGLE_CLIENT_ID or code.startswith("mock_dev_code"):
            logger.info("Using localhost dev mode for Google OAuth token exchange")
            return {
                "access_token": f"mock_access_token_{code}",
                "refresh_token": f"mock_refresh_token_{code}",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": settings.GOOGLE_OAUTH_SCOPES,
                "user_info": {
                    "id": f"google_dev_{code[-8:]}",
                    "email": "dev.user@gmail.com",
                    "name": "Dev Google User",
                    "picture": "https://lh3.googleusercontent.com/a/default-user",
                }
            }

        data = {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": cb_uri,
            "grant_type": "authorization_code",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(GOOGLE_TOKEN_URL, data=data)
                res.raise_for_status()
                token_data = res.json()

                access_token = token_data.get("access_token")
                user_info_res = client.get(
                    GOOGLE_USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                user_info_res.raise_for_status()
                token_data["user_info"] = user_info_res.json()
                return token_data

        except httpx.HTTPStatusError as exc:
            logger.error(f"Google token exchange HTTP error: {exc.response.text}")
            raise ValueError(f"Failed to exchange Google OAuth code: {exc.response.text}")
        except Exception as exc:
            logger.error(f"Google token exchange unexpected error: {exc}")
            raise ValueError(f"Failed to communicate with Google OAuth: {str(exc)}")

    @staticmethod
    def refresh_access_token(db: Session, account: UserGoogleAccount) -> str:
        """
        Refresh expired Google OAuth access token using the stored refresh token.
        """
        if not account.refresh_token:
            return account.access_token

        # Dev mode check
        if account.refresh_token.startswith("mock_refresh_token") or not settings.GOOGLE_CLIENT_ID:
            account.access_token = f"mock_access_token_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            account.token_expiry = datetime.utcnow() + timedelta(hours=1)
            db.commit()
            return account.access_token

        data = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": account.refresh_token,
            "grant_type": "refresh_token",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(GOOGLE_TOKEN_URL, data=data)
                res.raise_for_status()
                token_data = res.json()

                account.access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)
                account.token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
                account.updated_at = datetime.utcnow()
                db.commit()
                return account.access_token

        except Exception as exc:
            logger.error(f"Failed to refresh Google access token for user {account.user_id}: {exc}")
            raise

    @staticmethod
    def get_valid_access_token(db: Session, account: UserGoogleAccount) -> str:
        """
        Return a valid access token, auto-refreshing if expired or within 5 mins of expiry.
        """
        if account.token_expiry and account.token_expiry <= datetime.utcnow() + timedelta(minutes=5):
            return GoogleCalendarService.refresh_access_token(db, account)
        return account.access_token

    # ── Secure Account Association ──────────────────────────────────────────────

    @staticmethod
    def save_user_google_account(
        db: Session,
        user_id: str,
        token_data: Dict[str, Any],
    ) -> UserGoogleAccount:
        """
        Persist or update Google OAuth account credentials for a user.
        """
        user_info = token_data.get("user_info", {})
        google_user_id = user_info.get("id") or user_info.get("sub")
        google_email = user_info.get("email") or ""
        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        scopes = token_data.get("scope", settings.GOOGLE_OAUTH_SCOPES)

        account = db.query(UserGoogleAccount).filter(UserGoogleAccount.user_id == user_id).first()
        if not account:
            account = UserGoogleAccount(
                user_id=user_id,
                google_user_id=google_user_id,
                email=google_email,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expiry=token_expiry,
                scopes=scopes,
                is_calendar_connected=True,
            )
            db.add(account)
        else:
            account.google_user_id = google_user_id
            account.email = google_email
            account.access_token = access_token
            if refresh_token:
                account.refresh_token = refresh_token
            account.token_expiry = token_expiry
            account.scopes = scopes
            account.is_calendar_connected = True
            account.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(account)
        log_event("GOOGLE_CALENDAR_CONNECTED", {"user_id": user_id, "google_email": google_email})
        return account

    @staticmethod
    def disconnect_google_account(db: Session, user_id: str) -> bool:
        """
        Disconnect a user's Google Calendar integration.
        """
        account = db.query(UserGoogleAccount).filter(UserGoogleAccount.user_id == user_id).first()
        if account:
            account.is_calendar_connected = False
            db.commit()
            log_event("GOOGLE_CALENDAR_DISCONNECTED", {"user_id": user_id})
            return True
        return False

    @staticmethod
    def get_user_calendar_status(db: Session, user_id: str) -> Dict[str, Any]:
        """
        Query whether the user has an active Google Calendar integration.
        """
        account = db.query(UserGoogleAccount).filter(
            UserGoogleAccount.user_id == user_id,
            UserGoogleAccount.is_calendar_connected == True
        ).first()

        if not account:
            return {"connected": False, "email": None, "scopes": None, "connected_at": None}

        return {
            "connected": True,
            "email": account.email,
            "scopes": account.scopes,
            "connected_at": account.created_at,
        }

    # ── Idempotent Calendar Event Operations ────────────────────────────────────

    @staticmethod
    def _build_event_body(appointment: Appointment) -> Dict[str, Any]:
        """
        Construct a standard Google Calendar event body from an Appointment record.
        """
        doctor_name = "Doctor"
        specialization = "General Medicine"
        if appointment.doctor:
            specialization = appointment.doctor.specialization
            if appointment.doctor.user:
                doctor_name = f"Dr. {appointment.doctor.user.full_name}"

        patient_name = appointment.patient.full_name if appointment.patient else "Patient"
        patient_email = appointment.patient.email if appointment.patient else ""

        start_time = appointment.slot.start_time if appointment.slot else datetime.utcnow()
        end_time = appointment.slot.end_time if appointment.slot else start_time + timedelta(minutes=30)

        summary = f"Clinica Appointment: {patient_name} with {doctor_name} ({specialization})"
        description = (
            f"Clinica Healthcare Consultation\n"
            f"------------------------------------\n"
            f"Doctor: {doctor_name} ({specialization})\n"
            f"Patient: {patient_name} ({patient_email})\n"
            f"Status: {appointment.status.value}\n"
            f"Symptoms / Reason for Visit:\n{appointment.symptoms}\n\n"
            f"Appointment Reference ID: {appointment.id}\n"
            f"Manage in Clinica Portal: http://localhost:5173"
        )

        return {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_time.isoformat() + "Z" if not start_time.isoformat().endswith("Z") else start_time.isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_time.isoformat() + "Z" if not end_time.isoformat().endswith("Z") else end_time.isoformat(),
                "timeZone": "UTC",
            },
            "attendees": [
                {"email": patient_email, "displayName": patient_name}
            ] if patient_email else [],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "email", "minutes": 1440},
                ],
            },
            "extendedProperties": {
                "shared": {
                    "clinica_appointment_id": appointment.id,
                    "clinica_status": appointment.status.value,
                }
            }
        }

    @staticmethod
    def create_calendar_event(
        db: Session,
        account: UserGoogleAccount,
        appointment: Appointment,
    ) -> Optional[str]:
        """
        Create a new event in the user's primary Google Calendar idempotently.
        """
        # Localhost Dev mode simulation
        if not settings.GOOGLE_CLIENT_ID or account.access_token.startswith("mock_access_token"):
            mock_id = f"gcal_evt_{appointment.id[:8]}_{int(datetime.utcnow().timestamp())}"
            log_event("GOOGLE_CALENDAR_EVENT_CREATED_DEV", {
                "user_id": account.user_id,
                "appointment_id": appointment.id,
                "event_id": mock_id,
            })
            return mock_id

        token = GoogleCalendarService.get_valid_access_token(db, account)
        event_body = GoogleCalendarService._build_event_body(appointment)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(GOOGLE_CALENDAR_EVENTS_URL, json=event_body, headers=headers)
                res.raise_for_status()
                data = res.json()
                event_id = data.get("id")
                log_event("GOOGLE_CALENDAR_EVENT_CREATED", {
                    "user_id": account.user_id,
                    "appointment_id": appointment.id,
                    "event_id": event_id,
                })
                return event_id
        except httpx.HTTPStatusError as exc:
            logger.error(f"Google Calendar API create error ({exc.response.status_code}): {exc.response.text}")
            raise
        except Exception as exc:
            logger.error(f"Google Calendar create network error: {exc}")
            raise

    @staticmethod
    def update_calendar_event(
        db: Session,
        account: UserGoogleAccount,
        appointment: Appointment,
        event_id: str,
    ) -> Optional[str]:
        """
        Update an existing event in the user's Google Calendar.
        If the event is not found (404/410), falls back to create_calendar_event.
        """
        if not event_id:
            return GoogleCalendarService.create_calendar_event(db, account, appointment)

        # Localhost Dev mode simulation
        if not settings.GOOGLE_CLIENT_ID or account.access_token.startswith("mock_access_token"):
            log_event("GOOGLE_CALENDAR_EVENT_UPDATED_DEV", {
                "user_id": account.user_id,
                "appointment_id": appointment.id,
                "event_id": event_id,
            })
            return event_id

        token = GoogleCalendarService.get_valid_access_token(db, account)
        event_body = GoogleCalendarService._build_event_body(appointment)

        url = f"{GOOGLE_CALENDAR_EVENTS_URL}/{event_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.patch(url, json=event_body, headers=headers)
                if res.status_code in (404, 410):
                    # Event was removed externally — recreate idempotently
                    logger.warning(f"Event {event_id} not found in Google Calendar; recreating.")
                    return GoogleCalendarService.create_calendar_event(db, account, appointment)
                res.raise_for_status()
                log_event("GOOGLE_CALENDAR_EVENT_UPDATED", {
                    "user_id": account.user_id,
                    "appointment_id": appointment.id,
                    "event_id": event_id,
                })
                return event_id
        except httpx.HTTPStatusError as exc:
            logger.error(f"Google Calendar API update error ({exc.response.status_code}): {exc.response.text}")
            raise
        except Exception as exc:
            logger.error(f"Google Calendar update network error: {exc}")
            raise

    @staticmethod
    def delete_calendar_event(
        db: Session,
        account: UserGoogleAccount,
        event_id: str,
    ) -> bool:
        """
        Delete/cancel an event from the user's Google Calendar.
        Idempotent: Treats 404/410 Not Found as clean success.
        """
        if not event_id:
            return True

        # Localhost Dev mode simulation
        if not settings.GOOGLE_CLIENT_ID or account.access_token.startswith("mock_access_token"):
            log_event("GOOGLE_CALENDAR_EVENT_DELETED_DEV", {
                "user_id": account.user_id,
                "event_id": event_id,
            })
            return True

        token = GoogleCalendarService.get_valid_access_token(db, account)
        url = f"{GOOGLE_CALENDAR_EVENTS_URL}/{event_id}"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.delete(url, headers=headers)
                if res.status_code in (200, 204, 404, 410):
                    log_event("GOOGLE_CALENDAR_EVENT_DELETED", {
                        "user_id": account.user_id,
                        "event_id": event_id,
                    })
                    return True
                res.raise_for_status()
                return True
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 410):
                return True
            logger.error(f"Google Calendar API delete error ({exc.response.status_code}): {exc.response.text}")
            raise
        except Exception as exc:
            logger.error(f"Google Calendar delete network error: {exc}")
            raise

    # ── Master Synchronization Job Handler ──────────────────────────────────────

    @staticmethod
    def process_calendar_sync_job(db: Session, job: BackgroundJob):
        """
        Execute a calendar synchronization job (CREATE, UPDATE, DELETE).
        Called by JobManager worker. Google API failures will be retried automatically.
        Appointment records are NEVER invalidated if this job fails.
        """
        appointment_id = job.payload.get("appointment_id")
        action = job.payload.get("action", "CREATE").upper()
        target_event_id = job.payload.get("google_event_id")

        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            logger.warning(f"Calendar sync job: Appointment {appointment_id} not found.")
            job.result = {"status": "skipped", "reason": "Appointment not found"}
            return

        # Find connected Google accounts for patient and doctor
        accounts_to_sync = []

        patient_account = db.query(UserGoogleAccount).filter(
            UserGoogleAccount.user_id == appointment.patient_id,
            UserGoogleAccount.is_calendar_connected == True,
        ).first()
        if patient_account:
            accounts_to_sync.append(("patient", patient_account))

        if appointment.doctor and appointment.doctor.user_id:
            doctor_account = db.query(UserGoogleAccount).filter(
                UserGoogleAccount.user_id == appointment.doctor.user_id,
                UserGoogleAccount.is_calendar_connected == True,
            ).first()
            if doctor_account:
                accounts_to_sync.append(("doctor", doctor_account))

        if not accounts_to_sync:
            logger.info(f"Calendar sync: No connected Google Calendar for appointment {appointment_id}")
            job.result = {"status": "skipped", "reason": "No connected Google accounts"}
            return

        synced_event_id = appointment.google_event_id or target_event_id
        results = {}

        for role, account in accounts_to_sync:
            try:
                if action == "CREATE":
                    if synced_event_id:
                        # Idempotent: event exists, update it instead of creating duplicates
                        res_id = GoogleCalendarService.update_calendar_event(db, account, appointment, synced_event_id)
                    else:
                        res_id = GoogleCalendarService.create_calendar_event(db, account, appointment)
                    if res_id:
                        synced_event_id = res_id
                    results[role] = {"action": "created", "event_id": res_id}

                elif action == "UPDATE":
                    res_id = GoogleCalendarService.update_calendar_event(db, account, appointment, synced_event_id)
                    if res_id:
                        synced_event_id = res_id
                    results[role] = {"action": "updated", "event_id": res_id}

                elif action == "DELETE":
                    GoogleCalendarService.delete_calendar_event(db, account, synced_event_id)
                    results[role] = {"action": "deleted", "event_id": synced_event_id}

            except Exception as exc:
                logger.error(f"Failed to sync calendar for {role} (user {account.user_id}) on appointment {appointment_id}: {exc}")
                raise

        if action in ("CREATE", "UPDATE") and synced_event_id:
            appointment.google_event_id = synced_event_id
            db.commit()
        elif action == "DELETE":
            appointment.google_event_id = None
            db.commit()

        job.result = {
            "status": "completed",
            "action": action,
            "event_id": synced_event_id,
            "synced_parties": results,
        }
