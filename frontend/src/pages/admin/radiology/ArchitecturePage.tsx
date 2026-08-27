import React from 'react';
import { useNavigate as useNavigateDom } from 'react-router-dom';
import { Cpu, HardDrive, ShieldCheck, Database, Layers, ArrowRight, Activity, Server, AlertCircle } from 'lucide-react';
import AIBadge from '../../../components/rcm/AIBadge';

const ArchitecturePage: React.FC = () => {
  const navigate = useNavigateDom();

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>System Architecture Overview</h2>
          <p>Comparison between Proof of Concept (PoC) and Future Production PACS/RIS Integration</p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/worklist')} type="button">
          ← Back to Worklist
        </button>
      </div>

      {/* Notice Banner */}
      <div className="alert-banner alert-banner-warning" style={{ marginBottom: 24 }}>
        <AlertCircle size={18} />
        <span>
          <strong>Architecture Scope Notice:</strong> The current system operates as a stand-alone Proof of Concept (PoC) using synthetic DICOM data. Production PACS/RIS integration requires secure DICOM routers and enterprise EHR connectors.
        </span>
      </div>

      {/* Architecture Card 1: PoC Architecture per Requirement 13 */}
      <div className="chart-card" style={{ marginBottom: 24, borderTop: '4px solid var(--primary)' }}>
        <div className="card-header">
          <div>
            <h3 style={{ margin: 0 }}>1. Current Proof of Concept (PoC) Architecture</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Demonstration Environment</span>
          </div>
          <span className="status-pill status-approved">Active Prototype</span>
        </div>
        <div className="card-body">
          <div className="architecture-flow" style={{ display: 'flex', alignItems: 'center', gap: 12, overflowX: 'auto', padding: '16px 8px' }}>
            <div className="arch-node" style={{ background: '#EBF8FF', border: '1.5px solid #3182CE', borderRadius: 8, padding: 14, minWidth: 160, textAlign: 'center' }}>
              <HardDrive size={24} style={{ color: '#3182CE', marginBottom: 6 }} />
              <div style={{ fontWeight: 700, fontSize: 13 }}>Public / De-identified DICOM Dataset</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Synthetic Studies</div>
            </div>

            <ArrowRight size={20} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#E6F6EE', border: '1.5px solid #38A169', borderRadius: 8, padding: 14, minWidth: 160, textAlign: 'center' }}>
              <Database size={24} style={{ color: '#38A169', marginBottom: 6 }} />
              <div style={{ fontWeight: 700, fontSize: 13 }}>Databricks Platform</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Unity Catalog Volume</div>
            </div>

            <ArrowRight size={20} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#FEF3E2', border: '1.5px solid #E8850A', borderRadius: 8, padding: 14, minWidth: 160, textAlign: 'center' }}>
              <Cpu size={24} style={{ color: '#E8850A', marginBottom: 6 }} />
              <div style={{ fontWeight: 700, fontSize: 13 }}>Deep Learning Model</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>MLflow Inference Engine</div>
            </div>

            <ArrowRight size={20} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#FDE8E8', border: '1.5px solid #E53E3E', borderRadius: 8, padding: 14, minWidth: 160, textAlign: 'center' }}>
              <ShieldCheck size={24} style={{ color: '#E53E3E', marginBottom: 6 }} />
              <div style={{ fontWeight: 700, fontSize: 13 }}>Triage Results</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Gold Delta Table</div>
            </div>

            <ArrowRight size={20} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#FAF5FF', border: '1.5px solid #805AD5', borderRadius: 8, padding: 14, minWidth: 160, textAlign: 'center' }}>
              <Layers size={24} style={{ color: '#805AD5', marginBottom: 6 }} />
              <div style={{ fontWeight: 700, fontSize: 13 }}>Prototype Dashboard</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Meridian UI</div>
            </div>
          </div>
        </div>
      </div>

      {/* Architecture Card 2: Future Production Architecture per Requirement 13 */}
      <div className="chart-card" style={{ borderTop: '4px solid #38A169' }}>
        <div className="card-header">
          <div>
            <h3 style={{ margin: 0 }}>2. Future Production Integration Concept</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Hospital PACS / RIS Integration Blueprint</span>
          </div>
          <span className="risk-badge risk-low" style={{ fontSize: 11 }}>
            Future Integration Concept
          </span>
        </div>
        <div className="card-body">
          <div className="architecture-flow" style={{ display: 'flex', alignItems: 'center', gap: 10, overflowX: 'auto', padding: '16px 8px' }}>
            <div className="arch-node" style={{ background: '#EDF2F7', border: '1.5px solid #718096', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
              <Server size={22} style={{ color: '#4A5568', marginBottom: 4 }} />
              <div style={{ fontWeight: 700, fontSize: 12 }}>Hospital X-Ray Machine</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Modality Stream</div>
            </div>

            <ArrowRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#EBF8FF', border: '1.5px solid #3182CE', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
              <Database size={22} style={{ color: '#3182CE', marginBottom: 4 }} />
              <div style={{ fontWeight: 700, fontSize: 12 }}>Hospital PACS / RIS</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>DICOM Archive</div>
            </div>

            <ArrowRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#E6F6EE', border: '1.5px solid #38A169', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
              <ShieldCheck size={22} style={{ color: '#38A169', marginBottom: 4 }} />
              <div style={{ fontWeight: 700, fontSize: 12 }}>Secure Integration Layer</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>HL7 / DICOM Router</div>
            </div>

            <ArrowRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#FEF3E2', border: '1.5px solid #E8850A', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
              <Cpu size={22} style={{ color: '#E8850A', marginBottom: 4 }} />
              <div style={{ fontWeight: 700, fontSize: 12 }}>Databricks AI Platform</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Serving Endpoints</div>
            </div>

            <ArrowRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#FDE8E8', border: '1.5px solid #E53E3E', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
              <Activity size={22} style={{ color: '#E53E3E', marginBottom: 4 }} />
              <div style={{ fontWeight: 700, fontSize: 12 }}>AI Triage Result</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Priority Queue Event</div>
            </div>

            <ArrowRight size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />

            <div className="arch-node" style={{ background: '#FAF5FF', border: '1.5px solid #805AD5', borderRadius: 8, padding: 12, minWidth: 140, textAlign: 'center' }}>
              <Layers size={22} style={{ color: '#805AD5', marginBottom: 4 }} />
              <div style={{ fontWeight: 700, fontSize: 12 }}>Radiology Worklist</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>Radiologist Station</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ArchitecturePage;
