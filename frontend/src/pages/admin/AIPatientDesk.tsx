import React, { useState, useEffect, useCallback } from 'react';
import {
  Bot, CalendarCheck, CheckCircle, AlertTriangle, Globe, MessageSquare,
  RefreshCw, ChevronLeft, ChevronRight, Eye, X
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell
} from 'recharts';
import {
  fetchConversations, fetchIntentBreakdown, fetchConversationMessages,
  type Conversation,
} from '../../services/dashboardApi';

const INTENT_COLORS: Record<string, string> = {
  GREETING: '#48BB78',
  BOOK_APPOINTMENT: '#4A90D9',
  CANCEL_APPOINTMENT: '#F56565',
  RESCHEDULE_APPOINTMENT: '#ECC94B',
  DOCTOR_AVAILABILITY: '#9F7AEA',
  HOSPITAL_INFORMATION: '#5AAFA5',
  DEPARTMENT_INFORMATION: '#ED8936',
  SYMPTOM_GUIDANCE: '#E53E3E',
  PRE_ADMISSION: '#38B2AC',
  HUMAN_ESCALATION: '#FC8181',
  LANGUAGE_CHANGE: '#B794F4',
  EMERGENCY_GUIDANCE: '#C53030',
};

const CHART_COLORS = ['#4A90D9', '#5AAFA5', '#48BB78', '#ECC94B', '#F56565', '#9F7AEA', '#ED8936', '#38B2AC'];

const LANGUAGES = ['ENGLISH', 'TAMIL', 'HINDI', 'TELUGU', 'MALAYALAM', 'KANNADA', 'URDU'];

