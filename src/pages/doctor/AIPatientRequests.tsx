import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { patients } from '../../data/patients';
import { aiConversations } from '../../data/aiConversations';
import { Bot, CheckCircle, MessageSquare } from 'lucide-react';

const AIPatientRequests: React.FC = () => {
  const { user } = useAuth();
  const myPatients = patients.filter(p => p.assignedDoctorId === user?.loginId);
  const myPatientIds = myPatients.map(p => p.id);

  const relevantConversations = aiConversations.filter(c => myPatientIds.includes(c.patientId));
  const [selectedConv, setSelectedConv] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState('');

  const conv = selectedConv ? relevantConversations.find(c => c.id === selectedConv) : null;

  const handleAction = (action: string, convId: string) => {
    setActionMsg(`${action} action performed for conversation ${convId}`);
    setTimeout(() => setActionMsg(''), 3000);
  };

  return (
    <div>
      <div className="page-header">
        <h2>AI Patient Requests</h2>
        <p>Review AI-assisted patient requests for {user?.name}</p>
      </div>

      {actionMsg && <div className="success-alert"><CheckCircle size={16} /> {actionMsg}</div>}

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
        {/* Request List */}
        <div className="card" style={{ flex: 1, minWidth: 300 }}>
          <div className="card-header"><h3>Patient Requests</h3></div>
          <div className="card-body" style={{ padding: 0 }}>
            {relevantConversations.length > 0 ? relevantConversations.map(c => (
              <div
                key={c.id}
                onClick={() => setSelectedConv(c.id)}
                style={{
                  padding: '16px 20px',
                  borderBottom: '1px solid var(--border-light)',
                  cursor: 'pointer',
                  background: selectedConv === c.id ? 'var(--primary-lightest)' : 'transparent',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                  <span style={{ fontWeight: 600 }}>{c.patientName}</span>
                  <span className={`channel-badge ${c.channel.toLowerCase()}`}>{c.channel}</span>
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 6 }}>
                  {c.messages[0]?.text.substring(0, 80)}...
                </p>
                <div style={{ display: 'flex', gap: 6 }}>
                  <span className="intent-badge">{c.intent}</span>
                  <span className={`status-badge ${c.status.toLowerCase().replace(/ /g, '-')}`}>{c.status}</span>
                </div>
                {c.status === 'Needs Doctor Confirmation' && (
                  <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                    <button className="btn btn-success btn-sm" onClick={e => { e.stopPropagation(); handleAction('Approved', c.id); }}>Approve</button>
                    <button className="btn btn-primary btn-sm" onClick={e => { e.stopPropagation(); handleAction('Responded', c.id); }}>Respond</button>
                    <button className="btn btn-secondary btn-sm" onClick={e => { e.stopPropagation(); handleAction('Scheduled', c.id); }}>Schedule</button>
                    <button className="btn btn-danger btn-sm" onClick={e => { e.stopPropagation(); handleAction('Escalated', c.id); }}>Escalate</button>
                  </div>
                )}
              </div>
            )) : (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                <Bot size={40} style={{ opacity: 0.3, marginBottom: 12 }} />
                <p>No AI patient requests for your patients.</p>
              </div>
            )}
          </div>
        </div>

        {/* Chat View */}
        <div style={{ flex: 1, minWidth: 320 }}>
          {conv ? (
            <div className="chat-container" style={{ maxWidth: '100%' }}>
              <div className="chat-header">
                <div className="chat-header-avatar">{conv.channel === 'WhatsApp' ? '💬' : '🎙️'}</div>
                <div className="chat-header-info">
                  <h4>{conv.patientName}</h4>
                  <span>{conv.channel} · {conv.language}</span>
                </div>
              </div>
              <div className="chat-messages" style={{ minHeight: 300 }}>
                {conv.messages.map((m, i) => (
                  <div key={i} className={`chat-message ${m.sender}`}>
                    <div className="chat-bubble">{m.text}</div>
                    <div className="chat-time">{m.time}</div>
                  </div>
                ))}
                <div style={{ clear: 'both' }}></div>
              </div>
              <div className="chat-metadata">
                <span className="chat-metadata-item"><strong>Intent:</strong> {conv.intent}</span>
                <span className="chat-metadata-item"><strong>Status:</strong> {conv.status}</span>
                <span className="chat-metadata-item"><strong>Language:</strong> {conv.language}</span>
              </div>
            </div>
          ) : (
            <div className="card">
              <div className="card-body" style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                <MessageSquare size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
                <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-secondary)' }}>Select a Request</h3>
                <p style={{ fontSize: 13 }}>Click on a request to view the conversation</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AIPatientRequests;
