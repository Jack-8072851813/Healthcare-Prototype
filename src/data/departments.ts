export interface Department {
  id: string;
  name: string;
  doctorsCount: number;
  todayAppointments: number;
  availability: 'Available' | 'Limited' | 'Full';
  icon: string;
  headDoctor: string;
  description: string;
}

export const departments: Department[] = [
  { id: 'DEP01', name: 'Cardiology', doctorsCount: 3, todayAppointments: 14, availability: 'Available', icon: 'Heart', headDoctor: 'Dr. Surendhar G', description: 'Comprehensive cardiac care including interventional procedures' },
  { id: 'DEP02', name: 'Oncology', doctorsCount: 2, todayAppointments: 8, availability: 'Available', icon: 'Shield', headDoctor: 'Dr. Vijay Anand', description: 'Cancer care including chemotherapy and radiation therapy' },
  { id: 'DEP03', name: 'Critical Care', doctorsCount: 4, todayAppointments: 6, availability: 'Limited', icon: 'Activity', headDoctor: 'Dr. Kumar R', description: '24/7 intensive care and critical care management' },
  { id: 'DEP04', name: 'Pediatrics', doctorsCount: 2, todayAppointments: 12, availability: 'Available', icon: 'Baby', headDoctor: 'Dr. Arthi Latha T', description: 'Complete child healthcare from newborn to adolescent' },
  { id: 'DEP05', name: 'Orthopaedic & Sports Surgery', doctorsCount: 3, todayAppointments: 10, availability: 'Available', icon: 'Bone', headDoctor: 'Dr. Dinesh Choudary', description: 'Joint replacement, sports medicine, and trauma care' },
  { id: 'DEP06', name: 'Radiology', doctorsCount: 2, todayAppointments: 18, availability: 'Available', icon: 'ScanLine', headDoctor: 'Dr. Priya M', description: 'Advanced diagnostic imaging including MRI, CT, and ultrasound' },
  { id: 'DEP07', name: 'Vascular Surgery', doctorsCount: 1, todayAppointments: 4, availability: 'Available', icon: 'GitBranch', headDoctor: 'Dr. Senthil V', description: 'Vascular and endovascular surgical procedures' },
  { id: 'DEP08', name: 'Nephrology', doctorsCount: 2, todayAppointments: 7, availability: 'Available', icon: 'Droplets', headDoctor: 'Dr. Sathiyan', description: 'Kidney disease management and dialysis services' },
  { id: 'DEP09', name: 'Neurology', doctorsCount: 2, todayAppointments: 8, availability: 'Available', icon: 'Brain', headDoctor: 'Dr. Neeraj E', description: 'Brain, spine, and nervous system disorder management' },
  { id: 'DEP10', name: 'Obstetrics & Gynaecology', doctorsCount: 3, todayAppointments: 11, availability: 'Available', icon: 'HeartPulse', headDoctor: 'Dr. Preethi S', description: 'Women\'s health, maternity care, and gynecological services' },
  { id: 'DEP11', name: 'Emergency & Trauma Care', doctorsCount: 5, todayAppointments: 15, availability: 'Available', icon: 'Siren', headDoctor: 'Dr. Anand K', description: '24/7 emergency and trauma services' },
  { id: 'DEP12', name: 'Urology', doctorsCount: 2, todayAppointments: 6, availability: 'Available', icon: 'Stethoscope', headDoctor: 'Dr. Ganesh B', description: 'Urinary tract and male reproductive system care' },
  { id: 'DEP13', name: 'Dermatology', doctorsCount: 2, todayAppointments: 9, availability: 'Available', icon: 'Sparkles', headDoctor: 'Dr. Mayuri', description: 'Skin, hair, and nail disease diagnosis and treatment' },
  { id: 'DEP14', name: 'Pulmonology', doctorsCount: 2, todayAppointments: 7, availability: 'Available', icon: 'Wind', headDoctor: 'Dr. Ramesh Kumar', description: 'Respiratory disease diagnosis and management' },
  { id: 'DEP15', name: 'Diabetology', doctorsCount: 2, todayAppointments: 13, availability: 'Available', icon: 'Pill', headDoctor: 'Dr. Srinivasan K', description: 'Comprehensive diabetes management and care' },
  { id: 'DEP16', name: 'Neuro Surgery', doctorsCount: 1, todayAppointments: 3, availability: 'Limited', icon: 'Zap', headDoctor: 'Dr. Venkat N', description: 'Brain and spinal surgical procedures' },
  { id: 'DEP17', name: 'Surgical Gastroenterology', doctorsCount: 2, todayAppointments: 5, availability: 'Available', icon: 'Slice', headDoctor: 'Dr. Bharath G', description: 'Gastrointestinal surgical procedures' },
  { id: 'DEP18', name: 'Plastic Surgery', doctorsCount: 1, todayAppointments: 4, availability: 'Available', icon: 'Scissors', headDoctor: 'Dr. Aravind P', description: 'Reconstructive and cosmetic surgical procedures' },
  { id: 'DEP19', name: 'Dental & OFMS', doctorsCount: 2, todayAppointments: 8, availability: 'Available', icon: 'SmilePlus', headDoctor: 'Dr. Lakshmi D', description: 'Dental care and oral & maxillofacial surgery' },
  { id: 'DEP20', name: 'General Medicine', doctorsCount: 4, todayAppointments: 16, availability: 'Available', icon: 'Clipboard', headDoctor: 'Dr. Abdul Rahman S', description: 'Primary healthcare and general medical care' },
  { id: 'DEP21', name: 'Anaesthesiology', doctorsCount: 3, todayAppointments: 10, availability: 'Available', icon: 'Syringe', headDoctor: 'Dr. Karthik A', description: 'Perioperative care and pain management' },
];
