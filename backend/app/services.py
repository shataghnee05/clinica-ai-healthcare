import uuid
import json
import re
from datetime import datetime, timedelta, date, time
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from fastapi import HTTPException, status

from app.models import (
    User,
    UserRole,
    DoctorProfile,
    DoctorWorkingHours,
    Slot,
    SlotStatus,
    Appointment,
    AppointmentStatus,
    BackgroundJob,
    JobType,
    JobStatus,
    PreVisitSummary,
    Consultation,
    ConsultationStatus,
    Prescription,
    Medication,
    PostVisitSummary,
    AISummaryStatus,
    UrgencyLevel,
    DoctorLeave,
    LeaveStatus,
    Notification,
    MedicationReminder,
    MedicationReminderStatus,
    NotificationType,
    PasswordResetOTP,
)
import random
from app.email_providers import get_email_provider
from app.email_templates import template_password_reset_otp
from app.schemas import (
    UserRegister,
    DoctorCreate,
    DoctorUpdate,
    WorkingHoursUpdate,
    ConfirmAppointmentRequest,
    ConsultationCompleteRequest,
)
from app.jobs import JobManager
from app.ai.service import AIService
from app.security import get_password_hash, verify_password
from app.config import settings
from app.logger import log_event


class AuthService:
    @staticmethod
    def register_user(db: Session, data: UserRegister) -> User:
        clean_email = data.email.strip().lower()
        existing = db.query(User).filter(User.email == clean_email).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered",
            )
        user = User(
            email=clean_email,
            password_hash=get_password_hash(data.password),
            full_name=data.full_name.strip(),
            role=UserRole.PATIENT,
            accepted_insurance=data.accepted_insurance,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        log_event("USER_REGISTERED", {"user_id": user.id, "email": user.email, "role": user.role.value})
        return user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        clean_email = email.strip().lower()
        user = db.query(User).filter(User.email == clean_email).first()
        if not user or not verify_password(password, user.password_hash):
            return None
        log_event("USER_LOGIN", {"user_id": user.id, "email": user.email, "role": user.role.value})
        return user

    @staticmethod
    def authenticate_or_register_google_user(
        db: Session,
        code: str,
        role: UserRole = UserRole.PATIENT,
        redirect_uri: Optional[str] = None,
        current_user: Optional[User] = None,
    ) -> Tuple[User, Dict[str, Any]]:
        from app.google_calendar_service import GoogleCalendarService
        import secrets

        token_data = GoogleCalendarService.exchange_code_for_tokens(code, redirect_uri)
        user_info = token_data.get("user_info", {})
        google_email = (user_info.get("email") or "").strip().lower()
        google_name = (user_info.get("name") or "Google User").strip()

        if not google_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account email not accessible")

        if current_user:
            user = current_user
        else:
            user = db.query(User).filter(User.email == google_email).first()
            if not user:
                # Create user with a secure random hash
                random_pw = secrets.token_urlsafe(32)
                user = User(
                    email=google_email,
                    password_hash=get_password_hash(random_pw),
                    full_name=google_name,
                    role=role if role in (UserRole.PATIENT, UserRole.DOCTOR) else UserRole.PATIENT,
                    accepted_insurance=[],
                )
                db.add(user)
                db.flush()

                # If registering as doctor, create DoctorProfile
                if user.role == UserRole.DOCTOR:
                    profile = DoctorProfile(
                        user_id=user.id,
                        specialization="General Medicine",
                        bio="",
                        slot_duration_minutes=settings.DEFAULT_SLOT_DURATION_MINUTES,
                        is_active=True,
                    )
                    db.add(profile)
                    db.flush()
                db.commit()
                db.refresh(user)
                log_event("USER_REGISTERED_GOOGLE", {"user_id": user.id, "email": user.email, "role": user.role.value})

        # Save Google Account tokens
        GoogleCalendarService.save_user_google_account(db, user.id, token_data)
        log_event("USER_GOOGLE_AUTH_SUCCESS", {"user_id": user.id, "email": user.email})
        return user, token_data

    @staticmethod
    def request_password_reset_otp(db: Session, email: str) -> Dict[str, Any]:
        clean_email = email.strip().lower()
        user = db.query(User).filter(User.email == clean_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this email address. Please verify your email or register."
            )

        # Generate a secure 6-digit numeric OTP
        otp_code = f"{random.randint(100000, 999999)}"
        expires_at = datetime.utcnow() + timedelta(minutes=10)

        # Invalidate any existing unused OTPs for this email
        db.query(PasswordResetOTP).filter(
            PasswordResetOTP.email == clean_email,
            PasswordResetOTP.is_used == False
        ).update({"is_used": True})

        # Create new OTP record
        otp_record = PasswordResetOTP(
            email=clean_email,
            otp_code=otp_code,
            expires_at=expires_at,
            is_used=False,
        )
        db.add(otp_record)
        db.commit()

        # Send email via Email Provider (Resend, SMTP, or Mock)
        subject, plain_text, html_body = template_password_reset_otp(
            user_name=user.full_name,
            otp_code=otp_code,
            expiry_minutes=10,
        )
        email_provider = get_email_provider()
        success, err = email_provider.send_email(
            to_email=clean_email,
            subject=subject,
            body=plain_text,
            html_body=html_body,
        )
        log_event("PASSWORD_RESET_OTP_GENERATED", {
            "email": clean_email,
            "email_sent": success,
            "error": err
        })

        return {
            "status": "success",
            "message": f"Verification code has been sent to {clean_email}.",
            "email": clean_email,
        }

    @staticmethod
    def verify_password_reset_otp(db: Session, email: str, otp: str) -> bool:
        clean_email = email.strip().lower()
        clean_otp = otp.strip()
        record = db.query(PasswordResetOTP).filter(
            PasswordResetOTP.email == clean_email,
            PasswordResetOTP.otp_code == clean_otp,
            PasswordResetOTP.is_used == False,
            PasswordResetOTP.expires_at > datetime.utcnow(),
        ).order_by(PasswordResetOTP.created_at.desc()).first()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code. Please request a new code.",
            )
        return True

    @staticmethod
    def reset_password_with_otp(db: Session, email: str, otp: str, new_password: str) -> User:
        clean_email = email.strip().lower()
        clean_otp = otp.strip()

        user = db.query(User).filter(User.email == clean_email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found."
            )

        # Validate OTP
        record = db.query(PasswordResetOTP).filter(
            PasswordResetOTP.email == clean_email,
            PasswordResetOTP.otp_code == clean_otp,
            PasswordResetOTP.is_used == False,
            PasswordResetOTP.expires_at > datetime.utcnow(),
        ).order_by(PasswordResetOTP.created_at.desc()).first()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code. Please request a new code.",
            )

        if len(new_password) < 6:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 6 characters long.",
            )

        # Mark OTP as used
        record.is_used = True
        user.password_hash = get_password_hash(new_password)
        db.commit()
        db.refresh(user)

        log_event("PASSWORD_RESET_SUCCESS", {"user_id": user.id, "email": user.email})
        return user


