import React, { useEffect, useState, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  fetchDashboardSummary, fetchAppointments, fetchDateWiseAnalytics, fetchDailyView,
  format12HourTime,
  type DashboardSummary, type Appointment, type DateWiseAnalytics, type DailyViewResponse
} from '../../services/dashboardApi';
import {
  CalendarCheck, Users, Clock, Bot, BedDouble,
  CheckCircle, Eye, RefreshCw, XCircle, UserPlus, UserCheck, TrendingUp, AlertTriangle, Calendar
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import DateRangeFilter, { type DateRangeValue, formatFriendlyDate, toYMD } from '../../components/DateRangeFilter';

const STATUS_COLORS: Record<string, string> = {
  BOOKED: '#ECC94B',
  CONFIRMED: '#48BB78',
  COMPLETED: '#4299E1',
  CANCELLED: '#F56565',
  RESCHEDULED: '#9F7AEA',
  NO_SHOW: '#A0AEC0',
};

const DoctorDashboard: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  const [dateRange, setDateRange] = useState<DateRangeValue>({
    dateFrom: toYMD(new Date(new Date().getFullYear(), new Date().getMonth(), 1)),
    dateTo: toYMD(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0)),
    preset: 'this_month',
    displayLabel: 'This Month',
  });

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [analytics, setAnalytics] = useState<DateWiseAnalytics | null>(null);
  const [rangeAppointments, setRangeAppointments] = useState<Appointment[]>([]);
  const [dailyView, setDailyView] = useState<DailyViewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [sum, ana, apptRes, dView] = await Promise.all([
        fetchDashboardSummary({
          date_from: dateRange.dateFrom,
          date_to: dateRange.dateTo,
        }),
        fetchDateWiseAnalytics({
          date_from: dateRange.dateFrom,
          date_to: dateRange.dateTo,
        }),
        fetchAppointments({
          date_from: dateRange.dateFrom,
          date_to: dateRange.dateTo,
          per_page: 50,
        }),
        fetchDailyView({
          date: toYMD(new Date()),
        }),
      ]);
      setSummary(sum);
      setAnalytics(ana);
      setRangeAppointments(apptRes.appointments);
      setDailyView(dView);
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
    }
  }, [dateRange]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good Morning' : hour < 17 ? 'Good Afternoon' : 'Good Evening';

  // Status pie chart
  const statusPieData = summary
    ? [
        { name: 'Completed', value: summary.appointments.completed, color: STATUS_COLORS.COMPLETED },
        { name: 'Confirmed', value: summary.appointments.confirmed, color: STATUS_COLORS.CONFIRMED },
        { name: 'Booked', value: summary.appointments.booked, color: STATUS_COLORS.BOOKED },
        { name: 'Cancelled', value: summary.appointments.cancelled, color: STATUS_COLORS.CANCELLED },
        { name: 'Rescheduled', value: summary.appointments.rescheduled, color: STATUS_COLORS.RESCHEDULED },
        { name: 'No Show', value: summary.appointments.no_show, color: STATUS_COLORS.NO_SHOW },
      ].filter(item => item.value > 0)
    : [];

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2>Meridian Hospital — Doctor Portal</h2>
            <p>{greeting}, {user?.name} {user?.department ? `· Department: ${user?.department}` : ''}</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={loadData}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              {loading ? 'Loading...' : `Refresh · ${lastUpdated.toLocaleTimeString()}`}
            </button>
          </div>
        </div>
      </div>

      {/* Date Filter Bar */}
      <div
        className="card"
        style={{
          padding: '12px 16px',
          marginBottom: 20,
          background: 'var(--bg-secondary)',
          border: '1px solid var(--border)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: 12,
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <DateRangeFilter
          initialPreset="this_month"
          initialFrom={dateRange.dateFrom}
          initialTo={dateRange.dateTo}
          onChange={val => setDateRange(val)}
        />
        <div style={{ fontSize: 13, color: 'var(--primary)', fontWeight: 600 }}>
          🔒 Showing ONLY your clinical records
        </div>
      </div>

      {/* Showing range banner */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: 'var(--primary-lightest, #EFF6FF)',
          border: '1px solid #BFDBFE',
          borderRadius: 8,
          padding: '8px 16px',
          marginBottom: 20,
          fontSize: 13,
          color: 'var(--primary, #2563EB)',
          fontWeight: 500,
        }}
      >
        <div>
          📅 Showing data from <strong>{formatFriendlyDate(dateRange.dateFrom)}</strong> to <strong>{formatFriendlyDate(dateRange.dateTo)}</strong>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {summary?.appointments.total ?? 0} appointment(s) in selected range
        </div>
      </div>

      {/* Primary KPI Grid */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><CalendarCheck size={22} /></div>
            <span className="kpi-trend up"><TrendingUp size={14} /> In Range</span>
          </div>
          <div className="kpi-value">{loading ? '—' : summary?.appointments.total ?? 0}</div>
          <div className="kpi-label">My Appointments</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon teal"><CheckCircle size={22} /></div>
            <span className="kpi-trend up">{summary?.appointments.total ? Math.round(((summary.appointments.completed) / summary.appointments.total) * 100) : 0}%</span>
          </div>
          <div className="kpi-value">{loading ? '—' : summary?.appointments.completed ?? 0}</div>
          <div className="kpi-label">Completed Consultations</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon green"><CalendarCheck size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.appointments.confirmed ?? 0}</div>
          <div className="kpi-label">Confirmed</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon amber"><Clock size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.appointments.booked ?? 0}</div>
          <div className="kpi-label">Booked (Pending)</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon red"><XCircle size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.appointments.cancelled ?? 0}</div>
          <div className="kpi-label">Cancelled</div>
        </div>

        <div className="kpi-card" style={{ cursor: 'pointer' }} onClick={() => navigate('/doctor/patient-records')}>
          <div className="kpi-card-header"><div className="kpi-icon teal"><Users size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : summary?.patients.unique_in_range ?? summary?.patients.total ?? 0}</div>
          <div className="kpi-label">My Patients (In Range)</div>
        </div>
      </div>

      {/* Secondary Metrics Row */}
      {summary && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
          {[
            { label: 'Upcoming Consultations', value: summary.appointments.upcoming, color: '#4A90D9', icon: Clock },
            { label: 'New Patients In Range', value: summary.patients.new_in_range ?? 0, color: '#48BB78', icon: UserPlus },
            { label: 'Returning Patients', value: summary.patients.returning_in_range ?? 0, color: '#3182CE', icon: UserCheck },
            { label: 'Rescheduled', value: summary.appointments.rescheduled, color: '#9F7AEA', icon: Clock },
            { label: 'No-Show', value: summary.appointments.no_show, color: '#A0AEC0', icon: AlertTriangle },
            { label: 'Open Escalations', value: summary.escalations.open, color: '#E53E3E', icon: Bot },
          ].map(item => (
            <div key={item.label} className="card" style={{ flex: '1 1 160px', padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ padding: 10, borderRadius: 8, background: `${item.color}15`, color: item.color }}>
                <item.icon size={20} />
              </div>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700, color: item.color }}>{item.value}</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{item.label}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Today's Schedule & Slot Utilization Summary */}
      {dailyView?.doctor_schedules && dailyView.doctor_schedules.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <h3><Clock size={16} style={{ marginRight: 8 }} />Today's Working Schedule & Slot Utilization ({formatFriendlyDate(toYMD(new Date()))})</h3>
          </div>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16 }}>
              {dailyView.doctor_schedules.map(ds => (
                <div key={ds.schedule_id} style={{ background: 'var(--bg-secondary)', padding: '16px', borderRadius: 8, border: '1px solid var(--border)' }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                    Working Hours: {ds.working_hours}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                    Slot Duration: {ds.slot_duration_minutes} mins · Total Slots: {ds.total_slots}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, marginBottom: 6 }}>
                    <span>Booked: <strong>{ds.booked_slots}</strong></span>
                    <span>Completed: <strong style={{ color: '#16A34A' }}>{ds.completed_slots}</strong></span>
                    <span>Available: <strong style={{ color: '#2563EB' }}>{ds.available_slots}</strong></span>
                  </div>
                  <div style={{ marginTop: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>
                      <span>Slot Utilization</span>
                      <span>{ds.slot_utilization_pct}%</span>
                    </div>
                    <div style={{ width: '100%', height: 8, background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${Math.min(100, ds.slot_utilization_pct)}%`,
                          height: '100%',
                          background: ds.slot_utilization_pct > 80 ? '#16A34A' : ds.slot_utilization_pct > 50 ? '#2563EB' : '#D97706',
                        }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Charts Row: Trend & Status */}
      <div className="chart-grid" style={{ marginBottom: 24 }}>
        <div className="chart-card">
          <div className="card-header">
            <h3>Daily Appointment Trend</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              {formatFriendlyDate(dateRange.dateFrom)} – {formatFriendlyDate(dateRange.dateTo)}
            </span>
          </div>
          <div className="card-body">
            {analytics?.appointments_by_date && analytics.appointments_by_date.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={analytics.appointments_by_date}>
                  <defs>
                    <linearGradient id="colorDocAppt" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#4A90D9" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#4A90D9" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#8796A9' }} />
                  <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                  <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area type="monotone" dataKey="total" name="Total" stroke="#4A90D9" strokeWidth={2} fill="url(#colorDocAppt)" />
                  <Area type="monotone" dataKey="completed" name="Completed" stroke="#48BB78" strokeWidth={2} fill="none" />
                  <Area type="monotone" dataKey="cancelled" name="Cancelled" stroke="#F56565" strokeWidth={1.5} fill="none" strokeDasharray="3 3" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                No appointments found for the selected date range.
              </div>
            )}
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <h3>Status Distribution</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>In Selected Range</span>
          </div>
          <div className="card-body">
            {statusPieData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={statusPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={3}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {statusPieData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                No appointments in selected range.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Appointments Timeline in Selected Range */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h3>Appointments in Selected Range ({formatFriendlyDate(dateRange.dateFrom)} – {formatFriendlyDate(dateRange.dateTo)})</h3>
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/doctor/appointments')}>
            View All in Table →
          </button>
        </div>
        <div className="card-body">
          {loading ? (
            <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading appointments...</div>
          ) : (
            <div className="timeline">
              {rangeAppointments.map(a => (
                <div key={a.id} className={`timeline-item ${a.status.toLowerCase()}`}>
                  <div className="timeline-time">
                    <div style={{ fontWeight: 600 }}>{format12HourTime(a.appointment_time)}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.appointment_date}</div>
                  </div>
                  <div className="timeline-content">
                    <div>
                      <div className="timeline-patient">{a.patient_name} ({a.patient_code})</div>
                      <div className="timeline-dept">
                        {a.department_name} · {a.booking_source}
                        {a.duration_minutes && ` · ${a.duration_minutes} min slot`}
                        {a.patient_reason && ` · Reason: "${a.patient_reason}"`}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
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
                      <div className="timeline-actions">
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => navigate(`/doctor/patient-records/${a.patient_id}`)}
                          title="View Patient Record"
                        >
                          <Eye size={13} />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {rangeAppointments.length === 0 && (
                <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                  No appointments found for the selected date range.
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
