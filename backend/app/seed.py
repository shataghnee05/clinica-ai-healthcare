from datetime import date, timedelta
from app.models import SessionLocal, User, UserRole, DoctorProfile
from app.services import DoctorService, SlotService
from app.schemas import DoctorCreate

def seed():
    db = SessionLocal()

    try:
        doctors_to_create = [
            {
                "email": "dr.house@unthinkable.ai",
                "password": "DocPassword123!",
                "full_name": "Dr. Gregory House",
                "specialization": "Diagnostics",
                "bio": "Department Head of Diagnostic Medicine. Specializes in complex, rare, and undiagnosed conditions.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "BlueCross", "UnitedHealthcare", "Cigna"],
            },
            {
                "email": "dr.cuddy@unthinkable.ai",
                "password": "DocPassword123!",
                "full_name": "Dr. Lisa Cuddy",
                "specialization": "Endocrinology",
                "bio": "Dean of Medicine and Chief of Endocrinology. Specializes in hormonal and metabolic health.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["BlueCross", "Cigna", "Medicare"],
            },
            {
                "email": "dr.wilson@unthinkable.ai",
                "password": "DocPassword123!",
                "full_name": "Dr. James Wilson",
                "specialization": "Cardiology",
                "bio": "Senior Consultant in Cardiology and Preventive Cardiovascular Health.",
                "slot_duration_minutes": 30,
                "accepted_insurance": ["Aetna", "UnitedHealthcare"],
            },
            {
                "email": "dr.cameron@unthinkable.ai",
                "password": "DocPassword123!",
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
                print(f"Created doctor: {d['full_name']} and generated 14-day slots")
            else:
                profile = db.query(DoctorProfile).filter(DoctorProfile.user_id == existing.id).first()
                if profile:
                    today = date.today()
                    SlotService.generate_slots_for_doctor(db, profile.id, today, today + timedelta(days=14))

        print("Seeding complete.")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
