import React, { useEffect, useState, useCallback } from 'react';
import {
  Users, CalendarCheck, Stethoscope, Clock, Bot,
  TrendingUp, TrendingDown, Hospital, ArrowUpRight, AlertTriangle, RefreshCw,
  Calendar, CheckCircle, XCircle, UserCheck, UserPlus, BedDouble, Filter, Layers, ListFilter
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import {
  fetchDashboardSummary, fetchDateWiseAnalytics, fetchDailyView, fetchDoctors, fetchDepartments,
  format12HourTime,
  type DashboardSummary, type DateWiseAnalytics, type DailyViewResponse, type Doctor, type Department
} from '../../services/dashboardApi';
import DateRangeFilter, { type DateRangeValue, formatFriendlyDate, toYMD } from '../../components/DateRangeFilter';

const COLORS = ['#4A90D9', '#5AAFA5', '#48BB78', '#ECC94B', '#F56565', '#9F7AEA', '#ED8936'];

const STATUS_COLORS: Record<string, string> = {
  BOOKED: '#ECC94B',
  CONFIRMED: '#48BB78',
  COMPLETED: '#4299E1',
  CANCELLED: '#F56565',
  RESCHEDULED: '#9F7AEA',
  NO_SHOW: '#A0AEC0',
};

function KpiSkeleton() {
  return (
    <div className="kpi-card" style={{ opacity: 0.5 }}>
      <div className="kpi-card-header">
        <div style={{ width: 36, height: 36, borderRadius: 8, background: 'var(--border)', animation: 'pulse 1.5s infinite' }} />
      </div>
      <div style={{ height: 32, width: 80, background: 'var(--border)', borderRadius: 6, marginBottom: 8, animation: 'pulse 1.5s infinite' }} />
      <div style={{ height: 14, width: 120, background: 'var(--border)', borderRadius: 4, animation: 'pulse 1.5s infinite' }} />
    </div>
  );
}

const AdminDashboard: React.FC = () => {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good Morning' : hour < 17 ? 'Good Afternoon' : 'Good Evening';

  // Active view tab
  const [activeTab, setActiveTab] = useState<'analytics' | 'daily_ops'>('analytics');

  // Filters
  const [dateRange, setDateRange] = useState<DateRangeValue>({
    dateFrom: toYMD(new Date(new Date().getFullYear(), new Date().getMonth(), 1)),
    dateTo: toYMD(new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0)),
    preset: 'this_month',
    displayLabel: 'This Month',
  });
  const [selectedDept, setSelectedDept] = useState<string>('');
  const [selectedDoctorId, setSelectedDoctorId] = useState<number | undefined>(undefined);
  const [selectedSource, setSelectedSource] = useState<string>('');

  // Daily Ops specific date
  const [dailyOpsDate, setDailyOpsDate] = useState<string>(toYMD(new Date()));

  // Data states
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [analytics, setAnalytics] = useState<DateWiseAnalytics | null>(null);
  const [dailyView, setDailyView] = useState<DailyViewResponse | null>(null);
  const [doctorList, setDoctorList] = useState<Doctor[]>([]);
  const [deptList, setDeptList] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  // Load static filter options (doctors, departments) once
  useEffect(() => {
    fetchDoctors().then(res => setDoctorList(res.doctors));
    fetchDepartments().then(res => setDeptList(res.departments));
  }, []);

  // Fetch all dashboard data when filters change
  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    try {
      const [sum, ana, dView] = await Promise.all([
        fetchDashboardSummary({
          date_from: dateRange.dateFrom,
          date_to: dateRange.dateTo,
          department: selectedDept || undefined,
          doctor_id: selectedDoctorId,
          booking_source: selectedSource || undefined,
        }),
        fetchDateWiseAnalytics({
          date_from: dateRange.dateFrom,
          date_to: dateRange.dateTo,
          department: selectedDept || undefined,
          doctor_id: selectedDoctorId,
          booking_source: selectedSource || undefined,
        }),
        fetchDailyView({
          date: dailyOpsDate,
          department: selectedDept || undefined,
          doctor_id: selectedDoctorId,
        }),
      ]);
      setSummary(sum);
      setAnalytics(ana);
      setDailyView(dView);
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
    }
  }, [dateRange, selectedDept, selectedDoctorId, selectedSource, dailyOpsDate]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Handle DateRange change
  const handleDateRangeChange = (val: DateRangeValue) => {
    setDateRange(val);
  };

  // Build Status Breakdown Pie data
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

  // Build Booking Source Pie data
  const sourcePieData = summary?.appointments.by_source
    ? Object.entries(summary.appointments.by_source)
        .map(([k, v]) => ({ name: k.replace('_', ' '), value: v }))
        .filter(item => item.value > 0)
    : [];

  return (
    <div>
      {/* Header & Main Controls */}
      <div className="page-header" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2>Meridian Hospital — Administration Analytics</h2>
            <p>{greeting}, Admin · Live date-wise operational data</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={loadDashboardData}
              disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              {loading ? 'Loading...' : `Refresh · ${lastUpdated.toLocaleTimeString()}`}
            </button>
          </div>
        </div>
      </div>

      {/* Global Filter Bar */}
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
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <DateRangeFilter
            initialPreset="this_month"
            initialFrom={dateRange.dateFrom}
            initialTo={dateRange.dateTo}
            onChange={handleDateRangeChange}
          />

          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <select
              value={selectedDept}
              onChange={e => setSelectedDept(e.target.value)}
              style={{
                padding: '6px 12px',
                border: '1.5px solid var(--border)',
                borderRadius: 'var(--radius-sm, 6px)',
                fontSize: 13,
                background: 'var(--bg-primary)',
              }}
            >
              <option value="">All Departments</option>
              {deptList.map(d => (
                <option key={d.id} value={d.department_name}>{d.department_name}</option>
              ))}
            </select>

            <select
              value={selectedDoctorId !== undefined ? String(selectedDoctorId) : ''}
              onChange={e => setSelectedDoctorId(e.target.value ? Number(e.target.value) : undefined)}
              style={{
                padding: '6px 12px',
                border: '1.5px solid var(--border)',
                borderRadius: 'var(--radius-sm, 6px)',
                fontSize: 13,
                background: 'var(--bg-primary)',
              }}
            >
              <option value="">All Doctors</option>
              {doctorList.map(doc => (
                <option key={doc.id} value={doc.id}>{doc.display_name}</option>
              ))}
            </select>

            <select
              value={selectedSource}
              onChange={e => setSelectedSource(e.target.value)}
              style={{
                padding: '6px 12px',
                border: '1.5px solid var(--border)',
                borderRadius: 'var(--radius-sm, 6px)',
                fontSize: 13,
                background: 'var(--bg-primary)',
              }}
            >
              <option value="">All Booking Sources</option>
              <option value="WHATSAPP_TEXT">WhatsApp Text</option>
              <option value="WHATSAPP_VOICE">WhatsApp Voice</option>
              <option value="ADMIN">Admin</option>
              <option value="DOCTOR">Doctor</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          <button
            className={`btn btn-sm ${activeTab === 'analytics' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('analytics')}
            style={{ display: 'flex', alignItems: 'center', gap: 5 }}
          >
            <TrendingUp size={14} /> Analytics & Trends
          </button>
          <button
            className={`btn btn-sm ${activeTab === 'daily_ops' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('daily_ops')}
            style={{ display: 'flex', alignItems: 'center', gap: 5 }}
          >
            <Calendar size={14} /> Daily View
          </button>
        </div>
      </div>

      {/* Showing Data Range Banner */}
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
          {selectedDept && ` · Department: ${selectedDept}`}
          {selectedDoctorId && ` · Doctor ID: ${selectedDoctorId}`}
          {selectedSource && ` · Source: ${selectedSource}`}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {summary?.appointments.total ?? 0} total appointment(s) in selected range
        </div>
      </div>

      {/* Main KPI Grid */}
      <div className="kpi-grid">
        {loading && !summary ? (
          Array.from({ length: 6 }).map((_, i) => <KpiSkeleton key={i} />)
        ) : (
          <>
            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon blue"><CalendarCheck size={22} /></div>
                <span className="kpi-trend up"><TrendingUp size={14} /> In Range</span>
              </div>
              <div className="kpi-value">{summary?.appointments.total ?? 0}</div>
              <div className="kpi-label">Total Appointments</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon teal"><CheckCircle size={22} /></div>
                <span className="kpi-trend up">{summary?.appointments.total ? Math.round(((summary.appointments.completed) / summary.appointments.total) * 100) : 0}%</span>
              </div>
              <div className="kpi-value">{summary?.appointments.completed ?? 0}</div>
              <div className="kpi-label">Completed Consultations</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon green"><CalendarCheck size={22} /></div>
              </div>
              <div className="kpi-value">{summary?.appointments.confirmed ?? 0}</div>
              <div className="kpi-label">Confirmed Appointments</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon amber"><Clock size={22} /></div>
              </div>
              <div className="kpi-value">{summary?.appointments.booked ?? 0}</div>
              <div className="kpi-label">Booked (Pending)</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon red"><XCircle size={22} /></div>
              </div>
              <div className="kpi-value">{summary?.appointments.cancelled ?? 0}</div>
              <div className="kpi-label">Cancelled</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon teal"><Users size={22} /></div>
              </div>
              <div className="kpi-value">{summary?.patients.unique_in_range ?? 0}</div>
              <div className="kpi-label">Unique Patients (In Range)</div>
            </div>
          </>
        )}
      </div>

      {/* Secondary Metrics Row */}
      {summary && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
          {[
            { label: 'Rescheduled', value: summary.appointments.rescheduled, color: '#9F7AEA', icon: Clock },
            { label: 'No-Show', value: summary.appointments.no_show, color: '#A0AEC0', icon: AlertTriangle },
            { label: 'New Patients (In Range)', value: summary.patients.new_in_range ?? 0, color: '#48BB78', icon: UserPlus },
            { label: 'Returning Patients', value: summary.patients.returning_in_range ?? 0, color: '#3182CE', icon: UserCheck },
            { label: 'Pre-Admissions', value: summary.admissions?.in_range ?? 0, color: '#D69E2E', icon: BedDouble },
            { label: 'Escalations (In Range)', value: summary.escalations.in_range ?? 0, color: '#E53E3E', icon: AlertTriangle },
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

      {/* TAB 1: ANALYTICS & TRENDS */}
      {activeTab === 'analytics' && (
        <>
          {/* Charts Row 1: Appointments by Date & Status Breakdown */}
          <div className="chart-grid">
            <div className="chart-card">
              <div className="card-header">
                <h3>Appointments by Date</h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {formatFriendlyDate(dateRange.dateFrom)} – {formatFriendlyDate(dateRange.dateTo)}
                </span>
              </div>
              <div className="card-body">
                {analytics?.appointments_by_date && analytics.appointments_by_date.length > 0 ? (
                  <ResponsiveContainer width="100%" height={270}>
                    <AreaChart data={analytics.appointments_by_date}>
                      <defs>
                        <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#4A90D9" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#4A90D9" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#8796A9' }} />
                      <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                      <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Area type="monotone" dataKey="total" name="Total" stroke="#4A90D9" strokeWidth={2} fill="url(#colorTotal)" />
                      <Area type="monotone" dataKey="completed" name="Completed" stroke="#48BB78" strokeWidth={2} fill="none" />
                      <Area type="monotone" dataKey="confirmed" name="Confirmed" stroke="#ECC94B" strokeWidth={1.5} fill="none" />
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
                <h3>Appointment Status Breakdown</h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Distribution</span>
              </div>
              <div className="card-body">
                {statusPieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={270}>
                    <PieChart>
                      <Pie
                        data={statusPieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={95}
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
                    No appointments found for the selected date range.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Charts Row 2: Doctor-wise Appointments & Department-wise Breakdown */}
          <div className="chart-grid">
            <div className="chart-card">
              <div className="card-header">
                <h3>Doctor-wise Appointments</h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>By Doctor</span>
              </div>
              <div className="card-body">
                {analytics?.doctor_analytics && analytics.doctor_analytics.length > 0 ? (
                  <ResponsiveContainer width="100%" height={270}>
                    <BarChart data={analytics.doctor_analytics}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                      <XAxis dataKey="doctor_name" tick={{ fontSize: 11, fill: '#8796A9' }} />
                      <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                      <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                      <Legend wrapperStyle={{ fontSize: 12 }} />
                      <Bar dataKey="total" name="Total" fill="#4A90D9" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="completed" name="Completed" fill="#48BB78" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="cancelled" name="Cancelled" fill="#F56565" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                    No doctor appointment data available.
                  </div>
                )}
              </div>
            </div>

            <div className="chart-card">
              <div className="card-header">
                <h3>Department-wise Appointments</h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>By Department</span>
              </div>
              <div className="card-body">
                {analytics?.department_analytics && analytics.department_analytics.length > 0 ? (
                  <ResponsiveContainer width="100%" height={270}>
                    <BarChart data={analytics.department_analytics} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                      <XAxis type="number" tick={{ fontSize: 12, fill: '#8796A9' }} />
                      <YAxis dataKey="name" type="category" tick={{ fontSize: 12, fill: '#8796A9' }} width={120} />
                      <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                      <Bar dataKey="value" name="Appointments" radius={[0, 4, 4, 0]}>
                        {analytics.department_analytics.map((_entry, index) => (
                          <Cell key={index} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                    No department data available.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Charts Row 3: Booking Source & Creation/Cancellation Trend */}
          <div className="chart-grid">
            <div className="chart-card">
              <div className="card-header">
                <h3>Booking Source Distribution</h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>WhatsApp vs Portal</span>
              </div>
              <div className="card-body">
                {sourcePieData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={270}>
                    <PieChart>
                      <Pie
                        data={sourcePieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={55}
                        outerRadius={90}
                        paddingAngle={3}
                        dataKey="value"
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {sourcePieData.map((_entry, index) => (
                          <Cell key={index} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                    No source data available for selected range.
                  </div>
                )}
              </div>
            </div>

            <div className="chart-card">
              <div className="card-header">
                <h3>New Patients Registration Trend</h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>By Creation Date</span>
              </div>
              <div className="card-body">
                {analytics?.new_patients_by_date && analytics.new_patients_by_date.length > 0 ? (
                  <ResponsiveContainer width="100%" height={270}>
                    <BarChart data={analytics.new_patients_by_date}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                      <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#8796A9' }} />
                      <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                      <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                      <Bar dataKey="count" name="New Patients" fill="#5AAFA5" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                    No patient registration data found in selected range.
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {/* TAB 2: DAILY OPERATIONAL VIEW */}
      {activeTab === 'daily_ops' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Daily Ops Date Selector & Totals Header */}
          <div className="card" style={{ padding: '16px 20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Calendar size={18} style={{ color: 'var(--primary)' }} />
                <span style={{ fontWeight: 600, fontSize: 15 }}>Operational Date:</span>
                <input
                  type="date"
                  value={dailyOpsDate}
                  onChange={e => setDailyOpsDate(e.target.value)}
                  style={{
                    padding: '6px 12px',
                    border: '1.5px solid var(--border)',
                    borderRadius: 'var(--radius-sm, 6px)',
                    fontSize: 13,
                    fontWeight: 600,
                    background: 'var(--bg-primary)',
                  }}
                />
                <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                  ({dailyView?.day_of_week || ''})
                </span>
              </div>

              {/* Daily totals badges */}
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <span style={{ background: '#EBF8FF', color: '#2B6CB0', padding: '6px 12px', borderRadius: 6, fontWeight: 600, fontSize: 13 }}>
                  Total: {dailyView?.totals.total ?? 0}
                </span>
                <span style={{ background: '#F0FDF4', color: '#15803D', padding: '6px 12px', borderRadius: 6, fontWeight: 600, fontSize: 13 }}>
                  Completed: {dailyView?.totals.completed ?? 0}
                </span>
                <span style={{ background: '#FEFCE8', color: '#A16207', padding: '6px 12px', borderRadius: 6, fontWeight: 600, fontSize: 13 }}>
                  Pending: {dailyView?.totals.pending ?? 0}
                </span>
                <span style={{ background: '#FEF2F2', color: '#B91C1C', padding: '6px 12px', borderRadius: 6, fontWeight: 600, fontSize: 13 }}>
                  Cancelled: {dailyView?.totals.cancelled ?? 0}
                </span>
                <span style={{ background: '#F3F4F6', color: '#4B5563', padding: '6px 12px', borderRadius: 6, fontWeight: 600, fontSize: 13 }}>
                  No-Show: {dailyView?.totals.no_show ?? 0}
                </span>
              </div>
            </div>
          </div>

          {/* Doctor Schedule & Slot Utilization Summary */}
          {dailyView?.doctor_schedules && dailyView.doctor_schedules.length > 0 && (
            <div className="card">
              <div className="card-header">
                <h3><Stethoscope size={16} style={{ marginRight: 8 }} />Doctor Schedule & Slot Utilization ({formatFriendlyDate(dailyOpsDate)})</h3>
              </div>
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Doctor</th>
                      <th>Department</th>
                      <th>Working Hours</th>
                      <th>Slot Duration</th>
                      <th>Total Slots</th>
                      <th>Booked</th>
                      <th>Completed</th>
                      <th>Available</th>
                      <th>Slot Utilization</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dailyView.doctor_schedules.map(ds => (
                      <tr key={ds.schedule_id}>
                        <td style={{ fontWeight: 600 }}>{ds.doctor_name}</td>
                        <td style={{ fontSize: 12 }}>{ds.department_name}</td>
                        <td style={{ fontSize: 12 }}>{ds.working_hours}</td>
                        <td>{ds.slot_duration_minutes} mins</td>
                        <td style={{ fontWeight: 600 }}>{ds.total_slots}</td>
                        <td style={{ color: '#D97706', fontWeight: 600 }}>{ds.booked_slots}</td>
                        <td style={{ color: '#16A34A', fontWeight: 600 }}>{ds.completed_slots}</td>
                        <td style={{ color: '#2563EB', fontWeight: 600 }}>{ds.available_slots}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ width: 60, height: 8, background: '#E2E8F0', borderRadius: 4, overflow: 'hidden' }}>
                              <div
                                style={{
                                  width: `${Math.min(100, ds.slot_utilization_pct)}%`,
                                  height: '100%',
                                  background: ds.slot_utilization_pct > 80 ? '#16A34A' : ds.slot_utilization_pct > 50 ? '#2563EB' : '#D97706',
                                }}
                              />
                            </div>
                            <span style={{ fontWeight: 600, fontSize: 12 }}>{ds.slot_utilization_pct}%</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Chronological Daily Appointments */}
          <div className="card">
            <div className="card-header">
              <h3>Daily Appointments ({formatFriendlyDate(dailyOpsDate)})</h3>
            </div>
            <div className="table-container">
              {dailyView?.appointments && dailyView.appointments.length > 0 ? (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Duration</th>
                      <th>Booking ID</th>
                      <th>Patient</th>
                      <th>Doctor</th>
                      <th>Department</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dailyView.appointments.map(a => (
                      <tr key={a.id}>
                        <td style={{ fontWeight: 600, color: 'var(--primary)' }}>
                          {format12HourTime(a.appointment_time)}
                          {a.appointment_end_time && ` – ${format12HourTime(a.appointment_end_time)}`}
                        </td>
                        <td style={{ fontSize: 12 }}>{a.duration_minutes ? `${a.duration_minutes} min` : '30 min'}</td>
                        <td style={{ fontSize: 12, fontWeight: 500 }}>{a.booking_id}</td>
                        <td>
                          <div style={{ fontWeight: 600 }}>{a.patient_name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{a.patient_code} · {a.patient_phone}</div>
                        </td>
                        <td>{a.doctor_name}</td>
                        <td style={{ fontSize: 12 }}>{a.department_name}</td>
                        <td style={{ fontSize: 12 }}>{a.patient_reason || '—'}</td>
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
                        <td><span className="intent-badge">{a.booking_source}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                  No appointments scheduled for {formatFriendlyDate(dailyOpsDate)}.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;
