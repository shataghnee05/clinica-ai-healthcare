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
from datetime import datetime, timedelta
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
    AppointmentStatus,
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


def _enqueue_notification_job(
    db: Session,
    job_type: JobType,
    payload: dict,
    scheduled_at: Optional[datetime] = None,
) -> BackgroundJob:
    job = BackgroundJob(
        id=str(uuid.uuid4()),
        job_type=job_type,
        status=JobStatus.PENDING,
        payload=payload,
        attempts=0,
        max_attempts=3,
        scheduled_at=scheduled_at or datetime.utcnow(),
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
    def schedule_appointment_reminder(db: Session, appointment: Appointment) -> Optional[str]:
        """
        Schedule an appointment reminder background job at configured hours before appointment.
        Guards against duplicate reminder jobs.
        """
        try:
            if not appointment or appointment.status != AppointmentStatus.CONFIRMED:
                return None
            if not appointment.slot or not appointment.slot.start_time:
                return None

            start_time = appointment.slot.start_time
            now = datetime.utcnow()
            lead_hours = getattr(settings, "APPOINTMENT_REMINDER_HOURS_BEFORE", 24)
            reminder_time = start_time - timedelta(hours=lead_hours)

            if start_time <= now:
                # Appointment is in the past
                return None

            scheduled_at = reminder_time if reminder_time > now else now

            # Guard against duplicate pending reminder jobs for this appointment
            existing_jobs = db.query(BackgroundJob).filter(
                BackgroundJob.job_type == JobType.NOTIFY_APPOINTMENT_REMINDER,
                BackgroundJob.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
            ).all()
            for j in existing_jobs:
                if j.payload and j.payload.get("appointment_id") == appointment.id:
                    return j.id

            job = _enqueue_notification_job(
                db=db,
                job_type=JobType.NOTIFY_APPOINTMENT_REMINDER,
                payload={"appointment_id": appointment.id},
                scheduled_at=scheduled_at,
            )
            db.commit()
            log_event("APPOINTMENT_REMINDER_SCHEDULED", {
                "appointment_id": appointment.id,
                "job_id": job.id,
                "scheduled_at": scheduled_at.isoformat(),
            })
            return job.id
        except Exception as exc:
            logger.error("Failed to schedule appointment reminder: %s", exc)
            return None

    @staticmethod
    def cancel_appointment_reminder(db: Session, appointment_id: str) -> int:
        """
        Cancel any pending appointment reminder jobs for a cancelled or rescheduled appointment.
        """
        try:
            pending_jobs = db.query(BackgroundJob).filter(
                BackgroundJob.job_type == JobType.NOTIFY_APPOINTMENT_REMINDER,
                BackgroundJob.status == JobStatus.PENDING,
            ).all()
            cancelled_count = 0
            for j in pending_jobs:
                if j.payload and j.payload.get("appointment_id") == appointment_id:
                    j.status = JobStatus.FAILED
                    j.error_message = "Cancelled due to appointment update / cancellation"
                    cancelled_count += 1
            if cancelled_count > 0:
                db.commit()
                log_event("APPOINTMENT_REMINDER_CANCELLED", {
                    "appointment_id": appointment_id,
                    "count": cancelled_count,
                })
            return cancelled_count
        except Exception as exc:
            logger.error("Failed to cancel appointment reminder: %s", exc)
            return 0

    @staticmethod
    def notify_appointment_reminder(db: Session, appointment: Appointment) -> Optional[str]:
        """
        Send upcoming appointment reminder notification to patient and doctor immediately.
        """
        try:
            patient = appointment.patient
            doctor_user = appointment.doctor.user if appointment.doctor and appointment.doctor.user else None
            doctor_name = f"Dr. {doctor_user.full_name}" if doctor_user else "your doctor"
            specialization = appointment.doctor.specialization if appointment.doctor else "General"
            start_str = appointment.slot.start_time.strftime("%A, %B %d, %Y at %I:%M %p UTC") if appointment.slot and appointment.slot.start_time else "Scheduled Time"

            # 1. Patient Notification
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

            # 2. Doctor Notification
            if doctor_user and doctor_user.email:
                doc_title = f"Upcoming Appointment Reminder: {patient.full_name if patient else 'Patient'}"
                doc_body = (
                    f"Dear {doctor_name},\n\n"
                    f"This is a reminder of your upcoming appointment with patient {patient.full_name if patient else 'Patient'}.\n"
                    f"Date & Time: {start_str}\n"
                    f"Symptoms: {appointment.symptoms or 'Routine consultation'}\n"
                    f"Appointment ID: {appointment.id}\n\n"
                    f"Clinïca Healthcare Team"
                )
                doc_notif = _create_notification(
                    db=db,
                    user_id=doctor_user.id,
                    notif_type=NotificationType.APPOINTMENT_REMINDER,
                    title=doc_title,
                    body=doc_body,
                    reference_id=appointment.id,
                )
                doc_job = _enqueue_notification_job(db, JobType.NOTIFY_APPOINTMENT_REMINDER, {
                    "notification_id": doc_notif.id,
                    "to_email": doctor_user.email,
                    "subject": doc_title,
                    "body": doc_body,
                })
                doc_notif.job_id = doc_job.id

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
        Enqueue MEDICATION_REMINDER background jobs for each MedicationReminder record
        scheduled for the actual dose time (reminder.scheduled_for).
        """
        count = 0
        for reminder in reminders:
            try:
                # Check for existing duplicate job for this reminder
                if reminder.job_id:
                    existing = db.query(BackgroundJob).filter(BackgroundJob.id == reminder.job_id).first()
                    if existing:
                        continue

                med = reminder.medication
                subject, plain_text, html_content = template_medication_reminder(
                    patient_name=patient.full_name,
                    medication_name=med.name if med else "Medication",
                    dosage=med.dosage if med else "",
                    dose_label=reminder.dose_label,
                    instructions=med.instructions if med else "",
                )
                job = _enqueue_notification_job(
                    db=db,
                    job_type=JobType.MEDICATION_REMINDER,
                    payload={
                        "reminder_id": reminder.id,
                        "to_email": patient.email,
                        "subject": subject,
                        "body": plain_text,
                        "html_body": html_content,
                    },
                    scheduled_at=reminder.scheduled_for,
                )
                reminder.job_id = job.id
                count += 1
            except Exception as exc:
                logger.error("Failed to enqueue medication reminder %s: %s", reminder.id, exc)
        return count

    # ── Job Execution Handlers (Executed by Background Job Workers) ──────────

    @staticmethod
    def execute_appointment_reminder_job(db: Session, job: BackgroundJob) -> None:
        """
        Execute scheduled appointment reminder:
        - Verifies appointment is still CONFIRMED (skips if cancelled)
        - Creates in-app notifications and sends transactional emails for patient and doctor
        """
        appointment_id = job.payload.get("appointment_id")
        if not appointment_id:
            notification_id = job.payload.get("notification_id")
            if notification_id:
                to_email = job.payload.get("to_email", "")
                subject = job.payload.get("subject", "")
                body = job.payload.get("body", "")
                html_body = job.payload.get("html_body")
                NotificationService.execute_notification_job(db, notification_id, to_email, subject, body, html_body=html_body)
                return
            raise ValueError("No appointment_id or notification_id in appointment reminder payload")

        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise ValueError(f"Appointment {appointment_id} not found")

        if appointment.status != AppointmentStatus.CONFIRMED:
            logger.info("Skipping reminder for appointment %s because status is %s", appointment.id, appointment.status)
            job.result = {"skipped": True, "reason": f"Appointment status is {appointment.status.value}"}
            db.commit()
            return

        patient = appointment.patient
        doctor_user = appointment.doctor.user if appointment.doctor and appointment.doctor.user else None
        doctor_name = f"Dr. {doctor_user.full_name}" if doctor_user else "your doctor"
        specialization = appointment.doctor.specialization if appointment.doctor else "General"
        start_str = appointment.slot.start_time.strftime("%A, %B %d, %Y at %I:%M %p UTC") if appointment.slot and appointment.slot.start_time else "Scheduled Time"

        provider = get_email_provider()

        # 1. Patient Notification & Email
        if patient:
            subject, plain_text, html_content = template_appointment_reminder(
                patient_name=patient.full_name or "Patient",
                doctor_name=doctor_name,
                specialization=specialization,
                date_time_str=start_str,
                appointment_id=appointment.id,
            )
            patient_notif = _create_notification(
                db=db,
                user_id=patient.id,
                notif_type=NotificationType.APPOINTMENT_REMINDER,
                title=subject,
                body=plain_text,
                reference_id=appointment.id,
            )
            patient_notif.job_id = job.id
            if patient.email:
                p_success, p_error = provider.send_email(patient.email, subject, plain_text, html_body=html_content)
                patient_notif.email_sent = p_success
                patient_notif.email_error = p_error

        # 2. Doctor Notification & Email
        if doctor_user and doctor_user.email:
            doc_subject = f"Upcoming Appointment Reminder: {patient.full_name if patient else 'Patient'}"
            doc_body = (
                f"Dear {doctor_name},\n\n"
                f"This is a reminder of your upcoming appointment with patient {patient.full_name if patient else 'Patient'}.\n"
                f"Date & Time: {start_str}\n"
                f"Symptoms / Reason: {appointment.symptoms or 'Routine consultation'}\n"
                f"Appointment ID: {appointment.id}\n\n"
                f"Clinïca Healthcare Team"
            )
            doc_notif = _create_notification(
                db=db,
                user_id=doctor_user.id,
                notif_type=NotificationType.APPOINTMENT_REMINDER,
                title=doc_subject,
                body=doc_body,
                reference_id=appointment.id,
            )
            doc_notif.job_id = job.id
            d_success, d_error = provider.send_email(doctor_user.email, doc_subject, doc_body)
            doc_notif.email_sent = d_success
            doc_notif.email_error = d_error

        job.result = {"delivered": True, "appointment_id": appointment.id}
        db.commit()
        log_event("APPOINTMENT_REMINDER_EXECUTED", {"appointment_id": appointment.id, "job_id": job.id})

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
        Creates in-app notification record.
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

        # Create in-app notification for patient
        if reminder.patient_id:
            notif = _create_notification(
                db=db,
                user_id=reminder.patient_id,
                notif_type=NotificationType.MEDICATION_REMINDER,
                title=subject,
                body=body,
                reference_id=reminder.id,
            )
            notif.email_sent = success
            notif.email_error = error
            notif.job_id = reminder.job_id

        db.commit()

        if not success and error:
            # Re-raise so JobManager increments attempts and schedules exponential backoff
            raise RuntimeError(f"Medication reminder delivery failed: {error}")
