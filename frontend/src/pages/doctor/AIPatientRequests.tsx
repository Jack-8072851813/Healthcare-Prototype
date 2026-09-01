import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  fetchEscalations, updateEscalationStatus, fetchConversations, fetchConversationMessages,
  type Escalation, type Conversation
} from '../../services/dashboardApi';
import { Bot, CheckCircle, MessageSquare, RefreshCw, AlertCircle } from 'lucide-react';

const AIPatientRequests: React.FC = () => {
  const { user } = useAuth();
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConvId, setSelectedConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState('');
  const [activeTab, setActiveTab] = useState<'escalations' | 'conversations'>('escalations');

  const showMsg = (msg: string) => {
    setActionMsg(msg);
    setTimeout(() => setActionMsg(''), 3500);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [esc, conv] = await Promise.all([
        fetchEscalations({ per_page: 50 }),
        fetchConversations({ per_page: 50 }),
      ]);
      setEscalations(esc.escalations);
      setConversations(conv.conversations);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleResolveEscalation = async (id: number, notes: string) => {
    const ok = await updateEscalationStatus(id, 'RESOLVED', notes);
    if (ok) {
      showMsg('✓ Escalation resolved successfully');
      load();
    } else {
      showMsg('❌ Failed to update escalation');
    }
  };

  const loadMessages = async (convId: number) => {
    setSelectedConvId(convId);
    const data = await fetchConversationMessages(convId);
    setMessages(data?.messages ?? []);
  };

  const tabStyle = (tab: string) => ({
    padding: '8px 20px',
    borderBottom: activeTab === tab ? '2px solid var(--primary)' : '2px solid transparent',
    background: 'none',
    border: 'none',
    borderBottomWidth: 2,
    borderBottomStyle: 'solid' as const,
    borderBottomColor: activeTab === tab ? 'var(--primary)' : 'transparent',
    fontWeight: activeTab === tab ? 700 : 400,
    color: activeTab === tab ? 'var(--primary)' : 'var(--text-muted)',
    cursor: 'pointer',
    fontSize: 14,
  });

  return (
    <div>
      <div className="page-header">
        <h2>AI Patient Requests</h2>
        <p>Review AI-assisted patient requests — {user?.name}</p>
      </div>

      {actionMsg && <div className="success-alert"><CheckCircle size={16} /> {actionMsg}</div>}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: 20 }}>
        <button style={tabStyle('escalations')} onClick={() => setActiveTab('escalations')}>
          <AlertCircle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
          Escalations ({escalations.length})
        </button>
        <button style={tabStyle('conversations')} onClick={() => setActiveTab('conversations')}>
          <MessageSquare size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
          AI Conversations ({conversations.length})
        </button>
        <div style={{ marginLeft: 'auto', padding: '4px 0' }}>
          <button className="btn btn-secondary btn-sm" onClick={load} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>Loading...</div>
      ) : activeTab === 'escalations' ? (
        /* Escalations Tab */
        <div className="card">
          <div className="card-header"><h3>Open Escalations</h3></div>
          {escalations.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>
              <Bot size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
              <p>No active escalations.</p>
            </div>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Patient</th>
                    <th>Reason</th>
                    <th>Question</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {escalations.map(e => (
                    <tr key={e.id}>
                      <td>
                        <div style={{ fontWeight: 600 }}>{e.patient_name || e.whatsapp_number}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{e.patient_code}</div>
                      </td>
                      <td style={{ fontSize: 12 }}>{e.escalation_reason}</td>
                      <td style={{ fontSize: 12, maxWidth: 200 }}>{e.patient_question?.substring(0, 80) || '—'}</td>
                      <td><span className={`status-badge ${e.status === 'OPEN' ? 'pending' : 'active'}`}>{e.status}</span></td>
                      <td style={{ fontSize: 12 }}>{e.created_at ? new Date(e.created_at).toLocaleDateString() : '—'}</td>
                      <td>
                        {e.status === 'OPEN' && (
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button className="btn btn-success btn-sm"
                              onClick={() => handleResolveEscalation(e.id, 'Resolved by doctor')}>
                              Resolve
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        /* Conversations Tab */
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          <div className="card" style={{ flex: 1, minWidth: 300 }}>
            <div className="card-header"><h3>Patient Conversations</h3></div>
            <div className="card-body" style={{ padding: 0 }}>
              {conversations.length === 0 ? (
                <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Bot size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
                  <p>No conversations found.</p>
                </div>
              ) : conversations.map(c => (
                <div
                  key={c.id}
                  onClick={() => loadMessages(c.id)}
                  style={{
                    padding: '16px 20px',
                    borderBottom: '1px solid var(--border-light)',
                    cursor: 'pointer',
                    background: selectedConvId === c.id ? 'var(--primary-lightest)' : 'transparent',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontWeight: 600 }}>{c.patient_name || c.whatsapp_number}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.message_count} msgs</span>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    {c.current_intent && <span className="intent-badge">{c.current_intent}</span>}
                    <span className={`status-badge ${c.conversation_status === 'ACTIVE' ? 'active' : 'inactive'}`}>
                      {c.conversation_status}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                    {c.language} · {c.last_message_at ? new Date(c.last_message_at).toLocaleString() : '—'}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ flex: 1, minWidth: 320 }}>
            {selectedConvId ? (
              <div className="card">
                <div className="card-header">
                  <h3>Conversation Messages</h3>
                </div>
                <div className="card-body">
                  {messages.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)' }}>No messages to display.</div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                      {(messages as Array<Record<string, unknown>>).map((m, i) => (
                        <div key={i} style={{
                          padding: '10px 14px',
                          background: String(m.sender_type) === 'PATIENT' ? 'var(--primary-lightest)' : 'var(--bg-secondary)',
                          borderRadius: 'var(--radius-md)',
                          fontSize: 13,
                        }}>
                          <div style={{ fontWeight: 600, fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                            {String(m.sender_type)}
                          </div>
                          <div>{String(m.message_text || m.content || '')}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="card">
                <div className="card-body" style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                  <MessageSquare size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
                  <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-secondary)' }}>Select a Conversation</h3>
                  <p style={{ fontSize: 13 }}>Click on a conversation to view messages</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AIPatientRequests;
