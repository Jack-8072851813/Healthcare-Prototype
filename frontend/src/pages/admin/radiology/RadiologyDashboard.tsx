import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FileText, AlertCircle, AlertTriangle, CheckCircle, Clock,
  ArrowRight, Upload, RefreshCw, Cpu, Activity, ShieldCheck,
} from 'lucide-react';
import {
  fetchRadiologyDashboard,
  fetchRadiologyStudies,
} from '../../../services/radiologyApi';
import type { RadiologyDashboardSummary, RadiologyStudy } from '../../../data/radiology/studies';
import TriageBadge from '../../../components/radiology/TriageBadge';
import AIBadge from '../../../components/rcm/AIBadge';

const RadiologyDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [summary, setSummary] = useState<RadiologyDashboardSummary | null>(null);
  const [recentStudies, setRecentStudies] = useState<RadiologyStudy[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = async () => {
    setLoading(true);
    const [sumData, studiesData] = await Promise.all([
      fetchRadiologyDashboard(),
      fetchRadiologyStudies(),
    ]);
    setSummary(sumData);
    setRecentStudies(studiesData.slice(0, 7));
    setLoading(false);
  };

  useEffect(() => {
    loadData();
  }, []);

  if (loading || !summary) {
    return (
      <div className="page-loading">
        <div className="loading-spinner" />
        <p>Loading Radiology Triage Data…</p>
      </div>
    );
  }

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2>Meridian AI Radiology Triage Assistant</h2>
            <AIBadge text="Clinical Decision Support · Radiologist Interpretation Required" />
          </div>
          <p>AI-Assisted Chest X-Ray Worklist Prioritization & Triage</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-outline btn-sm" onClick={loadData} type="button">
            <RefreshCw size={14} /> Refresh
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => navigate('/admin/radiology/analyze')}
            type="button"
          >
            <Upload size={14} /> Analyze New X-Ray
          </button>
        </div>
      </div>

      {/* Clinical Disclaimer Banner */}
      <div className="alert-banner alert-banner-warning" style={{ marginBottom: 20 }}>
        <ShieldCheck size={18} />
        <span>
          <strong>Clinical Triage Protocol Notice:</strong> AI findings prioritize urgent studies for radiologist review. All final interpretations and clinical diagnoses remain the sole responsibility of the qualified radiologist.
        </span>
      </div>

      {/* Summary Cards */}
      <div className="kpi-grid">
        <div className="kpi-card clickable" onClick={() => navigate('/admin/radiology/worklist?priority=All')}>
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><FileText size={22} /></div>
            <span className="kpi-trend up">Live</span>
          </div>
          <div className="kpi-value">{summary.totalStudies}</div>
          <div className="kpi-label">Total Studies</div>
        </div>

        <div className="kpi-card clickable" onClick={() => navigate('/admin/radiology/worklist?priority=CRITICAL')}>
          <div className="kpi-card-header">
            <div className="kpi-icon red"><AlertCircle size={22} /></div>
            <span className="kpi-trend down" style={{ color: 'var(--error)' }}>
              {Math.round((summary.critical / summary.totalStudies) * 100)}%
            </span>
          </div>
          <div className="kpi-value" style={{ color: 'var(--error)' }}>{summary.critical}</div>
          <div className="kpi-label">Critical Studies</div>
        </div>

        <div className="kpi-card clickable" onClick={() => navigate('/admin/radiology/worklist?priority=HIGH')}>
          <div className="kpi-card-header">
            <div className="kpi-icon amber"><AlertTriangle size={22} /></div>
            <span className="kpi-trend down" style={{ color: 'var(--warning)' }}>High Priority</span>
          </div>
          <div className="kpi-value" style={{ color: 'var(--warning)' }}>{summary.high}</div>
          <div className="kpi-label">High Priority</div>
        </div>

        <div className="kpi-card clickable" onClick={() => navigate('/admin/radiology/worklist?priority=ROUTINE')}>
          <div className="kpi-card-header">
            <div className="kpi-icon green"><CheckCircle size={22} /></div>
            <span className="kpi-trend up"><Activity size={14} /> Normal</span>
          </div>
          <div className="kpi-value">{summary.routine}</div>
          <div className="kpi-label">Routine</div>
        </div>

        <div className="kpi-card clickable" onClick={() => navigate('/admin/radiology/worklist?priority=Awaiting+Analysis')}>
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><Clock size={22} /></div>
            <span className="kpi-trend up">In Queue</span>
          </div>
          <div className="kpi-value">{summary.awaitingAnalysis}</div>
          <div className="kpi-label">Awaiting AI Analysis</div>
        </div>
      </div>

      {/* Main Content Grid: Urgent Worklist Preview + Architecture Quick View */}
      <div className="chart-grid" style={{ gridTemplateColumns: '1.8fr 1fr' }}>
        {/* Urgent Worklist Preview Table */}
        <div className="chart-card">
          <div className="card-header">
            <div>
              <h3 style={{ margin: 0 }}>Priority Triage Worklist</h3>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Sorted by Critical → High → Routine
              </span>
            </div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => navigate('/admin/radiology/worklist')}
              type="button"
            >
              Full Worklist <ArrowRight size={14} />
            </button>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Study ID</th>
                  <th>Modality</th>
                  <th>AI Finding</th>
                  <th>Confidence</th>
                  <th>Study Time</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {recentStudies.map(s => (
                  <tr
                    key={s.id}
                    className="clickable-row"
                    onClick={() => navigate(`/admin/radiology/studies/${s.id}`)}
                  >
                    <td><TriageBadge priority={s.priority} size="sm" /></td>
                    <td><span className="mono link-text">{s.id}</span></td>
                    <td><span className="category-tag">{s.modality}</span></td>
                    <td style={{ fontWeight: 600 }}>{s.aiFinding}</td>
                    <td>
                      {s.confidenceScore > 0 ? (
                        <span style={{
                          fontWeight: 700,
                          color: s.priority === 'CRITICAL' ? 'var(--error)' : s.priority === 'HIGH' ? 'var(--warning)' : 'var(--success)'
                        }}>
                          {s.confidenceScore}%
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{s.studyTime}</td>
                    <td>
                      <button className="btn btn-ghost btn-sm" type="button">Review</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Databricks AI Engine Card */}
        <div className="chart-card">
          <div className="card-header">
            <h3>Databricks AI Engine</h3>
            <AIBadge text="v1.0 MLflow" />
          </div>
          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="info-box" style={{ background: 'var(--bg-primary)', padding: 12, borderRadius: 8, border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
                <Cpu size={16} style={{ color: 'var(--primary)' }} />
                <span>Databricks Unity Catalog & MLflow</span>
              </div>
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
                Studies are ingested into Unity Catalog Volumes, preprocessed, and scored by MLflow registered deep learning models for rapid triage.
              </p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Model Architecture:</span>
                <span style={{ fontWeight: 600 }}>DenseNet-121 / ResNet50</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Avg Inference Speed:</span>
                <span style={{ fontWeight: 600, color: 'var(--success)' }}>1.8 seconds</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Radiologist Agreement Rate:</span>
                <span style={{ fontWeight: 600 }}>{summary.agreementRate}%</span>
              </div>
            </div>

            <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => navigate('/admin/radiology/pipeline')}
                style={{ width: '100%', justifyContent: 'center' }}
                type="button"
              >
                View Databricks AI Pipeline
              </button>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => navigate('/admin/radiology/performance')}
                style={{ width: '100%', justifyContent: 'center' }}
                type="button"
              >
                View Model Performance Metrics
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RadiologyDashboard;
