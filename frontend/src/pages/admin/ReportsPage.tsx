import React from 'react';
import {
  BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { CalendarCheck, Users, Building2, Bot, ClipboardList } from 'lucide-react';

const appointmentData = [
  { name: 'Mon', confirmed: 52, pending: 12, cancelled: 5 },
  { name: 'Tue', confirmed: 58, pending: 15, cancelled: 3 },
  { name: 'Wed', confirmed: 61, pending: 10, cancelled: 7 },
  { name: 'Thu', confirmed: 55, pending: 18, cancelled: 4 },
  { name: 'Fri', confirmed: 64, pending: 11, cancelled: 6 },
];

const registrationData = [
  { name: 'Jan', count: 42 }, { name: 'Feb', count: 48 }, { name: 'Mar', count: 55 },
  { name: 'Apr', count: 51 }, { name: 'May', count: 62 }, { name: 'Jun', count: 58 },
  { name: 'Jul', count: 71 }, { name: 'Aug', count: 45 },
];

const deptPerformance = [
  { name: 'Cardiology', patients: 145, appointments: 86 },
  { name: 'Orthopaedics', patients: 98, appointments: 62 },
  { name: 'Gen Med', patients: 210, appointments: 124 },
  { name: 'Pediatrics', patients: 145, appointments: 78 },
  { name: 'Neurology', patients: 72, appointments: 45 },
];

const aiReportData = [
  { name: 'Booking', value: 42 }, { name: 'Reschedule', value: 18 },
  { name: 'Query', value: 35 }, { name: 'Cancellation', value: 12 },
  { name: 'Info', value: 28 }, { name: 'Escalation', value: 8 },
];

const COLORS = ['#4A90D9', '#5AAFA5', '#48BB78', '#ECC94B', '#9F7AEA', '#F56565'];

const reports = [
  { title: 'Appointment Report', icon: CalendarCheck, desc: 'Weekly appointment trends and status breakdown' },
  { title: 'Patient Registration Report', icon: Users, desc: 'Monthly patient registration patterns' },
  { title: 'Department Performance', icon: Building2, desc: 'Department-wise patient and appointment metrics' },
  { title: 'AI Patient Desk Report', icon: Bot, desc: 'AI conversation analytics and intent distribution' },
  { title: 'Pre-Admission Report', icon: ClipboardList, desc: 'Pre-admission follow-up and document status' },
];

const ReportsPage: React.FC = () => {
  return (
    <div>
      <div className="page-header">
        <h2>Hospital Reports</h2>
        <p>Analytics and reporting for Meridian Hospital operations</p>
        <span className="demo-badge">⚠️ DEMO DATA — Fictional Reports</span>
      </div>

      {/* Report Cards */}
      <div className="kpi-grid" style={{ marginBottom: 28 }}>
        {reports.map(r => (
          <div key={r.title} className="kpi-card" style={{ cursor: 'pointer' }}>
            <div className="kpi-icon blue" style={{ marginBottom: 8 }}><r.icon size={22} /></div>
            <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-primary)', marginBottom: 4 }}>{r.title}</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{r.desc}</div>
          </div>
        ))}
      </div>

      {/* Charts */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header"><h3>Appointment Report</h3></div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={appointmentData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="confirmed" name="Confirmed" fill="#48BB78" radius={[3, 3, 0, 0]} />
                <Bar dataKey="pending" name="Pending" fill="#ECC94B" radius={[3, 3, 0, 0]} />
                <Bar dataKey="cancelled" name="Cancelled" fill="#F56565" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header"><h3>Patient Registration Trend</h3></div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={registrationData}>
                <defs>
                  <linearGradient id="colorReg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#5AAFA5" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#5AAFA5" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Area type="monotone" dataKey="count" stroke="#5AAFA5" strokeWidth={2} fill="url(#colorReg)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header"><h3>Department Performance</h3></div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={deptPerformance}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="patients" name="Patients" fill="#4A90D9" radius={[3, 3, 0, 0]} />
                <Bar dataKey="appointments" name="Appointments" fill="#5AAFA5" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header"><h3>AI Patient Desk — Intent Distribution</h3></div>
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={aiReportData} cx="50%" cy="50%" innerRadius={55} outerRadius={90} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {aiReportData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportsPage;
