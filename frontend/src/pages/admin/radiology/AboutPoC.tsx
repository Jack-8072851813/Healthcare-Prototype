import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Info, ShieldAlert, CheckCircle2, Cpu, FileText, Layers } from 'lucide-react';
import AIBadge from '../../../components/rcm/AIBadge';

const AboutPoC: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>About Meridian AI Radiology Triage Assistant</h2>
          <p>Proof of Concept Overview & Evaluation Guidelines</p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/worklist')} type="button">
          ← Back to Worklist
        </button>
      </div>

      {/* Mandatory Evaluation Disclaimer per Requirement 16 */}
      <div className="alert-banner alert-banner-critical" style={{ marginBottom: 24 }}>
        <ShieldAlert size={20} />
        <div>
          <strong>Important Clinical Evaluation Notice:</strong> This prototype is designed for demonstration and technological feasibility evaluation only. It is NOT an independently validated or cleared diagnostic medical system and must NOT be used for direct patient diagnostic decision-making without qualified radiologist interpretation.
        </div>
      </div>

      <div className="detail-grid">
        {/* Core Overview */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="chart-card">
            <div className="card-header">
              <h3>Project Objective & Scope</h3>
              <AIBadge text="Clinical Decision Support Prototype" />
            </div>
            <div className="card-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14, fontSize: 13, lineHeight: 1.6 }}>
                <div>
                  <h4 style={{ margin: '0 0 4px', color: 'var(--primary-dark)', fontSize: 14 }}>1. Primary Objective</h4>
                  <p style={{ margin: 0, color: 'var(--text-secondary)' }}>
                    To demonstrate how AI-assisted triage analysis of Chest X-Rays can prioritize potentially urgent radiology studies (such as Pneumothorax or severe Pneumonia) so that radiologists review high-risk cases earlier than routine chronological arrivals.
                  </p>
                </div>

                <div>
                  <h4 style={{ margin: '0 0 4px', color: 'var(--primary-dark)', fontSize: 14 }}>2. Target AI Findings Supported</h4>
                  <ul style={{ margin: '4px 0 0', paddingLeft: 20, color: 'var(--text-secondary)' }}>
                    <li><strong>Pneumothorax</strong> — Apical visceral pleural line detection / pleural air space</li>
                    <li><strong>Pneumonia / Lung Opacity</strong> — Focal, multifocal, or lobar lung consolidations</li>
                    <li><strong>Pleural Effusion</strong> — Costophrenic angle blunting & fluid collection</li>
                    <li><strong>No Urgent Finding</strong> — Normal radiograph appearance or minor chronic changes</li>
                  </ul>
                </div>

                <div>
                  <h4 style={{ margin: '0 0 4px', color: 'var(--primary-dark)', fontSize: 14 }}>3. Triage Priority Tiers</h4>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 6 }}>
                    <span className="triage-badge triage-critical">CRITICAL — Immediate Priority</span>
                    <span className="triage-badge triage-high">HIGH — Expedited Review</span>
                    <span className="triage-badge triage-routine">ROUTINE — Standard Queue</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="chart-card">
            <div className="card-header">
              <h3>Human-in-the-Loop Clinical Workflow</h3>
              <CheckCircle2 size={16} style={{ color: 'var(--success)' }} />
            </div>
            <div className="card-body">
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
                The core principle of the Meridian AI Radiology Triage Assistant is <strong>Clinical Decision Support (CDS)</strong>. The AI model acts exclusively as an automated worklist sorter. The final clinical interpretation, reporting, and diagnostic sign-off always remain with the certified radiologist.
              </p>
            </div>
          </div>
        </div>

        {/* Right Column: Platform & Stage details */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="chart-card">
            <div className="card-header">
              <h3>Technology Platform</h3>
              <Cpu size={16} style={{ color: 'var(--primary)' }} />
            </div>
            <div className="card-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 13 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 8 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Platform Architecture:</span>
                  <span style={{ fontWeight: 600 }}>Databricks Data Intelligence</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 8 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Data Governance:</span>
                  <span style={{ fontWeight: 600 }}>Unity Catalog Volumes</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 8 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Model Tracking:</span>
                  <span style={{ fontWeight: 600 }}>MLflow Model Registry</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-light)', paddingBottom: 8 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Table Architecture:</span>
                  <span style={{ fontWeight: 600 }}>Delta Lake Medallion (Bronze/Silver/Gold)</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Current Stage:</span>
                  <span className="status-pill status-review">Proof of Concept (PoC)</span>
                </div>
              </div>
            </div>
          </div>

          <div className="chart-card">
            <div className="card-header">
              <h3>Demo Navigation Quick Links</h3>
              <Layers size={16} />
            </div>
            <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/worklist')} style={{ justifyContent: 'flex-start' }} type="button">
                ▸ View AI Radiology Worklist
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/analyze')} style={{ justifyContent: 'flex-start' }} type="button">
                ▸ Analyze New Chest X-Ray
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/performance')} style={{ justifyContent: 'flex-start' }} type="button">
                ▸ View AI Model Performance Metrics
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/pipeline')} style={{ justifyContent: 'flex-start' }} type="button">
                ▸ View Databricks AI Pipeline Diagram
              </button>
              <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/architecture')} style={{ justifyContent: 'flex-start' }} type="button">
                ▸ View PACS/RIS Architecture Comparison
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AboutPoC;
