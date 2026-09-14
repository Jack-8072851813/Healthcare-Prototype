import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, Mic, RotateCcw, AlertTriangle, Play, Square, Volume2, VolumeX, CheckCheck, Menu, X, ChevronRight
} from 'lucide-react';

interface ChatMessage {
  id: string;
  sender: 'PATIENT' | 'AI_AGENT' | 'SYSTEM';
  text: string;
  timestamp: string;
  isVoice?: boolean;
  voiceDuration?: string;
  audioUrl?: string; // base64 Data URI or URL
  interactive_buttons?: { id: string; title: string; description?: string }[];
  interactive_type?: string;
  list_button_title?: string;
}

interface SidebarItem {
  id: string;
  icon: string;
  title: string;
  description: string;
  sectionName: string;
}

const SIDEBAR_SERVICES: SidebarItem[] = [
  { id: 'btn_cat_appts', icon: '📅', title: 'Appointments', description: 'Book, view, reschedule or cancel', sectionName: 'Appointments' },
  { id: 'btn_cat_doctors', icon: '👨‍⚕️', title: 'Doctors & Services', description: 'Find doctors and hospital services', sectionName: 'Doctors & Services' },
  { id: 'btn_cat_health', icon: '📋', title: 'My Health & Records', description: 'Reports, documents and pre-admission', sectionName: 'My Health & Records' },
  { id: 'btn_cat_billing', icon: '💳', title: 'Billing & Payments', description: 'Bills, balance and insurance', sectionName: 'Billing & Payments' },
  { id: 'btn_cat_voice_lang', icon: '🎤', title: 'Voice & Language', description: 'Language and voice', sectionName: 'Voice & Language' },
  { id: 'btn_cat_staff', icon: '🧑‍💼', title: 'Talk to Hospital Staff', description: 'Human support', sectionName: 'Talk to Staff' },
  { id: 'btn_cat_emergency', icon: '🚨', title: 'Emergency', description: 'Immediate safety route', sectionName: 'Emergency' },
];

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

const formatMessageText = (text: string) => {
  if (!text) return null;
  const lines = text.split('\n');
  return lines.map((line, lineIdx) => {
    const parts = line.split(/(\*[^*]+\*)/g);
    return (
      <React.Fragment key={lineIdx}>
        {lineIdx > 0 && <br />}
        {parts.map((part, partIdx) => {
          if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
            return (
              <strong key={partIdx} style={{ color: '#075E54', fontWeight: 700 }}>
                {part.slice(1, -1)}
              </strong>
            );
          }
          return part;
        })}
      </React.Fragment>
    );
  });
};

const PatientChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [currentSection, setCurrentSection] = useState('Overview');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  
  // Voice Recording & Playback State
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recordingStatus, setRecordingStatus] = useState<string | null>(null);
  const [playingAudioId, setPlayingAudioId] = useState<string | null>(null);
  
  // Interactive Slot List Modal State
  const [slotModalOpen, setSlotModalOpen] = useState(false);
  const [slotModalButtons, setSlotModalButtons] = useState<{ id: string; title: string; description?: string }[]>([]);
  const [slotModalHeader, setSlotModalHeader] = useState('Available Time Slots');

  // Voice Simulator fallback state
  const [showVoiceModal, setShowVoiceModal] = useState(false);
  const [selectedPrompt, setSelectedPrompt] = useState(VOICE_PROMPTS[0]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recordingTimerRef = useRef<any>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);

  const BASE_URL = window.location.hostname === '127.0.0.1' ? 'http://127.0.0.1:8000' : 'http://localhost:8000';

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

  const resetSession = async () => {
    const newId = 'CONV_' + Math.random().toString(36).substr(2, 9).toUpperCase();
    setConversationId(newId);
    setCurrentSection('Overview');
    stopAudio();

    try {
      const response = await fetch(`${BASE_URL}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: newId,
          patient_id: null,
          message: 'Hi'
        })
      });

      if (response.ok) {
        const data = await response.json();
        setMessages([
          {
            id: 'welcome',
            sender: 'AI_AGENT',
            text: data.response,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            interactive_buttons: data.interactive_buttons,
            interactive_type: data.interactive_type,
            list_button_title: data.list_button_title
          }
        ]);
        return;
      }
    } catch (e) {
      console.error(e);
    }

    setMessages([
      {
        id: 'welcome',
        sender: 'AI_AGENT',
        text: 'Meridian Hospital 👋\n\nWelcome to Meridian Hospital.\nHow can I help you today?',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        interactive_buttons: [
          { id: 'btn_cat_appts', title: '📅 Appointments', description: 'Book, view, reschedule or cancel' },
          { id: 'btn_cat_doctors', title: '👨‍⚕️ Doctors & Services', description: 'Find doctors, departments and services' },
          { id: 'btn_cat_inquiries', title: '💬 Patient Help & Inquiries', description: 'Hospital administrative assistance' },
          { id: 'btn_cat_health', title: '📋 My Health & Records', description: 'Reports, appointments, documents and pre-admission' },
          { id: 'btn_cat_billing', title: '💳 Billing & Payments', description: 'Bills, payments and insurance' },
          { id: 'btn_cat_voice_lang', title: '🎤 Voice & Language', description: 'Voice interaction and language selection' },
          { id: 'btn_cat_staff', title: '🧑‍💼 Talk to Hospital Staff', description: 'Human support' },
          { id: 'btn_cat_emergency', title: '🚨 Emergency', description: 'Immediate safety route' }
        ]
      }
    ]);
  };

  // Text message submit
  const sendMessage = async (textToSend: string, buttonId?: string) => {
    if (!textToSend.trim()) return;

    // Track active section if a category button was clicked
    const matchedService = SIDEBAR_SERVICES.find(s => s.id === buttonId || textToSend.includes(s.title));
    if (matchedService) {
      setCurrentSection(matchedService.sectionName);
    } else if (buttonId === 'btn_main_menu') {
      setCurrentSection('Overview');
    }

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
          message: textToSend,
          button_id: buttonId
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
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        interactive_buttons: data.interactive_buttons,
        interactive_type: data.interactive_type,
        list_button_title: data.list_button_title
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

  // Sidebar item click handler
  const handleSidebarClick = (item: SidebarItem) => {
    setCurrentSection(item.sectionName);
    setMobileSidebarOpen(false);
    sendMessage(`${item.icon} ${item.title}`, item.id);
  };

  // Voice Recording Flow
  const handleMicClick = async () => {
    if (isRecording) {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        mediaRecorderRef.current.stop();
      }
    } else {
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
          
          stream.getTracks().forEach(track => track.stop());
        };
        
        mediaRecorder.start();
        setIsRecording(true);
        setRecordingStatus('Listening...');
      } catch (err) {
        console.warn("Microphone access failed or unsupported. Launching Voice Simulator modal...", err);
        setShowVoiceModal(true);
      }
    }
  };

  // Send Voice audio file to backend
  const sendVoiceAudio = async (audioFile: File, displayTranscript: string) => {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsgId = 'msg_voice_' + Date.now();

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
    
    let seconds = 0;
    const interval = setInterval(() => {
      seconds++;
    }, 1000);
    
    setTimeout(() => {
      clearInterval(interval);
      setIsRecording(false);
      
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
    
    audio.onended = () => setPlayingAudioId(null);
    audio.onerror = () => setPlayingAudioId(null);
    
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
      height: '100vh',
      width: '100vw',
      background: '#d1d7db',
      fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#111b21',
      overflow: 'hidden',
      position: 'relative'
    }}>
      {/* LEFT SIDEBAR - PATIENT SERVICES */}
      <div 
        className={`patient-sidebar ${mobileSidebarOpen ? 'open' : ''}`}
        style={{
          width: '320px',
          minWidth: '320px',
          flexShrink: 0,
          background: '#ffffff',
          borderRight: '1px solid #e9edef',
          display: 'flex',
          flexDirection: 'column',
          zIndex: 100,
          boxShadow: '2px 0 8px rgba(0,0,0,0.05)',
          transition: 'transform 0.3s ease'
        }}
      >
        {/* Sidebar Header: Meridian Hospital Branding */}
        <div style={{
          padding: '16px 20px',
          background: '#075E54',
          color: '#ffffff',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                background: '#ffffff',
                color: '#075E54',
                fontWeight: 800,
                fontSize: '15px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 4px rgba(0,0,0,0.15)'
              }}>
                MH
              </div>
              <div style={{ fontWeight: 700, fontSize: '17px', letterSpacing: '-0.2px' }}>
                Meridian Hospital
              </div>
            </div>
            {/* Close button for mobile */}
            <button 
              onClick={() => setMobileSidebarOpen(false)}
              className="mobile-close-btn"
              style={{
                display: 'none',
                background: 'none',
                border: 'none',
                color: '#ffffff',
                cursor: 'pointer'
              }}
            >
              <X size={20} />
            </button>
          </div>
          <div style={{ fontSize: '11.5px', opacity: 0.9, fontWeight: 500, paddingLeft: '46px', marginTop: '-4px' }}>
            AI Patient Desk • WhatsApp Experience
          </div>
        </div>

        {/* Sidebar Navigation Title */}
        <div style={{
          padding: '14px 20px 8px 20px',
          fontSize: '11px',
          fontWeight: 800,
          color: '#075E54',
          letterSpacing: '0.8px',
          textTransform: 'uppercase',
          background: '#f8f9fa',
          borderBottom: '1px solid #f0f2f5'
        }}>
          PATIENT SERVICES
        </div>

        {/* Sidebar Navigation Links */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '8px 12px',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          {SIDEBAR_SERVICES.map((item) => {
            const isActive = currentSection === item.sectionName;
            return (
              <div
                key={item.id}
                onClick={() => handleSidebarClick(item)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '10px 12px',
                  borderRadius: '10px',
                  cursor: 'pointer',
                  background: isActive ? '#e8f5e9' : 'transparent',
                  borderLeft: isActive ? '4px solid #128C7E' : '4px solid transparent',
                  transition: 'all 0.15s ease'
                }}
                onMouseOver={(e) => {
                  if (!isActive) e.currentTarget.style.background = '#f5f6f6';
                }}
                onMouseOut={(e) => {
                  if (!isActive) e.currentTarget.style.background = 'transparent';
                }}
              >
                <div style={{ fontSize: '20px', marginRight: '12px', minWidth: '24px', textAlign: 'center' }}>
                  {item.icon}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ 
                    fontWeight: isActive ? 700 : 600, 
                    fontSize: '13.5px', 
                    color: isActive ? '#075E54' : '#111b21',
                    lineHeight: 1.2
                  }}>
                    {item.title}
                  </div>
                  <div style={{ 
                    fontSize: '11px', 
                    color: '#667781', 
                    whiteSpace: 'nowrap', 
                    overflow: 'hidden', 
                    textOverflow: 'ellipsis',
                    marginTop: '2px'
                  }}>
                    {item.description}
                  </div>
                </div>
                <ChevronRight size={14} style={{ color: isActive ? '#128C7E' : '#aebac1', marginLeft: '6px' }} />
              </div>
            );
          })}
        </div>

        {/* Sidebar Footer info */}
        <div style={{
          padding: '12px 16px',
          background: '#f0f2f5',
          borderTop: '1px solid #e9edef',
          fontSize: '11px',
          color: '#54656f',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <span>24/7 AI Desk Active</span>
          <button
            onClick={resetSession}
            style={{
              background: 'none',
              border: 'none',
              color: '#128C7E',
              fontWeight: 700,
              cursor: 'pointer',
              fontSize: '11px',
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <RotateCcw size={12} /> Reset
          </button>
        </div>
      </div>

      {/* CENTER CHAT AREA */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: '#efeae2',
        position: 'relative'
      }}>
        {/* Chat Header */}
        <div style={{
          height: '60px',
          background: '#075E54',
          color: '#ffffff',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          justifyContent: 'space-between',
          zIndex: 10,
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {/* Mobile menu toggle button */}
            <button 
              onClick={() => setMobileSidebarOpen(true)}
              className="mobile-menu-btn"
              style={{
                display: 'none',
                background: 'none',
                border: 'none',
                color: '#ffffff',
                cursor: 'pointer',
                padding: '4px'
              }}
            >
              <Menu size={22} />
            </button>

            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '50%',
              background: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#075E54',
              fontWeight: 800,
              fontSize: '15px'
            }}>
              MH
            </div>
            <div>
              <div style={{ fontWeight: 700, fontSize: '15px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>Meridian Hospital</span>
                <span style={{ fontSize: '13px', opacity: 0.85, fontWeight: 400 }}>—</span>
                <span style={{ fontSize: '13.5px', color: '#a7ffeb', fontWeight: 600 }}>{currentSection}</span>
              </div>
              <div style={{ fontSize: '11.5px', opacity: 0.9, display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#25D366', display: 'inline-block' }} />
                AI Patient Desk • WhatsApp Experience
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
              fontSize: '12px',
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
            <RotateCcw size={13} />
            Start Over
          </button>
        </div>

        {/* Scrollable Chat Messages Container */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px 24px',
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
                  padding: '6px 14px',
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
                  maxWidth: '82%',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                {/* Message Card Bubble */}
                <div style={{
                  background: isAgent ? '#ffffff' : '#d9fdd3',
                  color: '#111b21',
                  padding: '10px 14px',
                  borderRadius: isAgent ? '0px 12px 12px 12px' : '12px 0px 12px 12px',
                  fontSize: '14px',
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
                    <div>{formatMessageText(m.text)}</div>
                  )}

                  {/* Interactive List Button (for time slots) */}
                  {isAgent && m.interactive_buttons && m.interactive_buttons.length > 0 && (m.interactive_type === 'list' || m.interactive_buttons.some(b => b.id.startsWith('btn_slot_'))) && (
                    <div style={{ marginTop: '10px' }}>
                      <button
                        onClick={() => {
                          setSlotModalButtons(m.interactive_buttons || []);
                          setSlotModalHeader(m.text.split('\n')[0].replace(/\*/g, '') || 'Available Time Slots');
                          setSlotModalOpen(true);
                        }}
                        style={{
                          width: '100%',
                          padding: '10px 14px',
                          background: '#f0f2f5',
                          color: '#075E54',
                          border: '1.5px solid #128C7E',
                          borderRadius: '8px',
                          fontWeight: 700,
                          fontSize: '13.5px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '8px',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                          transition: 'all 0.2s ease'
                        }}
                        onMouseOver={(e) => e.currentTarget.style.background = '#e8f5e9'}
                        onMouseOut={(e) => e.currentTarget.style.background = '#f0f2f5'}
                      >
                        <span>{m.list_button_title || 'Choose a time ▼'}</span>
                      </button>
                    </div>
                  )}

                  {/* Standard Interactive Action Buttons & Category Cards */}
                  {isAgent && m.interactive_buttons && m.interactive_buttons.length > 0 && m.interactive_type !== 'list' && !m.interactive_buttons.some(b => b.id.startsWith('btn_slot_')) && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '10px' }}>
                      {m.interactive_buttons.map((btn) => {
                        const hasDesc = !!btn.description || btn.id.startsWith('btn_cat_');
                        if (hasDesc) {
                          return (
                            <div
                              key={btn.id}
                              onClick={() => sendMessage(btn.title, btn.id)}
                              style={{
                                background: '#ffffff',
                                border: '1.5px solid #128C7E',
                                borderRadius: '10px',
                                padding: '10px 14px',
                                cursor: 'pointer',
                                boxShadow: '0 2px 4px rgba(0,0,0,0.04)',
                                transition: 'all 0.18s ease'
                              }}
                              onMouseOver={(e) => {
                                e.currentTarget.style.background = '#e8f5e9';
                                e.currentTarget.style.transform = 'translateY(-1px)';
                              }}
                              onMouseOut={(e) => {
                                e.currentTarget.style.background = '#ffffff';
                                e.currentTarget.style.transform = 'none';
                              }}
                            >
                              <div style={{ fontWeight: 700, fontSize: '13.5px', color: '#075E54' }}>
                                {btn.title}
                              </div>
                              {btn.description && (
                                <div style={{ fontSize: '11.5px', color: '#54656f', marginTop: '2px', lineHeight: 1.3 }}>
                                  {btn.description}
                                </div>
                              )}
                            </div>
                          );
                        }
                        return (
                          <button
                            key={btn.id}
                            onClick={() => sendMessage(btn.title, btn.id)}
                            style={{
                              width: '100%',
                              padding: '9px 14px',
                              background: '#ffffff',
                              border: '1px solid #128C7E',
                              borderRadius: '8px',
                              color: '#075E54',
                              fontWeight: 600,
                              fontSize: '13px',
                              cursor: 'pointer',
                              textAlign: 'center',
                              boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                              transition: 'all 0.15s ease'
                            }}
                            onMouseOver={(e) => {
                              e.currentTarget.style.background = '#e8f5e9';
                            }}
                            onMouseOut={(e) => {
                              e.currentTarget.style.background = '#ffffff';
                            }}
                          >
                            {btn.title}
                          </button>
                        );
                      })}
                    </div>
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

                  {/* Timestamp & Blue Tick */}
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
              Meridian AI Assistant is typing...
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

        {/* BOTTOM MESSAGE COMPOSER */}
        <div style={{
          height: '64px',
          background: '#f0f2f5',
          display: 'flex',
          alignItems: 'center',
          padding: '0 16px',
          gap: '10px',
          borderTop: '1px solid #e0e0e0'
        }}>
          {/* Emoji button */}
          <button
            style={{
              background: 'none',
              border: 'none',
              fontSize: '20px',
              cursor: 'pointer',
              opacity: 0.75,
              padding: '4px'
            }}
            title="Emoji"
          >
            😊
          </button>

          {/* Text Input */}
          <input 
            type="text"
            placeholder="Message Meridian Hospital..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyPress}
            disabled={isRecording}
            style={{
              flex: 1,
              height: '44px',
              background: '#ffffff',
              border: 'none',
              outline: 'none',
              borderRadius: '8px',
              padding: '0 16px',
              fontSize: '14.5px',
              boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.05)'
            }}
          />

          {/* Microphone button */}
          <button
            onClick={handleMicClick}
            title={isRecording ? "Stop Recording" : "Record Voice Message"}
            style={{
              width: '42px',
              height: '42px',
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

          {/* Send Arrow Button */}
          <button
            onClick={() => sendMessage(inputText)}
            disabled={isRecording || !inputText.trim()}
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              border: 'none',
              background: (!inputText.trim() || isRecording) ? '#b0bec5' : '#128C7E',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
              transition: 'background 0.2s'
            }}
          >
            <Send size={18} />
          </button>
        </div>
      </div>

      {/* Interactive Time-Slot Selection List Modal */}
      {slotModalOpen && (
        <div style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(17, 27, 33, 0.65)',
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'center',
          zIndex: 998
        }}>
          <div style={{
            background: '#ffffff',
            width: '100%',
            maxWidth: '650px',
            borderTopLeftRadius: '16px',
            borderTopRightRadius: '16px',
            boxShadow: '0 -4px 30px rgba(0,0,0,0.2)',
            display: 'flex',
            flexDirection: 'column',
            maxHeight: '75%',
            overflow: 'hidden'
          }}>
            {/* List Modal Header */}
            <div style={{
              background: '#075E54',
              color: '#ffffff',
              padding: '14px 20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderTopLeftRadius: '16px',
              borderTopRightRadius: '16px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '18px' }}>📅</span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: '15px' }}>{slotModalHeader || 'Select Appointment Time'}</div>
                  <div style={{ fontSize: '11.5px', opacity: 0.85 }}>Tap an available slot to book</div>
                </div>
              </div>
              <button 
                onClick={() => setSlotModalOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#ffffff',
                  cursor: 'pointer',
                  fontSize: '22px',
                  padding: '0 4px',
                  lineHeight: 1
                }}
              >
                &times;
              </button>
            </div>

            {/* Scrollable list of options */}
            <div style={{
              padding: '16px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              maxHeight: '380px',
              background: '#f8f9fa'
            }}>
              {slotModalButtons.map((btn) => (
                <div
                  key={btn.id}
                  onClick={() => {
                    setSlotModalOpen(false);
                    sendMessage(btn.title, btn.id);
                  }}
                  style={{
                    background: '#ffffff',
                    border: '1px solid #e0e0e0',
                    borderRadius: '8px',
                    padding: '12px 16px',
                    fontSize: '14.5px',
                    fontWeight: 600,
                    color: '#111b21',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.15s ease',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.background = '#e8f5e9';
                    e.currentTarget.style.borderColor = '#128C7E';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.background = '#ffffff';
                    e.currentTarget.style.borderColor = '#e0e0e0';
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '16px', color: '#128C7E' }}>⏰</span>
                    <span>{btn.title}</span>
                  </div>
                  <span style={{ fontSize: '12px', color: '#128C7E', fontWeight: 700 }}>Select →</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

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

      {/* Responsive Styles & Animations */}
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
        @media (max-width: 768px) {
          .patient-sidebar {
            position: absolute !important;
            top: 0;
            bottom: 0;
            left: 0;
            transform: translateX(-100%);
            box-shadow: 4px 0 15px rgba(0,0,0,0.2) !important;
          }
          .patient-sidebar.open {
            transform: translateX(0) !important;
          }
          .mobile-menu-btn, .mobile-close-btn {
            display: flex !important;
          }
        }
      `}</style>
    </div>
  );
};

export default PatientChat;
