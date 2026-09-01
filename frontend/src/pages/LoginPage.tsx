import React, { useState } from 'react';
import { useAuth, UserRole } from '../context/AuthContext';
import { requestDoctorOTP, resetDoctorPasswordWithOTP, isValidEmail, isValidPhone } from '../services/dashboardApi';
import { MessageSquare, Mic, Globe, Shield, KeyRound, X, CheckCircle, AlertCircle } from 'lucide-react';
import logo from '../assets/logo.svg';

const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('admin');
  const [error, setError] = useState('');

  // Forgot Password OTP Modal state
  const [showForgotModal, setShowForgotModal] = useState(false);
  const [forgotStep, setForgotStep] = useState<'REQUEST' | 'VERIFY'>('REQUEST');
  const [identifier, setIdentifier] = useState('');
  const [otpCode, setOtpCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpMessage, setOtpMessage] = useState('');
  const [otpError, setOtpError] = useState('');
  const [debugOtp, setDebugOtp] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username.trim()) {
      setError('Please enter your Username.');
      return;
    }
    if (!password) {
      setError('Please enter your Password.');
      return;
    }
    const result = await login(username.trim(), password, role);
    if (!result.success) {
      setError(result.error || 'Login failed');
    }
  };

  const handleRequestOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    setOtpError('');
    setOtpMessage('');
    setDebugOtp('');
    if (!identifier.trim()) {
      setOtpError('Please enter your Username, Phone number, or Email.');
      return;
    }
    setOtpLoading(true);
    try {
      const res = await requestDoctorOTP(identifier.trim());
      if (res.success) {
        setOtpMessage(res.message || 'OTP sent successfully!');
        if (res.debug_otp) setDebugOtp(res.debug_otp);
        setForgotStep('VERIFY');
      } else {
        setOtpError(res.error || 'Failed to send OTP.');
      }
    } finally {
      setOtpLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setOtpError('');
    setOtpMessage('');
    if (!otpCode.trim() || !newPassword.trim()) {
      setOtpError('Please enter the 6-digit OTP and new password.');
      return;
    }
    if (newPassword.length < 6) {
      setOtpError('Password must be at least 6 characters.');
      return;
    }
    setOtpLoading(true);
    try {
      const res = await resetDoctorPasswordWithOTP(identifier.trim(), otpCode.trim(), newPassword);
      if (res.success) {
        alert('✓ Password updated successfully! You can now log in with your new password.');
        setShowForgotModal(false);
        setForgotStep('REQUEST');
        setPassword(newPassword);
        setRole('doctor');
      } else {
        setOtpError(res.error || 'Password reset failed.');
      }
    } finally {
      setOtpLoading(false);
    }
  };

  const closeForgotModal = () => {
    setShowForgotModal(false);
    setForgotStep('REQUEST');
    setIdentifier('');
    setOtpCode('');
    setNewPassword('');
    setOtpMessage('');
    setOtpError('');
    setDebugOtp('');
  };

  return (
    <div className="login-page">
      <div className="login-left">
        <div className="login-left-content">
          <img src={logo} alt="Meridian Hospital" className="login-logo" />
          <h1 className="login-hospital-name">Meridian Hospital</h1>
          <p className="login-tagline">The Family Hospital</p>
          <p className="login-location">Kolathur, Chennai</p>
          <div className="login-message">
            Delivering compassionate, world-class healthcare with advanced AI-powered patient communication across WhatsApp, Voice, and multilingual channels.
          </div>
          <div className="login-features">
            <div className="login-feature">
              <MessageSquare /> WhatsApp AI
            </div>
            <div className="login-feature">
              <Mic /> Voice Agent
            </div>
            <div className="login-feature">
              <Globe /> Multilingual
            </div>
            <div className="login-feature">
              <Shield /> Secure Portal
            </div>
          </div>
        </div>
      </div>
      <div className="login-right">
        <form className="login-card" onSubmit={handleSubmit}>
          <h2>Welcome to Meridian Hospital</h2>
          <p className="subtitle">AI Patient Desk & Hospital Management</p>
          
          {error && <div className="login-error">{error}</div>}
          
          <div className="form-group">
            <label>Username</label>
            <input
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>
          <div className="form-group">
            <label>Role</label>
            <select value={role} onChange={e => setRole(e.target.value as UserRole)}>
              <option value="admin">Admin</option>
              <option value="doctor">Doctor</option>
            </select>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Doctor access support available</span>
            <button
              type="button"
              onClick={() => setShowForgotModal(true)}
              style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontSize: 13, fontWeight: 600, padding: 0 }}
            >
              Forgot Password?
            </button>
          </div>

          <button type="submit" className="login-btn">Sign In</button>
          <div className="login-demo-tag">
            🔬 Prototype / Demo Environment
          </div>
        </form>
      </div>

      {/* Forgot Password OTP Modal */}
      {showForgotModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          padding: 20,
        }}>
          <div style={{
            background: 'var(--bg-primary)', borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: 460, boxShadow: '0 20px 60px rgba(0,0,0,0.3)', padding: 24,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <KeyRound size={20} color="var(--primary)" />
                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Doctor Password Reset</h3>
              </div>
              <button onClick={closeForgotModal} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <X size={20} />
              </button>
            </div>

            {otpError && (
              <div className="error-alert" style={{ marginBottom: 12, fontSize: 13 }}>
                <AlertCircle size={15} /> {otpError}
              </div>
            )}

            {otpMessage && (
              <div className="success-alert" style={{ marginBottom: 12, fontSize: 13 }}>
                <CheckCircle size={15} /> {otpMessage}
              </div>
            )}

            {debugOtp && (
              <div style={{ background: '#FEF3C7', color: '#92400E', padding: '8px 12px', borderRadius: 6, fontSize: 12, fontWeight: 600, marginBottom: 12 }}>
                🔑 Demo Environment OTP Code: <code style={{ fontSize: 14, textDecoration: 'underline' }}>{debugOtp}</code>
              </div>
            )}

            {forgotStep === 'REQUEST' ? (
              <form onSubmit={handleRequestOTP}>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 16 }}>
                  Enter your registered Username, Phone Number, or Email. An OTP will be sent to confirm password change.
                </p>
                <div style={{ marginBottom: 20 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    Username, Phone, or Email
                  </label>
                  <input
                    type="text"
                    value={identifier}
                    onChange={e => setIdentifier(e.target.value)}
                    placeholder="e.g., dr.surendhar or +91 9876543210"
                    style={{ width: '100%', padding: '10px 14px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 14 }}
                    required
                  />
                </div>
                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-secondary" onClick={closeForgotModal} disabled={otpLoading}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={otpLoading}>
                    {otpLoading ? 'Sending OTP...' : 'Send OTP'}
                  </button>
                </div>
              </form>
            ) : (
              <form onSubmit={handleResetPassword}>
                <div style={{ marginBottom: 14 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    Enter 6-Digit OTP
                  </label>
                  <input
                    type="text"
                    maxLength={6}
                    value={otpCode}
                    onChange={e => setOtpCode(e.target.value)}
                    placeholder="123456"
                    style={{ width: '100%', padding: '10px 14px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 16, letterSpacing: 4, textAlign: 'center', fontWeight: 700 }}
                    required
                  />
                </div>

                <div style={{ marginBottom: 20 }}>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 6 }}>
                    Enter New Password
                  </label>
                  <input
                    type="password"
                    value={newPassword}
                    onChange={e => setNewPassword(e.target.value)}
                    placeholder="Minimum 6 characters"
                    style={{ width: '100%', padding: '10px 14px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 14 }}
                    required
                  />
                </div>

                <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                  <button type="button" className="btn btn-secondary" onClick={() => setForgotStep('REQUEST')} disabled={otpLoading}>Back</button>
                  <button type="submit" className="btn btn-primary" disabled={otpLoading}>
                    {otpLoading ? 'Resetting...' : 'Confirm & Change Password'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default LoginPage;
