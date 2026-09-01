import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  fetchPatientDetail, updatePatient, isValidEmail, isValidPhone, format12HourTime,
  type Appointment, type Conversation
} from '../../services/dashboardApi';
import {
  ArrowLeft, User, Phone, Mail, MapPin, Heart, AlertTriangle,
  Calendar, MessageSquare, Edit3, Save, X, CheckCircle
} from 'lucide-react';

interface PatientDetail {
  id: number;
  patient_code: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
  gender: string;
  phone: string;
  whatsapp_number: string | null;
  email: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  pincode: string | null;
  emergency_contact_name: string | null;
  emergency_contact_phone: string | null;
  blood_group: string | null;
  status: string;
  created_at: string;
  updated_at: string | null;
}

const PatientProfile: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  const [patient, setPatient] = useState<PatientDetail | null>(null);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Edit mode state
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');
  const [editData, setEditData] = useState<Partial<PatientDetail>>({});

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3500);
  };

  const isDoctor = user?.role === 'doctor';
  const backPath = location.pathname.startsWith('/doctor') ? '/doctor/patient-records' : '/admin/patients';
  const backLabel = isDoctor ? 'Back to Patient Records' : 'Back to Patients';

  const loadData = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError('');
    try {
      const data = await fetchPatientDetail(Number(id));
      if (!data) {
        setError('Patient not found or access denied.');
        return;
      }
      setPatient(data.patient as unknown as PatientDetail);
      setAppointments(data.appointments);
      setConversations(data.conversations);
    } catch {
      setError('Failed to load patient data.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleEditStart = () => {
    if (!patient) return;
    setEditData({ ...patient });
    setEditMode(true);
  };

  const handleEditCancel = () => {
    setEditMode(false);
    setEditData({});
  };

  const handleSave = async () => {
    if (!patient || !id) return;
    if (editData.email && !isValidEmail(String(editData.email))) {
      showToast('❌ Please enter a valid Email address (e.g. patient@example.com)');
      return;
    }
    if (editData.phone && !isValidPhone(String(editData.phone))) {
      showToast('❌ Phone number must contain exactly 10 digits (e.g. 9876543210)');
      return;
    }
    setSaving(true);
    try {
      const ok = await updatePatient(Number(id), editData);
      if (ok) {
        showToast('✓ Patient details updated successfully');
        setEditMode(false);
        loadData();
      } else {
        showToast('❌ Failed to update patient details');
      }
    } finally {
      setSaving(false);
    }
  };

  const field = (key: keyof PatientDetail, label: string, type: string = 'text') => {
    if (editMode) {
      return (
        <div className="info-row">
          <label>{label}</label>
          <input
            type={type}
            value={String(editData[key] ?? '')}
            onChange={e => setEditData(prev => ({ ...prev, [key]: e.target.value }))}
            style={{
              padding: '6px 10px',
              border: '1.5px solid var(--primary)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 13,
              fontFamily: 'inherit',
              background: 'var(--bg-primary)',
              width: '100%',
            }}
          />
        </div>
      );
    }
    const val = patient?.[key];
    return (
      <div className="info-row">
        <label>{label}</label>
        <span>{val ? String(val) : '—'}</span>
      </div>
    );
  };

  const selectField = (key: keyof PatientDetail, label: string, options: string[]) => {
    if (editMode) {
      return (
        <div className="info-row">
          <label>{label}</label>
          <select
            value={String(editData[key] ?? '')}
            onChange={e => setEditData(prev => ({ ...prev, [key]: e.target.value }))}
            style={{
              padding: '6px 10px',
              border: '1.5px solid var(--primary)',
              borderRadius: 'var(--radius-sm)',
              fontSize: 13,
              fontFamily: 'inherit',
              background: 'var(--bg-primary)',
            }}
          >
            <option value="">— Select —</option>
            {options.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
      );
    }
    const val = patient?.[key];
    return (
      <div className="info-row">
        <label>{label}</label>
        <span>{val ? String(val) : '—'}</span>
      </div>
    );
  };

  const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);
  const calcAge = (dob: string) => {
    if (!dob) return '—';
    return Math.floor((Date.now() - new Date(dob).getTime()) / (365.25 * 24 * 3600 * 1000));
  };

  if (loading) {
    return <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)' }}>Loading patient data...</div>;
  }

  if (error || !patient) {
    return (
      <div className="empty-state">
        <h3>{error || 'Patient Not Found'}</h3>
        <p>Patient ID: {id}</p>
        <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate(-1)}>Go Back</button>
      </div>
    );
  }

  const fullName = `${patient.first_name} ${patient.last_name}`;

  return (
    <div>
      {toast && <div className="success-alert" style={{ marginBottom: 16 }}><CheckCircle size={16} /> {toast}</div>}

      <button className="back-btn" onClick={() => navigate(backPath)}>
        <ArrowLeft size={16} /> {backLabel}
      </button>

      <div className="page-header">
        <h2>Patient Profile</h2>
        <div style={{ display: 'flex', gap: 10 }}>
          {!editMode ? (
            <button className="btn btn-primary" onClick={handleEditStart}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Edit3 size={15} /> Edit Details
            </button>
          ) : (
            <>
              <button className="btn btn-success" onClick={handleSave} disabled={saving}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Save size={15} /> {saving ? 'Saving...' : 'Save Changes'}
              </button>
              <button className="btn btn-secondary" onClick={handleEditCancel}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <X size={15} /> Cancel
              </button>
            </>
          )}
        </div>
      </div>

      {editMode && (
        <div className="success-alert" style={{ background: 'var(--primary-lightest)', color: 'var(--primary)', border: '1px solid var(--primary)', marginBottom: 20 }}>
          ✏️ You are in edit mode. Make your changes and click "Save Changes".
        </div>
      )}

      {/* Profile Header */}
      <div className="profile-header">
        <div className="profile-avatar">{getInitials(fullName)}</div>
        <div className="profile-info">
          <h2>{fullName}</h2>
          <div className="meta">
            <span><User size={14} /> {patient.patient_code}</span>
            <span>{calcAge(patient.date_of_birth)} years, {patient.gender}</span>
            {patient.blood_group && <span><Heart size={14} /> {patient.blood_group}</span>}
            <span className={`status-badge ${patient.status === 'ACTIVE' ? 'active' : 'inactive'}`}>{patient.status}</span>
          </div>
        </div>
      </div>

      <div className="profile-grid">
        {/* Basic Information */}
        <div className="card">
          <div className="card-header"><h3>Basic Information</h3></div>
          <div className="card-body">
            {field('first_name', 'First Name')}
            {field('last_name', 'Last Name')}
            {field('date_of_birth', 'Date of Birth', 'date')}
            {selectField('gender', 'Gender', ['MALE', 'FEMALE', 'OTHER'])}
            {selectField('blood_group', 'Blood Group', ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'])}
            {selectField('status', 'Status', ['ACTIVE', 'INACTIVE'])}
            <div className="info-row"><label>Registered</label><span>{patient.created_at ? new Date(patient.created_at).toLocaleDateString() : '—'}</span></div>
          </div>
        </div>

        {/* Contact Information */}
        <div className="card">
          <div className="card-header"><h3>Contact Information</h3></div>
          <div className="card-body">
            {field('phone', 'Phone')}
            {field('whatsapp_number', 'WhatsApp')}
            {field('email', 'Email', 'email')}
            {field('address', 'Address')}
            {field('city', 'City')}
            {field('state', 'State')}
            {field('pincode', 'Pincode')}
          </div>
        </div>

        {/* Emergency Contact */}
        <div className="card">
          <div className="card-header"><h3><AlertTriangle size={15} style={{ marginRight: 6 }} />Emergency Contact</h3></div>
          <div className="card-body">
            {field('emergency_contact_name', 'Contact Name')}
            {field('emergency_contact_phone', 'Contact Phone')}
          </div>
        </div>
      </div>

      {/* Appointment History */}
      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <h3><Calendar size={16} style={{ marginRight: 8 }} />Appointment History</h3>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr><th>Booking ID</th><th>Doctor</th><th>Department</th><th>Date</th><th>Time</th><th>Source</th><th>Status</th></tr>
            </thead>
            <tbody>
              {appointments.length > 0 ? appointments.map((a, i) => (
                <tr key={i}>
                  <td style={{ fontWeight: 600, color: 'var(--primary)', fontSize: 12 }}>{a.booking_id}</td>
                  <td>{a.doctor_name}</td>
                  <td>{a.department_name}</td>
                  <td>{a.appointment_date}</td>
                  <td>{format12HourTime(a.appointment_time)}</td>
                  <td><span className="intent-badge">{a.booking_source}</span></td>
                  <td><span className={`status-badge ${a.status.toLowerCase()}`}>{a.status}</span></td>
                </tr>
              )) : (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No appointment records found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI Conversation History */}
      {conversations.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <h3><MessageSquare size={16} style={{ marginRight: 8 }} />AI Conversation History</h3>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr><th>Code</th><th>Language</th><th>Intent</th><th>Status</th><th>Started</th><th>Last Message</th></tr>
              </thead>
              <tbody>
                {conversations.map((c, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 600, fontSize: 12, color: 'var(--primary)' }}>{c.conversation_code}</td>
                    <td>{c.language}</td>
                    <td>{c.current_intent ? <span className="intent-badge">{c.current_intent}</span> : '—'}</td>
                    <td><span className={`status-badge ${c.conversation_status === 'ACTIVE' ? 'active' : 'inactive'}`}>{c.conversation_status}</span></td>
                    <td style={{ fontSize: 12 }}>{c.started_at ? new Date(c.started_at).toLocaleDateString() : '—'}</td>
                    <td style={{ fontSize: 12 }}>{c.last_message_at ? new Date(c.last_message_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default PatientProfile;
