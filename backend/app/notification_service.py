"""
Phase 2B — Provider-independent Notification Service.

Design contract:
- Email send failures NEVER raise exceptions to callers.
- Appointment / Consultation state is NEVER modified here.
- All outbound communication is best-effort and failure-tolerant.
"""
import logging
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.logger import log_event
from app.models import (
    Notification,
    NotificationType,
    BackgroundJob,
    JobType,
    JobStatus,
    User,
    Appointment,
    DoctorLeave,
    Medication,
    MedicationReminder,
)

logger = logging.getLogger(__name__)


# ── Low-level SMTP sender ────────────────────────────────────────────────────

def _send_email(to_email: str, subject: str, body: str) -> Tuple[bool, Optional[str]]:
    """
    Send a plain-text email via SMTP.
    Returns (success, error_message).
    Never raises — failure is logged and returned as a flag.
    """
    if not settings.NOTIFICATION_ENABLED or not settings.SMTP_HOST:
        # No-op when unconfigured — this is intentional for local / test environments
        logger.debug("Notification skipped (NOTIFICATION_ENABLED=False or SMTP_HOST empty): %s", subject)
        return True, None  # treat as success so job completes cleanly

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.NOTIFICATION_FROM_EMAIL
        msg["To"] = to_email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.NOTIFICATION_FROM_EMAIL, [to_email], msg.as_string())

        log_event("EMAIL_SENT", {"to": to_email, "subject": subject})
        return True, None

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Email send failed to %s: %s", to_email, error_msg)
        log_event("EMAIL_FAILED", {"to": to_email, "subject": subject, "error": error_msg})
        return False, error_msg


# ── Notification record helpers ───────────────────────────────────────────────

def _create_notification(
    db: Session,
    user_id: str,
    notif_type: NotificationType,
    title: str,
    body: str,
    reference_id: Optional[str] = None,
) -> Notification:
    notif = Notification(
        id=str(uuid.uuid4()),
        user_id=user_id,
        notification_type=notif_type,
        title=title,
        body=body,
        reference_id=reference_id,
        is_read=False,
        email_sent=False,
    )
    db.add(notif)
    db.flush()
    return notif


def _enqueue_notification_job(db: Session, job_type: JobType, payload: dict) -> BackgroundJob:
    job = BackgroundJob(
        id=str(uuid.uuid4()),
        job_type=job_type,
        status=JobStatus.PENDING,
        payload=payload,
        attempts=0,
        max_attempts=3,
        scheduled_at=datetime.utcnow(),
    )
    db.add(job)
    db.flush()
    return job


# ── Public API ────────────────────────────────────────────────────────────────