const AIPatientDesk: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [intentBreakdown, setIntentBreakdown] = useState<{ intent: string; count: number }[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState('');
  const [langFilter, setLangFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedConv, setSelectedConv] = useState<Conversation | null>(null);
  const [convMessages, setConvMessages] = useState<unknown[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [convRes, ibRes] = await Promise.all([
        fetchConversations({ status: statusFilter || undefined, language: langFilter || undefined, page, per_page: 15 }),
        fetchIntentBreakdown(30),
      ]);
      setConversations(convRes.conversations);
      setTotal(convRes.total);
      setTotalPages(convRes.total_pages);
      setIntentBreakdown(ibRes.intent_breakdown);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, langFilter, page]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const openConversation = async (conv: Conversation) => {
    setSelectedConv(conv);
    setLoadingMessages(true);
    const res = await fetchConversationMessages(conv.id);
    setConvMessages(res?.messages ?? []);
    setLoadingMessages(false);
  };

  // Compute summary stats from conversations
  const totalConvs = total;
  const escalated = conversations.filter(c => c.conversation_status === 'ESCALATED').length;

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2>Meridian AI Patient Desk</h2>
            <p>AI-powered conversational assistance — live data from database</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={loadData} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon teal"><Bot size={22} /></div></div>
          <div className="kpi-value">{totalConvs}</div>
          <div className="kpi-label">Total AI Conversations</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon blue"><CalendarCheck size={22} /></div></div>
          <div className="kpi-value">{intentBreakdown.find(i => i.intent === 'BOOK_APPOINTMENT')?.count ?? 0}</div>
          <div className="kpi-label">Appointment Booking Intents</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon green"><CheckCircle size={22} /></div></div>
          <div className="kpi-value">{intentBreakdown.reduce((s, i) => s + Number(i.count), 0)}</div>
          <div className="kpi-label">Total Classified Intents</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon amber"><AlertTriangle size={22} /></div></div>
          <div className="kpi-value">{escalated}</div>
          <div className="kpi-label">Human Escalations (page)</div>
        </div>
      </div>

      {/* Language & Channel info */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: 200 }}>
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Globe size={20} style={{ color: 'var(--primary)' }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Languages Supported</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                {LANGUAGES.map(l => (
                  <span key={l} className="intent-badge" style={{ fontSize: 11 }}>{l}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="card" style={{ flex: 1, minWidth: 200 }}>
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <MessageSquare size={20} style={{ color: 'var(--success)' }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Channels</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                <span className="channel-badge whatsapp">💬 WhatsApp Text</span>
                <span className="channel-badge voice">🎤 WhatsApp Voice</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Intent Breakdown Chart */}
      {intentBreakdown.length > 0 && (
        <div className="chart-card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <h3>Intent Distribution</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Last 30 Days</span>
          </div>
          <div className="card-body">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={intentBreakdown}>
                <CartesianGrid strokeDasharray="3 3" stroke="#EDF2F7" />
                <XAxis dataKey="intent" tick={{ fontSize: 10, fill: '#8796A9' }} angle={-15} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 12, fill: '#8796A9' }} />
                <Tooltip contentStyle={{ borderRadius: 8, border: '1px solid #E2E8F0' }} />
                <Bar dataKey="count" name="Messages" radius={[4, 4, 0, 0]}>
                  {intentBreakdown.map((entry, index) => (
                    <Cell key={index} fill={INTENT_COLORS[entry.intent] || CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Conversations Table */}
      <div className="card">
        <div className="card-header">
          <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600 }}>Recent Conversations</h3>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}
              style={{ padding: '7px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}>
              <option value="">All Status</option>
              <option value="ACTIVE">Active</option>
              <option value="COMPLETED">Completed</option>
              <option value="ESCALATED">Escalated</option>
            </select>
            <select value={langFilter} onChange={e => { setLangFilter(e.target.value); setPage(1); }}
              style={{ padding: '7px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}>
              <option value="">All Languages</option>
              {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
          </div>
        </div>

        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>Loading conversations...</div>
          ) : conversations.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>No conversations found.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Patient</th>
                  <th>WhatsApp #</th>
                  <th>Language</th>
                  <th>Intent</th>
                  <th>Messages</th>
                  <th>Last Active</th>
                  <th>Status</th>
                  <th>View</th>
                </tr>
              </thead>
              <tbody>
                {conversations.map(c => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600, color: 'var(--primary)', fontSize: 11 }}>{c.conversation_code}</td>
                    <td style={{ fontSize: 13 }}>{c.patient_name || <span style={{ color: 'var(--text-muted)' }}>Anonymous</span>}</td>
                    <td style={{ fontSize: 12 }}>{c.whatsapp_number}</td>
                    <td>
                      <span className="intent-badge" style={{ fontSize: 11 }}>{c.language}</span>
                    </td>
                    <td>
                      {c.current_intent ? (
                        <span className="intent-badge" style={{
                          fontSize: 10,
                          background: `${INTENT_COLORS[c.current_intent] || '#4A90D9'}18`,
                          color: INTENT_COLORS[c.current_intent] || '#4A90D9',
                        }}>
                          {c.current_intent}
                        </span>
                      ) : <span style={{ color: 'var(--text-muted)' }}>—</span>}
                    </td>
                    <td style={{ textAlign: 'center', fontWeight: 600 }}>{c.message_count}</td>
                    <td style={{ fontSize: 12 }}>
                      {c.last_message_at ? new Date(c.last_message_at).toLocaleString() : '—'}
                    </td>
                    <td>
                      <span className={`status-badge ${c.conversation_status === 'ACTIVE' ? 'active' : c.conversation_status === 'ESCALATED' ? 'cancelled' : 'completed'}`}>
                        {c.conversation_status}
                      </span>
                    </td>
                    <td>
                      <button className="btn btn-secondary btn-sm" onClick={() => openConversation(c)}>
                        <Eye size={13} /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="pagination" style={{ padding: '16px 22px' }}>
          <span className="pagination-info">
            {loading ? 'Loading...' : `${total} conversations total`}
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

      {/* Conversation Messages Modal */}
      {selectedConv && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div style={{
            background: 'var(--bg-card)', borderRadius: 12, padding: 24,
            width: '90%', maxWidth: 640, maxHeight: '80vh', overflowY: 'auto',
            boxShadow: '0 20px 60px rgba(0,0,0,0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 16 }}>{selectedConv.patient_name || 'Anonymous Patient'}</h3>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                  {selectedConv.conversation_code} · {selectedConv.whatsapp_number}
                </div>
              </div>
              <button className="btn btn-secondary btn-sm" onClick={() => { setSelectedConv(null); setConvMessages([]); }}>
                <X size={14} />
              </button>
            </div>

            {loadingMessages ? (
              <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)' }}>Loading messages...</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {(convMessages as Array<{ sender_type: string; message_text?: string; created_at: string; intent?: string }>).map((msg, idx) => (
                  <div key={idx} style={{
                    display: 'flex',
                    justifyContent: msg.sender_type === 'PATIENT' ? 'flex-start' : 'flex-end',
                  }}>
                    <div style={{
                      maxWidth: '78%',
                      background: msg.sender_type === 'PATIENT' ? 'var(--bg-primary)' : 'var(--primary)',
                      color: msg.sender_type === 'PATIENT' ? 'var(--text-primary)' : '#fff',
                      borderRadius: 10,
                      padding: '10px 14px',
                      fontSize: 13,
                      lineHeight: 1.5,
                    }}>
                      <div style={{ fontSize: 10, opacity: 0.65, marginBottom: 4 }}>
                        {msg.sender_type} {msg.intent ? `· ${msg.intent}` : ''}
                      </div>
                      {msg.message_text || '—'}
                      <div style={{ fontSize: 10, opacity: 0.5, marginTop: 4 }}>
                        {msg.created_at ? new Date(msg.created_at).toLocaleTimeString() : ''}
                      </div>
                    </div>
                  </div>
                ))}
                {convMessages.length === 0 && (
                  <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)' }}>
                    No messages recorded for this conversation.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AIPatientDesk;
