import React, { useState } from 'react';
import { Hospital, Users, Bot, Bell, Globe, Shield } from 'lucide-react';
import logo from '../../assets/logo.svg';

const SettingsPage: React.FC = () => {
  const [toggles, setToggles] = useState<Record<string, boolean>>({
    notifications: true,
    aiDesk: true,
    whatsapp: true,
    voice: true,
    sms: true,
    email: true,
    tamil: true,
    hindi: true,
    telugu: true,
  });

  const toggle = (key: string) => setToggles(prev => ({ ...prev, [key]: !prev[key] }));

  return (
    <div>
      <div className="page-header">
        <h2>Settings</h2>
        <p>Configure hospital and application settings</p>
        <span className="demo-badge">⚠️ Demo settings — changes are not persisted</span>
      </div>

      {/* Hospital Information */}
      <div className="settings-section">
        <h3><Hospital size={18} style={{ marginRight: 8, color: 'var(--primary)' }} />Hospital Information</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
          <img src={logo} alt="Meridian Hospital" style={{ width: 48, height: 48, borderRadius: 10 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 16 }}>Meridian Hospital</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>The Family Hospital — Kolathur, Chennai</div>
          </div>
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Hospital Name</h4><p>Meridian Hospital</p></div>
          <button className="btn btn-secondary btn-sm">Edit</button>
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Contact Number</h4><p>044 6666 9910</p></div>
          <button className="btn btn-secondary btn-sm">Edit</button>
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Emergency Number</h4><p>044 6666 9999</p></div>
          <button className="btn btn-secondary btn-sm">Edit</button>
        </div>
      </div>

      {/* User Management */}
      <div className="settings-section">
        <h3><Users size={18} style={{ marginRight: 8, color: 'var(--primary)' }} />User Management</h3>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Admin Users</h4><p>1 admin user configured</p></div>
          <button className="btn btn-secondary btn-sm">Manage</button>
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Doctor Users</h4><p>2 doctor users configured (demo)</p></div>
          <button className="btn btn-secondary btn-sm">Manage</button>
        </div>
      </div>

      {/* AI Patient Desk */}
      <div className="settings-section">
        <h3><Bot size={18} style={{ marginRight: 8, color: 'var(--primary)' }} />AI Patient Desk Settings</h3>
        <div className="settings-item">
          <div className="settings-item-label"><h4>AI Patient Desk</h4><p>Enable or disable the AI conversational agent</p></div>
          <div className={`toggle-switch ${toggles.aiDesk ? 'active' : ''}`} onClick={() => toggle('aiDesk')} />
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>WhatsApp Integration</h4><p>Enable WhatsApp messaging channel</p></div>
          <div className={`toggle-switch ${toggles.whatsapp ? 'active' : ''}`} onClick={() => toggle('whatsapp')} />
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Voice Agent</h4><p>Enable voice-based AI interaction</p></div>
          <div className={`toggle-switch ${toggles.voice ? 'active' : ''}`} onClick={() => toggle('voice')} />
        </div>
      </div>

      {/* Notifications */}
      <div className="settings-section">
        <h3><Bell size={18} style={{ marginRight: 8, color: 'var(--primary)' }} />Notification Settings</h3>
        <div className="settings-item">
          <div className="settings-item-label"><h4>SMS Notifications</h4><p>Send SMS for appointments and reminders</p></div>
          <div className={`toggle-switch ${toggles.sms ? 'active' : ''}`} onClick={() => toggle('sms')} />
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Email Notifications</h4><p>Send email confirmations</p></div>
          <div className={`toggle-switch ${toggles.email ? 'active' : ''}`} onClick={() => toggle('email')} />
        </div>
      </div>

      {/* Languages */}
      <div className="settings-section">
        <h3><Globe size={18} style={{ marginRight: 8, color: 'var(--primary)' }} />Language Settings</h3>
        <div className="settings-item">
          <div className="settings-item-label"><h4>English</h4><p>Default language</p></div>
          <div className="toggle-switch active" style={{ cursor: 'not-allowed', opacity: 0.6 }} />
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Tamil (தமிழ்)</h4><p>Enable Tamil language support</p></div>
          <div className={`toggle-switch ${toggles.tamil ? 'active' : ''}`} onClick={() => toggle('tamil')} />
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Hindi (हिन्दी)</h4><p>Enable Hindi language support</p></div>
          <div className={`toggle-switch ${toggles.hindi ? 'active' : ''}`} onClick={() => toggle('hindi')} />
        </div>
        <div className="settings-item">
          <div className="settings-item-label"><h4>Telugu (తెలుగు)</h4><p>Enable Telugu language support</p></div>
          <div className={`toggle-switch ${toggles.telugu ? 'active' : ''}`} onClick={() => toggle('telugu')} />
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
