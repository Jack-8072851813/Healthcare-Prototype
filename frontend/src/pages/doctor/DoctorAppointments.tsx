import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  fetchAppointments, updateAppointmentStatus, format12HourTime, type Appointment
} from '../../services/dashboardApi';
import { CheckCircle, XCircle, RefreshCw, Search } from 'lucide-react';

const STATUS_CLASS: Record<string, string> = {
  BOOKED: 'pending',
  CONFIRMED: 'confirmed',
  COMPLETED: 'active',
  CANCELLED: 'inactive',
  NO_SHOW: 'inactive',
  RESCHEDULED: 'pending',
};

const DoctorAppointments: React.FC = () => {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');
  const [total, setTotal] = useState(0);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3500);
  };

  const loadAppointments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchAppointments({
        search: search || undefined,
        status: statusFilter || undefined,
        per_page: 50,
      });
      setAppointments(res.appointments);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    const timer = setTimeout(loadAppointments, 300);
    return () => clearTimeout(timer);
  }, [loadAppointments]);

  const handleStatusUpdate = async (bookingId: string, newStatus: string, reason?: string) => {
    const ok = await updateAppointmentStatus(bookingId, newStatus, reason);
    if (ok) {
      showToast(`Appointment ${bookingId} → ${newStatus}`);
      loadAppointments();
    } else {
      showToast('❌ Status update failed.');
    }
  };

  return (
    <div>
      <div className="page-header">
        <h2>My Appointments</h2>
        <p>Appointments for {user?.name}{user?.department ? ` — ${user?.department}` : ''}</p>
      </div>

      {toast && <div className="success-alert"><CheckCircle size={16} /> {toast}</div>}

      <div className="card">
        <div className="card-header">
          <div className="search-bar" style={{ maxWidth: 280 }}>
            <Search size={18} />
            <input
              placeholder="Search patient, booking ID..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
              style={{ padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontFamily: 'inherit' }}>
              <option value="">All Status</option>
              <option value="BOOKED">Booked</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
              <option value="NO_SHOW">No Show</option>
            </select>
            <button className="btn btn-secondary btn-sm" onClick={loadAppointments} disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              Refresh
            </button>
          </div>
        </div>

        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>Loading appointments...</div>
          ) : appointments.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>No appointments found.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Booking ID</th>
                  <th>Patient</th>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Department</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map(a => (
                  <tr key={a.id}>
                    <td style={{ fontWeight: 600, color: 'var(--primary)', fontSize: 12 }}>{a.booking_id}</td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{a.patient_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.patient_phone}</div>
                    </td>
                    <td>{a.appointment_date}</td>
                    <td>{format12HourTime(a.appointment_time)}</td>
                    <td style={{ fontSize: 12 }}>{a.department_name}</td>
                    <td><span className="intent-badge">{a.booking_source}</span></td>
                    <td>
                      <span className={`status-badge ${STATUS_CLASS[a.status] || ''}`}>{a.status}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {a.status === 'BOOKED' && (
                          <button className="btn btn-primary btn-sm"
                            onClick={() => handleStatusUpdate(a.booking_id, 'CONFIRMED')}>
                            <CheckCircle size={13} /> Confirm
                          </button>
                        )}
                        {a.status === 'CONFIRMED' && (
                          <button className="btn btn-success btn-sm"
                            onClick={() => handleStatusUpdate(a.booking_id, 'COMPLETED')}>
                            <CheckCircle size={13} /> Complete
                          </button>
                        )}
                        {(a.status === 'BOOKED' || a.status === 'CONFIRMED') && (
                          <button className="btn btn-danger btn-sm"
                            onClick={() => handleStatusUpdate(a.booking_id, 'CANCELLED')}>
                            <XCircle size={13} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ padding: '12px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
          {loading ? 'Loading...' : `${appointments.length} of ${total} appointment(s) shown`}
        </div>
      </div>
    </div>
  );
};

export default DoctorAppointments;
