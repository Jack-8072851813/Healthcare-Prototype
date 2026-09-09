/**
 * dashboardApi.ts
 * ===============
 * Typed API client for all Admin/Doctor Dashboard endpoints.
 * Connects to the FastAPI backend at http://localhost:8000/api/dashboard/*.
 *
 * Falls back to empty/default data if the backend is unreachable so the
 * UI never crashes in offline/dev scenarios.
 */

// ─── Utility Helpers ──────────────────────────────────────────────────────────

export function format12HourTime(timeStr: string | null | undefined): string {
  if (!timeStr) return '—';
  const str = String(timeStr).trim();
  if (!str) return '—';
  if (str.toUpperCase().includes('AM') || str.toUpperCase().includes('PM')) {
    return str;
  }
  const parts = str.split(':');
  if (parts.length < 2) return str;
  let hours = parseInt(parts[0], 10);
  const minutes = parts[1].slice(0, 2);
  if (isNaN(hours)) return str;
  const ampm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12;
  if (hours === 0) hours = 12;
  const padHours = hours < 10 ? `0${hours}` : `${hours}`;
  return `${padHours}:${minutes} ${ampm}`;
}

export function isValidEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  return /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(email.trim());
}

export function isValidPhone(phone: string | null | undefined): boolean {
  if (!phone) return false;
  const cleaned = phone.replace(/\D/g, '');
  return cleaned.length === 10;
}

// ─── Types ────────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  date_from?: string;
  date_to?: string;
  patients: {
    total: number;
    new_today: number;
    new_this_month: number;
    new_in_range?: number;
    returning_in_range?: number;
    unique_in_range?: number;
  };
  appointments: {
    today: number;
    upcoming: number;
    booked: number;
    confirmed: number;
    completed: number;
    cancelled: number;
    rescheduled: number;
    no_show: number;
    total: number;
    by_source: Record<string, number>;
  };
  doctors: { active: number };
  conversations: { total: number; today: number };
  escalations: { open: number; total: number; in_range?: number };
  admissions?: { in_range: number };
}

export interface Patient {
  id: number;
  patient_code: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  phone: string;
  whatsapp_number: string | null;
  email: string | null;
  city: string | null;
  blood_group: string | null;
  status: string;
  created_at: string;
}

export interface PatientListResponse {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  patients: Patient[];
}

export interface Appointment {
  id: number;
  booking_id: string;
  appointment_date: string;
  appointment_time: string;
  appointment_end_time?: string;
  duration_minutes?: number;
  status: string;
  booking_source: string;
  patient_reason: string | null;
  cancellation_reason: string | null;
  reschedule_reason?: string | null;
  created_at: string;
  cancelled_at?: string | null;
  rescheduled_at?: string | null;
  patient_id: number;
  patient_code: string;
  patient_name: string;
  patient_phone: string;
  doctor_id: number;
  doctor_name: string;
  specialization: string;
  department_id: number;
  department_name: string;
}

export interface AppointmentListResponse {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
  appointments: Appointment[];
}

export interface DateWiseAnalytics {
  date_from: string;
  date_to: string;
  appointments_by_date: {
    date: string;
    name: string;
    total: number;
    booked: number;
    confirmed: number;
    completed: number;
    cancelled: number;
    rescheduled: number;
    no_show: number;
  }[];
  booking_trend: { date: string; count: number }[];
  cancellation_trend: { date: string; count: number }[];
  reschedule_trend: { date: string; count: number }[];
  completion_trend: { date: string; count: number }[];
  new_patients_by_date: { date: string; count: number }[];
  doctor_analytics: {
    doctor_id: number;
    doctor_name: string;
    department_name: string;
    total: number;
    completed: number;
    booked: number;
    confirmed: number;
    cancelled: number;
    rescheduled: number;
    no_show: number;
  }[];
  department_analytics: {
    department_id: number;
    name: string;
    value: number;
    total: number;
    completed: number;
    pending: number;
    cancelled: number;
  }[];
  booking_source_analytics: {
    source: string;
    count: number;
  }[];
}

