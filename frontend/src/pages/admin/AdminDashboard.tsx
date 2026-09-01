import React, { useEffect, useState } from 'react';
import {
  Users, CalendarCheck, Stethoscope, Clock, Bot,
  TrendingUp, TrendingDown, Hospital, ArrowUpRight, AlertTriangle, RefreshCw
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import {
  fetchDashboardSummary, fetchAppointmentTrend, fetchPatientRegistrationTrend,
  fetchDepartmentAppointments, fetchIntentBreakdown,
  type DashboardSummary,
} from '../../services/dashboardApi';

const COLORS = ['#4A90D9', '#5AAFA5', '#48BB78', '#ECC94B', '#F56565', '#9F7AEA', '#ED8936'];

const appointmentStatusColors: Record<string, string> = {
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

  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [apptTrend, setApptTrend] = useState<{ name: string; total: number }[]>([]);
  const [patientTrend, setPatientTrend] = useState<{ month: string; patients: number }[]>([]);
  const [deptAppts, setDeptAppts] = useState<{ name: string; value: number }[]>([]);
  const [intentBreakdown, setIntentBreakdown] = useState<{ intent: string; count: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date>(new Date());

  const loadData = async () => {
    setLoading(true);
    try {
      const [s, at, pt, da, ib] = await Promise.all([
        fetchDashboardSummary(),
        fetchAppointmentTrend(7),
        fetchPatientRegistrationTrend(8),
        fetchDepartmentAppointments(),
        fetchIntentBreakdown(30),
      ]);
      setSummary(s);
      setApptTrend(at.trend);
      setPatientTrend(pt.trend);
      setDeptAppts(da.departments);
      setIntentBreakdown(ib.intent_breakdown);
      setLastUpdated(new Date());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Build appointment status pie from summary
  const apptStatusPie = summary
    ? Object.entries({
        Confirmed: summary.appointments.confirmed,
        Booked: summary.appointments.booked,
        Completed: summary.appointments.completed,
        Cancelled: summary.appointments.cancelled,
        'No Show': summary.appointments.no_show,
      })
        .filter(([, v]) => v > 0)
        .map(([name, value]) => ({ name, value }))
    : [];

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2>Meridian Hospital — Administration Dashboard</h2>
            <p>{greeting}, Admin · Live data from hospital database</p>
          </div>
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

      {/* KPI Cards */}
      <div className="kpi-grid">
        {loading && !summary ? (
          Array.from({ length: 6 }).map((_, i) => <KpiSkeleton key={i} />)
        ) : (
          <>
            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon blue"><Users size={22} /></div>
                <span className="kpi-trend up"><TrendingUp size={14} /> +{summary?.patients.new_this_month ?? 0} this month</span>
              </div>
              <div className="kpi-value">{summary?.patients.total.toLocaleString() ?? '—'}</div>
              <div className="kpi-label">Total Patients</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon teal"><CalendarCheck size={22} /></div>
                <span className="kpi-trend up"><ArrowUpRight size={14} /></span>
              </div>
              <div className="kpi-value">{summary?.appointments.today ?? '—'}</div>
              <div className="kpi-label">Today's Appointments</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon green"><Stethoscope size={22} /></div>
              </div>
              <div className="kpi-value">{summary?.doctors.active ?? '—'}</div>
              <div className="kpi-label">Active Doctors</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon amber"><Clock size={22} /></div>
              </div>
              <div className="kpi-value">{(summary?.appointments.booked ?? 0) + (summary?.appointments.confirmed ?? 0)}</div>
              <div className="kpi-label">Pending / Confirmed Appts</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon teal"><Bot size={22} /></div>
                <span className="kpi-trend up"><TrendingUp size={14} /> Today</span>
              </div>
              <div className="kpi-value">{summary?.conversations.today ?? '—'}</div>
              <div className="kpi-label">AI Conversations Today</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-card-header">
                <div className="kpi-icon red"><AlertTriangle size={22} /></div>
              </div>
              <div className="kpi-value">{summary?.escalations.open ?? '—'}</div>
              <div className="kpi-label">Open Escalations</div>
            </div>
          </>
        )}
      </div>

      {/* Secondary KPI row */}
      {summary && (
        <div style={{ display: 'flex', gap: 12, marginBottom: 24, flexWrap: 'wrap' }}>
          {[
            { label: 'Upcoming', value: summary.appointments.upcoming, color: '#4A90D9' },
            { label: 'Completed', value: summary.appointments.completed, color: '#48BB78' },
            { label: 'Cancelled', value: summary.appointments.cancelled, color: '#F56565' },
            { label: 'New Patients Today', value: summary.patients.new_today, color: '#9F7AEA' },
            { label: 'Total Conversations', value: summary.conversations.total, color: '#5AAFA5' },
          ].map(item => (
            <div key={item.label} className="card" style={{ flex: '1 1 160px', padding: '14px 18px' }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: item.color }}>{item.value}</div>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{item.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Charts Row 1 */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header">
            <h3>Appointment Trend</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Last 7 Days</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={apptTrend}>
                <defs>
                  <linearGradient id="colorAppt" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4A90D9" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#4A90D9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }} />
                <Area type="monotone" dataKey="total" name="Total" stroke="#4A90D9" strokeWidth={2} fill="url(#colorAppt)" />
                <Area type="monotone" dataKey="completed" name="Completed" stroke="#48BB78" strokeWidth={1.5} fill="none" strokeDasharray="4 2" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <h3>Patient Registration Trend</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Last 8 Months</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={patientTrend}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Bar dataKey="patients" fill="#5AAFA5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header">
            <h3>Department-wise Appointments</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Today</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={deptAppts} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis type="number" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 12, fill: '#8796A9' }} width={100} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Bar dataKey="value" name="Appointments" radius={[0, 4, 4, 0]}>
                  {deptAppts.map((_entry, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <h3>AI Intent Breakdown</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Last 30 Days</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={intentBreakdown.slice(0, 8)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="intent" tick={{ fontSize: 10, fill: '#8796A9' }} angle={-20} textAnchor="end" height={45} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Bar dataKey="count" name="Messages" radius={[4, 4, 0, 0]}>
                  {intentBreakdown.slice(0, 8).map((_entry, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Appointment Status Pie + Hospital Info */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header">
            <h3>Appointment Status Distribution</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>All Time</span>
          </div>
          <div className="card-body">
            {apptStatusPie.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={apptStatusPie}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={95}
                    paddingAngle={4}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {apptStatusPie.map((entry, index) => (
                      <Cell key={index} fill={appointmentStatusColors[entry.name.replace(' ', '_').toUpperCase()] || COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)', fontSize: 13 }}>
                No appointment data available yet.
              </div>
            )}
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <h3>About Meridian Hospital</h3>
            <Hospital size={18} style={{ color: 'var(--primary)' }} />
          </div>
          <div className="card-body">
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 16 }}>
              Meridian Hospital is a multispeciality hospital providing comprehensive healthcare services
              with AI-powered patient communication via WhatsApp.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {['AI Patient Desk', 'WhatsApp Booking', '24/7 Emergency', 'Multispeciality', 'Advanced Diagnostics', '7 Languages'].map(f => (
                <span key={f} className="facility-tag" style={{ fontSize: 11, padding: '4px 10px' }}>{f}</span>
              ))}
            </div>
            {summary && (
              <div style={{ marginTop: 16, padding: '12px', background: 'var(--bg-primary)', borderRadius: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
                <strong>Live Stats:</strong><br />
                📋 {summary.appointments.total} total appointments · {summary.conversations.total} conversations<br />
                📞 {summary.appointments.by_source['WHATSAPP_TEXT'] || 0} booked via WhatsApp Text · {summary.appointments.by_source['WHATSAPP_VOICE'] || 0} via Voice
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