class DoctorService:
    @staticmethod
    def create_doctor(db: Session, data: DoctorCreate) -> DoctorProfile:
        clean_email = data.email.strip().lower()
        existing_user = db.query(User).filter(User.email == clean_email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered",
            )
        user = User(
            email=clean_email,
            password_hash=get_password_hash(data.password),
            full_name=data.full_name.strip(),
            role=UserRole.DOCTOR,
            accepted_insurance=data.accepted_insurance,
        )
        db.add(user)
        db.flush()

        profile = DoctorProfile(
            user_id=user.id,
            specialization=data.specialization.strip(),
            bio=data.bio.strip() if data.bio else "",
            slot_duration_minutes=data.slot_duration_minutes,
            is_active=True,
        )
        db.add(profile)
        db.flush()

        for day in range(5):
            wh = DoctorWorkingHours(
                doctor_id=profile.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(17, 0),
                is_day_off=False,
            )
            db.add(wh)
        for day in [5, 6]:
            wh = DoctorWorkingHours(
                doctor_id=profile.id,
                day_of_week=day,
                start_time=time(9, 0),
                end_time=time(13, 0),
                is_day_off=True,
            )
            db.add(wh)

        db.commit()
        db.refresh(profile)
        log_event("DOCTOR_CREATED", {"doctor_id": profile.id, "user_id": user.id, "specialization": profile.specialization})
        return profile

    @staticmethod
    def update_doctor(db: Session, doctor_id: str, data: DoctorUpdate) -> DoctorProfile:
        profile = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        if data.full_name is not None and profile.user:
            profile.user.full_name = data.full_name.strip()
        if data.specialization is not None:
            profile.specialization = data.specialization.strip()
        if data.bio is not None:
            profile.bio = data.bio.strip()
        if data.slot_duration_minutes is not None:
            profile.slot_duration_minutes = data.slot_duration_minutes
        if data.accepted_insurance is not None and profile.user:
            profile.user.accepted_insurance = data.accepted_insurance

        db.commit()
        db.refresh(profile)
        log_event("DOCTOR_UPDATED", {"doctor_id": profile.id})
        return profile

    @staticmethod
    def set_doctor_status(db: Session, doctor_id: str, is_active: bool) -> DoctorProfile:
        profile = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        profile.is_active = is_active
        db.commit()
        db.refresh(profile)
        log_event("DOCTOR_STATUS_CHANGED", {"doctor_id": profile.id, "is_active": is_active})
        return profile

    @staticmethod
    def get_doctors(
        db: Session,
        specialization: Optional[str] = None,
        insurance: Optional[str] = None,
        search: Optional[str] = None,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        query = db.query(DoctorProfile).join(User, DoctorProfile.user_id == User.id)
        if not include_inactive:
            query = query.filter(DoctorProfile.is_active == True)
        
        if specialization:
            query = query.filter(DoctorProfile.specialization.ilike(f"%{specialization.strip()}%"))
        if search:
            s = search.strip()
            query = query.filter(
                or_(
                    User.full_name.ilike(f"%{s}%"),
                    DoctorProfile.specialization.ilike(f"%{s}%"),
                )
            )

        profiles = query.all()
        results = []
        for p in profiles:
            ins_list = p.user.accepted_insurance or []
            if insurance and insurance not in ins_list:
                continue
            results.append({
                "id": p.id,
                "user_id": p.user_id,
                "full_name": p.user.full_name,
                "email": p.user.email,
                "specialization": p.specialization,
                "bio": p.bio,
                "slot_duration_minutes": p.slot_duration_minutes,
                "is_active": p.is_active,
                "accepted_insurance": ins_list,
                "working_hours": p.working_hours,
            })
        return results

    @staticmethod
    def get_doctor_by_id(db: Session, doctor_id: str) -> Optional[Dict[str, Any]]:
        profile = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not profile:
            return None
        return {
            "id": profile.id,
            "user_id": profile.user_id,
            "full_name": profile.user.full_name,
            "email": profile.user.email,
            "specialization": profile.specialization,
            "bio": profile.bio,
            "slot_duration_minutes": profile.slot_duration_minutes,
            "is_active": profile.is_active,
            "accepted_insurance": profile.user.accepted_insurance or [],
            "working_hours": profile.working_hours,
        }

    @staticmethod
    def update_working_hours(db: Session, doctor_id: str, data: WorkingHoursUpdate):
        profile = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        
        for item in data.hours:
            st_parts = [int(x) for x in item.start_time.split(":")]
            et_parts = [int(x) for x in item.end_time.split(":")]
            st = time(st_parts[0], st_parts[1])
            et = time(et_parts[0], et_parts[1])
            if not item.is_day_off and st >= et:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Start time ({item.start_time}) must be earlier than end time ({item.end_time}) on day {item.day_of_week}",
                )

        db.query(DoctorWorkingHours).filter(DoctorWorkingHours.doctor_id == doctor_id).delete()
        for item in data.hours:
            st_parts = [int(x) for x in item.start_time.split(":")]
            et_parts = [int(x) for x in item.end_time.split(":")]
            wh = DoctorWorkingHours(
                doctor_id=doctor_id,
                day_of_week=item.day_of_week,
                start_time=time(st_parts[0], st_parts[1]),
                end_time=time(et_parts[0], et_parts[1]),
                is_day_off=item.is_day_off,
            )
            db.add(wh)
        db.commit()
        log_event("WORKING_HOURS_UPDATED", {"doctor_id": doctor_id})
        return True

class SlotService:
    @staticmethod
    def generate_slots_for_doctor(db: Session, doctor_id: str, start_d: date, end_d: date) -> int:
        if start_d > end_d:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Start date cannot be after end date",
            )

        doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        working_hours_map = {wh.day_of_week: wh for wh in doctor.working_hours}
        duration = timedelta(minutes=doctor.slot_duration_minutes)

        range_start_dt = datetime.combine(start_d, time(0, 0, 0))
        range_end_dt = datetime.combine(end_d, time(23, 59, 59))
        existing_starts = set(
            row[0] for row in db.query(Slot.start_time).filter(
                Slot.doctor_id == doctor_id,
                Slot.start_time >= range_start_dt,
                Slot.start_time <= range_end_dt
            ).all()
        )

        slots_to_create = []
        curr_d = start_d
        while curr_d <= end_d:
            day_wh = working_hours_map.get(curr_d.weekday())
            if day_wh and not day_wh.is_day_off:
                start_dt = datetime.combine(curr_d, day_wh.start_time)
                end_dt = datetime.combine(curr_d, day_wh.end_time)

                slot_start = start_dt
                while slot_start + duration <= end_dt:
                    slot_end = slot_start + duration
                    if slot_start not in existing_starts:
                        slot = Slot(
                            doctor_id=doctor_id,
                            start_time=slot_start,
                            end_time=slot_end,
                            status=SlotStatus.AVAILABLE,
                        )
                        slots_to_create.append(slot)
                        existing_starts.add(slot_start)
                    slot_start = slot_end
            curr_d += timedelta(days=1)

        if slots_to_create:
            db.bulk_save_objects(slots_to_create)
            db.commit()

        log_event("SLOTS_GENERATED", {"doctor_id": doctor_id, "count": len(slots_to_create), "from": str(start_d), "to": str(end_d)})
        return len(slots_to_create)

    @staticmethod
    def get_doctor_slots(db: Session, doctor_id: str, slot_date: Optional[date] = None) -> List[Slot]:
        now = datetime.utcnow()
        expired_holds = db.query(Slot).filter(
            Slot.doctor_id == doctor_id,
            Slot.status == SlotStatus.HELD,
            Slot.hold_expires_at < now
        ).all()
        for s in expired_holds:
            s.status = SlotStatus.AVAILABLE
            s.held_by_patient_id = None
            s.hold_expires_at = None
            log_event("HOLD_EXPIRED", {"slot_id": s.id, "doctor_id": s.doctor_id})
        if expired_holds:
            db.commit()

        query = db.query(Slot).filter(Slot.doctor_id == doctor_id)
        if slot_date:
            day_start = datetime.combine(slot_date, time(0, 0, 0))
            day_end = datetime.combine(slot_date, time(23, 59, 59))
            query = query.filter(Slot.start_time >= day_start, Slot.start_time <= day_end)

        return query.order_by(Slot.start_time.asc()).all()

