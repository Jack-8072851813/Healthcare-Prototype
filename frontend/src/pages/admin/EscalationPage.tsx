import React, { useState, useEffect, useCallback } from 'react';
import {
  AlertTriangle, RefreshCw, CheckCircle, Clock, ChevronLeft, ChevronRight,
  MessageSquare, User, Phone
} from 'lucide-react';
import { fetchEscalations, updateEscalationStatus, type Escalation } from '../../services/dashboardApi';

const STATUS_COLORS: Record<string, { badge: string; label: string }> = {
  OPEN: { badge: 'cancelled', label: '🔴 Open' },
  IN_PROGRESS: { badge: 'pending', label: '🟡 In Progress' },
  RESOLVED: { badge: 'active', label: '🟢 Resolved' },
};

const EscalationPage: React.FC = () => {
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');
  const [resolveModal, setResolveModal] = useState<Escalation | null>(null);
  const [resolutionNote, setResolutionNote] = useState('');

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(''), 3500);
  };

  const loadEscalations = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchEscalations({
        status: statusFilter || undefined,
        page,
        per_page: 15,
      });
      setEscalations(res.escalations);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    loadEscalations();
  }, [loadEscalations]);

  const handleStatusUpdate = async (id: number, newStatus: string, notes?: string) => {
    const ok = await updateEscalationStatus(id, newStatus, notes);
    if (ok) {
      showToast(`Escalation #${id} updated to ${newStatus}`);
      loadEscalations();
    } else {
      showToast('❌ Failed to update escalation status.');
    }
  };

  const openResolveModal = (esc: Escalation) => {
    setResolveModal(esc);
    setResolutionNote('');
  };

  const submitResolve = async () => {
    if (!resolveModal) return;
    await handleStatusUpdate(resolveModal.id, 'RESOLVED', resolutionNote);
    setResolveModal(null);
  };

  const openCount = escalations.filter(e => e.status === 'OPEN').length;
  const inProgressCount = escalations.filter(e => e.status === 'IN_PROGRESS').length;

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2>Human Escalation Management</h2>
            <p>Cases where patients requested human assistance via the AI Patient Desk</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={loadEscalations} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>
      </div>

      {toast && <div className="success-alert"><CheckCircle size={16} /> {toast}</div>}

      {/* Summary KPIs */}
      <div className="kpi-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 24 }}>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon red"><AlertTriangle size={22} /></div>
          </div>
          <div className="kpi-value" style={{ color: '#F56565' }}>{openCount}</div>
          <div className="kpi-label">Open (this page)</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon amber"><Clock size={22} /></div>
          </div>
          <div className="kpi-value" style={{ color: '#ECC94B' }}>{inProgressCount}</div>
          <div className="kpi-label">In Progress (this page)</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><MessageSquare size={22} /></div>
          </div>
          <div className="kpi-value">{total}</div>
          <div className="kpi-label">Total Escalations</div>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="card-header">
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Escalation Cases</h3>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
              style={{ padding: '7px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}>
              <option value="">All Status</option>
              <option value="OPEN">Open</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </div>
        </div>

        {/* Escalation Cards */}
        <div style={{ padding: '8px 0' }}>
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>Loading escalations...</div>
          ) : escalations.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              <AlertTriangle size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
              <div>No escalation cases {statusFilter ? `with status "${statusFilter}"` : 'recorded yet'}.</div>
              <div style={{ fontSize: 12, marginTop: 6 }}>
                Escalations are created when the AI Patient Desk cannot resolve a patient request.
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
              {escalations.map(esc => (
                <div key={esc.id} style={{
                  padding: '18px 24px',
                  borderBottom: '1px solid var(--border-light)',
                  display: 'grid',
                  gridTemplateColumns: '1fr 2fr 160px',
                  gap: 20,
                  alignItems: 'start',
                  transition: 'background 0.2s',
                }}>
                  {/* Left: Patient + conversation info */}
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <div style={{
                        width: 32, height: 32, borderRadius: '50%',
                        background: 'var(--primary-lighter)', color: 'var(--primary)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14
                      }}>
                        <User size={16} />
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>
                          {esc.patient_name || 'Unknown Patient'}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {esc.patient_code || 'Not registered'}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--text-muted)' }}>
                      <Phone size={11} /> {esc.whatsapp_number}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                      {esc.conversation_code}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      {esc.created_at ? new Date(esc.created_at).toLocaleString() : '—'}
                    </div>
                  </div>

                  {/* Middle: Reason + question */}
                  <div>
                    <div style={{ marginBottom: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                        Escalation Reason
                      </span>
                      <div style={{
                        marginTop: 4, padding: '8px 12px', background: '#FFF5F5',
                        borderLeft: '3px solid #F56565', borderRadius: '0 6px 6px 0',
                        fontSize: 13, color: 'var(--text-primary)'
                      }}>
                        {esc.escalation_reason}
                      </div>
                    </div>
                    {esc.patient_question && (
                      <div>
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                          Patient's Question
                        </span>
                        <div style={{
                          marginTop: 4, padding: '8px 12px', background: 'var(--bg-primary)',
                          borderLeft: '3px solid var(--primary)', borderRadius: '0 6px 6px 0',
                          fontSize: 13, color: 'var(--text-secondary)', fontStyle: 'italic'
                        }}>
                          "{esc.patient_question}"
                        </div>
                      </div>
                    )}
                    {esc.resolution_notes && (
                      <div style={{ marginTop: 8 }}>
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--success)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                          Resolution Notes
                        </span>
                        <div style={{
                          marginTop: 4, padding: '8px 12px', background: '#F0FFF4',
                          borderLeft: '3px solid #48BB78', borderRadius: '0 6px 6px 0',
                          fontSize: 13, color: 'var(--text-primary)'
                        }}>
                          {esc.resolution_notes}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right: Status + actions */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
                    <span className={`status-badge ${STATUS_COLORS[esc.status]?.badge || 'active'}`}>
                      {STATUS_COLORS[esc.status]?.label || esc.status}
                    </span>

                    {esc.status === 'OPEN' && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleStatusUpdate(esc.id, 'IN_PROGRESS')}
                        style={{ width: '100%', justifyContent: 'center' }}
                      >
                        <Clock size={13} /> Assign / Start
                      </button>
                    )}

                    {(esc.status === 'OPEN' || esc.status === 'IN_PROGRESS') && (
                      <button
                        className="btn btn-success btn-sm"
                        onClick={() => openResolveModal(esc)}
                        style={{ width: '100%', justifyContent: 'center' }}
                      >
                        <CheckCircle size={13} /> Mark Resolved
                      </button>
                    )}

                    {esc.status === 'RESOLVED' && esc.resolved_at && (
                      <div style={{ fontSize: 11, color: 'var(--success)', textAlign: 'right' }}>
                        Resolved<br />{new Date(esc.resolved_at).toLocaleDateString()}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="pagination" style={{ padding: '16px 22px' }}>
          <span className="pagination-info">
            {loading ? 'Loading...' : `${total} escalation(s) total`}
          </span>
          <div className="pagination-buttons">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft size={14} /></button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const pg = i + Math.max(1, page - 3);
              if (pg > totalPages) return null;
              return <button key={pg} className={page === pg ? 'active' : ''} onClick={() => setPage(pg)}>{pg}</button>;
            })}
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><ChevronRight size={14} /></button>
          </div>
        </div>
      </div>

      {/* Resolve Modal */}
      {resolveModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{
            background: 'var(--bg-card)', borderRadius: 12, padding: 28,
            width: '90%', maxWidth: 480, boxShadow: '0 20px 60px rgba(0,0,0,0.2)'
          }}>
            <h3 style={{ marginTop: 0, fontSize: 16, marginBottom: 8 }}>Resolve Escalation</h3>
            <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
              Patient: <strong>{resolveModal.patient_name || 'Unknown'}</strong><br />
              Reason: {resolveModal.escalation_reason}
            </p>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
              Resolution Notes <span style={{ fontWeight: 400, color: 'var(--text-muted)' }}>(optional)</span>
            </label>
            <textarea
              value={resolutionNote}
              onChange={e => setResolutionNote(e.target.value)}
              placeholder="Describe how the issue was resolved..."
              style={{
                width: '100%', minHeight: 100, padding: '10px 12px',
                border: '1.5px solid var(--border)', borderRadius: 8, fontSize: 13,
                fontFamily: 'inherit', resize: 'vertical', boxSizing: 'border-box'
              }}
            />
            <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary" onClick={() => setResolveModal(null)}>
                Cancel
              </button>
              <button className="btn btn-success" onClick={submitResolve}>
                <CheckCircle size={14} /> Mark as Resolved
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default EscalationPage;
