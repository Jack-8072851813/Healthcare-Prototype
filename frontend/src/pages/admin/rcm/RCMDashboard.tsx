import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, AlertTriangle, TrendingDown, CheckCircle,
  TrendingUp, ArrowRight, RefreshCw,
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { fetchRCMDashboard, type RCMDashboardData } from '../../../services/api';
import AIBadge from '../../../components/rcm/AIBadge';
import RiskBadge from '../../../components/rcm/RiskBadge';
import type { RiskLevel } from '../../../data/rcm/claims';

const STATUS_COLORS: Record<string, string> = {
  Approved: '#48BB78', Rejected: '#F56565', Pending: '#ECC94B', 'Under Review': '#4A90D9',
};

const RCMDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<RCMDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const d = await fetchRCMDashboard();
    setData(d);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  if (loading || !data) {
    return (
      <div className="page-loading">
        <div className="loading-spinner" />
        <p>Loading Revenue Cycle data…</p>
      </div>
    );
  }

  const leakageLakh = (data.potential_revenue_leakage / 100000).toFixed(2);

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>AI Revenue Cycle Management</h2>
          <p>Claims analysis, risk scoring, and revenue leakage detection</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <AIBadge />
          <button className="btn btn-outline btn-sm" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/admin/revenue-cycle/claims')}>
            View All Claims <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><FileText size={22} /></div>
            <span className="kpi-trend up"><TrendingUp size={14} /> Live</span>
          </div>
          <div className="kpi-value">{data.total_claims.toLocaleString()}</div>
          <div className="kpi-label">Total Claims</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon red"><AlertTriangle size={22} /></div>
            <span className="kpi-trend down"><TrendingUp size={14} /> {Math.round((data.claims_at_risk / data.total_claims) * 100)}%</span>
          </div>
          <div className="kpi-value">{data.claims_at_risk}</div>
          <div className="kpi-label">Claims at Risk</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon amber"><TrendingDown size={22} /></div>
            <span className="kpi-trend down" style={{ color: 'var(--error)' }}>Leakage</span>
          </div>
          <div className="kpi-value">₹{leakageLakh}L</div>
          <div className="kpi-label">Potential Revenue Leakage</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon green"><CheckCircle size={22} /></div>
            <span className="kpi-trend up"><TrendingUp size={14} /></span>
          </div>
          <div className="kpi-value">{data.first_pass_acceptance_rate}%</div>
          <div className="kpi-label">First-Pass Acceptance Rate</div>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header">
            <h3>Claims by Status</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>All time</span>
          </div>
          <div className="card-body" style={{ display: 'flex', alignItems: 'center' }}>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={data.claims_by_status}
                  cx="50%" cy="50%"
                  innerRadius={60} outerRadius={95}
                  paddingAngle={4} dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                  labelLine={{ stroke: '#ccc' }}
                >
                  {data.claims_by_status.map((entry: { name: string; value: number }, i: number) => (
                    <Cell key={i} fill={STATUS_COLORS[entry.name] || '#9F7AEA'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <h3>Rejection Trend</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Last 6 months</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={data.rejection_trend}>
                <defs>
                  <linearGradient id="colorRej" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#F56565" stopOpacity={0.18} />
                    <stop offset="95%" stopColor="#F56565" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4A90D9" stopOpacity={0.10} />
                    <stop offset="95%" stopColor="#4A90D9" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="total" name="Total Claims" stroke="#4A90D9" strokeWidth={2} fill="url(#colorTotal)" />
                <Area type="monotone" dataKey="rejected" name="Rejected" stroke="#F56565" strokeWidth={2} fill="url(#colorRej)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header">
            <h3>Top Rejection Reasons</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>By frequency</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.top_rejection_reasons} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis type="number" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis dataKey="reason" type="category" tick={{ fontSize: 11, fill: '#8796A9' }} width={160} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                <Bar dataKey="count" fill="#E8850A" radius={[0, 4, 4, 0]} name="Count" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* High-risk claims preview */}
        <div className="chart-card">
          <div className="card-header">
            <h3>High-Risk Claims</h3>
            <button
              className="btn btn-link"
              style={{ fontSize: 12 }}
              onClick={() => navigate('/admin/revenue-cycle/claims?risk_level=Critical')}
            >
              View all →
            </button>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            <div className="mini-table">
              <div className="mini-table-head">
                <span>Claim</span>
                <span>Patient</span>
                <span>Amount</span>
                <span>Risk</span>
              </div>
              {data.high_risk_claims.slice(0, 6).map((c: { id: string; patient_name: string; amount: number; risk_level: string; risk_score: number }) => (
                <div
                  key={c.id}
                  className="mini-table-row clickable"
                  onClick={() => navigate(`/admin/revenue-cycle/claims/${c.id}`)}
                >
                  <span className="mono">{c.id}</span>
                  <span>{c.patient_name}</span>
                  <span>₹{(c.amount / 1000).toFixed(0)}K</span>
                  <RiskBadge level={c.risk_level as RiskLevel} score={c.risk_score} size="sm" />
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RCMDashboard;
