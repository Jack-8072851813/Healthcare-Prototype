import React, { useState } from 'react';
import { aiConversations } from '../../data/aiConversations';
import {
  Bot, CalendarCheck, CheckCircle, AlertTriangle, Globe, MessageSquare,
  Mic, ChevronDown, ArrowDown, Phone, Volume2
} from 'lucide-react';

const AIPatientDesk: React.FC = () => {
  const [selectedConv, setSelectedConv] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'conversations' | 'architecture' | 'voice'>('conversations');

  const conv = selectedConv ? aiConversations.find(c => c.id === selectedConv) : null;

  const intents = [
    'Appointment Booking', 'Appointment Rescheduling', 'Appointment Cancellation',
    'Doctor Availability', 'Department Information', 'Hospital Information',
    'OPD Timings', 'Pre-Admission Follow-up', 'Appointment Status', 'Human Staff Escalation'
  ];

  return (
    <div>
      <div className="page-header">
        <h2>Meridian AI Patient Desk</h2>
        <p>AI-powered conversational assistance for patients</p>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon teal"><Bot size={22} /></div>
          </div>
          <div className="kpi-value">143</div>
          <div className="kpi-label">AI Conversations Today</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon blue"><CalendarCheck size={22} /></div>
          </div>
          <div className="kpi-value">32</div>
          <div className="kpi-label">Appointments Booked by AI</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon green"><CheckCircle size={22} /></div>
          </div>
          <div className="kpi-value">91</div>
          <div className="kpi-label">Patient Queries Resolved</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header">
            <div className="kpi-icon amber"><AlertTriangle size={22} /></div>
          </div>
          <div className="kpi-value">8</div>
          <div className="kpi-label">Human Escalations</div>
        </div>
      </div>

      {/* Language & Channel Info */}
      <div style={{ display: 'flex', gap: 16, marginBottom: 24, flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: 200 }}>
          <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <Globe size={20} style={{ color: 'var(--primary)' }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Languages Supported</div>
              <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                {['English', 'Tamil', 'Hindi', 'Telugu'].map(l => (
                  <span key={l} className="intent-badge">{l}</span>
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
              <div style={{ display: 'flex', gap: 6, marginTop: 4 }}>
                <span className="channel-badge whatsapp">💬 WhatsApp</span>
                <span className="channel-badge voice">🎙️ Voice</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs">
        <button className={`tab ${activeTab === 'conversations' ? 'active' : ''}`} onClick={() => setActiveTab('conversations')}>
          💬 Conversations
        </button>
        <button className={`tab ${activeTab === 'architecture' ? 'active' : ''}`} onClick={() => setActiveTab('architecture')}>
          🏗️ Architecture
        </button>
        <button className={`tab ${activeTab === 'voice' ? 'active' : ''}`} onClick={() => setActiveTab('voice')}>
          🎙️ Voice Agent
        </button>
      </div>

      {/* Conversations Tab */}
      {activeTab === 'conversations' && (
        <div style={{ display: 'flex', gap: 20 }}>
          {/* Conversation List */}
          <div className="card" style={{ flex: 1, minWidth: 280 }}>
            <div className="card-header"><h3>Recent AI Conversations</h3></div>
            <div className="card-body" style={{ padding: 0 }}>
              {aiConversations.map(c => (
                <div
                  key={c.id}
                  onClick={() => setSelectedConv(c.id)}
                  style={{
                    padding: '14px 20px',
                    borderBottom: '1px solid var(--border-light)',
                    cursor: 'pointer',
                    background: selectedConv === c.id ? 'var(--primary-lightest)' : 'transparent',
                    transition: 'background 0.2s',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>{c.patientName}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{c.timestamp.split(' ').slice(1).join(' ')}</span>
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    <span className={`channel-badge ${c.channel.toLowerCase()}`}>{c.channel}</span>
                    <span className="intent-badge">{c.intent}</span>
                    <span className={`status-badge ${c.status.toLowerCase().replace(/ /g, '-')}`}>{c.status}</span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                    🌐 {c.language}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Chat Window */}
          <div style={{ flex: 1, minWidth: 320 }}>
            {conv ? (
              <div className="chat-container" style={{ maxWidth: '100%' }}>
                <div className="chat-header">
                  <div className="chat-header-avatar">
                    {conv.channel === 'WhatsApp' ? '💬' : '🎙️'}
                  </div>
                  <div className="chat-header-info">
                    <h4>{conv.patientName}</h4>
                    <span>Meridian AI Patient Desk • {conv.language}</span>
                  </div>
                </div>
                <div className="chat-messages" style={{ minHeight: 360, maxHeight: 460 }}>
                  {conv.messages.map((m, i) => (
                    <div key={i} className={`chat-message ${m.sender}`}>
                      <div className="chat-bubble">{m.text}</div>
                      <div className="chat-time">{m.time}</div>
                    </div>
                  ))}
                  <div style={{ clear: 'both' }}></div>
                </div>
                <div className="chat-metadata">
                  <span className="chat-metadata-item"><strong>Channel:</strong> {conv.channel}</span>
                  <span className="chat-metadata-item"><strong>Language:</strong> {conv.language}</span>
                  <span className="chat-metadata-item"><strong>Intent:</strong> {conv.intent}</span>
                  <span className="chat-metadata-item"><strong>Status:</strong> {conv.status}</span>
                  <span className="chat-metadata-item"><strong>Patient:</strong> {conv.patientName}</span>
                </div>
              </div>
            ) : (
              <div className="card">
                <div className="card-body" style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
                  <Bot size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
                  <h3 style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 4 }}>Select a Conversation</h3>
                  <p style={{ fontSize: 13 }}>Click on a conversation from the list to view the chat history</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Architecture Tab */}
      {activeTab === 'architecture' && (
        <div className="card">
          <div className="card-header"><h3>AI Patient Desk Architecture</h3></div>
          <div className="card-body">
            <div className="architecture-flow">
              <div className="arch-node patient">👤 Patient</div>
              <div className="arch-arrow">↓</div>
              <div className="arch-node channel">📱 WhatsApp / 🎙️ Voice</div>
              <div className="arch-arrow">↓</div>
              <div className="arch-node ai">🤖 Meridian AI Patient Desk</div>
              <div className="arch-arrow">↓</div>
              <div className="arch-node process">🧠 Intent Detection & NLP</div>
              <div className="arch-arrow">↓</div>
              <div className="arch-node data">🗄️ Hospital Data / Appointment System</div>
              <div className="arch-arrow">↓</div>
              <div className="arch-node action">⚡ Action (Book / Reschedule / Query)</div>
              <div className="arch-arrow">↓</div>
              <div className="arch-node response">💬 AI Response</div>
              <div className="arch-arrow">↓</div>
              <div className="arch-node patient">👤 Patient</div>
            </div>

            <div style={{ marginTop: 32 }}>
              <h4 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12 }}>Supported AI Intents</h4>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {intents.map(intent => (
                  <span key={intent} className="intent-badge" style={{ padding: '6px 14px', fontSize: 12 }}>
                    {intent}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Voice Tab */}
      {activeTab === 'voice' && (
        <VoiceAgentUI />
      )}
    </div>
  );
};

/* ═══ Voice Agent UI ═══ */
const VoiceAgentUI: React.FC = () => {
  const [isActive, setIsActive] = useState(true);
  const [isMuted, setIsMuted] = useState(false);

  const transcript = [
    { speaker: 'Patient', text: 'I want to book an appointment with a cardiologist.', isAI: false },
    { speaker: 'AI', text: 'Sure! Which date would you prefer for your cardiology appointment?', isAI: true },
    { speaker: 'Patient', text: 'Tomorrow afternoon, please.', isAI: false },
    { speaker: 'AI', text: 'I found two available cardiology appointments for tomorrow afternoon:\n\n1. Dr. Surendhar G — 2:00 PM\n2. Dr. G. Shanthosh — 3:30 PM\n\nWhich slot would you prefer?', isAI: true },
    { speaker: 'Patient', text: 'The 2 PM slot with Dr. Surendhar.', isAI: false },
    { speaker: 'AI', text: 'Your appointment with Dr. Surendhar G has been confirmed for tomorrow at 2:00 PM in the Cardiology department. Please arrive 15 minutes early. Is there anything else I can help you with?', isAI: true },
  ];

  return (
    <div>
      <div className="page-header" style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 18 }}>Meridian AI Voice Patient Desk</h2>
        <p>Prototype voice interface — no real microphone integration</p>
      </div>

      <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
        {/* Voice Control Panel */}
        <div className="voice-container" style={{ flex: '0 0 360px' }}>
          <button
            className={`voice-mic-btn ${isActive ? 'active' : ''}`}
            onClick={() => setIsActive(!isActive)}
          >
            {isActive ? <Phone size={36} /> : <Mic size={36} />}
          </button>

          <div className="voice-status">
            {isActive ? '🔴 Call Active — Listening...' : 'Press to start voice call'}
          </div>

          {isActive && (
            <>
              <div className="voice-duration">04:32</div>
              <div className="voice-waveform">
                {Array.from({ length: 10 }).map((_, i) => (
                  <div key={i} className="bar" />
                ))}
              </div>
              <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginTop: 8, flexWrap: 'wrap' }}>
                <span className="channel-badge voice">🎙️ Voice</span>
                <span className="intent-badge">English</span>
                <span className="status-badge active">Active</span>
              </div>
            </>
          )}

          <div className="voice-controls">
            <button
              className={`btn ${isMuted ? 'btn-danger' : 'btn-secondary'}`}
              onClick={() => setIsMuted(!isMuted)}
            >
              <Volume2 size={16} /> {isMuted ? 'Unmute' : 'Mute'}
            </button>
            <button className="btn btn-danger" onClick={() => setIsActive(false)}>
              <Phone size={16} /> End Call
            </button>
          </div>

          <div style={{ marginTop: 16, padding: '8px 12px', background: 'var(--bg-primary)', borderRadius: 8, fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
            Select Language: &nbsp;
            <select style={{ border: '1px solid var(--border)', borderRadius: 4, padding: '4px 8px', fontSize: 12, fontFamily: 'inherit' }}>
              <option>English</option>
              <option>Tamil</option>
              <option>Hindi</option>
              <option>Telugu</option>
            </select>
          </div>
        </div>

        {/* Transcript */}
        <div className="card" style={{ flex: 1, minWidth: 300 }}>
          <div className="card-header"><h3>Conversation Transcript</h3></div>
          <div className="card-body" style={{ padding: 0 }}>
            <div className="voice-transcript" style={{ margin: 0, background: 'white', borderRadius: 0 }}>
              {transcript.map((item, i) => (
                <div key={i} className="voice-transcript-item">
                  <span className={`speaker ${item.isAI ? 'ai' : ''}`}>{item.speaker}</span>
                  <span className="text" style={{ whiteSpace: 'pre-line' }}>{item.text}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AIPatientDesk;
