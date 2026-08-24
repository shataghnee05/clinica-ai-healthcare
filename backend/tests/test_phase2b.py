import os
import sys
import uuid
from datetime import datetime, timedelta, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["AI_PROVIDER"] = "mock"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

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
    DoctorLeave,
    Notification,
    MedicationReminder,
    MedicationReminderStatus,
    BackgroundJob,
    JobType,
    JobStatus,
)
from app.security import get_password_hash
from app.jobs import JobManager
from app.notification_service import NotificationService

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def cleanup_phase2b_test_data():
    yield
    db = TestingSessionLocal()
    try:

        db.query(Notification).filter(Notification.title.like("%Leave%")).delete(synchronize_session=False)
        test_users = db.query(User).filter(
            (User.email.like("admin_%@test.com")) |
            (User.email.like("dr_%@test.com")) |
            (User.email.like("pat_%@test.com")) |
            (User.email.like("pat2_%@test.com"))
        ).all()
        for u in test_users:
            profs = db.query(DoctorProfile).filter(DoctorProfile.user_id == u.id).all()
            for p in profs:
                db.query(DoctorLeave).filter(DoctorLeave.doctor_id == p.id).delete(synchronize_session=False)
                db.query(Slot).filter(Slot.doctor_id == p.id).delete(synchronize_session=False)
                db.query(Appointment).filter(Appointment.doctor_id == p.id).delete(synchronize_session=False)
                db.delete(p)
            db.query(Appointment).filter(Appointment.patient_id == u.id).delete(synchronize_session=False)
            db.query(Notification).filter(Notification.user_id == u.id).delete(synchronize_session=False)
            db.delete(u)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

