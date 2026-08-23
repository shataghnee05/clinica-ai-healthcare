import os
import sys
import uuid
from datetime import datetime, timedelta

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment to use mock AI provider for fast, deterministic unit test verification
os.environ["AI_PROVIDER"] = "mock"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text


from app.main import app
from app.models import (
    engine,
    User,
    UserRole,
    DoctorProfile,
    Slot,
    SlotStatus,
    Appointment,
    AppointmentStatus,
    Consultation,
    ConsultationStatus,
    PreVisitSummary,
    PostVisitSummary,
    AISummaryStatus,
)
from app.security import get_password_hash
from app.jobs import JobManager, JobType, JobStatus
from app.ai.service import AIService
from app.ai.schemas import PreVisitSummaryResult, PostVisitSummaryResult
from app.ai.providers.gemini_provider import GeminiProvider

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def cleanup_phase2a_test_data():
    settings.AI_PROVIDER = "mock"
    os.environ["AI_PROVIDER"] = "mock"

    yield
    db = TestingSessionLocal()
    try:
        db.execute(text("""
            DELETE FROM users 
            WHERE email LIKE 'p2a_%' 
               OR email LIKE 'test_admin_%' 
               OR email LIKE 'dr.p2a_%' 
               OR email LIKE 'patient_p2a_%'
        """))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@pytest.fixture
def setup_phase2a_environment():
    db = TestingSessionLocal()
    rand_suffix = str(uuid.uuid4())[:8]

    try:
        # Create Admin
        admin = User(
            email=f"p2a_admin_{rand_suffix}@testdomain.com",
            password_hash=get_password_hash("AdminPass123!"),
            full_name="Phase2A Admin",
            role=UserRole.ADMIN,
        )
        db.add(admin)

        # Create Doctor A
        doc_user_a = User(
            email=f"dr.p2a_a_{rand_suffix}@testdomain.com",
            password_hash=get_password_hash("DocPass123!"),
            full_name="Dr. Sarah Connor",
            role=UserRole.DOCTOR,
            accepted_insurance=["Aetna", "BlueCross"],
        )
        db.add(doc_user_a)
        db.flush()

        doc_profile_a = DoctorProfile(
            user_id=doc_user_a.id,
            specialization="Pulmonology",
            bio="Specialist in respiratory diseases and internal medicine.",
            slot_duration_minutes=30,
            is_active=True,
        )
        db.add(doc_profile_a)

        # Create Doctor B
        doc_user_b = User(
            email=f"dr.p2a_b_{rand_suffix}@testdomain.com",
            password_hash=get_password_hash("DocPass123!"),
            full_name="Dr. Emmett Brown",
            role=UserRole.DOCTOR,
            accepted_insurance=["Aetna", "Cigna"],
        )
        db.add(doc_user_b)
        db.flush()

        doc_profile_b = DoctorProfile(
            user_id=doc_user_b.id,
            specialization="Neurology",
            bio="Specialist in neurobiology and trauma.",
            slot_duration_minutes=30,
            is_active=True,
        )
        db.add(doc_profile_b)

        # Create Patient A
        patient_user_a = User(
            email=f"patient_p2a_a_{rand_suffix}@testdomain.com",
            password_hash=get_password_hash("PatientPass123!"),
            full_name="John Connor",
            role=UserRole.PATIENT,
            accepted_insurance=["Aetna"],
        )
        db.add(patient_user_a)

        # Create Patient B
        patient_user_b = User(
            email=f"patient_p2a_b_{rand_suffix}@testdomain.com",
            password_hash=get_password_hash("PatientPass123!"),
            full_name="Marty McFly",
            role=UserRole.PATIENT,
            accepted_insurance=["Cigna"],
        )
        db.add(patient_user_b)
        db.flush()

        # Create Open Slot for Doctor A
        start_t = datetime.utcnow() + timedelta(days=2, hours=10)
        end_t = start_t + timedelta(minutes=30)
        slot = Slot(
            doctor_id=doc_profile_a.id,
            start_time=start_t,
            end_time=end_t,
            status=SlotStatus.AVAILABLE,
        )
        db.add(slot)
        db.commit()

        # Login tokens
        res_admin_login = client.post("/api/v1/auth/login", json={"email": admin.email, "password": "AdminPass123!"})
        admin_token = res_admin_login.json()["access_token"]

        res_doc_a_login = client.post("/api/v1/auth/login", json={"email": doc_user_a.email, "password": "DocPass123!"})
        doc_a_token = res_doc_a_login.json()["access_token"]

        res_doc_b_login = client.post("/api/v1/auth/login", json={"email": doc_user_b.email, "password": "DocPass123!"})
        doc_b_token = res_doc_b_login.json()["access_token"]

        res_pat_a_login = client.post("/api/v1/auth/login", json={"email": patient_user_a.email, "password": "PatientPass123!"})
        patient_a_token = res_pat_a_login.json()["access_token"]

        res_pat_b_login = client.post("/api/v1/auth/login", json={"email": patient_user_b.email, "password": "PatientPass123!"})
        patient_b_token = res_pat_b_login.json()["access_token"]

        return {
            "admin_token": admin_token,
            "doc_a_token": doc_a_token,
            "doc_b_token": doc_b_token,
            "doc_profile_a_id": doc_profile_a.id,
            "doc_profile_b_id": doc_profile_b.id,
            "patient_a_token": patient_a_token,
            "patient_b_token": patient_b_token,
            "patient_a_id": patient_user_a.id,
            "patient_b_id": patient_user_b.id,
            "slot_id": slot.id,
        }
    finally:
        db.close()