export interface DoctorDailyScheduleSlot {
  schedule_id: number;
  doctor_id: number;
  doctor_name: string;
  specialization: string;
  department_name: string;
  day_of_week: string;
  working_hours: string;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  total_slots: number;
  booked_slots: number;
  completed_slots: number;
  cancelled_slots: number;
  rescheduled_slots: number;
  no_show_slots: number;
  available_slots: number;
  slot_utilization_pct: number;
}

export interface DailyViewResponse {
  date: string;
  day_of_week: string;
  totals: {
    total: number;
    completed: number;
    pending: number;
    booked: number;
    confirmed: number;
    cancelled: number;
    rescheduled: number;
    no_show: number;
  };
  appointments: Appointment[];
  doctor_schedules: DoctorDailyScheduleSlot[];
}

export interface Doctor {
  id: number;
  doctor_code: string;
  display_name: string;
  first_name: string;
  last_name: string;
  specialization: string;
  qualification: string;
  experience_years: number;
  phone: string | null;
  email: string | null;
  consultation_fee: number;
  status: string;
  created_at: string;
  department_id: number;
  department_name: string;
  today_appts: number;
  total_appts: number;
}

export interface NewDoctorPayload {
  first_name: string;
  last_name: string;
  specialization: string;
  qualification: string;
  experience_years: number;
  phone?: string;
  email?: string;
  consultation_fee: number;
  department_id: number;
  username: string;
  password: string;
}

export interface Department {
  id: number;
  department_code: string;
  department_name: string;
  description: string | null;
  status: string;
  doctor_count: number;
  today_appts: number;
  total_appts: number;
}

export interface Conversation {
  id: number;
  conversation_code: string;
  whatsapp_number: string;
  language: string;
  current_intent: string | null;
  conversation_status: string;
  started_at: string;
  last_message_at: string;
  patient_name: string | null;
  patient_code: string | null;
  message_count: number;
}

export interface Escalation {
  id: number;
  escalation_reason: string;
  patient_question: string | null;
  status: string;
  resolution_notes: string | null;
  created_at: string;
  resolved_at: string | null;
  conversation_code: string;
  whatsapp_number: string;
  patient_name: string | null;
  patient_code: string | null;
}

export interface TrendPoint {
  name: string;
  date: string;
  total: number;
  booked: number;
  completed: number;
  cancelled: number;
}

export interface IntentBreakdownItem {
  intent: string;
  count: number;
}

// ─── HTTP Helpers ─────────────────────────────────────────────────────────────

const BASE_URL = 'http://localhost:8000';

function getAuthHeaders(): Record<string, string> {
  try {
    const userStr = sessionStorage.getItem('meridian_user');
    if (userStr) {
      const user = JSON.parse(userStr);
      if (user && user.token) {
        return { 'Authorization': `Bearer ${user.token}` };
      }
    }
  } catch (e) {
    console.error('Error parsing meridian_user for auth headers:', e);
  }
  return {};
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T | null> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    const headers = {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
      ...(options?.headers || {}),
    };
    const res = await fetch(`${BASE_URL}${path}`, {
      signal: controller.signal,
      ...options,
      headers,
    });
    clearTimeout(timer);
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const errorMsg = data?.detail || `Server error (${res.status})`;
      console.warn(`[Dashboard API] ${path} returned ${res.status}:`, errorMsg);
      return { success: false, error: errorMsg } as unknown as T;
    }
    return data as T;
  } catch (err) {
    console.error(`[Dashboard API] ${path} failed:`, err);
    return null;
  }
}

// ─── Summary ──────────────────────────────────────────────────────────────────

export async function fetchDashboardSummary(params?: {
  date_from?: string;
  date_to?: string;
  department?: string;
  doctor_id?: number;
  booking_source?: string;
}): Promise<DashboardSummary> {
  const qs = new URLSearchParams();
  if (params?.date_from) qs.set('date_from', params.date_from);
  if (params?.date_to) qs.set('date_to', params.date_to);
  if (params?.department) qs.set('department', params.department);
  if (params?.doctor_id) qs.set('doctor_id', String(params.doctor_id));
  if (params?.booking_source) qs.set('booking_source', params.booking_source);

  const query = qs.toString() ? `?${qs.toString()}` : '';
  const data = await apiFetch<DashboardSummary>(`/api/dashboard/summary${query}`);
  return data ?? {
    patients: { total: 0, new_today: 0, new_this_month: 0, new_in_range: 0, returning_in_range: 0, unique_in_range: 0 },
    appointments: { today: 0, upcoming: 0, booked: 0, confirmed: 0, completed: 0, cancelled: 0, rescheduled: 0, no_show: 0, total: 0, by_source: {} },
    doctors: { active: 0 },
    conversations: { total: 0, today: 0 },
    escalations: { open: 0, total: 0, in_range: 0 },
    admissions: { in_range: 0 },
  };
}

