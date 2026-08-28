import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Mic, RotateCcw, AlertTriangle, ArrowLeft, 
  MessageSquare, Settings, User, Check, CheckCheck, Play, Square
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'PATIENT' | 'AI_AGENT' | 'SYSTEM';
  text: string;
  timestamp: string;
  language?: string;
  intent?: string;
  toolCalled?: string | null;
  missingSlots?: string[];
}

const VOICE_PROMPTS = [
  { text: "Hi, I need an appointment.", lang: "English", display: "🎙️ [EN] \"Hi, I need an appointment.\"" },
  { text: "Is Dr. Arun available tomorrow?", lang: "English", display: "🎙️ [EN] \"Is Dr. Arun available tomorrow?\"" },
  { text: "General Medicine tomorrow at 09:00 AM.", lang: "English", display: "🎙️ [EN] \"General Medicine tomorrow at 09:00 AM.\"" },
  { text: "நான் ஒரு அப்பாயிண்ட்மெண்ட் பதிவு செய்ய வேண்டும்.", lang: "Tamil", display: "🎙️ [TA] \"நான் ஒரு அப்பாயிண்ட்மெண்ட் பதிவு செய்ய வேண்டும்.\"" },
  { text: "मुझे कल डॉक्टर अरुण से मिलना है।", lang: "Hindi", display: "🎙️ [HI] \"मुझे कल डॉक्टर अरुण से मिलना है।\"" },
  { text: "నాకు రేపు అపాయింట్మెంట్ కావాలి.", lang: "Telugu", display: "🎙️ [TE] \"నాకు రేపు అపాయింట్మెంట్ కావాలి.\"" },
  { text: "I want to cancel my appointment.", lang: "English", display: "🎙️ [EN] \"I want to cancel my appointment.\"" },
  { text: "Reschedule APT10001 to next Monday.", lang: "English", display: "🎙️ [EN] \"Reschedule APT10001 to next Monday.\"" },
];

const PatientChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('ENGLISH');
  const [selectedPatientCode, setSelectedPatientCode] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [showDebugMenu, setShowDebugMenu] = useState(false);
  
  // Voice Simulation state
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [selectedPrompt, setSelectedPrompt] = useState(VOICE_PROMPTS[0]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const BASE_URL = 'http://localhost:8000';

  // Initialize unique session
  useEffect(() => {
    resetSession();
  }, []);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Voice recording timer
  useEffect(() => {
    let interval: any;
    if (isRecording) {
      interval = setInterval(() => {
        setRecordingSeconds(prev => prev + 1);
      }, 1000);
    } else {
      setRecordingSeconds(0);
    }
    return () => clearInterval(interval);
  }, [isRecording]);

  const resetSession = () => {
    const newId = 'CONV_' + Math.random().toString(36).substr(2, 9).toUpperCase();
    setConversationId(newId);
    setMessages([
      {
        id: 'welcome',
        sender: 'AI_AGENT',
        text: 'Welcome to Meridian Hospital AI Desk. How can I assist you today? (You can type or send a simulated voice message).',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        intent: 'GREETING',
        language: 'ENGLISH'
      }
    ]);
  };

  const sendMessage = async (textToSend: string, isVoice = false) => {
    if (!textToSend.trim()) return;

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsgId = 'msg_' + Date.now();
    
    // 1. Append user message locally
    const newUserMsg: ChatMessage = {
      id: userMsgId,
      sender: 'PATIENT',
      text: textToSend,
      timestamp
    };
    
    setMessages(prev => [...prev, newUserMsg]);
    setInputText('');
    setIsTyping(true);

    // 2. Fetch AI agent reply
    try {
      const response = await fetch(`${BASE_URL}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          patient_id: selectedPatientCode || null,
          message: textToSend,
          language: selectedLanguage
        })
      });

      if (!response.ok) {
        throw new Error('Backend failed');
      }

      const data = await response.json();
      
      // Update selected language if changed by backend
      if (data.language && data.language !== selectedLanguage) {
        setSelectedLanguage(data.language);
      }

      const aiMsg: ChatMessage = {
        id: 'msg_ai_' + Date.now(),
        sender: 'AI_AGENT',
        text: data.response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        language: data.language,
        intent: data.intent,
        toolCalled: data.tool_called,
        missingSlots: data.missing_information
      };

      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      // Offline fallback simulator
      setTimeout(() => {
        const errorMsg: ChatMessage = {
          id: 'error_' + Date.now(),
          sender: 'SYSTEM',
          text: 'Connection error. Please ensure the backend server is running.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, errorMsg]);
      }, 800);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      sendMessage(inputText);
    }
  };

  // Simulates voice audio upload
  const triggerVoiceRecording = () => {
    setIsRecording(true);
    // Simulate recording for 2.5 seconds, then submit
    setTimeout(() => {
      setIsRecording(false);
      setShowVoiceModal(false);
      sendMessage(selectedPrompt.text, true);
    }, 2500);
  };

  return (
    <div style={{
      display: 'flex',
      height: 'calc(100vh - 64px)',
      background: '#f0f2f5',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#303030'
    }}>
      {/* Sidebar Controls */}
      {showDebugMenu && (
        <div style={{
        width: '320px',
        background: '#ffffff',
        borderRight: '1px solid #e0e0e0',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '2px 0 5px rgba(0,0,0,0.02)'
      }}>
        {/* Header */}
        <div style={{
          padding: '20px',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          background: 'linear-gradient(135deg, #128C7E, #075E54)',
          color: '#ffffff'
        }}>
          <MessageSquare size={24} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '16px' }}>POC Sandbox</div>
            <div style={{ fontSize: '12px', opacity: 0.8 }}>WhatsApp Agent Desk</div>
          </div>
        </div>

        {/* Configurations */}
        <div style={{ padding: '20px', flex: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#666', marginBottom: '6px' }}>
              ACT AS PATIENT CODE (Pre-fill)
            </label>
            <select 
              value={selectedPatientCode} 
              onChange={(e) => setSelectedPatientCode(e.target.value)}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                border: '1px solid #ccc',
                outline: 'none',
                fontSize: '14px',
                background: '#fafafa'
              }}
            >
              <option value="">-- No registered code (guest booking) --</option>
              <option value="P001">P001 (Acting as registered P001)</option>
              <option value="P002">P002 (Acting as registered P002)</option>
              <option value="P003">P003 (Acting as registered P003)</option>
            </select>
            <div style={{ fontSize: '11px', color: '#888', marginTop: '4px' }}>
              If set, sends patient code validation parameter on chat payload.
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#666', marginBottom: '6px' }}>
              PREFERRED LANGUAGE
            </label>
            <select 
              value={selectedLanguage} 
              onChange={(e) => setSelectedLanguage(e.target.value)}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '6px',
                border: '1px solid #ccc',
                outline: 'none',
                fontSize: '14px',
                background: '#fafafa'
              }}
            >
              <option value="ENGLISH">ENGLISH</option>
              <option value="TAMIL">TAMIL (தமிழ்)</option>
              <option value="HINDI">HINDI (हिंदी)</option>
              <option value="TELUGU">TELUGU (తెలుగు)</option>
              <option value="MALAYALAM">MALAYALAM (മലയാളം)</option>
              <option value="KANNADA">KANNADA (ಕನ್ನಡ)</option>
              <option value="URDU">URDU (اردو)</option>
            </select>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#666', marginBottom: '6px' }}>
              SESSION ID
            </label>
            <div style={{ 
              background: '#f5f5f5', 
              padding: '10px', 
              borderRadius: '6px', 
              fontSize: '13px', 
              fontFamily: 'monospace',
              border: '1px solid #e0e0e0',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <span>{conversationId}</span>
              <button 
                onClick={resetSession} 
                title="Reset Session"
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#128C7E' }}
              >
                <RotateCcw size={16} />
              </button>
            </div>
          </div>

          {/* Guidelines */}
          <div style={{ 
            background: '#e3f2fd', 
            padding: '12px', 
            borderRadius: '6px', 
            fontSize: '12px', 
            color: '#0d47a1', 
            lineHeight: 1.4,
            marginTop: 'auto'
          }}>
            <strong>💡 Testing Tip:</strong> Say "Hi" to greet the agent, or ask "I have fever" to see symptom matching. Say "English please" or "தமிழில்" to watch the language swap dynamic trigger.
          </div>
        </div>
      </div>
      )}

      {/* Main Chat Simulator Workspace */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        background: '#efeae2',
        position: 'relative'
      }}>
        {/* WhatsApp Header bar */}
        <div style={{
          height: '60px',
          background: '#f0f2f5',
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          justifyContent: 'space-between',
          zIndex: 10
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Hospital avatar */}
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              background: '#128C7E',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '16px'
            }}>
              MH
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: '15px', color: '#111b21' }}>Meridian Hospital AI Desk</div>
              <div style={{ fontSize: '12px', color: '#54656f', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#25D366', display: 'inline-block' }} />
                AI Multilingual Assistant (Active)
              </div>
            </div>
          </div>
          
          <div style={{ display: 'flex', gap: '16px', color: '#54656f' }}>
            <Settings 
              size={20} 
              style={{ cursor: 'pointer', color: showDebugMenu ? '#128C7E' : '#54656f' }} 
              onClick={() => setShowDebugMenu(!showDebugMenu)} 
            />
          </div>
        </div>

        {/* Scrollable messages container */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px 40px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px'
        }}>
          {messages.map((m) => {
            if (m.sender === 'SYSTEM') {
              return (
                <div key={m.id} style={{
                  alignSelf: 'center',
                  background: '#ffe0b2',
                  color: '#e65100',
                  padding: '6px 12px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                }}>
                  <AlertTriangle size={14} />
                  <span>{m.text}</span>
                </div>
              );
            }

            const isAgent = m.sender === 'AI_AGENT';
            return (
              <div 
                key={m.id} 
                style={{
                  alignSelf: isAgent ? 'flex-start' : 'flex-end',
                  maxWidth: '65%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                {/* Bubble card */}
                <div style={{
                  background: isAgent ? '#ffffff' : '#d9fdd3',
                  color: '#111b21',
                  padding: '8px 12px',
                  borderRadius: isAgent ? '0px 12px 12px 12px' : '12px 0px 12px 12px',
                  fontSize: '14.5px',
                  lineHeight: '1.45',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                  position: 'relative'
                }}>
                  {/* Message content */}
                  <div>{m.text}</div>

                  {/* Timestamp and Check */}
                  <div style={{
                    fontSize: '10px',
                    color: '#667781',
                    textAlign: 'right',
                    marginTop: '4px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'flex-end',
                    gap: '4px'
                  }}>
                    {m.timestamp}
                    {!isAgent && <CheckCheck size={14} style={{ color: '#53bdeb' }} />}
                  </div>
                </div>

                {/* Developer slot metadata tags */}
                {showDebugMenu && isAgent && (m.intent || m.toolCalled) && (
                  <div style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: '4px',
                    marginTop: '2px',
                    alignSelf: 'flex-start'
                  }}>
                    {m.intent && (
                      <span style={{
                        background: '#e0f2f1',
                        color: '#00695c',
                        fontSize: '9px',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '10px',
                        border: '1px solid #b2dfdb'
                      }}>
                        INTENT: {m.intent}
                      </span>
                    )}
                    {m.toolCalled && (
                      <span style={{
                        background: '#efebe9',
                        color: '#4e342e',
                        fontSize: '9px',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '10px',
                        border: '1px solid #d7ccc8'
                      }}>
                        TOOL: {m.toolCalled}
                      </span>
                    )}
                    {m.missingSlots && m.missingSlots.length > 0 && (
                      <span style={{
                        background: '#fff3e0',
                        color: '#e65100',
                        fontSize: '9px',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '10px',
                        border: '1px solid #ffe0b2'
                      }}>
                        MISSING: {m.missingSlots.join(', ')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
          
          {isTyping && (
            <div style={{
              alignSelf: 'flex-start',
              background: '#ffffff',
              padding: '10px 16px',
              borderRadius: '0px 12px 12px 12px',
              boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
              fontSize: '13px',
              color: '#666',
              fontStyle: 'italic',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <span className="dot-blink" style={{ display: 'inline-block', width: '6px', height: '6px', background: '#999', borderRadius: '50%' }}></span>
              Meridian Agent is typing...
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div style={{
          height: '62px',
          background: '#f0f2f5',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: '12px',
          borderTop: '1px solid #e0e0e0'
        }}>
          {/* Audio voice simulation button */}
          <button
            onClick={() => setShowVoiceModal(true)}
            title="Simulate Voice Input"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              border: 'none',
              background: '#128C7E',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              transition: 'transform 0.1s'
            }}
            onMouseDown={(e) => e.currentTarget.style.transform = 'scale(0.9)'}
            onMouseUp={(e) => e.currentTarget.style.transform = 'scale(1)'}
          >
            <Mic size={20} />
          </button>

          <input 
            type="text"
            placeholder="Type a message..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyPress}
            style={{
              flex: 1,
              height: '42px',
              background: '#ffffff',
              border: 'none',
              outline: 'none',
              borderRadius: '8px',
              padding: '0 16px',
              fontSize: '14.5px',
              boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.05)'
            }}
          />

          <button
            onClick={() => sendMessage(inputText)}
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              border: 'none',
              background: '#128C7E',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
            }}
          >
            <Send size={18} />
          </button>
        </div>
      </div>

      {/* Multilingual Voice Simulation Dialogue Box */}
      {showVoiceModal && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(17, 27, 33, 0.65)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 999
        }}>
          <div style={{
            background: '#ffffff',
            width: '450px',
            borderRadius: '12px',
            boxShadow: '0 8px 30px rgba(0,0,0,0.15)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            {/* Modal Header */}
            <div style={{
              background: '#075E54',
              color: '#ffffff',
              padding: '16px 20px',
              fontWeight: 700,
              fontSize: '16px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}>
              <span>🎙️ Multilingual Voice Agent Simulator</span>
              <button 
                onClick={() => setShowVoiceModal(false)}
                style={{ background: 'none', border: 'none', color: '#ffffff', cursor: 'pointer', fontSize: '18px' }}
              >
                &times;
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ fontSize: '13.5px', color: '#54656f', lineHeight: 1.4 }}>
                Real voice recordings are parsed via multilingual voice channels (Twilio/WhatsApp Voice). In this POC, select a pre-recorded test utterance to simulate voice translation:
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#666', marginBottom: '6px' }}>
                  SELECT RECORDING UTTERANCE
                </label>
                <select 
                  value={VOICE_PROMPTS.indexOf(selectedPrompt)} 
                  onChange={(e) => setSelectedPrompt(VOICE_PROMPTS[Number(e.target.value)])}
                  style={{
                    width: '100%',
                    padding: '10px',
                    borderRadius: '6px',
                    border: '1px solid #ccc',
                    outline: 'none',
                    fontSize: '13.5px',
                    background: '#fafafa'
                  }}
                >
                  {VOICE_PROMPTS.map((p, idx) => (
                    <option key={idx} value={idx}>{p.display}</option>
                  ))}
                </select>
              </div>

              {/* Recording Animation Waveform */}
              {isRecording ? (
                <div style={{
                  background: '#f8f9fa',
                  border: '1px dashed #25D366',
                  borderRadius: '8px',
                  padding: '24px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '12px'
                }}>
                  {/* Wave bar animation */}
                  <div style={{ display: 'flex', gap: '4px', alignItems: 'center', height: '30px' }}>
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(i => (
                      <div 
                        key={i} 
                        className="wave-bar" 
                        style={{
                          width: '4px',
                          background: '#25D366',
                          borderRadius: '2px',
                          animationDelay: `${i * 0.1}s`
                        }}
                      />
                    ))}
                  </div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#128C7E' }}>
                    Simulating audio upload: {recordingSeconds}s
                  </div>
                </div>
              ) : (
                <div style={{
                  background: '#f8f9fa',
                  border: '1px solid #e0e0e0',
                  borderRadius: '8px',
                  padding: '16px',
                  fontSize: '13px',
                  color: '#444'
                }}>
                  <div><strong>Selected transcript:</strong></div>
                  <div style={{ fontStyle: 'italic', marginTop: '4px', color: '#111b21', fontSize: '14px' }}>
                    "{selectedPrompt.text}"
                  </div>
                  <div style={{ fontSize: '11px', color: '#888', marginTop: '6px' }}>
                    Language Code: <strong>{selectedPrompt.lang.toUpperCase()}</strong>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div style={{
              background: '#f0f2f5',
              padding: '12px 20px',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '12px',
              borderTop: '1px solid #e0e0e0'
            }}>
              <button
                onClick={() => setShowVoiceModal(false)}
                disabled={isRecording}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid #ccc',
                  background: '#ffffff',
                  cursor: 'pointer',
                  fontSize: '13.5px'
                }}
              >
                Cancel
              </button>
              <button
                onClick={triggerVoiceRecording}
                disabled={isRecording}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#128C7E',
                  color: '#ffffff',
                  cursor: 'pointer',
                  fontWeight: 600,
                  fontSize: '13.5px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px'
                }}
              >
                <Play size={16} />
                Send Audio Recording
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Simple wave and dot animations */}
      <style>{`
        .dot-blink {
          animation: blink 1.4s infinite both;
        }
        @keyframes blink {
          0% { opacity: .2; }
          20% { opacity: 1; }
          100% { opacity: .2; }
        }
        .wave-bar {
          height: 100%;
          animation: wave 1.2s ease-in-out infinite alternate;
        }
        @keyframes wave {
          0% { height: 8px; }
          100% { height: 28px; }
        }
      `}</style>
    </div>
  );
};

export default PatientChat;
