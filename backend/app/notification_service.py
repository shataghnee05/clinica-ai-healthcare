"""
Provider-independent Notification & Email Service for Clinica.

Features:
- Backed by Resend REST API (with SMTP and Mock provider fallbacks)
- Sends transactional emails asynchronously through BackgroundJob system
- Non-blocking: API requests return immediately
- Exponential backoff retries on email delivery failures
- Comprehensive error tracking in database (Notification & BackgroundJob tables)
- Rich responsive HTML and accessible plain-text templates

Supported Notifications:
1. Appointment Confirmation (Patient & Doctor)
2. Appointment Cancellation (Patient & Doctor)
3. Doctor Leave Notification (Affected Patients & Doctor)
4. Appointment Reminder (Upcoming consultation)
5. Medication Reminder (Prescribed patient doses)
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, List, Tuple
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
    MedicationReminderStatus,
)
from app.email_providers import get_email_provider
from app.email_templates import (
    template_appointment_confirmation,
    template_appointment_cancellation,
    template_doctor_leave,
    template_appointment_reminder,
    template_medication_reminder,
)

logger = logging.getLogger(__name__)


# ── Notification Record & Job Helpers ────────────────────────────────────────

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


# ── Notification Service Core ────────────────────────────────────────────────

class NotificationService:
    """
    Provider-independent notification dispatcher.
    Enqueues notification background jobs and creates in-app notifications.
    Fault-tolerant: failures here NEVER roll back appointment transactions.
    """

    @staticmethod
    def notify_appointment_confirmation(db: Session, appointment: Appointment) -> Optional[str]:
        """
        Send confirmation email and in-app notification when an appointment is confirmed.
        Notifies patient with appointment details and doctor with agenda update.
        """
        try:
            patient = appointment.patient
            doctor_user = appointment.doctor.user if appointment.doctor and appointment.doctor.user else None
            doctor_name = f"Dr. {doctor_user.full_name}" if doctor_user else "Doctor"
            specialization = appointment.doctor.specialization if appointment.doctor else "General"
            start_str = appointment.slot.start_time.strftime("%A, %B %d, %Y at %I:%M %p UTC") if appointment.slot and appointment.slot.start_time else "Scheduled Time"

            # 1. Patient Notification
            subject, plain_text, html_content = template_appointment_confirmation(
                patient_name=patient.full_name if patient else "Patient",
                doctor_name=doctor_name,
                specialization=specialization,
                date_time_str=start_str,
                symptoms=appointment.symptoms or "Routine consultation",
                appointment_id=appointment.id,
            )

            notif = _create_notification(
                db=db,
                user_id=patient.id,
                notif_type=NotificationType.APPOINTMENT_CONFIRMATION,
                title=subject,
                body=plain_text,
                reference_id=appointment.id,
            )
            job = _enqueue_notification_job(db, JobType.NOTIFY_APPOINTMENT_CONFIRMATION, {
                "notification_id": notif.id,
                "to_email": patient.email,
                "subject": subject,
                "body": plain_text,
                "html_body": html_content,
            })
            notif.job_id = job.id

            # 2. Doctor Notification (if doctor account exists)
            if doctor_user and doctor_user.email:
                doc_title = f"New Appointment Booked: {patient.full_name if patient else 'Patient'}"
                doc_body = (
                    f"Dear {doctor_name},\n\n"
                    f"A new appointment has been confirmed with patient {patient.full_name if patient else 'Patient'}.\n"
                    f"Date & Time: {start_str}\n"
                    f"Symptoms: {appointment.symptoms}\n\n"
                    f"Reference: {appointment.id}\nClinïca Portal"
                )
                doc_notif = _create_notification(
                    db=db,
                    user_id=doctor_user.id,
                    notif_type=NotificationType.APPOINTMENT_CONFIRMATION,
                    title=doc_title,
                    body=doc_body,
                    reference_id=appointment.id,
                )
                doc_job = _enqueue_notification_job(db, JobType.NOTIFY_APPOINTMENT_CONFIRMATION, {
                    "notification_id": doc_notif.id,
                    "to_email": doctor_user.email,
                    "subject": doc_title,
                    "body": doc_body,
                })
                doc_notif.job_id = doc_job.id

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
        """
        Send cancellation email and in-app notification when an appointment is cancelled.
        """
        try:
            patient = appointment.patient
            doctor_user = appointment.doctor.user if appointment.doctor and appointment.doctor.user else None
            doctor_name = f"Dr. {doctor_user.full_name}" if doctor_user else "your doctor"
            start_str = appointment.slot.start_time.strftime("%A, %B %d, %Y at %I:%M %p UTC") if appointment.slot and appointment.slot.start_time else "Scheduled Time"

            # 1. Patient Notification
            subject, plain_text, html_content = template_appointment_cancellation(
                patient_name=patient.full_name if patient else "Patient",
                doctor_name=doctor_name,
                date_time_str=start_str,
                reason=reason or "Schedule update",
                cancelled_by_leave=cancelled_by_leave,
            )

            notif = _create_notification(
                db=db,
                user_id=patient.id,
                notif_type=NotificationType.APPOINTMENT_CANCELLATION,
                title=subject,
                body=plain_text,
                reference_id=appointment.id,
            )
            job = _enqueue_notification_job(db, JobType.NOTIFY_APPOINTMENT_CANCELLATION, {
                "notification_id": notif.id,
                "to_email": patient.email,
                "subject": subject,
                "body": plain_text,
                "html_body": html_content,
            })
            notif.job_id = job.id

            # 2. Doctor Notification
            if doctor_user and doctor_user.email:
                doc_title = f"Appointment Cancelled: {patient.full_name if patient else 'Patient'}"
                doc_body = (
                    f"Dear {doctor_name},\n\n"
                    f"The appointment on {start_str} with {patient.full_name if patient else 'Patient'} has been cancelled.\n"
                    f"Reason: {reason or 'Patient cancellation'}\n\n"
                    f"The slot has been restored to available status."
                )
                doc_notif = _create_notification(
                    db=db,
                    user_id=doctor_user.id,
                    notif_type=NotificationType.APPOINTMENT_CANCELLATION,
                    title=doc_title,
                    body=doc_body,
                    reference_id=appointment.id,
                )
                doc_job = _enqueue_notification_job(db, JobType.NOTIFY_APPOINTMENT_CANCELLATION, {
                    "notification_id": doc_notif.id,
                    "to_email": doctor_user.email,
                    "subject": doc_title,
                    "body": doc_body,
                })
                doc_notif.job_id = doc_job.id

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
        """
        Notify patient when their appointment is cancelled due to doctor approved leave.
        """
        try:
            patient = appointment.patient
            doctor_user = appointment.doctor.user if appointment.doctor and appointment.doctor.user else None
            doctor_name = f"Dr. {doctor_user.full_name}" if doctor_user else "your doctor"
            start_str = appointment.slot.start_time.strftime("%A, %B %d, %Y at %I:%M %p UTC") if appointment.slot and appointment.slot.start_time else "Scheduled Time"
            leave_period = f"{leave.start_date} to {leave.end_date}"

            subject, plain_text, html_content = template_doctor_leave(
                patient_name=patient.full_name if patient else "Patient",
                doctor_name=doctor_name,
                date_time_str=start_str,
                leave_period=leave_period,
            )

            notif = _create_notification(
                db=db,
                user_id=patient.id,
                notif_type=NotificationType.DOCTOR_LEAVE,
                title=subject,
                body=plain_text,
                reference_id=appointment.id,
            )
            job = _enqueue_notification_job(db, JobType.NOTIFY_DOCTOR_LEAVE, {
                "notification_id": notif.id,
                "to_email": patient.email,
                "subject": subject,
                "body": plain_text,
                "html_body": html_content,
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
        """
        Notify doctor that their leave request has been approved by admin.
        """
        try:
            doc_user = leave.doctor.user if leave.doctor else None
            if not doc_user:
                return None
            title = "Leave Request Approved"
            body = (
                f"Dear Dr. {doc_user.full_name},\n\n"
                f"Your leave application for the period {leave.start_date} to {leave.end_date} "
                f"has been APPROVED by hospital administration.\n\n"
                f"Any conflicting patient appointments have been automatically cancelled and patients notified.\n\n"
                f"Clinïca Administration"
            )
            notif = _create_notification(db, doc_user.id, NotificationType.DOCTOR_LEAVE_APPROVAL, title, body, leave.id)
            if doc_user.email:
                job = _enqueue_notification_job(db, JobType.NOTIFY_DOCTOR_LEAVE, {
                    "notification_id": notif.id,
                    "to_email": doc_user.email,
                    "subject": title,
                    "body": body,
                })
                notif.job_id = job.id
            db.flush()
            log_event("NOTIFICATION_ENQUEUED", {"type": "DOCTOR_LEAVE_APPROVAL", "leave_id": leave.id})
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
        """
        Notify doctor that their leave request was rejected by admin.
        """
        try:
            doc_user = leave.doctor.user if leave.doctor else None
            if not doc_user:
                return None
            title = "Leave Request Not Approved"
            body = (
                f"Dear Dr. {doc_user.full_name},\n\n"
                f"Your leave application for {leave.start_date} to {leave.end_date} was NOT approved by administration.\n\n"
                f"Reason from Administration:\n\"{reason}\"\n\n"
                f"Please contact administration if you require further details.\n\n"
                f"Clinïca Administration"
            )
            notif = _create_notification(db, doc_user.id, NotificationType.DOCTOR_LEAVE_REJECTION, title, body, leave.id)
            if doc_user.email:
                job = _enqueue_notification_job(db, JobType.NOTIFY_DOCTOR_LEAVE, {
                    "notification_id": notif.id,
                    "to_email": doc_user.email,
                    "subject": title,
                    "body": body,
                })
                notif.job_id = job.id
            db.flush()
            log_event("NOTIFICATION_ENQUEUED", {"type": "DOCTOR_LEAVE_REJECTION", "leave_id": leave.id})
            return notif.id
        except Exception as exc:
            logger.error("Failed to enqueue doctor leave rejection notification: %s", exc)
            return None

    @staticmethod
    def notify_appointment_reminder(db: Session, appointment: Appointment) -> Optional[str]:
        """
        Send upcoming appointment reminder notification to patient and doctor.
        """
        try:
            patient = appointment.patient
            doctor_user = appointment.doctor.user if appointment.doctor and appointment.doctor.user else None
            doctor_name = f"Dr. {doctor_user.full_name}" if doctor_user else "your doctor"
            specialization = appointment.doctor.specialization if appointment.doctor else "General"
            start_str = appointment.slot.start_time.strftime("%A, %B %d, %Y at %I:%M %p UTC") if appointment.slot and appointment.slot.start_time else "Scheduled Time"

            subject, plain_text, html_content = template_appointment_reminder(
                patient_name=patient.full_name if patient else "Patient",
                doctor_name=doctor_name,
                specialization=specialization,
                date_time_str=start_str,
                appointment_id=appointment.id,
            )

            notif = _create_notification(
                db=db,
                user_id=patient.id,
                notif_type=NotificationType.APPOINTMENT_REMINDER,
                title=subject,
                body=plain_text,
                reference_id=appointment.id,
            )
            job = _enqueue_notification_job(db, JobType.NOTIFY_APPOINTMENT_REMINDER, {
                "notification_id": notif.id,
                "to_email": patient.email,
                "subject": subject,
                "body": plain_text,
                "html_body": html_content,
            })
            notif.job_id = job.id
            db.commit()
            log_event("NOTIFICATION_ENQUEUED", {"type": "APPOINTMENT_REMINDER", "appointment_id": appointment.id})
            return job.id
        except Exception as exc:
            logger.error("Failed to enqueue appointment reminder notification: %s", exc)
            return None

    @staticmethod
    def enqueue_medication_reminders(
        db: Session,
        reminders: list,   # list[MedicationReminder]
        patient: User,
    ) -> int:
        """
        Enqueue MEDICATION_REMINDER background jobs for each MedicationReminder record.
        """
        count = 0
        for reminder in reminders:
            try:
                med = reminder.medication
                subject, plain_text, html_content = template_medication_reminder(
                    patient_name=patient.full_name,
                    medication_name=med.name,
                    dosage=med.dosage,
                    dose_label=reminder.dose_label,
                    instructions=med.instructions or "",
                )
                job = _enqueue_notification_job(db, JobType.MEDICATION_REMINDER, {
                    "reminder_id": reminder.id,
                    "to_email": patient.email,
                    "subject": subject,
                    "body": plain_text,
                    "html_body": html_content,
                })
                reminder.job_id = job.id
                count += 1
            except Exception as exc:
                logger.error("Failed to enqueue medication reminder %s: %s", reminder.id, exc)
        return count

    # ── Job Execution Handlers (Executed by Background Job Workers) ──────────

    @staticmethod
    def execute_notification_job(
        db: Session,
        notification_id: str,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> None:
        """
        Execute an email delivery job via the configured Email Provider.
        Updates Notification status and records errors on failure for retry.
        """
        notif = db.query(Notification).filter(Notification.id == notification_id).first()
        if not notif and notification_id:
            raise ValueError(f"Notification record {notification_id} not found")

        provider = get_email_provider()
        success, error = provider.send_email(to_email, subject, body, html_body=html_body)

        if notif:
            notif.email_sent = success
            notif.email_error = error
            db.commit()

        if not success and error:
            # Re-raise so JobManager increments attempts and schedules exponential backoff
            raise RuntimeError(f"Email delivery failed: {error}")

    @staticmethod
    def execute_medication_reminder_job(
        db: Session,
        reminder_id: str,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
    ) -> None:
        """
        Execute a medication reminder email delivery job.
        Updates MedicationReminder status to SENT or FAILED.
        """
        reminder = db.query(MedicationReminder).filter(MedicationReminder.id == reminder_id).first()
        if not reminder:
            raise ValueError(f"Medication reminder record {reminder_id} not found")

        provider = get_email_provider()
        success, error = provider.send_email(to_email, subject, body, html_body=html_body)

        if success:
            reminder.status = MedicationReminderStatus.SENT
            reminder.sent_at = datetime.utcnow()
            reminder.error_message = None
        else:
            reminder.status = MedicationReminderStatus.FAILED
            reminder.error_message = error

        db.commit()

        if not success and error:
            # Re-raise so JobManager increments attempts and schedules exponential backoff
            raise RuntimeError(f"Medication reminder delivery failed: {error}")
