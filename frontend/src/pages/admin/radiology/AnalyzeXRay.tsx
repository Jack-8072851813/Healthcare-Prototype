import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, FileUp, CheckCircle, ArrowRight, ShieldAlert,
  Play, Sparkles, RefreshCcw, Eye, Info,
} from 'lucide-react';
import { analyzeChestXRay } from '../../../services/radiologyApi';
import type { RadiologyStudy } from '../../../data/radiology/studies';
import TriageBadge from '../../../components/radiology/TriageBadge';
import AIBadge from '../../../components/rcm/AIBadge';
import XRayViewer from '../../../components/radiology/XRayViewer';

const PIPELINE_STEPS = [
  'Uploading Study',
  'Validating Image & Metadata',
  'Image Preprocessing (Unity Catalog)',
  'Running AI Model Inference (MLflow)',
  'Calculating Finding Probabilities',
  'Assigning Triage Priority Rules',
  'Completed & Pushed to Gold Table',
];

const AnalyzeXRay: React.FC = () => {
  const navigate = useNavigate();

  const [studyId, setStudyId] = useState(`CXR-2026-${Math.floor(100 + Math.random() * 900)}`);
  const [modality, setModality] = useState<'CR' | 'DX'>('CR');
  const [bodyPart, setBodyPart] = useState('CHEST');
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const [analyzing, setAnalyzing] = useState(false);
  const [activeStepIndex, setActiveStepIndex] = useState(-1);
  const [resultStudy, setResultStudy] = useState<RadiologyStudy | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setImageFile(file);
      if (file.type.startsWith('image/')) {
        setPreviewUrl(URL.createObjectURL(file));
      } else {
        setPreviewUrl(null);
      }
    }
  };

  const handleRunTriage = async () => {
    setAnalyzing(true);
    setResultStudy(null);

    // Step by step animation simulation
    for (let i = 0; i < PIPELINE_STEPS.length - 1; i++) {
      setActiveStepIndex(i);
      await new Promise(resolve => setTimeout(resolve, 350));
    }

    // Call service abstraction
    const result = await analyzeChestXRay({
      studyId,
      modality,
      bodyPart,
      imageFileName: imageFile?.name || 'synthetic_cxr.dcm',
    });

    setActiveStepIndex(PIPELINE_STEPS.length - 1);
    setResultStudy(result);
    setAnalyzing(false);
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Analyze New Chest X-Ray</h2>
          <p>Simulated Databricks AI Inference & Triage Pipeline</p>
        </div>
        <button className="btn btn-outline btn-sm" onClick={() => navigate('/admin/radiology/worklist')} type="button">
          ← Back to Worklist
        </button>
      </div>

      <div className="detail-grid">
        {/* Left Panel: Study Upload & Input Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="chart-card">
            <div className="card-header">
              <h3>Upload & Study Information</h3>
              <AIBadge text="Databricks Pipeline Ingestion" />
            </div>
            <div className="card-body">
              <div className="info-grid" style={{ marginBottom: 16 }}>
                <div className="info-item">
                  <label className="info-label">Study ID</label>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      className="search-input"
                      style={{ paddingLeft: 12, fontFamily: 'monospace' }}
                      value={studyId}
                      onChange={e => setStudyId(e.target.value)}
                    />
                    <button
                      className="btn btn-ghost btn-sm"
                      onClick={() => setStudyId(`CXR-2026-${Math.floor(100 + Math.random() * 900)}`)}
                      type="button"
                    >
                      <RefreshCcw size={12} />
                    </button>
                  </div>
                </div>

                <div className="info-item">
                  <label className="info-label">Modality</label>
                  <select
                    className="filter-select"
                    value={modality}
                    onChange={e => setModality(e.target.value as 'CR' | 'DX')}
                  >
                    <option value="CR">CR (Computed Radiography)</option>
                    <option value="DX">DX (Digital Radiography)</option>
                  </select>
                </div>

                <div className="info-item">
                  <label className="info-label">Body Part</label>
                  <input
                    className="search-input"
                    style={{ paddingLeft: 12 }}
                    value={bodyPart}
                    onChange={e => setBodyPart(e.target.value)}
                  />
                </div>

                <div className="info-item">
                  <label className="info-label">Target Model</label>
                  <span className="info-value mono" style={{ fontSize: 12, color: 'var(--primary)', paddingTop: 6 }}>
                    chest-xray-triage-v1
                  </span>
                </div>
              </div>

              {/* Upload Dropzone */}
              <div className="upload-dropzone" style={{ border: '2px dashed var(--border)', padding: 24, borderRadius: 8, textAlign: 'center', background: 'var(--bg-primary)' }}>
                <FileUp size={36} style={{ color: 'var(--primary)', marginBottom: 8 }} />
                <div style={{ fontWeight: 600, fontSize: 14 }}>Upload DICOM (.dcm) or PNG/JPG Chest X-Ray</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', margin: '4px 0 12px' }}>
                  De-identified images only. Files are stored in Unity Catalog Volume for AI preprocessing.
                </div>
                <input
                  type="file"
                  accept=".dcm,.png,.jpg,.jpeg"
                  onChange={handleFileChange}
                  id="cxr-file-input"
                  style={{ display: 'none' }}
                />
                <label htmlFor="cxr-file-input" className="btn btn-outline btn-sm" style={{ cursor: 'pointer' }}>
                  Choose Image File
                </label>
                {imageFile && (
                  <div style={{ marginTop: 10, fontSize: 12, fontWeight: 600, color: 'var(--success)' }}>
                    ✓ Selected: {imageFile.name} ({(imageFile.size / 1024).toFixed(1)} KB)
                  </div>
                )}
              </div>

              {/* Submit Action */}
              <div style={{ marginTop: 20 }}>
                <button
                  className="btn btn-primary"
                  style={{ width: '100%', justifyContent: 'center', padding: '10px 16px', fontSize: 14 }}
                  onClick={handleRunTriage}
                  disabled={analyzing}
                  type="button"
                >
                  {analyzing ? (
                    <>
                      <span className="loading-spinner-sm" />
                      Running AI Triage Pipeline...
                    </>
                  ) : (
                    <>
                      <Play size={16} /> Run AI Triage
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Interactive Preview Canvas */}
          <div className="chart-card">
            <div className="card-header">
              <h3>Image Preview</h3>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>DICOM Viewer Canvas</span>
            </div>
            <div className="card-body">
              <XRayViewer study={resultStudy} uploadedImageUrl={previewUrl} />
            </div>
          </div>
        </div>

        {/* Right Panel: Pipeline Progress & AI Triage Results */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Pipeline Execution Stages Visualizer */}
          <div className="chart-card">
            <div className="card-header">
              <h3>Databricks AI Execution Pipeline</h3>
              <Sparkles size={16} style={{ color: 'var(--primary)' }} />
            </div>
            <div className="card-body">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {PIPELINE_STEPS.map((stepName, idx) => {
                  const isDone = activeStepIndex > idx;
                  const isCurrent = activeStepIndex === idx;
                  return (
                    <div
                      key={stepName}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 10,
                        padding: '8px 12px',
                        borderRadius: 6,
                        background: isCurrent ? 'var(--primary-lightest)' : isDone ? 'var(--bg-hover)' : 'transparent',
                        border: isCurrent ? '1px solid var(--primary-lighter)' : '1px solid transparent',
                      }}
                    >
                      <div style={{ width: 22, height: 22, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 11, fontWeight: 700, background: isDone ? 'var(--success)' : isCurrent ? 'var(--primary)' : 'var(--border)', color: '#fff', flexShrink: 0 }}>
                        {isDone ? '✓' : idx + 1}
                      </div>
                      <span style={{ fontSize: 12, fontWeight: isCurrent ? 700 : 500, color: isCurrent ? 'var(--primary-dark)' : 'var(--text-primary)' }}>
                        {stepName}
                      </span>
                      {isCurrent && <span className="loading-spinner-sm" style={{ marginLeft: 'auto' }} />}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* AI Analysis Result Display Box */}
          {resultStudy ? (
            <div className="chart-card recommendation-card">
              <div className="card-header">
                <h3>AI Triage Result</h3>
                <TriageBadge priority={resultStudy.priority} />
              </div>
              <div className="card-body">
                <div style={{ background: 'var(--bg-primary)', padding: 14, borderRadius: 8, marginBottom: 14 }}>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: uppercaseLetterSpacing('0.06em'), fontWeight: 700 }}>
                    PRIMARY AI FINDING
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: resultStudy.priority === 'CRITICAL' ? 'var(--error)' : 'var(--warning)', marginTop: 4 }}>
                    {resultStudy.aiFinding}
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginTop: 2 }}>
                    Model Confidence: <span style={{ color: 'var(--primary)' }}>{resultStudy.confidenceScore}%</span>
                  </div>
                </div>

                {/* Secondary Abnormality Probabilities Breakdown */}
                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8 }}>
                    Abnormality Probability Breakdown:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
                        <span>Pneumothorax</span>
                        <span style={{ fontWeight: 700 }}>{resultStudy.probabilities.pneumothorax}%</span>
                      </div>
                      <div className="confidence-bar-track">
                        <div className="confidence-bar-fill" style={{ width: `${resultStudy.probabilities.pneumothorax}%`, background: 'var(--error)' }} />
                      </div>
                    </div>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
                        <span>Pneumonia / Lung Opacity</span>
                        <span style={{ fontWeight: 700 }}>{resultStudy.probabilities.pneumonia}%</span>
                      </div>
                      <div className="confidence-bar-track">
                        <div className="confidence-bar-fill" style={{ width: `${resultStudy.probabilities.pneumonia}%`, background: 'var(--warning)' }} />
                      </div>
                    </div>
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 }}>
                        <span>Pleural Effusion</span>
                        <span style={{ fontWeight: 700 }}>{resultStudy.probabilities.pleuralEffusion}%</span>
                      </div>
                      <div className="confidence-bar-track">
                        <div className="confidence-bar-fill" style={{ width: `${resultStudy.probabilities.pleuralEffusion}%`, background: '#3182ce' }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Inference metadata */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', paddingTop: 10, borderTop: '1px solid var(--border-light)' }}>
                  <span>Model: <strong>{resultStudy.modelVersion}</strong></span>
                  <span>Inference Time: <strong>{resultStudy.inferenceTimeSeconds}s</strong></span>
                </div>

                {/* Clinical Notice per Requirement 8 */}
                <div style={{ marginTop: 14, background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 6, padding: 10, display: 'flex', gap: 8, fontSize: 11, color: '#873800' }}>
                  <Info size={16} style={{ flexShrink: 0, marginTop: 1 }} />
                  <span>
                    <strong>Clinical Notice:</strong> AI-generated triage recommendation. Final image interpretation and clinical decision must be performed by a qualified radiologist.
                  </span>
                </div>

                <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ flex: 1, justifyContent: 'center' }}
                    onClick={() => navigate(`/admin/radiology/studies/${resultStudy.id}`)}
                    type="button"
                  >
                    Open Study Detail View <ArrowRight size={14} />
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div className="chart-card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 260, textAlign: 'center' }}>
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>
                <Upload size={32} style={{ opacity: 0.5, marginBottom: 8 }} />
                <p>Click <strong>"Run AI Triage"</strong> to simulate Databricks inference and view triage prediction.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

function uppercaseLetterSpacing(val: string) {
  return { letterSpacing: val } as unknown as string;
}

export default AnalyzeXRay;