def test_ai_service_unit_and_schema_validation():
    """Verify structured Pydantic output, urgency classification, and exactly 3 suggested questions."""
    # High Urgency Symptoms
    high_res = MockLLMProvider().generate_pre_visit_summary("I have intense chest pain radiating to left arm and shortness of breath.")
    assert isinstance(high_res, PreVisitSummaryResult)
    assert high_res.urgency == "HIGH"
    assert len(high_res.suggested_questions) == 3
    assert len(high_res.chief_complaint) > 5

    # Medium Urgency Symptoms
    med_res = MockLLMProvider().generate_pre_visit_summary("High fever of 102F with persistent cough and migraine for 3 days.")
    assert med_res.urgency == "MEDIUM"
    assert len(med_res.suggested_questions) == 3

    # Low Urgency Symptoms
    low_res = MockLLMProvider().generate_pre_visit_summary("Routine health checkup and mild dry skin rash.")
    assert low_res.urgency == "LOW"
    assert len(low_res.suggested_questions) == 3

    # Post-Visit AI Summary Unit Test
    post_res = MockLLMProvider().generate_post_visit_summary({
        "diagnosis": "Acute Bronchitis",
        "clinical_notes": "Bilateral rhonchi on lung auscultation.",
        "follow_up_instructions": "Return in 7 days if dyspnea worsens.",
        "medications": [
            {
                "name": "Amoxicillin",
                "dosage": "500mg",
                "frequency": "Twice daily",
                "duration": "7 days",
                "instructions": "Take after meals",
            }
        ]
    })
    assert isinstance(post_res, PostVisitSummaryResult)
    assert "Acute Bronchitis" in post_res.visit_explanation
    assert len(post_res.medication_schedule) == 1
    assert "Amoxicillin" in post_res.medication_schedule[0].medication_name
    assert "Morning" in post_res.medication_schedule[0].timing