// ─── Patients ─────────────────────────────────────────────────────────────────

export async function fetchPatients(params?: {
  search?: string;
  status?: string;
  page?: number;
  per_page?: number;
}): Promise<PatientListResponse> {
  const qs = new URLSearchParams();
  if (params?.search) qs.set('search', params.search);
  if (params?.status) qs.set('status', params.status);
  if (params?.page) qs.set('page', String(params.page));
  if (params?.per_page) qs.set('per_page', String(params.per_page));

  const data = await apiFetch<PatientListResponse>(`/api/dashboard/patients?${qs}`);
  return data ?? { total: 0, page: 1, per_page: 20, total_pages: 1, patients: [] };
}

export async function fetchPatientDetail(patientId: number) {
  return apiFetch<{
    patient: Record<string, unknown>;
    appointments: Appointment[];
    upcoming_appointments?: Appointment[];
    previous_appointments?: Appointment[];
    conversations: Conversation[];
    pre_admissions?: PreAdmissionItem[];
  }>(`/api/dashboard/patients/${patientId}`);
}

export async function updatePatient(patientId: number, data: Record<string, unknown>): Promise<boolean> {
  const result = await apiFetch<{ success: boolean }>(`/api/dashboard/patients/${patientId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  return result?.success ?? false;
}

// ─── Appointments ─────────────────────────────────────────────────────────────

export async function fetchAppointments(params?: {
  search?: string;
  status?: string;
  department?: string;
  doctor_id?: number;
  booking_source?: string;
  date_from?: string;
  date_to?: string;
  date_type?: 'appointment_date' | 'created_at';
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  page?: number;
  per_page?: number;
}): Promise<AppointmentListResponse> {
  const qs = new URLSearchParams();
  if (params?.search) qs.set('search', params.search);
  if (params?.status) qs.set('status', params.status);
  if (params?.department) qs.set('department', params.department);
  if (params?.doctor_id) qs.set('doctor_id', String(params.doctor_id));
  if (params?.booking_source) qs.set('booking_source', params.booking_source);
  if (params?.date_from) qs.set('date_from', params.date_from);
  if (params?.date_to) qs.set('date_to', params.date_to);
  if (params?.date_type) qs.set('date_type', params.date_type);
  if (params?.sort_by) qs.set('sort_by', params.sort_by);
  if (params?.sort_order) qs.set('sort_order', params.sort_order);
  if (params?.page) qs.set('page', String(params.page));
  if (params?.per_page) qs.set('per_page', String(params.per_page));

  const data = await apiFetch<AppointmentListResponse>(`/api/dashboard/appointments?${qs}`);
  return data ?? { total: 0, page: 1, per_page: 20, total_pages: 1, appointments: [] };
}

export async function fetchDateWiseAnalytics(params?: {
  date_from?: string;
  date_to?: string;
  doctor_id?: number;
  department?: string;
  booking_source?: string;
}): Promise<DateWiseAnalytics> {
  const qs = new URLSearchParams();
  if (params?.date_from) qs.set('date_from', params.date_from);
  if (params?.date_to) qs.set('date_to', params.date_to);
  if (params?.doctor_id) qs.set('doctor_id', String(params.doctor_id));
  if (params?.department) qs.set('department', params.department);
  if (params?.booking_source) qs.set('booking_source', params.booking_source);

  const query = qs.toString() ? `?${qs.toString()}` : '';
  const data = await apiFetch<DateWiseAnalytics>(`/api/dashboard/analytics/date-wise${query}`);
  return data ?? {
    date_from: '',
    date_to: '',
    appointments_by_date: [],
    booking_trend: [],
    cancellation_trend: [],
    reschedule_trend: [],
    completion_trend: [],
    new_patients_by_date: [],
    doctor_analytics: [],
    department_analytics: [],
    booking_source_analytics: [],
  };
}

export async function fetchDailyView(params?: {
  date?: string;
  doctor_id?: number;
  department?: string;
}): Promise<DailyViewResponse> {
  const qs = new URLSearchParams();
  if (params?.date) qs.set('date', params.date);
  if (params?.doctor_id) qs.set('doctor_id', String(params.doctor_id));
  if (params?.department) qs.set('department', params.department);

  const query = qs.toString() ? `?${qs.toString()}` : '';
  const data = await apiFetch<DailyViewResponse>(`/api/dashboard/daily-view${query}`);
  return data ?? {
    date: '',
    day_of_week: '',
    totals: { total: 0, completed: 0, pending: 0, booked: 0, confirmed: 0, cancelled: 0, rescheduled: 0, no_show: 0 },
    appointments: [],
    doctor_schedules: [],
  };
}

export async function updateAppointmentStatus(bookingId: string, status: string, reason?: string): Promise<boolean> {
  const data = await apiFetch<{ success: boolean }>(`/api/dashboard/appointments/${bookingId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status, reason }),
  });
  return data?.success ?? false;
}

