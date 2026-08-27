import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, LineChart, Line,
} from 'recharts';
import { fetchModelPerformanceMetrics } from '../../../services/radiologyApi';
import type { ModelPerformanceMetric } from '../../../data/radiology/studies';
import AIBadge from '../../../components/rcm/AIBadge';
import { Activity, ShieldAlert, Award, FileText, CheckCircle2 } from 'lucide-react';

const ModelPerformance: React.FC = () => {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<ModelPerformanceMetric[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchModelPerformanceMetrics().then(data => {
      setMetrics(data);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return <div className="page-loading"><div className="loading-spinner" /><p>Loading performance metrics…</p></div>;
  }

  const chartData = metrics.map(m => ({
    name: m.finding.replace(' / Lung Opacity', ''),
    Sensitivity: Math.round(m.sensitivity * 100),
    Specificity: Math.round(m.specificity * 100),
    Precision: Math.round(m.precision * 100),
    F1: Math.round(m.f1Score * 100),
    AUROC: Math.round(m.auroc * 100),
  }));

  const totalAnalyzed = metrics.reduce((acc, m) => acc + m.sampleCount, 0);
  const totalTP = metrics.reduce((acc, m) => acc + m.truePositives, 0);
  const totalFP = metrics.reduce((acc, m) => acc + m.falsePositives, 0);
  const totalFN = metrics.reduce((acc, m) => acc + m.falseNegatives, 0);

  return (
    <div>
      <div className="page-header">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2>AI Model Performance & Evaluation</h2>
            <span className="risk-badge risk-medium" style={{ fontSize: 11 }}>
              Prototype / Sample Metrics
            </span>
          </div>
          <p>Validation performance across target Chest X-Ray findings (DenseNet-121 / Databricks MLflow)</p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/worklist')} type="button">
          ← Back to Worklist
        </button>
      </div>

      {/* Mandatory Demo Metric Notice per Requirement 11 */}
      <div className="alert-banner alert-banner-warning" style={{ marginBottom: 20 }}>
        <ShieldAlert size={18} />
        <span>
          <strong>Prototype Evaluation Notice:</strong> The metrics below are sample validation values from model experiment tracking. They demonstrate performance monitoring capabilities and are not validated clinical diagnostic metrics.
        </span>
      </div>

      {/* Overview KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><FileText size={22} /></div>
            <span className="kpi-trend up">MLflow</span>
          </div>
          <div className="kpi-value">{totalAnalyzed.toLocaleString()}</div>
          <div className="kpi-label">Validation Studies Analyzed</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon green"><Award size={22} /></div>
            <span className="kpi-trend up">94.2%</span>
          </div>
          <div className="kpi-value">94%</div>
          <div className="kpi-label">Radiologist Agreement Rate</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon amber"><Activity size={22} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--warning)' }}>{totalFP}</div>
          <div className="kpi-label">False-Positive Count</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon red"><ShieldAlert size={22} /></div>
          </div>
          <div className="kpi-value" style={{ color: 'var(--error)' }}>{totalFN}</div>
          <div className="kpi-label">False-Negative Count</div>
        </div>
      </div>

      {/* Performance Metric Comparison Chart */}
      <div className="chart-grid" style={{ gridTemplateColumns: '1.5fr 1fr', marginBottom: 20 }}>
        <div className="chart-card">
          <div className="card-header">
            <h3>Metric Comparison by Finding (%)</h3>
            <AIBadge text="MLflow Model Validation" />
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis domain={[70, 100]} tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Sensitivity" fill="#4A90D9" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Specificity" fill="#5AAFA5" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Precision" fill="#E8850A" radius={[4, 4, 0, 0]} />
                <Bar dataKey="F1" fill="#9F7AEA" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* AUROC Performance Chart */}
        <div className="chart-card">
          <div className="card-header">
            <h3>ROC Area Under Curve (AUROC)</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Target ≥ 0.95</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis type="number" domain={[85, 100]} tick={{ fontSize: 12, fill: '#8796A9' }} />
                <YAxis dataKey="name" type="category" tick={{ fontSize: 12, fill: '#8796A9' }} width={120} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid var(--border)' }} />
                <Bar dataKey="AUROC" fill="#48BB78" radius={[0, 4, 4, 0]} name="AUROC Score (%)" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Detailed Performance Breakdown Table per Requirement 11 */}
      <div className="chart-card">
        <div className="card-header">
          <h3>Detailed Metrics Breakdown</h3>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>chest-xray-triage-v1</span>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Target Finding</th>
                <th>Sensitivity</th>
                <th>Specificity</th>
                <th>Precision</th>
                <th>Recall</th>
                <th>F1 Score</th>
                <th>AUROC</th>
                <th>TP</th>
                <th>FP</th>
                <th>FN</th>
                <th>TN</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map(m => (
                <tr key={m.finding}>
                  <td style={{ fontWeight: 600 }}>{m.finding}</td>
                  <td style={{ fontWeight: 700, color: 'var(--primary)' }}>{(m.sensitivity * 100).toFixed(1)}%</td>
                  <td>{(m.specificity * 100).toFixed(1)}%</td>
                  <td>{(m.precision * 100).toFixed(1)}%</td>
                  <td>{(m.recall * 100).toFixed(1)}%</td>
                  <td style={{ fontWeight: 600 }}>{(m.f1Score * 100).toFixed(1)}%</td>
                  <td style={{ fontWeight: 700, color: 'var(--success)' }}>{m.auroc.toFixed(3)}</td>
                  <td style={{ color: 'var(--success)' }}>{m.truePositives}</td>
                  <td style={{ color: 'var(--warning)' }}>{m.falsePositives}</td>
                  <td style={{ color: 'var(--error)' }}>{m.falseNegatives}</td>
                  <td>{m.trueNegatives}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ModelPerformance;
