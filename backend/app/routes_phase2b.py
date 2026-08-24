"""
Phase 2B API Routes:
- Doctor Leave (preview, confirm, list, delete)
- Appointment cancellation with reason + rescheduling
- Notifications (list, mark-read)
- Medication Reminders (list)
- Admin job listing
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.models import get_db, User, BackgroundJob, DoctorProfile, JobStatus
from app.jobs import run_job_in_background
from app.schemas import (
    DoctorLeaveCreate,
    DoctorLeavePreviewOut,
    DoctorLeaveOut,
    DoctorLeaveRejectRequest,
    RescheduleRequest,
    CancelRequest,
    AppointmentOut,
    NotificationOut,
    MedicationReminderOut,
    BackgroundJobOut,
)
from app.security import get_current_user, require_admin, require_patient, require_doctor
from app.services import (
    DoctorLeaveService,
    AppointmentService,
    NotificationQueryService,
    MedicationReminderService,
)

phase2b_router = APIRouter()


# ── Doctor Leave Endpoints (Doctor Self-Service) ──────────────────────────────

@phase2b_router.post(
    "/doctor/leaves/preview",
    response_model=DoctorLeavePreviewOut,
)
def doctor_preview_own_leave(
    data: DoctorLeaveCreate,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor previews which appointments would be affected by their own leave."""
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return DoctorLeaveService.preview_leave(db, profile.id, data.start_date, data.end_date)