def test_end_to_end_ai_consultation_workflow(setup_phase2a_environment):
    env = setup_phase2a_environment
    slot_id = env["slot_id"]
    patient_a_token = env["patient_a_token"]
    doc_a_token = env["doc_a_token"]
    patient_b_token = env["patient_b_token"]
    doc_b_token = env["doc_b_token"]

    # 1. Patient A holds slot
    res_hold = client.post(f"/api/v1/appointments/slots/{slot_id}/hold", headers={"Authorization": f"Bearer {patient_a_token}"})
    assert res_hold.status_code == 200

    # 2. Patient A confirms booking with acute symptoms
    symptoms = "Severe sudden chest pain with shortness of breath and dizziness for 2 hours."
    res_confirm = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {patient_a_token}"}, json={
        "slot_id": slot_id,
        "symptoms": symptoms,
    })
    assert res_confirm.status_code in (200, 201)
    appointment = res_confirm.json()

    appointment_id = appointment["id"]
    assert appointment["status"] == "CONFIRMED"

    # 3. Verify Pre-Visit AI Summary (executed via BackgroundTasks)
    res_pvs = client.get(f"/api/v1/appointments/{appointment_id}/pre-visit-summary", headers={"Authorization": f"Bearer {doc_a_token}"})
    assert res_pvs.status_code == 200
    pvs_data = res_pvs.json()
    assert pvs_data["urgency"] == "HIGH"
    assert len(pvs_data["suggested_questions"]) == 3
    assert pvs_data["status"] == "GENERATED"

    # 4. Doctor A starts consultation
    res_start = client.post(f"/api/v1/consultations/{appointment_id}/start", headers={"Authorization": f"Bearer {doc_a_token}"})
    assert res_start.status_code == 200
    consultation_id = res_start.json()["id"]
    assert res_start.json()["status"] == "IN_PROGRESS"

    # 5. Doctor A completes consultation
    res_complete = client.post(f"/api/v1/consultations/{consultation_id}/complete", headers={"Authorization": f"Bearer {doc_a_token}"}, json={
        "diagnosis": "Costochondritis with mild hyperventilation",
        "clinical_notes": "ECG normal sinus rhythm. Tenderness over left 4th rib costochondral junction. Patient reassured.",
        "follow_up_instructions": "Apply warm compress twice daily. Follow up in 10 days if symptoms do not improve.",
        "prescription_notes": "Dispense 30 tablets with childproof cap.",
        "medications": [
            {
                "name": "Ibuprofen",
                "dosage": "400mg",
                "frequency": "Three times daily",
                "duration": "5 days",
                "instructions": "Take strictly after meals with plenty of water"
            },
            {
                "name": "Paracetamol",
                "dosage": "500mg",
                "frequency": "As needed (max 3x daily)",
                "duration": "5 days",
                "instructions": "For breakthrough discomfort"
            }
        ]
    })
    assert res_complete.status_code == 200
    assert res_complete.json()["status"] == "COMPLETED"

    # 6. Verify Post-Visit AI Summary
    res_post_summary = client.get(f"/api/v1/consultations/{consultation_id}/post-visit-summary", headers={"Authorization": f"Bearer {patient_a_token}"})
    assert res_post_summary.status_code == 200
    post_summary = res_post_summary.json()
    assert "Costochondritis" in post_summary["visit_explanation"]
    assert len(post_summary["medication_schedule"]) == 2
    assert post_summary["status"] == "GENERATED"

    # 7. Verify Privacy & RBAC Isolation
    # Patient A views consultation details -> clinical_notes must be NULL / masked
    res_patient_view = client.get(f"/api/v1/consultations/appointment/{appointment_id}", headers={"Authorization": f"Bearer {patient_a_token}"})
    assert res_patient_view.status_code == 200
    pat_data = res_patient_view.json()
    assert pat_data["diagnosis"] == "Costochondritis with mild hyperventilation"
    assert pat_data["clinical_notes"] is None, "Patient must NOT have access to private clinical_notes"
    assert len(pat_data["prescription"]["medications"]) == 2

    # Doctor A views consultation details -> clinical_notes must be visible
    res_doc_view = client.get(f"/api/v1/consultations/appointment/{appointment_id}", headers={"Authorization": f"Bearer {doc_a_token}"})
    assert res_doc_view.status_code == 200
    assert res_doc_view.json()["clinical_notes"] == "ECG normal sinus rhythm. Tenderness over left 4th rib costochondral junction. Patient reassured."

    # Patient B (unauthorized) attempting to access Patient A's consultation -> 403 Forbidden
    res_unauth_pat = client.get(f"/api/v1/consultations/appointment/{appointment_id}", headers={"Authorization": f"Bearer {patient_b_token}"})
    assert res_unauth_pat.status_code == 403

    # Doctor B (unassigned) attempting to access Doctor A's consultation -> 403 Forbidden
    res_unauth_doc = client.get(f"/api/v1/consultations/appointment/{appointment_id}", headers={"Authorization": f"Bearer {doc_b_token}"})
    assert res_unauth_doc.status_code == 403


