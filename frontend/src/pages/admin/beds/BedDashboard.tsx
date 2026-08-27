import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BedDouble, Users, AlertTriangle, TrendingUp, Activity, ArrowRight, RefreshCw,
} from 'lucide-react';
import {
  BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { fetchBedDashboard, type BedDashboardData } from '../../../services/api';
import OccupancyBar from '../../../components/beds/OccupancyBar';
import WhyPanel from '../../../components/rcm/WhyPanel';
import AIBadge from '../../../components/rcm/AIBadge';

const DEPT_COLORS: Record<string, string> = {
  ICU: '#F56565', 'General Ward': '#4A90D9', Paediatric: '#48BB78', Surgical: '#E8850A',
};

const BedDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [data, setData] = useState<BedDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const d = await fetchBedDashboard();
    setData(d);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  if (loading || !data) {
    return (
      <div className="page-loading">
        <div className="loading-spinner" />
        <p>Loading Bed Allocation data…</p>
      </div>
    );
  }

  const shortageAlerts = data.forecast_summary.filter((e: { shortage: number }) => e.shortage > 0);

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Predictive Bed Allocation</h2>
          <p>Real-time occupancy and AI-powered demand forecasting</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <AIBadge />
          <button className="btn btn-outline btn-sm" onClick={load}>
            <RefreshCw size={14} /> Refresh
          </button>
          <button className="btn btn-primary btn-sm" onClick={() => navigate('/admin/bed-allocation/forecast')}>
            View Forecast <ArrowRight size={14} />
          </button>
        </div>
      </div>

      {/* Surge Alerts */}
      {shortageAlerts.length > 0 && (
        <div className="alert-banner-list">
          {shortageAlerts.map((a: { department: string; expected_demand: number; available: number; shortage: number }) => (
            <div key={a.department} className="alert-banner alert-banner-warning">
              <AlertTriangle size={16} />
              <span>
                <strong>Bed Shortage Predicted (24h):</strong> {a.department} — Expected demand of{' '}
                <strong>{a.expected_demand}</strong> beds with only <strong>{a.available}</strong> available.
                Shortage: <strong>{a.shortage}</strong>.
              </span>
              <AIBadge />
            </div>
          ))}
        </div>
      )}

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><BedDouble size={22} /></div>
          </div>
          <div className="kpi-value">{data.total_beds}</div>
          <div className="kpi-label">Total Beds</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon red"><Users size={22} /></div>
            <span className="kpi-trend down">{data.occupancy_rate}%</span>
          </div>
          <div className="kpi-value">{data.occupied}</div>
          <div className="kpi-label">Currently Occupied</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon green"><BedDouble size={22} /></div>
            <span className="kpi-trend up"><TrendingUp size={14} /></span>
          </div>
          <div className="kpi-value">{data.available}</div>
          <div className="kpi-label">Available Beds</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon amber"><Activity size={22} /></div>
          </div>
          <div className="kpi-value">{data.occupancy_rate}%</div>
          <div className="kpi-label">Occupancy Rate</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon red"><AlertTriangle size={22} /></div>
            <span className="kpi-trend down" style={{ color: data.predicted_shortage > 0 ? 'var(--error)' : 'var(--success)' }}>
              {data.predicted_shortage > 0 ? 'Alert' : 'OK'}
            </span>
          </div>
          <div className="kpi-value" style={{ color: data.predicted_shortage > 0 ? 'var(--error)' : 'var(--success)' }}>
            {data.predicted_shortage}
          </div>
          <div className="kpi-label">Predicted Shortage (24h)</div>
        </div>
      </div>

      {/* Department Occupancy Cards */}
      <div className="dept-occ-grid">
        {data.departments.map((dept: { name: string; occupied: number; total_beds: number }, _deptIndex: number) => {
          const fc = data.forecast_summary.find((e: { department: string; expected_demand: number; available: number; shortage: number; confidence: number }) => e.department === dept.name);
          return (
            <div key={dept.name} className="chart-card dept-occ-card">
              <div className="card-header">
                <h3>{dept.name}</h3>
                <span
                  className="dept-dot"
                  style={{ background: DEPT_COLORS[dept.name] || '#4A90D9' }}
                />
              </div>
              <div className="card-body">
                <OccupancyBar occupied={dept.occupied} total={dept.total_beds} />
                {fc && (
                  <div className="dept-forecast-mini">
                    <span>24h forecast:</span>
                    <span style={{ fontWeight: 600 }}>{fc.expected_demand} needed</span>
                    {fc.shortage > 0
                      ? <span className="shortage-tag">−{fc.shortage} shortage</span>
                      : <span className="ok-tag">No shortage</span>}
                  </div>
                )}
                {fc && (
                  <WhyPanel
                    factors={[
                      `Expected demand: ${fc.expected_demand} beds based on historical admission patterns`,
                      `Current availability: ${fc.available} beds`,
                      `Forecast confidence: ${Math.round(fc.confidence * 100)}%`,
                      fc.shortage > 0 ? `Shortage risk: ${fc.shortage} additional beds required` : 'Capacity appears sufficient',
                    ]}
                    title="Why this forecast?"
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Charts Row */}
      <div className="chart-grid">
        <div className="chart-card">
          <div className="card-header">
            <h3>Current vs Predicted Occupancy</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>8-day window</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={data.occupancy_trend}>
                <defs>
                  <linearGradient id="gradCurrent" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#4A90D9" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#4A90D9" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradPred" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#E8850A" stopOpacity={0.12} />
                    <stop offset="95%" stopColor="#E8850A" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="current" name="Occupied" stroke="#4A90D9" strokeWidth={2} fill="url(#gradCurrent)" />
                <Area type="monotone" dataKey="predicted" name="Predicted" stroke="#E8850A" strokeWidth={2} strokeDasharray="5 3" fill="url(#gradPred)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="chart-card">
          <div className="card-header">
            <h3>Department Demand (24h Forecast)</h3>
            <AIBadge />
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.forecast_summary}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="department" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="available" name="Available" fill="#4A90D9" radius={[4, 4, 0, 0]} />
                <Bar dataKey="expected_demand" name="Expected Demand" fill="#E8850A" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BedDashboard;
