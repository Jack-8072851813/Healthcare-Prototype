import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { doctors } from '../../data/doctors';
import { User, Mail, Phone, Clock, Building2, Award, Stethoscope } from 'lucide-react';
import logo from '../../assets/logo.svg';

const DoctorProfile: React.FC = () => {
  const { user } = useAuth();
  const doctor = doctors.find(d => d.loginId === user?.loginId);

  if (!doctor) return <div className="empty-state"><p>Doctor profile not found</p></div>;

  return (
    <div>
      <div className="page-header">
        <h2>Profile</h2>
        <p>Your professional profile at Meridian Hospital</p>
      </div>

      <div className="profile-header">
        <div className="profile-avatar">{doctor.avatar}</div>
        <div className="profile-info">
          <h2>{doctor.name}</h2>
          <div className="meta">
            <span><Stethoscope size={14} /> {doctor.specialization}</span>
            <span><Building2 size={14} /> {doctor.department}</span>
            <span className="status-badge active">{doctor.status}</span>
          </div>
        </div>
      </div>

      <div className="profile-grid">
        <div className="card">
          <div className="card-header"><h3>Professional Information</h3></div>
          <div className="card-body">
            <div className="info-row"><label>Doctor ID</label><span>{doctor.id}</span></div>
            <div className="info-row"><label>Specialization</label><span>{doctor.specialization}</span></div>
            <div className="info-row"><label>Department</label><span>{doctor.department}</span></div>
            <div className="info-row"><label>Qualification</label><span>{doctor.qualification}</span></div>
            <div className="info-row"><label>Experience</label><span>{doctor.experience}</span></div>
            <div className="info-row"><label>OPD Timings</label><span>{doctor.opdTimings}</span></div>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><h3>Contact Information</h3></div>
          <div className="card-body">
            <div className="info-row"><label><Mail size={13} /> Email</label><span>{doctor.email}</span></div>
            <div className="info-row"><label><Phone size={13} /> Phone</label><span>{doctor.phone}</span></div>
            <div className="info-row"><label>Total Patients</label><span>{doctor.patientsCount}</span></div>
            <div className="info-row"><label>Today's Appointments</label><span>{doctor.todayAppointments}</span></div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'var(--primary-lightest)', borderRadius: 'var(--radius-lg)' }}>
          <img src={logo} alt="Meridian Hospital" style={{ width: 36, height: 36, borderRadius: 8 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Meridian Hospital</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>The Family Hospital · Kolathur, Chennai</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DoctorProfile;