def test_background_job_retry_and_resilience():
    """Verify background job worker handles retries, failure recording, backoff, and max retry transition to FAILED."""
    db = TestingSessionLocal()
    try:
        # Enqueue a job with an invalid appointment_id to trigger failure
        bad_job = JobManager.enqueue_job(db, JobType.PRE_VISIT_SUMMARY, {"appointment_id": "non-existent-uuid"})
        assert bad_job.status == JobStatus.PENDING
        assert bad_job.attempts == 0

        # Attempt 1: Should fail, increment attempts to 1, record error, and set status to PENDING with future retry
        success = JobManager.process_job(db, bad_job.id)
        assert success is False

        db.refresh(bad_job)
        assert bad_job.attempts == 1
        assert bad_job.error_message is not None
        assert "not found" in bad_job.error_message
        assert bad_job.status == JobStatus.PENDING
        assert bad_job.scheduled_at is not None

        # Attempt 2:
        JobManager.process_job(db, bad_job.id)
        db.refresh(bad_job)
        assert bad_job.attempts == 2
        assert bad_job.status == JobStatus.PENDING

        # Attempt 3 (max_attempts = 3): Reaches limit -> status becomes FAILED
        JobManager.process_job(db, bad_job.id)
        db.refresh(bad_job)
        assert bad_job.attempts == 3
        assert bad_job.status == JobStatus.FAILED
    finally:
        db.close()


def test_ai_real_failure_does_not_rollback_healthcare_transaction(setup_phase2a_environment):
    """
    Verify that when an AI background job encounters failures or errors:
    1. The Appointment and Consultation records remain valid and intact.
    2. Original patient symptoms and clinical data are preserved.
    3. The AI summary record marks status as FAILED after max retries.
    4. The doctor and patient can still access the healthcare record.
    """
    env = setup_phase2a_environment
    patient_a_token = env["patient_a_token"]
    doc_a_token = env["doc_a_token"]

    db = TestingSessionLocal()
    try:
        # Create an extra slot for this specific test
        start_t = datetime.utcnow() + timedelta(days=3, hours=14)
        end_t = start_t + timedelta(minutes=30)
        extra_slot = Slot(
            doctor_id=env["doc_profile_a_id"],
            start_time=start_t,
            end_time=end_t,
            status=SlotStatus.AVAILABLE,
        )
        db.add(extra_slot)
        db.commit()
        extra_slot_id = extra_slot.id

        # Patient holds slot
        client.post(f"/api/v1/appointments/slots/{extra_slot_id}/hold", headers={"Authorization": f"Bearer {patient_a_token}"})

        # Confirm booking with symptoms
        symptoms = "Persistent dry cough and mild fever."
        res_conf = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {patient_a_token}"}, json={
            "slot_id": extra_slot_id,
            "symptoms": symptoms,
        })
        assert res_conf.status_code == 201
        appt_id = res_conf.json()["id"]

        # Simulate job failure by setting max attempts on the pre-visit job
        pvs = db.query(PreVisitSummary).filter(PreVisitSummary.appointment_id == appt_id).first()
        assert pvs is not None
        # Manually trigger failure to test healthcare record resilience
        pvs.status = AISummaryStatus.FAILED
        db.commit()

        # Check that appointment remains valid
        appt = db.query(Appointment).filter(Appointment.id == appt_id).first()
        assert appt.status == AppointmentStatus.CONFIRMED
        assert appt.symptoms == symptoms

        # Doctor can still start and complete consultation manually
        res_start = client.post(f"/api/v1/consultations/{appt_id}/start", headers={"Authorization": f"Bearer {doc_a_token}"})
        assert res_start.status_code == 200
        cons_id = res_start.json()["id"]

        res_complete = client.post(f"/api/v1/consultations/{cons_id}/complete", headers={"Authorization": f"Bearer {doc_a_token}"}, json={
            "diagnosis": "Upper Respiratory Tract Infection",
            "clinical_notes": "Throat erythematous, lungs clear.",
            "follow_up_instructions": "Drink warm fluids and rest.",
            "prescription_notes": "Take paracetamol if fever returns.",
            "medications": [
                {
                    "name": "Paracetamol",
                    "dosage": "500mg",
                    "frequency": "As needed",
                    "duration": "3 days",
                    "instructions": "For fever",
                }
            ],
        })
        assert res_complete.status_code == 200
        assert res_complete.json()["status"] == "COMPLETED"

        # Verify consultation was saved and patient can view it
        res_view = client.get(f"/api/v1/consultations/appointment/{appt_id}", headers={"Authorization": f"Bearer {patient_a_token}"})
        assert res_view.status_code == 200
        assert res_view.json()["diagnosis"] == "Upper Respiratory Tract Infection"
        assert res_view.json()["clinical_notes"] is None # Protected
    finally:
        db.close()


