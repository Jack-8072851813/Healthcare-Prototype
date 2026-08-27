import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, CheckCircle2, XCircle, AlertTriangle, ShieldCheck,
  User, Hash, CalendarDays, Clock, FileText, Send, Sparkles,
} from 'lucide-react';
import { fetchRadiologyStudy, submitRadiologistFeedback } from '../../../services/radiologyApi';
import type { RadiologyStudy, ReviewStatus } from '../../../data/radiology/studies';
import TriageBadge from '../../../components/radiology/TriageBadge';
import XRayViewer from '../../../components/radiology/XRayViewer';
import AIBadge from '../../../components/rcm/AIBadge';

const StudyDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [study, setStudy] = useState<RadiologyStudy | null>(null);
  const [loading, setLoading] = useState(true);

  // Radiologist feedback form state
  const [selectedReview, setSelectedReview] = useState<ReviewStatus>('Agree');
  const [comments, setComments] = useState('');
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackSuccess, setFeedbackSuccess] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchRadiologyStudy(id).then(s => {
      setStudy(s);
      if (s?.feedback?.status && s.feedback.status !== 'Unreviewed') {
        setSelectedReview(s.feedback.status);
        setComments(s.feedback.comments || '');
      }
      setLoading(false);
    });
  }, [id]);

  const handleFeedbackSubmit = async () => {
    if (!id) return;
    setSubmittingFeedback(true);
    const updated = await submitRadiologistFeedback(id, {
      status: selectedReview,
      comments: comments || undefined,
    });
    if (updated) {
      setStudy(updated);
      setFeedbackSuccess(true);
      setTimeout(() => setFeedbackSuccess(false), 4000);
    }
    setSubmittingFeedback(false);
  };

  if (loading) {
    return <div className="page-loading"><div className="loading-spinner" /><p>Loading Chest X-Ray study…</p></div>;
  }

  if (!study) {
    return (
      <div className="page-loading">
        <p>Radiology Study not found.</p>
        <button className="btn btn-primary" onClick={() => navigate('/admin/radiology/worklist')}>
          ← Return to Worklist
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)} type="button">
            <ArrowLeft size={16} />
          </button>
          <div>
            <h2>Study Detail — <span className="mono">{study.id}</span></h2>
            <p>Chest X-Ray DICOM Review & AI Triage Analysis</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <AIBadge text="AI Triage Recommendation" />
          <TriageBadge priority={study.priority} />
        </div>
      </div>

      {/* Two-Panel Layout */}
      <div className="detail-grid">
        {/* Left Panel: Interactive DICOM Chest X-Ray Viewer */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="chart-card">
            <div className="card-header">
              <h3>Chest X-Ray Viewer</h3>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                Patient ID: <strong className="mono">{study.patientId}</strong>
              </span>
            </div>
            <div className="card-body">
              <XRayViewer study={study} />
            </div>
          </div>

          {/* Patient & Study Metadata */}
          <div className="chart-card">
            <div className="card-header">
              <h3>Study Metadata</h3>
              <span className="category-tag">{study.modality}</span>
            </div>
            <div className="card-body">
              <div className="info-grid">
                <div className="info-item">
                  <span className="info-label"><Hash size={12} /> Study ID</span>
                  <span className="info-value mono">{study.id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><User size={12} /> Patient ID</span>
                  <span className="info-value mono">{study.patientId}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><User size={12} /> Patient Age / Gender</span>
                  <span className="info-value">{study.patientAge}y / {study.patientGender}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><FileText size={12} /> Body Part</span>
                  <span className="info-value">{study.bodyPart}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><CalendarDays size={12} /> Study Date</span>
                  <span className="info-value">{study.studyDate}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><Clock size={12} /> Study Time</span>
                  <span className="info-value">{study.studyTime}</span>
                </div>
                <div className="info-item" style={{ gridColumn: 'span 2' }}>
                  <span className="info-label"><User size={12} /> Referring Physician</span>
                  <span className="info-value">{study.referringPhysician}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Panel: AI Analysis & Radiologist Feedback */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* AI Analysis Panel */}
          <div className="chart-card">
            <div className="card-header">
              <h3>AI Triage Analysis</h3>
              <Sparkles size={16} style={{ color: 'var(--primary)' }} />
            </div>
            <div className="card-body">
              <div style={{ background: 'var(--bg-primary)', padding: 14, borderRadius: 8, marginBottom: 14 }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.06em' }}>
                  FLAGGED FINDING
                </div>
                <div style={{ fontSize: 22, fontWeight: 800, color: study.priority === 'CRITICAL' ? 'var(--error)' : 'var(--warning)', marginTop: 4 }}>
                  {study.aiFinding}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginTop: 4 }}>
                  Confidence Score: <span style={{ color: 'var(--primary)', fontWeight: 700 }}>{study.confidenceScore}%</span>
                </div>
              </div>

              {/* Probabilities Breakdown */}
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 10 }}>
                  Abnormality Probabilities:
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                      <span>Pneumothorax</span>
                      <span style={{ fontWeight: 700 }}>{study.probabilities.pneumothorax}%</span>
                    </div>
                    <div className="confidence-bar-track">
                      <div className="confidence-bar-fill" style={{ width: `${study.probabilities.pneumothorax}%`, background: 'var(--error)' }} />
                    </div>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                      <span>Pneumonia / Lung Opacity</span>
                      <span style={{ fontWeight: 700 }}>{study.probabilities.pneumonia}%</span>
                    </div>
                    <div className="confidence-bar-track">
                      <div className="confidence-bar-fill" style={{ width: `${study.probabilities.pneumonia}%`, background: 'var(--warning)' }} />
                    </div>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                      <span>Pleural Effusion</span>
                      <span style={{ fontWeight: 700 }}>{study.probabilities.pleuralEffusion}%</span>
                    </div>
                    <div className="confidence-bar-track">
                      <div className="confidence-bar-fill" style={{ width: `${study.probabilities.pleuralEffusion}%`, background: '#3182ce' }} />
                    </div>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
                      <span>No Urgent Finding</span>
                      <span style={{ fontWeight: 700 }}>{study.probabilities.noUrgentFinding}%</span>
                    </div>
                    <div className="confidence-bar-track">
                      <div className="confidence-bar-fill" style={{ width: `${study.probabilities.noUrgentFinding}%`, background: 'var(--success)' }} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Model Info */}
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', paddingTop: 10, borderTop: '1px solid var(--border-light)' }}>
                <span>Model: <strong>{study.modelVersion}</strong></span>
                <span>Inference Time: <strong>{study.inferenceTimeSeconds}s</strong></span>
              </div>

              {/* Clinical Notice */}
              <div style={{ marginTop: 14, background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 6, padding: 10, fontSize: 11, color: '#873800', lineHeight: 1.4 }}>
                <strong>Clinical Notice:</strong> AI-generated triage recommendation. Final image interpretation and clinical decision must be performed by a qualified radiologist.
              </div>
            </div>
          </div>

          {/* Radiologist Feedback Section */}
          <div className="chart-card">
            <div className="card-header">
              <h3>Radiologist Review & Feedback</h3>
              <ShieldCheck size={16} style={{ color: 'var(--success)' }} />
            </div>
            <div className="card-body">
              {feedbackSuccess && (
                <div className="alert-banner alert-banner-warning" style={{ background: '#e6f6ee', borderColor: '#9ae6b4', color: '#22543d', marginBottom: 14 }}>
                  <CheckCircle2 size={16} />
                  <span>Feedback recorded successfully. Stored for AI model monitoring.</span>
                </div>
              )}

              <div style={{ marginBottom: 14 }}>
                <label className="info-label" style={{ marginBottom: 8 }}>Select Clinical Assessment</label>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button
                    className={`btn ${selectedReview === 'Agree' ? 'btn-primary' : 'btn-outline'}`}
                    style={{ flex: 1, justifyContent: 'center', background: selectedReview === 'Agree' ? 'var(--success)' : '', borderColor: 'var(--success)' }}
                    onClick={() => setSelectedReview('Agree')}
                    type="button"
                  >
                    <CheckCircle2 size={14} /> Agree with AI
                  </button>

                  <button
                    className={`btn ${selectedReview === 'Disagree' ? 'btn-primary' : 'btn-outline'}`}
                    style={{ flex: 1, justifyContent: 'center', background: selectedReview === 'Disagree' ? 'var(--error)' : '', borderColor: 'var(--error)' }}
                    onClick={() => setSelectedReview('Disagree')}
                    type="button"
                  >
                    <XCircle size={14} /> Disagree with AI
                  </button>

                  <button
                    className={`btn ${selectedReview === 'Needs Further Review' ? 'btn-primary' : 'btn-outline'}`}
                    style={{ flex: 1, justifyContent: 'center', background: selectedReview === 'Needs Further Review' ? 'var(--warning)' : '', borderColor: 'var(--warning)' }}
                    onClick={() => setSelectedReview('Needs Further Review')}
                    type="button"
                  >
                    <AlertTriangle size={14} /> Needs Review
                  </button>
                </div>
              </div>

              <div style={{ marginBottom: 16 }}>
                <label className="info-label" style={{ marginBottom: 6 }}>Clinical Comments / Findings Notes</label>
                <textarea
                  className="search-input"
                  style={{ width: '100%', minHeight: 80, padding: 10, fontFamily: 'inherit', resize: 'vertical' }}
                  placeholder="Enter radiologist interpretation notes or discrepancy reasons..."
                  value={comments}
                  onChange={e => setComments(e.target.value)}
                />
              </div>

              {study.feedback.status !== 'Unreviewed' && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 12 }}>
                  Last reviewed by <strong>{study.feedback.reviewedBy}</strong> on {study.feedback.reviewedAt}
                </div>
              )}

              <button
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center' }}
                onClick={handleFeedbackSubmit}
                disabled={submittingFeedback}
                type="button"
              >
                {submittingFeedback ? (
                  <>
                    <span className="loading-spinner-sm" />
                    Recording Feedback...
                  </>
                ) : (
                  <>
                    <Send size={14} /> Submit Feedback
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default StudyDetail;
