import React, { useState, useEffect, useCallback } from 'react';
import { Search, Filter, CheckCircle, XCircle, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { fetchAppointments, updateAppointmentStatus, format12HourTime, type Appointment } from '../../services/dashboardApi';

const STATUS_COLORS: Record<string, string> = {
  BOOKED: 'pending',
  CONFIRMED: 'active',
  COMPLETED: 'completed',
  CANCELLED: 'cancelled',
  RESCHEDULED: 'rescheduled',
  NO_SHOW: 'inactive',
};

const AppointmentManagement: React.FC = () => {
  const [search, setSearch] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const perPage = 15;

  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [departments, setDepartments] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');

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
        department: deptFilter || undefined,
        date_from: dateFilter || undefined,
        date_to: dateFilter || undefined,
        page,
        per_page: perPage,
      });
      setAppointments(res.appointments);
      setTotal(res.total);
      setTotalPages(res.total_pages);
      // Collect unique departments from first load
      if (departments.length === 0 && res.appointments.length > 0) {
        const depts = [...new Set(res.appointments.map(a => a.department_name))].sort();
        setDepartments(depts);
      }
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, deptFilter, dateFilter, page]);

  useEffect(() => {
    const timer = setTimeout(loadAppointments, 300);
    return () => clearTimeout(timer);
  }, [loadAppointments]);

  const handleStatusChange = async (bookingId: string, newStatus: string, reason?: string) => {
    const ok = await updateAppointmentStatus(bookingId, newStatus, reason);
    if (ok) {
      showToast(`Appointment ${bookingId} → ${newStatus}`);
      loadAppointments();
    } else {
      showToast('❌ Status update failed. Check the backend.');
    }
  };

  const formatDate = (d: string) => d ? new Date(d).toLocaleDateString() : '—';
  const formatTime = (t: string) => {
    if (!t) return '—';
    const [h, m] = t.split(':');
    const hour = parseInt(h);
    return `${hour % 12 || 12}:${m} ${hour < 12 ? 'AM' : 'PM'}`;
  };

  return (
    <div>
      <div className="page-header">
        <h2>Appointment Management</h2>
        <p>View and manage all appointments — live from hospital database</p>
      </div>

      {toast && (
        <div className="success-alert">
          <CheckCircle size={16} /> {toast}
        </div>
      )}

      <div className="card">
        <div className="card-header" style={{ flexWrap: 'wrap', gap: 12 }}>
          <div className="search-bar" style={{ maxWidth: 300 }}>
            <Search size={18} />
            <input
              placeholder="Search patient, doctor, ID..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <Filter size={16} style={{ color: 'var(--text-muted)' }} />
            <input
              type="date"
              value={dateFilter}
              onChange={e => { setDateFilter(e.target.value); setPage(1); }}
              style={{ padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontFamily: 'inherit' }}
            />
            <select value={deptFilter} onChange={e => { setDeptFilter(e.target.value); setPage(1); }}>
              <option value="">All Departments</option>
              {departments.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
            <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}>
              <option value="">All Status</option>
              {['BOOKED', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'RESCHEDULED', 'NO_SHOW'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
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
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              Loading appointments...
            </div>
          ) : appointments.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              No appointments found for selected filters.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Booking ID</th>
                  <th>Patient</th>
                  <th>Doctor</th>
                  <th>Department</th>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {appointments.map(a => (
                  <tr key={a.booking_id}>
                    <td style={{ fontWeight: 600, color: 'var(--primary)', fontSize: 12 }}>{a.booking_id}</td>
                    <td>
                      <div style={{ fontWeight: 500, fontSize: 13 }}>{a.patient_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.patient_phone}</div>
                    </td>
                    <td>
                      <div style={{ fontSize: 13 }}>{a.doctor_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.specialization}</div>
                    </td>
                    <td style={{ fontSize: 13 }}>{a.department_name}</td>
                    <td style={{ fontSize: 13 }}>{formatDate(a.appointment_date)}</td>
                    <td style={{ fontSize: 13, fontWeight: 500 }}>{format12HourTime(a.appointment_time)}</td>
                    <td>
                      <span className="intent-badge" style={{ fontSize: 11 }}>{a.booking_source}</span>
                    </td>
                    <td>
                      <span className={`status-badge ${STATUS_COLORS[a.status] || ''}`}>
                        {a.status}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {a.status === 'BOOKED' && (
                          <button
                            className="btn btn-success btn-sm"
                            onClick={() => handleStatusChange(a.booking_id, 'CONFIRMED')}
                            title="Confirm"
                          >
                            <CheckCircle size={13} />
                          </button>
                        )}
                        {(a.status === 'CONFIRMED' || a.status === 'BOOKED') && (
                          <>
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleStatusChange(a.booking_id, 'COMPLETED')}
                              title="Mark Completed"
                              style={{ fontSize: 11 }}
                            >
                              ✓ Done
                            </button>
                            <button
                              className="btn btn-danger btn-sm"
                              onClick={() => handleStatusChange(a.booking_id, 'CANCELLED', 'Cancelled by admin')}
                              title="Cancel"
                            >
                              <XCircle size={13} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="pagination" style={{ padding: '16px 22px' }}>
          <span className="pagination-info">
            {loading ? 'Loading...' : `Showing ${Math.min((page - 1) * perPage + 1, total)}–${Math.min(page * perPage, total)} of ${total} appointments`}
          </span>
          <div className="pagination-buttons">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft size={14} /></button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const pg = i + Math.max(1, page - 3);
              if (pg > totalPages) return null;
              return <button key={pg} className={page === pg ? 'active' : ''} onClick={() => setPage(pg)}>{pg}</button>;
            })}
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><ChevronRight size={14} /></button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AppointmentManagement;
