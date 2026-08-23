export type UserRole = "PATIENT" | "DOCTOR" | "ADMIN";

export type SlotStatus = "AVAILABLE" | "HELD" | "BOOKED" | "CANCELLED";

export type AppointmentStatus = "CONFIRMED" | "COMPLETED" | "CANCELLED";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  accepted_insurance: string[];
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface WorkingHour {
  day_of_week: number;
  start_time: string;
  end_time: string;
  is_day_off: boolean;
}

export interface Doctor {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  specialization: string;
  bio: string;
  slot_duration_minutes: number;
  is_active: boolean;
  accepted_insurance: string[];
  working_hours?: WorkingHour[];
}

export interface Slot {
  id: string;
  doctor_id: string;
  start_time: string;
  end_time: string;
  status: SlotStatus;
  held_by_patient_id?: string | null;
  hold_expires_at?: string | null;
}

export interface Appointment {
  id: string;
  slot_id: string;
  doctor_id: string;
  patient_id: string;
  symptoms: string;
  status: AppointmentStatus;
  booked_at: string;
  doctor_name?: string;
  doctor_specialization?: string;
  patient_name?: string;
  patient_email?: string;
  start_time?: string;
  end_time?: string;
  cancellation_reason?: string | null;
  rescheduled_from_slot_id?: string | null;
}

export interface SystemStats {
  total_patients: number;
  total_doctors: number;
  total_slots: number;
  total_appointments: number;
  total_holds_active: number;
  server_time: string;
}

export interface PatientAdmin {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  accepted_insurance: string[];
  created_at: string;
  total_appointments: number;
}

export type UrgencyLevel = "LOW" | "MEDIUM" | "HIGH";
export type AISummaryStatus = "PENDING" | "GENERATED" | "FAILED";
export type ConsultationStatus = "IN_PROGRESS" | "COMPLETED";

export interface PreVisitSummary {
  id: string;
  appointment_id: string;
  urgency: UrgencyLevel;
  chief_complaint: string;
  suggested_questions: string[];
  status: AISummaryStatus;
  created_at: string;
}

export interface Medication {
  id?: string;
  name: string;
  dosage: string;
  frequency: string;
  duration: string;
  instructions?: string;
}

export interface Prescription {
  id?: string;
  notes?: string;
  created_at?: string;
  medications: Medication[];
}

export interface MedicationScheduleItem {
  medication_name: string;
  dosage: string;
  timing: string;
  instructions?: string;
}

export interface PostVisitSummary {
  id: string;
  consultation_id: string;
  visit_explanation: string;
  medication_schedule: MedicationScheduleItem[];
  follow_up_steps: string;
  status: AISummaryStatus;
  created_at: string;
}

export interface Consultation {
  id: string;
  appointment_id: string;
  doctor_id: string;
  patient_id: string;
  diagnosis: string;
  clinical_notes?: string | null;
  follow_up_instructions: string;
  status: ConsultationStatus;
  started_at: string;
  completed_at?: string | null;
  doctor_name?: string;
  doctor_specialization?: string;
  patient_name?: string;
  patient_email?: string;
  prescription?: Prescription | null;
  post_visit_summary?: PostVisitSummary | null;
  pre_visit_summary?: PreVisitSummary | null;
}

// ── Phase 2B Types ──────────────────────────────────────────────────────────

export type NotificationType =
  | "APPOINTMENT_CONFIRMATION"
  | "APPOINTMENT_CANCELLATION"
  | "APPOINTMENT_REMINDER"
  | "DOCTOR_LEAVE"
  | "DOCTOR_LEAVE_APPROVAL"
  | "DOCTOR_LEAVE_REJECTION"
  | "MEDICATION_REMINDER";

export type LeaveStatus = "PENDING" | "APPROVED" | "REJECTED";

export type MedicationReminderStatus = "PENDING" | "SENT" | "FAILED";

export interface AffectedAppointment {
  appointment_id: string;
  patient_name: string;
  patient_email: string;
  start_time?: string;
  end_time?: string;
  symptoms: string;
  status: string;
}

export interface LeavePreview {
  doctor_id: string;
  doctor_name: string;
  start_date: string;
  end_date: string;
  affected_appointments: AffectedAppointment[];
  affected_count: number;
}

export interface DoctorLeave {
  id: string;
  doctor_id: string;
  doctor_name?: string;
  doctor_email?: string;
  doctor_specialization?: string;
  start_date: string;
  end_date: string;
  reason?: string;
  status: LeaveStatus;
  rejection_reason?: string | null;
  created_by_admin_id?: string | null;
  reviewed_by_admin_id?: string | null;
  confirmed_at?: string | null;
  reviewed_at?: string | null;
  affected_appointments_count: number;
  created_at?: string;
}

export interface Notification {
  id: string;
  user_id: string;
  notification_type: NotificationType;
  title: string;
  body: string;
  is_read: boolean;
  reference_id?: string | null;
  email_sent: boolean;
  email_error?: string | null;
  created_at: string;
}

export interface MedicationReminder {
  id: string;
  medication_id: string;
  patient_id: string;
  scheduled_for: string;
  dose_label: string;
  status: MedicationReminderStatus;
  sent_at?: string | null;
  error_message?: string | null;
  created_at: string;
}
