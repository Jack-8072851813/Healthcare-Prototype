import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { fetchAppointments, format12HourTime, type Appointment } from '../../services/dashboardApi';
import { BedDouble, RefreshCw } from 'lucide-react';

const DoctorAdmissions: React.FC = () => {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);

  // Show booked/confirmed appointments as "upcoming admissions"
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const today = new Date().toISOString().split('T')[0];
      const res = await fetchAppointments({
        status: 'BOOKED',
        date_from: today,
        per_page: 50,
      });
      setAppointments(res.appointments);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <div className="page-header">
        <h2>Admissions</h2>
        <p>Upcoming scheduled appointments for {user?.name}'s patients</p>
      </div>

      <div className="card">
        <div className="card-header">
          <h3><BedDouble size={16} style={{ marginRight: 8 }} />Upcoming Bookings</h3>
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
                  <th>Booking ID</th>
                  <th>Appointment Date</th>
                  <th>Time</th>
                  <th>Department</th>
                  <th>Source</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map(a => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 500 }}>{a.patient_name}</td>
                    <td style={{ fontSize: 12, color: 'var(--primary)', fontWeight: 600 }}>{a.booking_id}</td>
                    <td>{a.appointment_date}</td>
                    <td>{format12HourTime(a.appointment_time)}</td>
                    <td>{a.department_name}</td>
                    <td><span className="intent-badge">{a.booking_source}</span></td>
                    <td><span className="status-badge pending">{a.status}</span></td>
                  </tr>
                ))}
                {appointments.length === 0 && (
                  <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No upcoming admissions</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ padding: '12px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
          {loading ? 'Loading...' : `${appointments.length} upcoming booking(s)`}
        </div>
      </div>
    </div>
  );
};

export default DoctorAdmissions;
