import { patients, Patient } from '../data/patients';
import { doctors, Doctor } from '../data/doctors';
import { appointments, Appointment } from '../data/appointments';
import { aiConversations, AIConversation, preAdmissions, PreAdmission } from '../data/aiConversations';
import { departments, Department } from '../data/departments';

// Simulate async API calls
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/* ── Patient Service ── */
export const mockPatientService = {
  getAll: async (): Promise<Patient[]> => { await delay(100); return [...patients]; },
  getById: async (id: string): Promise<Patient | undefined> => { await delay(50); return patients.find(p => p.id === id); },
  getByDoctor: async (doctorLoginId: string): Promise<Patient[]> => { await delay(100); return patients.filter(p => p.assignedDoctorId === doctorLoginId); },
  search: async (query: string): Promise<Patient[]> => {
    await delay(100);
    const q = query.toLowerCase();
    return patients.filter(p => p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q) || p.department.toLowerCase().includes(q));
  },
};

/* ── Doctor Service ── */
export const mockDoctorService = {
  getAll: async (): Promise<Doctor[]> => { await delay(100); return [...doctors]; },
  getById: async (id: string): Promise<Doctor | undefined> => { await delay(50); return doctors.find(d => d.id === id); },
  getByLoginId: async (loginId: string): Promise<Doctor | undefined> => { await delay(50); return doctors.find(d => d.loginId === loginId); },
};

/* ── Appointment Service ── */
export const mockAppointmentService = {
  getAll: async (): Promise<Appointment[]> => { await delay(100); return [...appointments]; },
  getByDoctor: async (doctorId: string): Promise<Appointment[]> => { await delay(100); return appointments.filter(a => a.doctorId === doctorId); },
  getByPatient: async (patientId: string): Promise<Appointment[]> => { await delay(100); return appointments.filter(a => a.patientId === patientId); },
  getByDate: async (date: string): Promise<Appointment[]> => { await delay(100); return appointments.filter(a => a.date === date); },
  updateStatus: async (id: string, status: Appointment['status']): Promise<Appointment | undefined> => {
    await delay(200);
    const apt = appointments.find(a => a.id === id);
    if (apt) apt.status = status;
    return apt;
  },
};

/* ── AI Conversation Service ── */
export const mockAIService = {
  getConversations: async (): Promise<AIConversation[]> => { await delay(100); return [...aiConversations]; },
  getById: async (id: string): Promise<AIConversation | undefined> => { await delay(50); return aiConversations.find(c => c.id === id); },
  getByPatient: async (patientId: string): Promise<AIConversation[]> => { await delay(100); return aiConversations.filter(c => c.patientId === patientId); },
  getStats: async () => {
    await delay(50);
    return {
      totalToday: 143,
      appointmentsBooked: 32,
      queriesResolved: 91,
      escalations: 8,
      languages: ['English', 'Tamil', 'Hindi', 'Telugu'],
      channels: ['WhatsApp', 'Voice'],
    };
  },
};

/* ── Department Service ── */
export const mockDepartmentService = {
  getAll: async (): Promise<Department[]> => { await delay(100); return [...departments]; },
  getById: async (id: string): Promise<Department | undefined> => { await delay(50); return departments.find(d => d.id === id); },
};

/* ── Pre-Admission Service ── */
export const mockPreAdmissionService = {
  getAll: async (): Promise<PreAdmission[]> => { await delay(100); return [...preAdmissions]; },
  getByPatient: async (patientId: string): Promise<PreAdmission[]> => { await delay(100); return preAdmissions.filter(p => p.patientId === patientId); },
};

/* ── WhatsApp Service (placeholder) ── */
export const mockWhatsAppService = {
  sendMessage: async (_to: string, _message: string): Promise<{ success: boolean }> => { await delay(300); return { success: true }; },
  getStatus: async (): Promise<{ connected: boolean }> => { await delay(50); return { connected: true }; },
};

/* ── Voice Service (placeholder) ── */
export const mockVoiceService = {
  startCall: async (): Promise<{ callId: string }> => { await delay(200); return { callId: 'CALL-' + Date.now() }; },
  endCall: async (_callId: string): Promise<{ success: boolean }> => { await delay(100); return { success: true }; },
  getTranscript: async (_callId: string): Promise<string[]> => { await delay(100); return ['Transcript line 1', 'Transcript line 2']; },
};

/* ── LLM Service (placeholder for future integration) ── */
export const mockLLMService = {
  generateResponse: async (prompt: string): Promise<string> => {
    await delay(500);
    return `[Mock AI Response] Based on your query: "${prompt.substring(0, 50)}..." — This is a simulated response from the Meridian Hospital AI assistant.`;
  },
};

/* ── Notification Service (placeholder) ── */
export const mockNotificationService = {
  sendSMS: async (_phone: string, _message: string): Promise<boolean> => { await delay(200); return true; },
  sendEmail: async (_email: string, _subject: string, _body: string): Promise<boolean> => { await delay(200); return true; },
};