class NotificationService:
    """
    Enqueues notification background jobs and creates Notification inbox records.
    All methods are safe to call inside appointment transactions —
    any failure here must not roll back appointment state.
    """

    @staticmethod
    def notify_appointment_confirmation(db: Session, appointment: Appointment) -> Optional[str]:
        """Create notification + enqueue email job for appointment confirmation."""
        try:
            patient = appointment.patient
            doctor_name = appointment.doctor.user.full_name if appointment.doctor and appointment.doctor.user else "your doctor"
            start = appointment.slot.start_time.strftime("%Y-%m-%d %H:%M") if appointment.slot else "scheduled time"
            title = "Appointment Confirmed"
            body = (
                f"Dear {patient.full_name},\n\n"
                f"Your appointment with {doctor_name} has been confirmed.\n"
                f"Date/Time: {start}\n\n"
                f"Please arrive 10 minutes early.\n\nClinïca Team"
            )
            notif = _create_notification(db, patient.id, NotificationType.APPOINTMENT_CONFIRMATION, title, body, appointment.id)
            job = _enqueue_notification_job(db, JobType.NOTIFY_APPOINTMENT_CONFIRMATION, {
                "notification_id": notif.id,
                "to_email": patient.email,
                "subject": title,
                "body": body,
            })
            notif.job_id = job.id
            db.commit()
            log_event("NOTIFICATION_ENQUEUED", {"type": "CONFIRMATION", "appointment_id": appointment.id})
            return job.id
        except Exception as exc:
            logger.error("Failed to enqueue confirmation notification: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def notify_appointment_cancellation(
        db: Session,
        appointment: Appointment,
        reason: Optional[str] = None,
        cancelled_by_leave: bool = False,
    ) -> Optional[str]:
        """Create notification + enqueue email job for appointment cancellation."""
        try:
            patient = appointment.patient
            doctor_name = appointment.doctor.user.full_name if appointment.doctor and appointment.doctor.user else "your doctor"
            start = appointment.slot.start_time.strftime("%Y-%m-%d %H:%M") if appointment.slot else "scheduled time"
            reason_text = f"\nReason: {reason}" if reason else ""
            leave_text = "\nThis cancellation was due to the doctor's approved leave." if cancelled_by_leave else ""
            title = "Appointment Cancelled"
            body = (
                f"Dear {patient.full_name},\n\n"
                f"Your appointment with {doctor_name} on {start} has been cancelled.{reason_text}{leave_text}\n\n"
                f"Please rebook at your convenience.\n\nClinïca Team"
            )
            notif = _create_notification(db, patient.id, NotificationType.APPOINTMENT_CANCELLATION, title, body, appointment.id)
            job = _enqueue_notification_job(db, JobType.NOTIFY_APPOINTMENT_CANCELLATION, {
                "notification_id": notif.id,
                "to_email": patient.email,
                "subject": title,
                "body": body,
            })
            notif.job_id = job.id
            db.commit()
            log_event("NOTIFICATION_ENQUEUED", {"type": "CANCELLATION", "appointment_id": appointment.id})
            return job.id
        except Exception as exc:
            logger.error("Failed to enqueue cancellation notification: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def notify_doctor_leave_to_patient(
        db: Session,
        appointment: Appointment,
        leave: DoctorLeave,
    ) -> Optional[str]:
        """Notify a patient whose appointment was cancelled due to doctor leave."""
        try:
            patient = appointment.patient
            doctor_name = appointment.doctor.user.full_name if appointment.doctor and appointment.doctor.user else "your doctor"
            start = appointment.slot.start_time.strftime("%Y-%m-%d %H:%M") if appointment.slot else "scheduled time"
            title = "Appointment Cancelled – Doctor on Leave"
            body = (
                f"Dear {patient.full_name},\n\n"
                f"We regret to inform you that your appointment with {doctor_name} on {start} "
                f"has been cancelled due to the doctor's approved leave "
                f"({leave.start_date} – {leave.end_date}).\n\n"
                f"Please rebook at your earliest convenience.\n\nClinïca Team"
            )
            notif = _create_notification(db, patient.id, NotificationType.DOCTOR_LEAVE, title, body, appointment.id)
            job = _enqueue_notification_job(db, JobType.NOTIFY_DOCTOR_LEAVE, {
                "notification_id": notif.id,
                "to_email": patient.email,
                "subject": title,
                "body": body,
            })
            notif.job_id = job.id
            db.flush()
            log_event("NOTIFICATION_ENQUEUED", {"type": "DOCTOR_LEAVE", "appointment_id": appointment.id, "leave_id": leave.id})
            return job.id
        except Exception as exc:
            logger.error("Failed to enqueue doctor-leave notification: %s", exc)
            return None

    @staticmethod
    def notify_doctor_leave_approval(
        db: Session,
        leave: DoctorLeave,
    ) -> Optional[str]:
        """Notify the doctor that their leave request has been approved by admin."""
        try:
            doc_user = leave.doctor.user if leave.doctor else None
            if not doc_user:
                return None
            title = "Leave Request Approved"
            body = (
                f"Dear Dr. {doc_user.full_name},\n\n"
                f"Your leave application for the period {leave.start_date} to {leave.end_date} "
                f"has been APPROVED by the hospital administration.\n\n"
                f"Any conflicting patient appointments have been automatically cancelled and patients notified.\n\n"
                f"Clinica Administration"
            )
            notif = _create_notification(db, doc_user.id, NotificationType.DOCTOR_LEAVE_APPROVAL, title, body, leave.id)
            db.flush()
            log_event("NOTIFICATION_ENQUEUED", {"type": "DOCTOR_LEAVE_APPROVAL", "leave_id": leave.id, "doctor_id": leave.doctor_id})
            return notif.id
        except Exception as exc:
            logger.error("Failed to enqueue doctor leave approval notification: %s", exc)
            return None

    @staticmethod
    def notify_doctor_leave_rejection(
        db: Session,
        leave: DoctorLeave,
        reason: str,
    ) -> Optional[str]:
        """Notify the doctor that their leave request was rejected by admin with a reason."""
        try:
            doc_user = leave.doctor.user if leave.doctor else None
            if not doc_user:
                return None
            title = "Leave Request Not Approved"
            body = (
                f"Dear Dr. {doc_user.full_name},\n\n"
                f"Your leave application for {leave.start_date} to {leave.end_date} was NOT approved by administration.\n\n"
                f"Reason from Administration:\n\"{reason}\"\n\n"
                f"Please contact the administrative office if you need further clarification.\n\n"
                f"Clinica Administration"
            )
            notif = _create_notification(db, doc_user.id, NotificationType.DOCTOR_LEAVE_REJECTION, title, body, leave.id)
            db.flush()
            log_event("NOTIFICATION_ENQUEUED", {"type": "DOCTOR_LEAVE_REJECTION", "leave_id": leave.id, "doctor_id": leave.doctor_id})
            return notif.id
        except Exception as exc:
            logger.error("Failed to enqueue doctor leave rejection notification: %s", exc)
            return None

    @staticmethod
    def enqueue_medication_reminders(
        db: Session,
        reminders: list,   # list[MedicationReminder]
        patient: User,
    ) -> int:
        """Enqueue MEDICATION_REMINDER jobs for each MedicationReminder row."""
        count = 0
        for reminder in reminders:
            try:
                med = reminder.medication
                title = f"Medication Reminder: {med.name}"
                body = (
                    f"Dear {patient.full_name},\n\n"
                    f"This is a reminder to take your medication:\n"
                    f"  {med.name} — {med.dosage} ({reminder.dose_label})\n"
                    f"  Instructions: {med.instructions or 'As directed'}\n\n"
                    f"Clinïca Team"
                )
                job = _enqueue_notification_job(db, JobType.MEDICATION_REMINDER, {
                    "reminder_id": reminder.id,
                    "to_email": patient.email,
                    "subject": title,
                    "body": body,
                })
                reminder.job_id = job.id
                count += 1
            except Exception as exc:
                logger.error("Failed to enqueue medication reminder %s: %s", reminder.id, exc)
        return count

    # ── Job execution helpers (called by JobManager) ─────────────────────────

    @staticmethod
    def execute_notification_job(db: Session, notification_id: str, to_email: str, subject: str, body: str) -> None:
        """
        Send the email and update the Notification record.
        Raises on failure so JobManager can retry.
        """
        notif = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notif and notification_id:
            raise ValueError(f"Notification {notification_id} not found")

        success, error = _send_email(to_email, subject, body)
        if notif:
            notif.email_sent = success
            notif.email_error = error
        # If email fails, re-raise so JobManager retries — but Notification record is still saved
        if not success and error:
            raise RuntimeError(f"Email send failed: {error}")

    @staticmethod
    def execute_medication_reminder_job(db: Session, reminder_id: str, to_email: str, subject: str, body: str) -> None:
        """Send medication reminder email and update MedicationReminder row."""
        reminder = db.query(MedicationReminder).filter(MedicationReminder.id == reminder_id).first()
        if not reminder:
            raise ValueError(f"Medication reminder {reminder_id} not found")

        success, error = _send_email(to_email, subject, body)
        if success:
            from app.models import MedicationReminderStatus
            reminder.status = MedicationReminderStatus.SENT
            reminder.sent_at = datetime.utcnow()
        else:
            from app.models import MedicationReminderStatus
            reminder.status = MedicationReminderStatus.FAILED
            reminder.error_message = error
        if not success and error:
            raise RuntimeError(f"Medication reminder email failed: {error}")
