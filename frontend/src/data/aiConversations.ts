export interface AIConversation {
  id: string;
  patientId: string;
  patientName: string;
  channel: 'WhatsApp' | 'Voice';
  language: 'English' | 'Tamil' | 'Hindi' | 'Telugu';
  intent: string;
  status: 'Completed' | 'Active' | 'Escalated' | 'Needs Doctor Confirmation';
  timestamp: string;
  messages: { sender: 'patient' | 'ai'; text: string; time: string }[];
}

export const aiConversations: AIConversation[] = [
  {
    id: 'CONV001',
    patientId: 'P1001',
    patientName: 'Raj Kumar',
    channel: 'WhatsApp',
    language: 'English',
    intent: 'Appointment Booking',
    status: 'Completed',
    timestamp: '2026-08-26 09:15 AM',
    messages: [
      { sender: 'patient', text: 'Hi, I want to book an appointment with a cardiologist tomorrow.', time: '09:15 AM' },
      { sender: 'ai', text: 'Good morning! Welcome to Meridian Hospital. Let me check the available cardiology appointments for tomorrow.', time: '09:15 AM' },
      { sender: 'ai', text: 'I found the following availability:\n\n🩺 Dr. Surendhar G — 10:00 AM\n🩺 Dr. G. Shanthosh — 2:00 PM\n\nWhich slot would you prefer?', time: '09:16 AM' },
      { sender: 'patient', text: 'I want 2 PM.', time: '09:16 AM' },
      { sender: 'ai', text: '✅ Your appointment has been confirmed!\n\n📋 Appointment Details:\n👤 Patient: Raj Kumar\n🩺 Doctor: Dr. G. Shanthosh\n📅 Date: 27-Aug-2026\n🕐 Time: 2:00 PM\n🏥 Department: Cardiology\n\nPlease arrive 15 minutes early. Thank you for choosing Meridian Hospital!', time: '09:17 AM' },
    ],
  },
  {
    id: 'CONV002',
    patientId: 'P1005',
    patientName: 'Suresh Babu',
    channel: 'WhatsApp',
    language: 'Tamil',
    intent: 'Appointment Booking',
    status: 'Completed',
    timestamp: '2026-08-26 10:30 AM',
    messages: [
      { sender: 'patient', text: 'வணக்கம், நாளைக்கு cardiology doctor appointment வேண்டும்.', time: '10:30 AM' },
      { sender: 'ai', text: 'வணக்கம்! Meridian Hospital-க்கு வரவேற்கிறோம். நாளைக்கான Cardiology appointment availability-ஐ பார்க்கிறேன்.', time: '10:30 AM' },
      { sender: 'ai', text: 'நாளைக்கு கிடைக்கும் நேரங்கள்:\n\n🩺 Dr. Surendhar G — காலை 10:00 மணி\n🩺 Dr. G. Shanthosh — மதியம் 2:00 மணி\n\nஎந்த நேரம் உங்களுக்கு வசதியாக இருக்கும்?', time: '10:31 AM' },
      { sender: 'patient', text: '2 மணிக்கு வேண்டும்.', time: '10:31 AM' },
      { sender: 'ai', text: '✅ உங்கள் appointment வெற்றிகரமாக பதிவு செய்யப்பட்டது!\n\n📋 Appointment விவரங்கள்:\n👤 நோயாளி: Suresh Babu\n🩺 மருத்துவர்: Dr. G. Shanthosh\n📅 தேதி: 27-Aug-2026\n🕐 நேரம்: மதியம் 2:00 மணி\n🏥 துறை: Cardiology\n\nதயவுசெய்து 15 நிமிடங்கள் முன்னதாக வாருங்கள். Meridian Hospital-ஐ தேர்ந்தெடுத்ததற்கு நன்றி!', time: '10:32 AM' },
    ],
  },
  {
    id: 'CONV003',
    patientId: 'P1007',
    patientName: 'Vignesh Kumar',
    channel: 'WhatsApp',
    language: 'English',
    intent: 'Appointment Rescheduling',
    status: 'Completed',
    timestamp: '2026-08-26 11:00 AM',
    messages: [
      { sender: 'patient', text: 'I need to reschedule my ortho appointment from tomorrow to next week.', time: '11:00 AM' },
      { sender: 'ai', text: 'I can help you with that, Vignesh. Let me look up your current appointment details.', time: '11:00 AM' },
      { sender: 'ai', text: 'I found your appointment:\n\n📋 Current Appointment:\n🩺 Dr. Dinesh Choudary\n📅 27-Aug-2026, 10:00 AM\n\nLet me check availability for next week. Which day works best?', time: '11:01 AM' },
      { sender: 'patient', text: 'Wednesday would be great.', time: '11:01 AM' },
      { sender: 'ai', text: '✅ Your appointment has been rescheduled!\n\n📋 Updated Appointment:\n🩺 Doctor: Dr. Dinesh Choudary\n📅 New Date: 03-Sep-2026 (Wednesday)\n🕐 Time: 10:00 AM\n🏥 Department: Orthopaedics\n\nYou will receive a confirmation SMS shortly.', time: '11:02 AM' },
    ],
  },
  {
    id: 'CONV004',
    patientId: 'P1004',
    patientName: 'Meena Devi',
    channel: 'Voice',
    language: 'English',
    intent: 'Medical Query',
    status: 'Needs Doctor Confirmation',
    timestamp: '2026-08-26 02:00 PM',
    messages: [
      { sender: 'patient', text: 'I want to meet my cardiologist tomorrow. I have been having chest pain since yesterday.', time: '02:00 PM' },
      { sender: 'ai', text: 'I understand you\'re experiencing chest pain. Let me prioritize this for you and check immediate availability.', time: '02:00 PM' },
      { sender: 'ai', text: 'I\'ve flagged this as urgent and sent a notification to Dr. Abdul Rahman S. Given the symptoms, would you like me to:\n\n1. Book an emergency consultation for today\n2. Connect you with our emergency helpline\n3. Schedule a priority appointment for tomorrow morning\n\n⚠️ If you are in severe pain, please visit our Emergency Department immediately or call 044 6666 9999.', time: '02:01 PM' },
      { sender: 'patient', text: 'Book for tomorrow morning please, the pain is mild.', time: '02:02 PM' },
      { sender: 'ai', text: 'I\'ve submitted a priority appointment request for tomorrow morning. This requires doctor confirmation due to the symptom description. You\'ll receive confirmation shortly.\n\n⚠️ If pain intensifies, please call our Emergency: 044 6666 9999', time: '02:03 PM' },
    ],
  },
  {
    id: 'CONV005',
    patientId: 'P1001',
    patientName: 'Raj Kumar',
    channel: 'WhatsApp',
    language: 'English',
    intent: 'Hospital Information',
    status: 'Completed',
    timestamp: '2026-08-26 08:30 AM',
    messages: [
      { sender: 'patient', text: 'What are the OPD timings at Meridian Hospital?', time: '08:30 AM' },
      { sender: 'ai', text: 'Good morning! Here are the OPD timings at Meridian Hospital, Kolathur:\n\n🕐 General OPD: 8:00 AM – 8:00 PM\n🕐 Specialist OPD: 9:00 AM – 5:00 PM\n🏥 Emergency: 24/7\n\n📞 For specific doctor availability, please call: 044 6666 9910\n\nIs there anything else I can help you with?', time: '08:31 AM' },
    ],
  },
  {
    id: 'CONV006',
    patientId: 'P1008',
    patientName: 'Lakshmi',
    channel: 'WhatsApp',
    language: 'English',
    intent: 'Appointment Status',
    status: 'Completed',
    timestamp: '2026-08-26 03:00 PM',
    messages: [
      { sender: 'patient', text: 'Can you check the status of my next appointment?', time: '03:00 PM' },
      { sender: 'ai', text: 'Hello Lakshmi! Let me look up your upcoming appointment details.', time: '03:00 PM' },
      { sender: 'ai', text: 'Here are your upcoming appointments:\n\n📋 Next Appointment:\n🩺 Doctor: Dr. Sathiyan\n📅 Date: 07-Sep-2026\n🕐 Time: 09:00 AM\n🏥 Department: Nephrology\n📍 Status: ✅ Confirmed\n\nWould you like to reschedule or need any other help?', time: '03:01 PM' },
    ],
  },
  {
    id: 'CONV007',
    patientId: 'P1006',
    patientName: 'Kavya Raj',
    channel: 'WhatsApp',
    language: 'English',
    intent: 'Department Information',
    status: 'Completed',
    timestamp: '2026-08-26 04:00 PM',
    messages: [
      { sender: 'patient', text: 'Do you have a dermatology department? What treatments are available?', time: '04:00 PM' },
      { sender: 'ai', text: 'Yes! Meridian Hospital has a well-equipped Dermatology Department.\n\n🏥 Services available:\n• Skin disease diagnosis & treatment\n• Cosmetic dermatology\n• Laser treatments\n• Hair & nail disorders\n• Allergy testing\n\n🩺 Lead Doctor: Dr. Mayuri\n🕐 OPD: 10:00 AM – 4:00 PM\n\nWould you like to book an appointment?', time: '04:01 PM' },
    ],
  },
  {
    id: 'CONV008',
    patientId: 'P1001',
    patientName: 'Raj Kumar',
    channel: 'WhatsApp',
    language: 'English',
    intent: 'Appointment Cancellation',
    status: 'Completed',
    timestamp: '2026-08-26 05:00 PM',
    messages: [
      { sender: 'patient', text: 'I need to cancel my appointment on 30th August.', time: '05:00 PM' },
      { sender: 'ai', text: 'I can help you with that, Raj Kumar. Let me look up your appointment on 30th August.', time: '05:00 PM' },
      { sender: 'ai', text: 'I found your appointment:\n\n📋 Appointment:\n🩺 Doctor: Dr. Surendhar G\n📅 Date: 30-Aug-2026\n🕐 Time: 09:00 AM\n\nAre you sure you want to cancel this appointment?', time: '05:01 PM' },
      { sender: 'patient', text: 'Yes, please cancel it.', time: '05:01 PM' },
      { sender: 'ai', text: '✅ Your appointment on 30-Aug-2026 has been cancelled.\n\nWould you like to reschedule for a different date? Our team is here to help.\n\nMeridian Hospital | Kolathur, Chennai', time: '05:02 PM' },
    ],
  },
];

