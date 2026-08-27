import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { patients } from '../../data/patients';
import { appointments } from '../../data/appointments';
import { aiConversations } from '../../data/aiConversations';
import { preAdmissions } from '../../data/aiConversations';
import {
  CalendarCheck, Users, Clock, Bot, BedDouble,
  TrendingUp, CheckCircle, Eye
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const DoctorDashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const myPatients = patients.filter(p => p.assignedDoctorId === user?.loginId);
  const myAppointments = appointments.filter(a => a.doctorId === user?.loginId);
  const todayAppts = myAppointments.filter(a => a.date === '2026-08-27');
  const pendingFollowups = myAppointments.filter(a => a.status === 'Pending').length;
  const myAdmissions = preAdmissions.filter(p => myPatients.some(mp => mp.id === p.patientId));
  const aiRequests = aiConversations.filter(c =>
    c.status === 'Needs Doctor Confirmation' &&
    myPatients.some(p => p.id === c.patientId)
  );

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good Morning' : hour < 17 ? 'Good Afternoon' : 'Good Evening';

  return (
    <div>
      <div className="page-header">
        <h2>Meridian Hospital — Doctor Portal</h2>
        <p>{greeting}, {user?.name} · Department: {user?.department}</p>
      </div>

      {/* KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon blue"><CalendarCheck size={22} /></div></div>
          <div className="kpi-value">{todayAppts.length}</div>
          <div className="kpi-label">Today's Appointments</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon teal"><Users size={22} /></div></div>
          <div className="kpi-value">{myPatients.length}</div>
          <div className="kpi-label">My Patients</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon amber"><Clock size={22} /></div></div>
          <div className="kpi-value">{pendingFollowups}</div>
          <div className="kpi-label">Pending Follow-ups</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon green"><Bot size={22} /></div></div>
          <div className="kpi-value">{aiRequests.length}</div>
          <div className="kpi-label">AI Patient Requests</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon red"><BedDouble size={22} /></div></div>
          <div className="kpi-value">{myAdmissions.length}</div>
          <div className="kpi-label">Upcoming Admissions</div>
        </div>
      </div>

      {/* Today's Appointments Timeline */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h3>Today's Appointments</h3>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>27 Aug 2026</span>
        </div>
        <div className="card-body">
          <div className="timeline">
            {todayAppts.map(a => (
              <div key={a.id} className={`timeline-item ${a.status.toLowerCase()}`}>
                <div className="timeline-time">{a.time}</div>
                <div className="timeline-content">
                  <div>
                    <div className="timeline-patient">{a.patientName}</div>
                    <div className="timeline-dept">{a.department} · {a.type}</div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className={`status-badge ${a.status.toLowerCase()}`}>{a.status}</span>
                    <div className="timeline-actions">
                      <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/doctor/patient-records/${a.patientId}`)}>
                        <Eye size={13} />
                      </button>
                      {a.status === 'Confirmed' && (
                        <button className="btn btn-primary btn-sm">Start</button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
            {todayAppts.length === 0 && (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                No appointments scheduled for today.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* AI Patient Requests */}
      {aiRequests.length > 0 && (
        <div className="card">
          <div className="card-header">
            <h3>AI Patient Requests — Needs Your Attention</h3>
          </div>
          <div className="card-body">
            {aiRequests.map(r => (
              <div key={r.id} style={{ padding: 16, border: '1px solid var(--border-light)', borderRadius: 'var(--radius-md)', marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontWeight: 600 }}>{r.patientName}</span>
                  <span className={`channel-badge ${r.channel.toLowerCase()}`}>{r.channel}</span>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                  {r.messages[0]?.text}
                </p>
                <div style={{ display: 'flex', gap: 6 }}>
                  <span className="intent-badge">{r.intent}</span>
                  <span className="status-badge needs-confirmation">{r.status}</span>
                </div>
                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <button className="btn btn-success btn-sm">Approve</button>
                  <button className="btn btn-primary btn-sm">Respond</button>
                  <button className="btn btn-secondary btn-sm">Schedule</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default DoctorDashboard;
