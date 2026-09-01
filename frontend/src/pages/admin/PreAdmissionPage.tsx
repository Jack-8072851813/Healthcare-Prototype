import React, { useState, useEffect, useCallback } from 'react';
import { fetchAppointments, format12HourTime, type Appointment } from '../../services/dashboardApi';
import { BedDouble, FileText, Bell, CheckCircle, MessageSquare, RefreshCw } from 'lucide-react';

const PreAdmissionPage: React.FC = () => {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      const res = await fetchAppointments({ date_from: today, per_page: 100 });
      setAppointments(res.appointments);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const booked = appointments.filter(a => a.status === 'BOOKED').length;
  const confirmed = appointments.filter(a => a.status === 'CONFIRMED').length;
  const total = appointments.length;
  const cancelled = appointments.filter(a => a.status === 'CANCELLED').length;

  return (
    <div>
      <div className="page-header">
        <h2>Pre-Admission Follow-up</h2>
        <p>Manage upcoming appointments and patient follow-ups — live data</p>
      </div>

      {/* KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon blue"><BedDouble size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : booked}</div>
          <div className="kpi-label">Booked (Pending Confirmation)</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon green"><CheckCircle size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : confirmed}</div>
          <div className="kpi-label">Confirmed</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon amber"><Bell size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : total}</div>
          <div className="kpi-label">Total Upcoming</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon red"><FileText size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : cancelled}</div>
          <div className="kpi-label">Cancelled</div>
        </div>
      </div>

      {/* AI Reminder Sample */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <h3><MessageSquare size={16} style={{ marginRight: 8 }} />AI Pre-Admission Reminder (Sample)</h3>
        </div>
        <div className="card-body">
          <div style={{ background: '#DCF8C6', padding: 16, borderRadius: 10, maxWidth: 440, fontSize: 14, lineHeight: 1.7, color: '#303030' }}>
            <p style={{ fontWeight: 600, marginBottom: 8 }}>📱 WhatsApp AI Reminder</p>
            <p>Dear <strong>Patient</strong>,</p>
            <p>This is a reminder from <strong>Meridian Hospital</strong> regarding your upcoming appointment. Please ensure you arrive 15 minutes before your scheduled time.</p>
            <p style={{ marginTop: 8, fontSize: 12, color: '#666' }}>📞 Contact: 044 6666 9910 | 🏥 Meridian Hospital, Kolathur, Chennai</p>
          </div>
        </div>
      </div>

      {/* Upcoming Appointments Table */}
      <div className="card">
        <div className="card-header">
          <h3>Upcoming Appointments</h3>
          <button className="btn btn-secondary btn-sm" onClick={load} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>
        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>Loading...</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>Phone</th>
                  <th>Appointment Date</th>
                  <th>Time</th>
                  <th>Department</th>
                  <th>Doctor</th>
                  <th>Source</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map(a => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 500 }}>{a.patient_name}</td>
                    <td style={{ fontSize: 12 }}>{a.patient_phone}</td>
                    <td>{a.appointment_date}</td>
                    <td>{format12HourTime(a.appointment_time)}</td>
                    <td>{a.department_name}</td>
                    <td style={{ fontSize: 12 }}>{a.doctor_name}</td>
                    <td><span className="intent-badge">{a.booking_source}</span></td>
                    <td>
                      <span className={`status-badge ${
                        a.status === 'CONFIRMED' ? 'active' :
                        a.status === 'CANCELLED' ? 'inactive' : 'pending'
                      }`}>{a.status}</span>
                    </td>
                  </tr>
                ))}
                {appointments.length === 0 && (
                  <tr><td colSpan={8} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No upcoming appointments</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ padding: '12px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
          {loading ? 'Loading...' : `${appointments.length} upcoming appointment(s)`}
        </div>
      </div>
    </div>
  );
};

export default PreAdmissionPage;
