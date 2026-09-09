import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  fetchAppointments, updateAppointmentStatus, format12HourTime, type Appointment
} from '../../services/dashboardApi';
import { CheckCircle, XCircle, RefreshCw, Search, Calendar } from 'lucide-react';
import DateRangeFilter, { type DateRangeValue, formatFriendlyDate, toYMD } from '../../components/DateRangeFilter';

const STATUS_CLASS: Record<string, string> = {
  BOOKED: 'pending',
  CONFIRMED: 'active',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  NO_SHOW: 'inactive',
  RESCHEDULED: 'rescheduled',
};

const DoctorAppointments: React.FC = () => {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateRange, setDateRange] = useState<DateRangeValue>({
    dateFrom: toYMD(new Date(new Date().getFullYear(), new Date().getMonth(), 1)),
    dateTo: toYMD(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0)),
    preset: 'this_month',
    displayLabel: 'This Month',
  });
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
        date_from: dateRange.dateFrom,
        date_to: dateRange.dateTo,
        per_page: 50,
      });
      setAppointments(res.appointments);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, dateRange]);

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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2>My Appointments</h2>
            <p>Appointments for {user?.name}{user?.department ? ` — ${user?.department}` : ''}</p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={loadAppointments}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {toast && <div className="success-alert" style={{ marginBottom: 16 }}><CheckCircle size={16} /> {toast}</div>}

      {/* Filter Card */}
      <div className="card" style={{ marginBottom: 20, padding: '14px 18px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
          <div className="search-bar" style={{ maxWidth: 300, flex: '1 1 200px' }}>
            <Search size={18} />
            <input
              placeholder="Search patient, booking ID..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <DateRangeFilter
              initialPreset="this_month"
              initialFrom={dateRange.dateFrom}
              initialTo={dateRange.dateTo}
              onChange={val => setDateRange(val)}
            />

            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              style={{
                padding: '6px 12px',
                border: '1.5px solid var(--border)',
                borderRadius: 'var(--radius-sm, 6px)',
                fontSize: 13,
                fontFamily: 'inherit',
                background: 'var(--bg-primary)',
              }}
            >
              <option value="">All Status</option>
              <option value="BOOKED">Booked</option>
              <option value="CONFIRMED">Confirmed</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
              <option value="RESCHEDULED">Rescheduled</option>
              <option value="NO_SHOW">No Show</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>Loading appointments...</div>
          ) : appointments.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              No appointments found for the selected date range ({formatFriendlyDate(dateRange.dateFrom)} – {formatFriendlyDate(dateRange.dateTo)}).
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Booking ID</th>
                  <th>Patient</th>
                  <th>Reason</th>
                  <th>Appointment Date</th>
                  <th>Time & Duration</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map(a => (
                  <tr key={a.id || a.booking_id}>
                    <td style={{ fontWeight: 600, color: 'var(--primary)', fontSize: 12 }}>{a.booking_id}</td>
                    <td>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{a.patient_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.patient_code} · {a.patient_phone}</div>
                    </td>
                    <td style={{ fontSize: 12, maxWidth: 180, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={a.patient_reason || ''}>
                      {a.patient_reason || '—'}
                    </td>
                    <td style={{ fontSize: 13, fontWeight: 500 }}>{a.appointment_date}</td>
                    <td style={{ fontSize: 13 }}>
                      <div style={{ fontWeight: 600 }}>{format12HourTime(a.appointment_time)}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {a.duration_minutes ? `${a.duration_minutes} mins` : '30 mins'}
                        {a.appointment_end_time && ` (– ${format12HourTime(a.appointment_end_time)})`}
                      </div>
                    </td>
                    <td><span className="intent-badge">{a.booking_source}</span></td>
                    <td>
                      <span className={`status-badge ${STATUS_CLASS[a.status] || ''}`}>{a.status}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {a.status === 'BOOKED' && (
                          <button
                            className="btn btn-primary btn-sm"
                            onClick={() => handleStatusUpdate(a.booking_id, 'CONFIRMED')}
                            title="Confirm"
                          >
                            <CheckCircle size={13} /> Confirm
                          </button>
                        )}
                        {a.status === 'CONFIRMED' && (
                          <button
                            className="btn btn-success btn-sm"
                            onClick={() => handleStatusUpdate(a.booking_id, 'COMPLETED')}
                            title="Complete Consultation"
                          >
                            <CheckCircle size={13} /> Complete
                          </button>
                        )}
                        {(a.status === 'BOOKED' || a.status === 'CONFIRMED') && (
                          <button
                            className="btn btn-danger btn-sm"
                            onClick={() => handleStatusUpdate(a.booking_id, 'CANCELLED', 'Cancelled by doctor')}
                            title="Cancel"
                          >
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
