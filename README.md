# Clinica — Healthcare Appointment & AI Clinical Intelligence Platform

A production-grade, concurrency-safe healthcare appointment management and clinical intelligence platform built with **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL / SQLite**, **Google Gemini AI**, **Google Calendar API**, **Resend transactional email**, and **React 19 / TypeScript / Tailwind CSS**.

Hosted Web Application: **[https://clinica-ai-healthcare-dc52.vercel.app](https://clinica-ai-healthcare-dc52.vercel.app)**  
GitHub Repository: **[https://github.com/shataghnee05/clinica-ai-healthcare](https://github.com/shataghnee05/clinica-ai-healthcare)**

---

## 📋 Table of Contents
1. [Project Overview & Objectives](#-project-overview--objectives)
2. [Complete Feature Matrix](#-complete-feature-matrix)
3. [User Workflows](#-user-workflows)
   - [Patient Workflow](#1-patient-workflow)
   - [Doctor Workflow](#2-doctor-workflow)
   - [Admin Workflow](#3-admin-workflow)
4. [Technology Stack & System Architecture](#-technology-stack--system-architecture)
5. [Local Setup & Installation Guide](#-local-setup--installation-guide)
6. [Environment Variables & Configuration (`.env.example`)](#-environment-variables--configuration-envexample)
7. [Comprehensive API Reference](#-comprehensive-api-reference)
8. [Database Schema & Entity Relationship (ER) Diagram](#-database-schema--entity-relationship-er-diagram)
9. [Google Gemini AI Clinical Intelligence Workflows](#-google-gemini-ai-clinical-intelligence-workflows)
10. [Google Calendar OAuth 2.0 Synchronization](#-google-calendar-oauth-20-synchronization)
11. [Email & Notification Infrastructure](#-email--notification-infrastructure)
12. [Background Job Worker Architecture](#-background-job-worker-architecture)
13. [Authentication & Role-Based Access Control (RBAC)](#-authentication--role-based-access-control-rbac)
14. [Testing & Quality Assurance](#-testing--quality-assurance)
15. [Deployment Guide](#-deployment-guide)
16. [Known Limitations & Design Trade-offs](#-known-limitations--design-trade-offs)
17. [Submission Checklist & 800-Word System Design Write-Up](#-submission-checklist--system-design-write-up)

---

## 🏥 Project Overview & Objectives

Clinica is designed to eliminate double bookings, streamline clinical documentation with generative AI, and automate scheduling logistics for modern healthcare systems:

1. **Zero Double-Bookings under High Concurrency**: Optimistic concurrency control (OCC) combined with timed slot holding ensures that race conditions between multiple patients booking the same slot are eliminated.
2. **AI-Powered Clinical Assistance**: Google Gemini 1.5/3.6 Flash analyzes patient-submitted symptoms before the consultation (Pre-Visit SOAP summary, triage urgency rating, 3 targeted diagnostic questions) and generates plain-language patient recovery explanations with structured medication schedules after consultation (Post-Visit summary).
3. **Doctor Leave & Schedule Disruption Resilience**: Multi-stage leave management (preview & conflict detection, doctor application `PENDING`, admin review `APPROVED` / `REJECTED` with custom justification, automatic conflict cancellation with slot release, and patient reschedule reassignment).
4. **Automated Patient Engagement**: Transactional notifications (Appointment Confirmation, Cancellation, Reschedule, Doctor Leave alerts, 24h Appointment Reminders, Scheduled Medication Reminders, and Password Reset OTPs) dispatched asynchronously via Resend/SMTP without blocking user transactions.
5. **Two-Way Google Calendar Synchronization**: OAuth 2.0 integration allowing patients and doctors to automatically reflect appointments and schedule updates in their personal Google Calendars.

---

## 🌟 Complete Feature Matrix

| Domain | Implemented Features |
| :--- | :--- |
| **Authentication & Security** | JWT-based auth (HS256, 24h expiry), role enforcement (`PATIENT`, `DOCTOR`, `ADMIN`), bcrypt password hashing, Google OAuth 2.0 Single Sign-On, 6-digit email OTP Password Reset workflow. |
| **Slot Management** | Dynamic recurring slot generation (configurable 15m, 30m, 45m, 60m duration), custom weekly working hours, day-off toggles, 5-minute atomic slot hold reservation with versioned compare-and-swap (CAS). |
| **Appointment Booking** | Symptom capture, slot reservation verification, conflict resolution, cancellation with reason, concurrency-safe patient/doctor/admin rescheduling. |
| **Clinical Consultations** | Live consultation session management, clinical notes (doctor-private), diagnosis recording, follow-up instructions, prescription & medication dosage builder. |
| **AI Clinical Intelligence** | Pre-Visit SOAP triage (`LOW`, `MEDIUM`, `HIGH`), chief complaint summary, 3 targeted physician questions, Post-Visit plain-English patient summary, structured medication schedule generation. |
| **Doctor Leave System** | Leave impact preview without cancellation, doctor leave application (`PENDING`), admin approval/rejection with custom feedback, atomic release of conflicting slots, patient leave notification dispatch. |
| **Notifications & Reminders** | In-app notification center, unread badges, mark-as-read API, 24h advance appointment reminders (patient & doctor), future-scheduled medication dose reminders across duration. |
| **Calendar Integration** | Google OAuth 2.0 authorization, token exchange & refresh, idempotent event creation, update on reschedule, and deletion on cancellation. |
| **Admin Control Center** | System health analytics, doctor directory management, doctor profile creation with automatic 14-day schedule generation, registered patient directory, background job queue inspection & manual execution. |
| **User Experience (UI/UX)** | Responsive single-page application (React 19 + Tailwind CSS 4), dark/light glassmorphic theme toggle, live hold timers, toast notifications, search filters by doctor specialization & insurance. |

---

## 🔄 User Workflows

### 1. Patient Workflow
1. **Registration / Login**: Register with email, password, and accepted insurance providers, or sign in via Google OAuth 2.0.
2. **Search & Filter Doctors**: Browse verified doctors by specialty (Cardiology, Dermatology, Endocrinology, etc.) and accepted insurance (Aetna, BlueCross, Cigna, etc.).
3. **Select & Hold Slot**: Select an available slot. The system places a **5-minute exclusive hold** on the slot with a countdown timer.
4. **Confirm Booking**: Describe symptoms (min. 3 characters) and confirm booking. An appointment confirmation email and in-app notification are triggered, and a Google Calendar event is created if connected.
5. **Pre-Visit AI Review**: View the AI-generated pre-visit triage assessment (chief complaint, urgency rating).
6. **Attend Consultation & Post-Visit Summary**: Following consultation completion by the doctor, view the post-visit summary, plain-language explanation, recovery instructions, and prescription schedule.
7. **Medication & Appointment Reminders**: Receive 24h advance appointment reminders and timed medication reminders for each dose throughout the treatment duration.
8. **Reschedule / Cancel**: Reschedule to another available slot or cancel with a reason.

### 2. Doctor Workflow
1. **Doctor Agenda & Schedule**: View daily and weekly agenda of confirmed consultations with patient details and pre-visit AI SOAP summaries.
2. **Conduct Consultation**: Start consultation session, record clinical notes (kept private from patients), diagnosis, follow-up instructions, and prescribe medications with dosage, frequency, and duration.
3. **Complete Visit**: Submitting consultation marks appointment as `COMPLETED`, triggers AI post-visit summary generation, and schedules future medication reminder jobs.
4. **Leave Application**:
   - Preview affected appointments over selected leave dates.
   - Submit leave application with reason (status set to `PENDING`).
   - View leave history and admin review feedback / rejection reasons.
5. **Manage Working Hours**: Update daily start/end times and toggle weekly days off.
6. **Reschedule Affected Appointments**: Directly reschedule leave-disrupted appointments on behalf of patients to alternative open slots.

### 3. Admin Workflow
1. **System Statistics**: Real-time dashboard showing total doctors, active patients, confirmed appointments, completed consultations, pending AI jobs, and leave requests.
2. **Physician Management**:
   - Register new doctors with specialization, bio, slot duration, and insurance.
   - Automatically generates a 14-day initial schedule.
   - Toggle physician active/inactive status or remove physician profiles.
3. **Leave Administration**:
   - Filter leave requests (`ALL`, `PENDING`, `APPROVED`, `REJECTED`).
   - Approve leave: atomically cancels conflicting appointments, releases slots, notifies affected patients, and notifies the doctor.
   - Reject leave: records administrative explanation and notifies physician.
   - Direct Admin Leave: explicitly record and approve leave directly on behalf of any physician.
4. **Patient Oversight**: View all registered patients and manage patient records.
5. **Background Job Queue**: Monitor asynchronous task execution (`PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`) and trigger manual queue processing.

---

## 🏗️ Technology Stack & System Architecture

```mermaid
graph TB
    subgraph Client ["Frontend (React 19 + TypeScript + Tailwind CSS 4)"]
        SPA["Single Page Application (Vite 8)"]
        AuthUI["Auth & Google OAuth Callback"]
        PatientPortal["Patient Dashboard & Booking"]
        DoctorPortal["Doctor Agenda & Consultation"]
        AdminPortal["Admin Management & Analytics"]
    end

    subgraph Backend ["Backend (FastAPI + Python 3.10+)"]
        API["REST API Router (/api/v1)"]
        Sec["JWT Auth & Security (HS256)"]
        ApptSvc["Appointment & Slot Concurrency Engine"]
        LeaveSvc["Doctor Leave Engine"]
        AISvc["AI Clinical Service (Google Gemini)"]
        NotifSvc["Notification Dispatcher"]
        GCalSvc["Google Calendar Service"]
        JobMgr["Asynchronous Background Job Worker"]
    end

    subgraph Database ["Database Layer"]
        DB[(PostgreSQL / Supabase / SQLite)]
    end

    subgraph External ["External Services"]
        GeminiAPI["Google Gemini 1.5/3.6 Flash API"]
        GoogleOAuth["Google OAuth 2.0 & Calendar API"]
        ResendAPI["Resend REST API / SMTP"]
    end

    SPA --> API
    API --> Sec
    API --> ApptSvc
    API --> LeaveSvc
    API --> AISvc
    API --> NotifSvc
    API --> GCalSvc
    API --> JobMgr

    ApptSvc --> DB
    LeaveSvc --> DB
    NotifSvc --> DB
    JobMgr --> DB

    AISvc --> GeminiAPI
    GCalSvc --> GoogleOAuth
    NotifSvc --> ResendAPI
    JobMgr --> GeminiAPI
    JobMgr --> ResendAPI
    JobMgr --> GoogleOAuth
```

### Core Technologies
- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (0.110+) running on ASGI [Uvicorn](https://www.uvicorn.org/).
- **ORM & Data Layer**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with declarative mapping, connection pooling, and schema migration auto-repair.
- **Database Engine**: [PostgreSQL](https://www.postgresql.org/) (Production/Supabase) / [SQLite](https://www.sqlite.org/) (Development with zero configuration).
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/) and `pydantic-settings`.
- **Frontend Stack**: [React 19](https://react.dev/), [TypeScript 6.0](https://www.typescriptlang.org/), [Vite 8](https://vite.dev/), [Tailwind CSS 4](https://tailwindcss.com/), [Lucide React](https://lucide.dev/).
- **AI Model**: Google Gemini 1.5 Flash / Gemini 3.6 Flash via direct REST API with JSON schema enforcement.
- **Email Delivery**: Resend REST API with fallback to standard SMTP and simulated development mode.
- **Calendar Synchronization**: Google Calendar REST API v3 with OAuth 2.0 offline access.

---

## 🚀 Local Setup & Installation Guide

### Prerequisites
- **Python**: Version `3.10` or higher
- **Node.js**: Version `18.0.0` or higher (`npm` included)
- **Git**: Installed and configured

### Step 1: Clone Repository
```bash
git clone https://github.com/shataghnee05/clinica-ai-healthcare.git
cd clinica-ai-healthcare
```

### Step 2: Configure Environment Variables
Create `.env` in the project root:
```bash
cp .env.example .env
```
Open `.env` and fill in required secrets (see [Environment Variables](#-environment-variables--configuration-envexample)).

### Step 3: Backend Setup
```bash
# Navigate to backend directory
cd backend

# Create and activate a virtual environment
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# macOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run initial database migrations and seed default doctors
python -m app.seed

# Start FastAPI backend server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend API and Swagger docs will be live at:
- **API Base**: `http://127.0.0.1:8000/api/v1`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

### Step 4: Frontend Setup
Open a new terminal:
```bash
# Navigate to frontend directory
cd frontend

# Install node dependencies
npm install

# Start Vite development server
npm run dev
```
The frontend application will be live at `http://localhost:5173/`.

### Pre-Seeded Default Accounts
| Role | Email | Password | Details |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@clinica.health` | `ClinicaAdmin2026!` | Full administrative hospital access |
| **Doctor** | `dr.rajesh.sharma@clinica.health` | `ClinicaDoctor2026!` | Senior Interventional Cardiologist |
| **Doctor** | `dr.priya.patel@clinica.health` | `ClinicaDoctor2026!` | Clinical Dermatologist |
| **Doctor** | `dr.ananya.mukherjee@clinica.health` | `ClinicaDoctor2026!` | Chief Endocrinologist |
| **Doctor** | `dr.vikram.sengupta@clinica.health` | `ClinicaDoctor2026!` | Director of Internal Medicine |
| **Doctor** | `dr.arvind.swaminathan@clinica.health` | `ClinicaDoctor2026!` | Senior Consultant Neurologist |
| **Doctor** | `dr.sunita.rao@clinica.health` | `ClinicaDoctor2026!` | Senior Pediatric Specialist |
| **Patient** | Self-register via UI | Any (min 6 chars) | Instant registration via `/register` |

---

## ⚙️ Environment Variables & Configuration (`.env.example`)

The application reads configuration using `pydantic-settings` from `.env`. Below is the complete specification:

```ini
# ==========================================
# 1. DATABASE CONFIGURATION
# ==========================================
# SQLite for local development (default if omitted):
DATABASE_URL=sqlite:///./healthcare.db
# PostgreSQL / Supabase for production:
# DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres

# Optional Supabase credentials
SUPABASE_URL=https://[YOUR-SUPABASE-PROJECT-REF].supabase.co
SUPABASE_KEY=[YOUR-SUPABASE-ANON-KEY]

# ==========================================
# 2. APPLICATION SECURITY & JWT
# ==========================================
# Required: Strong cryptographic secret for signing JWT tokens
SECRET_KEY=your_super_secret_jwt_key_here_min_32_characters
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# ==========================================
# 3. BOOKING ENGINE SETTINGS
# ==========================================
SLOT_HOLD_DURATION_MINUTES=5
DEFAULT_SLOT_DURATION_MINUTES=30
APPOINTMENT_REMINDER_HOURS_BEFORE=24

# ==========================================
# 4. GOOGLE GEMINI AI CLINICAL INTELLIGENCE
# ==========================================
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# ==========================================
# 5. EMAIL & NOTIFICATION INFRASTRUCTURE
# ==========================================
# Provider options: 'resend', 'smtp', or 'mock' (default: resend)
EMAIL_PROVIDER=resend
RESEND_API_KEY=your_resend_api_key_here
NOTIFICATION_FROM_EMAIL=onboarding@resend.dev
NOTIFICATION_ENABLED=true

# SMTP Configuration (only required when EMAIL_PROVIDER=smtp)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=

# ==========================================
# 6. GOOGLE OAUTH 2.0 & CALENDAR INTEGRATION
# ==========================================
GOOGLE_CLIENT_ID=your_google_oauth_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_oauth_client_secret
GOOGLE_REDIRECT_URI=http://localhost:5173/auth/google/callback
GOOGLE_OAUTH_SCOPES=openid email profile https://www.googleapis.com/auth/calendar.events

# ==========================================
# 7. SEED CREDENTIALS (DEVELOPMENT)
# ==========================================
SEED_ADMIN_EMAIL=admin@clinica.health
SEED_ADMIN_PASSWORD=ClinicaAdmin2026!
SEED_DOCTOR_PASSWORD=ClinicaDoctor2026!
```

---

## 📡 Comprehensive API Reference

All API routes are prefixed with `/api/v1`. Bearer JWT tokens must be included in `Authorization: Bearer <TOKEN>` header.

### 1. Authentication Endpoints
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/auth/register` | Public | Register new patient account. Returns JWT token. |
| `POST` | `/auth/login` | Public | Authenticate user (Patient, Doctor, Admin). Returns JWT. |
| `GET` | `/auth/me` | Authenticated | Retrieve current user profile. |
| `POST` | `/auth/forgot-password` | Public | Generate & email 6-digit OTP verification code. |
| `POST` | `/auth/verify-otp` | Public | Validate OTP validity and expiration (10m). |
| `POST` | `/auth/reset-password` | Public | Reset password using valid OTP. |
| `GET` | `/auth/google/url` | Public | Generate Google OAuth 2.0 authorization URL. |
| `POST` | `/auth/google/callback` | Public | Exchange OAuth authorization code for session JWT. |
| `GET` | `/auth/google/status` | Authenticated | Check Google Calendar connection status. |
| `POST` | `/auth/google/disconnect` | Authenticated | Disconnect Google Calendar integration. |

### 2. Doctor & Schedule Endpoints
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/doctors` | Public | List active doctors with optional `specialization`, `insurance`, and `search`. |
| `GET` | `/doctors/{doctor_id}` | Public | Get doctor profile and working hours. |
| `GET` | `/doctors/{doctor_id}/slots` | Public | List slots for doctor with optional `slot_date` filter. Releases expired holds on retrieval. |
| `PUT` | `/admin/doctors/{doctor_id}/working-hours` | Admin | Update doctor weekly working hours and day-off configuration. |
| `POST` | `/admin/doctors/{doctor_id}/generate-slots` | Admin | Generate slots between `start_date` and `end_date`. |

### 3. Slot Hold & Appointment Endpoints
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/appointments/slots/{slot_id}/hold` | Patient | Acquire exclusive 5-minute hold on a slot. |
| `DELETE` | `/appointments/slots/{slot_id}/hold` | Patient | Manually release an active slot hold. |
| `POST` | `/appointments/confirm` | Patient | Confirm appointment on an active held slot with symptoms description. |
| `GET` | `/appointments/patient/my-appointments` | Patient | List patient's booked appointments with status and doctor details. |
| `GET` | `/appointments/doctor/agenda` | Doctor | List assigned appointments for logged-in physician. |
| `PATCH` | `/appointments/{appointment_id}/cancel` | Authorized | Cancel confirmed appointment. Releases slot and triggers notifications. |
| `POST` | `/appointments/{appointment_id}/reschedule` | Authorized | Concurrency-safe reschedule of confirmed or leave-affected appointment to a new slot. |

### 4. Consultation & AI Endpoints
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/appointments/{appointment_id}/pre-visit-summary` | Authorized | Retrieve AI pre-visit SOAP summary. |
| `POST` | `/appointments/{appointment_id}/generate-pre-visit-summary` | Doctor/Admin | Trigger on-demand AI pre-visit summary generation. |
| `POST` | `/consultations/{appointment_id}/start` | Doctor/Admin | Start clinical consultation session (`IN_PROGRESS`). |
| `POST` | `/consultations/{consultation_id}/complete` | Doctor/Admin | Submit clinical notes, diagnosis, instructions, medications, and enqueue post-visit AI summary. |
| `GET` | `/consultations/appointment/{appointment_id}` | Authorized | Get full consultation details, prescription, pre- and post-visit summaries. |
| `GET` | `/consultations/{consultation_id}/post-visit-summary` | Authorized | Retrieve AI post-visit summary and medication schedule. |

### 5. Doctor Leave Management Endpoints
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/doctor/leaves/preview` | Doctor | Preview appointments conflicting with planned leave dates. |
| `POST` | `/doctor/leaves/apply` | Doctor | Submit doctor leave request for administrative review (`PENDING`). |
| `GET` | `/doctor/leaves/my` | Doctor | List doctor's leave request history with review statuses and feedback. |
| `DELETE` | `/doctor/leaves/{leave_id}` | Doctor | Delete doctor's own leave record. |
| `GET` | `/admin/leaves` | Admin | List all leave applications with optional `doctor_id` and `status_filter`. |
| `POST` | `/admin/leaves/{leave_id}/approve` | Admin | Approve leave: atomically cancels conflicting appointments, releases slots, notifies patients and doctor. |
| `POST` | `/admin/leaves/{leave_id}/reject` | Admin | Reject leave request with administrative reason explanation. |
| `POST` | `/admin/doctors/{doctor_id}/leaves/confirm` | Admin | Directly create and confirm doctor leave in a single administrative step. |

### 6. Notifications, Reminders & Job Management
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/notifications/my` | Authenticated | Retrieve in-app notifications for current user. |
| `PATCH` | `/notifications/{notification_id}/read` | Authenticated | Mark in-app notification as read. |
| `GET` | `/medication-reminders/my` | Patient | List scheduled medication reminders with dose label and status. |
| `GET` | `/admin/jobs` | Admin | Inspect background job queue with optional `job_status` filter. |
| `POST` | `/admin/jobs/process-pending` | Admin | Manually trigger processing of due pending background jobs. |
| `GET` | `/admin/stats` | Admin | Retrieve system summary counts and metrics. |

---

## 🗄️ Database Schema & Entity Relationship (ER) Diagram

```mermaid
erDiagram
    users ||--o| doctor_profiles : "has"
    users ||--o{ appointments : "books as patient"
    users ||--o{ notifications : "receives"
    users ||--o| user_google_accounts : "connects"
    
    doctor_profiles ||--o{ doctor_working_hours : "defines"
    doctor_profiles ||--o{ slots : "offers"
    doctor_profiles ||--o{ appointments : "conducts as doctor"
    doctor_profiles ||--o{ doctor_leaves : "applies for"
    
    slots ||--o| appointments : "assigned to"
    
    appointments ||--o| pre_visit_summaries : "has"
    appointments ||--o| consultations : "has"
    
    consultations ||--o| prescriptions : "includes"
    consultations ||--o| post_visit_summaries : "generates"
    
    prescriptions ||--o{ medications : "contains"
    medications ||--o{ medication_reminders : "schedules"
    
    users {
        string id PK
        string email UK
        string password_hash
        string full_name
        string role
        json accepted_insurance
        datetime created_at
    }

    doctor_profiles {
        string id PK
        string user_id FK, UK
        string specialization
        text bio
        int slot_duration_minutes
        bool is_active
    }

    slots {
        string id PK
        string doctor_id FK
        datetime start_time
        datetime end_time
        string status
        string held_by_patient_id FK
        datetime hold_expires_at
        int version
    }

    appointments {
        string id PK
        string slot_id FK, UK
        string doctor_id FK
        string patient_id FK
        text symptoms
        string status
        datetime booked_at
        text cancellation_reason
        string rescheduled_from_slot_id FK
        string google_event_id
    }

    consultations {
        string id PK
        string appointment_id FK, UK
        string doctor_id FK
        string patient_id FK
        text clinical_notes
        text diagnosis
        text follow_up_instructions
        string status
        datetime started_at
        datetime completed_at
    }

    medications {
        string id PK
        string prescription_id FK
        string name
        string dosage
        string frequency
        string duration
        text instructions
        date start_date
        date end_date
    }

    medication_reminders {
        string id PK
        string medication_id FK
        string patient_id FK
        datetime scheduled_for
        string dose_label
        string status
        string job_id
        datetime sent_at
        text error_message
    }

    doctor_leaves {
        string id PK
        string doctor_id FK
        date start_date
        date end_date
        text reason
        string status
        text rejection_reason
        int affected_appointments_count
    }

    background_jobs {
        string id PK
        string job_type
        string status
        json payload
        json result
        int attempts
        int max_attempts
        datetime scheduled_at
        datetime locked_at
    }
```

---

## 🤖 Google Gemini AI Clinical Intelligence Workflows

Clinica integrates Google Gemini Flash (`gemini-1.5-flash` / `gemini-3.6-flash`) using direct HTTP API calls with strict JSON output formatting.

### 1. Pre-Visit SOAP Triage Assistant

- **Trigger**: Enqueued automatically when an appointment is confirmed (`JobType.PRE_VISIT_SUMMARY`).
- **System Instruction**:
  ```text
  You are an AI Clinical Assistant for Clinica healthcare portal.
  Analyze the patient's symptoms and return a JSON object with:
  'urgency' (string: 'LOW', 'MEDIUM', or 'HIGH'),
  'chief_complaint' (concise string summary), and
  'suggested_questions' (an array of EXACTLY 3 relevant clinical questions for the physician to ask).
  ```
- **Prompt**:
  ```text
  Patient Symptoms:
  {symptoms}
  ```
- **Output JSON Schema & Validation**:
  ```json
  {
    "urgency": "LOW | MEDIUM | HIGH",
    "chief_complaint": "String summary",
    "suggested_questions": ["Question 1", "Question 2", "Question 3"]
  }
  ```
  Validated using Pydantic `PreVisitSummaryResult`. If suggested questions are missing or malformed, validator injects clinical fallback questions.
- **Persistence**: Saved in `pre_visit_summaries` table (`status=GENERATED`, `raw_response`).
- **Failure Handling**: On Gemini API timeout or key failure, job status transitions through retries with exponential backoff. Upon 3 failed attempts, summary record status is set to `FAILED` without crashing booking flows.

### 2. Post-Visit Patient Recovery & Rx Scheduler

- **Trigger**: Enqueued automatically when doctor completes consultation (`JobType.POST_VISIT_SUMMARY`).
- **System Instruction**:
  ```text
  You are an AI Medical Communicator for patients.
  Generate a clear, patient-friendly post-visit summary in plain English.
  Return a JSON object with:
  'visit_explanation' (a 2-3 sentence compassionate, plain English explanation of their diagnosis and assessment),
  'medication_schedule' (an array of objects, each with 'medication_name', 'dosage', 'timing', 'instructions'), and
  'follow_up_steps' (clear next steps for the patient's recovery and warning signs).
  ```
- **Prompt**:
  ```text
  Consultation Record:
  {
    "diagnosis": "...",
    "clinical_notes": "...",
    "follow_up_instructions": "...",
    "medications": [...]
  }
  ```
- **Output JSON Schema**:
  ```json
  {
    "visit_explanation": "2-3 sentence explanation",
    "medication_schedule": [
      {
        "medication_name": "Amlodipine",
        "dosage": "5mg",
        "timing": "Morning after breakfast",
        "instructions": "Take with water"
      }
    ],
    "follow_up_steps": "Actionable recovery steps"
  }
  ```
- **Persistence**: Saved in `post_visit_summaries` table (`status=GENERATED`).

---

## 📅 Google Calendar OAuth 2.0 Synchronization

Clinica supports multi-party calendar synchronization using the Google Calendar REST API v3:

1. **Authorization & Connection**:
   - User initiates Google Calendar connect via `/api/v1/auth/google/url`.
   - Consent screen requests `openid email profile https://www.googleapis.com/auth/calendar.events` scope with offline access.
   - Callback exchanges authorization code for access token & refresh token and persists encrypted record in `user_google_accounts`.
2. **Calendar Event Synchronization**:
   - **Booking Creation (`action: "CREATE"`)**: Enqueues `GOOGLE_CALENDAR_SYNC` background job creating an event with appointment ID, physician details, patient name, and formatted UTC start/end times. Event ID is saved to `appointments.google_event_id`.
   - **Rescheduling (`action: "UPDATE"`)**: Updates event start and end times on Google Calendar.
   - **Cancellation (`action: "DELETE"`)**: Idempotently deletes the event from Google Calendar using `google_event_id`.
3. **Resilience**:
   - Automatic access token refresh using `refresh_token` when expired.
   - Failures in Google Calendar API execution are retried via `BackgroundJob` exponential backoff and **never** roll back database appointment bookings.

---

## 📬 Email & Notification Infrastructure

- **Transactional Providers**: Provider-independent architecture via `app.email_providers.py`:
  - `ResendProvider`: Direct REST API calls to `https://api.resend.com/emails`.
  - `SMTPProvider`: Standard TLS/SSL SMTP client.
  - `MockEmailProvider`: Development logger.
- **Templates (`app.email_templates.py`)**: Responsive HTML and accessible plain-text templates for:
  1. Appointment Confirmation
  2. Appointment Cancellation
  3. Doctor Leave Schedule Notice
  4. 24h Advance Appointment Reminder
  5. Timed Medication Reminder
  6. 6-Digit Password Reset OTP
- **Fault-Tolerance**:
  - In-app `Notification` record is created atomically.
  - Email sending job is queued in `BackgroundJob`.
  - Email transport failures trigger exponential backoff retries (`backoff = min(300, 2^attempts * 5)` seconds) and record error trace without affecting appointment state.

---

## ⚙️ Background Job Worker Architecture

Clinica utilizes a database-backed background job queue in the `background_jobs` table:

```mermaid
stateDiagram-v2
    [*] --> PENDING: Job Enqueued (scheduled_at)
    PENDING --> PROCESSING: Worker Picks Job (scheduled_at <= now)
    PROCESSING --> COMPLETED: Handler Success
    PROCESSING --> PENDING: Handler Failure (attempts < 3, backoff scheduled_at)
    PROCESSING --> FAILED: Handler Failure (attempts >= 3)
    COMPLETED --> [*]
    FAILED --> [*]
```

### Job Types & Handlers
- `PRE_VISIT_SUMMARY`: Calls Gemini AI for symptom triage.
- `POST_VISIT_SUMMARY`: Calls Gemini AI for post-visit explanation and Rx schedule.
- `NOTIFY_APPOINTMENT_CONFIRMATION`: Dispatches confirmation emails.
- `NOTIFY_APPOINTMENT_CANCELLATION`: Dispatches cancellation emails.
- `NOTIFY_APPOINTMENT_REMINDER`: Dispatches 24h appointment reminder to patient and doctor.
- `NOTIFY_DOCTOR_LEAVE`: Dispatches leave notifications to affected patients and doctor.
- `MEDICATION_REMINDER`: Dispatches timed dose notification for prescribed medication.
- `GOOGLE_CALENDAR_SYNC`: Creates, updates, or deletes Google Calendar events.

---

## 🔒 Authentication & Role-Based Access Control (RBAC)

1. **Authentication**:
   - Passwords hashed using `bcrypt` (work factor 12).
   - Session tokens signed with HMAC-SHA256 (`pyjwt`) containing `sub: user_id`, `role: user_role`, and `exp`.
2. **Role Enforcement**:
   - `require_patient`: Restricts hold creation, appointment booking, viewing personal appointments, and medication reminders.
   - `require_doctor`: Restricts agenda access, starting/completing consultations, submitting leave applications, and updating working hours.
   - `require_admin`: Restricts doctor creation, physician status toggling, leave approval/rejection, registered patient removal, and background job queue control.

---

## 🧪 Testing & Quality Assurance

The codebase includes an automated test suite verifying all core capabilities, race condition handling, and role permissions:

```bash
# Activate virtual environment
cd backend
pytest -v
```

### Test Suites Overview
- **`tests/test_app.py`**:
  - Authentication, registration, and RBAC permission barriers.
  - Slot hold expiration and release mechanics.
  - **20-Thread Concurrent Hold Race Condition Test**: Confirms exactly 1 patient acquires slot hold under concurrent attempts.
  - Appointment confirmation, consultation completion, and AI pre-visit summary flow.
  - Admin doctor creation, status updates, working hours, and stats.
- **`tests/test_phase2a.py`**:
  - AI clinical pre-visit summary error handling and fallback questions.
  - Consultation workflow with diagnosis, clinical notes, and post-visit summaries.
  - Prescription and medication item persistence.
- **`tests/test_phase2b.py`**:
  - Doctor leave preview and conflict identification.
  - Doctor leave application (`PENDING`), admin approval (`APPROVED`), and rejection (`REJECTED`).
  - Automatic cancellation and slot release of conflicting appointments during approved leaves.
  - Rescheduling of leave-disrupted appointments.
  - Reschedule conflict prevention (cannot book occupied slot).
  - Scheduled medication reminders generation and background job retry backoff.
  - In-app notification mark-as-read state.
  - Non-blocking external notification resilience.

---

## 🌐 Deployment Guide

### Frontend Deployment (Vercel)
1. Link repository to Vercel.
2. Root directory: `frontend`.
3. Build Command: `npm run build`.
4. Output Directory: `dist`.
5. Rewrite rules are pre-configured in `frontend/vercel.json`.

### Backend Deployment (Render / Railway / AWS / VPS)
1. Set Root Directory: `backend`.
2. Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Set environment variables from `.env.example` in provider dashboard.
4. Database: Connect managed PostgreSQL instance (e.g. Supabase, Render PostgreSQL).

---

## ⚠️ Known Limitations & Design Trade-offs

1. **Background Worker Deployment**:
   - In single-instance setups, jobs are processed using FastAPI `BackgroundTasks` and `/api/v1/admin/jobs/process-pending`. In high-volume multi-instance production environments, a dedicated Redis/Celery worker process is recommended.
2. **AI Provider Fallback**:
   - Google Gemini API is the primary AI provider with mock fallback for automated testing environments. Multi-model failover (e.g. Gemini to Claude/OpenAI) can be added to the provider strategy.
3. **Slot Duration Granularity**:
   - Slot generation generates contiguous fixed-length slots within daily working hours. Variable-length appointment booking on arbitrary start times is constrained to slot boundaries by design to prevent calendar fragmentation.

---

## 📝 Submission Checklist & System Design Write-Up

### Deliverables Checklist
- [x] **Complete Source-Code Repository / ZIP**: Full backend and frontend code with seed data and test suite.
- [x] **README.md**: Comprehensive documentation with setup guide, `.env.example`, API reference, database schema, LLM prompts, and Google Calendar setup.
- [x] **Hosted Application URL**: [https://clinica-ai-healthcare-dc52.vercel.app](https://clinica-ai-healthcare-dc52.vercel.app)
- [x] **800-Word System Design Write-Up**: Embedded below.

---

### 🏛️ System Design Write-Up: Concurrency, Conflict Resolution, and Fault Tolerance

#### 1. Double-Booking Prevention & Optimistic Concurrency Control (OCC)
In modern healthcare scheduling, the greatest concurrency hazard is the "booking race," where multiple patients simultaneously select the same high-demand appointment slot. Standard pessimistic locking (`SELECT ... FOR UPDATE`) causes thread contention, database connection exhaustion, and latency spikes. Clinica solves this using a high-throughput **Optimistic Concurrency Control (OCC) and Slot-Hold state machine**:

Each slot in the `slots` table maintains an integer `version` counter and a state column (`AVAILABLE`, `HELD`, `BOOKED`, `CANCELLED`). When a patient selects a slot, the system executes an atomic CAS update:
```sql
UPDATE slots
SET status = 'HELD', held_by_patient_id = :patient_id,
    hold_expires_at = :expires_at, version = version + 1
WHERE id = :slot_id
  AND (status = 'AVAILABLE' OR (status = 'HELD' AND hold_expires_at < :now));
```
Because the database engine guarantees atomicity on row updates, exactly one patient receives `rows_updated == 1`, while all competing requests receive `rows_updated == 0` and are immediately returned a clean `409 Conflict ("Slot is no longer available or is currently held")`.

When the holding patient confirms their booking with symptoms, a second atomic CAS update transitions the slot from `HELD` to `BOOKED`:
```sql
UPDATE slots
SET status = 'BOOKED', hold_expires_at = NULL, version = version + 1
WHERE id = :slot_id
  AND status = 'HELD'
  AND held_by_patient_id = :patient_id
  AND hold_expires_at >= :now;
```
If the patient abandons the booking or allows the 5-minute timer to expire, no manual unlock job is required: subsequent slot queries evaluate `hold_expires_at < now` and automatically treat the slot as available for re-holding.

#### 2. Doctor Leave Conflict Resolution & Appointment Rescheduling
Physician leave management requires careful balance between doctor flexibility and patient schedule preservation. Clinica implements a **three-stage leave workflow**:

1. **Non-Destructive Impact Preview**: When a doctor requests leave, the system executes a read-only conflict query across `appointments` joining `slots` between `start_date` and `end_date`. The doctor views exactly which patient appointments will be affected without modifying any database records.
2. **Administrative Approval Flow**: The doctor submits a formal leave application (`PENDING`). During this state, patient bookings remain confirmed. Upon hospital administrator review, approval triggers an atomic transaction:
   - The leave status transitions to `APPROVED`.
   - Conflicting `CONFIRMED` appointments have their status updated to `CANCELLED` with the explicit reason `"Doctor on approved leave (YYYY-MM-DD – YYYY-MM-DD)"`.
   - Conflicting slot rows are atomically reset to `AVAILABLE` with `held_by_patient_id = NULL`.
   - Any pending 24h appointment reminder background jobs for the cancelled appointments are immediately cancelled.
   - Individualized `NOTIFY_DOCTOR_LEAVE` notification jobs are enqueued for every affected patient.
3. **Reschedule Engine**: Patients or clinic staff can reschedule cancelled appointments. The `reschedule_appointment` endpoint atomically reserves a new slot on behalf of the patient, releases the previous slot, creates updated confirmation notifications, and schedules a new 24h reminder for the revised appointment time.

#### 3. Fault-Tolerant Notification & External API Architecture
A critical architectural principle in Clinica is **strict transaction isolation between core healthcare state and external third-party services** (Resend email, Google Gemini AI, and Google Calendar API):

1. **Non-Blocking Asynchronous Job Queuing**: External network calls are never executed synchronously inside the database transaction that confirms an appointment or completes a consultation. Database commits complete in milliseconds, guaranteeing high availability and sub-50ms API response times.
2. **Background Job Queue with Exponential Backoff**: When transactional emails or calendar syncs are dispatched, a `BackgroundJob` record is inserted with `status = 'PENDING'`, `attempts = 0`, and `scheduled_at`. If the Resend API or Google Calendar API encounters network timeouts or rate limits:
   - The error is logged to `background_jobs.error_message`.
   - The job attempt counter increments.
   - The job is rescheduled with exponential backoff (`backoff_seconds = min(300, 2^attempts * 5)`).
   - If maximum attempts (3) are exhausted, the job status transitions to `FAILED`.
   - **Crucially, the appointment's `CONFIRMED` state in the database remains intact and is never rolled back.**
3. **In-App Notification Decoupling**: In-app notifications (`Notification` model) are written to the database in the primary transaction. Even in catastrophic external email gateway outages, users retain full visibility of all appointment confirmations, leave notices, and medication reminders directly within their portal notification center.
