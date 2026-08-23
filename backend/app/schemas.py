from datetime import datetime, time
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from app.models import UserRole, SlotStatus, AppointmentStatus

class Token(BaseModel):
    access_token: str
    token_type: str
    user: "UserOut"

class TokenPayload(BaseModel):
    sub: Optional[str] = None
    role: Optional[str] = None

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=2)
    accepted_insurance: List[str] = []

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: UserRole
    accepted_insurance: List[str] = []
    created_at: datetime

class DoctorCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    full_name: str = Field(min_length=2)
    specialization: str = Field(min_length=2)
    bio: Optional[str] = ""
    slot_duration_minutes: int = Field(default=30, ge=10, le=180)
    accepted_insurance: List[str] = []

class DoctorUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2)
    specialization: Optional[str] = Field(None, min_length=2)
    bio: Optional[str] = None
    slot_duration_minutes: Optional[int] = Field(None, ge=10, le=180)
    accepted_insurance: Optional[List[str]] = None

class DoctorStatusUpdate(BaseModel):
    is_active: bool

class WorkingHoursItem(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: str
    end_time: str
    is_day_off: bool = False

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        parts = v.split(":")
        if len(parts) != 2:
            raise ValueError("Time must be in HH:MM format")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("Invalid hour or minute")
        return v

class WorkingHoursUpdate(BaseModel):
    hours: List[WorkingHoursItem]

class WorkingHoursOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    day_of_week: int
    start_time: time
    end_time: time
    is_day_off: bool

class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    full_name: str
    email: str
    specialization: str
    bio: str
    slot_duration_minutes: int
    is_active: bool
    accepted_insurance: List[str] = []
    working_hours: List[WorkingHoursOut] = []

class SlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doctor_id: str
    start_time: datetime
    end_time: datetime
    status: SlotStatus
    held_by_patient_id: Optional[str] = None
    hold_expires_at: Optional[datetime] = None

class GenerateSlotsRequest(BaseModel):
    start_date: str
    end_date: str

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        datetime.strptime(v, "%Y-%m-%d")
        return v

class HoldSlotResponse(BaseModel):
    slot_id: str
    status: SlotStatus
    held_by_patient_id: str
    hold_expires_at: datetime
    message: str

class ConfirmAppointmentRequest(BaseModel):
    slot_id: str
    symptoms: str = Field(min_length=3)

    @field_validator("symptoms")
    @classmethod
    def validate_symptoms(cls, v: str) -> str:
        s = v.strip()
        if len(s) < 3:
            raise ValueError("Symptoms description must be at least 3 characters")
        return s

class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slot_id: str
    doctor_id: str
    patient_id: str
    symptoms: str
    status: AppointmentStatus
    booked_at: datetime
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    # Phase 2B additions
    cancellation_reason: Optional[str] = None
    rescheduled_from_slot_id: Optional[str] = None

class SystemStats(BaseModel):
    total_patients: int
    total_doctors: int
    total_slots: int
    total_appointments: int
    total_holds_active: int
    server_time: datetime

class PatientAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: UserRole
    accepted_insurance: List[str] = []
    created_at: datetime
    total_appointments: int = 0

from app.models import UrgencyLevel, AISummaryStatus, ConsultationStatus

class PreVisitSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    appointment_id: str
    urgency: UrgencyLevel
    chief_complaint: str
    suggested_questions: List[str]
    status: AISummaryStatus
    created_at: datetime

class MedicationInput(BaseModel):
    name: str = Field(min_length=1)
    dosage: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    instructions: Optional[str] = ""

class MedicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    dosage: str
    frequency: str
    duration: str
    instructions: Optional[str] = ""

class PrescriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notes: Optional[str] = ""
    created_at: datetime
    medications: List[MedicationOut] = []

class PostVisitSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    consultation_id: str
    visit_explanation: str
    medication_schedule: List[dict] = []
    follow_up_steps: str
    status: AISummaryStatus
    created_at: datetime

class ConsultationCompleteRequest(BaseModel):
    diagnosis: str = Field(min_length=2)
    clinical_notes: str = Field(default="")
    follow_up_instructions: str = Field(default="")
    prescription_notes: Optional[str] = ""
    medications: List[MedicationInput] = []

class ConsultationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    appointment_id: str
    doctor_id: str
    patient_id: str
    diagnosis: str
    clinical_notes: Optional[str] = None
    follow_up_instructions: str
    status: ConsultationStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    doctor_name: Optional[str] = None
    doctor_specialization: Optional[str] = None
    patient_name: Optional[str] = None
    patient_email: Optional[str] = None
    prescription: Optional[PrescriptionOut] = None
    post_visit_summary: Optional[PostVisitSummaryOut] = None
    pre_visit_summary: Optional[PreVisitSummaryOut] = None

class GeneratePreVisitSummaryRequest(BaseModel):
    provider: Optional[str] = "gemini"

Token.model_rebuild()


# ── Phase 2B Schemas ─────────────────────────────────────────────────────────

from datetime import date
from app.models import NotificationType, MedicationReminderStatus, LeaveStatus

class DoctorLeaveCreate(BaseModel):
    start_date: date
    end_date: date
    reason: Optional[str] = ""

class DoctorLeaveRejectRequest(BaseModel):
    reason: Optional[str] = "Leave request was not approved by administration."

class AffectedAppointmentOut(BaseModel):
    appointment_id: str
    patient_name: str
    patient_email: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    symptoms: str
    status: str

class DoctorLeavePreviewOut(BaseModel):
    doctor_id: str
    doctor_name: str
    start_date: str
    end_date: str
    affected_appointments: List[AffectedAppointmentOut]
    affected_count: int

class DoctorLeaveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    doctor_id: str
    doctor_name: Optional[str] = None
    doctor_email: Optional[str] = None
    doctor_specialization: Optional[str] = None
    start_date: date
    end_date: date
    reason: Optional[str] = ""
    status: LeaveStatus = LeaveStatus.PENDING
    rejection_reason: Optional[str] = None
    created_by_admin_id: Optional[str] = None
    reviewed_by_admin_id: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    affected_appointments_count: int = 0
    created_at: Optional[datetime] = None

class RescheduleRequest(BaseModel):
    new_slot_id: str
    reason: Optional[str] = None

class CancelRequest(BaseModel):
    reason: Optional[str] = None

class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    notification_type: NotificationType
    title: str
    body: str
    is_read: bool
    reference_id: Optional[str] = None
    email_sent: bool
    email_error: Optional[str] = None
    created_at: datetime

class MedicationReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    medication_id: str
    patient_id: str
    scheduled_for: datetime
    dose_label: str
    status: MedicationReminderStatus
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

class BackgroundJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str
    status: str
    attempts: int
    max_attempts: int
    error_message: Optional[str] = None
    scheduled_at: datetime
    created_at: datetime
    updated_at: datetime
