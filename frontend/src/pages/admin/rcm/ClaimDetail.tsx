import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, CheckCircle2, Clock, FileText, ShieldAlert,
  IndianRupee, CalendarDays, Building2, User, Hash,
} from 'lucide-react';
import { fetchClaim, markClaimReviewed } from '../../../services/api';
import RiskBadge from '../../../components/rcm/RiskBadge';
import WhyPanel from '../../../components/rcm/WhyPanel';
import AIBadge from '../../../components/rcm/AIBadge';
import type { ClaimDetail as ClaimDetailType, RiskLevel } from '../../../data/rcm/claims';

const STATUS_PILL: Record<string, string> = {
  Approved: 'status-pill status-approved',
  Rejected: 'status-pill status-rejected',
  Pending: 'status-pill status-pending',
  'Under Review': 'status-pill status-review',
};

const RISK_ACTIONS_COLOR: Record<string, string> = {
  Low: '#48BB78', Medium: '#E8850A', High: '#E53E3E', Critical: '#C53030',
};

const ClaimDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [claim, setClaim] = useState<ClaimDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [reviewed, setReviewed] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchClaim(id).then(c => {
      setClaim(c);
      if (c) setReviewed(c.reviewed);
      setLoading(false);
    });
  }, [id]);

  const handleMarkReviewed = async () => {
    if (!id) return;
    setReviewing(true);
    await markClaimReviewed(id);
    setReviewed(r => !r);
    setReviewing(false);
  };

  if (loading) {
    return <div className="page-loading"><div className="loading-spinner" /><p>Loading claim…</p></div>;
  }

  if (!claim) {
    return (
      <div className="page-loading">
        <p>Claim not found.</p>
        <button className="btn btn-primary" onClick={() => navigate(-1)}>← Go Back</button>
      </div>
    );
  }

  const riskColor = RISK_ACTIONS_COLOR[claim.risk_level] || '#4A90D9';

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(-1)}>
            <ArrowLeft size={16} />
          </button>
          <div>
            <h2>Claim Detail — <span className="mono">{claim.id}</span></h2>
            <p>Full risk analysis and AI recommendations</p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <AIBadge />
          <button
            className={`btn ${reviewed ? 'btn-outline' : 'btn-primary'} btn-sm`}
            onClick={handleMarkReviewed}
            disabled={reviewing}
          >
            {reviewing ? <span className="loading-spinner-sm" /> : <CheckCircle2 size={14} />}
            {reviewed ? 'Reviewed ✓' : 'Mark as Reviewed'}
          </button>
        </div>
      </div>

      <div className="detail-grid">
        {/* Left Column — Claim Info */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Basic Info Card */}
          <div className="chart-card">
            <div className="card-header">
              <h3><FileText size={16} style={{ marginRight: 6 }} />Claim Information</h3>
              <span className={STATUS_PILL[claim.status] || 'status-pill'}>{claim.status}</span>
            </div>
            <div className="card-body">
              <div className="info-grid">
                <div className="info-item">
                  <span className="info-label"><Hash size={12} /> Claim ID</span>
                  <span className="info-value mono">{claim.id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><User size={12} /> Patient</span>
                  <span className="info-value">{claim.patient_name}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><Hash size={12} /> Patient ID</span>
                  <span className="info-value mono">{claim.patient_id}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><Building2 size={12} /> Insurance Provider</span>
                  <span className="info-value">{claim.insurance_provider}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><FileText size={12} /> Procedure Category</span>
                  <span className="info-value"><span className="category-tag">{claim.procedure_category}</span></span>
                </div>
                <div className="info-item">
                  <span className="info-label"><IndianRupee size={12} /> Claim Amount</span>
                  <span className="info-value" style={{ fontWeight: 700, fontSize: 17, color: 'var(--text-primary)' }}>
                    ₹{claim.amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                  </span>
                </div>
                <div className="info-item">
                  <span className="info-label"><CalendarDays size={12} /> Claim Date</span>
                  <span className="info-value">{claim.claim_date}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><CalendarDays size={12} /> Discharge Date</span>
                  <span className="info-value">{claim.discharge_date || <span className="missing-val">Not provided</span>}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><Hash size={12} /> Authorization #</span>
                  <span className="info-value">{claim.authorization_number || <span className="missing-val">Missing</span>}</span>
                </div>
                <div className="info-item">
                  <span className="info-label"><FileText size={12} /> Discharge Summary</span>
                  <span className="info-value">
                    {claim.discharge_summary
                      ? <span style={{ color: 'var(--success)', fontWeight: 500 }}>✓ Uploaded</span>
                      : <span className="missing-val">✗ Missing</span>}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Detected Issues */}
          {claim.risk_factors.length > 0 && (
            <div className="chart-card issue-card">
              <div className="card-header">
                <h3><ShieldAlert size={16} style={{ marginRight: 6 }} />Detected Issues</h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{claim.risk_factors.length} issue(s)</span>
              </div>
              <div className="card-body">
                <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {claim.risk_factors.map((f, i) => {
                    const [head, ...rest] = f.split('—');
                    return (
                      <li key={i} className="issue-item">
                        <span className="issue-bullet">⚑</span>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{head.trim()}</div>
                          {rest.length > 0 && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{rest.join('—').trim()}</div>}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>
          )}
        </div>

        {/* Right Column — Risk Analysis */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Risk Score Card */}
          <div className="chart-card">
            <div className="card-header">
              <h3>AI Risk Analysis</h3>
              <RiskBadge level={claim.risk_level as RiskLevel} score={claim.risk_score} />
            </div>
            <div className="card-body">
              {/* Score Meter */}
              <div className="risk-meter-wrap">
                <div className="risk-meter-track">
                  <div
                    className="risk-meter-fill"
                    style={{ width: `${claim.risk_score}%`, background: riskColor }}
                  />
                  <div className="risk-meter-segments">
                    <span className="seg-label" style={{ left: '0%' }}>0</span>
                    <span className="seg-label" style={{ left: '30%' }}>Low</span>
                    <span className="seg-label" style={{ left: '60%' }}>Med</span>
                    <span className="seg-label" style={{ left: '80%' }}>High</span>
                    <span className="seg-label" style={{ left: '100%' }}>100</span>
                  </div>
                </div>
                <div className="risk-score-big" style={{ color: riskColor }}>
                  {claim.risk_score}<span style={{ fontSize: 18, fontWeight: 400, color: 'var(--text-muted)' }}>/100</span>
                </div>
              </div>

              <WhyPanel factors={claim.risk_factors} score={claim.risk_score} />
            </div>
          </div>

          {/* AI Recommendation */}
          <div className="chart-card recommendation-card">
            <div className="card-header">
              <h3>AI Recommendation</h3>
              <AIBadge />
            </div>
            <div className="card-body">
              <div className="recommendation-box" style={{ borderLeftColor: riskColor }}>
                <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--text-primary)', margin: 0 }}>
                  {claim.recommended_action}
                </p>
              </div>
              <div style={{ marginTop: 14, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {claim.risk_level === 'Critical' && (
                  <span className="action-tag action-escalate">Escalate Immediately</span>
                )}
                {!claim.discharge_summary && (
                  <span className="action-tag action-doc">Upload Discharge Summary</span>
                )}
                {!claim.authorization_number && (
                  <span className="action-tag action-doc">Add Authorization #</span>
                )}
                {claim.status === 'Rejected' && (
                  <span className="action-tag action-resubmit">Re-submission Required</span>
                )}
              </div>
            </div>
          </div>

          {/* Review Status */}
          <div className="chart-card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {reviewed
                ? <CheckCircle2 size={32} style={{ color: 'var(--success)', flexShrink: 0 }} />
                : <Clock size={32} style={{ color: 'var(--warning)', flexShrink: 0 }} />}
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>
                  {reviewed ? 'Marked as Reviewed' : 'Pending Human Review'}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  {reviewed
                    ? 'A billing executive has reviewed this claim.'
                    : 'This claim has not yet been reviewed by a billing executive.'}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ClaimDetail;