export interface PreAdmission {
  id: string;
  patientId: string;
  patientName: string;
  admissionDate: string;
  department: string;
  doctor: string;
  documentsRequired: number;
  documentsSubmitted: number;
  followUpStatus: 'Pending' | 'Completed' | 'Overdue';
  admissionStatus: 'Scheduled' | 'Confirmed' | 'Cancelled';
  notes: string;
}

export const preAdmissions: PreAdmission[] = [
  { id: 'PRE001', patientId: 'P1001', patientName: 'Raj Kumar', admissionDate: '2026-08-30', department: 'Cardiology', doctor: 'Dr. Surendhar G', documentsRequired: 3, documentsSubmitted: 2, followUpStatus: 'Pending', admissionStatus: 'Scheduled', notes: 'Angioplasty procedure' },
  { id: 'PRE002', patientId: 'P1012', patientName: 'Anitha Kumari', admissionDate: '2026-08-28', department: 'Oncology', doctor: 'Dr. Vijay Anand', documentsRequired: 4, documentsSubmitted: 4, followUpStatus: 'Completed', admissionStatus: 'Confirmed', notes: 'Chemotherapy cycle 3' },
  { id: 'PRE003', patientId: 'P1007', patientName: 'Vignesh Kumar', admissionDate: '2026-09-01', department: 'Orthopaedics', doctor: 'Dr. Dinesh Choudary', documentsRequired: 3, documentsSubmitted: 1, followUpStatus: 'Pending', admissionStatus: 'Scheduled', notes: 'ACL reconstruction surgery' },
  { id: 'PRE004', patientId: 'P1005', patientName: 'Suresh Babu', admissionDate: '2026-09-02', department: 'Cardiology', doctor: 'Dr. G. Shanthosh', documentsRequired: 3, documentsSubmitted: 3, followUpStatus: 'Completed', admissionStatus: 'Confirmed', notes: 'Cardiac catheterization' },
  { id: 'PRE005', patientId: 'P1008', patientName: 'Lakshmi', admissionDate: '2026-09-03', department: 'Nephrology', doctor: 'Dr. Sathiyan', documentsRequired: 3, documentsSubmitted: 0, followUpStatus: 'Overdue', admissionStatus: 'Scheduled', notes: 'Dialysis fistula creation' },
  { id: 'PRE006', patientId: 'P1015', patientName: 'Ramesh Krishnan', admissionDate: '2026-09-05', department: 'Cardiology', doctor: 'Dr. Surendhar G', documentsRequired: 4, documentsSubmitted: 2, followUpStatus: 'Pending', admissionStatus: 'Scheduled', notes: 'Pacemaker implantation' },
  { id: 'PRE007', patientId: 'P1014', patientName: 'Sangeetha M', admissionDate: '2026-09-04', department: 'Orthopaedics', doctor: 'Dr. Dinesh Choudary', documentsRequired: 3, documentsSubmitted: 3, followUpStatus: 'Completed', admissionStatus: 'Confirmed', notes: 'Spinal decompression surgery' },
  { id: 'PRE008', patientId: 'P1003', patientName: 'Arun Kumar', admissionDate: '2026-09-06', department: 'Neurology', doctor: 'Dr. Neeraj E', documentsRequired: 3, documentsSubmitted: 1, followUpStatus: 'Pending', admissionStatus: 'Scheduled', notes: 'EEG monitoring' },
  { id: 'PRE009', patientId: 'P1010', patientName: 'Divya Lakshmi', admissionDate: '2026-09-08', department: 'Obstetrics & Gynaecology', doctor: 'Dr. Preethi S', documentsRequired: 4, documentsSubmitted: 3, followUpStatus: 'Pending', admissionStatus: 'Scheduled', notes: 'Planned delivery' },
  { id: 'PRE010', patientId: 'P1013', patientName: 'Mohan Raj', admissionDate: '2026-09-10', department: 'Urology', doctor: 'Dr. Ganesh B', documentsRequired: 3, documentsSubmitted: 2, followUpStatus: 'Pending', admissionStatus: 'Scheduled', notes: 'Lithotripsy procedure' },
  { id: 'PRE011', patientId: 'P1017', patientName: 'Gopal Krishnan', admissionDate: '2026-09-07', department: 'Orthopaedics', doctor: 'Dr. Dinesh Choudary', documentsRequired: 3, documentsSubmitted: 0, followUpStatus: 'Overdue', admissionStatus: 'Scheduled', notes: 'Total knee replacement' },
  { id: 'PRE012', patientId: 'P1011', patientName: 'Venkatesh R', admissionDate: '2026-09-12', department: 'Diabetology', doctor: 'Dr. Srinivasan K', documentsRequired: 3, documentsSubmitted: 3, followUpStatus: 'Completed', admissionStatus: 'Confirmed', notes: 'Diabetic foot care procedure' },
];
