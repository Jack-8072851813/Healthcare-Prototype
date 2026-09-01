import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Mic, RotateCcw, AlertTriangle, Play, Square, Volume2, VolumeX, CheckCheck
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'PATIENT' | 'AI_AGENT' | 'SYSTEM';
  text: string;
  timestamp: string;
  isVoice?: boolean;
  voiceDuration?: string;
  audioUrl?: string; // base64 Data URI or URL
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
  const [isTyping, setIsTyping] = useState(false);
  
  // Voice Recording & Playback State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recordingStatus, setRecordingStatus] = useState<string | null>(null);
  const [playingAudioId, setPlayingAudioId] = useState<string | null>(null);
  
  // Voice Simulator fallback state
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState(VOICE_PROMPTS[0]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<any>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  const BASE_URL = 'http://localhost:8000';

  // Initialize unique session
  useEffect(() => {
    resetSession();
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
      if (audioPlayerRef.current) audioPlayerRef.current.pause();
    };
  }, []);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping, recordingStatus]);

  // Voice recording timer
  useEffect(() => {
    if (isRecording) {
      recordingTimerRef.current = setInterval(() => {
        setRecordingSeconds(prev => prev + 1);
      }, 1000);
    } else {
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
      }
      setRecordingSeconds(0);
    }
    return () => {
      if (recordingTimerRef.current) clearInterval(recordingTimerRef.current);
    };
  }, [isRecording]);

  const resetSession = () => {
    const newId = 'CONV_' + Math.random().toString(36).substr(2, 9).toUpperCase();
    setConversationId(newId);
    setMessages([
      {
        id: 'welcome',
        sender: 'AI_AGENT',
        text: 'Hello! Welcome to Meridian Hospital. I am your AI Patient Desk Assistant. I can help you with appointments, doctor availability, appointment cancellation or rescheduling, hospital information, and pre-admission assistance. How can I help you today?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      }
    ]);
    stopAudio();
  };

  // Text message submit
  const sendMessage = async (textToSend: string) => {
    if (!textToSend.trim()) return;

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsgId = 'msg_' + Date.now();
    
    const newUserMsg: ChatMessage = {
      id: userMsgId,
      sender: 'PATIENT',
      text: textToSend,
      timestamp
    };
    
    setMessages(prev => [...prev, newUserMsg]);
    setInputText('');
    setIsTyping(true);

    try {
      const response = await fetch(`${BASE_URL}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          patient_id: null,
          message: textToSend
        })
      });

      if (!response.ok) {
        throw new Error('Backend failed');
      }

      const data = await response.json();
      
      const aiMsg: ChatMessage = {
        id: 'msg_ai_' + Date.now(),
        sender: 'AI_AGENT',
        text: data.response,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => [...prev, aiMsg]);
    } catch (error) {
      setTimeout(() => {
        const errorMsg: ChatMessage = {
          id: 'error_' + Date.now(),
          sender: 'SYSTEM',
          text: 'Connection error. Please ensure the backend server is running.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setMessages(prev => [...prev, errorMsg]);
      }, 600);
    } finally {
      setIsTyping(false);
    }
  };

  // Actual Browser Recording Flow
  const handleMicClick = async () => {
    if (isRecording) {
      // Stop recording
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
    } else {
      // Start recording
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunksRef.current = [];
        
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        
        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };
        
        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
          const audioFile = new File([audioBlob], 'microphone_voice.wav', { type: 'audio/wav' });
          sendVoiceAudio(audioFile, '🎤 Voice message');
          
          // Stop all tracks in stream to release microphone light
          stream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorder.start();
        setIsRecording(true);
        setRecordingStatus('Listening...');
      } catch (err) {
        console.warn("Microphone access failed or unsupported. Launching Voice Simulator modal...", err);
        // Fallback to simulator modal
        setShowVoiceModal(true);
      }
    }
  };

  // Send Voice audio file to the backend
  const sendVoiceAudio = async (audioFile: File, displayTranscript: string) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsgId = 'msg_voice_' + Date.now();

    // Add voice bubble locally
    const newUserMsg: ChatMessage = {
      id: userMsgId,
      sender: 'PATIENT',
      text: displayTranscript,
      timestamp,
      isVoice: true,
      voiceDuration: recordingSeconds > 0 ? `00:${recordingSeconds.toString().padStart(2, '0')}` : '00:03'
    };

    setMessages(prev => [...prev, newUserMsg]);
    setIsTyping(true);
    setRecordingStatus('Processing...');

    const formData = new FormData();
    formData.append('audio', audioFile);
    formData.append('session_id', conversationId);

    try {
      setRecordingStatus('AI Assistant is responding...');
      const response = await fetch(`${BASE_URL}/api/agent/voice/process`, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error('Voice process failed');
      }

      const data = await response.json();
      
      const aiMsgId = 'msg_ai_' + Date.now();
      const aiMsg: ChatMessage = {
        id: aiMsgId,
        sender: 'AI_AGENT',
        text: data.response_text,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        audioUrl: data.audio
      };

      setMessages(prev => [...prev, aiMsg]);
      
      // Auto-play the voice response
      if (data.audio) {
        playAudio(data.audio, aiMsgId);
      }
    } catch (error) {
      console.error(error);
      const errorMsg: ChatMessage = {
        id: 'error_' + Date.now(),
        sender: 'SYSTEM',
        text: "I couldn't understand the voice message clearly. Please try again.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
      setIsRecording(false);
      setRecordingStatus(null);
    }
  };

  // Simulated recording from prompt selector
  const triggerSimulatedVoice = () => {
    setIsRecording(true);
    setRecordingStatus('Listening...');
    setShowVoiceModal(false);
    
    // Simulate recording duration of 3 seconds
    let seconds = 0;
    const interval = setInterval(() => {
      seconds++;
    }, 1000);
    
    setTimeout(() => {
      clearInterval(interval);
      setIsRecording(false);
      
      // Generate a mock wav blob to satisfy backend API
      const wavHeader = new Uint8Array(44);
      const audioBlob = new Blob([wavHeader], { type: 'audio/wav' });
      const filename = `${selectedPrompt.lang.toLowerCase()}_${selectedPrompt.text.replace(/[^a-z0-9]/gi, '_').toLowerCase()}.wav`;
      const audioFile = new File([audioBlob], filename, { type: 'audio/wav' });
      
      sendVoiceAudio(audioFile, `🎤 "${selectedPrompt.text}"`);
    }, 3000);
  };

  // Playback handlers
  const playAudio = (audioUrl: string, msgId: string) => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
    }
    
    const audio = new Audio(audioUrl);
    audioPlayerRef.current = audio;
    setPlayingAudioId(msgId);
    
    audio.onended = () => {
      setPlayingAudioId(null);
    };
    audio.onerror = () => {
      setPlayingAudioId(null);
    };
    
    audio.play().catch(err => {
      console.warn("Autoplay was blocked or failed:", err);
      setPlayingAudioId(null);
    });
  };

  const stopAudio = () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      setPlayingAudioId(null);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      sendMessage(inputText);
    }
  };

  return (
    <div style={{
      display: 'flex',
      height: 'calc(100vh - 64px)',
      background: '#f0f2f5',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#303030',
      justifyContent: 'center',
      alignItems: 'center'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '850px',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        background: '#efeae2',
        position: 'relative',
        boxShadow: '0 4px 20px rgba(0,0,0,0.05)'
      }}>
        {/* Branding Header */}
        <div style={{
          height: '60px',
          background: '#075E54',
          color: '#ffffff',
          display: 'flex',
          alignItems: 'center',
          padding: '0 20px',
          justifyContent: 'space-between',
          zIndex: 10,
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              background: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#075E54',
              fontWeight: 700,
              fontSize: '16px'
            }}>
              MH
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: '15px' }}>Meridian Hospital Patient Desk</div>
              <div style={{ fontSize: '12px', opacity: 0.9, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#25D366', display: 'inline-block' }} />
                Online AI Assistant
              </div>
            </div>
          </div>
          
          <button
            onClick={resetSession}
            style={{
              background: '#128C7E',
              color: '#ffffff',
              border: 'none',
              borderRadius: '20px',
              padding: '6px 14px',
              fontSize: '12.5px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              transition: 'background 0.2s'
            }}
            onMouseOver={(e) => e.currentTarget.style.background = '#0b665c'}
            onMouseOut={(e) => e.currentTarget.style.background = '#128C7E'}
          >
            <RotateCcw size={14} />
            Start Over
          </button>
        </div>

        {/* Scrollable messages container */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '24px 30px',
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
                  gap: '6px'
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
                  maxWidth: '75%',
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
                  {/* Voice message indicator */}
                  {m.isVoice ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#128C7E', fontWeight: 600 }}>
                      <Mic size={16} />
                      <span>Voice message</span>
                      <span style={{ fontSize: '11px', color: '#667781', fontWeight: 'normal' }}>({m.voiceDuration})</span>
                    </div>
                  ) : (
                    <div>{m.text}</div>
                  )}

                  {/* Play audio button for AI generated audio response */}
                  {isAgent && m.audioUrl && (
                    <div style={{ marginTop: '8px', borderTop: '1px solid #f0f0f0', paddingTop: '6px' }}>
                      {playingAudioId === m.id ? (
                        <button
                          onClick={stopAudio}
                          style={{
                            background: '#ffebee',
                            color: '#c62828',
                            border: 'none',
                            borderRadius: '4px',
                            padding: '4px 8px',
                            fontSize: '11.5px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <VolumeX size={13} />
                          Pause Audio Response
                        </button>
                      ) : (
                        <button
                          onClick={() => playAudio(m.audioUrl!, m.id)}
                          style={{
                            background: '#e8f5e9',
                            color: '#2e7d32',
                            border: 'none',
                            borderRadius: '4px',
                            padding: '4px 8px',
                            fontSize: '11.5px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                        >
                          <Volume2 size={13} />
                          Play Audio Response
                        </button>
                      )}
                    </div>
                  )}

                  {/* Timestamp */}
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
              Agent is typing...
            </div>
          )}

          {recordingStatus && (
            <div style={{
              alignSelf: 'center',
              background: '#e3f2fd',
              color: '#0d47a1',
              padding: '8px 16px',
              borderRadius: '20px',
              fontSize: '12.5px',
              fontWeight: 600,
              boxShadow: '0 2px 5px rgba(0,0,0,0.05)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <span className="dot-blink" style={{ display: 'inline-block', width: '6px', height: '6px', background: '#0d47a1', borderRadius: '50%' }}></span>
              {recordingStatus}
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
          {/* Microphone button */}
          <button
            onClick={handleMicClick}
            title={isRecording ? "Stop Recording" : "Record Voice Message"}
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              border: 'none',
              background: isRecording ? '#c62828' : '#128C7E',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              animation: isRecording ? 'pulse 1.5s infinite alternate' : 'none'
            }}
          >
            {isRecording ? <Square size={16} /> : <Mic size={20} />}
          </button>

          <input 
            type="text"
            placeholder="Type a message..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={isRecording}
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
            disabled={isRecording || !inputText.trim()}
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              border: 'none',
              background: (!inputText.trim() || isRecording) ? '#b0bec5' : '#128C7E',
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

      {/* Multilingual Voice Simulator Modal (Fallback) */}
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
                Your browser or device has blocked microphone capture. Select a pre-recorded test utterance to simulate voice translation:
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
                onClick={triggerSimulatedVoice}
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

      {/* Simple blink animation and recording pulse */}
      <style>{`
        .dot-blink {
          animation: blink 1.4s infinite both;
        }
        @keyframes blink {
          0% { opacity: .2; }
          20% { opacity: 1; }
          100% { opacity: .2; }
        }
        @keyframes pulse {
          0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(198, 40, 40, 0.4); }
          100% { transform: scale(1.1); box-shadow: 0 0 0 8px rgba(198, 40, 40, 0); }
        }
      `}</style>
    </div>
  );
};

export default PatientChat;