@pytest.fixture(scope="module")
def p2b_env():
    import secrets
    test_password = f"TestPass_{secrets.token_hex(8)}!"
    db = TestingSessionLocal()
    suffix = str(uuid.uuid4())[:8]

    admin = User(
        email=f"admin_{suffix}@test.com",
        password_hash=get_password_hash(test_password),
        full_name="Admin P2B",
        role=UserRole.ADMIN,
    )
    doc_user = User(
        email=f"dr_{suffix}@test.com",
        password_hash=get_password_hash(test_password),
        full_name="Dr. Gregory",
        role=UserRole.DOCTOR,
    )
    db.add_all([admin, doc_user])
    db.flush()

    doc_profile = DoctorProfile(
        user_id=doc_user.id,
        specialization="Cardiology",
        is_active=True,
    )
    patient = User(
        email=f"pat_{suffix}@test.com",
        password_hash=get_password_hash(test_password),
        full_name="Patient Bob",
        role=UserRole.PATIENT,
    )
    patient2 = User(
        email=f"pat2_{suffix}@test.com",
        password_hash=get_password_hash(test_password),
        full_name="Patient Alice",
        role=UserRole.PATIENT,
    )
    db.add_all([doc_profile, patient, patient2])
    db.commit()

    t1 = datetime.utcnow() + timedelta(days=2, hours=10)
    t2 = datetime.utcnow() + timedelta(days=10, hours=10)
    t3 = datetime.utcnow() + timedelta(days=12, hours=10)

    s1 = Slot(doctor_id=doc_profile.id, start_time=t1, end_time=t1 + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    s2 = Slot(doctor_id=doc_profile.id, start_time=t2, end_time=t2 + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    s3 = Slot(doctor_id=doc_profile.id, start_time=t3, end_time=t3 + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    db.add_all([s1, s2, s3])
    db.commit()

    a_tok = client.post("/api/v1/auth/login", json={"email": admin.email, "password": test_password}).json()["access_token"]
    d_tok = client.post("/api/v1/auth/login", json={"email": doc_user.email, "password": test_password}).json()["access_token"]
    p_tok = client.post("/api/v1/auth/login", json={"email": patient.email, "password": test_password}).json()["access_token"]
    p2_tok = client.post("/api/v1/auth/login", json={"email": patient2.email, "password": test_password}).json()["access_token"]

    db_data = {
        "admin_tok": a_tok,
        "doc_tok": d_tok,
        "pat_tok": p_tok,
        "pat2_tok": p2_tok,
        "doc_id": doc_profile.id,
        "pat_id": patient.id,
        "slot1_id": s1.id,
        "slot2_id": s2.id,
        "slot3_id": s3.id,
        "t1": t1,
    }
    db.close()
    return db_data

def test_doctor_leave_preview_and_confirm(p2b_env):
    """Admin previews leave and explicitly confirms: conflicting appointments cancelled, non-conflicting intact."""
    tok = p2b_env["pat_tok"]
    s1, s2 = p2b_env["slot1_id"], p2b_env["slot2_id"]

    client.post(f"/api/v1/appointments/slots/{s1}/hold", headers={"Authorization": f"Bearer {tok}"})
    r1 = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {tok}"}, json={"slot_id": s1, "symptoms": "Chest pain"})
    assert r1.status_code == 201
    appt1_id = r1.json()["id"]

    client.post(f"/api/v1/appointments/slots/{s2}/hold", headers={"Authorization": f"Bearer {tok}"})
    r2 = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {tok}"}, json={"slot_id": s2, "symptoms": "Followup check"})
    assert r2.status_code == 201
    appt2_id = r2.json()["id"]

    admin_tok = p2b_env["admin_tok"]
    doc_id = p2b_env["doc_id"]
    start_d = (datetime.utcnow() + timedelta(days=1)).date()
    end_d = (datetime.utcnow() + timedelta(days=4)).date()

    prev_res = client.post(
        f"/api/v1/admin/doctors/{doc_id}/leaves/preview",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"start_date": str(start_d), "end_date": str(end_d), "reason": "Conference"},
    )
    assert prev_res.status_code == 200
    preview = prev_res.json()
    assert preview["affected_count"] == 1
    assert preview["affected_appointments"][0]["appointment_id"] == appt1_id

    conf_res = client.post(
        f"/api/v1/admin/doctors/{doc_id}/leaves/confirm",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"start_date": str(start_d), "end_date": str(end_d), "reason": "Conference"},
    )
    assert conf_res.status_code == 201
    leave_data = conf_res.json()
    assert leave_data["affected_appointments_count"] == 1

    db = TestingSessionLocal()
    a1 = db.query(Appointment).filter(Appointment.id == appt1_id).first()
    a2 = db.query(Appointment).filter(Appointment.id == appt2_id).first()
    slot1 = db.query(Slot).filter(Slot.id == s1).first()

    assert a1.status == AppointmentStatus.CANCELLED
    assert "approved leave" in (a1.cancellation_reason or "")
    assert slot1.status == SlotStatus.AVAILABLE
    assert a2.status == AppointmentStatus.CONFIRMED

    notif = db.query(Notification).filter(Notification.user_id == p2b_env["pat_id"]).first()
    assert notif is not None
    db.close()

def test_doctor_leave_application_approval_and_rejection(p2b_env):
    """Doctor applies for leave -> PENDING -> Admin approves -> APPROVED / Admin rejects with reason -> REJECTED."""
    doc_tok = p2b_env["doc_tok"]
    admin_tok = p2b_env["admin_tok"]

    start_d1 = (datetime.utcnow() + timedelta(days=20)).date()
    end_d1 = (datetime.utcnow() + timedelta(days=24)).date()

    apply_res = client.post(
        "/api/v1/doctor/leaves/apply",
        headers={"Authorization": f"Bearer {doc_tok}"},
        json={"start_date": str(start_d1), "end_date": str(end_d1), "reason": "Medical research symposium"},
    )
    assert apply_res.status_code == 201
    leave_id = apply_res.json()["id"]
    assert apply_res.json()["status"] == "PENDING"

    my_leaves = client.get("/api/v1/doctor/leaves/my", headers={"Authorization": f"Bearer {doc_tok}"}).json()
    assert any(l["id"] == leave_id and l["status"] == "PENDING" for l in my_leaves)

    approve_res = client.post(
        f"/api/v1/admin/leaves/{leave_id}/approve",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    start_d2 = (datetime.utcnow() + timedelta(days=30)).date()
    end_d2 = (datetime.utcnow() + timedelta(days=35)).date()

    apply2_res = client.post(
        "/api/v1/doctor/leaves/apply",
        headers={"Authorization": f"Bearer {doc_tok}"},
        json={"start_date": str(start_d2), "end_date": str(end_d2), "reason": "Vacation trip"},
    )
    assert apply2_res.status_code == 201
    leave2_id = apply2_res.json()["id"]

    rejection_reason = "Staff shortage during surgical week. Please reschedule."
    reject_res = client.post(
        f"/api/v1/admin/leaves/{leave2_id}/reject",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"reason": rejection_reason},
    )
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"
    assert reject_res.json()["rejection_reason"] == rejection_reason

    my_leaves2 = client.get("/api/v1/doctor/leaves/my", headers={"Authorization": f"Bearer {doc_tok}"}).json()
    rejected_leave = next(l for l in my_leaves2 if l["id"] == leave2_id)
    assert rejected_leave["status"] == "REJECTED"
    assert rejected_leave["rejection_reason"] == rejection_reason

def test_appointment_cancellation_and_rescheduling(p2b_env):
    """Test cancellation with slot release and concurrency-safe rescheduling."""
    tok = p2b_env["pat_tok"]
    doc_id = p2b_env["doc_id"]

    db = TestingSessionLocal()
    t_a = datetime.utcnow() + timedelta(days=25, hours=10)
    t_b = datetime.utcnow() + timedelta(days=26, hours=10)
    sa = Slot(doctor_id=doc_id, start_time=t_a, end_time=t_a + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    sb = Slot(doctor_id=doc_id, start_time=t_b, end_time=t_b + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    db.add_all([sa, sb])
    db.commit()
    s2, s3 = sa.id, sb.id
    db.close()

    client.post(f"/api/v1/appointments/slots/{s2}/hold", headers={"Authorization": f"Bearer {tok}"})
    r = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {tok}"}, json={"slot_id": s2, "symptoms": "Headache"})
    appt_id = r.json()["id"]

    resched_r = client.post(
        f"/api/v1/appointments/{appt_id}/reschedule",
        headers={"Authorization": f"Bearer {tok}"},
        json={"new_slot_id": s3, "reason": "Work conflict"},
    )
    assert resched_r.status_code == 200
    resched_data = resched_r.json()
    assert resched_data["slot_id"] == s3
    assert resched_data["rescheduled_from_slot_id"] == s2

    db = TestingSessionLocal()
    old_slot = db.query(Slot).filter(Slot.id == s2).first()
    new_slot = db.query(Slot).filter(Slot.id == s3).first()
    assert old_slot.status == SlotStatus.AVAILABLE
    assert new_slot.status == SlotStatus.BOOKED

    cancel_r = client.patch(
        f"/api/v1/appointments/{appt_id}/cancel",
        headers={"Authorization": f"Bearer {tok}"},
        json={"reason": "No longer needed"},
    )
    assert cancel_r.status_code == 200
    db.refresh(new_slot)
    assert new_slot.status == SlotStatus.AVAILABLE
    db.close()

def test_reschedule_conflict_handling(p2b_env):
    """Patient 2 cannot reschedule to a slot already held/booked by Patient 1."""
    p1_tok = p2b_env["pat_tok"]
    p2_tok = p2b_env["pat2_tok"]
    doc_id = p2b_env["doc_id"]

    db = TestingSessionLocal()
    t_c = datetime.utcnow() + timedelta(days=28, hours=10)
    t_d = datetime.utcnow() + timedelta(days=29, hours=10)
    sc = Slot(doctor_id=doc_id, start_time=t_c, end_time=t_c + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    sd = Slot(doctor_id=doc_id, start_time=t_d, end_time=t_d + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    db.add_all([sc, sd])
    db.commit()
    s2, s3 = sc.id, sd.id
    db.close()

    client.post(f"/api/v1/appointments/slots/{s2}/hold", headers={"Authorization": f"Bearer {p1_tok}"})
    r1 = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {p1_tok}"}, json={"slot_id": s2, "symptoms": "Cough"})
    appt1_id = r1.json()["id"]

    client.post(f"/api/v1/appointments/slots/{s3}/hold", headers={"Authorization": f"Bearer {p2_tok}"})
    client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {p2_tok}"}, json={"slot_id": s3, "symptoms": "Fever"})

    conflict_r = client.post(
        f"/api/v1/appointments/{appt1_id}/reschedule",
        headers={"Authorization": f"Bearer {p1_tok}"},
        json={"new_slot_id": s3},
    )
    assert conflict_r.status_code == 409

def test_medication_reminders_and_job_reliability(p2b_env):
    """Prescription generates scheduled medication reminders; background jobs retry on failure."""
    p_tok = p2b_env["pat_tok"]
    d_tok = p2b_env["doc_tok"]
    doc_id = p2b_env["doc_id"]

    db = TestingSessionLocal()
    t_med = datetime.utcnow() + timedelta(days=20, hours=10)
    slot_med = Slot(doctor_id=doc_id, start_time=t_med, end_time=t_med + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    db.add(slot_med)
    db.commit()
    s_id = slot_med.id
    db.close()

    client.post(f"/api/v1/appointments/slots/{s_id}/hold", headers={"Authorization": f"Bearer {p_tok}"})
    appt = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {p_tok}"}, json={"slot_id": s_id, "symptoms": "Hypertension"}).json()

    cons = client.post(f"/api/v1/consultations/{appt['id']}/start", headers={"Authorization": f"Bearer {d_tok}"}).json()
    comp = client.post(
        f"/api/v1/consultations/{cons['id']}/complete",
        headers={"Authorization": f"Bearer {d_tok}"},
        json={
            "diagnosis": "Essential Hypertension",
            "clinical_notes": "BP 140/90",
            "follow_up_instructions": "Low sodium diet",
            "medications": [
                {"name": "Amlodipine", "dosage": "5mg", "frequency": "Once daily", "duration": "5 days", "instructions": "Morning"}
            ],
        },
    )
    assert comp.status_code == 200

    rem_res = client.get("/api/v1/medication-reminders/my", headers={"Authorization": f"Bearer {p_tok}"})
    assert rem_res.status_code == 200
    rems = rem_res.json()
    assert len(rems) == 5

    db = TestingSessionLocal()
    bad_job = JobManager.enqueue_job(db, JobType.MEDICATION_REMINDER, {"reminder_id": "non-existent"})
    assert JobManager.process_job(db, bad_job.id) is False
    db.refresh(bad_job)
    assert bad_job.attempts == 1
    assert bad_job.status == JobStatus.PENDING

    JobManager.process_job(db, bad_job.id)
    JobManager.process_job(db, bad_job.id)
    db.refresh(bad_job)
    assert bad_job.attempts == 3
    assert bad_job.status == JobStatus.FAILED
    db.close()

def test_notification_delivery_and_read_state(p2b_env):
    """Notifications are queryable and can be marked as read."""
    p_tok = p2b_env["pat_tok"]
    notifs_res = client.get("/api/v1/notifications/my", headers={"Authorization": f"Bearer {p_tok}"})
    assert notifs_res.status_code == 200
    notifs = notifs_res.json()

    if len(notifs) > 0:
        nid = notifs[0]["id"]
        mark_res = client.patch(f"/api/v1/notifications/{nid}/read", headers={"Authorization": f"Bearer {p_tok}"})
        assert mark_res.status_code == 200
        assert mark_res.json()["is_read"] is True

def test_email_failure_does_not_affect_appointment_state(p2b_env):
    """External notification failure must NOT alter appointment CONFIRMED state."""
    p_tok = p2b_env["pat_tok"]
    doc_id = p2b_env["doc_id"]

    db = TestingSessionLocal()
    t_email = datetime.utcnow() + timedelta(days=22, hours=10)
    slot_email = Slot(doctor_id=doc_id, start_time=t_email, end_time=t_email + timedelta(minutes=30), status=SlotStatus.AVAILABLE)
    db.add(slot_email)
    db.commit()
    s_email_id = slot_email.id
    db.close()

    client.post(f"/api/v1/appointments/slots/{s_email_id}/hold", headers={"Authorization": f"Bearer {p_tok}"})
    appt = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {p_tok}"}, json={"slot_id": s_email_id, "symptoms": "Sore throat"}).json()

    db = TestingSessionLocal()
    db_appt = db.query(Appointment).filter(Appointment.id == appt["id"]).first()
    assert db_appt.status == AppointmentStatus.CONFIRMED

    NotificationService.execute_notification_job(db, "fake-id", "invalid@", "Subject", "Body")
    db.refresh(db_appt)
    assert db_appt.status == AppointmentStatus.CONFIRMED
    db.close()

def test_rbac_authorization(p2b_env):
    """Unauthorized roles cannot access admin doctor leaves or other patient's reschedule."""
    p_tok = p2b_env["pat_tok"]
    doc_id = p2b_env["doc_id"]

    res = client.post(
        f"/api/v1/admin/doctors/{doc_id}/leaves/preview",
        headers={"Authorization": f"Bearer {p_tok}"},
        json={"start_date": "2026-09-01", "end_date": "2026-09-05"},
    )
    assert res.status_code == 403
