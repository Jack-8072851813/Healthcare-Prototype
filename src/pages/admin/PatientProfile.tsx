import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { patients } from '../../data/patients';
import { appointments } from '../../data/appointments';
import { aiConversations } from '../../data/aiConversations';
import { ArrowLeft, User, Phone, Mail, MapPin, Heart, AlertTriangle, Calendar, FileText, MessageSquare } from 'lucide-react';

const PatientProfile: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const patient = patients.find(p => p.id === id);
  const patientAppointments = appointments.filter(a => a.patientId === id);
  const patientConversations = aiConversations.filter(c => c.patientId === id);

  if (!patient) {
    return (
      <div className="empty-state">
        <h3>Patient Not Found</h3>
        <p>No patient found with ID: {id}</p>
        <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate(-1)}>Go Back</button>
      </div>
    );
  }

  const getInitials = (name: string) => name.split(' ').map(n => n[0]).join('').toUpperCase();

  return (
    <div>
      <button className="back-btn" onClick={() => navigate(-1)}>
        <ArrowLeft size={16} /> Back to Patients
      </button>

      <div className="page-header">
        <h2>Patient Profile</h2>
        <span className="demo-badge">⚠️ DEMO PATIENT DATA — Fictional Record</span>
      </div>

      {/* Profile Header */}
      <div className="profile-header">
        <div className="profile-avatar">{getInitials(patient.name)}</div>
        <div className="profile-info">
          <h2>{patient.name}</h2>
          <div className="meta">
            <span><User size={14} /> {patient.id}</span>
            <span>{patient.age} years, {patient.gender}</span>
            <span><Heart size={14} /> {patient.bloodGroup}</span>
            <span className={`status-badge ${patient.status.toLowerCase()}`}>{patient.status}</span>
          </div>
        </div>
      </div>

      <div className="profile-grid">
        {/* Basic Information */}
        <div className="card">
          <div className="card-header"><h3>Basic Information</h3></div>
          <div className="card-body">
            <div className="info-row"><label>Full Name</label><span>{patient.name}</span></div>
            <div className="info-row"><label>Age</label><span>{patient.age} years</span></div>
            <div className="info-row"><label>Gender</label><span>{patient.gender}</span></div>
            <div className="info-row"><label>Blood Group</label><span>{patient.bloodGroup}</span></div>
            <div className="info-row"><label>Registered Date</label><span>{patient.registeredDate}</span></div>
          </div>
        </div>

        {/* Contact Information */}
        <div className="card">
          <div className="card-header"><h3>Contact Information</h3></div>
          <div className="card-body">
            <div className="info-row"><label><Phone size={13} /> Phone</label><span>{patient.phone}</span></div>
            <div className="info-row"><label><Mail size={13} /> Email</label><span>{patient.email}</span></div>
            <div className="info-row"><label><MapPin size={13} /> Address</label><span>{patient.address}</span></div>
            <div className="info-row"><label><AlertTriangle size={13} /> Emergency</label><span>{patient.emergencyContact}</span></div>
          </div>
        </div>

        {/* Assigned Doctor & Department */}
        <div className="card">
          <div className="card-header"><h3>Department & Doctor</h3></div>
          <div className="card-body">
            <div className="info-row"><label>Department</label><span>{patient.department}</span></div>
            <div className="info-row"><label>Assigned Doctor</label><span>{patient.assignedDoctor}</span></div>
            <div className="info-row"><label>Last Visit</label><span>{patient.lastVisit}</span></div>
            <div className="info-row"><label>Next Appointment</label><span>{patient.nextAppointment}</span></div>
          </div>
        </div>

        {/* Medical History */}
        <div className="card">
          <div className="card-header"><h3>Medical History</h3></div>
          <div className="card-body">
            <div style={{ marginBottom: 12 }}>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' }}>Conditions</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                {patient.medicalHistory.length > 0 ? patient.medicalHistory.map(m => (
                  <span key={m} className="intent-badge">{m}</span>
                )) : <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>No conditions recorded</span>}
              </div>
            </div>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' }}>Allergies</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
                {patient.allergies.length > 0 ? patient.allergies.map(a => (
                  <span key={a} style={{ padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600, background: 'var(--error-bg)', color: '#9B2C2C', border: '1px solid #FED7D7' }}>{a}</span>
                )) : <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>No known allergies</span>}
              </div>
            </div>
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
              <tr><th>ID</th><th>Doctor</th><th>Department</th><th>Date</th><th>Time</th><th>Type</th><th>Status</th></tr>
            </thead>
            <tbody>
              {patientAppointments.length > 0 ? patientAppointments.map(a => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{a.id}</td>
                  <td>{a.doctorName}</td>
                  <td>{a.department}</td>
                  <td>{a.date}</td>
                  <td>{a.time}</td>
                  <td><span className="intent-badge">{a.type}</span></td>
                  <td><span className={`status-badge ${a.status.toLowerCase()}`}>{a.status}</span></td>
                </tr>
              )) : (
                <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--text-muted)', padding: 24 }}>No appointment records found</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* AI Conversations */}
      {patientConversations.length > 0 && (
        <div className="card" style={{ marginTop: 20 }}>
          <div className="card-header">
            <h3><MessageSquare size={16} style={{ marginRight: 8 }} />AI Conversation History</h3>
          </div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr><th>ID</th><th>Channel</th><th>Language</th><th>Intent</th><th>Status</th><th>Time</th></tr>
              </thead>
              <tbody>
                {patientConversations.map(c => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600 }}>{c.id}</td>
                    <td><span className={`channel-badge ${c.channel.toLowerCase()}`}>{c.channel}</span></td>
                    <td>{c.language}</td>
                    <td><span className="intent-badge">{c.intent}</span></td>
                    <td><span className={`status-badge ${c.status.toLowerCase().replace(/ /g, '-')}`}>{c.status}</span></td>
                    <td>{c.timestamp}</td>
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
