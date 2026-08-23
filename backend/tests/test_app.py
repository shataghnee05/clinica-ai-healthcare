import os
import sys
import concurrent.futures
from datetime import datetime, timedelta, date, time
import uuid
import pytest
from fastapi.testclient import TestClient

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.config import settings
from app.models import get_db, Slot, SlotStatus, User, UserRole
from app.security import get_password_hash


from sqlalchemy.pool import NullPool

db_url = settings.DATABASE_URL
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine_kwargs = {"connect_args": connect_args, "pool_pre_ping": True}
if not db_url.startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(db_url, **engine_kwargs)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(scope="session")
def admin_credentials():
    """Create a temporary dynamic admin user for test runs."""
    admin_id = str(uuid.uuid4())
    rand_suffix = str(int(datetime.utcnow().timestamp()))
    email = f"test_admin_{rand_suffix}_{admin_id[:6]}@test.com"
    password = f"TestAdminSecurePass!{rand_suffix}"
    db = TestingSessionLocal()
    try:
        admin_user = User(
            id=admin_id,
            email=email,
            password_hash=get_password_hash(password),
            full_name="Dynamic Test Administrator",
            role=UserRole.ADMIN,
            accepted_insurance=["BlueCross", "Aetna", "UnitedHealthcare", "Cigna"],
        )
        db.add(admin_user)
        db.commit()
    finally:
        db.close()

    yield {"email": email, "password": password, "user_id": admin_id}

    db_cleanup = TestingSessionLocal()
    try:
        db_cleanup.query(User).filter(User.id == admin_id).delete()
        db_cleanup.commit()
    except Exception:
        db_cleanup.rollback()
    finally:
        db_cleanup.close()


@pytest.fixture(scope="session")
def admin_headers(admin_credentials):
    res_login = client.post("/api/v1/auth/login", json={
        "email": admin_credentials["email"],
        "password": admin_credentials["password"]
    })
    assert res_login.status_code == 200, f"Failed admin login: {res_login.text}"
    token = res_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_auth_registration_and_rbac():
    rand_suffix = str(uuid.uuid4())[:8]
    patient_email = f"patient_{rand_suffix}@example.com"

    res_reg = client.post("/api/v1/auth/register", json={
        "email": patient_email,
        "password": "Password123!",
        "full_name": "Test Patient",
        "accepted_insurance": ["Aetna"]
    })
    assert res_reg.status_code == 201
    reg_data = res_reg.json()
    assert reg_data["user"]["role"] == "PATIENT"
    patient_token = reg_data["access_token"]
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    res_unauth = client.get("/api/v1/admin/stats")
    assert res_unauth.status_code == 401

    res_forbidden = client.get("/api/v1/admin/stats", headers=patient_headers)
    assert res_forbidden.status_code == 403

    res_doc_forbidden = client.get("/api/v1/appointments/doctor/agenda", headers=patient_headers)
    assert res_doc_forbidden.status_code == 403

