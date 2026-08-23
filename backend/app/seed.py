import os
import secrets
import sys
from datetime import date, timedelta
from app.models import SessionLocal, User, UserRole, DoctorProfile
from app.security import get_password_hash
from app.services import DoctorService, SlotService
from app.schemas import DoctorCreate

def seed():
    """
    Development-only database seeder for initial local testing.
    Uses environment variables for all credentials or generates secure one-time credentials.
    """
    environment = os.getenv("ENV", "development").lower()
    if environment == "production":
        print("[SECURITY NOTICE] Seeding is disabled in production environment.")
        return

    db = SessionLocal()

    try:
        # 1. Resolve Doctor Credentials from Environment or Generate Securely
        doctor_password = os.getenv("SEED_DOCTOR_PASSWORD")
        if not doctor_password:
            doctor_password = secrets.token_urlsafe(16)
            print(f"[DEV SEED] SEED_DOCTOR_PASSWORD not set. Generated dynamic doctor password: {doctor_password}")
        else:
            print("[DEV SEED] Using SEED_DOCTOR_PASSWORD from environment.")

        doctors_to_create = [
            {
                "email": "dr.house@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Gregory House",
                "specialization": "Diagnostics",
                "bio": "Department Head of Diagnostic Medicine. Specializes in complex, rare, and undiagnosed conditions.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "BlueCross", "UnitedHealthcare", "Cigna"],
            },
            {
                "email": "dr.cuddy@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Lisa Cuddy",
                "specialization": "Endocrinology",
                "bio": "Dean of Medicine and Chief of Endocrinology. Specializes in hormonal and metabolic health.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["BlueCross", "Cigna", "Medicare"],
            },
            {
                "email": "dr.wilson@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. James Wilson",
                "specialization": "Cardiology",
                "bio": "Senior Consultant in Cardiology and Preventive Cardiovascular Health.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "UnitedHealthcare"],
            },
            {
                "email": "dr.cameron@clinica.health",
                "password": doctor_password,
                "full_name": "Dr. Allison Cameron",
                "specialization": "Dermatology",
                "bio": "Clinical Specialist in Diagnostic Dermatology and Immunology.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "BlueCross", "Cigna"],
            },
        ]

        for d in doctors_to_create:
            existing = db.query(User).filter(User.email == d["email"]).first()
            if not existing:
                profile = DoctorService.create_doctor(db, DoctorCreate(**d))
                today = date.today()
                SlotService.generate_slots_for_doctor(db, profile.id, today, today + timedelta(days=14))
                print(f"[DEV SEED] Created physician: {d['full_name']} ({d['email']})")
            else:
                profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == existing.id).first()
                if profile:
                    today = date.today()
                    SlotService.generate_slots_for_doctor(db, profile.id, today, today + timedelta(days=14))

        # 2. Optional Development Admin User
        admin_email = os.getenv("SEED_ADMIN_EMAIL")
        admin_password = os.getenv("SEED_ADMIN_PASSWORD")
        if admin_email and admin_password:
            existing_admin = db.query(User).filter(User.email == admin_email).first()
            if not existing_admin:
                admin_user = User(
                    id=str(secrets.token_hex(16)),
                    email=admin_email,
                    password_hash=get_password_hash(admin_password),
                    full_name="Hospital Administrator",
                    role=UserRole.ADMIN,
                )
                db.add(admin_user)
                db.commit()
                print(f"[DEV SEED] Created development admin account: {admin_email}")

        print("[DEV SEED] Database seeding complete.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()

