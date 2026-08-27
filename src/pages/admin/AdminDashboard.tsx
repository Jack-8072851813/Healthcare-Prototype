import React from 'react';
import {
  Users, CalendarCheck, Stethoscope, Clock, BedDouble, Bot,
  TrendingUp, TrendingDown, Hospital, ArrowUpRight
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

const appointmentTrend = [
  { name: 'Mon', appointments: 72 }, { name: 'Tue', appointments: 85 },
  { name: 'Wed', appointments: 91 }, { name: 'Thu', appointments: 78 },
  { name: 'Fri', appointments: 86 }, { name: 'Sat', appointments: 64 },
  { name: 'Sun', appointments: 32 },
];

const patientRegistration = [
  { name: 'Jan', patients: 45 }, { name: 'Feb', patients: 52 },
  { name: 'Mar', patients: 61 }, { name: 'Apr', patients: 48 },
  { name: 'May', patients: 55 }, { name: 'Jun', patients: 67 },
  { name: 'Jul', patients: 72 }, { name: 'Aug', patients: 58 },
];

const deptAppointments = [
  { name: 'Cardiology', value: 14 }, { name: 'Ortho', value: 10 },
  { name: 'Gen Med', value: 16 }, { name: 'Pediatrics', value: 12 },
  { name: 'Neurology', value: 8 }, { name: 'Derma', value: 9 },
];

const aiConversationVolume = [
  { name: 'Mon', whatsapp: 42, voice: 18 }, { name: 'Tue', whatsapp: 55, voice: 22 },
  { name: 'Wed', whatsapp: 48, voice: 25 }, { name: 'Thu', whatsapp: 62, voice: 28 },
  { name: 'Fri', whatsapp: 58, voice: 20 }, { name: 'Sat', whatsapp: 35, voice: 12 },
];

const appointmentStatus = [
  { name: 'Confirmed', value: 52, color: '#48BB78' },
  { name: 'Pending', value: 17, color: '#ECC94B' },
  { name: 'Completed', value: 12, color: '#4299E1' },
  { name: 'Cancelled', value: 5, color: '#F56565' },
];

const COLORS = ['#4A90D9', '#5AAFA5', '#48BB78', '#ECC94B', '#F56565', '#9F7AEA'];

const AdminDashboard: React.FC = () => {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good Morning' : hour < 17 ? 'Good Afternoon' : 'Good Evening';

  return (
    <div>
      <div className="page-header">
        <h2>Meridian Hospital — Administration Dashboard</h2>
        <p>{greeting}, Admin · Hospital operations and AI Patient Desk overview</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><Users size={22} /></div>
            <span className="kpi-trend up"><TrendingUp size={14} /> +5.2%</span>
          </div>
          <div className="kpi-value">1,248</div>
          <div className="kpi-label">Total Patients</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon teal"><CalendarCheck size={22} /></div>
            <span className="kpi-trend up"><TrendingUp size={14} /> +12%</span>
          </div>
          <div className="kpi-value">86</div>
          <div className="kpi-label">Today's Appointments</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon green"><Stethoscope size={22} /></div>
            <span className="kpi-trend up"><ArrowUpRight size={14} /></span>
          </div>
          <div className="kpi-value">24</div>
          <div className="kpi-label">Active Doctors</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon amber"><Clock size={22} /></div>
            <span className="kpi-trend down"><TrendingDown size={14} /> -8%</span>
          </div>
          <div className="kpi-value">17</div>
          <div className="kpi-label">Pending Appointments</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon red"><BedDouble size={22} /></div>
            <span className="kpi-trend up"><TrendingUp size={14} /> +3</span>
          </div>
          <div className="kpi-value">12</div>
          <div className="kpi-label">Upcoming Admissions</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon teal"><Bot size={22} /></div>
            <span className="kpi-trend up"><TrendingUp size={14} /> +22%</span>
          </div>
          <div className="kpi-value">143</div>
          <div className="kpi-label">AI Conversations Today</div>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header">
            <h3>Appointment Trend</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>This Week</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={appointmentTrend}>
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
                <Area type="monotone" dataKey="appointments" stroke="#4A90D9" strokeWidth={2} fill="url(#colorAppt)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <h3>Patient Registration Trend</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>2026</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={patientRegistration}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#8796A9' }} />
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
              <BarChart data={deptAppointments} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis type="number" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 12, fill: '#8796A9' }} width={80} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                  {deptAppointments.map((_entry, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <h3>AI Conversation Volume</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>This Week</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={aiConversationVolume}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="whatsapp" name="WhatsApp" fill="#48BB78" radius={[4, 4, 0, 0]} />
                <Bar dataKey="voice" name="Voice" fill="#4A90D9" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Appointment Status Pie */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header">
            <h3>Appointment Status</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Today</span>
          </div>
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={appointmentStatus} cx="50%" cy="50%" innerRadius={60} outerRadius={95} paddingAngle={4} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {appointmentStatus.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hospital Overview Mini Card */}
        <div className="chart-card">
          <div className="card-header">
            <h3>About Meridian Hospital</h3>
            <Hospital size={18} style={{ color: 'var(--primary)' }} />
          </div>
          <div className="card-body">
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 16 }}>
              Meridian Hospital is a multispeciality hospital located in Kolathur, Chennai,
              providing comprehensive healthcare services with advanced diagnostics and
              AI-powered patient communication.
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {['300 Beds', '24/7 Emergency', 'Multispeciality', 'Advanced Diagnostics', 'Telemedicine', 'Critical Care'].map(f => (
                <span key={f} className="facility-tag" style={{ fontSize: 11, padding: '4px 10px' }}>{f}</span>
              ))}
            </div>
            <div style={{ marginTop: 16, padding: '12px', background: 'var(--bg-primary)', borderRadius: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
              📍 46D, Jawaharlal Nehru Road, Kolathur, Chennai – 600099<br />
              📞 044 6666 9910 &nbsp; | &nbsp; 🚨 Emergency: 044 6666 9999
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdminDashboard;