def test_admin_doctor_lifecycle_and_working_hours(admin_headers):
    rand_suffix = str(uuid.uuid4())[:8]
    doc_email = f"dr.test_{rand_suffix}@testdomain.com"

    res_create = client.post("/api/v1/admin/doctors", headers=admin_headers, json={
        "email": doc_email,
        "password": "DocPassword123!",
        "full_name": "Dr. Testing Specialist",
        "specialization": "Neurology",
        "bio": "Expert in neurological conditions",
        "slot_duration_minutes": 30,
        "accepted_insurance": ["Aetna", "Cigna"]
    })
    assert res_create.status_code == 201
    doc_data = res_create.json()
    doctor_id = doc_data["id"]

    res_update = client.put(f"/api/v1/admin/doctors/{doctor_id}", headers=admin_headers, json={
        "specialization": "Neuro-Oncology",
        "slot_duration_minutes": 45
    })
    assert res_update.status_code == 200
    assert res_update.json()["specialization"] == "Neuro-Oncology"
    assert res_update.json()["slot_duration_minutes"] == 45

    res_deactivate = client.patch(f"/api/v1/admin/doctors/{doctor_id}/status", headers=admin_headers, json={
        "is_active": False
    })
    assert res_deactivate.status_code == 200
    assert res_deactivate.json()["is_active"] is False

    res_public_list = client.get("/api/v1/doctors?specialization=Neuro-Oncology")
    assert res_public_list.status_code == 200
    matching = [d for d in res_public_list.json() if d["id"] == doctor_id]
    assert len(matching) == 0

    res_reactivate = client.patch(f"/api/v1/admin/doctors/{doctor_id}/status", headers=admin_headers, json={
        "is_active": True
    })
    assert res_reactivate.status_code == 200
    assert res_reactivate.json()["is_active"] is True

    res_invalid_wh = client.put(f"/api/v1/admin/doctors/{doctor_id}/working-hours", headers=admin_headers, json={
        "hours": [
            {"day_of_week": 0, "start_time": "17:00", "end_time": "09:00", "is_day_off": False}
        ]
    })
    assert res_invalid_wh.status_code == 400

    res_valid_wh = client.put(f"/api/v1/admin/doctors/{doctor_id}/working-hours", headers=admin_headers, json={
        "hours": [
            {"day_of_week": 0, "start_time": "08:00", "end_time": "16:00", "is_day_off": False},
            {"day_of_week": 1, "start_time": "08:00", "end_time": "16:00", "is_day_off": False}
        ]
    })
    assert res_valid_wh.status_code == 200

