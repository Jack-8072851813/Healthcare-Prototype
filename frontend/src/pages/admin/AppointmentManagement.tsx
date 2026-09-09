import React, { useState, useEffect, useCallback } from 'react';
import {
  Search, Filter, CheckCircle, XCircle, RefreshCw, ChevronLeft, ChevronRight,
  Download, ArrowUpDown, Clock, Calendar, User, Stethoscope, Building
} from 'lucide-react';
import {
  fetchAppointments, fetchDoctors, fetchDepartments, updateAppointmentStatus,
  format12HourTime,
  type Appointment, type Doctor, type Department
} from '../../services/dashboardApi';
import DateRangeFilter, { type DateRangeValue, formatFriendlyDate, toYMD } from '../../components/DateRangeFilter';

const STATUS_COLORS: Record<string, string> = {
  BOOKED: '#ECC94B',
  CONFIRMED: '#48BB78',
  COMPLETED: '#4299E1',
  CANCELLED: '#F56565',
  RESCHEDULED: '#9F7AEA',
  NO_SHOW: '#A0AEC0',
};

const AppointmentManagement: React.FC = () => {
  const [search, setSearch] = useState('');
  const [dateRange, setDateRange] = useState<DateRangeValue>({
    dateFrom: toYMD(new Date(new Date().getFullYear(), new Date().getMonth(), 1)),
    dateTo: toYMD(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0)),
    preset: 'this_month',
    displayLabel: 'This Month',
  });
  const [dateType, setDateType] = useState<'appointment_date' | 'created_at'>('appointment_date');
  const [deptFilter, setDeptFilter] = useState('');
  const [doctorFilter, setDoctorFilter] = useState<number | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [sortBy, setSortBy] = useState('appointment_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [page, setPage] = useState(1);
  const perPage = 15;

  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');

  // Load static filter options
  useEffect(() => {
    fetchDoctors().then(res => setDoctors(res.doctors));
    fetchDepartments().then(res => setDepartments(res.departments));
  }, []);

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
        doctor_id: doctorFilter,
        booking_source: sourceFilter || undefined,
        date_from: dateRange.dateFrom,
        date_to: dateRange.dateTo,
        date_type: dateType,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        per_page: perPage,
      });
      setAppointments(res.appointments);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, deptFilter, doctorFilter, sourceFilter, dateRange, dateType, sortBy, sortOrder, page]);

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

  // CSV Export feature
  const exportToCSV = async () => {
    try {
      // Fetch up to 1000 items matching current filters
      const res = await fetchAppointments({
        search: search || undefined,
        status: statusFilter || undefined,
        department: deptFilter || undefined,
        doctor_id: doctorFilter,
        booking_source: sourceFilter || undefined,
        date_from: dateRange.dateFrom,
        date_to: dateRange.dateTo,
        date_type: dateType,
        sort_by: sortBy,
        sort_order: sortOrder,
        page: 1,
        per_page: 1000,
      });

      if (!res.appointments || res.appointments.length === 0) {
        showToast('⚠️ No appointments to export');
        return;
      }

      const headers = [
        'Appointment ID (Booking ID)',
        'Patient Name',
        'Patient ID (Code)',
        'Phone',
        'Doctor Name',
        'Department',
        'Reason',
        'Appointment Date',
        'Appointment Time',
        'Duration (Minutes)',
        'Status',
        'Booking Source',
        'Created Date'
      ];

      const rows = res.appointments.map(a => [
        `"${a.booking_id || ''}"`,
        `"${a.patient_name || ''}"`,
        `"${a.patient_code || ''}"`,
        `"${a.patient_phone || ''}"`,
        `"${a.doctor_name || ''}"`,
        `"${a.department_name || ''}"`,
        `"${(a.patient_reason || '').replace(/"/g, '""')}"`,
        `"${a.appointment_date || ''}"`,
        `"${a.appointment_time || ''}"`,
        `"${a.duration_minutes || 30}"`,
        `"${a.status || ''}"`,
        `"${a.booking_source || ''}"`,
        `"${a.created_at ? new Date(a.created_at).toISOString().split('T')[0] : ''}"`
      ]);

      const csvContent = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `appointments_${dateRange.dateFrom}_to_${dateRange.dateTo}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      showToast('✓ Appointments exported to CSV successfully');
    } catch (e) {
      showToast('❌ Failed to export CSV');
    }
  };

  const formatDate = (d: string) => d ? new Date(d).toLocaleDateString() : '—';

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2>Appointment Management</h2>
            <p>View, filter, sort and manage hospital appointments — live database</p>
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={exportToCSV}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <Download size={14} /> Export CSV
            </button>
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

      {toast && (
        <div className="success-alert" style={{ marginBottom: 16 }}>
          <CheckCircle size={16} /> {toast}
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="card" style={{ marginBottom: 20, padding: '14px 18px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
          {/* Search */}
          <div className="search-bar" style={{ flex: '1 1 240px', maxWidth: 320 }}>
            <Search size={18} />
            <input
              placeholder="Search patient, doctor, ID..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
            />
          </div>

          {/* Date Filter & Date Type */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <DateRangeFilter
              initialPreset="this_month"
              initialFrom={dateRange.dateFrom}
              initialTo={dateRange.dateTo}
              onChange={val => { setDateRange(val); setPage(1); }}
            />

            <select
              value={dateType}
              onChange={e => { setDateType(e.target.value as 'appointment_date' | 'created_at'); setPage(1); }}
              style={{
                padding: '6px 12px',
                border: '1.5px solid var(--border)',
                borderRadius: 'var(--radius-sm, 6px)',
                fontSize: 13,
                fontWeight: 500,
                background: 'var(--bg-primary)',
              }}
              title="Select which timestamp to filter on"
            >
              <option value="appointment_date">Filter by: Appointment Date</option>
              <option value="created_at">Filter by: Booking Created Date</option>
            </select>
          </div>
        </div>

        {/* Secondary Filter Row: Doctor, Department, Status, Source, Sorting */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center', marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
          <Filter size={15} style={{ color: 'var(--text-muted)' }} />

          <select
            value={deptFilter}
            onChange={e => { setDeptFilter(e.target.value); setPage(1); }}
            style={{ padding: '6px 10px', border: '1.5px solid var(--border)', borderRadius: 6, fontSize: 13 }}
          >
            <option value="">All Departments</option>
            {departments.map(d => <option key={d.id} value={d.department_name}>{d.department_name}</option>)}
          </select>

          <select
            value={doctorFilter !== undefined ? String(doctorFilter) : ''}
            onChange={e => { setDoctorFilter(e.target.value ? Number(e.target.value) : undefined); setPage(1); }}
            style={{ padding: '6px 10px', border: '1.5px solid var(--border)', borderRadius: 6, fontSize: 13 }}
          >
            <option value="">All Doctors</option>
            {doctors.map(d => <option key={d.id} value={d.id}>{d.display_name}</option>)}
          </select>

          <select
            value={statusFilter}
            onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
            style={{ padding: '6px 10px', border: '1.5px solid var(--border)', borderRadius: 6, fontSize: 13 }}
          >
            <option value="">All Status</option>
            {['BOOKED', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'RESCHEDULED', 'NO_SHOW'].map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          <select
            value={sourceFilter}
            onChange={e => { setSourceFilter(e.target.value); setPage(1); }}
            style={{ padding: '6px 10px', border: '1.5px solid var(--border)', borderRadius: 6, fontSize: 13 }}
          >
            <option value="">All Sources</option>
            <option value="WHATSAPP_TEXT">WhatsApp Text</option>
            <option value="WHATSAPP_VOICE">WhatsApp Voice</option>
            <option value="ADMIN">Admin</option>
            <option value="DOCTOR">Doctor</option>
          </select>

          {/* Sort By Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 'auto' }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Sort by:</span>
            <select
              value={sortBy}
              onChange={e => setSortBy(e.target.value)}
              style={{ padding: '6px 10px', border: '1.5px solid var(--border)', borderRadius: 6, fontSize: 13 }}
            >
              <option value="appointment_date">Appointment Date</option>
              <option value="created_at">Created Date</option>
              <option value="patient">Patient Name</option>
              <option value="doctor">Doctor Name</option>
              <option value="status">Status</option>
            </select>

            <button
              className="btn btn-secondary btn-sm"
              onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
              style={{ padding: '6px 10px', display: 'flex', alignItems: 'center', gap: 4 }}
              title={`Sort ${sortOrder.toUpperCase()}`}
            >
              <ArrowUpDown size={14} /> {sortOrder.toUpperCase()}
            </button>
          </div>
        </div>
      </div>

      {/* Appointment Table */}
      <div className="card">
        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              Loading appointments...
            </div>
          ) : appointments.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              No appointments found for the selected date range and filters.
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Booking ID</th>
                  <th>Patient</th>
                  <th>Doctor</th>
                  <th>Department</th>
                  <th>Reason</th>
                  <th>Appointment Date</th>
                  <th>Time & Duration</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>Created Date</th>
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
                    <td>
                      <div style={{ fontSize: 13, fontWeight: 500 }}>{a.doctor_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.specialization}</div>
                    </td>
                    <td style={{ fontSize: 13 }}>{a.department_name}</td>
                    <td style={{ fontSize: 12, maxWidth: 160, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={a.patient_reason || ''}>
                      {a.patient_reason || '—'}
                    </td>
                    <td style={{ fontSize: 13, fontWeight: 500 }}>{formatDate(a.appointment_date)}</td>
                    <td style={{ fontSize: 13 }}>
                      <div style={{ fontWeight: 600 }}>{format12HourTime(a.appointment_time)}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        {a.duration_minutes ? `${a.duration_minutes} mins` : '30 mins'}
                        {a.appointment_end_time && ` (– ${format12HourTime(a.appointment_end_time)})`}
                      </div>
                    </td>
                    <td>
                      <span
                        className="status-badge"
                        style={{
                          background: `${STATUS_COLORS[a.status] || '#A0AEC0'}20`,
                          color: STATUS_COLORS[a.status] || '#4A5568',
                          fontWeight: 600,
                        }}
                      >
                        {a.status}
                      </span>
                    </td>
                    <td>
                      <span className="intent-badge" style={{ fontSize: 11 }}>{a.booking_source}</span>
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {a.status === 'BOOKED' && (
                          <button
                            className="btn btn-success btn-sm"
                            onClick={() => handleStatusChange(a.booking_id, 'CONFIRMED')}
                            title="Confirm Appointment"
                          >
                            <CheckCircle size={13} /> Confirm
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
                              title="Cancel Appointment"
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

        {/* Pagination */}
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
