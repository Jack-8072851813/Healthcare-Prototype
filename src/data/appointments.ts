export interface Appointment {
  id: string;
  patientId: string;
  patientName: string;
  doctorId: string;
  doctorName: string;
  department: string;
  date: string;
  time: string;
  type: 'Consultation' | 'Follow-up' | 'Emergency' | 'Procedure' | 'Telemedicine';
  status: 'Confirmed' | 'Pending' | 'Completed' | 'Cancelled';
  notes?: string;
}

export const appointments: Appointment[] = [
  { id: 'APT001', patientId: 'P1001', patientName: 'Raj Kumar', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-27', time: '09:00 AM', type: 'Consultation', status: 'Confirmed' },
  { id: 'APT002', patientId: 'P1005', patientName: 'Suresh Babu', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-27', time: '10:00 AM', type: 'Follow-up', status: 'Confirmed' },
  { id: 'APT003', patientId: 'P1003', patientName: 'Arun Kumar', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-27', time: '11:00 AM', type: 'Consultation', status: 'Completed' },
  { id: 'APT004', patientId: 'P1004', patientName: 'Meena Devi', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-27', time: '12:00 PM', type: 'Follow-up', status: 'Pending' },
  { id: 'APT005', patientId: 'P1015', patientName: 'Ramesh Krishnan', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-27', time: '02:00 PM', type: 'Consultation', status: 'Confirmed' },
  { id: 'APT006', patientId: 'P1016', patientName: 'Deepa Sundar', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-27', time: '02:30 PM', type: 'Follow-up', status: 'Confirmed' },
  { id: 'APT007', patientId: 'P1001', patientName: 'Raj Kumar', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-27', time: '03:00 PM', type: 'Procedure', status: 'Pending' },
  { id: 'APT008', patientId: 'P1005', patientName: 'Suresh Babu', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-27', time: '03:30 PM', type: 'Telemedicine', status: 'Confirmed' },
  { id: 'APT009', patientId: 'P1007', patientName: 'Vignesh Kumar', doctorId: 'doc2', doctorName: 'Dr. Dinesh Choudary', department: 'Orthopaedics', date: '2026-08-27', time: '10:00 AM', type: 'Consultation', status: 'Confirmed' },
  { id: 'APT010', patientId: 'P1014', patientName: 'Sangeetha M', doctorId: 'doc2', doctorName: 'Dr. Dinesh Choudary', department: 'Orthopaedics', date: '2026-08-27', time: '11:00 AM', type: 'Follow-up', status: 'Confirmed' },
  { id: 'APT011', patientId: 'P1017', patientName: 'Gopal Krishnan', doctorId: 'doc2', doctorName: 'Dr. Dinesh Choudary', department: 'Orthopaedics', date: '2026-08-27', time: '11:30 AM', type: 'Consultation', status: 'Pending' },
  { id: 'APT012', patientId: 'P1007', patientName: 'Vignesh Kumar', doctorId: 'doc2', doctorName: 'Dr. Dinesh Choudary', department: 'Orthopaedics', date: '2026-08-27', time: '02:00 PM', type: 'Procedure', status: 'Confirmed' },
  { id: 'APT013', patientId: 'P1014', patientName: 'Sangeetha M', doctorId: 'doc2', doctorName: 'Dr. Dinesh Choudary', department: 'Orthopaedics', date: '2026-08-27', time: '03:00 PM', type: 'Follow-up', status: 'Confirmed' },
  { id: 'APT014', patientId: 'P1017', patientName: 'Gopal Krishnan', doctorId: 'doc2', doctorName: 'Dr. Dinesh Choudary', department: 'Orthopaedics', date: '2026-08-27', time: '04:00 PM', type: 'Consultation', status: 'Pending' },
  { id: 'APT015', patientId: 'P1002', patientName: 'Priya Sharma', doctorId: 'doc-ped1', doctorName: 'Dr. Arthi Latha T', department: 'Pediatrics', date: '2026-08-27', time: '09:30 AM', type: 'Follow-up', status: 'Confirmed' },
  { id: 'APT016', patientId: 'P1006', patientName: 'Kavya Raj', doctorId: 'doc-derm1', doctorName: 'Dr. Mayuri', department: 'Dermatology', date: '2026-08-27', time: '10:30 AM', type: 'Consultation', status: 'Confirmed' },
  { id: 'APT017', patientId: 'P1008', patientName: 'Lakshmi', doctorId: 'doc-neph1', doctorName: 'Dr. Sathiyan', department: 'Nephrology', date: '2026-08-27', time: '09:00 AM', type: 'Follow-up', status: 'Confirmed' },
  { id: 'APT018', patientId: 'P1009', patientName: 'Karthik Rajan', doctorId: 'doc-pulm1', doctorName: 'Dr. Ramesh Kumar', department: 'Pulmonology', date: '2026-08-27', time: '11:00 AM', type: 'Consultation', status: 'Pending' },
  { id: 'APT019', patientId: 'P1010', patientName: 'Divya Lakshmi', doctorId: 'doc-obg1', doctorName: 'Dr. Preethi S', department: 'Obstetrics & Gynaecology', date: '2026-08-27', time: '09:00 AM', type: 'Consultation', status: 'Confirmed' },
  { id: 'APT020', patientId: 'P1012', patientName: 'Anitha Kumari', doctorId: 'doc-onco1', doctorName: 'Dr. Vijay Anand', department: 'Oncology', date: '2026-08-27', time: '10:00 AM', type: 'Follow-up', status: 'Confirmed' },
  // Past appointments
  { id: 'APT021', patientId: 'P1001', patientName: 'Raj Kumar', doctorId: 'doc1', doctorName: 'Dr. Surendhar G', department: 'Cardiology', date: '2026-08-20', time: '09:00 AM', type: 'Follow-up', status: 'Completed' },
  { id: 'APT022', patientId: 'P1005', patientName: 'Suresh Babu', doctorId: 'doc-card2', doctorName: 'Dr. G. Shanthosh', department: 'Cardiology', date: '2026-08-19', time: '02:00 PM', type: 'Consultation', status: 'Completed' },
  { id: 'APT023', patientId: 'P1007', patientName: 'Vignesh Kumar', doctorId: 'doc2', doctorName: 'Dr. Dinesh Choudary', department: 'Orthopaedics', date: '2026-08-23', time: '10:00 AM', type: 'Follow-up', status: 'Completed' },
  { id: 'APT024', patientId: 'P1003', patientName: 'Arun Kumar', doctorId: 'doc-neuro1', doctorName: 'Dr. Neeraj E', department: 'Neurology', date: '2026-08-22', time: '11:00 AM', type: 'Consultation', status: 'Completed' },
  { id: 'APT025', patientId: 'P1011', patientName: 'Venkatesh R', doctorId: 'doc-diab1', doctorName: 'Dr. Srinivasan K', department: 'Diabetology', date: '2026-08-17', time: '08:30 AM', type: 'Follow-up', status: 'Completed' },
  { id: 'APT026', patientId: 'P1013', patientName: 'Mohan Raj', doctorId: 'doc-uro1', doctorName: 'Dr. Ganesh B', department: 'Urology', date: '2026-08-28', time: '10:00 AM', type: 'Consultation', status: 'Confirmed' },
];