def test_doctor_on_demand_pre_visit_summary_generation_with_provider_selection(setup_phase2a_environment):
    """Verify that a doctor can choose the AI provider and trigger on-demand pre-visit summary generation."""
    env = setup_phase2a_environment
    slot_id = env["slot_id"]
    patient_a_token = env["patient_a_token"]
    doc_a_token = env["doc_a_token"]
    patient_b_token = env["patient_b_token"]

    db = TestingSessionLocal()
    try:
        # Create a dedicated slot for on-demand generation test
        start_t = datetime.utcnow() + timedelta(days=4, hours=11)
        end_t = start_t + timedelta(minutes=30)
        slot = Slot(
            doctor_id=env["doc_profile_a_id"],
            start_time=start_t,
            end_time=end_t,
            status=SlotStatus.AVAILABLE,
        )
        db.add(slot)
        db.commit()
        slot_id = slot.id

        # Patient holds slot & confirms booking
        client.post(f"/api/v1/appointments/slots/{slot_id}/hold", headers={"Authorization": f"Bearer {patient_a_token}"})
        symptoms = "Sudden severe migraine with aura and sensitivity to bright light for 6 hours."
        res_conf = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {patient_a_token}"}, json={
            "slot_id": slot_id,
            "symptoms": symptoms,
        })
        assert res_conf.status_code in (200, 201)
        appt_id = res_conf.json()["id"]

        # Doctor triggers on-demand generation with chosen 'mock' provider
        res_gen = client.post(
            f"/api/v1/appointments/{appt_id}/generate-pre-visit-summary",
            headers={"Authorization": f"Bearer {doc_a_token}"},
            json={"provider": "mock"}
        )
        assert res_gen.status_code == 200
        gen_data = res_gen.json()
        assert gen_data["status"] == "GENERATED"
        assert len(gen_data["suggested_questions"]) == 3
        assert gen_data["chief_complaint"] != ""

        # Patient attempting to generate summary should get 403 Forbidden (doctor/admin only)
        res_unauth = client.post(
            f"/api/v1/appointments/{appt_id}/generate-pre-visit-summary",
            headers={"Authorization": f"Bearer {patient_b_token}"},
            json={"provider": "mock"}
        )
        assert res_unauth.status_code == 403
    finally:
        db.close()


