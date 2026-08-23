import os
import secrets
import sys
from datetime import date, timedelta
from app.models import (
    SessionLocal,
    User,
    UserRole,
    DoctorProfile,
    Slot,
    Appointment,
    DoctorLeave,
    Consultation,
    Prescription,
    Medication,
    MedicationReminder,
    Notification,
    PreVisitSummary,
    PostVisitSummary,
    UserGoogleAccount,
)
from app.security import get_password_hash
from app.services import DoctorService, SlotService
from app.schemas import DoctorCreate

def clean_old_and_test_accounts(db):
    """
    Remove legacy test accounts and old British seeded doctor accounts cleanly.
    """
    old_doctor_patterns = [
        "dr.house@clinica.health",
        "dr.cuddy@clinica.health",
        "dr.wilson@clinica.health",
        "dr.cameron@clinica.health",
        "dr.cuddy@unthinkable.ai",
        "dr.wilson@unthinkable.ai",
        "dr.cameron@unthinkable.ai",
    ]

    all_users = db.query(User).all()
    target_user_ids = []

    for user in all_users:
        email = (user.email or "").lower()
        full_name = (user.full_name or "").lower()

        is_old_doctor = (
            email in old_doctor_patterns
            or "gregory house" in full_name
            or "lisa cuddy" in full_name
            or "james wilson" in full_name
            or "allison cameron" in full_name
            or full_name in (
                "dr. gregory",
                "dr. testing specialist",
                "dr. 20-thread race condition test",
                "dr. expired hold test",
            )
        )

        is_test_account = (
            email.endswith("@example.com")
            or email.endswith("@test.com")
            or email.endswith("@testdomain.com")
            or "test" in email
            or "race_" in email
            or "pat_" in email
            or "pat2_" in email
            or "admin_e9cc" in email
            or "dr_e9cc" in email
            or "admin_4e8f" in email
            or "dr_4e8f" in email
            or "gandu" in email
        )

        if is_old_doctor or is_test_account:
            target_user_ids.append(user.id)
            print(f"[CLEANUP TARGET] Found: {user.full_name} ({user.email}) [{user.role.value}]")

    if not target_user_ids:
        print("[CLEANUP] No test accounts or old British doctor accounts found.")
        return

    # Find DoctorProfiles linked to target users
    target_doctor_profiles = db.query(DoctorProfile).filter(DoctorProfile.user_id.in_(target_user_ids)).all()
    target_doc_profile_ids = [p.id for p in target_doctor_profiles]

    # 1. Delete dependent summaries & consultations linked to appointments
    target_appts = db.query(Appointment).filter(
        (Appointment.patient_id.in_(target_user_ids)) | (Appointment.doctor_id.in_(target_doc_profile_ids))
    ).all()
    target_appt_ids = [a.id for a in target_appts]

    if target_appt_ids:
        db.query(PreVisitSummary).filter(PreVisitSummary.appointment_id.in_(target_appt_ids)).delete(synchronize_session=False)
        consultations = db.query(Consultation).filter(Consultation.appointment_id.in_(target_appt_ids)).all()
        for c in consultations:
            db.query(PostVisitSummary).filter(PostVisitSummary.consultation_id == c.id).delete(synchronize_session=False)
            prescriptions = db.query(Prescription).filter(Prescription.consultation_id == c.id).all()
            for p in prescriptions:
                meds = db.query(Medication).filter(Medication.prescription_id == p.id).all()
                for m in meds:
                    db.query(MedicationReminder).filter(MedicationReminder.medication_id == m.id).delete(synchronize_session=False)
                    db.delete(m)
                db.delete(p)
            db.delete(c)
        db.query(Appointment).filter(Appointment.id.in_(target_appt_ids)).delete(synchronize_session=False)

    # 2. Clear held slots
    db.query(Slot).filter(Slot.held_by_patient_id.in_(target_user_ids)).update({
        Slot.held_by_patient_id: None,
        Slot.status: "AVAILABLE",
        Slot.hold_expires_at: None,
    }, synchronize_session=False)

    # 3. Delete slots of target doctors
    if target_doc_profile_ids:
        db.query(DoctorLeave).filter(DoctorLeave.doctor_id.in_(target_doc_profile_ids)).delete(synchronize_session=False)
        db.query(Slot).filter(Slot.doctor_id.in_(target_doc_profile_ids)).delete(synchronize_session=False)
        db.query(DoctorProfile).filter(DoctorProfile.id.in_(target_doc_profile_ids)).delete(synchronize_session=False)

    # 4. Delete notifications & google accounts of target users
    db.query(Notification).filter(Notification.user_id.in_(target_user_ids)).delete(synchronize_session=False)
    db.query(UserGoogleAccount).filter(UserGoogleAccount.user_id.in_(target_user_ids)).delete(synchronize_session=False)
    db.query(MedicationReminder).filter(MedicationReminder.patient_id.in_(target_user_ids)).delete(synchronize_session=False)

    # 5. Delete Users
    deleted_count = db.query(User).filter(User.id.in_(target_user_ids)).delete(synchronize_session=False)
    db.commit()
    print(f"[CLEANUP] Successfully purged {deleted_count} legacy test & old doctor accounts from database.")