@phase2b_router.post(
    "/doctor/leaves/apply",
    response_model=DoctorLeaveOut,
    status_code=status.HTTP_201_CREATED,
)
def doctor_apply_own_leave(
    data: DoctorLeaveCreate,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor submits a leave request for Admin approval (status: PENDING)."""
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return DoctorLeaveService.apply_leave(
        db, profile.id, data.start_date, data.end_date, data.reason or "", current_user
    )


@phase2b_router.post(
    "/doctor/leaves/confirm",
    response_model=DoctorLeaveOut,
    status_code=status.HTTP_201_CREATED,
)
def doctor_confirm_own_leave_compat(
    data: DoctorLeaveCreate,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Backward-compatible endpoint: submits doctor leave application for admin approval."""
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return DoctorLeaveService.apply_leave(
        db, profile.id, data.start_date, data.end_date, data.reason or "", current_user
    )


@phase2b_router.get(
    "/doctor/leaves/my",
    response_model=List[DoctorLeaveOut],
)
def list_my_doctor_leaves(
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    """Doctor lists their own leave requests and history with statuses & rejection reasons."""
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    return DoctorLeaveService.get_leaves(db, profile.id)


@phase2b_router.delete("/doctor/leaves/{leave_id}", status_code=status.HTTP_200_OK)
def delete_own_doctor_leave(
    leave_id: str,
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Doctor profile not found")
    DoctorLeaveService.delete_leave(db, leave_id, current_user)
    return {"status": "OK", "message": "Leave record deleted"}


# ── Admin Doctor Leave Endpoints ──────────────────────────────────────────────

@phase2b_router.get(
    "/admin/leaves",
    response_model=List[DoctorLeaveOut],
)
def admin_list_all_leaves(
    doctor_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin lists all leave applications across doctors with optional filters."""
    return DoctorLeaveService.get_leaves(db, doctor_id=doctor_id, status_filter=status_filter)


@phase2b_router.post(
    "/admin/leaves/{leave_id}/approve",
    response_model=DoctorLeaveOut,
)
def admin_approve_leave(
    leave_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin approves a doctor's leave request.
    Cancels conflicting CONFIRMED appointments, releases slots, and notifies affected patients and doctor.
    """
    leave = DoctorLeaveService.approve_leave(db, leave_id, current_user)
    pending_jobs = db.query(BackgroundJob).filter(
        BackgroundJob.status == JobStatus.PENDING,
        BackgroundJob.scheduled_at <= datetime.utcnow(),
    ).order_by(BackgroundJob.created_at.desc()).limit(10).all()
    for job in pending_jobs:
        background_tasks.add_task(run_job_in_background, job.id)
    return leave


@phase2b_router.post(
    "/admin/leaves/{leave_id}/reject",
    response_model=DoctorLeaveOut,
)
def admin_reject_leave(
    leave_id: str,
    data: Optional[DoctorLeaveRejectRequest] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin rejects a doctor's leave request with reasons.
    Appointments remain active, doctor is notified with the rejection reason.
    """
    reason = data.reason if data and data.reason else "Leave request was not approved by administration."
    return DoctorLeaveService.reject_leave(db, leave_id, reason, current_user)


@phase2b_router.post(
    "/admin/doctors/{doctor_id}/leaves/preview",
    response_model=DoctorLeavePreviewOut,
)
def preview_doctor_leave(
    doctor_id: str,
    data: DoctorLeaveCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Preview which CONFIRMED appointments would be affected by a leave period.
    Does NOT create any records.
    """
    return DoctorLeaveService.preview_leave(db, doctor_id, data.start_date, data.end_date)


@phase2b_router.post(
    "/admin/doctors/{doctor_id}/leaves/confirm",
    response_model=DoctorLeaveOut,
    status_code=status.HTTP_201_CREATED,
)
def confirm_doctor_leave(
    doctor_id: str,
    data: DoctorLeaveCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin explicitly creates and confirms a doctor leave directly.
    Cancels conflicting CONFIRMED appointments, releases slots, enqueues notifications.
    """
    leave = DoctorLeaveService.confirm_leave(
        db, doctor_id, data.start_date, data.end_date, data.reason or "", current_user
    )
    pending_jobs = db.query(BackgroundJob).filter(
        BackgroundJob.status == JobStatus.PENDING,
        BackgroundJob.scheduled_at <= datetime.utcnow(),
    ).order_by(BackgroundJob.created_at.desc()).limit(10).all()
    for job in pending_jobs:
        background_tasks.add_task(run_job_in_background, job.id)
    return leave


@phase2b_router.get(
    "/admin/doctors/{doctor_id}/leaves",
    response_model=List[DoctorLeaveOut],
)
def list_doctor_leaves(
    doctor_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all leaves for a given doctor."""
    return DoctorLeaveService.get_leaves(db, doctor_id)


@phase2b_router.delete("/admin/leaves/{leave_id}", status_code=status.HTTP_200_OK)
def delete_doctor_leave(
    leave_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    DoctorLeaveService.delete_leave(db, leave_id, current_user)
    return {"status": "OK", "message": "Leave record deleted"}




# ── Appointment Rescheduling ──────────────────────────────────────────────────

@phase2b_router.post("/appointments/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule_appointment(
    appointment_id: str,
    data: RescheduleRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reschedule a CONFIRMED appointment to a new slot.
    Reuses Phase 1 concurrency-safe hold + book logic.
    Old slot is released; notification jobs created for both old and new.
    """
    appointment = AppointmentService.reschedule_appointment(
        db, appointment_id, data.new_slot_id, current_user
    )
    # Process pending notification jobs in background (only due jobs)
    pending_jobs = db.query(BackgroundJob).filter(
        BackgroundJob.status == JobStatus.PENDING,
        BackgroundJob.scheduled_at <= datetime.utcnow(),
    ).order_by(BackgroundJob.created_at.desc()).limit(5).all()
    for job in pending_jobs:
        background_tasks.add_task(run_job_in_background, job.id)

    return AppointmentService._serialize_appointment(appointment)


# ── Notifications ─────────────────────────────────────────────────────────────

@phase2b_router.get("/notifications/my", response_model=List[NotificationOut])
def get_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all notifications for the current user (patient or doctor)."""
    return NotificationQueryService.get_user_notifications(db, current_user.id)


@phase2b_router.patch("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return NotificationQueryService.mark_read(db, notification_id, current_user.id)


# ── Medication Reminders ──────────────────────────────────────────────────────

@phase2b_router.get("/medication-reminders/my", response_model=List[MedicationReminderOut])
def get_my_medication_reminders(
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    """Get medication reminders for the current patient."""
    return MedicationReminderService.get_patient_reminders(db, current_user.id)


# ── Admin: Job Visibility ─────────────────────────────────────────────────────

@phase2b_router.get("/admin/jobs", response_model=List[BackgroundJobOut])
def admin_list_jobs(
    limit: int = 50,
    job_status: Optional[str] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List background jobs with optional status filter."""
    from app.models import JobStatus
    query = db.query(BackgroundJob)
    if job_status:
        try:
            query = query.filter(BackgroundJob.status == JobStatus(job_status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid job status: {job_status}")
    return query.order_by(BackgroundJob.created_at.desc()).limit(limit).all()
