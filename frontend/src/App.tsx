import React, { useState, useEffect } from "react";
import type {
  User,
  Doctor,
  Slot,
  Appointment,
  SystemStats,
  PatientAdmin,
  PreVisitSummary,
  Consultation,
  Medication,
  DoctorLeave,
  LeavePreview,
  Notification,
  MedicationReminder,
  GoogleCalendarStatus,
} from "./types";
import { api, setToken, clearToken, getStoredUser, setStoredUser, getToken } from "./api";
import {
  Calendar,
  Clock,
  User as UserIcon,
  Search,
  CheckCircle2,
  AlertCircle,
  X,
  Stethoscope,
  ChevronRight,
  LogOut,
  RefreshCw,
  FileText,
  Sun,
  Moon,
  Trash2,
  Sparkles,
  Plus,
  Pill,
  ShieldCheck,
  Bell,
  CalendarX,
  ArrowRightLeft,
  Check,
  AlertTriangle,
  Lock,
  Mail,
  ArrowRight,
  HeartPulse,
  UserPlus,
  XCircle,
} from "lucide-react";

export default function App() {
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = localStorage.getItem("theme");
    return saved === "dark" || saved === "light" ? saved : "light";
  });

  const [currentUser, setCurrentUser] = useState<User | null>(getStoredUser());
  
  // Auth Portal States (for unauthenticated entrance)
  const [selectedPortalRole, setSelectedPortalRole] = useState<"PATIENT" | "DOCTOR" | "ADMIN">("PATIENT");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authFullName, setAuthFullName] = useState("");
  const [authInsurance, setAuthInsurance] = useState("Aetna, BlueCross");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  // Active Tabs for authenticated roles
  // Patient: 'find-doctors' | 'my-appointments' | 'medications'
  // Doctor: 'doctor-agenda' | 'doctor-leaves'
  // Admin: 'admin-stats' | 'admin-doctors' | 'admin-leaves' | 'admin-patients' | 'admin-jobs'
  const [patientTab, setPatientTab] = useState<"find-doctors" | "my-appointments" | "medications">("find-doctors");
  const [doctorTab, setDoctorTab] = useState<"doctor-agenda" | "doctor-leaves">("doctor-agenda");
  const [adminTab, setAdminTab] = useState<"admin-stats" | "admin-doctors" | "admin-leaves" | "admin-patients" | "admin-jobs">("admin-stats");

  // Google Calendar Integration State
  const [googleCalendarStatus, setGoogleCalendarStatus] = useState<GoogleCalendarStatus | null>(null);
  const [googleConnecting, setGoogleConnecting] = useState(false);

  // Patient Booking States
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedSpecialization, setSelectedSpecialization] = useState<string>("");
  const [doctorsLoading, setDoctorsLoading] = useState(false);

  const [selectedDoctor, setSelectedDoctor] = useState<Doctor | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split("T")[0];
  });
  const [slots, setSlots] = useState<Slot[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);

  const [heldSlot, setHeldSlot] = useState<Slot | null>(null);
  const [holdRemainingSeconds, setHoldRemainingSeconds] = useState<number>(300);
  const [symptomsInput, setSymptomsInput] = useState("");
  const [bookingLoading, setBookingLoading] = useState(false);
  const [bookingSuccess, setBookingSuccess] = useState<Appointment | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  const [patientAppointments, setPatientAppointments] = useState<Appointment[]>([]);
  const [patientAppointmentsLoading, setPatientAppointmentsLoading] = useState(false);

  // Doctor Agenda States
  const [doctorAgenda, setDoctorAgenda] = useState<Appointment[]>([]);
  const [doctorAgendaLoading, setDoctorAgendaLoading] = useState(false);

  // Doctor Leave States (Self-Service)
  const [docLeaveStartDate, setDocLeaveStartDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 2);
    return d.toISOString().split("T")[0];
  });
  const [docLeaveEndDate, setDocLeaveEndDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 5);
    return d.toISOString().split("T")[0];
  });
  const [docLeaveReason, setDocLeaveReason] = useState("Medical conference / Personal leave");
  const [docLeavePreview, setDocLeavePreview] = useState<LeavePreview | null>(null);
  const [docLeavePreviewLoading, setDocLeavePreviewLoading] = useState(false);
  const [docLeaveConfirmLoading, setDocLeaveConfirmLoading] = useState(false);
  const [docLeavesList, setDocLeavesList] = useState<DoctorLeave[]>([]);
  const [docLeavesLoading, setDocLeavesLoading] = useState(false);

  // Admin States
  const [adminStats, setAdminStats] = useState<SystemStats | null>(null);
  const [adminDoctorsList, setAdminDoctorsList] = useState<Doctor[]>([]);

  const [adminPatientsList, setAdminPatientsList] = useState<PatientAdmin[]>([]);
  const [adminPatientsLoading, setAdminPatientsLoading] = useState(false);

  // Admin Leave Oversight States
  const [adminLeaveDoctorId, setAdminLeaveDoctorId] = useState("");
  const [adminLeaveStatusFilter, setAdminLeaveStatusFilter] = useState<string>("ALL");
  const [adminDoctorLeavesList, setAdminDoctorLeavesList] = useState<DoctorLeave[]>([]);
  const [adminDoctorLeavesLoading, setAdminDoctorLeavesLoading] = useState(false);
  const [adminRejectingLeave, setAdminRejectingLeave] = useState<DoctorLeave | null>(null);
  const [adminRejectReasonInput, setAdminRejectReasonInput] = useState("");
  const [adminRejectSubmitting, setAdminRejectSubmitting] = useState(false);
  const [adminApproveSubmitting, setAdminApproveSubmitting] = useState<string | null>(null);

  // Admin Doctor Registration Modal States
  const [adminRegisterDoctorModalOpen, setAdminRegisterDoctorModalOpen] = useState(false);
  const [adminNewDocName, setAdminNewDocName] = useState("");
  const [adminNewDocEmail, setAdminNewDocEmail] = useState("");
  const [adminNewDocPassword, setAdminNewDocPassword] = useState("");
  const [adminNewDocSpecialization, setAdminNewDocSpecialization] = useState("Cardiology");
  const [adminNewDocBio, setAdminNewDocBio] = useState("");
  const [adminNewDocSlotDuration, setAdminNewDocSlotDuration] = useState<number>(30);
  const [adminNewDocInsurance, setAdminNewDocInsurance] = useState("Aetna, BlueCross, Cigna, UnitedHealthcare");
  const [adminNewDocAutoSlots, setAdminNewDocAutoSlots] = useState(true);
  const [adminNewDocSubmitting, setAdminNewDocSubmitting] = useState(false);

  // Admin Job Monitor
  const [adminJobsList, setAdminJobsList] = useState<any[]>([]);
  const [adminJobsLoading, setAdminJobsLoading] = useState(false);

  // Phase 2A: Consultation & AI States
  const [consultationModalAppt, setConsultationModalAppt] = useState<Appointment | null>(null);
  const [activeConsultation, setActiveConsultation] = useState<Consultation | null>(null);
  const [activePreVisitSummary, setActivePreVisitSummary] = useState<PreVisitSummary | null>(null);
  const [consultationDiagnosis, setConsultationDiagnosis] = useState("");
  const [consultationClinicalNotes, setConsultationClinicalNotes] = useState("");
  const [consultationFollowUp, setConsultationFollowUp] = useState("");
  const [consultationRxNotes, setConsultationRxNotes] = useState("");
  const [consultationMedications, setConsultationMedications] = useState<Medication[]>([
    { name: "", dosage: "", frequency: "", duration: "", instructions: "" }
  ]);
  const [consultationSubmitting, setConsultationSubmitting] = useState(false);
  const [isGeneratingAiSummary, setIsGeneratingAiSummary] = useState(false);

  // Notifications & Reminders
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [showNotifModal, setShowNotifModal] = useState(false);
  const [medicationReminders, setMedicationReminders] = useState<MedicationReminder[]>([]);
  const [remindersLoading, setRemindersLoading] = useState(false);

  // Cancellation Modal
  const [cancellingAppt, setCancellingAppt] = useState<Appointment | null>(null);
  const [cancelReasonInput, setCancelReasonInput] = useState("");
  const [cancelLoading, setCancelLoading] = useState(false);

  // Reschedule Modal
  const [reschedulingAppt, setReschedulingAppt] = useState<Appointment | null>(null);
  const [rescheduleDate, setRescheduleDate] = useState<string>(() => {
    const d = new Date();
    d.setDate(d.getDate() + 2);
    return d.toISOString().split("T")[0];
  });
  const [rescheduleSlots, setRescheduleSlots] = useState<Slot[]>([]);
  const [rescheduleSlotsLoading, setRescheduleSlotsLoading] = useState(false);
  const [rescheduleHeldSlot, setRescheduleHeldSlot] = useState<Slot | null>(null);
  const [rescheduleHoldRemaining, setRescheduleHoldRemaining] = useState<number>(300);
  const [rescheduleReason, setRescheduleReason] = useState("");
  const [rescheduleLoading, setRescheduleLoading] = useState(false);

  // Theme effect
  useEffect(() => {
    localStorage.setItem("theme", theme);
    if (theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  // Check stored user on load
  useEffect(() => {
    if (getToken()) {
      api.auth.getMe()
        .then((user) => {
          setCurrentUser(user);
          setStoredUser(user);
        })
        .catch(() => {
          clearToken();
          setCurrentUser(null);
        });
    }
  }, []);

  // Doctor list loading (for Patient search & Admin)
  useEffect(() => {
    loadDoctors();
  }, [selectedSpecialization]);

  // Load slots when doctor and date change
  useEffect(() => {
    if (selectedDoctor) {
      loadSlots(selectedDoctor.id, selectedDate);
    }
  }, [selectedDoctor, selectedDate]);

  // Role-based data loading
  useEffect(() => {
    if (!currentUser) return;

    if (currentUser.role === "PATIENT") {
      if (patientTab === "my-appointments") loadPatientAppointments();
      if (patientTab === "medications") loadMedicationReminders();
    } else if (currentUser.role === "DOCTOR") {
      if (doctorTab === "doctor-agenda") loadDoctorAgenda();
      if (doctorTab === "doctor-leaves") loadMyDoctorLeaves();
    } else if (currentUser.role === "ADMIN") {
      if (adminTab === "admin-stats") loadAdminStats();
      if (adminTab === "admin-doctors") loadAdminDoctors();
      if (adminTab === "admin-patients") loadAdminPatients();
      if (adminTab === "admin-jobs") loadAdminJobs();
      if (adminTab === "admin-leaves") {
        loadAdminAllLeaves(adminLeaveStatusFilter, adminLeaveDoctorId);
      }
    }
  }, [currentUser, patientTab, doctorTab, adminTab, adminLeaveDoctorId, adminLeaveStatusFilter]);

  // Notifications poll & Google Calendar status
  useEffect(() => {
    if (currentUser) {
      loadNotifications();
      loadGoogleCalendarStatus();
      const interval = setInterval(loadNotifications, 15000);
      return () => clearInterval(interval);
    }
  }, [currentUser]);

  // Handle Google OAuth callback on mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get("code");
    const state = urlParams.get("state");
    if (code) {
      window.history.replaceState({}, document.title, window.location.pathname);
      setAuthLoading(true);
      api.auth
        .googleCallback(code, state || "login", selectedPortalRole)
        .then((res) => {
          setToken(res.access_token);
          setCurrentUser(res.user);
          setStoredUser(res.user);
          if (res.user.role === "PATIENT") setPatientTab("find-doctors");
          if (res.user.role === "DOCTOR") setDoctorTab("doctor-agenda");
          if (res.user.role === "ADMIN") setAdminTab("admin-stats");
          api.auth.getGoogleCalendarStatus().then(setGoogleCalendarStatus).catch(() => {});
        })
        .catch((err: any) => {
          setAuthError(err.message || "Google authentication failed");
        })
        .finally(() => {
          setAuthLoading(false);
        });
    }
  }, []);

  // 5-minute atomic slot hold countdown timer
  useEffect(() => {
    if (!heldSlot) return;
    const timer = setInterval(() => {
      setHoldRemainingSeconds((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setHeldSlot(null);
          setErrorMessage("Your slot hold expired. Please choose another slot.");
          if (selectedDoctor) loadSlots(selectedDoctor.id, selectedDate);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [heldSlot, selectedDoctor, selectedDate]);

  // Reschedule hold timer
  useEffect(() => {
    if (!rescheduleHeldSlot) return;
    const timer = setInterval(() => {
      setRescheduleHoldRemaining((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          setRescheduleHeldSlot(null);
          setErrorMessage("Reschedule slot hold expired. Please select a slot again.");
          if (reschedulingAppt) loadRescheduleSlots(reschedulingAppt.doctor_id, rescheduleDate);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [rescheduleHeldSlot, reschedulingAppt, rescheduleDate]);

  // Fetch functions
  const loadDoctors = async () => {
    setDoctorsLoading(true);
    try {
      const data = await api.doctors.list({
        specialization: selectedSpecialization || undefined,
        search: searchQuery || undefined,
      });
      setDoctors(data);
      if (data.length > 0 && !adminLeaveDoctorId) {
        setAdminLeaveDoctorId(data[0].id);
      }
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setDoctorsLoading(false);
    }
  };

  const loadAdminDoctors = async () => {
    try {
      const data = await api.admin.listDoctors();
      setAdminDoctorsList(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const loadSlots = async (doctorId: string, dateStr: string) => {
    setSlotsLoading(true);
    try {
      const data = await api.doctors.getSlots(doctorId, dateStr);
      setSlots(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setSlotsLoading(false);
    }
  };

  const loadPatientAppointments = async () => {
    setPatientAppointmentsLoading(true);
    try {
      const data = await api.appointments.getMyAppointments();
      setPatientAppointments(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setPatientAppointmentsLoading(false);
    }
  };

  const loadDoctorAgenda = async () => {
    setDoctorAgendaLoading(true);
    try {
      const data = await api.appointments.getDoctorAgenda();
      setDoctorAgenda(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setDoctorAgendaLoading(false);
    }
  };

  const loadMyDoctorLeaves = async () => {
    setDocLeavesLoading(true);
    try {
      const leaves = await api.doctorLeaves.getMy();
      setDocLeavesList(leaves);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setDocLeavesLoading(false);
    }
  };

  const loadAdminAllLeaves = async (statusFilter?: string, docId?: string) => {
    if (currentUser?.role !== "ADMIN") return;
    setAdminDoctorLeavesLoading(true);
    try {
      const leaves = await api.admin.listAllLeaves(
        statusFilter === "ALL" ? undefined : statusFilter,
        docId || undefined
      );
      setAdminDoctorLeavesList(leaves);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setAdminDoctorLeavesLoading(false);
    }
  };

  const loadAdminStats = async () => {
    try {
      const data = await api.admin.getStats();
      setAdminStats(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const loadAdminPatients = async () => {
    setAdminPatientsLoading(true);
    try {
      const data = await api.admin.listPatients();
      setAdminPatientsList(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setAdminPatientsLoading(false);
    }
  };

  const loadAdminJobs = async () => {
    setAdminJobsLoading(true);
    try {
      const jobs = await api.admin.listJobs(25);
      setAdminJobsList(jobs);
    } catch {
      // Background poll silently fails
    } finally {
      setAdminJobsLoading(false);
    }
  };

  const loadNotifications = async () => {
    if (!getToken()) return;
    try {
      const notifs = await api.notifications.getMy();
      setNotifications(notifs);
    } catch {
      // Ignore background errors
    }
  };

  const loadMedicationReminders = async () => {
    setRemindersLoading(true);
    try {
      const data = await api.medicationReminders.getMy();
      setMedicationReminders(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setRemindersLoading(false);
    }
  };

  const loadGoogleCalendarStatus = async () => {
    if (!getToken()) return;
    try {
      const s = await api.auth.getGoogleCalendarStatus();
      setGoogleCalendarStatus(s);
    } catch {
      // Ignore
    }
  };

  const handleGoogleAuth = async (flowState: string = "login") => {
    try {
      setGoogleConnecting(true);
      setAuthError("");
      const res = await api.auth.getGoogleAuthUrl(flowState);
      window.location.href = res.auth_url;
    } catch (err: any) {
      setAuthError(err.message || "Failed to initiate Google OAuth");
      setErrorMessage(err.message || "Failed to initiate Google OAuth");
      setGoogleConnecting(false);
    }
  };

  const handleDisconnectGoogleCalendar = async () => {
    try {
      await api.auth.disconnectGoogleCalendar();
      setGoogleCalendarStatus({ connected: false });
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to disconnect Google Calendar");
    }
  };

  // Auth Handler
  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError("");
    setAuthLoading(true);

    try {
      if (authMode === "login") {
        const res = await api.auth.login({ email: authEmail.trim(), password: authPassword });
        setToken(res.access_token);
        setCurrentUser(res.user);
        setStoredUser(res.user);
        setAuthPassword("");
        if (res.user.role === "PATIENT") setPatientTab("find-doctors");
        if (res.user.role === "DOCTOR") setDoctorTab("doctor-agenda");
        if (res.user.role === "ADMIN") setAdminTab("admin-stats");
      } else {
        const insuranceList = authInsurance.split(",").map((s) => s.trim()).filter(Boolean);
        const res = await api.auth.register({
          email: authEmail.trim(),
          password: authPassword,
          full_name: authFullName.trim(),
          accepted_insurance: insuranceList,
        });
        setToken(res.access_token);
        setCurrentUser(res.user);
        setStoredUser(res.user);
        setAuthPassword("");
        setPatientTab("find-doctors");
      }
    } catch (err: any) {
      setAuthError(err.message || "Authentication failed");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    clearToken();
    setCurrentUser(null);
    setSelectedDoctor(null);
    setHeldSlot(null);
    setBookingSuccess(null);
    setErrorMessage("");
    setAuthPassword("");
  };

  // Slot Hold & Booking Handlers
  const handleHoldSlot = async (slot: Slot) => {
    if (!currentUser) return;
    if (currentUser.role !== "PATIENT") {
      setErrorMessage("Only patients can hold and book consultation slots.");
      return;
    }

    setErrorMessage("");
    try {
      await api.appointments.holdSlot(slot.id);
      setHeldSlot(slot);
      setHoldRemainingSeconds(300);
      if (selectedDoctor) loadSlots(selectedDoctor.id, selectedDate);
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleConfirmBooking = async () => {
    if (!heldSlot) return;
    setBookingLoading(true);
    setErrorMessage("");

    try {
      const appt = await api.appointments.confirm({
        slot_id: heldSlot.id,
        symptoms: symptomsInput,
      });
      setBookingSuccess(appt);
      setHeldSlot(null);
      setSymptomsInput("");
      if (selectedDoctor) loadSlots(selectedDoctor.id, selectedDate);
      loadPatientAppointments();
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setBookingLoading(false);
    }
  };

  // Doctor Leave Self-Service Handlers
  const handleDoctorPreviewLeave = async (e: React.FormEvent) => {
    e.preventDefault();
    setDocLeavePreviewLoading(true);
    setErrorMessage("");
    setDocLeavePreview(null);
    try {
      const preview = await api.doctorLeaves.preview(docLeaveStartDate, docLeaveEndDate, docLeaveReason);
      setDocLeavePreview(preview);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setDocLeavePreviewLoading(false);
    }
  };

  const handleDoctorApplyLeave = async () => {
    if (!docLeavePreview) return;
    setDocLeaveConfirmLoading(true);
    setErrorMessage("");
    try {
      await api.doctorLeaves.apply(docLeaveStartDate, docLeaveEndDate, docLeaveReason);
      setDocLeavePreview(null);
      loadMyDoctorLeaves();
      alert("Leave application submitted successfully! Your request is pending administrator approval.");
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setDocLeaveConfirmLoading(false);
    }
  };

  const handleDoctorDeleteLeave = async (leaveId: string) => {
    if (!confirm("Are you sure you want to cancel this leave application?")) return;
    try {
      await api.doctorLeaves.delete(leaveId);
      loadMyDoctorLeaves();
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  // Admin Leave Oversight Handlers
  const handleAdminApproveLeave = async (leave: DoctorLeave) => {
    if (!confirm(`Approve leave for ${leave.doctor_name || "Doctor"} from ${leave.start_date} to ${leave.end_date}? Any conflicting patient appointments (${leave.affected_appointments_count}) will be cancelled and patients notified.`)) {
      return;
    }
    setAdminApproveSubmitting(leave.id);
    try {
      await api.admin.approveLeave(leave.id);
      loadAdminAllLeaves(adminLeaveStatusFilter, adminLeaveDoctorId);
      alert("Doctor leave approved successfully! Conflicting appointments were cancelled and notifications dispatched.");
    } catch (err: any) {
      alert("Error approving leave: " + err.message);
    } finally {
      setAdminApproveSubmitting(null);
    }
  };

  const handleAdminOpenReject = (leave: DoctorLeave) => {
    setAdminRejectingLeave(leave);
    setAdminRejectReasonInput("Administrative scheduling requirements / hospital staffing coverage shortage.");
  };

  const handleAdminConfirmReject = async () => {
    if (!adminRejectingLeave) return;
    if (!adminRejectReasonInput.trim()) {
      alert("Please provide a reason for the rejection.");
      return;
    }
    setAdminRejectSubmitting(true);
    try {
      await api.admin.rejectLeave(adminRejectingLeave.id, adminRejectReasonInput.trim());
      setAdminRejectingLeave(null);
      setAdminRejectReasonInput("");
      loadAdminAllLeaves(adminLeaveStatusFilter, adminLeaveDoctorId);
      alert("Leave request rejected. Explanation was sent to the doctor.");
    } catch (err: any) {
      alert("Error rejecting leave: " + err.message);
    } finally {
      setAdminRejectSubmitting(false);
    }
  };

  // Admin Doctor Registration Handler
  const handleAdminRegisterDoctor = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdminNewDocSubmitting(true);
    try {
      const insuranceList = adminNewDocInsurance
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const newDoc = await api.admin.createDoctor({
        full_name: adminNewDocName.trim(),
        email: adminNewDocEmail.trim(),
        password: adminNewDocPassword,
        specialization: adminNewDocSpecialization.trim(),
        bio: adminNewDocBio.trim(),
        slot_duration_minutes: Number(adminNewDocSlotDuration),
        accepted_insurance: insuranceList.length > 0 ? insuranceList : ["Aetna", "BlueCross", "Cigna"],
      });

      if (adminNewDocAutoSlots) {
        const today = new Date();
        const startStr = today.toISOString().split("T")[0];
        const futureDate = new Date();
        futureDate.setDate(today.getDate() + 14);
        const endStr = futureDate.toISOString().split("T")[0];
        await api.admin.generateSlots(newDoc.id, startStr, endStr);
      }

      setAdminRegisterDoctorModalOpen(false);
      setAdminNewDocName("");
      setAdminNewDocEmail("");
      setAdminNewDocPassword("");
      setAdminNewDocSpecialization("Cardiology");
      setAdminNewDocBio("");
      loadAdminDoctors();
      loadDoctors();
      alert(`Dr. ${newDoc.full_name} has been successfully registered!`);
    } catch (err: any) {
      alert("Failed to register doctor: " + err.message);
    } finally {
      setAdminNewDocSubmitting(false);
    }
  };

  const handleOpenRescheduleModal = (appt: Appointment) => {
    setReschedulingAppt(appt);
    setRescheduleHeldSlot(null);
    setRescheduleReason("");
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const dStr = tomorrow.toISOString().split("T")[0];
    setRescheduleDate(dStr);
    loadRescheduleSlots(appt.doctor_id, dStr);
  };

  // Doctor Consultation & SOAP Notes Handlers
  const handleOpenConsultation = async (appt: Appointment) => {
    setConsultationModalAppt(appt);
    setErrorMessage("");

    try {
      try {
        const summary = await api.consultations.getPreVisitSummary(appt.id);
        setActivePreVisitSummary(summary);
      } catch {
        setActivePreVisitSummary(null);
      }

      try {
        const cons = await api.consultations.getByAppointment(appt.id);
        setActiveConsultation(cons);
        setConsultationDiagnosis(cons.diagnosis || "");
        setConsultationClinicalNotes(cons.clinical_notes || "");
        setConsultationFollowUp(cons.follow_up_instructions || "");
        if (cons.prescription?.medications?.length) {
          setConsultationMedications(cons.prescription.medications);
        } else {
          setConsultationMedications([{ name: "", dosage: "", frequency: "", duration: "", instructions: "" }]);
        }
        setConsultationRxNotes(cons.prescription?.notes || "");
      } catch {
        const startRes = await api.consultations.start(appt.id);
        setActiveConsultation({
          id: startRes.id,
          appointment_id: appt.id,
          doctor_id: appt.doctor_id,
          patient_id: appt.patient_id,
          clinical_notes: "",
          diagnosis: "",
          follow_up_instructions: "",
          status: "IN_PROGRESS",
          started_at: startRes.started_at,
        });
        setConsultationDiagnosis("");
        setConsultationClinicalNotes("");
        setConsultationFollowUp("");
        setConsultationMedications([{ name: "", dosage: "", frequency: "", duration: "", instructions: "" }]);
        setConsultationRxNotes("");
      }
    } catch (err: any) {
      setErrorMessage(`Could not load consultation: ${err.message}`);
    }
  };

  const handleGenerateAiPreVisitSummary = async () => {
    if (!consultationModalAppt) return;
    setIsGeneratingAiSummary(true);
    try {
      const result = await api.consultations.generatePreVisitSummary(consultationModalAppt.id);
      setActivePreVisitSummary(result);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to generate AI SOAP summary with Gemini");
    } finally {
      setIsGeneratingAiSummary(false);
    }
  };

  const handleCompleteConsultation = async () => {
    if (!activeConsultation) return;
    if (!consultationDiagnosis.trim()) {
      setErrorMessage("Diagnosis is required to complete the consultation.");
      return;
    }

    setConsultationSubmitting(true);
    setErrorMessage("");

    try {
      const validMeds = consultationMedications.filter((m) => m.name.trim() !== "");
      await api.consultations.complete(activeConsultation.id, {
        diagnosis: consultationDiagnosis.trim(),
        clinical_notes: consultationClinicalNotes.trim(),
        follow_up_instructions: consultationFollowUp.trim(),
        prescription_notes: consultationRxNotes.trim(),
        medications: validMeds,
      });

      setConsultationModalAppt(null);
      setActiveConsultation(null);
      loadDoctorAgenda();
      alert("Consultation finalized successfully. Post-visit summary and reminders dispatched!");
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setConsultationSubmitting(false);
    }
  };

  // Appointment Cancellation & Rescheduling Handlers
  const handleConfirmCancel = async () => {
    if (!cancellingAppt) return;
    setCancelLoading(true);
    setErrorMessage("");
    try {
      await api.appointments.cancel(cancellingAppt.id, cancelReasonInput.trim());
      setCancellingAppt(null);
      setCancelReasonInput("");
      loadPatientAppointments();
      if (currentUser?.role === "DOCTOR") loadDoctorAgenda();
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setCancelLoading(false);
    }
  };

  const loadRescheduleSlots = async (doctorId: string, dateStr: string) => {
    setRescheduleSlotsLoading(true);
    try {
      const data = await api.doctors.getSlots(doctorId, dateStr);
      setRescheduleSlots(data);
    } catch (err: any) {
      setErrorMessage(err.message);
    } finally {
      setRescheduleSlotsLoading(false);
    }
  };

  const handleHoldRescheduleSlot = async (slot: Slot) => {
    setErrorMessage("");
    try {
      await api.appointments.holdSlot(slot.id);
      setRescheduleHeldSlot(slot);
      setRescheduleHoldRemaining(300);
      if (reschedulingAppt) loadRescheduleSlots(reschedulingAppt.doctor_id, rescheduleDate);
    } catch (err: any) {
      setErrorMessage(err.message);
    }
  };

  const handleConfirmReschedule = async () => {
    if (!reschedulingAppt || !rescheduleHeldSlot) return;
    setRescheduleLoading(true);
    setErrorMessage("");
    try {
      await api.appointments.reschedule(
        reschedulingAppt.id,
        rescheduleHeldSlot.id,
        rescheduleReason.trim() || undefined
      );
      setReschedulingAppt(null);
      setRescheduleHeldSlot(null);
      setRescheduleReason("");
      loadPatientAppointments();
      if (currentUser?.role === "DOCTOR") {
        loadDoctorAgenda();
        loadMyDoctorLeaves();
      }
      alert("Appointment rescheduled successfully! The patient has been notified.");
    } catch (err: any) {
      setErrorMessage(err.message);
      alert("Rescheduling failed: " + err.message);
    } finally {
      setRescheduleLoading(false);
    }
  };

  const handleMarkNotifRead = async (id: string) => {
    try {
      await api.notifications.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
    } catch {
      // Ignore
    }
  };

  // Helper formatting functions
  const formatTime = (isoString?: string) => {
    if (!isoString) return "";
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  const formatDate = (isoString?: string) => {
    if (!isoString) return "";
    const date = new Date(isoString);
    return date.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  const unreadNotifsCount = notifications.filter((n) => !n.is_read).length;

  // =========================================================================
  // VIEW 1: UNAUTHENTICATED ROLE-BASED LOGIN / REGISTER PORTAL
  // =========================================================================
  if (!currentUser) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col justify-between transition-colors duration-200">
        {/* Top Minimal Header */}
        <header className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur sticky top-0 z-10 px-6 py-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-md shadow-teal-600/20">
                <HeartPulse className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">Clinica</span>
                <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-teal-100 dark:bg-teal-950 text-teal-800 dark:text-teal-300">
                  Healthcare Platform
                </span>
              </div>
            </div>

            <button
              onClick={toggleTheme}
              className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition"
              title="Toggle Theme"
            >
              {theme === "light" ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5 text-amber-400" />}
            </button>
          </div>
        </header>

        {/* Main Portal Selection & Login Container */}
        <main className="flex-1 flex items-center justify-center p-6 my-6">
          <div className="w-full max-w-xl">
            {/* Role Tab Selector */}
            <div className="bg-slate-200/80 dark:bg-slate-900 p-1.5 rounded-2xl flex space-x-1.5 mb-6 shadow-inner border border-slate-200 dark:border-slate-800">
              <button
                type="button"
                onClick={() => {
                  setSelectedPortalRole("PATIENT");
                  setAuthError("");
                }}
                className={`flex-1 flex items-center justify-center space-x-2 py-3 rounded-xl font-semibold text-sm transition-all duration-200 ${
                  selectedPortalRole === "PATIENT"
                    ? "bg-white dark:bg-slate-800 text-teal-600 dark:text-teal-400 shadow-md"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                <UserIcon className="w-4 h-4" />
                <span>Patient Portal</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setSelectedPortalRole("DOCTOR");
                  setAuthMode("login");
                  setAuthError("");
                }}
                className={`flex-1 flex items-center justify-center space-x-2 py-3 rounded-xl font-semibold text-sm transition-all duration-200 ${
                  selectedPortalRole === "DOCTOR"
                    ? "bg-white dark:bg-slate-800 text-blue-600 dark:text-blue-400 shadow-md"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                <Stethoscope className="w-4 h-4" />
                <span>Doctor Portal</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setSelectedPortalRole("ADMIN");
                  setAuthMode("login");
                  setAuthError("");
                }}
                className={`flex-1 flex items-center justify-center space-x-2 py-3 rounded-xl font-semibold text-sm transition-all duration-200 ${
                  selectedPortalRole === "ADMIN"
                    ? "bg-white dark:bg-slate-800 text-indigo-600 dark:text-indigo-400 shadow-md"
                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                }`}
              >
                <ShieldCheck className="w-4 h-4" />
                <span>Hospital Admin</span>
              </button>
            </div>

            {/* Main Login Card */}
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-8 shadow-xl">
              {/* Role Header Banner */}
              <div className="text-center mb-8">
                {selectedPortalRole === "PATIENT" && (
                  <>
                    <div className="inline-flex p-3 rounded-2xl bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400 mb-3">
                      <UserIcon className="w-7 h-7" />
                    </div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                      {authMode === "login" ? "Patient Sign In" : "Register as Patient"}
                    </h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                      {authMode === "login"
                        ? "Sign in to book doctor appointments, track prescriptions & view medical summaries."
                        : "Create a new patient profile with your insurance coverage."}
                    </p>
                  </>
                )}

                {selectedPortalRole === "DOCTOR" && (
                  <>
                    <div className="inline-flex p-3 rounded-2xl bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 mb-3">
                      <Stethoscope className="w-7 h-7" />
                    </div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Doctor Clinical Portal</h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                      Access your patient agenda, record SOAP clinical notes, and manage leave schedules.
                    </p>
                  </>
                )}

                {selectedPortalRole === "ADMIN" && (
                  <>
                    <div className="inline-flex p-3 rounded-2xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 mb-3">
                      <ShieldCheck className="w-7 h-7" />
                    </div>
                    <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Hospital Administration</h2>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                      Manage clinical rosters, inspect system statistics, and oversee leave requests.
                    </p>
                  </>
                )}
              </div>

              {/* Error Message Alert */}
              {authError && (
                <div className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/60 border border-rose-200 dark:border-rose-800/60 text-rose-700 dark:text-rose-300 text-sm flex items-start space-x-3">
                  <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
                  <span>{authError}</span>
                </div>
              )}

              {/* Login / Register Form */}
              <form onSubmit={handleAuthSubmit} className="space-y-4">
                {selectedPortalRole === "PATIENT" && authMode === "register" && (
                  <>
                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1.5">
                        Full Name
                      </label>
                      <input
                        type="text"
                        required
                        value={authFullName}
                        onChange={(e) => setAuthFullName(e.target.value)}
                        placeholder="Jane Doe"
                        className="w-full px-4 py-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500 transition"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1.5">
                        Accepted Insurance (comma separated)
                      </label>
                      <input
                        type="text"
                        value={authInsurance}
                        onChange={(e) => setAuthInsurance(e.target.value)}
                        placeholder="Aetna, BlueCross, Cigna"
                        className="w-full px-4 py-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500 transition"
                      />
                    </div>
                  </>
                )}

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1.5">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
                    <input
                      type="email"
                      required
                      value={authEmail}
                      onChange={(e) => setAuthEmail(e.target.value)}
                      placeholder={
                        selectedPortalRole === "PATIENT"
                          ? "patient@example.com"
                          : selectedPortalRole === "DOCTOR"
                          ? "doctor@clinica.health"
                          : "admin@clinica.health"
                      }
                      className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500 transition"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1.5">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
                    <input
                      type="password"
                      required
                      value={authPassword}
                      onChange={(e) => setAuthPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-teal-500 transition"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={authLoading}
                  className="w-full py-3.5 rounded-xl bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white font-semibold shadow-lg shadow-teal-600/25 transition duration-200 flex items-center justify-center space-x-2 mt-6 disabled:opacity-50"
                >
                  {authLoading ? (
                    <RefreshCw className="w-5 h-5 animate-spin" />
                  ) : (
                    <>
                      <span>{authMode === "login" ? `Sign In to Portal` : "Create Patient Account"}</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>

                {/* Google OAuth Button */}
                <div className="relative my-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-200 dark:border-slate-800" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-white dark:bg-slate-900 px-3 text-slate-400 font-medium">Or continue with</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleGoogleAuth("login")}
                  disabled={authLoading || googleConnecting}
                  className="w-full py-3 px-4 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700/70 text-slate-700 dark:text-slate-200 font-semibold text-sm shadow-sm transition duration-150 flex items-center justify-center space-x-3 disabled:opacity-50"
                >
                  {googleConnecting ? (
                    <RefreshCw className="w-4 h-4 animate-spin text-teal-600" />
                  ) : (
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path
                        fill="#4285F4"
                        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
                      />
                      <path
                        fill="#34A853"
                        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.33 24 12 24z"
                      />
                      <path
                        fill="#FBBC05"
                        d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.98 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
                      />
                      <path
                        fill="#EA4335"
                        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.33 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
                      />
                    </svg>
                  )}
                  <span>Sign in with Google</span>
                </button>
              </form>

              {/* Patient Toggle: Sign in vs Register */}
              {selectedPortalRole === "PATIENT" && (
                <div className="text-center mt-6 pt-6 border-t border-slate-200 dark:border-slate-800">
                  {authMode === "login" ? (
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      New to Clinica?{" "}
                      <button
                        type="button"
                        onClick={() => {
                          setAuthMode("register");
                          setAuthError("");
                        }}
                        className="text-teal-600 dark:text-teal-400 font-semibold hover:underline"
                      >
                        Register a new patient account
                      </button>
                    </p>
                  ) : (
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Already have an account?{" "}
                      <button
                        type="button"
                        onClick={() => {
                          setAuthMode("login");
                          setAuthError("");
                        }}
                        className="text-teal-600 dark:text-teal-400 font-semibold hover:underline"
                      >
                        Sign In here
                      </button>
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>
        </main>

        <footer className="text-center py-6 text-xs text-slate-500 dark:text-slate-500 border-t border-slate-200 dark:border-slate-800">
          Clinica Healthcare Platform • Concurrency-safe slot holds, AI clinical SOAP notes, and doctor leave manager
        </footer>
      </div>
    );
  }

  // =========================================================================
  // VIEW 2: AUTHENTICATED APP SHELL (PATIENT / DOCTOR / ADMIN)
  // =========================================================================
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col transition-colors duration-200">
      {/* Top Navbar */}
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 backdrop-blur sticky top-0 z-30 px-6 py-3.5 shadow-sm">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-6">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 rounded-xl bg-teal-600 flex items-center justify-center text-white shadow-md shadow-teal-600/20">
                <HeartPulse className="w-6 h-6" />
              </div>
              <div>
                <span className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">Clinica</span>
                <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                  {currentUser.role}
                </span>
              </div>
            </div>

            {/* Navigation Tabs based on Role */}
            <nav className="hidden md:flex items-center space-x-1 pl-4 border-l border-slate-200 dark:border-slate-800">
              {currentUser.role === "PATIENT" && (
                <>
                  <button
                    onClick={() => setPatientTab("find-doctors")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition ${
                      patientTab === "find-doctors"
                        ? "bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    Find Doctors
                  </button>
                  <button
                    onClick={() => setPatientTab("my-appointments")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition flex items-center space-x-1.5 ${
                      patientTab === "my-appointments"
                        ? "bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <span>My Appointments</span>
                    {patientAppointments.length > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full text-xs bg-teal-600 text-white font-bold">
                        {patientAppointments.length}
                      </span>
                    )}
                  </button>
                  <button
                    onClick={() => setPatientTab("medications")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition flex items-center space-x-1.5 ${
                      patientTab === "medications"
                        ? "bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <Pill className="w-4 h-4" />
                    <span>My Medications</span>
                  </button>
                </>
              )}

              {currentUser.role === "DOCTOR" && (
                <>
                  <button
                    onClick={() => setDoctorTab("doctor-agenda")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition flex items-center space-x-1.5 ${
                      doctorTab === "doctor-agenda"
                        ? "bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <Calendar className="w-4 h-4" />
                    <span>Doctor Agenda</span>
                  </button>
                  <button
                    onClick={() => setDoctorTab("doctor-leaves")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition flex items-center space-x-1.5 ${
                      doctorTab === "doctor-leaves"
                        ? "bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    <CalendarX className="w-4 h-4" />
                    <span>Apply Leaves</span>
                  </button>
                </>
              )}

              {currentUser.role === "ADMIN" && (
                <>
                  <button
                    onClick={() => setAdminTab("admin-stats")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition ${
                      adminTab === "admin-stats"
                        ? "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    Executive Stats
                  </button>
                  <button
                    onClick={() => setAdminTab("admin-doctors")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition ${
                      adminTab === "admin-doctors"
                        ? "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    Doctor Rosters
                  </button>
                  <button
                    onClick={() => setAdminTab("admin-leaves")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition ${
                      adminTab === "admin-leaves"
                        ? "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    Leave Overseer
                  </button>
                  <button
                    onClick={() => setAdminTab("admin-patients")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition ${
                      adminTab === "admin-patients"
                        ? "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    Patients Directory
                  </button>
                  <button
                    onClick={() => setAdminTab("admin-jobs")}
                    className={`px-3.5 py-2 rounded-xl text-sm font-semibold transition ${
                      adminTab === "admin-jobs"
                        ? "bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400"
                        : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                    }`}
                  >
                    Job Monitor
                  </button>
                </>
              )}
            </nav>
          </div>

          {/* Right Header Actions */}
          <div className="flex items-center space-x-3">
            {/* Notification Bell */}
            <button
              onClick={() => setShowNotifModal(true)}
              className="relative p-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition"
              title="Notifications"
            >
              <Bell className="w-5 h-5" />
              {unreadNotifsCount > 0 && (
                <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-rose-500 text-white text-xs font-bold flex items-center justify-center animate-pulse">
                  {unreadNotifsCount}
                </span>
              )}
            </button>

            {/* Theme Toggle */}
            {/* Google Calendar Connect / Status Badge */}
            {currentUser && currentUser.role !== "ADMIN" && (
              googleCalendarStatus?.connected ? (
                <div className="flex items-center space-x-2 px-3 py-1.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/60 text-xs text-emerald-800 dark:text-emerald-300">
                  <Calendar className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                  <span className="hidden md:inline font-medium">Calendar Connected</span>
                  <button
                    onClick={handleDisconnectGoogleCalendar}
                    className="text-[10px] text-emerald-700 dark:text-emerald-400 underline hover:text-rose-600 transition ml-1"
                    title="Disconnect Google Calendar"
                  >
                    Disconnect
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => handleGoogleAuth("connect_calendar")}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-xs font-semibold text-slate-700 dark:text-slate-300 transition"
                  title="Connect your Google Calendar to sync confirmed appointments automatically"
                >
                  <Calendar className="w-4 h-4 text-teal-600" />
                  <span className="hidden sm:inline">Connect Google Calendar</span>
                </button>
              )
            )}

            <button
              onClick={toggleTheme}
              className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition"
              title="Toggle Theme"
            >
              {theme === "light" ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5 text-amber-400" />}
            </button>

            {/* User Profile Badge */}
            <div className="hidden sm:flex items-center space-x-2.5 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700/60 text-xs">
              <div className="w-6 h-6 rounded-lg bg-teal-600 text-white flex items-center justify-center font-bold">
                {currentUser.full_name.charAt(0).toUpperCase()}
              </div>
              <div className="text-left">
                <div className="font-semibold text-slate-900 dark:text-white leading-tight">
                  {currentUser.full_name}
                </div>
                <div className="text-slate-500 dark:text-slate-400 text-[10px] leading-tight">
                  {currentUser.email}
                </div>
              </div>
            </div>

            {/* Logout Button */}
            <button
              onClick={handleLogout}
              className="flex items-center space-x-1.5 px-3.5 py-2 rounded-xl border border-rose-200 dark:border-rose-900/40 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-sm font-semibold transition"
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </div>
      </header>

      {/* Global Error Banner */}
      {errorMessage && (
        <div className="bg-rose-500 text-white px-6 py-3 text-sm font-medium flex items-center justify-between shadow-md">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-5 h-5" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage("")} className="hover:opacity-80">
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Dynamic Content Per Role */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 space-y-6">

        {/* =================================================================== */}
        {/* ROLE A: PATIENT VIEW                                                */}
        {/* =================================================================== */}
        {currentUser.role === "PATIENT" && (
          <>
            {/* SUB-VIEW 1: FIND DOCTORS */}
            {patientTab === "find-doctors" && (
              <div className="space-y-6">
                {/* Search & Filter Bar */}
                <div className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col md:flex-row gap-4 items-center">
                  <div className="relative flex-1 w-full">
                    <Search className="w-5 h-5 text-slate-400 absolute left-3.5 top-3.5" />
                    <input
                      type="text"
                      placeholder="Search doctor by name or specialty..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && loadDoctors()}
                      className="w-full pl-11 pr-4 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                    />
                  </div>

                  <select
                    value={selectedSpecialization}
                    onChange={(e) => setSelectedSpecialization(e.target.value)}
                    className="w-full md:w-60 px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                  >
                    <option value="">All Specializations</option>
                    <option value="Endocrinology">Endocrinology</option>
                    <option value="Cardiology">Cardiology</option>
                    <option value="Dermatology">Dermatology</option>
                    <option value="Diagnostics">Diagnostics</option>
                  </select>

                  <button
                    onClick={loadDoctors}
                    className="w-full md:w-auto px-5 py-3 rounded-xl bg-teal-600 hover:bg-teal-700 text-white font-semibold text-sm transition shadow-md shadow-teal-600/20"
                  >
                    Search
                  </button>
                </div>

                {/* Booking Success Alert */}
                {bookingSuccess && (
                  <div className="bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 rounded-2xl p-6 shadow-sm">
                    <div className="flex items-start space-x-3">
                      <CheckCircle2 className="w-6 h-6 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <h3 className="text-lg font-bold text-emerald-900 dark:text-emerald-200">
                          Appointment Confirmed!
                        </h3>
                        <p className="text-sm text-emerald-700 dark:text-emerald-300 mt-1">
                          Your appointment with {bookingSuccess.doctor_name} has been successfully scheduled.
                        </p>
                        <div className="mt-3 flex space-x-3">
                          <button
                            onClick={() => setPatientTab("my-appointments")}
                            className="px-4 py-2 rounded-xl bg-emerald-600 text-white text-xs font-semibold hover:bg-emerald-700 transition"
                          >
                            View in My Appointments
                          </button>
                          <button
                            onClick={() => setBookingSuccess(null)}
                            className="px-4 py-2 rounded-xl border border-emerald-300 dark:border-emerald-700 text-emerald-800 dark:text-emerald-300 text-xs font-semibold hover:bg-emerald-100 dark:hover:bg-emerald-900/40 transition"
                          >
                            Book Another
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Doctor Selection & Slot Booking Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Doctor List */}
                  <div className="lg:col-span-5 space-y-4">
                    <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Available Doctors ({doctors.length})
                    </h2>

                    {doctorsLoading ? (
                      <div className="p-8 text-center text-slate-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading doctors...</div>
                    ) : doctors.length === 0 ? (
                      <div className="p-8 text-center bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 text-slate-500">
                        No doctors match your criteria.
                      </div>
                    ) : (
                      doctors.map((doc) => {
                        const isSelected = selectedDoctor?.id === doc.id;
                        return (
                          <div
                            key={doc.id}
                            onClick={() => {
                              setSelectedDoctor(doc);
                              setHeldSlot(null);
                            }}
                            className={`p-5 rounded-2xl border transition cursor-pointer ${
                              isSelected
                                ? "bg-teal-50/70 dark:bg-teal-950/40 border-teal-500 shadow-md"
                                : "bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800 hover:border-slate-300 dark:hover:border-slate-700"
                            }`}
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <h3 className="font-bold text-base text-slate-900 dark:text-white flex items-center space-x-2">
                                  <span>{doc.full_name}</span>
                                  <span className="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-teal-100 dark:bg-teal-900 text-teal-800 dark:text-teal-200">
                                    {doc.specialization}
                                  </span>
                                </h3>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 line-clamp-2">
                                  {doc.bio}
                                </p>
                              </div>
                              <ChevronRight className={`w-5 h-5 ${isSelected ? "text-teal-600" : "text-slate-400"}`} />
                            </div>

                            {doc.accepted_insurance && doc.accepted_insurance.length > 0 && (
                              <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex flex-wrap gap-1 items-center">
                                <span className="text-[10px] uppercase font-semibold text-slate-400 mr-1">Insurance:</span>
                                {doc.accepted_insurance.map((ins) => (
                                  <span key={ins} className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[10px] text-slate-600 dark:text-slate-400">
                                    {ins}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })
                    )}
                  </div>

                  {/* Slot Booking Panel */}
                  <div className="lg:col-span-7">
                    {selectedDoctor ? (
                      <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-6">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
                          <div>
                            <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                              Book with {selectedDoctor.full_name}
                            </h3>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {selectedDoctor.specialization} • {selectedDoctor.slot_duration_minutes}-minute consultation
                            </p>
                          </div>

                          <input
                            type="date"
                            value={selectedDate}
                            onChange={(e) => setSelectedDate(e.target.value)}
                            min={new Date().toISOString().split("T")[0]}
                            className="px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-teal-500"
                          />
                        </div>

                        {/* Available Slots */}
                        <div>
                          <div className="flex items-center justify-between mb-3">
                            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                              Available Time Slots ({slots.filter((s) => s.status === "AVAILABLE").length})
                            </h4>
                            <button
                              onClick={() => loadSlots(selectedDoctor.id, selectedDate)}
                              className="text-xs text-teal-600 dark:text-teal-400 hover:underline flex items-center space-x-1"
                            >
                              <RefreshCw className="w-3.5 h-3.5" />
                              <span>Refresh Slots</span>
                            </button>
                          </div>

                          {slotsLoading ? (
                            <div className="p-8 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" /> Loading open slots...</div>
                          ) : slots.length === 0 ? (
                            <div className="p-8 text-center bg-slate-50 dark:bg-slate-800/50 rounded-xl text-slate-500 text-sm">
                              No slots generated for {selectedDate}. Please select another date.
                            </div>
                          ) : (
                            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2.5">
                              {slots.map((slot) => {
                                const isHeldByMe = heldSlot?.id === slot.id;
                                const isAvailable = slot.status === "AVAILABLE";
                                return (
                                  <button
                                    key={slot.id}
                                    disabled={!isAvailable && !isHeldByMe}
                                    onClick={() => handleHoldSlot(slot)}
                                    className={`p-3 rounded-xl text-center font-semibold text-xs transition border ${
                                      isHeldByMe
                                        ? "bg-teal-600 text-white border-teal-600 ring-2 ring-teal-500/50 shadow-md"
                                        : isAvailable
                                        ? "bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white border-slate-200 dark:border-slate-700 hover:border-teal-500 hover:bg-teal-50 dark:hover:bg-teal-950/30"
                                        : "bg-slate-100 dark:bg-slate-800/40 text-slate-400 dark:text-slate-600 border-transparent cursor-not-allowed"
                                    }`}
                                  >
                                    <div className="font-bold">{formatTime(slot.start_time)}</div>
                                    <div className="text-[10px] mt-0.5 opacity-80">{slot.status}</div>
                                  </button>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        {/* Active Slot Hold Timer & Symptoms Confirmation */}
                        {heldSlot && (
                          <div className="p-5 rounded-2xl bg-teal-50 dark:bg-teal-950/40 border border-teal-300 dark:border-teal-800 space-y-4">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center space-x-2 text-teal-900 dark:text-teal-200 font-bold text-sm">
                                <Clock className="w-4 h-4 text-teal-600 dark:text-teal-400" />
                                <span>Slot Locked for You ({formatTime(heldSlot.start_time)} - {formatTime(heldSlot.end_time)})</span>
                              </div>
                              <span className="px-2.5 py-1 rounded-full bg-teal-600 text-white text-xs font-mono font-bold animate-pulse">
                                {formatTimer(holdRemainingSeconds)}
                              </span>
                            </div>

                            <div>
                              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5">
                                Describe Your Symptoms (Optional)
                              </label>
                              <textarea
                                rows={3}
                                value={symptomsInput}
                                onChange={(e) => setSymptomsInput(e.target.value)}
                                placeholder="E.g., Mild headache and dizziness for 3 days..."
                                className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
                              />
                            </div>

                            <button
                              onClick={handleConfirmBooking}
                              disabled={bookingLoading}
                              className="w-full py-3 rounded-xl bg-teal-600 hover:bg-teal-700 active:bg-teal-800 text-white font-bold shadow-md shadow-teal-600/25 transition flex items-center justify-center space-x-2"
                            >
                              {bookingLoading ? (
                                <RefreshCw className="w-4 h-4 animate-spin" />
                              ) : (
                                <>
                                  <Check className="w-4 h-4" />
                                  <span>Confirm Appointment Booking</span>
                                </>
                              )}
                            </button>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="bg-white dark:bg-slate-900 p-12 rounded-2xl border border-slate-200 dark:border-slate-800 text-center text-slate-400 space-y-3">
                        <Stethoscope className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-700" />
                        <h3 className="text-lg font-bold text-slate-700 dark:text-slate-300">Select a Medical Provider</h3>
                        <p className="text-xs max-w-sm mx-auto">
                          Choose a doctor from the list on the left to view real-time open appointments and hold a slot.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* SUB-VIEW 2: MY APPOINTMENTS */}
            {patientTab === "my-appointments" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">My Appointments</h2>
                  <button
                    onClick={loadPatientAppointments}
                    className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                </div>

                {patientAppointmentsLoading ? (
                  <div className="p-12 text-center text-slate-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading appointments...</div>
                ) : patientAppointments.length === 0 ? (
                  <div className="bg-white dark:bg-slate-900 p-12 rounded-2xl border border-slate-200 dark:border-slate-800 text-center space-y-3">
                    <Calendar className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-700" />
                    <h3 className="text-base font-bold text-slate-700 dark:text-slate-300">No Appointments Yet</h3>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto">
                      You do not have any scheduled or past appointments. Find a doctor to schedule your first visit!
                    </p>
                    <button
                      onClick={() => setPatientTab("find-doctors")}
                      className="mt-2 px-4 py-2 rounded-xl bg-teal-600 text-white font-semibold text-xs hover:bg-teal-700 transition"
                    >
                      Find a Doctor
                    </button>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {patientAppointments.map((appt) => (
                      <div
                        key={appt.id}
                        className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-bold text-base text-slate-900 dark:text-white">
                              {appt.doctor_name || "Doctor"}
                            </h3>
                            <p className="text-xs text-teal-600 dark:text-teal-400 font-medium">
                              {appt.doctor_specialization || "Specialist"}
                            </p>
                          </div>
                          <span
                            className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                              appt.status === "CONFIRMED"
                                ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-200"
                                : appt.status === "COMPLETED"
                                ? "bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-200"
                                : "bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-200"
                            }`}
                          >
                            {appt.status}
                          </span>
                        </div>

                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 space-y-1.5 text-xs text-slate-600 dark:text-slate-400">
                          <div className="flex items-center space-x-2">
                            <Calendar className="w-4 h-4 text-slate-400" />
                            <span>{formatDate(appt.start_time)} • {formatTime(appt.start_time)} - {formatTime(appt.end_time)}</span>
                          </div>
                          {appt.symptoms && (
                            <div className="flex items-start space-x-2 pt-1">
                              <FileText className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
                              <span className="italic">"{appt.symptoms}"</span>
                            </div>
                          )}
                          {appt.google_event_id && (
                            <div className="flex items-center space-x-1.5 pt-1 text-teal-600 dark:text-teal-400 font-medium text-[11px]">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Synced to Google Calendar</span>
                            </div>
                          )}
                          {appt.cancellation_reason && (
                            <div className="flex items-start space-x-2 pt-1 text-rose-600 dark:text-rose-400">
                              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                              <span>Reason: {appt.cancellation_reason}</span>
                            </div>
                          )}
                        </div>

                        {/* Appointment Actions */}
                        {appt.status === "CONFIRMED" && (
                          <div className="flex space-x-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                            <button
                              onClick={() => {
                                setReschedulingAppt(appt);
                                setRescheduleHeldSlot(null);
                                loadRescheduleSlots(appt.doctor_id, rescheduleDate);
                              }}
                              className="flex-1 py-2 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800 text-xs font-semibold transition flex items-center justify-center space-x-1"
                            >
                              <ArrowRightLeft className="w-3.5 h-3.5" />
                              <span>Reschedule</span>
                            </button>

                            <button
                              onClick={() => setCancellingAppt(appt)}
                              className="px-4 py-2 rounded-xl border border-rose-200 dark:border-rose-900/40 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-xs font-semibold transition"
                            >
                              Cancel
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* SUB-VIEW 3: MY MEDICATIONS */}
            {patientTab === "medications" && (
              <div className="space-y-6">
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">Active Prescriptions & Reminders</h2>

                {remindersLoading ? (
                  <div className="p-12 text-center text-slate-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading medications...</div>
                ) : medicationReminders.length === 0 ? (
                  <div className="bg-white dark:bg-slate-900 p-12 rounded-2xl border border-slate-200 dark:border-slate-800 text-center space-y-3">
                    <Pill className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-700" />
                    <h3 className="text-base font-bold text-slate-700 dark:text-slate-300">No Active Prescriptions</h3>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto">
                      Any medications prescribed during your completed doctor consultations will appear here with scheduled dosage reminders.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {medicationReminders.map((rem) => (
                      <div
                        key={rem.id}
                        className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between"
                      >
                        <div className="flex items-center space-x-3">
                          <div className="p-3 rounded-xl bg-teal-50 dark:bg-teal-950 text-teal-600 dark:text-teal-400">
                            <Pill className="w-5 h-5" />
                          </div>
                          <div>
                            <h4 className="font-bold text-sm text-slate-900 dark:text-white">
                              {rem.dose_label || "Prescribed Medication"}
                            </h4>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {formatDate(rem.scheduled_for)} • {formatTime(rem.scheduled_for)}
                            </p>
                          </div>
                        </div>
                        <span className="px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-semibold">
                          {rem.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* =================================================================== */}
        {/* ROLE B: DOCTOR VIEW                                                 */}
        {/* =================================================================== */}
        {currentUser.role === "DOCTOR" && (
          <>
            {/* SUB-VIEW 1: DOCTOR AGENDA */}
            {doctorTab === "doctor-agenda" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">Doctor Clinical Agenda</h2>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Real-time queue of scheduled appointments, patient symptoms, and SOAP note generation.
                    </p>
                  </div>
                  <button
                    onClick={loadDoctorAgenda}
                    className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                </div>

                {doctorAgendaLoading ? (
                  <div className="p-12 text-center text-slate-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading agenda...</div>
                ) : doctorAgenda.length === 0 ? (
                  <div className="bg-white dark:bg-slate-900 p-12 rounded-2xl border border-slate-200 dark:border-slate-800 text-center space-y-3">
                    <Calendar className="w-12 h-12 mx-auto text-slate-300 dark:text-slate-700" />
                    <h3 className="text-base font-bold text-slate-700 dark:text-slate-300">No Patient Visits Scheduled</h3>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto">
                      Your schedule is clear for upcoming slots. Patient appointments will display here automatically.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {doctorAgenda.map((appt) => (
                      <div
                        key={appt.id}
                        className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4"
                      >
                        <div className="flex items-start justify-between">
                          <div>
                            <h3 className="font-bold text-base text-slate-900 dark:text-white">
                              {appt.patient_name || "Patient"}
                            </h3>
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              {appt.patient_email || "patient@example.com"}
                            </p>
                          </div>
                          <span
                            className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                              appt.status === "CONFIRMED"
                                ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-200"
                                : appt.status === "COMPLETED"
                                ? "bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-200"
                                : "bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-200"
                            }`}
                          >
                            {appt.status}
                          </span>
                        </div>

                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 space-y-1.5 text-xs text-slate-600 dark:text-slate-400">
                          <div className="flex items-center space-x-2 font-medium">
                            <Clock className="w-4 h-4 text-blue-500" />
                            <span>{formatDate(appt.start_time)} • {formatTime(appt.start_time)} - {formatTime(appt.end_time)}</span>
                          </div>
                          {appt.symptoms && (
                            <div className="flex items-start space-x-2 pt-1">
                              <FileText className="w-4 h-4 text-slate-400 flex-shrink-0 mt-0.5" />
                              <span className="italic">Reported Symptoms: "{appt.symptoms}"</span>
                            </div>
                          )}
                          {appt.google_event_id && (
                            <div className="flex items-center space-x-1.5 pt-1 text-teal-600 dark:text-teal-400 font-medium text-[11px]">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Synced to Google Calendar</span>
                            </div>
                          )}
                        </div>

                        {appt.status === "CONFIRMED" && (
                          <div className="flex items-center space-x-2 pt-1">
                            <button
                              onClick={() => handleOpenConsultation(appt)}
                              className="flex-1 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-semibold text-xs shadow-md shadow-blue-600/20 transition flex items-center justify-center space-x-1.5"
                            >
                              <Stethoscope className="w-4 h-4" />
                              <span>Start Consultation</span>
                            </button>
                            <button
                              onClick={() => handleOpenRescheduleModal(appt)}
                              className="px-3.5 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 font-semibold text-xs transition flex items-center justify-center space-x-1.5"
                              title="Reschedule this slot to a new date/time"
                            >
                              <Calendar className="w-4 h-4 text-indigo-500" />
                              <span>Reschedule</span>
                            </button>
                          </div>
                        )}

                        {appt.status === "CANCELLED" && (
                          <div className="space-y-2 pt-1">
                            <div className="p-2.5 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-xs text-amber-800 dark:text-amber-300 flex items-start space-x-2">
                              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                              <span>{appt.cancellation_reason || "Appointment was cancelled due to doctor leave"}</span>
                            </div>
                            <button
                              onClick={() => handleOpenRescheduleModal(appt)}
                              className="w-full py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-xs shadow-md shadow-indigo-600/20 transition flex items-center justify-center space-x-1.5"
                            >
                              <Calendar className="w-4 h-4" />
                              <span>Reschedule Pending Slot for Patient</span>
                            </button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* SUB-VIEW 2: DOCTOR LEAVE MANAGEMENT */}
            {doctorTab === "doctor-leaves" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">Apply for Leave / Vacation</h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Schedule time off. The system will detect conflicting appointments, cancel them, and automatically notify patients.
                  </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Leave Application Form */}
                  <div className="lg:col-span-5 bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                    <h3 className="font-bold text-sm text-slate-900 dark:text-white">Request Leave Period</h3>

                    <form onSubmit={handleDoctorPreviewLeave} className="space-y-3">
                      <div>
                        <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                          Start Date
                        </label>
                        <input
                          type="date"
                          required
                          value={docLeaveStartDate}
                          min={new Date().toISOString().split("T")[0]}
                          onChange={(e) => setDocLeaveStartDate(e.target.value)}
                          className="w-full p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                          End Date
                        </label>
                        <input
                          type="date"
                          required
                          value={docLeaveEndDate}
                          min={docLeaveStartDate}
                          onChange={(e) => setDocLeaveEndDate(e.target.value)}
                          className="w-full p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                          Reason / Description
                        </label>
                        <input
                          type="text"
                          required
                          value={docLeaveReason}
                          onChange={(e) => setDocLeaveReason(e.target.value)}
                          placeholder="E.g., Medical conference, personal leave"
                          className="w-full p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-blue-500"
                        />
                      </div>

                      <button
                        type="submit"
                        disabled={docLeavePreviewLoading}
                        className="w-full py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs shadow-md shadow-blue-600/20 transition flex items-center justify-center space-x-1.5"
                      >
                        {docLeavePreviewLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <span>Preview Leave Impact</span>}
                      </button>
                    </form>

                    {/* Preview Conflict Card */}
                    {docLeavePreview && (
                      <div className="mt-4 p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 space-y-3">
                        <div className="flex items-center space-x-2 text-amber-800 dark:text-amber-300 text-xs font-bold">
                          <AlertTriangle className="w-4 h-4" />
                          <span>Conflicting Appointments ({docLeavePreview.affected_count})</span>
                        </div>

                        {docLeavePreview.affected_count === 0 ? (
                          <p className="text-xs text-amber-700 dark:text-amber-300">
                            No active patient bookings will be disrupted by this leave period.
                          </p>
                        ) : (
                          <div className="space-y-1.5 max-h-36 overflow-y-auto">
                            {docLeavePreview.affected_appointments.map((a: any) => (
                              <div key={a.appointment_id} className="text-[11px] p-2 rounded bg-white dark:bg-slate-900 border border-amber-200 dark:border-amber-900">
                                <strong>{a.patient_name}</strong> • {formatDate(a.start_time)} ({formatTime(a.start_time)})
                              </div>
                            ))}
                          </div>
                        )}

                        <button
                          onClick={handleDoctorApplyLeave}
                          disabled={docLeaveConfirmLoading}
                          className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow transition flex items-center justify-center space-x-1.5"
                        >
                          {docLeaveConfirmLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <span>Submit Leave Application for Admin Approval</span>}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Active / Approved Leaves */}
                  <div className="lg:col-span-7 bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                    <h3 className="font-bold text-sm text-slate-900 dark:text-white">Your Leave Applications & History</h3>

                    {docLeavesLoading ? (
                      <div className="p-8 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" /> Loading leaves...</div>
                    ) : docLeavesList.length === 0 ? (
                      <div className="p-8 text-center text-slate-500 text-xs">
                        You have no submitted leave records.
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {docLeavesList.map((leave) => (
                          <div
                            key={leave.id}
                            className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/60 space-y-2"
                          >
                            <div className="flex items-start justify-between">
                              <div>
                                <div className="font-bold text-sm text-slate-900 dark:text-white flex items-center space-x-2">
                                  <span>{leave.start_date} → {leave.end_date}</span>
                                  <span
                                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                                      leave.status === "APPROVED"
                                        ? "bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                                        : leave.status === "REJECTED"
                                        ? "bg-rose-100 dark:bg-rose-950/80 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
                                        : "bg-amber-100 dark:bg-amber-950/80 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800"
                                    }`}
                                  >
                                    {leave.status === "APPROVED"
                                      ? "Approved"
                                      : leave.status === "REJECTED"
                                      ? "Rejected"
                                      : "Pending Admin Approval"}
                                  </span>
                                </div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                  <strong>Reason:</strong> {leave.reason || "Personal Leave"}
                                </p>
                              </div>

                              {leave.status === "PENDING" && (
                                <button
                                  onClick={() => handleDoctorDeleteLeave(leave.id)}
                                  className="p-2 rounded-lg hover:bg-rose-100 dark:hover:bg-rose-950/60 text-rose-600 transition"
                                  title="Cancel Leave Request"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </div>

                            {/* Rejection Note Display */}
                            {leave.status === "REJECTED" && (
                              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-200 space-y-1">
                                <div className="font-semibold flex items-center space-x-1.5 text-rose-700 dark:text-rose-300">
                                  <AlertCircle className="w-3.5 h-3.5" />
                                  <span>Admin Rejection Reason</span>
                                </div>
                                <p className="italic">
                                  "{leave.rejection_reason || "Leave request was not approved by administration."}"
                                </p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Disrupted Appointments from Approved Leaves */}
                    {doctorAgenda.some((a) => a.status === "CANCELLED") && (
                      <div className="mt-6 p-5 rounded-2xl bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800/80 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2 text-indigo-900 dark:text-indigo-200 font-bold text-xs">
                            <Calendar className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                            <span>Appointments Disrupted by Approved Leaves (Pending Reschedule)</span>
                          </div>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-200 dark:bg-indigo-900 text-indigo-800 dark:text-indigo-200">
                            {doctorAgenda.filter((a) => a.status === "CANCELLED").length} Patient(s)
                          </span>
                        </div>
                        <p className="text-xs text-slate-600 dark:text-slate-400">
                          These patient slots were cancelled during your approved leave. You can pick and assign new available slots to them:
                        </p>
                        <div className="space-y-2">
                          {doctorAgenda
                            .filter((a) => a.status === "CANCELLED")
                            .map((appt) => (
                              <div
                                key={appt.id}
                                className="p-3.5 rounded-xl bg-white dark:bg-slate-900 border border-indigo-100 dark:border-indigo-900 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs"
                              >
                                <div>
                                  <div className="font-bold text-slate-900 dark:text-white">
                                    {appt.patient_name || "Patient"} • <span className="text-slate-500 font-normal">{appt.patient_email}</span>
                                  </div>
                                  <div className="text-slate-500 dark:text-slate-400 text-[11px] mt-0.5">
                                    Cancelled Slot: {formatDate(appt.start_time)} ({formatTime(appt.start_time)}) • Reason: "{appt.cancellation_reason || 'Doctor on approved leave'}"
                                  </div>
                                </div>
                                <button
                                  onClick={() => handleOpenRescheduleModal(appt)}
                                  className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-bold text-xs shadow-sm transition flex items-center justify-center space-x-1.5 flex-shrink-0"
                                >
                                  <Calendar className="w-3.5 h-3.5" />
                                  <span>Reschedule Slot</span>
                                </button>
                              </div>
                            ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* =================================================================== */}
        {/* ROLE C: ADMIN VIEW                                                  */}
        {/* =================================================================== */}
        {currentUser.role === "ADMIN" && (
          <>
            {/* SUB-VIEW 1: EXECUTIVE STATS */}
            {adminTab === "admin-stats" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">System Executive Dashboard</h2>
                  <button
                    onClick={loadAdminStats}
                    className="p-2.5 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                </div>

                {adminStats && (
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
                      <span className="text-xs uppercase font-semibold text-slate-500 dark:text-slate-400">Total Patients</span>
                      <div className="text-3xl font-extrabold text-teal-600 dark:text-teal-400">{adminStats.total_patients}</div>
                    </div>
                    <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
                      <span className="text-xs uppercase font-semibold text-slate-500 dark:text-slate-400">Active Doctors</span>
                      <div className="text-3xl font-extrabold text-blue-600 dark:text-blue-400">{adminStats.total_doctors}</div>
                    </div>
                    <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
                      <span className="text-xs uppercase font-semibold text-slate-500 dark:text-slate-400">Appointments Booked</span>
                      <div className="text-3xl font-extrabold text-indigo-600 dark:text-indigo-400">{adminStats.total_appointments}</div>
                    </div>
                    <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm space-y-1">
                      <span className="text-xs uppercase font-semibold text-slate-500 dark:text-slate-400">Active Slot Holds</span>
                      <div className="text-3xl font-extrabold text-amber-600 dark:text-amber-400">{adminStats.total_holds_active}</div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* SUB-VIEW 2: DOCTOR ROSTERS */}
            {adminTab === "admin-doctors" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">Doctor Roster & Availability</h2>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Manage clinical staff, specialties, and register new physicians to the hospital network.
                    </p>
                  </div>
                  <button
                    onClick={() => setAdminRegisterDoctorModalOpen(true)}
                    className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-xs shadow-md shadow-indigo-600/20 transition flex items-center space-x-2"
                  >
                    <UserPlus className="w-4 h-4" />
                    <span>Register New Doctor</span>
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {adminDoctorsList.map((doc) => (
                    <div
                      key={doc.id}
                      className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-3"
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="font-bold text-base text-slate-900 dark:text-white">{doc.full_name}</h4>
                          <p className="text-xs text-teal-600 dark:text-teal-400 font-semibold">{doc.specialization}</p>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">{doc.email}</p>
                        </div>
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${doc.is_active ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300" : "bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400"}`}>
                          {doc.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                      {doc.bio && (
                        <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 italic">
                          "{doc.bio}"
                        </p>
                      )}
                      <div className="pt-3 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-500">
                        <span>Slot Duration: {doc.slot_duration_minutes || 30} mins</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* SUB-VIEW 3: LEAVE OVERSEER & APPROVALS */}
            {adminTab === "admin-leaves" && (
              <div className="space-y-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">Doctor Leave Applications & Approvals</h2>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Review leave requests from doctors. Approving will automatically cancel conflicting bookings and notify patients. Rejecting provides a reason to the doctor.
                    </p>
                  </div>

                  {/* Filter Tabs */}
                  <div className="bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl flex space-x-1 self-start md:self-auto border border-slate-200 dark:border-slate-700">
                    {["ALL", "PENDING", "APPROVED", "REJECTED"].map((st) => (
                      <button
                        key={st}
                        onClick={() => {
                          setAdminLeaveStatusFilter(st);
                          loadAdminAllLeaves(st, adminLeaveDoctorId);
                        }}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                          adminLeaveStatusFilter === st
                            ? "bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm"
                            : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
                        }`}
                      >
                        {st === "ALL" ? "All Requests" : st === "PENDING" ? "Pending Approval" : st === "APPROVED" ? "Approved" : "Rejected"}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-4">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200 dark:border-slate-800">
                    <div>
                      <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                        Filter by Doctor
                      </label>
                      <select
                        value={adminLeaveDoctorId}
                        onChange={(e) => {
                          setAdminLeaveDoctorId(e.target.value);
                          loadAdminAllLeaves(adminLeaveStatusFilter, e.target.value);
                        }}
                        className="w-full md:w-80 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="">All Doctors</option>
                        {doctors.map((d) => (
                          <option key={d.id} value={d.id}>{d.full_name} ({d.specialization})</option>
                        ))}
                      </select>
                    </div>

                    <button
                      onClick={() => loadAdminAllLeaves(adminLeaveStatusFilter, adminLeaveDoctorId)}
                      className="p-2 rounded-xl border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-400 transition self-end"
                      title="Refresh leaves list"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  </div>

                  <div>
                    {adminDoctorLeavesLoading ? (
                      <div className="p-8 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" /> Loading leave applications...</div>
                    ) : adminDoctorLeavesList.length === 0 ? (
                      <div className="p-8 text-center text-slate-500 text-xs">
                        No leave records found matching current filters.
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {adminDoctorLeavesList.map((leave) => (
                          <div
                            key={leave.id}
                            className={`p-5 rounded-2xl border transition ${
                              leave.status === "PENDING"
                                ? "border-amber-300 dark:border-amber-700/60 bg-amber-50/50 dark:bg-amber-950/20"
                                : leave.status === "REJECTED"
                                ? "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40"
                                : "border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/40"
                            }`}
                          >
                            <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                              <div className="space-y-1">
                                <div className="flex items-center space-x-2.5">
                                  <h4 className="font-bold text-sm text-slate-900 dark:text-white">
                                    {leave.doctor_name || "Doctor"}
                                  </h4>
                                  <span className="text-xs text-slate-500 dark:text-slate-400">
                                    • {leave.doctor_specialization || "Physician"}
                                  </span>
                                  <span
                                    className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                                      leave.status === "APPROVED"
                                        ? "bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
                                        : leave.status === "REJECTED"
                                        ? "bg-rose-100 dark:bg-rose-950 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
                                        : "bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-800 animate-pulse"
                                    }`}
                                  >
                                    {leave.status === "APPROVED"
                                      ? "Approved"
                                      : leave.status === "REJECTED"
                                      ? "Rejected"
                                      : "Pending Admin Review"}
                                  </span>
                                </div>

                                <div className="text-xs text-slate-700 dark:text-slate-300 font-semibold pt-1 flex items-center space-x-2">
                                  <Calendar className="w-3.5 h-3.5 text-slate-400" />
                                  <span>{leave.start_date} → {leave.end_date}</span>
                                </div>

                                <p className="text-xs text-slate-600 dark:text-slate-400">
                                  <strong>Reason for Leave:</strong> {leave.reason || "Personal / Medical Leave"}
                                </p>

                                <div className="pt-1 text-[11px] text-slate-500 dark:text-slate-400 flex items-center space-x-2">
                                  <span className="px-2 py-0.5 rounded bg-slate-200/70 dark:bg-slate-700/70 text-slate-700 dark:text-slate-300 font-medium">
                                    {leave.affected_appointments_count} conflicting appointment(s)
                                  </span>
                                  {leave.created_at && (
                                    <span>• Submitted {formatDate(leave.created_at)}</span>
                                  )}
                                </div>
                              </div>

                              {/* Action buttons for PENDING leaves */}
                              {leave.status === "PENDING" && (
                                <div className="flex items-center space-x-2 self-start md:self-center">
                                  <button
                                    onClick={() => handleAdminApproveLeave(leave)}
                                    disabled={adminApproveSubmitting === leave.id}
                                    className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white font-semibold text-xs shadow-md shadow-emerald-600/20 transition flex items-center space-x-1.5"
                                  >
                                    {adminApproveSubmitting === leave.id ? (
                                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                    ) : (
                                      <>
                                        <Check className="w-3.5 h-3.5" />
                                        <span>Approve Leave</span>
                                      </>
                                    )}
                                  </button>

                                  <button
                                    onClick={() => handleAdminOpenReject(leave)}
                                    className="px-4 py-2 rounded-xl border border-rose-300 dark:border-rose-800 hover:bg-rose-50 dark:hover:bg-rose-950/60 text-rose-600 dark:text-rose-400 font-semibold text-xs transition flex items-center space-x-1.5"
                                  >
                                    <X className="w-3.5 h-3.5" />
                                    <span>Reject...</span>
                                  </button>
                                </div>
                              )}
                            </div>

                            {/* Show rejection reason note if rejected */}
                            {leave.status === "REJECTED" && (
                              <div className="mt-3 p-3 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/60 text-xs text-rose-800 dark:text-rose-200 space-y-1">
                                <div className="font-bold flex items-center space-x-1.5 text-rose-700 dark:text-rose-300">
                                  <AlertCircle className="w-3.5 h-3.5" />
                                  <span>Reason for Rejection (sent to doctor):</span>
                                </div>
                                <p className="italic">"{leave.rejection_reason}"</p>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* SUB-VIEW 4: PATIENTS DIRECTORY */}
            {adminTab === "admin-patients" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold text-slate-900 dark:text-white">Patients Directory</h2>
                </div>

                {adminPatientsLoading ? (
                  <div className="p-12 text-center text-slate-500"><RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" /> Loading patients...</div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {adminPatientsList.map((patient) => (
                      <div key={patient.id} className="bg-white dark:bg-slate-900 p-5 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm space-y-2">
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="font-bold text-base text-slate-900 dark:text-white">{patient.full_name}</h4>
                            <p className="text-xs text-slate-500 dark:text-slate-400">{patient.email}</p>
                          </div>
                          <span className="px-2 py-0.5 rounded-md bg-teal-50 dark:bg-teal-950 text-teal-700 dark:text-teal-300 text-xs font-semibold">
                            {patient.total_appointments} visits
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* SUB-VIEW 5: JOB MONITOR */}
            {adminTab === "admin-jobs" && (
              <div className="space-y-6">
                <h2 className="text-xl font-bold text-slate-900 dark:text-white">Background Job Queue Monitor</h2>

                <div className="bg-white dark:bg-slate-900 p-6 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm">
                  {adminJobsLoading ? (
                    <div className="p-8 text-center text-slate-500"><RefreshCw className="w-5 h-5 animate-spin mx-auto mb-2" /> Loading queue...</div>
                  ) : adminJobsList.length === 0 ? (
                    <div className="p-8 text-center text-slate-500 text-xs">No background jobs in recent queue.</div>
                  ) : (
                    <div className="space-y-2">
                      {adminJobsList.map((job) => (
                        <div key={job.id} className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 flex items-center justify-between text-xs">
                          <div>
                            <span className="font-bold">{job.job_type}</span>
                            <span className="ml-2 text-slate-500">ID: {job.id.slice(0, 8)}...</span>
                          </div>
                          <span className="px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-950 text-blue-800 dark:text-blue-300 font-semibold">
                            {job.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </>
        )}

      </main>

      {/* =================================================================== */}
      {/* MODALS (Consultation & AI Notes, Notifications, Reschedule, Cancel) */}
      {/* =================================================================== */}

      {/* Modal 1: Doctor Consultation & AI SOAP Notes */}
      {consultationModalAppt && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-3xl w-full p-6 shadow-2xl space-y-6 my-8">
            <div className="flex items-start justify-between pb-4 border-b border-slate-200 dark:border-slate-800">
              <div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">
                  Consultation: {consultationModalAppt.patient_name}
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {formatDate(consultationModalAppt.start_time)} • Symptoms: "{consultationModalAppt.symptoms || 'None reported'}"
                </p>
              </div>
              <button
                onClick={() => setConsultationModalAppt(null)}
                className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* AI Assistant Generator (Gemini AI Only) */}
            <div className="p-4 rounded-2xl bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-indigo-900 dark:text-indigo-200 font-bold text-xs">
                  <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                  <span>Google Gemini AI Clinical Assistant</span>
                </div>
                <button
                  type="button"
                  onClick={handleGenerateAiPreVisitSummary}
                  disabled={isGeneratingAiSummary}
                  className="px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-bold text-xs shadow-sm transition flex items-center space-x-1.5 disabled:opacity-50"
                >
                  {isGeneratingAiSummary ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Generating with Gemini...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-3.5 h-3.5" />
                      <span>Generate AI Clinical Insights</span>
                    </>
                  )}
                </button>
              </div>

              {activePreVisitSummary && (
                <div className="p-3 rounded-xl bg-white dark:bg-slate-900 text-xs space-y-1.5 border border-indigo-100 dark:border-indigo-900">
                  <div className="font-semibold text-slate-900 dark:text-white">
                    Chief Complaint: {activePreVisitSummary.chief_complaint}
                  </div>
                  {activePreVisitSummary.suggested_questions?.length > 0 && (
                    <div>
                      <div className="text-[11px] text-slate-500 uppercase font-bold mt-1">Suggested Questions:</div>
                      <ul className="list-disc list-inside space-y-0.5 text-slate-600 dark:text-slate-300">
                        {activePreVisitSummary.suggested_questions.map((q, idx) => (
                          <li key={idx}>{q}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Clinical SOAP Fields */}
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1">
                  Diagnosis <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={consultationDiagnosis}
                  onChange={(e) => setConsultationDiagnosis(e.target.value)}
                  placeholder="Primary clinical diagnosis..."
                  className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1">
                  Clinical Notes
                </label>
                <textarea
                  rows={4}
                  value={consultationClinicalNotes}
                  onChange={(e) => setConsultationClinicalNotes(e.target.value)}
                  placeholder="Detailed examination and assessment notes..."
                  className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500 font-mono text-xs"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1">
                  Follow-up Instructions
                </label>
                <input
                  type="text"
                  value={consultationFollowUp}
                  onChange={(e) => setConsultationFollowUp(e.target.value)}
                  placeholder="E.g., Revisit in 2 weeks if symptoms persist..."
                  className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-sm focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {/* Prescription Drawer */}
              <div className="pt-3 border-t border-slate-200 dark:border-slate-800">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400">
                    Prescribed Medications
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      setConsultationMedications([
                        ...consultationMedications,
                        { name: "", dosage: "", frequency: "", duration: "", instructions: "" },
                      ])
                    }
                    className="text-xs text-blue-600 dark:text-blue-400 font-semibold hover:underline flex items-center space-x-1"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Drug</span>
                  </button>
                </div>

                {consultationMedications.map((med, idx) => (
                  <div key={idx} className="grid grid-cols-4 gap-2 mb-2">
                    <input
                      type="text"
                      placeholder="Medication Name"
                      value={med.name}
                      onChange={(e) => {
                        const next = [...consultationMedications];
                        next[idx].name = e.target.value;
                        setConsultationMedications(next);
                      }}
                      className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                    />
                    <input
                      type="text"
                      placeholder="Dosage (e.g. 500mg)"
                      value={med.dosage}
                      onChange={(e) => {
                        const next = [...consultationMedications];
                        next[idx].dosage = e.target.value;
                        setConsultationMedications(next);
                      }}
                      className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                    />
                    <input
                      type="text"
                      placeholder="Frequency (e.g. 2x Daily)"
                      value={med.frequency}
                      onChange={(e) => {
                        const next = [...consultationMedications];
                        next[idx].frequency = e.target.value;
                        setConsultationMedications(next);
                      }}
                      className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                    />
                    <input
                      type="text"
                      placeholder="Duration (e.g. 7 days)"
                      value={med.duration}
                      onChange={(e) => {
                        const next = [...consultationMedications];
                        next[idx].duration = e.target.value;
                        setConsultationMedications(next);
                      }}
                      className="p-2 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs"
                    />
                  </div>
                ))}
              </div>
            </div>

            <div className="flex justify-end space-x-3 pt-4 border-t border-slate-200 dark:border-slate-800">
              <button
                onClick={() => setConsultationModalAppt(null)}
                className="px-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleCompleteConsultation}
                disabled={consultationSubmitting}
                className="px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-md shadow-blue-600/20 transition flex items-center space-x-2"
              >
                {consultationSubmitting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <span>Finalize & Complete Consultation</span>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 2: Notification Center */}
      {showNotifModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center space-x-2">
                <Bell className="w-5 h-5 text-teal-600" />
                <h3 className="font-bold text-base text-slate-900 dark:text-white">Notifications Center</h3>
              </div>
              <button
                onClick={() => setShowNotifModal(false)}
                className="p-1.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="max-h-80 overflow-y-auto space-y-2">
              {notifications.length === 0 ? (
                <p className="text-center text-xs text-slate-500 py-8">No notifications yet.</p>
              ) : (
                notifications.map((n) => (
                  <div
                    key={n.id}
                    onClick={() => handleMarkNotifRead(n.id)}
                    className={`p-3.5 rounded-xl border text-xs transition cursor-pointer ${
                      n.is_read
                        ? "bg-slate-50 dark:bg-slate-800/40 border-slate-200 dark:border-slate-800 text-slate-500"
                        : "bg-teal-50/70 dark:bg-teal-950/40 border-teal-300 dark:border-teal-800 text-slate-900 dark:text-white font-medium"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold">{n.title}</span>
                      <span className="text-[10px] text-slate-400">{formatTime(n.created_at)}</span>
                    </div>
                    <p className="mt-1 text-slate-600 dark:text-slate-300">{n.body}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {/* Modal 3: Cancel Appointment Modal */}
      {cancellingAppt && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <h3 className="text-lg font-bold text-slate-900 dark:text-white">Cancel Appointment</h3>
            <p className="text-xs text-slate-500">
              Are you sure you want to cancel your appointment with {cancellingAppt.doctor_name}?
            </p>
            <input
              type="text"
              value={cancelReasonInput}
              onChange={(e) => setCancelReasonInput(e.target.value)}
              placeholder="Reason for cancellation (optional)"
              className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-rose-500"
            />
            <div className="flex justify-end space-x-2 pt-2">
              <button
                onClick={() => setCancellingAppt(null)}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold"
              >
                Keep Appointment
              </button>
              <button
                onClick={handleConfirmCancel}
                disabled={cancelLoading}
                className="px-4 py-2 rounded-xl bg-rose-600 text-white text-xs font-bold hover:bg-rose-700 transition"
              >
                {cancelLoading ? "Cancelling..." : "Confirm Cancellation"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 4: Reschedule Modal */}
      {reschedulingAppt && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                Reschedule: {reschedulingAppt.doctor_name}
              </h3>
              <button onClick={() => setReschedulingAppt(null)} className="p-1 text-slate-400">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Select New Date</label>
                <input
                  type="date"
                  value={rescheduleDate}
                  min={new Date().toISOString().split("T")[0]}
                  onChange={(e) => {
                    setRescheduleDate(e.target.value);
                    loadRescheduleSlots(reschedulingAppt.doctor_id, e.target.value);
                  }}
                  className="w-full p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs font-semibold"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-500 mb-1">Pick New Available Slot</label>
                {rescheduleSlotsLoading ? (
                  <p className="text-xs text-slate-400">Loading open slots...</p>
                ) : (
                  <div className="grid grid-cols-3 gap-2 max-h-40 overflow-y-auto">
                    {rescheduleSlots.filter((s) => s.status === "AVAILABLE" || rescheduleHeldSlot?.id === s.id).map((slot) => (
                      <button
                        key={slot.id}
                        onClick={() => handleHoldRescheduleSlot(slot)}
                        className={`p-2 rounded-xl text-xs font-semibold border ${
                          rescheduleHeldSlot?.id === slot.id
                            ? "bg-teal-600 text-white border-teal-600"
                            : "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 hover:border-teal-500"
                        }`}
                      >
                        {formatTime(slot.start_time)}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {rescheduleHeldSlot && (
                <div className="p-3 rounded-xl bg-teal-50 dark:bg-teal-950 text-xs text-teal-800 dark:text-teal-300 font-medium">
                  Selected slot {formatTime(rescheduleHeldSlot.start_time)} (Lock timer: {formatTimer(rescheduleHoldRemaining)})
                </div>
              )}
            </div>

            <div className="flex justify-end space-x-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <button
                onClick={() => setReschedulingAppt(null)}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReschedule}
                disabled={!rescheduleHeldSlot || rescheduleLoading}
                className="px-5 py-2 rounded-xl bg-teal-600 text-white font-bold text-xs hover:bg-teal-700 disabled:opacity-50 transition"
              >
                {rescheduleLoading ? "Rescheduling..." : "Confirm Reschedule"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 5: Admin Leave Rejection Reason */}
      {adminRejectingLeave && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center space-x-2 text-rose-600">
                <XCircle className="w-5 h-5" />
                <h3 className="font-bold text-base text-slate-900 dark:text-white">Reject Leave Request</h3>
              </div>
              <button
                onClick={() => setAdminRejectingLeave(null)}
                className="p-1.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 space-y-1 text-xs text-slate-600 dark:text-slate-400">
              <div className="font-bold text-slate-900 dark:text-white">
                {adminRejectingLeave.doctor_name || "Doctor"} ({adminRejectingLeave.doctor_specialization})
              </div>
              <div>
                <strong>Requested Period:</strong> {adminRejectingLeave.start_date} → {adminRejectingLeave.end_date}
              </div>
              <div>
                <strong>Doctor's Reason:</strong> {adminRejectingLeave.reason || "None specified"}
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-600 dark:text-slate-400 mb-1.5">
                Reason for Rejection <span className="text-rose-500">*</span>
              </label>
              <textarea
                rows={4}
                required
                value={adminRejectReasonInput}
                onChange={(e) => setAdminRejectReasonInput(e.target.value)}
                placeholder="Explain to the doctor why this leave request cannot be approved at this time..."
                className="w-full p-3 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-rose-500 focus:outline-none"
              />
              <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-1">
                This explanation will be delivered directly to the doctor's notifications and portal dashboard.
              </p>
            </div>

            <div className="flex justify-end space-x-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setAdminRejectingLeave(null)}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleAdminConfirmReject}
                disabled={adminRejectSubmitting || !adminRejectReasonInput.trim()}
                className="px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold text-xs shadow-md shadow-rose-600/20 disabled:opacity-50 transition flex items-center space-x-1.5"
              >
                {adminRejectSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <span>Confirm Rejection</span>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal 6: Admin Register New Doctor */}
      {adminRegisterDoctorModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl max-w-xl w-full p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div className="flex items-center space-x-2 text-indigo-600">
                <UserPlus className="w-5 h-5" />
                <h3 className="font-bold text-base text-slate-900 dark:text-white">Register New Doctor</h3>
              </div>
              <button
                onClick={() => setAdminRegisterDoctorModalOpen(false)}
                className="p-1.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAdminRegisterDoctor} className="space-y-3.5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Doctor Full Name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={adminNewDocName}
                    onChange={(e) => setAdminNewDocName(e.target.value)}
                    placeholder="Dr. Gregory House"
                    className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Specialization <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={adminNewDocSpecialization}
                    onChange={(e) => setAdminNewDocSpecialization(e.target.value)}
                    placeholder="e.g. Cardiology, Neurology, Pediatrics"
                    className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Email Address <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="email"
                    required
                    value={adminNewDocEmail}
                    onChange={(e) => setAdminNewDocEmail(e.target.value)}
                    placeholder="doctor@clinica.health"
                    className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Initial Password <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="password"
                    required
                    value={adminNewDocPassword}
                    onChange={(e) => setAdminNewDocPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                  Professional Bio / Qualifications
                </label>
                <textarea
                  rows={2}
                  value={adminNewDocBio}
                  onChange={(e) => setAdminNewDocBio(e.target.value)}
                  placeholder="Department Chief of Medicine, Board Certified Specialist..."
                  className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Consultation Duration
                  </label>
                  <select
                    value={adminNewDocSlotDuration}
                    onChange={(e) => setAdminNewDocSlotDuration(Number(e.target.value))}
                    className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
                  >
                    <option value={15}>15 Minutes</option>
                    <option value={30}>30 Minutes (Standard)</option>
                    <option value={45}>45 Minutes</option>
                    <option value={60}>60 Minutes</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Accepted Insurances
                  </label>
                  <input
                    type="text"
                    value={adminNewDocInsurance}
                    onChange={(e) => setAdminNewDocInsurance(e.target.value)}
                    placeholder="Aetna, BlueCross, Cigna"
                    className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>

              <div className="p-3 rounded-xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 flex items-center space-x-2.5">
                <input
                  type="checkbox"
                  id="autoSlots"
                  checked={adminNewDocAutoSlots}
                  onChange={(e) => setAdminNewDocAutoSlots(e.target.checked)}
                  className="rounded text-indigo-600 focus:ring-indigo-500 w-4 h-4"
                />
                <label htmlFor="autoSlots" className="text-xs text-indigo-900 dark:text-indigo-200 font-medium">
                  Automatically generate 14-day open booking schedule for this doctor
                </label>
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setAdminRegisterDoctorModalOpen(false)}
                  className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={adminNewDocSubmitting}
                  className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs shadow-md shadow-indigo-600/20 disabled:opacity-50 transition flex items-center space-x-1.5"
                >
                  {adminNewDocSubmitting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <span>Register Physician</span>}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* =================================================================== */}
      {/* RESCHEDULE APPOINTMENT MODAL (For Doctor & Patient)                */}
      {/* =================================================================== */}
      {reschedulingAppt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white dark:bg-slate-900 rounded-3xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 dark:border-slate-800 space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
              <div className="flex items-center space-x-2.5">
                <div className="p-2 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                  <Calendar className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                    Reschedule Appointment
                  </h3>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Patient: <strong>{reschedulingAppt.patient_name}</strong> ({reschedulingAppt.patient_email})
                  </p>
                </div>
              </div>
              <button
                onClick={() => setReschedulingAppt(null)}
                className="p-2 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 text-xs text-slate-600 dark:text-slate-300 space-y-1">
              <div>
                <strong>Previous / Disrupted Slot:</strong> {formatDate(reschedulingAppt.start_time)} • {formatTime(reschedulingAppt.start_time)}
              </div>
              {reschedulingAppt.symptoms && (
                <div className="italic text-slate-500">Symptoms: "{reschedulingAppt.symptoms}"</div>
              )}
            </div>

            {/* Date Selection */}
            <div className="space-y-2">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Select New Appointment Date
              </label>
              <input
                type="date"
                value={rescheduleDate}
                min={new Date().toISOString().split("T")[0]}
                onChange={(e) => {
                  setRescheduleDate(e.target.value);
                  loadRescheduleSlots(reschedulingAppt.doctor_id, e.target.value);
                }}
                className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500 font-medium"
              />
            </div>

            {/* Available Slots */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                  Available Slots on {rescheduleDate}
                </label>
                {rescheduleSlotsLoading && (
                  <span className="text-[11px] text-slate-400 flex items-center space-x-1">
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    <span>Loading slots...</span>
                  </span>
                )}
              </div>

              {rescheduleSlotsLoading ? (
                <div className="p-6 text-center text-slate-400 text-xs">
                  <RefreshCw className="w-4 h-4 animate-spin mx-auto mb-1" />
                  Checking schedule...
                </div>
              ) : rescheduleSlots.filter((s) => s.status === "AVAILABLE").length === 0 ? (
                <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900/60 text-xs text-amber-800 dark:text-amber-300 text-center">
                  No open slots available on this date. Please pick another day.
                </div>
              ) : (
                <div className="grid grid-cols-3 gap-2 max-h-44 overflow-y-auto p-1">
                  {rescheduleSlots
                    .filter((s) => s.status === "AVAILABLE")
                    .map((slot) => {
                      const isSelected = rescheduleHeldSlot?.id === slot.id;
                      return (
                        <button
                          key={slot.id}
                          type="button"
                          onClick={() => setRescheduleHeldSlot(slot)}
                          className={`p-2.5 rounded-xl text-xs font-bold transition flex flex-col items-center justify-center border ${
                            isSelected
                              ? "bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-600/30"
                              : "bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-indigo-400 dark:hover:border-indigo-600"
                          }`}
                        >
                          <span>{formatTime(slot.start_time)}</span>
                          <span className="text-[10px] font-normal opacity-80 mt-0.5">
                            {formatTime(slot.end_time)}
                          </span>
                        </button>
                      );
                    })}
                </div>
              )}
            </div>

            {/* Optional Reschedule Reason */}
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300">
                Reschedule Note / Reason (Optional)
              </label>
              <input
                type="text"
                value={rescheduleReason}
                onChange={(e) => setRescheduleReason(e.target.value)}
                placeholder="E.g., Rescheduled after approved leave period"
                className="w-full p-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-xs focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Actions */}
            <div className="flex justify-end space-x-2 pt-3 border-t border-slate-200 dark:border-slate-800">
              <button
                type="button"
                onClick={() => setReschedulingAppt(null)}
                className="px-4 py-2 rounded-xl border border-slate-300 dark:border-slate-700 text-xs font-semibold hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmReschedule}
                disabled={!rescheduleHeldSlot || rescheduleLoading}
                className="px-6 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-bold text-xs shadow-md shadow-indigo-600/20 disabled:opacity-50 transition flex items-center space-x-1.5"
              >
                {rescheduleLoading ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Rescheduling...</span>
                  </>
                ) : (
                  <>
                    <Calendar className="w-3.5 h-3.5" />
                    <span>Confirm Reschedule</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