def seed():
    """
    Database seeder for Clinica healthcare platform.
    Cleans up old test / British doctor accounts and seeds authentic Indian doctors with available consultation slots.
    """
    environment = os.getenv("ENV", "development").lower()
    if environment == "production":
        print("[SECURITY NOTICE] Seeding is disabled in production environment.")
        return

    db = SessionLocal()

    try:
        # Step 1: Clean legacy test and British doctor accounts
        clean_old_and_test_accounts(db)

        # Step 2: Resolve doctor password
        doctor_password = os.getenv("SEED_DOCTOR_PASSWORD", "ClinicaDoctor2026!")

        # Step 3: Authentic Indian Doctors to seed
        doctors_to_create = [
            {
                "email": "dr.rajesh.sharma@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Rajesh Sharma",
                "specialization": "Cardiology",
                "bio": "Senior Consultant Interventional Cardiologist with over 18 years of clinical expertise. Specializes in preventive cardiovascular health, coronary management, and hypertension care.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "BlueCross", "UnitedHealthcare", "Cigna", "Star Health", "Max Bupa"],
            },
            {
                "email": "dr.priya.patel@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Priya Patel",
                "specialization": "Dermatology",
                "bio": "Lead Clinical Dermatologist and Trichology Specialist. Specializes in autoimmune dermatoses, clinical acne therapies, and diagnostic skin pathology.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "BlueCross", "Cigna", "HDFC ERGO", "Apollo Munich"],
            },
            {
                "email": "dr.ananya.mukherjee@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Ananya Mukherjee",
                "specialization": "Endocrinology",
                "bio": "Chief Endocrinologist and Metabolic Wellness Specialist. Expert in insulin resistance, thyroid disorders, gestational diabetes, and hormonal imbalance therapies.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["BlueCross", "Cigna", "UnitedHealthcare", "Star Health", "Care Health"],
            },
            {
                "email": "dr.vikram.sengupta@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Vikram Sengupta",
                "specialization": "Internal Medicine",
                "bio": "Director of Internal Medicine and Complex Diagnostic Evaluation. Specializes in multi-system health assessments, adult preventive medicine, and diagnostic investigations.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "BlueCross", "UnitedHealthcare", "Cigna", "Max Bupa"],
            },
            {
                "email": "dr.arvind.swaminathan@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Arvind Swaminathan",
                "specialization": "Neurology",
                "bio": "Senior Consultant Neurologist and Neuro-Assessment Specialist. Focuses on neuro-vascular health, migraine therapies, neuropathy management, and cognitive care.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "BlueCross", "Cigna", "HDFC ERGO", "Tata AIG"],
            },
            {
                "email": "dr.sunita.rao@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Sunita Rao",
                "specialization": "Pediatrics",
                "bio": "Senior Pediatric Specialist and Child Wellness Consultant with 15+ years experience in developmental assessments, pediatric vaccinations, and adolescent health.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "BlueCross", "UnitedHealthcare", "Star Health", "Care Health"],
            },
        ]

        for d in doctors_to_create:
            existing = db.query(User).filter(User.email == d["email"]).first()
            today = date.today()
            if not existing:
                profile = DoctorService.create_doctor(db, DoctorCreate(**d))
                SlotService.generate_slots_for_doctor(db, profile.id, today, today + timedelta(days=14))
                print(f"[DEV SEED] Created physician: {d['full_name']} ({d['email']}) — {d['specialization']}")
            else:
                profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == existing.id).first()
                if profile:
                    profile.specialization = d["specialization"]
                    profile.bio = d["bio"]
                    existing.full_name = d["full_name"]
                    db.commit()
                    SlotService.generate_slots_for_doctor(db, profile.id, today, today + timedelta(days=14))
                    print(f"[DEV SEED] Refreshed physician: {d['full_name']} ({d['email']})")

        # Step 4: Development Admin User
        admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@clinica.health")
        admin_password = os.getenv("SEED_ADMIN_PASSWORD", "ClinicaAdmin2026!")
        existing_admin = db.query(User).filter(User.email == admin_email).first()
        if not existing_admin:
            admin_user = User(
                email=admin_email,
                password_hash=get_password_hash(admin_password),
                full_name="Clinica Hospital Administrator",
                role=UserRole.ADMIN,
            )
            db.add(admin_user)
            db.commit()
            print(f"[DEV SEED] Created development admin account: {admin_email}")

        print("[DEV SEED] Database cleanup and Indian physician seeding complete.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
