from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app.models import get_db, User
from app.jobs import run_job_in_background
from app.schemas import (
    Token,
    UserRegister,
    UserLogin,
    UserOut,
    DoctorCreate,
    DoctorUpdate,
    DoctorStatusUpdate,
    DoctorOut,
    WorkingHoursUpdate,
    SlotOut,
    GenerateSlotsRequest,
    HoldSlotResponse,
    ConfirmAppointmentRequest,
    AppointmentOut,
    SystemStats,
    PatientAdminOut,
    PreVisitSummaryOut,
    GeneratePreVisitSummaryRequest,
    ConsultationCompleteRequest,
    ConsultationOut,
    PostVisitSummaryOut,
    CancelRequest,
    GoogleAuthUrlOut,
    GoogleCallbackRequest,
    GoogleCalendarStatusOut,
)
from app.security import (
    create_access_token,
    get_current_user,
    get_optional_current_user,
    require_patient,
    require_doctor,
    require_admin,
)
from app.google_calendar_service import GoogleCalendarService
from app.services import (
    AuthService,
    DoctorService,
    SlotService,
    AppointmentService,
    AdminService,
    ConsultationService,
)



api_router = APIRouter()

@api_router.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(data: UserRegister, db: Session = Depends(get_db)):
    user = AuthService.register_user(db, data)
    token = create_access_token(subject=user.id, role=user.role.value)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }

@api_router.post("/auth/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = AuthService.authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(subject=user.id, role=user.role.value)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }

@api_router.get("/auth/google/url", response_model=GoogleAuthUrlOut)
def get_google_auth_url(
    state: str = Query("login"),
    redirect_uri: Optional[str] = Query(None),
):
    url = GoogleCalendarService.get_authorization_url(state=state, redirect_uri=redirect_uri)
    return {"auth_url": url}

@api_router.post("/auth/google/callback", response_model=Token)
def google_auth_callback(
    data: GoogleCallbackRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    user, _ = AuthService.authenticate_or_register_google_user(
        db=db,
        code=data.code,
        role=data.role,
        current_user=current_user,
    )
    token = create_access_token(subject=user.id, role=user.role.value)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }

@api_router.get("/auth/google/status", response_model=GoogleCalendarStatusOut)
def get_google_calendar_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return GoogleCalendarService.get_user_calendar_status(db, current_user.id)

@api_router.post("/auth/google/disconnect")
def disconnect_google_calendar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = GoogleCalendarService.disconnect_google_account(db, current_user.id)
    return {"status": "OK", "message": "Google Calendar disconnected", "disconnected": success}

@api_router.get("/auth/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@api_router.get("/doctors", response_model=List[DoctorOut])
def list_doctors(
    specialization: Optional[str] = None,
    insurance: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return DoctorService.get_doctors(db, specialization, insurance, search, include_inactive=False)

@api_router.get("/doctors/{doctor_id}", response_model=DoctorOut)
def get_doctor(doctor_id: str, db: Session = Depends(get_db)):
    doctor = DoctorService.get_doctor_by_id(db, doctor_id)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    return doctor

@api_router.get("/doctors/{doctor_id}/slots", response_model=List[SlotOut])
def get_doctor_slots(
    doctor_id: str,
    slot_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    return SlotService.get_doctor_slots(db, doctor_id, slot_date)

@api_router.post("/appointments/slots/{slot_id}/hold", response_model=HoldSlotResponse)
def hold_slot(
    slot_id: str,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    slot = AppointmentService.hold_slot(db, slot_id, current_user.id)
    return {
        "slot_id": slot.id,
        "status": slot.status,
        "held_by_patient_id": slot.held_by_patient_id,
        "hold_expires_at": slot.hold_expires_at,
        "message": "Slot held for 5 minutes. Please complete booking with symptoms.",
    }

@api_router.delete("/appointments/slots/{slot_id}/hold")
def release_hold(
    slot_id: str,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    AppointmentService.release_hold(db, slot_id, current_user.id)
    return {"status": "OK", "message": "Slot hold released"}

@api_router.post("/appointments/confirm", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def confirm_appointment(
    data: ConfirmAppointmentRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    appointment = AppointmentService.confirm_appointment(db, data, current_user.id)
    if hasattr(appointment, "_enqueued_job_id") and appointment._enqueued_job_id:
        background_tasks.add_task(run_job_in_background, appointment._enqueued_job_id)
    if hasattr(appointment, "_calendar_job_id") and appointment._calendar_job_id:
        background_tasks.add_task(run_job_in_background, appointment._calendar_job_id)

    return {
        "id": appointment.id,
        "slot_id": appointment.slot_id,
        "doctor_id": appointment.doctor_id,
        "patient_id": appointment.patient_id,
        "symptoms": appointment.symptoms,
        "status": appointment.status,
        "booked_at": appointment.booked_at,
        "doctor_name": appointment.doctor.user.full_name if appointment.doctor and appointment.doctor.user else "Doctor",
        "doctor_specialization": appointment.doctor.specialization if appointment.doctor else "General",
        "patient_name": current_user.full_name,
        "patient_email": current_user.email,
        "start_time": appointment.slot.start_time if appointment.slot else None,
        "end_time": appointment.slot.end_time if appointment.slot else None,
        "google_event_id": appointment.google_event_id,
    }

@api_router.get("/appointments/patient/my-appointments", response_model=List[AppointmentOut])
def get_my_appointments(
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    return AppointmentService.get_patient_appointments(db, current_user.id)

@api_router.get("/appointments/doctor/agenda", response_model=List[AppointmentOut])
def get_doctor_agenda(
    current_user: User = Depends(require_doctor),
    db: Session = Depends(get_db),
):
    return AppointmentService.get_doctor_agenda(db, current_user.id)

@api_router.patch("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: str,
    background_tasks: BackgroundTasks,
    data: Optional[CancelRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reason = data.reason if data else None
    appointment = AppointmentService.cancel_appointment(db, appointment_id, current_user, reason=reason)
    if hasattr(appointment, "_calendar_job_id") and appointment._calendar_job_id:
        background_tasks.add_task(run_job_in_background, appointment._calendar_job_id)
    return {"status": "OK", "message": "Appointment cancelled successfully"}

@api_router.get("/admin/doctors", response_model=List[DoctorOut])
def admin_list_all_doctors(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return DoctorService.get_doctors(db, include_inactive=True)

@api_router.post("/admin/doctors", response_model=DoctorOut, status_code=status.HTTP_201_CREATED)
def admin_create_doctor(
    data: DoctorCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    profile = DoctorService.create_doctor(db, data)
    return DoctorService.get_doctor_by_id(db, profile.id)

@api_router.put("/admin/doctors/{doctor_id}", response_model=DoctorOut)
def admin_update_doctor(
    doctor_id: str,
    data: DoctorUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    DoctorService.update_doctor(db, doctor_id, data)
    return DoctorService.get_doctor_by_id(db, doctor_id)

@api_router.patch("/admin/doctors/{doctor_id}/status", response_model=DoctorOut)
def admin_set_doctor_status(
    doctor_id: str,
    data: DoctorStatusUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    DoctorService.set_doctor_status(db, doctor_id, data.is_active)
    return DoctorService.get_doctor_by_id(db, doctor_id)

@api_router.put("/admin/doctors/{doctor_id}/working-hours")
def admin_update_working_hours(
    doctor_id: str,
    data: WorkingHoursUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    DoctorService.update_working_hours(db, doctor_id, data)
    return {"status": "OK", "message": "Working hours updated successfully"}

@api_router.post("/admin/doctors/{doctor_id}/generate-slots")
def admin_generate_slots(
    doctor_id: str,
    data: GenerateSlotsRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    start_d = datetime.strptime(data.start_date, "%Y-%m-%d").date()
    end_d = datetime.strptime(data.end_date, "%Y-%m-%d").date()
    count = SlotService.generate_slots_for_doctor(db, doctor_id, start_d, end_d)
    return {"status": "OK", "slots_created": count}

@api_router.delete("/admin/doctors/{doctor_id}")
def admin_delete_doctor(
    doctor_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    AdminService.delete_doctor(db, doctor_id)
    return {"status": "OK", "message": "Doctor removed successfully"}

@api_router.get("/admin/stats", response_model=SystemStats)
def admin_get_stats(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return AppointmentService.get_system_stats(db)

@api_router.get("/admin/patients", response_model=List[PatientAdminOut])
def admin_get_registered_patients(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return AdminService.get_registered_patients(db)

@api_router.delete("/admin/patients/{patient_id}")
def admin_delete_patient(
    patient_id: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    AdminService.delete_patient(db, patient_id)
    return {"status": "OK", "message": "Patient removed successfully"}

# --- PHASE 2A: CONSULTATION & AI WORKFLOW ENDPOINTS ---

@api_router.get("/appointments/{appointment_id}/pre-visit-summary", response_model=PreVisitSummaryOut)
def get_pre_visit_summary(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ConsultationService.get_pre_visit_summary(db, appointment_id, current_user)

@api_router.post("/appointments/{appointment_id}/generate-pre-visit-summary", response_model=PreVisitSummaryOut)
def generate_pre_visit_summary(
    appointment_id: str,
    data: Optional[GeneratePreVisitSummaryRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    provider_name = data.provider if data else None
    return ConsultationService.generate_pre_visit_summary(db, appointment_id, provider_name, current_user)

@api_router.post("/consultations/{appointment_id}/start")
def start_consultation(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation = ConsultationService.start_consultation(db, appointment_id, current_user)
    return {
        "id": consultation.id,
        "appointment_id": consultation.appointment_id,
        "status": consultation.status,
        "started_at": consultation.started_at,
    }

@api_router.post("/consultations/{consultation_id}/complete")
def complete_consultation(
    consultation_id: str,
    data: ConsultationCompleteRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consultation = ConsultationService.complete_consultation(db, consultation_id, data, current_user)
    if hasattr(consultation, "_enqueued_job_id") and consultation._enqueued_job_id:
        background_tasks.add_task(run_job_in_background, consultation._enqueued_job_id)

    return {
        "id": consultation.id,
        "appointment_id": consultation.appointment_id,
        "status": consultation.status,
        "completed_at": consultation.completed_at,
        "message": "Consultation completed and post-visit summary queued",
    }

@api_router.get("/consultations/appointment/{appointment_id}", response_model=ConsultationOut)
def get_consultation_by_appointment(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ConsultationService.get_consultation_details(db, appointment_id, current_user)

@api_router.get("/consultations/{consultation_id}/post-visit-summary", response_model=PostVisitSummaryOut)
def get_post_visit_summary(
    consultation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ConsultationService.get_post_visit_summary(db, consultation_id, current_user)

@api_router.post("/admin/jobs/process-pending")
def admin_process_pending_jobs(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.jobs import JobManager
    count = JobManager.process_pending_jobs(db, limit=20)
    return {"status": "OK", "jobs_processed": count}


