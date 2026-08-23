import uuid
from datetime import datetime, time, date
import enum
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    Date,
    Time,
    ForeignKey,
    Enum,
    JSON,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from app.config import settings

Base = declarative_base()

class UserRole(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"

class SlotStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    BOOKED = "BOOKED"
    CANCELLED = "CANCELLED"

class AppointmentStatus(str, enum.Enum):
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.PATIENT, nullable=False)
    accepted_insurance = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctor_profile = relationship("DoctorProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="patient", foreign_keys="Appointment.patient_id")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    google_account = relationship("UserGoogleAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")

class DoctorProfile(Base):
    __tablename__ = "doctor_profiles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    specialization = Column(String(100), index=True, nullable=False)
    bio = Column(Text, default="")
    slot_duration_minutes = Column(Integer, default=settings.DEFAULT_SLOT_DURATION_MINUTES, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User", back_populates="doctor_profile")
    working_hours = relationship("DoctorWorkingHours", back_populates="doctor", cascade="all, delete-orphan")
    slots = relationship("Slot", back_populates="doctor", cascade="all, delete-orphan")
    appointments = relationship("Appointment", back_populates="doctor", foreign_keys="Appointment.doctor_id")
    leaves = relationship("DoctorLeave", back_populates="doctor", cascade="all, delete-orphan")

class DoctorWorkingHours(Base):
    __tablename__ = "doctor_working_hours"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, default=time(9, 0), nullable=False)
    end_time = Column(Time, default=time(17, 0), nullable=False)
    is_day_off = Column(Boolean, default=False, nullable=False)

    doctor = relationship("DoctorProfile", back_populates="working_hours")

    __table_args__ = (
        UniqueConstraint("doctor_id", "day_of_week", name="uq_doctor_day"),
    )

class Slot(Base):
    __tablename__ = "slots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(SlotStatus), default=SlotStatus.AVAILABLE, nullable=False, index=True)
    held_by_patient_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    hold_expires_at = Column(DateTime, nullable=True, index=True)
    version = Column(Integer, default=1, nullable=False)

    doctor = relationship("DoctorProfile", back_populates="slots")
    held_by_patient = relationship("User", foreign_keys=[held_by_patient_id])
    appointment = relationship("Appointment", back_populates="slot", uselist=False, foreign_keys="Appointment.slot_id")

    __table_args__ = (
        UniqueConstraint("doctor_id", "start_time", name="uq_doctor_slot_start"),
    )

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slot_id = Column(String(36), ForeignKey("slots.id", ondelete="CASCADE"), unique=True, nullable=False)
    doctor_id = Column(String(36), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symptoms = Column(Text, nullable=False)
    status = Column(Enum(AppointmentStatus), default=AppointmentStatus.CONFIRMED, nullable=False)
    booked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Phase 2B additions
    cancellation_reason = Column(Text, nullable=True)
    rescheduled_from_slot_id = Column(String(36), ForeignKey("slots.id", ondelete="SET NULL"), nullable=True)
    google_event_id = Column(String(255), nullable=True)

    slot = relationship("Slot", back_populates="appointment", foreign_keys=[slot_id])
    rescheduled_from_slot = relationship("Slot", foreign_keys=[rescheduled_from_slot_id])
    doctor = relationship("DoctorProfile", back_populates="appointments", foreign_keys=[doctor_id])
    patient = relationship("User", back_populates="appointments", foreign_keys=[patient_id])
    pre_visit_summary = relationship("PreVisitSummary", back_populates="appointment", uselist=False, cascade="all, delete-orphan")
    consultation = relationship("Consultation", back_populates="appointment", uselist=False, cascade="all, delete-orphan")


class JobType(str, enum.Enum):
    PRE_VISIT_SUMMARY = "PRE_VISIT_SUMMARY"
    POST_VISIT_SUMMARY = "POST_VISIT_SUMMARY"
    # Phase 2B notification jobs
    NOTIFY_APPOINTMENT_CONFIRMATION = "NOTIFY_APPOINTMENT_CONFIRMATION"
    NOTIFY_APPOINTMENT_CANCELLATION = "NOTIFY_APPOINTMENT_CANCELLATION"
    NOTIFY_APPOINTMENT_REMINDER = "NOTIFY_APPOINTMENT_REMINDER"
    NOTIFY_DOCTOR_LEAVE = "NOTIFY_DOCTOR_LEAVE"
    MEDICATION_REMINDER = "MEDICATION_REMINDER"
    GOOGLE_CALENDAR_SYNC = "GOOGLE_CALENDAR_SYNC"


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class UrgencyLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AISummaryStatus(str, enum.Enum):
    PENDING = "PENDING"
    GENERATED = "GENERATED"
    FAILED = "FAILED"


class ConsultationStatus(str, enum.Enum):
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class NotificationType(str, enum.Enum):
    APPOINTMENT_CONFIRMATION = "APPOINTMENT_CONFIRMATION"
    APPOINTMENT_CANCELLATION = "APPOINTMENT_CANCELLATION"
    APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"
    DOCTOR_LEAVE = "DOCTOR_LEAVE"
    DOCTOR_LEAVE_APPROVAL = "DOCTOR_LEAVE_APPROVAL"
    DOCTOR_LEAVE_REJECTION = "DOCTOR_LEAVE_REJECTION"
    MEDICATION_REMINDER = "MEDICATION_REMINDER"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class MedicationReminderStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_type = Column(Enum(JobType), nullable=False, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    error_message = Column(Text, nullable=True)
    scheduled_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    locked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PreVisitSummary(Base):
    __tablename__ = "pre_visit_summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    appointment_id = Column(String(36), ForeignKey("appointments.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    urgency = Column(Enum(UrgencyLevel), default=UrgencyLevel.LOW, nullable=False)
    chief_complaint = Column(Text, nullable=False)
    suggested_questions = Column(JSON, default=list, nullable=False)
    status = Column(Enum(AISummaryStatus), default=AISummaryStatus.PENDING, nullable=False)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    appointment = relationship("Appointment", back_populates="pre_visit_summary")


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    appointment_id = Column(String(36), ForeignKey("appointments.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    doctor_id = Column(String(36), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    clinical_notes = Column(Text, default="", nullable=False)
    diagnosis = Column(Text, default="", nullable=False)
    follow_up_instructions = Column(Text, default="", nullable=False)
    status = Column(Enum(ConsultationStatus), default=ConsultationStatus.IN_PROGRESS, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    appointment = relationship("Appointment", back_populates="consultation")
    doctor = relationship("DoctorProfile")
    patient = relationship("User")
    prescription = relationship("Prescription", back_populates="consultation", uselist=False, cascade="all, delete-orphan")
    post_visit_summary = relationship("PostVisitSummary", back_populates="consultation", uselist=False, cascade="all, delete-orphan")


class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    consultation_id = Column(String(36), ForeignKey("consultations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    notes = Column(Text, default="", nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    consultation = relationship("Consultation", back_populates="prescription")
    medications = relationship("Medication", back_populates="prescription", cascade="all, delete-orphan")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    prescription_id = Column(String(36), ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    dosage = Column(String(100), nullable=False)
    frequency = Column(String(100), nullable=False)
    duration = Column(String(100), nullable=False)
    instructions = Column(Text, default="", nullable=True)
    start_date = Column(Date, nullable=True)   # Phase 2B: for reminder scheduling
    end_date = Column(Date, nullable=True)     # Phase 2B: for reminder scheduling

    prescription = relationship("Prescription", back_populates="medications")
    reminders = relationship("MedicationReminder", back_populates="medication", cascade="all, delete-orphan")


class PostVisitSummary(Base):
    __tablename__ = "post_visit_summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    consultation_id = Column(String(36), ForeignKey("consultations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    visit_explanation = Column(Text, nullable=False)
    medication_schedule = Column(JSON, default=list, nullable=False)
    follow_up_steps = Column(Text, nullable=False)
    status = Column(Enum(AISummaryStatus), default=AISummaryStatus.PENDING, nullable=False)
    raw_response = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    consultation = relationship("Consultation", back_populates="post_visit_summary")


# ── Phase 2B New Models ──────────────────────────────────────────────────────

class DoctorLeave(Base):
    """Doctor leave request and admin approval record."""
    __tablename__ = "doctor_leaves"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id = Column(String(36), ForeignKey("doctor_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(Text, default="", nullable=True)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False)
    rejection_reason = Column(Text, nullable=True)
    created_by_admin_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_admin_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    affected_appointments_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    doctor = relationship("DoctorProfile", back_populates="leaves")
    created_by_admin = relationship("User", foreign_keys=[created_by_admin_id])
    reviewed_by_admin = relationship("User", foreign_keys=[reviewed_by_admin_id])


class Notification(Base):
    """In-app notification record for a user."""
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    reference_id = Column(String(36), nullable=True)   # appointment_id, leave_id, etc.
    job_id = Column(String(36), nullable=True)         # linked BackgroundJob id
    email_sent = Column(Boolean, default=False, nullable=False)
    email_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="notifications")


class MedicationReminder(Base):
    """Scheduled reminder for a single medication dose."""
    __tablename__ = "medication_reminders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medication_id = Column(String(36), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_for = Column(DateTime, nullable=False, index=True)
    dose_label = Column(String(100), nullable=False, default="")   # e.g. "Morning dose"
    status = Column(Enum(MedicationReminderStatus), default=MedicationReminderStatus.PENDING, nullable=False)
    job_id = Column(String(36), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    medication = relationship("Medication", back_populates="reminders")
    patient = relationship("User")


class UserGoogleAccount(Base):
    """Google OAuth and Google Calendar connection for a user."""
    __tablename__ = "user_google_accounts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    google_user_id = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    scopes = Column(Text, nullable=True)
    is_calendar_connected = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="google_account")


from sqlalchemy.pool import NullPool

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine_kwargs = {"connect_args": connect_args, "pool_pre_ping": True}
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_schema_migrations():
    """Ensure newly added columns exist in DB (PostgreSQL / SQLite) if not already present."""
    from sqlalchemy import text, inspect
    try:
        conn = engine.connect().execution_options(isolation_level="AUTOCOMMIT")
        insp = inspect(conn)
        tables = insp.get_table_names()
        if "doctor_leaves" in tables:
            existing_cols = {col["name"] for col in insp.get_columns("doctor_leaves")}
            if "status" not in existing_cols:
                try: conn.execute(text("ALTER TABLE doctor_leaves ADD COLUMN status VARCHAR(20) DEFAULT 'APPROVED' NOT NULL"))
                except Exception: pass
            if "rejection_reason" not in existing_cols:
                try: conn.execute(text("ALTER TABLE doctor_leaves ADD COLUMN rejection_reason TEXT"))
                except Exception: pass
            if "reviewed_by_admin_id" not in existing_cols:
                try: conn.execute(text("ALTER TABLE doctor_leaves ADD COLUMN reviewed_by_admin_id VARCHAR(36)"))
                except Exception: pass
            if "reviewed_at" not in existing_cols:
                try: conn.execute(text("ALTER TABLE doctor_leaves ADD COLUMN reviewed_at TIMESTAMP"))
                except Exception: pass
            if "created_at" not in existing_cols:
                try: conn.execute(text("ALTER TABLE doctor_leaves ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                except Exception: pass

        if "appointments" in tables:
            existing_appt_cols = {col["name"] for col in insp.get_columns("appointments")}
            if "google_event_id" not in existing_appt_cols:
                try: conn.execute(text("ALTER TABLE appointments ADD COLUMN google_event_id VARCHAR(255)"))
                except Exception: pass

        # PostgreSQL Enum additions & constraint relaxes
        if engine.dialect.name == "postgresql":
            try: conn.execute(text("ALTER TABLE doctor_leaves ALTER COLUMN confirmed_at DROP NOT NULL"))
            except Exception: pass
            try: conn.execute(text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DOCTOR_LEAVE_APPROVAL'"))
            except Exception: pass
            try: conn.execute(text("ALTER TYPE notificationtype ADD VALUE IF NOT EXISTS 'DOCTOR_LEAVE_REJECTION'"))
            except Exception: pass
            try: conn.execute(text("ALTER TYPE leavestatus ADD VALUE IF NOT EXISTS 'PENDING'"))
            except Exception: pass
            try: conn.execute(text("ALTER TYPE leavestatus ADD VALUE IF NOT EXISTS 'APPROVED'"))
            except Exception: pass
            try: conn.execute(text("ALTER TYPE leavestatus ADD VALUE IF NOT EXISTS 'REJECTED'"))
            except Exception: pass
            try: conn.execute(text("ALTER TYPE jobtype ADD VALUE IF NOT EXISTS 'GOOGLE_CALENDAR_SYNC'"))
            except Exception: pass
        conn.close()
    except Exception as e:
        pass

    # Ensure tables exist
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass


try:
    run_schema_migrations()
except Exception:
    pass

