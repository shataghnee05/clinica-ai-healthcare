# Clinica — Healthcare Appointment & AI Clinical Intelligence Platform

A full-stack, concurrency-safe healthcare platform built with **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL** (Supabase-ready), **Google Gemini AI**, and **React 18** (TypeScript + Tailwind CSS).

---

## 🌟 Key Features

### 1. Concurrency-Safe Appointment Booking
- **Atomic Optimistic Locking & Slot Holds**: 5-minute temporary reservation holds with atomic compare-and-swap (CAS) updates to prevent double bookings under high traffic.
- **Dynamic Slot Generation**: Configurable weekly physician working hours and custom slot durations (15m, 30m, 45m, 60m).

### 2. Google Gemini AI Clinical Intelligence
- **Pre-Visit SOAP Assistant**: Analyzes patient-reported symptoms to generate triage urgency ratings (`LOW`, `MEDIUM`, `HIGH`), chief complaint summaries, and 3 targeted clinical questions.
- **Post-Visit Summary & Rx Schedule**: Generates plain-English patient recovery explanations and structured medication schedules.
- **Resilient Background Processing**: Non-blocking asynchronous job execution with exponential backoff retries.

### 3. Doctor Leave Application & Admin Oversight
- **Doctor Leave Requests**: Physicians apply for leaves with conflict previews without pre-emptively cancelling patient bookings.
- **Admin Approval & Rejection Flow**: Admins review leave requests with status filters (`ALL`, `PENDING`, `APPROVED`, `REJECTED`). Rejections include custom explanations delivered to the physician.
- **Disrupted Slot Rescheduling**: Doctors can reassign and reschedule leave-disrupted appointments to new available slots for patients.

### 4. Admin Doctor Management
- Dedicated **Doctor Registration Modal** with automatic 14-day schedule generation, accepted insurances, and custom slot durations.

### 5. Multi-Role RBAC & Patient Engagement
- Strict permission boundaries for `PATIENT`, `DOCTOR`, and `ADMIN` using signed JWT tokens.
- In-app notification center and automated medication reminder tracking.
- Sleek modern UI with dynamic light and dark theme modes.

---

## 🚀 Getting Started

### 1. Environment Configuration
Copy the template and configure your environment variables:
```bash
cp .env.example .env
```
Fill in your `DATABASE_URL`, `SECRET_KEY`, and `GEMINI_API_KEY` in `.env`.

### 2. Backend Setup
```bash
cd backend
pip install -r requirements.txt
python -m app.seed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

The application will be available at `http://127.0.0.1:5173/`.