class AppointmentService:
    @staticmethod
    def hold_slot(db: Session, slot_id: str, patient_id: str) -> Slot:
        now = datetime.utcnow()
        new_expires = now + timedelta(minutes=settings.SLOT_HOLD_DURATION_MINUTES)

        try:
            existing_own = db.query(Slot).filter(
                Slot.id == slot_id,
                Slot.status == SlotStatus.HELD,
                Slot.held_by_patient_id == patient_id,
                Slot.hold_expires_at >= now
            ).first()
            if existing_own:
                existing_own.hold_expires_at = new_expires
                db.commit()
                db.refresh(existing_own)
                return existing_own

            rows_updated = db.query(Slot).filter(
                Slot.id == slot_id,
                or_(
                    Slot.status == SlotStatus.AVAILABLE,
                    and_(
                        Slot.status == SlotStatus.HELD,
                        Slot.hold_expires_at < now
                    )
                )
            ).update({
                Slot.status: SlotStatus.HELD,
                Slot.held_by_patient_id: patient_id,
                Slot.hold_expires_at: new_expires,
                Slot.version: Slot.version + 1
            }, synchronize_session=False)

            if rows_updated == 0:
                db.rollback()
                log_event("BOOKING_CONFLICT", {"slot_id": slot_id, "attempted_by": patient_id})
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Slot is no longer available or is currently held by another patient",
                )

            db.commit()
            slot = db.query(Slot).filter(Slot.id == slot_id).first()
            log_event("SLOT_HELD", {
                "slot_id": slot.id,
                "doctor_id": slot.doctor_id,
                "patient_id": patient_id,
                "expires_at": slot.hold_expires_at.isoformat() if slot.hold_expires_at else None
            })
            return slot
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error acquiring slot hold: {str(e)}"
            )

    @staticmethod
    def release_hold(db: Session, slot_id: str, patient_id: str) -> Slot:
        try:
            slot = db.query(Slot).filter(Slot.id == slot_id).first()
            if not slot:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slot not found")
            if slot.status == SlotStatus.HELD and slot.held_by_patient_id == patient_id:
                slot.status = SlotStatus.AVAILABLE
                slot.held_by_patient_id = None
                slot.hold_expires_at = None
                db.commit()
                db.refresh(slot)
                log_event("HOLD_RELEASED", {"slot_id": slot.id, "patient_id": patient_id})
            return slot
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error releasing slot hold: {str(e)}"
            )

    @staticmethod
    def confirm_appointment(db: Session, data: ConfirmAppointmentRequest, patient_id: str) -> Appointment:
        now = datetime.utcnow()
        clean_symptoms = data.symptoms.strip()
        if len(clean_symptoms) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Symptoms description must be at least 3 characters",
            )

        try:
            rows_updated = db.query(Slot).filter(
                Slot.id == data.slot_id,
                Slot.status == SlotStatus.HELD,
                Slot.held_by_patient_id == patient_id,
                Slot.hold_expires_at >= now
            ).update({
                Slot.status: SlotStatus.BOOKED,
                Slot.hold_expires_at: None,
                Slot.version: Slot.version + 1
            }, synchronize_session=False)

            if rows_updated == 0:
                db.rollback()
                log_event("BOOKING_CONFLICT", {"slot_id": data.slot_id, "patient_id": patient_id, "reason": "No valid active hold"})
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You must have an active unexpired hold on this slot to confirm the appointment",
                )

            slot = db.query(Slot).filter(Slot.id == data.slot_id).first()
            appointment_id = str(uuid.uuid4())
            appointment = Appointment(
                id=appointment_id,
                slot_id=slot.id,
                doctor_id=slot.doctor_id,
                patient_id=patient_id,
                symptoms=clean_symptoms,
                status=AppointmentStatus.CONFIRMED,
                booked_at=now,
            )
            db.add(appointment)
            db.flush()

            # Create PreVisitSummary with initial PENDING status
            pre_summary = PreVisitSummary(
                id=str(uuid.uuid4()),
                appointment_id=appointment.id,
                urgency=UrgencyLevel.LOW,
                chief_complaint="AI Pre-Visit Assessment is being generated...",
                suggested_questions=[],
                status=AISummaryStatus.PENDING,
            )
            db.add(pre_summary)
            db.commit()
            db.refresh(appointment)

            log_event("APPOINTMENT_CONFIRMED", {
                "appointment_id": appointment.id,
                "slot_id": slot.id,
                "doctor_id": slot.doctor_id,
                "patient_id": patient_id,
                "symptoms_length": len(clean_symptoms),
            })

            # Enqueue Pre-Visit Summary Background Job
            try:
                job = JobManager.enqueue_job(db, JobType.PRE_VISIT_SUMMARY, {"appointment_id": appointment.id})
                appointment._enqueued_job_id = job.id
            except Exception as e:
                log_event("AI_JOB_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(e)})

            # Enqueue Confirmation Notification Email Job (failure-tolerant)
            try:
                from app.notification_service import NotificationService
                NotificationService.notify_appointment_confirmation(db, appointment)
            except Exception as e:
                log_event("NOTIFICATION_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(e)})

            # Enqueue Google Calendar Sync Background Job (failure-tolerant)
            try:
                cal_job = JobManager.enqueue_job(
                    db,
                    JobType.GOOGLE_CALENDAR_SYNC,
                    {"appointment_id": appointment.id, "action": "CREATE"},
                )
                appointment._calendar_job_id = cal_job.id
            except Exception as e:
                log_event("CALENDAR_JOB_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(e)})

            # Automatically schedule Appointment Reminder Job (failure-tolerant)
            try:
                from app.notification_service import NotificationService
                NotificationService.schedule_appointment_reminder(db, appointment)
            except Exception as e:
                log_event("REMINDER_SCHEDULE_WARNING", {"appointment_id": appointment.id, "error": str(e)})

            return appointment

        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            log_event("BOOKING_ERROR", {"slot_id": data.slot_id, "patient_id": patient_id, "error": str(e)})
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Appointment could not be confirmed due to a conflicting booking or transaction error.",
            )

    @staticmethod
    def cancel_appointment(
        db: Session,
        appointment_id: str,
        user: User,
        reason: Optional[str] = None,
        cancelled_by_leave: bool = False,
    ) -> Appointment:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        is_patient = appointment.patient_id == user.id
        is_doc = appointment.doctor and appointment.doctor.user_id == user.id
        is_admin = user.role == UserRole.ADMIN

        if not (is_patient or is_doc or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to cancel this appointment")

        if appointment.status == AppointmentStatus.CANCELLED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Appointment is already cancelled")

        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancellation_reason = reason
        if appointment.slot:
            appointment.slot.status = SlotStatus.AVAILABLE
            appointment.slot.held_by_patient_id = None
            appointment.slot.hold_expires_at = None

        db.commit()
        db.refresh(appointment)
        log_event("APPOINTMENT_CANCELLED", {"appointment_id": appointment.id, "cancelled_by": user.id, "reason": reason})

        # Enqueue cancellation notification (failure-tolerant — outside main transaction)
        try:
            from app.notification_service import NotificationService
            NotificationService.notify_appointment_cancellation(db, appointment, reason, cancelled_by_leave)
        except Exception as exc:
            log_event("NOTIFICATION_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})

        # Enqueue Google Calendar deletion job (failure-tolerant)
        try:
            cal_job = JobManager.enqueue_job(
                db,
                JobType.GOOGLE_CALENDAR_SYNC,
                {
                    "appointment_id": appointment.id,
                    "action": "DELETE",
                    "google_event_id": appointment.google_event_id,
                },
            )
            appointment._calendar_job_id = cal_job.id
        except Exception as exc:
            log_event("CALENDAR_JOB_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})

        # Cancel pending appointment reminder jobs (failure-tolerant)
        try:
            from app.notification_service import NotificationService
            NotificationService.cancel_appointment_reminder(db, appointment.id)
        except Exception as exc:
            log_event("REMINDER_CANCEL_WARNING", {"appointment_id": appointment.id, "error": str(exc)})

        return appointment

    @staticmethod
    def reschedule_appointment(
        db: Session,
        appointment_id: str,
        new_slot_id: str,
        current_user: User,
    ) -> Appointment:
        """
        Reschedule an existing appointment to a new slot.
        Permits Patient, Doctor, or Admin to reschedule.
        Permits rescheduling of CONFIRMED or CANCELLED (e.g. leave-disrupted) appointments.
        """
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        is_patient = appointment.patient_id == current_user.id
        is_doctor = appointment.doctor and appointment.doctor.user_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        if not (is_patient or is_doctor or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to reschedule this appointment")

        if appointment.status not in (AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only confirmed or leave-affected appointments can be rescheduled",
            )

        if appointment.slot_id == new_slot_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New slot is the same as the current slot")

        old_slot = appointment.slot
        target_patient_id = appointment.patient_id

        # 1. Hold new slot on behalf of the patient (concurrency-safe optimistic lock)
        new_slot = AppointmentService.hold_slot(db, new_slot_id, target_patient_id)

        # 2. Atomically book new slot
        now = datetime.utcnow()
        rows_updated = db.query(Slot).filter(
            Slot.id == new_slot_id,
            Slot.status == SlotStatus.HELD,
            Slot.held_by_patient_id == target_patient_id,
            Slot.hold_expires_at >= now,
        ).update({
            Slot.status: SlotStatus.BOOKED,
            Slot.hold_expires_at: None,
            Slot.version: Slot.version + 1,
        }, synchronize_session=False)

        if rows_updated == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Could not book new slot — concurrent conflict detected",
            )

        # 3. Release old slot if not already available
        old_slot_id = old_slot.id if old_slot else None
        if old_slot and old_slot.status != SlotStatus.AVAILABLE:
            old_slot.status = SlotStatus.AVAILABLE
            old_slot.held_by_patient_id = None
            old_slot.hold_expires_at = None

        # 4. Update appointment to CONFIRMED on the new slot
        new_slot_obj = db.query(Slot).filter(Slot.id == new_slot_id).first()
        appointment.rescheduled_from_slot_id = old_slot_id
        appointment.slot_id = new_slot_id
        appointment.doctor_id = new_slot_obj.doctor_id
        appointment.status = AppointmentStatus.CONFIRMED
        appointment.cancellation_reason = None

        db.commit()
        db.refresh(appointment)
        log_event("APPOINTMENT_RESCHEDULED", {
            "appointment_id": appointment.id,
            "old_slot_id": old_slot_id,
            "new_slot_id": new_slot_id,
            "patient_id": target_patient_id,
            "rescheduled_by": current_user.role.value,
        })

        # 5. Enqueue notifications (failure-tolerant)
        try:
            from app.notification_service import NotificationService
            NotificationService.notify_appointment_confirmation(db, appointment)
        except Exception as exc:
            log_event("NOTIFICATION_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})

        # 6. Enqueue Google Calendar update job (failure-tolerant)
        try:
            cal_job = JobManager.enqueue_job(
                db,
                JobType.GOOGLE_CALENDAR_SYNC,
                {"appointment_id": appointment.id, "action": "UPDATE"},
            )
            appointment._calendar_job_id = cal_job.id
        except Exception as exc:
            log_event("CALENDAR_JOB_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})

        # 7. Reschedule reminder: cancel old reminder and schedule reminder for new slot time
        try:
            from app.notification_service import NotificationService
            NotificationService.cancel_appointment_reminder(db, appointment.id)
            NotificationService.schedule_appointment_reminder(db, appointment)
        except Exception as exc:
            log_event("REMINDER_RESCHEDULE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})

        return appointment

    @staticmethod
    def _serialize_appointment(a: Appointment) -> Dict[str, Any]:
        return {
            "id": a.id,
            "slot_id": a.slot_id,
            "doctor_id": a.doctor_id,
            "patient_id": a.patient_id,
            "symptoms": a.symptoms,
            "status": a.status,
            "booked_at": a.booked_at,
            "cancellation_reason": a.cancellation_reason,
            "rescheduled_from_slot_id": a.rescheduled_from_slot_id,
            "doctor_name": a.doctor.user.full_name if a.doctor and a.doctor.user else "Unknown Doctor",
            "doctor_specialization": a.doctor.specialization if a.doctor else "General",
            "patient_name": a.patient.full_name if a.patient else "Patient",
            "patient_email": a.patient.email if a.patient else "",
            "start_time": a.slot.start_time if a.slot else None,
            "end_time": a.slot.end_time if a.slot else None,
            "google_event_id": a.google_event_id,
        }

    @staticmethod
    def get_patient_appointments(db: Session, patient_id: str) -> List[Dict[str, Any]]:
        appointments = db.query(Appointment).filter(Appointment.patient_id == patient_id).order_by(Appointment.booked_at.desc()).all()
        return [AppointmentService._serialize_appointment(a) for a in appointments]

    @staticmethod
    def get_doctor_agenda(db: Session, doctor_user_id: str) -> List[Dict[str, Any]]:
        profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == doctor_user_id).first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor profile not found")

        appointments = db.query(Appointment).filter(Appointment.doctor_id == profile.id).order_by(Appointment.booked_at.desc()).all()
        return [AppointmentService._serialize_appointment(a) for a in appointments]

    @staticmethod
    def get_system_stats(db: Session) -> Dict[str, Any]:
        now = datetime.utcnow()
        total_patients = db.query(func.count(User.id)).filter(User.role == UserRole.PATIENT).scalar() or 0
        total_doctors = db.query(func.count(DoctorProfile.id)).scalar() or 0
        total_slots = db.query(func.count(Slot.id)).scalar() or 0
        total_appointments = db.query(func.count(Appointment.id)).scalar() or 0
        total_holds_active = db.query(func.count(Slot.id)).filter(
            Slot.status == SlotStatus.HELD,
            Slot.hold_expires_at >= now
        ).scalar() or 0

        return {
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "total_slots": total_slots,
            "total_appointments": total_appointments,
            "total_holds_active": total_holds_active,
            "server_time": now,
        }

class AdminService:
    @staticmethod
    def get_registered_patients(db: Session) -> List[Dict[str, Any]]:
        patients = db.query(User).filter(User.role == UserRole.PATIENT).order_by(User.created_at.desc()).all()
        results = []
        for p in patients:
            appt_count = db.query(func.count(Appointment.id)).filter(Appointment.patient_id == p.id).scalar() or 0
            results.append({
                "id": p.id,
                "email": p.email,
                "full_name": p.full_name,
                "role": p.role,
                "accepted_insurance": p.accepted_insurance or [],
                "created_at": p.created_at,
                "total_appointments": appt_count,
            })
        return results

    @staticmethod
    def delete_patient(db: Session, patient_id: str) -> bool:
        patient = db.query(User).filter(User.id == patient_id, User.role == UserRole.PATIENT).first()
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

        db.query(Slot).filter(Slot.held_by_patient_id == patient_id).update({
            Slot.held_by_patient_id: None,
            Slot.hold_expires_at: None,
            Slot.status: SlotStatus.AVAILABLE,
        }, synchronize_session=False)

        db.delete(patient)
        db.commit()
        log_event("PATIENT_DELETED", {"patient_id": patient_id})
        return True

    @staticmethod
    def delete_doctor(db: Session, doctor_id: str) -> bool:
        profile = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
        user = profile.user
        db.delete(profile)
        if user:
            db.delete(user)
        db.commit()
        log_event("DOCTOR_DELETED", {"doctor_id": doctor_id})
        return True


# ── Phase 2B: Doctor Leave Service ───────────────────────────────────────────

# ── Phase 2B: Doctor Leave Service ───────────────────────────────────────────

class DoctorLeaveService:
    @staticmethod
    def _enrich_leave(leave: DoctorLeave) -> DoctorLeave:
        """Attach doctor metadata to leave instance for API serialization."""
        if leave and leave.doctor:
            if leave.doctor.user:
                leave.doctor_name = leave.doctor.user.full_name
                leave.doctor_email = leave.doctor.user.email
            leave.doctor_specialization = leave.doctor.specialization
        return leave

    @staticmethod
    def _get_conflicting_appointments(
        db: Session,
        doctor_id: str,
        start_date: date,
        end_date: date,
    ) -> List[Appointment]:
        """Return CONFIRMED appointments whose slots fall within the leave window."""
        leave_start_dt = datetime.combine(start_date, time(0, 0, 0))
        leave_end_dt = datetime.combine(end_date, time(23, 59, 59))

        return (
            db.query(Appointment)
            .join(Slot, Appointment.slot_id == Slot.id)
            .filter(
                Appointment.doctor_id == doctor_id,
                Appointment.status == AppointmentStatus.CONFIRMED,
                Slot.start_time >= leave_start_dt,
                Slot.start_time <= leave_end_dt,
            )
            .all()
        )

    @staticmethod
    def preview_leave(
        db: Session,
        doctor_id: str,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        """
        Return a preview of which appointments would be affected by a leave.
        Does NOT create any records or cancel anything.
        """
        if start_date > end_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start date must be before end date")

        doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        conflicting = DoctorLeaveService._get_conflicting_appointments(db, doctor_id, start_date, end_date)

        affected = []
        for a in conflicting:
            affected.append({
                "appointment_id": a.id,
                "patient_name": a.patient.full_name if a.patient else "Unknown",
                "patient_email": a.patient.email if a.patient else "",
                "start_time": a.slot.start_time if a.slot else None,
                "end_time": a.slot.end_time if a.slot else None,
                "symptoms": a.symptoms,
                "status": a.status,
            })

        return {
            "doctor_id": doctor_id,
            "doctor_name": doctor.user.full_name if doctor.user else "",
            "start_date": str(start_date),
            "end_date": str(end_date),
            "affected_appointments": affected,
            "affected_count": len(affected),
        }

    @staticmethod
    def apply_leave(
        db: Session,
        doctor_id: str,
        start_date: date,
        end_date: date,
        reason: str,
        doctor_user: User,
    ) -> DoctorLeave:
        """
        Doctor applies for a leave. Record is created with status PENDING.
        Appointments are NOT cancelled until admin approves.
        """
        if start_date > end_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start date must be before end date")

        doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        conflicting = DoctorLeaveService._get_conflicting_appointments(db, doctor_id, start_date, end_date)

        leave = DoctorLeave(
            id=str(uuid.uuid4()),
            doctor_id=doctor_id,
            start_date=start_date,
            end_date=end_date,
            reason=reason or "",
            status=LeaveStatus.PENDING,
            affected_appointments_count=len(conflicting),
            created_at=datetime.utcnow(),
        )
        db.add(leave)
        db.commit()
        db.refresh(leave)

        log_event("DOCTOR_LEAVE_APPLIED", {
            "leave_id": leave.id,
            "doctor_id": doctor_id,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "affected_count": len(conflicting),
        })

        return DoctorLeaveService._enrich_leave(leave)

    @staticmethod
    def approve_leave(
        db: Session,
        leave_id: str,
        admin: User,
    ) -> DoctorLeave:
        """
        Admin approves a leave request.
        Cancels conflicting CONFIRMED appointments, releases slots, dispatches patient notifications,
        and dispatches approval notification to the doctor.
        """
        leave = db.query(DoctorLeave).filter(DoctorLeave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

        leave.status = LeaveStatus.APPROVED
        leave.reviewed_by_admin_id = admin.id
        leave.reviewed_at = datetime.utcnow()
        leave.confirmed_at = datetime.utcnow()

        conflicting = DoctorLeaveService._get_conflicting_appointments(db, leave.doctor_id, leave.start_date, leave.end_date)
        cancelled_count = 0

        for appointment in conflicting:
            appointment.status = AppointmentStatus.CANCELLED
            appointment.cancellation_reason = f"Doctor on approved leave ({leave.start_date} – {leave.end_date})"
            if appointment.slot:
                appointment.slot.status = SlotStatus.AVAILABLE
                appointment.slot.held_by_patient_id = None
                appointment.slot.hold_expires_at = None
            cancelled_count += 1

        leave.affected_appointments_count = cancelled_count
        db.commit()

        log_event("DOCTOR_LEAVE_APPROVED", {
            "leave_id": leave.id,
            "doctor_id": leave.doctor_id,
            "admin_id": admin.id,
            "cancelled_count": cancelled_count,
        })

        # Notify patients whose appointments were cancelled
        db.refresh(leave)
        for appointment in conflicting:
            try:
                from app.notification_service import NotificationService
                NotificationService.notify_doctor_leave_to_patient(db, appointment, leave)
                NotificationService.cancel_appointment_reminder(db, appointment.id)
            except Exception as exc:
                log_event("NOTIFICATION_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})
            try:
                JobManager.enqueue_job(
                    db,
                    JobType.GOOGLE_CALENDAR_SYNC,
                    {
                        "appointment_id": appointment.id,
                        "action": "DELETE",
                        "google_event_id": appointment.google_event_id,
                    },
                )
            except Exception as exc:
                log_event("CALENDAR_JOB_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})

        # Notify the Doctor that leave was approved
        try:
            from app.notification_service import NotificationService
            NotificationService.notify_doctor_leave_approval(db, leave)
        except Exception as exc:
            log_event("DOCTOR_NOTIF_WARNING", {"leave_id": leave.id, "error": str(exc)})

        try:
            db.commit()
        except Exception:
            db.rollback()

        return DoctorLeaveService._enrich_leave(leave)

    @staticmethod
    def reject_leave(
        db: Session,
        leave_id: str,
        rejection_reason: str,
        admin: User,
    ) -> DoctorLeave:
        """
        Admin rejects a leave request.
        Updates status to REJECTED, records rejection_reason, and notifies the doctor.
        Patient appointments remain intact.
        """
        leave = db.query(DoctorLeave).filter(DoctorLeave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")

        leave.status = LeaveStatus.REJECTED
        leave.rejection_reason = rejection_reason or "Leave request was not approved by administration."
        leave.reviewed_by_admin_id = admin.id
        leave.reviewed_at = datetime.utcnow()
        db.commit()

        log_event("DOCTOR_LEAVE_REJECTED", {
            "leave_id": leave.id,
            "doctor_id": leave.doctor_id,
            "admin_id": admin.id,
            "reason": rejection_reason,
        })

        # Notify doctor with the rejection reason
        db.refresh(leave)
        try:
            from app.notification_service import NotificationService
            NotificationService.notify_doctor_leave_rejection(db, leave, leave.rejection_reason)
            db.commit()
        except Exception as exc:
            log_event("DOCTOR_NOTIF_WARNING", {"leave_id": leave.id, "error": str(exc)})

        return DoctorLeaveService._enrich_leave(leave)

    @staticmethod
    def confirm_leave(
        db: Session,
        doctor_id: str,
        start_date: date,
        end_date: date,
        reason: str,
        admin: User,
    ) -> DoctorLeave:
        """
        Admin explicitly creates and confirms a leave directly.
        """
        if start_date > end_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start date must be before end date")

        doctor = db.query(DoctorProfile).filter(DoctorProfile.id == doctor_id).first()
        if not doctor:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

        leave = DoctorLeave(
            id=str(uuid.uuid4()),
            doctor_id=doctor_id,
            start_date=start_date,
            end_date=end_date,
            reason=reason or "",
            status=LeaveStatus.APPROVED,
            created_by_admin_id=admin.id,
            reviewed_by_admin_id=admin.id,
            confirmed_at=datetime.utcnow(),
            reviewed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.add(leave)
        db.flush()

        conflicting = DoctorLeaveService._get_conflicting_appointments(db, doctor_id, start_date, end_date)
        cancelled_count = 0

        for appointment in conflicting:
            appointment.status = AppointmentStatus.CANCELLED
            appointment.cancellation_reason = f"Doctor on approved leave ({start_date} – {end_date})"
            if appointment.slot:
                appointment.slot.status = SlotStatus.AVAILABLE
                appointment.slot.held_by_patient_id = None
                appointment.slot.hold_expires_at = None
            cancelled_count += 1

        leave.affected_appointments_count = cancelled_count
        db.commit()

        log_event("DOCTOR_LEAVE_CONFIRMED", {
            "leave_id": leave.id,
            "doctor_id": doctor_id,
            "admin_id": admin.id,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "cancelled_count": cancelled_count,
        })

        db.refresh(leave)
        for appointment in conflicting:
            try:
                from app.notification_service import NotificationService
                NotificationService.notify_doctor_leave_to_patient(db, appointment, leave)
                NotificationService.cancel_appointment_reminder(db, appointment.id)
            except Exception as exc:
                log_event("NOTIFICATION_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})
            try:
                JobManager.enqueue_job(
                    db,
                    JobType.GOOGLE_CALENDAR_SYNC,
                    {
                        "appointment_id": appointment.id,
                        "action": "DELETE",
                        "google_event_id": appointment.google_event_id,
                    },
                )
            except Exception as exc:
                log_event("CALENDAR_JOB_ENQUEUE_WARNING", {"appointment_id": appointment.id, "error": str(exc)})

        try:
            db.commit()
        except Exception:
            db.rollback()

        return DoctorLeaveService._enrich_leave(leave)

    @staticmethod
    def get_leaves(
        db: Session,
        doctor_id: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[DoctorLeave]:
        query = db.query(DoctorLeave)
        if doctor_id:
            query = query.filter(DoctorLeave.doctor_id == doctor_id)
        if status_filter:
            query = query.filter(DoctorLeave.status == status_filter)

        leaves = query.order_by(
            (DoctorLeave.status == LeaveStatus.PENDING).desc(),
            DoctorLeave.created_at.desc(),
            DoctorLeave.start_date.desc(),
        ).all()

        for l in leaves:
            DoctorLeaveService._enrich_leave(l)
        return leaves

    @staticmethod
    def delete_leave(db: Session, leave_id: str, user: User) -> bool:
        leave = db.query(DoctorLeave).filter(DoctorLeave.id == leave_id).first()
        if not leave:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave record not found")
        db.delete(leave)
        db.commit()
        log_event("DOCTOR_LEAVE_DELETED", {"leave_id": leave_id, "user_id": user.id})
        return True


# ── Phase 2B: Medication Reminder Service ────────────────────────────────────

_FREQUENCY_MAP = {
    "once daily": 1,
    "once a day": 1,
    "1 time": 1,
    "1x daily": 1,
    "1x": 1,
    "daily": 1,
    "every day": 1,
    "q.d.": 1,
    "qd": 1,
    "twice daily": 2,
    "twice a day": 2,
    "2 times": 2,
    "2x daily": 2,
    "2x": 2,
    "b.i.d.": 2,
    "bid": 2,
    "three times daily": 3,
    "three times a day": 3,
    "3 times": 3,
    "3x daily": 3,
    "3x": 3,
    "t.i.d.": 3,
    "tid": 3,
    "four times daily": 4,
    "four times a day": 4,
    "4 times": 4,
    "4x daily": 4,
    "4x": 4,
    "q.i.d.": 4,
    "qid": 4,
    "as needed": 0,
    "prn": 0,
    "p.r.n.": 0,
    "every 24 hours": 1,
    "every 24h": 1,
    "every 24 hrs": 1,
    "every 12 hours": 2,
    "every 12h": 2,
    "every 12 hrs": 2,
    "every 8 hours": 3,
    "every 8h": 3,
    "every 8 hrs": 3,
    "every 6 hours": 4,
    "every 6h": 4,
    "every 6 hrs": 4,
    "every 4 hours": 4,
    "every 4h": 4,
    "every 4 hrs": 4,
}

_DOSE_TIMES_BY_COUNT = {
    1: [("08:00", "Morning dose")],
    2: [("08:00", "Morning dose"), ("20:00", "Evening dose")],
    3: [("08:00", "Morning dose"), ("14:00", "Afternoon dose"), ("20:00", "Evening dose")],
    4: [("07:00", "Morning dose"), ("12:00", "Midday dose"), ("17:00", "Afternoon dose"), ("21:00", "Night dose")],
}

def _parse_frequency(frequency_str: str) -> int:
    """Return doses per day from frequency string. Returns 0 for 'as needed'."""
    f = frequency_str.strip().lower()
    for key, val in _FREQUENCY_MAP.items():
        if key in f:
            return val
    # Check for interval pattern like "every X hours" or "every X hrs" or "every X h"
    m_int = re.search(r"every\s*(\d+)\s*(?:hour|hr|h)", f)
    if m_int:
        hrs = int(m_int.group(1))
        if hrs > 0:
            return max(1, min(24 // hrs, 4))
    # Fallback: look for digit
    m = re.search(r"(\d+)", f)
    if m:
        return min(int(m.group(1)), 4)
    return 1  # default once daily

def _parse_duration_days(duration_str: str) -> int:
    """Return number of days from duration string like '7 days', '2 weeks'."""
    d = duration_str.strip().lower()
    m = re.search(r"(\d+)\s*(day|week|month)", d)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        if unit == "week":
            return n * 7
        elif unit == "month":
            return n * 30
        return n
    return 7  # default 7 days


class MedicationReminderService:
    @staticmethod
    def generate_reminders_for_prescription(
        db: Session,
        prescription: Prescription,
        consultation: Consultation,
    ) -> List[MedicationReminder]:
        """
        Generate MedicationReminder rows for each medication in the prescription.
        Reminders start from today (or med.start_date) and span the medication duration.
        Respects completed/cancelled appointments, start/end dates, and prevents duplicate reminders.
        """
        if consultation.appointment and consultation.appointment.status == AppointmentStatus.CANCELLED:
            log_event("REMINDER_GENERATION_SKIPPED", {"consultation_id": consultation.id, "reason": "Appointment cancelled"})
            return []

        patient = consultation.patient
        if not patient:
            return []

        today = datetime.utcnow().date()
        created_reminders: List[MedicationReminder] = []

        for med in prescription.medications:
            doses_per_day = _parse_frequency(med.frequency)
            if doses_per_day == 0:
                # "As needed" — generate a single reminder at start
                doses_per_day = 1
                duration_days = 1
            else:
                if med.start_date and med.end_date and med.end_date >= med.start_date:
                    duration_days = (med.end_date - med.start_date).days + 1
                else:
                    duration_days = _parse_duration_days(med.duration)

            dose_times = _DOSE_TIMES_BY_COUNT.get(doses_per_day, _DOSE_TIMES_BY_COUNT[1])

            start_d = med.start_date or today
            med.start_date = start_d
            med.end_date = start_d + timedelta(days=duration_days - 1)

            for day_offset in range(duration_days):
                reminder_date = start_d + timedelta(days=day_offset)
                for dose_time_str, dose_label in dose_times:
                    h, m_min = map(int, dose_time_str.split(":"))
                    scheduled_for = datetime.combine(reminder_date, time(h, m_min))

                    # Guard against duplicate MedicationReminder
                    existing = db.query(MedicationReminder).filter(
                        MedicationReminder.medication_id == med.id,
                        MedicationReminder.patient_id == patient.id,
                        MedicationReminder.scheduled_for == scheduled_for,
                    ).first()
                    if existing:
                        continue

                    reminder = MedicationReminder(
                        id=str(uuid.uuid4()),
                        medication_id=med.id,
                        patient_id=patient.id,
                        scheduled_for=scheduled_for,
                        dose_label=dose_label,
                        status=MedicationReminderStatus.PENDING,
                    )
                    db.add(reminder)
                    created_reminders.append(reminder)

        db.flush()

        # Enqueue notification jobs for each reminder
        try:
            from app.notification_service import NotificationService
            NotificationService.enqueue_medication_reminders(db, created_reminders, patient)
            db.commit()
        except Exception as exc:
            log_event("REMINDER_ENQUEUE_WARNING", {"consultation_id": consultation.id, "error": str(exc)})
            try:
                db.rollback()
            except Exception:
                pass

        log_event("MEDICATION_REMINDERS_GENERATED", {
            "consultation_id": consultation.id,
            "patient_id": patient.id,
            "reminder_count": len(created_reminders),
        })
        return created_reminders

    @staticmethod
    def get_patient_reminders(db: Session, patient_id: str) -> List[MedicationReminder]:
        return (
            db.query(MedicationReminder)
            .filter(MedicationReminder.patient_id == patient_id)
            .order_by(MedicationReminder.scheduled_for.asc())
            .all()
        )


# ── Phase 2B: Notification Query Service ─────────────────────────────────────

class NotificationQueryService:
    @staticmethod
    def get_user_notifications(db: Session, user_id: str) -> List[Notification]:
        return (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .all()
        )

    @staticmethod
    def mark_read(db: Session, notification_id: str, user_id: str) -> Notification:
        notif = db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        ).first()
        if not notif:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        notif.is_read = True
        db.commit()
        db.refresh(notif)
        return notif


# ── ConsultationService (Phase 2A, extended for Phase 2B) ────────────────────

class ConsultationService:
    @staticmethod
    def get_pre_visit_summary(db: Session, appointment_id: str, current_user: User) -> PreVisitSummary:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        is_doctor = appointment.doctor and appointment.doctor.user_id == current_user.id
        is_patient = appointment.patient_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        if not (is_doctor or is_patient or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this summary")

        summary = db.query(PreVisitSummary).filter(PreVisitSummary.appointment_id == appointment_id).first()
        if not summary:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pre-visit summary is still generating or unavailable")
        return summary

    @staticmethod
    def generate_pre_visit_summary(
        db: Session,
        appointment_id: str,
        provider_name: Optional[str],
        current_user: User,
    ) -> PreVisitSummary:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        is_doctor = appointment.doctor and appointment.doctor.user_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        if not (is_doctor or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned doctor or admin can generate AI summaries")

        summary = db.query(PreVisitSummary).filter(PreVisitSummary.appointment_id == appointment_id).first()
        if not summary:
            summary = PreVisitSummary(
                id=str(uuid.uuid4()),
                appointment_id=appointment_id,
                urgency=UrgencyLevel.LOW,
                chief_complaint="AI Pre-Visit Assessment is generating...",
                suggested_questions=[],
                status=AISummaryStatus.PENDING,
            )
            db.add(summary)
            db.flush()

        try:
            ai_result = AIService.generate_pre_visit_summary(appointment.symptoms, provider_name)
            summary.urgency = UrgencyLevel(ai_result.urgency)
            summary.chief_complaint = ai_result.chief_complaint
            summary.suggested_questions = ai_result.suggested_questions
            summary.status = AISummaryStatus.GENERATED
            summary.raw_response = json.dumps(ai_result.model_dump())
            db.commit()
            db.refresh(summary)
            log_event("AI_PRE_VISIT_SUMMARY_GENERATED", {
                "appointment_id": appointment_id,
                "provider": provider_name or "default",
                "urgency": summary.urgency.value,
            })
            return summary
        except Exception as exc:
            db.rollback()
            summary = db.query(PreVisitSummary).filter(PreVisitSummary.appointment_id == appointment_id).first()
            if summary:
                summary.status = AISummaryStatus.FAILED
                db.commit()
            log_event("AI_GENERATION_FAILED", {
                "appointment_id": appointment_id,
                "provider": provider_name or "default",
                "error": str(exc),
            })
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to generate summary with provider '{provider_name or 'default'}': {str(exc)}",
            )

    @staticmethod
    def start_consultation(db: Session, appointment_id: str, current_user: User) -> Consultation:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

        is_doctor = appointment.doctor and appointment.doctor.user_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        if not (is_doctor or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned doctor or admin can start a consultation")

        consultation = db.query(Consultation).filter(Consultation.appointment_id == appointment_id).first()
        if not consultation:
            consultation = Consultation(
                id=str(uuid.uuid4()),
                appointment_id=appointment_id,
                doctor_id=appointment.doctor_id,
                patient_id=appointment.patient_id,
                status=ConsultationStatus.IN_PROGRESS,
                started_at=datetime.utcnow(),
            )
            db.add(consultation)
            db.commit()
            db.refresh(consultation)
            log_event("CONSULTATION_STARTED", {"consultation_id": consultation.id, "appointment_id": appointment_id})

        return consultation

    @staticmethod
    def complete_consultation(db: Session, consultation_id: str, data: ConsultationCompleteRequest, current_user: User) -> Consultation:
        consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
        if not consultation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")

        is_doctor = consultation.doctor and consultation.doctor.user_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        if not (is_doctor or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the assigned doctor can complete this consultation")

        now = datetime.utcnow()
        consultation.diagnosis = data.diagnosis.strip()
        consultation.clinical_notes = data.clinical_notes.strip()
        consultation.follow_up_instructions = data.follow_up_instructions.strip()
        consultation.status = ConsultationStatus.COMPLETED
        consultation.completed_at = now

        if consultation.appointment:
            consultation.appointment.status = AppointmentStatus.COMPLETED

        prescription = db.query(Prescription).filter(Prescription.consultation_id == consultation_id).first()
        if not prescription:
            prescription = Prescription(
                id=str(uuid.uuid4()),
                consultation_id=consultation_id,
                notes=data.prescription_notes or "",
            )
            db.add(prescription)
            db.flush()
        else:
            prescription.notes = data.prescription_notes or ""
            db.query(Medication).filter(Medication.prescription_id == prescription.id).delete()

        for med in data.medications:
            med_item = Medication(
                id=str(uuid.uuid4()),
                prescription_id=prescription.id,
                name=med.name.strip(),
                dosage=med.dosage.strip(),
                frequency=med.frequency.strip(),
                duration=med.duration.strip(),
                instructions=med.instructions.strip() if med.instructions else "",
            )
            db.add(med_item)

        # Create PostVisitSummary with initial PENDING status
        post_summary = db.query(PostVisitSummary).filter(PostVisitSummary.consultation_id == consultation_id).first()
        if not post_summary:
            post_summary = PostVisitSummary(
                id=str(uuid.uuid4()),
                consultation_id=consultation_id,
                visit_explanation="AI Post-Visit Summary is being generated...",
                medication_schedule=[],
                follow_up_steps=consultation.follow_up_instructions or "Follow standard care guidelines.",
                status=AISummaryStatus.PENDING,
            )
            db.add(post_summary)
        else:
            post_summary.status = AISummaryStatus.PENDING

        db.commit()
        db.refresh(consultation)

        # Enqueue Post-Visit Summary Background Job
        try:
            job = JobManager.enqueue_job(db, JobType.POST_VISIT_SUMMARY, {"consultation_id": consultation.id})
            consultation._enqueued_job_id = job.id
        except Exception as e:
            log_event("AI_JOB_ENQUEUE_WARNING", {"consultation_id": consultation.id, "error": str(e)})

        # Phase 2B: Generate medication reminders from prescription
        try:
            db.refresh(prescription)
            MedicationReminderService.generate_reminders_for_prescription(db, prescription, consultation)
        except Exception as exc:
            log_event("REMINDER_GENERATION_WARNING", {"consultation_id": consultation.id, "error": str(exc)})

        log_event("CONSULTATION_COMPLETED", {
            "consultation_id": consultation.id,
            "appointment_id": consultation.appointment_id,
            "doctor_id": consultation.doctor_id,
            "medications_count": len(data.medications),
        })
        return consultation

    @staticmethod
    def get_consultation_details(db: Session, appointment_id: str, current_user: User) -> Dict[str, Any]:
        consultation = db.query(Consultation).filter(Consultation.appointment_id == appointment_id).first()
        if not consultation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No consultation recorded for this appointment")

        is_doctor = consultation.doctor and consultation.doctor.user_id == current_user.id
        is_patient = consultation.patient_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        if not (is_doctor or is_patient or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this consultation")

        # Patients cannot view private clinical_notes
        clinical_notes_val = consultation.clinical_notes if (is_doctor or is_admin) else None

        rx_data = None
        if consultation.prescription:
            rx_data = {
                "id": consultation.prescription.id,
                "notes": consultation.prescription.notes,
                "created_at": consultation.prescription.created_at,
                "medications": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "dosage": m.dosage,
                        "frequency": m.frequency,
                        "duration": m.duration,
                        "instructions": m.instructions,
                    }
                    for m in consultation.prescription.medications
                ],
            }

        post_summary_data = None
        if consultation.post_visit_summary:
            post_summary_data = {
                "id": consultation.post_visit_summary.id,
                "consultation_id": consultation.post_visit_summary.consultation_id,
                "visit_explanation": consultation.post_visit_summary.visit_explanation,
                "medication_schedule": consultation.post_visit_summary.medication_schedule or [],
                "follow_up_steps": consultation.post_visit_summary.follow_up_steps,
                "status": consultation.post_visit_summary.status,
                "created_at": consultation.post_visit_summary.created_at,
            }

        pre_summary_data = None
        if consultation.appointment and consultation.appointment.pre_visit_summary:
            pvs = consultation.appointment.pre_visit_summary
            pre_summary_data = {
                "id": pvs.id,
                "appointment_id": pvs.appointment_id,
                "urgency": pvs.urgency,
                "chief_complaint": pvs.chief_complaint,
                "suggested_questions": pvs.suggested_questions or [],
                "status": pvs.status,
                "created_at": pvs.created_at,
            }

        return {
            "id": consultation.id,
            "appointment_id": consultation.appointment_id,
            "doctor_id": consultation.doctor_id,
            "patient_id": consultation.patient_id,
            "diagnosis": consultation.diagnosis,
            "clinical_notes": clinical_notes_val,
            "follow_up_instructions": consultation.follow_up_instructions,
            "status": consultation.status,
            "started_at": consultation.started_at,
            "completed_at": consultation.completed_at,
            "doctor_name": consultation.doctor.user.full_name if consultation.doctor and consultation.doctor.user else "Doctor",
            "doctor_specialization": consultation.doctor.specialization if consultation.doctor else "General",
            "patient_name": consultation.patient.full_name if consultation.patient else "Patient",
            "patient_email": consultation.patient.email if consultation.patient else "",
            "prescription": rx_data,
            "post_visit_summary": post_summary_data,
            "pre_visit_summary": pre_summary_data,
        }

    @staticmethod
    def get_post_visit_summary(db: Session, consultation_id: str, current_user: User) -> PostVisitSummary:
        consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
        if not consultation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation not found")

        is_doctor = consultation.doctor and consultation.doctor.user_id == current_user.id
        is_patient = consultation.patient_id == current_user.id
        is_admin = current_user.role == UserRole.ADMIN

        if not (is_doctor or is_patient or is_admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to access this summary")

        summary = db.query(PostVisitSummary).filter(PostVisitSummary.consultation_id == consultation_id).first()
        if not summary:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post-visit summary is still generating or unavailable")

        return summary
