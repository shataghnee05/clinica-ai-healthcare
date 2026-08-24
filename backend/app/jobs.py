import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.models import (
    SessionLocal,
    BackgroundJob,
    JobType,
    JobStatus,
    Appointment,
    AppointmentStatus,
    PreVisitSummary,
    Consultation,
    PostVisitSummary,
    MedicationReminder,
    MedicationReminderStatus,
    AISummaryStatus,
    UrgencyLevel,
)
from app.ai.service import AIService

logger = logging.getLogger(__name__)

class JobManager:
    @staticmethod
    def enqueue_job(
        db: Session,
        job_type: JobType,
        payload: Dict[str, Any],
        scheduled_at: Optional[datetime] = None,
    ) -> BackgroundJob:
        job = BackgroundJob(
            job_type=job_type,
            status=JobStatus.PENDING,
            payload=payload,
            attempts=0,
            max_attempts=3,
            scheduled_at=scheduled_at or datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def process_job(db: Session, job_id: str, force: bool = False) -> bool:
        job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
        if not job or job.status in (JobStatus.COMPLETED, JobStatus.PROCESSING):
            return False

        if not force and job.scheduled_at and job.scheduled_at > datetime.utcnow():
            return False

        job.status = JobStatus.PROCESSING
        job.locked_at = datetime.utcnow()
        job.attempts += 1
        db.commit()

        try:
            if job.job_type == JobType.PRE_VISIT_SUMMARY:
                JobManager._handle_pre_visit_summary(db, job)
            elif job.job_type == JobType.POST_VISIT_SUMMARY:
                JobManager._handle_post_visit_summary(db, job)
            elif job.job_type in (
                JobType.NOTIFY_APPOINTMENT_CONFIRMATION,
                JobType.NOTIFY_APPOINTMENT_CANCELLATION,
                JobType.NOTIFY_APPOINTMENT_REMINDER,
                JobType.NOTIFY_DOCTOR_LEAVE,
            ):
                JobManager._handle_notification_job(db, job)
            elif job.job_type == JobType.MEDICATION_REMINDER:
                JobManager._handle_medication_reminder(db, job)
            elif job.job_type == JobType.GOOGLE_CALENDAR_SYNC:
                JobManager._handle_google_calendar_sync(db, job)

            job.status = JobStatus.COMPLETED
            job.error_message = None
            job.updated_at = datetime.utcnow()
            db.commit()
            return True

        except Exception as exc:
            logger.error(f"Error executing background job {job.id} (attempt {job.attempts}): {exc}", exc_info=True)
            db.rollback()

            job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
            if job:
                job.error_message = str(exc)
                if job.attempts >= job.max_attempts:
                    job.status = JobStatus.FAILED

                    if job.job_type == JobType.PRE_VISIT_SUMMARY:
                        appt_id = job.payload.get("appointment_id")
                        summary = db.query(PreVisitSummary).filter(PreVisitSummary.appointment_id == appt_id).first()
                        if summary:
                            summary.status = AISummaryStatus.FAILED
                    elif job.job_type == JobType.POST_VISIT_SUMMARY:
                        cons_id = job.payload.get("consultation_id")
                        summary = db.query(PostVisitSummary).filter(PostVisitSummary.consultation_id == cons_id).first()
                        if summary:
                            summary.status = AISummaryStatus.FAILED
                    elif job.job_type == JobType.MEDICATION_REMINDER:
                        reminder_id = job.payload.get("reminder_id")
                        reminder = db.query(MedicationReminder).filter(MedicationReminder.id == reminder_id).first()
                        if reminder:
                            reminder.status = MedicationReminderStatus.FAILED
                            reminder.error_message = str(exc)
                else:
                    job.status = JobStatus.PENDING

                    backoff_seconds = min(300, 2 ** job.attempts * 5)
                    job.scheduled_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)

                job.updated_at = datetime.utcnow()
                db.commit()
            return False

    @staticmethod
    def _handle_pre_visit_summary(db: Session, job: BackgroundJob):
        appointment_id = job.payload.get("appointment_id")
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise ValueError(f"Appointment {appointment_id} not found for pre-visit summary")

        ai_result = AIService.generate_pre_visit_summary(appointment.symptoms)

        summary = db.query(PreVisitSummary).filter(PreVisitSummary.appointment_id == appointment_id).first()
        if not summary:
            summary = PreVisitSummary(
                appointment_id=appointment_id,
                urgency=UrgencyLevel(ai_result.urgency),
                chief_complaint=ai_result.chief_complaint,
                suggested_questions=ai_result.suggested_questions,
                status=AISummaryStatus.GENERATED,
            )
            db.add(summary)
        else:
            summary.urgency = UrgencyLevel(ai_result.urgency)
            summary.chief_complaint = ai_result.chief_complaint
            summary.suggested_questions = ai_result.suggested_questions
            summary.status = AISummaryStatus.GENERATED

        job.result = ai_result.model_dump()
        db.commit()

    @staticmethod
    def _handle_post_visit_summary(db: Session, job: BackgroundJob):
        consultation_id = job.payload.get("consultation_id")
        consultation = db.query(Consultation).filter(Consultation.id == consultation_id).first()
        if not consultation:
            raise ValueError(f"Consultation {consultation_id} not found for post-visit summary")

        meds_payload = []
        if consultation.prescription and consultation.prescription.medications:
            for med in consultation.prescription.medications:
                meds_payload.append({
                    "name": med.name,
                    "dosage": med.dosage,
                    "frequency": med.frequency,
                    "duration": med.duration,
                    "instructions": med.instructions,
                })

        consultation_data = {
            "diagnosis": consultation.diagnosis,
            "clinical_notes": consultation.clinical_notes,
            "follow_up_instructions": consultation.follow_up_instructions,
            "medications": meds_payload,
        }

        ai_result = AIService.generate_post_visit_summary(consultation_data)

        summary = db.query(PostVisitSummary).filter(PostVisitSummary.consultation_id == consultation_id).first()
        schedule_dicts = [item.model_dump() for item in ai_result.medication_schedule]

        if not summary:
            summary = PostVisitSummary(
                consultation_id=consultation_id,
                visit_explanation=ai_result.visit_explanation,
                medication_schedule=schedule_dicts,
                follow_up_steps=ai_result.follow_up_steps,
                status=AISummaryStatus.GENERATED,
            )
            db.add(summary)
        else:
            summary.visit_explanation = ai_result.visit_explanation
            summary.medication_schedule = schedule_dicts
            summary.follow_up_steps = ai_result.follow_up_steps
            summary.status = AISummaryStatus.GENERATED

        job.result = ai_result.model_dump()
        db.commit()

    @staticmethod
    def _handle_notification_job(db: Session, job: BackgroundJob):
        """
        Execute a notification email job.
        Failure here is retried — but appointment state is NEVER modified.
        """
        from app.notification_service import NotificationService
        if job.job_type == JobType.NOTIFY_APPOINTMENT_REMINDER:
            NotificationService.execute_appointment_reminder_job(db, job)
            return

        notification_id = job.payload.get("notification_id")
        to_email = job.payload.get("to_email", "")
        subject = job.payload.get("subject", "")
        body = job.payload.get("body", "")
        html_body = job.payload.get("html_body")
        NotificationService.execute_notification_job(db, notification_id, to_email, subject, body, html_body=html_body)
        job.result = {"delivered": True}
        db.commit()

    @staticmethod
    def _handle_medication_reminder(db: Session, job: BackgroundJob):
        """Process a medication reminder job."""
        from app.notification_service import NotificationService
        reminder_id = job.payload.get("reminder_id")
        reminder = db.query(MedicationReminder).filter(MedicationReminder.id == reminder_id).first()
        if not reminder:
            raise ValueError(f"Medication reminder record {reminder_id} not found")

        if (
            reminder.medication
            and reminder.medication.prescription
            and reminder.medication.prescription.consultation
            and reminder.medication.prescription.consultation.appointment
            and reminder.medication.prescription.consultation.appointment.status == AppointmentStatus.CANCELLED
        ):
            logger.info("Skipping medication reminder %s because appointment is cancelled", reminder_id)
            reminder.status = MedicationReminderStatus.FAILED
            reminder.error_message = "Appointment was cancelled"
            job.result = {"delivered": False, "reason": "Appointment cancelled"}
            db.commit()
            return

        if reminder.medication and reminder.medication.end_date:
            if reminder.scheduled_for.date() > reminder.medication.end_date:
                logger.info("Skipping medication reminder %s past end date", reminder_id)
                reminder.status = MedicationReminderStatus.FAILED
                reminder.error_message = "Past medication end date"
                job.result = {"delivered": False, "reason": "Past medication end date"}
                db.commit()
                return

        to_email = job.payload.get("to_email", "")
        subject = job.payload.get("subject", "")
        body = job.payload.get("body", "")
        html_body = job.payload.get("html_body")
        NotificationService.execute_medication_reminder_job(db, reminder_id, to_email, subject, body, html_body=html_body)
        job.result = {"delivered": True}
        db.commit()

    @staticmethod
    def _handle_google_calendar_sync(db: Session, job: BackgroundJob):
        """
        Execute Google Calendar synchronization job.
        Failure here is retried via exponential backoff — appointment state is NEVER modified.
        """
        from app.google_calendar_service import GoogleCalendarService
        GoogleCalendarService.process_calendar_sync_job(db, job)

    @staticmethod
    def process_pending_jobs(db: Session, limit: int = 10) -> int:
        now = datetime.utcnow()
        pending_jobs = (
            db.query(BackgroundJob)
            .filter(
                or_(
                    and_(BackgroundJob.status == JobStatus.PENDING, BackgroundJob.scheduled_at <= now),
                    and_(BackgroundJob.status == JobStatus.PROCESSING, BackgroundJob.locked_at < now - timedelta(minutes=5))
                )
            )
            .order_by(BackgroundJob.created_at.asc())
            .limit(limit)
            .all()
        )

        processed = 0
        for job in pending_jobs:
            if JobManager.process_job(db, job.id):
                processed += 1
        return processed

def run_job_in_background(job_id: str):
    """FastAPI BackgroundTask worker wrapper"""
    db = SessionLocal()
    try:
        JobManager.process_job(db, job_id)
    finally:
        db.close()
