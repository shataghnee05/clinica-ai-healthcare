import type {
  AuthResponse,
  User,
  Doctor,
  Slot,
  Appointment,
  SystemStats,
  WorkingHour,
  DoctorLeave,
  LeavePreview,
  Notification,
  MedicationReminder,
} from "./types";

const envBase = import.meta.env.VITE_API_BASE_URL;
const API_BASE = envBase ? `${envBase.replace(/\/$/, "")}/api/v1` : "/api/v1";

export function getToken(): string | null {
  return localStorage.getItem("token");
}

export function setToken(token: string) {
  localStorage.setItem("token", token);
}

export function clearToken() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

export function getStoredUser(): User | null {
  const user = localStorage.getItem("user");
  return user ? JSON.parse(user) : null;
}

export function setStoredUser(user: User) {
  localStorage.setItem("user", JSON.stringify(user));
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = "An unexpected error occurred";
    try {
      const errorData = await response.json();
      errorDetail = errorData.detail || errorDetail;
    } catch {
      errorDetail = response.statusText;
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  auth: {
    register: (data: {
      email: string;
      password: string;
      full_name: string;
      accepted_insurance?: string[];
    }) => request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),

    login: (data: { email: string; password: string }) =>
      request<AuthResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    getMe: () => request<User>("/auth/me"),
  },

  doctors: {
    list: (params?: { specialization?: string; insurance?: string; search?: string }) => {
      const query = new URLSearchParams();
      if (params?.specialization) query.set("specialization", params.specialization);
      if (params?.insurance) query.set("insurance", params.insurance);
      if (params?.search) query.set("search", params.search);
      const qs = query.toString();
      return request<Doctor[]>(`/doctors${qs ? `?${qs}` : ""}`);
    },

    get: (id: string) => request<Doctor>(`/doctors/${id}`),

    getSlots: (doctorId: string, dateStr?: string) => {
      const query = dateStr ? `?slot_date=${dateStr}` : "";
      return request<Slot[]>(`/doctors/${doctorId}/slots${query}`);
    },
  },

  appointments: {
    holdSlot: (slotId: string) =>
      request<{ slot_id: string; status: string; hold_expires_at: string; message: string }>(
        `/appointments/slots/${slotId}/hold`,
        { method: "POST" }
      ),

    releaseHold: (slotId: string) =>
      request<{ status: string; message: string }>(`/appointments/slots/${slotId}/hold`, {
        method: "DELETE",
      }),

    confirm: (data: { slot_id: string; symptoms: string }) =>
      request<Appointment>("/appointments/confirm", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    getMyAppointments: () => request<Appointment[]>("/appointments/patient/my-appointments"),

    getDoctorAgenda: () => request<Appointment[]>("/appointments/doctor/agenda"),

    cancel: (appointmentId: string, reason?: string) =>
      request<{ status: string; message: string }>(`/appointments/${appointmentId}/cancel`, {
        method: "PATCH",
        body: JSON.stringify({ reason: reason || "" }),
      }),

    reschedule: (appointmentId: string, newSlotId: string, reason?: string) =>
      request<Appointment>(`/appointments/${appointmentId}/reschedule`, {
        method: "POST",
        body: JSON.stringify({ new_slot_id: newSlotId, reason: reason || "" }),
      }),
  },

  admin: {
    listDoctors: () => request<Doctor[]>("/admin/doctors"),

    createDoctor: (data: {
      email: string;
      password: string;
      full_name: string;
      specialization: string;
      bio?: string;
      slot_duration_minutes?: number;
      accepted_insurance?: string[];
    }) =>
      request<Doctor>("/admin/doctors", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    updateDoctor: (doctorId: string, data: {
      full_name?: string;
      specialization?: string;
      bio?: string;
      slot_duration_minutes?: number;
      accepted_insurance?: string[];
    }) =>
      request<Doctor>(`/admin/doctors/${doctorId}`, {
        method: "PUT",
        body: JSON.stringify(data),
      }),

    setDoctorStatus: (doctorId: string, isActive: boolean) =>
      request<Doctor>(`/admin/doctors/${doctorId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: isActive }),
      }),

    updateWorkingHours: (doctorId: string, hours: WorkingHour[]) =>
      request<{ status: string; message: string }>(`/admin/doctors/${doctorId}/working-hours`, {
        method: "PUT",
        body: JSON.stringify({ hours }),
      }),

    generateSlots: (doctorId: string, startDate: string, endDate: string) =>
      request<{ status: string; slots_created: number }>(
        `/admin/doctors/${doctorId}/generate-slots`,
        {
          method: "POST",
          body: JSON.stringify({ start_date: startDate, end_date: endDate }),
        }
      ),

    deleteDoctor: (doctorId: string) =>
      request<{ status: string; message: string }>(`/admin/doctors/${doctorId}`, {
        method: "DELETE",
      }),

    listPatients: () => request<import("./types").PatientAdmin[]>("/admin/patients"),

    deletePatient: (patientId: string) =>
      request<{ status: string; message: string }>(`/admin/patients/${patientId}`, {
        method: "DELETE",
      }),

    getStats: () => request<SystemStats>("/admin/stats"),

    // Phase 2B Admin Leave APIs
    previewLeave: (doctorId: string, startDate: string, endDate: string, reason?: string) =>
      request<LeavePreview>(`/admin/doctors/${doctorId}/leaves/preview`, {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate, reason: reason || "" }),
      }),

    confirmLeave: (doctorId: string, startDate: string, endDate: string, reason?: string) =>
      request<DoctorLeave>(`/admin/doctors/${doctorId}/leaves/confirm`, {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate, reason: reason || "" }),
      }),

    listLeaves: (doctorId: string) =>
      request<DoctorLeave[]>(`/admin/doctors/${doctorId}/leaves`),

    listAllLeaves: (statusFilter?: string, doctorId?: string) => {
      const params = new URLSearchParams();
      if (statusFilter) params.append("status_filter", statusFilter);
      if (doctorId) params.append("doctor_id", doctorId);
      const q = params.toString() ? `?${params.toString()}` : "";
      return request<DoctorLeave[]>(`/admin/leaves${q}`);
    },

    approveLeave: (leaveId: string) =>
      request<DoctorLeave>(`/admin/leaves/${leaveId}/approve`, {
        method: "POST",
      }),

    rejectLeave: (leaveId: string, reason: string) =>
      request<DoctorLeave>(`/admin/leaves/${leaveId}/reject`, {
        method: "POST",
        body: JSON.stringify({ reason }),
      }),

    deleteLeave: (leaveId: string) =>
      request<{ status: string; message: string }>(`/admin/leaves/${leaveId}`, {
        method: "DELETE",
      }),

    listJobs: (limit = 50, jobStatus?: string) => {
      const query = jobStatus ? `?job_status=${jobStatus}&limit=${limit}` : `?limit=${limit}`;
      return request<any[]>(`/admin/jobs${query}`);
    },
  },

  consultations: {
    getPreVisitSummary: (appointmentId: string) =>
      request<import("./types").PreVisitSummary>(`/appointments/${appointmentId}/pre-visit-summary`),

    generatePreVisitSummary: (appointmentId: string) =>
      request<import("./types").PreVisitSummary>(`/appointments/${appointmentId}/generate-pre-visit-summary`, {
        method: "POST",
        body: JSON.stringify({ provider: "gemini" }),
      }),

    start: (appointmentId: string) =>
      request<{ id: string; appointment_id: string; status: string; started_at: string }>(
        `/consultations/${appointmentId}/start`,
        { method: "POST" }
      ),

    complete: (
      consultationId: string,
      data: {
        diagnosis: string;
        clinical_notes: string;
        follow_up_instructions: string;
        prescription_notes?: string;
        medications: import("./types").Medication[];
      }
    ) =>
      request<{ id: string; status: string; completed_at: string; message: string }>(
        `/consultations/${consultationId}/complete`,
        {
          method: "POST",
          body: JSON.stringify(data),
        }
      ),

    getByAppointment: (appointmentId: string) =>
      request<import("./types").Consultation>(`/consultations/appointment/${appointmentId}`),

    getPostVisitSummary: (consultationId: string) =>
      request<import("./types").PostVisitSummary>(`/consultations/${consultationId}/post-visit-summary`),
  },

  // Phase 2B Notifications & Reminders APIs
  notifications: {
    getMy: () => request<Notification[]>("/notifications/my"),
    markRead: (id: string) => request<Notification>(`/notifications/${id}/read`, { method: "PATCH" }),
  },

  medicationReminders: {
    getMy: () => request<MedicationReminder[]>("/medication-reminders/my"),
  },

  doctorLeaves: {
    preview: (startDate: string, endDate: string, reason?: string) =>
      request<LeavePreview>("/doctor/leaves/preview", {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate, reason: reason || "" }),
      }),

    apply: (startDate: string, endDate: string, reason?: string) =>
      request<DoctorLeave>("/doctor/leaves/apply", {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate, reason: reason || "" }),
      }),

    confirm: (startDate: string, endDate: string, reason?: string) =>
      request<DoctorLeave>("/doctor/leaves/confirm", {
        method: "POST",
        body: JSON.stringify({ start_date: startDate, end_date: endDate, reason: reason || "" }),
      }),

    getMy: () => request<DoctorLeave[]>("/doctor/leaves/my"),

    delete: (leaveId: string) =>
      request<{ status: string; message: string }>(`/doctor/leaves/${leaveId}`, {
        method: "DELETE",
      }),
  },
};