def test_slot_generation_and_20_threads_concurrency_race(admin_headers):
    rand_suffix = str(uuid.uuid4())[:8]
    doc_email = f"dr.race_{rand_suffix}@testdomain.com"

    res_create = client.post("/api/v1/admin/doctors", headers=admin_headers, json={
        "email": doc_email,
        "password": "DocPassword123!",
        "full_name": "Dr. 20-Thread Race Condition Test",
        "specialization": "Cardiology",
        "bio": "Cardiology specialist for high concurrency tests",
        "slot_duration_minutes": 30,
        "accepted_insurance": ["Aetna"]
    })
    assert res_create.status_code == 201
    doctor_id = res_create.json()["id"]

    days_ahead = 1
    target_date = date.today() + timedelta(days=days_ahead)
    while target_date.weekday() >= 5:
        days_ahead += 1
        target_date = date.today() + timedelta(days=days_ahead)
    target_date_str = target_date.strftime("%Y-%m-%d")

    res_gen = client.post(f"/api/v1/admin/doctors/{doctor_id}/generate-slots", headers=admin_headers, json={
        "start_date": target_date_str,
        "end_date": target_date_str
    })
    assert res_gen.status_code == 200
    assert res_gen.json()["slots_created"] > 0

    res_slots = client.get(f"/api/v1/doctors/{doctor_id}/slots?slot_date={target_date_str}")
    assert res_slots.status_code == 200
    slots = res_slots.json()
    assert len(slots) > 0
    target_slot_id = slots[0]["id"]

    num_concurrent_patients = 20
    patient_tokens = []
    patient_ids = []

    # Bulk create 20 test patients for concurrent execution
    fixed_hash = get_password_hash("Password123!")
    db = TestingSessionLocal()
    try:
        users_to_add = []
        for i in range(num_concurrent_patients):
            uid = str(uuid.uuid4())
            p_email = f"patient_race_{i}_{rand_suffix}@example.com"
            u = User(
                id=uid,
                email=p_email,
                password_hash=fixed_hash,
                full_name=f"Concurrent Patient {i}",
                role=UserRole.PATIENT,
                accepted_insurance=["Aetna"],
            )
            users_to_add.append(u)
            patient_ids.append(uid)
            from app.security import create_access_token
            patient_tokens.append(create_access_token(subject=uid, role=UserRole.PATIENT.value))
        db.bulk_save_objects(users_to_add)
        db.commit()
    finally:
        db.close()


    def try_hold(args):
        token, p_id = args
        session = TestingSessionLocal()
        try:
            from app.services import AppointmentService
            from fastapi import HTTPException
            slot = AppointmentService.hold_slot(session, target_slot_id, p_id)
            return (token, p_id, 200, slot)
        except HTTPException as exc:
            return (token, p_id, exc.status_code, None)
        finally:
            session.close()

    # Concurrently execute 20 simultaneous hold requests against PostgreSQL
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent_patients) as executor:
        results = list(executor.map(try_hold, list(zip(patient_tokens, patient_ids))))

    successes = [r for r in results if r[2] == 200]
    conflicts = [r for r in results if r[2] == 409]

    # Exactly ONE must succeed, and all 19 other concurrent attempts must receive 409 Conflict
    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}"
    assert len(conflicts) == num_concurrent_patients - 1, f"Expected {num_concurrent_patients - 1} conflicts, got {len(conflicts)}"

    winning_token = successes[0][0]
    losing_token = conflicts[0][0]


    # Confirm appointment by losing patient must fail with 409 Conflict
    symptoms_text = "Severe chest discomfort and palpitations."
    res_bad_confirm = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {losing_token}"}, json={
        "slot_id": target_slot_id,
        "symptoms": symptoms_text
    })
    assert res_bad_confirm.status_code in (400, 409)

    # Empty symptoms validation
    res_empty_symptoms = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {winning_token}"}, json={
        "slot_id": target_slot_id,
        "symptoms": "   "
    })
    assert res_empty_symptoms.status_code == 422

    # Successful confirmation by winning patient
    res_good_confirm = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {winning_token}"}, json={
        "slot_id": target_slot_id,
        "symptoms": symptoms_text
    })
    assert res_good_confirm.status_code == 201
    appt_data = res_good_confirm.json()
    assert appt_data["symptoms"] == symptoms_text
    assert appt_data["status"] == "CONFIRMED"
    appt_id = appt_data["id"]

    # Doctor agenda check
    res_doc_login = client.post("/api/v1/auth/login", json={
        "email": doc_email,
        "password": "DocPassword123!"
    })
    assert res_doc_login.status_code == 200
    doc_token = res_doc_login.json()["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    res_agenda = client.get("/api/v1/appointments/doctor/agenda", headers=doc_headers)
    assert res_agenda.status_code == 200
    agenda = res_agenda.json()
    assert len(agenda) == 1
    assert agenda[0]["symptoms"] == symptoms_text

    # Unauthorized cancel attempt must return 403 Forbidden
    res_unauth_cancel = client.patch(f"/api/v1/appointments/{appt_id}/cancel", headers={"Authorization": f"Bearer {losing_token}"})
    assert res_unauth_cancel.status_code == 403

    # Authorized cancel by patient
    res_cancel = client.patch(f"/api/v1/appointments/{appt_id}/cancel", headers={"Authorization": f"Bearer {winning_token}"})
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "OK"

def test_expired_slot_hold_reclamation(admin_headers):
    rand_suffix = str(uuid.uuid4())[:8]
    doc_email = f"dr.expired_{rand_suffix}@testdomain.com"

    res_create = client.post("/api/v1/admin/doctors", headers=admin_headers, json={
        "email": doc_email,
        "password": "DocPassword123!",
        "full_name": "Dr. Expired Hold Test",
        "specialization": "General Medicine",
        "bio": "Test doctor for expired slot hold recovery",
        "slot_duration_minutes": 30,
        "accepted_insurance": ["Aetna"]
    })
    assert res_create.status_code == 201
    doctor_id = res_create.json()["id"]

    days_ahead = 2
    target_date = date.today() + timedelta(days=days_ahead)
    while target_date.weekday() >= 5:
        days_ahead += 1
        target_date = date.today() + timedelta(days=days_ahead)
    target_date_str = target_date.strftime("%Y-%m-%d")

    res_gen = client.post(f"/api/v1/admin/doctors/{doctor_id}/generate-slots", headers=admin_headers, json={
        "start_date": target_date_str,
        "end_date": target_date_str
    })
    assert res_gen.status_code == 200

    res_slots = client.get(f"/api/v1/doctors/{doctor_id}/slots?slot_date={target_date_str}")
    assert res_slots.status_code == 200
    slots = res_slots.json()
    assert len(slots) > 0
    slot_id = slots[0]["id"]

    # Register Patient A and acquire initial hold
    r_a = client.post("/api/v1/auth/register", json={
        "email": f"patient_a_{rand_suffix}@example.com",
        "password": "Password123!",
        "full_name": "Patient A",
        "accepted_insurance": ["Aetna"]
    })
    token_a = r_a.json()["access_token"]
    user_a_id = r_a.json()["user"]["id"]

    res_hold_a = client.post(f"/api/v1/appointments/slots/{slot_id}/hold", headers={"Authorization": f"Bearer {token_a}"})
    assert res_hold_a.status_code == 200

    # Simulate expiration in DB
    db = TestingSessionLocal()
    try:
        db_slot = db.query(Slot).filter(Slot.id == slot_id).first()
        db_slot.hold_expires_at = datetime.utcnow() - timedelta(minutes=10)
        db.commit()
    finally:
        db.close()

    # Register Patient B
    r_b = client.post("/api/v1/auth/register", json={
        "email": f"patient_b_{rand_suffix}@example.com",
        "password": "Password123!",
        "full_name": "Patient B",
        "accepted_insurance": ["Aetna"]
    })
    token_b = r_b.json()["access_token"]
    user_b_id = r_b.json()["user"]["id"]

    # Patient B should be able to reclaim expired hold
    res_hold_b = client.post(f"/api/v1/appointments/slots/{slot_id}/hold", headers={"Authorization": f"Bearer {token_b}"})
    assert res_hold_b.status_code == 200
    assert res_hold_b.json()["held_by_patient_id"] == user_b_id

    # Patient A now attempting to confirm should fail with 409
    res_a_confirm = client.post("/api/v1/appointments/confirm", headers={"Authorization": f"Bearer {token_a}"}, json={
        "slot_id": slot_id,
        "symptoms": "Old symptoms from expired hold"
    })
    assert res_a_confirm.status_code == 409

def test_admin_patient_management(admin_headers):
    rand_suffix = str(uuid.uuid4())[:8]
    p_email = f"patient_mgmt_{rand_suffix}@example.com"
    r = client.post("/api/v1/auth/register", json={
        "email": p_email,
        "password": "Password123!",
        "full_name": "Patient Management Test",
        "accepted_insurance": ["Cigna"]
    })
    assert r.status_code == 201
    patient_id = r.json()["user"]["id"]

    # Admin lists patients
    res_list = client.get("/api/v1/admin/patients", headers=admin_headers)
    assert res_list.status_code == 200
    patients = res_list.json()
    matching = [p for p in patients if p["id"] == patient_id]
    assert len(matching) == 1
    assert matching[0]["email"] == p_email

    # Admin deletes patient
    res_delete = client.delete(f"/api/v1/admin/patients/{patient_id}", headers=admin_headers)
    assert res_delete.status_code == 200
    assert res_delete.json()["status"] == "OK"

    # Verify patient is gone
    res_list_after = client.get("/api/v1/admin/patients", headers=admin_headers)
    assert res_list_after.status_code == 200
    matching_after = [p for p in res_list_after.json() if p["id"] == patient_id]
    assert len(matching_after) == 0

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data_after_tests():
    yield
    db = TestingSessionLocal()
    try:
        from sqlalchemy import text
        db.execute(text("DELETE FROM users WHERE email LIKE 'patient_mgmt_%' OR email LIKE 'patient_race_%' OR email LIKE 'patient_a_%' OR email LIKE 'patient_b_%' OR email LIKE 'dr.test_%' OR email LIKE 'dr.race_%' OR email LIKE 'dr.expired_%' OR email LIKE 'test_admin_%'"))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


