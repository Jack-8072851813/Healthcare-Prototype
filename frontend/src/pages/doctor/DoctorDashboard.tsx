import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  fetchDashboardSummary, fetchAppointments, format12HourTime,
  type DashboardSummary, type Appointment
} from '../../services/dashboardApi';
import {
  CalendarCheck, Users, Clock, Bot, BedDouble,
  CheckCircle, Eye, RefreshCw
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const DoctorDashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [todayAppts, setTodayAppts] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [sum, apptRes] = await Promise.all([
        fetchDashboardSummary(),
        fetchAppointments({
          date_from: new Date().toISOString().split('T')[0],
          date_to: new Date().toISOString().split('T')[0],
          per_page: 50,
        }),
      ]);
      setSummary(sum);
      setTodayAppts(apptRes.appointments);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good Morning' : hour < 17 ? 'Good Afternoon' : 'Good Evening';
  const todayStr = new Date().toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });

  return (
    <div>
      <div className="page-header">
        <h2>Meridian Hospital — Doctor Portal</h2>
        <p>{greeting}, {user?.name} {user?.department ? `· Department: ${user?.department}` : ''}</p>
      </div>

      {/* KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon blue"><CalendarCheck size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.appointments.today ?? 0}</div>
          <div className="kpi-label">Today's Appointments</div>
        </div>
        <div className="kpi-card" style={{ cursor: 'pointer' }} onClick={() => navigate('/doctor/patient-records')}>
          <div className="kpi-card-header"><div className="kpi-icon teal"><Users size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.patients.total ?? 0}</div>
          <div className="kpi-label">Patient Records</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon amber"><Clock size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.appointments.upcoming ?? 0}</div>
          <div className="kpi-label">Upcoming</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon green"><Bot size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.escalations.open ?? 0}</div>
          <div className="kpi-label">Open Escalations</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon red"><BedDouble size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.appointments.booked ?? 0}</div>
          <div className="kpi-label">Booked</div>
        </div>
      </div>

      {/* Today's Appointments Timeline */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h3>Today's Appointments</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{todayStr}</span>
            <button className="btn btn-secondary btn-sm" onClick={load} disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              Refresh
            </button>
          </div>
        </div>
        <div className="card-body">
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading appointments...</div>
          ) : (
            <div className="timeline">
              {todayAppts.map(a => (
                <div key={a.id} className={`timeline-item ${a.status.toLowerCase()}`}>
                  <div className="timeline-time">{format12HourTime(a.appointment_time)}</div>
                  <div className="timeline-content">
                    <div>
                      <div className="timeline-patient">{a.patient_name}</div>
                      <div className="timeline-dept">{a.department_name} · {a.booking_source}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className={`status-badge ${a.status.toLowerCase()}`}>{a.status}</span>
                      <div className="timeline-actions">
                        <button className="btn btn-secondary btn-sm"
                          onClick={() => navigate(`/doctor/patient-records/${a.patient_id}`)}>
                          <Eye size={13} />
                        </button>
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
          )}
        </div>
      </div>
    </div>
  );
};

export default DoctorDashboard;
