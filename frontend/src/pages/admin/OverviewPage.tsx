import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, BedDouble, AlertTriangle, CheckCircle, ArrowRight,
  TrendingUp, Activity, IndianRupee, Users,
} from 'lucide-react';
import { fetchRCMDashboard, fetchBedDashboard } from '../../services/api';
import type { RCMDashboardData, BedDashboardData } from '../../services/api';
import { useDemoRole } from '../../context/RoleContext';
import RiskBadge from '../../components/rcm/RiskBadge';
import OccupancyBar from '../../components/beds/OccupancyBar';
import AIBadge from '../../components/rcm/AIBadge';
import type { RiskLevel } from '../../data/rcm/claims';

interface KpiItem { label: string; value: string | number; icon: React.ReactNode; color: string; }
interface ModuleAlert { text: string; type: 'critical' | 'warning'; }

interface ModuleDef {
  key: string;
  title: string;
  icon: React.ReactNode;
  accentColor: string;
  description: string;
  kpis: KpiItem[];
  alerts: ModuleAlert[];
  primaryAction: { label: string; path: string };
  secondaryAction: { label: string; path: string };
}

const ROLE_CONFIG = {
  admin:          { greeting: 'Hospital Administrator', accent: '#4A90D9' },
  billing:        { greeting: 'Billing Executive',      accent: '#E8850A' },
  'bed-manager':  { greeting: 'Bed Manager',            accent: '#5AAFA5' },
};