// ─── Doctors ──────────────────────────────────────────────────────────────────

export interface DoctorSchedule {
  id: number;
  doctor_id: number;
  doctor_name: string;
  specialization: string;
  department_name: string;
  day_of_week: string;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  status: string;
  created_at?: string;
}

export async function fetchDoctors(params?: {
  search?: string;
  department?: string;
  status?: string;
}): Promise<{ doctors: Doctor[]; total: number }> {
  const qs = new URLSearchParams();
  if (params?.search) qs.set('search', params.search);
  if (params?.department) qs.set('department', params.department);
  if (params?.status) qs.set('status', params.status);

  const data = await apiFetch<{ doctors: Doctor[]; total: number }>(`/api/dashboard/doctors?${qs}`);
  return data ?? { doctors: [], total: 0 };
}

export async function updateDoctorStatus(doctorId: number, status: string): Promise<boolean> {
  const data = await apiFetch<{ success: boolean }>(`/api/dashboard/doctors/${doctorId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
  return data?.success ?? false;
}

export async function updateDoctorByAdmin(doctorId: number, data: Record<string, unknown>): Promise<{ success: boolean; message?: string; error?: string }> {
  const res = await apiFetch<{ success: boolean; message?: string; error?: string }>(`/api/dashboard/doctors/${doctorId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  return res ?? { success: false, error: 'Request failed' };
}

export async function updateDoctorSelfProfile(data: Record<string, unknown>): Promise<{ success: boolean; message?: string; error?: string }> {
  const res = await apiFetch<{ success: boolean; message?: string; error?: string }>('/api/dashboard/doctors/me/profile', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
  return res ?? { success: false, error: 'Request failed' };
}

export async function fetchSchedules(doctorId?: number): Promise<{ schedules: DoctorSchedule[]; total: number }> {
  const qs = doctorId ? `?doctor_id=${doctorId}` : '';
  const data = await apiFetch<{ schedules: DoctorSchedule[]; total: number }>(`/api/dashboard/schedules${qs}`);
  return data ?? { schedules: [], total: 0 };
}

export async function createSchedule(payload: {
  doctor_id: number;
  day_of_week: string;
  start_time: string;
  end_time: string;
  slot_duration_minutes?: number;
  status?: string;
}): Promise<{ success: boolean; schedule_id?: number; message?: string; error?: string }> {
  const data = await apiFetch<{ success: boolean; schedule_id?: number; message?: string; error?: string }>('/api/dashboard/schedules', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return data ?? { success: false, error: 'Failed to create schedule' };
}

export async function deleteSchedule(scheduleId: number): Promise<boolean> {
  const data = await apiFetch<{ success: boolean }>(`/api/dashboard/schedules/${scheduleId}`, {
    method: 'DELETE',
  });
  return data?.success ?? false;
}

export async function requestDoctorOTP(identifier: string): Promise<{ success: boolean; message?: string; debug_otp?: string; error?: string }> {
  try {
    const response = await fetch('http://localhost:8000/api/auth/forgot-password/request-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier }),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'OTP Request failed' };
    return data;
  } catch {
    return { success: false, error: 'Server unreachable' };
  }
}

export async function resetDoctorPasswordWithOTP(identifier: string, otp: string, new_password: string): Promise<{ success: boolean; message?: string; error?: string }> {
  try {
    const response = await fetch('http://localhost:8000/api/auth/forgot-password/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ identifier, otp, new_password }),
    });
    const data = await response.json();
    if (!response.ok) return { success: false, error: data.detail || 'Password reset failed' };
    return data;
  } catch {
    return { success: false, error: 'Server unreachable' };
  }
}

export async function createDoctor(payload: NewDoctorPayload): Promise<{ success: boolean; doctor_id?: number; error?: string }> {
  const data = await apiFetch<{ success: boolean; doctor_id?: number; error?: string }>('/api/dashboard/doctors', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return data ?? { success: false, error: 'Request failed' };
}

// ─── Departments ──────────────────────────────────────────────────────────────

export async function fetchDepartments(): Promise<{ departments: Department[]; total: number }> {
  const data = await apiFetch<{ departments: Department[]; total: number }>('/api/dashboard/departments');
  return data ?? { departments: [], total: 0 };
}

// ─── Conversations ────────────────────────────────────────────────────────────

export async function fetchConversations(params?: {
  status?: string;
  intent?: string;
  language?: string;
  page?: number;
  per_page?: number;
}): Promise<{ total: number; page: number; per_page: number; total_pages: number; conversations: Conversation[] }> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.intent) qs.set('intent', params.intent);
  if (params?.language) qs.set('language', params.language);
  if (params?.page) qs.set('page', String(params.page));
  if (params?.per_page) qs.set('per_page', String(params.per_page));

  const data = await apiFetch<{ total: number; page: number; per_page: number; total_pages: number; conversations: Conversation[] }>(
    `/api/dashboard/conversations?${qs}`
  );
  return data ?? { total: 0, page: 1, per_page: 20, total_pages: 1, conversations: [] };
}

export async function fetchConversationMessages(convId: number) {
  return apiFetch<{ conversation_id: number; messages: unknown[] }>(`/api/dashboard/conversations/${convId}/messages`);
}

// ─── Escalations ──────────────────────────────────────────────────────────────

export async function fetchEscalations(params?: {
  status?: string;
  page?: number;
  per_page?: number;
}): Promise<{ total: number; page: number; per_page: number; total_pages: number; escalations: Escalation[] }> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.page) qs.set('page', String(params.page));
  if (params?.per_page) qs.set('per_page', String(params.per_page));

  const data = await apiFetch<{ total: number; page: number; per_page: number; total_pages: number; escalations: Escalation[] }>(
    `/api/dashboard/escalations?${qs}`
  );
  return data ?? { total: 0, page: 1, per_page: 20, total_pages: 1, escalations: [] };
}

export async function updateEscalationStatus(
  escalationId: number,
  status: string,
  resolutionNotes?: string
): Promise<boolean> {
  const data = await apiFetch<{ success: boolean }>(`/api/dashboard/escalations/${escalationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, resolution_notes: resolutionNotes }),
  });
  return data?.success ?? false;
}

// ─── Charts ───────────────────────────────────────────────────────────────────

export async function fetchAppointmentTrend(days = 7): Promise<{ trend: TrendPoint[] }> {
  const data = await apiFetch<{ trend: TrendPoint[] }>(`/api/dashboard/charts/appointment-trend?days=${days}`);
  return data ?? { trend: [] };
}

export async function fetchIntentBreakdown(days = 30): Promise<{ intent_breakdown: IntentBreakdownItem[] }> {
  const data = await apiFetch<{ intent_breakdown: IntentBreakdownItem[] }>(
    `/api/dashboard/charts/intent-breakdown?days=${days}`
  );
  return data ?? { intent_breakdown: [] };
}

export async function fetchPatientRegistrationTrend(months = 6): Promise<{ trend: { month: string; patients: number }[] }> {
  const data = await apiFetch<{ trend: { month: string; patients: number }[] }>(
    `/api/dashboard/charts/patient-registration-trend?months=${months}`
  );
  return data ?? { trend: [] };
}

export async function fetchDepartmentAppointments(): Promise<{ departments: { name: string; value: number }[] }> {
  const data = await apiFetch<{ departments: { name: string; value: number }[] }>(
    '/api/dashboard/charts/department-appointments'
  );
  return data ?? { departments: [] };
}

// ─── Pre-Admissions ───────────────────────────────────────────────────────────

export interface PreAdmissionItem {
  id: number;
  pre_admission_code: string;
  patient_id: number;
  patient_code: string;
  patient_name: string;
  patient_phone: string;
  doctor_id: number;
  doctor_name: string;
  department_id: number;
  department_name: string;
  appointment_id?: number | null;
  booking_id?: string | null;
  expected_admission_date: string;
  expected_checkin_time?: string | null;
  admission_type: string;
  status: string;
  pending_documents?: string | null;
  submitted_documents?: string | null;
  instructions?: string | null;
  remarks?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  notification_status?: string | null;
}

export interface NewPreAdmissionPayload {
  patient_id: number;
  doctor_id: number;
  department_id: number;
  admission_type: string;
  expected_admission_date: string;
  expected_checkin_time?: string;
  instructions?: string;
  remarks?: string;
  pending_documents?: string;
}

export async function fetchPreAdmissions(params?: {
  search?: string;
  status?: string;
  admission_type?: string;
  admission_date?: string;
  patient_id?: number;
}): Promise<{ pre_admissions: PreAdmissionItem[] }> {
  const qs = new URLSearchParams();
  if (params?.search) qs.set('search', params.search);
  if (params?.status) qs.set('status', params.status);
  if (params?.admission_type) qs.set('admission_type', params.admission_type);
  if (params?.admission_date) qs.set('admission_date', params.admission_date);
  if (params?.patient_id) qs.set('patient_id', String(params.patient_id));

  const data = await apiFetch<{ pre_admissions: PreAdmissionItem[] }>(`/api/dashboard/pre-admissions?${qs}`);
  return data ?? { pre_admissions: [] };
}

export async function createPreAdmission(payload: NewPreAdmissionPayload): Promise<{
  success: boolean;
  pre_admission_id?: number;
  pre_admission_code?: string;
  error?: string;
}> {
  const data = await apiFetch<{
    success: boolean;
    pre_admission_id?: number;
    pre_admission_code?: string;
    error?: string;
  }>('/api/dashboard/pre-admissions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return data ?? { success: false, error: 'Failed to create pre-admission' };
}

export async function updatePreAdmissionStatus(
  id: number,
  payload: { status?: string; submitted_documents?: string; pending_documents?: string; remarks?: string }
): Promise<{ success: boolean; error?: string }> {
  const data = await apiFetch<{ success: boolean; error?: string }>(`/api/dashboard/pre-admissions/${id}/status`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  return data ?? { success: false, error: 'Update failed' };
}

export async function sendPreAdmissionNotification(id: number): Promise<{ success: boolean; status?: string; whatsapp_number?: string; phone?: string; error?: string }> {
  const data = await apiFetch<{ success: boolean; status?: string; whatsapp_number?: string; phone?: string; error?: string }>(`/api/dashboard/pre-admissions/${id}/notify`, {
    method: 'POST',
  });
  return data ?? { success: false, error: 'Notification failed' };
}

export async function fetchPreAdmissionConversation(id: number): Promise<{
  success: boolean;
  pre_admission_id: number;
  patient_name: string;
  conversation?: { id: number; conversation_code: string; language: string; current_intent: string; status: string } | null;
  messages: { id: number; sender_type: string; message_text: string; intent?: string; language?: string; timestamp?: string }[];
  error?: string;
}> {
  const data = await apiFetch<any>(`/api/dashboard/pre-admissions/${id}/conversation`);
  return data ?? { success: false, pre_admission_id: id, patient_name: '', messages: [] };
}