const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const { demoRole } = useDemoRole();
  const [rcm, setRcm] = useState<RCMDashboardData | null>(null);
  const [beds, setBeds] = useState<BedDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchRCMDashboard(), fetchBedDashboard()]).then(([r, b]) => {
      setRcm(r); setBeds(b); setLoading(false);
    });
  }, []);

  const hour = new Date().getHours();
  const timeGreet = hour < 12 ? 'Good Morning' : hour < 17 ? 'Good Afternoon' : 'Good Evening';
  const { greeting, accent } = ROLE_CONFIG[demoRole];

  if (loading || !rcm || !beds) {
    return <div className="page-loading"><div className="loading-spinner" /><p>Loading overview…</p></div>;
  }

  const leakageLakh = (rcm.potential_revenue_leakage / 100000).toFixed(2);
  const bedShortageAlerts = beds.forecast_summary.filter(
    (e: { shortage: number }) => e.shortage > 0
  ) as Array<{ department: string; shortage: number; available: number; expected_demand: number }>;

  const rcmHighRisk = rcm.high_risk_claims as Array<{
    id: string; patient_name: string; insurance_provider: string;
    amount: number; risk_level: string; risk_score: number;
  }>;

  const modules: ModuleDef[] = [
    {
      key: 'rcm',
      title: 'Revenue Cycle Management',
      icon: <FileText size={28} style={{ color: '#E8850A' }} />,
      accentColor: '#E8850A',
      description: 'AI-powered claim risk scoring, validation, and revenue leakage detection',
      kpis: [
        { label: 'Total Claims',  value: rcm.total_claims.toLocaleString(), icon: <FileText size={16} />,   color: '#4A90D9' },
        { label: 'At Risk',       value: rcm.claims_at_risk,                icon: <AlertTriangle size={16} />, color: '#F56565' },
        { label: 'Leakage',       value: `₹${leakageLakh}L`,               icon: <IndianRupee size={16} />,  color: '#E8850A' },
        { label: 'First Pass %',  value: `${rcm.first_pass_acceptance_rate}%`, icon: <CheckCircle size={16} />, color: '#48BB78' },
      ],
      alerts: rcmHighRisk.filter(c => c.risk_level === 'Critical').slice(0, 3).map(c => ({
        text: `${c.id} — ${c.patient_name} — Critical risk (${c.risk_score}/100)`,
        type: 'critical' as const,
      })),
      primaryAction:   { label: 'Open RCM Dashboard', path: '/admin/revenue-cycle' },
      secondaryAction: { label: 'View All Claims',     path: '/admin/revenue-cycle/claims' },
    },
    {
      key: 'beds',
      title: 'Predictive Bed Allocation',
      icon: <BedDouble size={28} style={{ color: '#5AAFA5' }} />,
      accentColor: '#5AAFA5',
      description: 'Real-time occupancy monitoring and AI-powered admission surge forecasting',
      kpis: [
        { label: 'Total Beds', value: beds.total_beds,       icon: <BedDouble size={16} />,     color: '#4A90D9' },
        { label: 'Occupied',   value: beds.occupied,         icon: <Users size={16} />,         color: '#F56565' },
        { label: 'Available',  value: beds.available,        icon: <BedDouble size={16} />,     color: '#48BB78' },
        { label: 'Occupancy',  value: `${beds.occupancy_rate}%`, icon: <Activity size={16} />, color: '#E8850A' },
      ],
      alerts: bedShortageAlerts.slice(0, 3).map(a => ({
        text: `${a.department}: predicted shortage of ${a.shortage} bed(s) in 24h`,
        type: 'warning' as const,
      })),
      primaryAction:   { label: 'Open Bed Dashboard', path: '/admin/bed-allocation' },
      secondaryAction: { label: 'View Forecast',       path: '/admin/bed-allocation/forecast' },
    },
  ];

  const orderedModules = demoRole === 'bed-manager' ? [modules[1], modules[0]] : modules;

  const combinedAlerts: ModuleAlert[] = [
    ...rcmHighRisk.filter(c => c.risk_level === 'Critical').slice(0, 2).map(c => ({
      type: 'critical' as const,
      text: `Critical claim: ${c.id} — ${c.patient_name} (₹${(c.amount / 1000).toFixed(0)}K, ${c.insurance_provider})`,
    })),
    ...bedShortageAlerts.map(a => ({
      type: 'warning' as const,
      text: `Bed shortage: ${a.department} — ${a.shortage} bed(s) needed in 24h forecast`,
    })),
  ];

  const bedDepts = beds.departments as Array<{ name: string; occupied: number; total_beds: number }>;

  return (
    <div>
      {/* Hero Welcome */}
      <div className="overview-hero" style={{ borderLeftColor: accent }}>
        <div>
          <h2>{timeGreet}, <span style={{ color: accent }}>{greeting}</span></h2>
          <p>Here's a combined AI intelligence summary across Revenue Cycle and Bed Allocation</p>
        </div>
        <AIBadge />
      </div>

      {/* Combined Alerts Feed */}
      {combinedAlerts.length > 0 && (
        <div className="alert-banner-list">
          {combinedAlerts.map((a: ModuleAlert, i: number) => (
            <div key={i} className={`alert-banner ${a.type === 'critical' ? 'alert-banner-critical' : 'alert-banner-warning'}`}>
              <AlertTriangle size={16} />
              <span>{a.text}</span>
            </div>
          ))}
        </div>
      )}

      {/* Module Cards */}
      <div className="overview-modules-grid">
        {orderedModules.map((mod: ModuleDef) => (
          <div key={mod.key} className="overview-module-card" style={{ borderTopColor: mod.accentColor }}>
            <div className="overview-module-header">
              {mod.icon}
              <div>
                <h3 style={{ fontSize: 17, fontWeight: 700, margin: 0 }}>{mod.title}</h3>
                <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 0' }}>{mod.description}</p>
              </div>
            </div>

            {/* KPIs */}
            <div className="overview-kpi-row">
              {mod.kpis.map((k: KpiItem) => (
                <div key={k.label} className="overview-kpi-mini">
                  <span style={{ color: k.color }}>{k.icon}</span>
                  <div>
                    <div style={{ fontSize: 18, fontWeight: 700 }}>{k.value}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{k.label}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* Mini Alerts */}
            {mod.alerts.length > 0 && (
              <div style={{ margin: '12px 0', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {mod.alerts.map((a: ModuleAlert, i: number) => (
                  <div key={i} className={`mini-alert ${a.type === 'critical' ? 'mini-alert-critical' : 'mini-alert-warning'}`}>
                    <AlertTriangle size={12} />
                    <span style={{ fontSize: 12 }}>{a.text}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Beds module — occupancy bars */}
            {mod.key === 'beds' && (
              <div style={{ margin: '12px 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {bedDepts.map((dept: { name: string; occupied: number; total_beds: number }) => (
                  <OccupancyBar key={dept.name} occupied={dept.occupied} total={dept.total_beds} label={dept.name} />
                ))}
              </div>
            )}

            {/* RCM module — high-risk claims mini table */}
            {mod.key === 'rcm' && (
              <div className="mini-table" style={{ margin: '12px 0' }}>
                <div className="mini-table-head">
                  <span>Claim ID</span><span>Patient</span><span>Risk</span>
                </div>
                {rcmHighRisk.slice(0, 4).map(c => (
                  <div key={c.id} className="mini-table-row clickable" onClick={() => navigate(`/admin/revenue-cycle/claims/${c.id}`)}>
                    <span className="mono">{c.id}</span>
                    <span>{c.patient_name}</span>
                    <RiskBadge level={c.risk_level as RiskLevel} score={c.risk_score} size="sm" />
                  </div>
                ))}
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 'auto', paddingTop: 12 }}>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => navigate(mod.primaryAction.path)}
                style={{ background: mod.accentColor, borderColor: mod.accentColor }}
              >
                {mod.primaryAction.label} <ArrowRight size={14} />
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => navigate(mod.secondaryAction.path)}>
                {mod.secondaryAction.label}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default OverviewPage;
