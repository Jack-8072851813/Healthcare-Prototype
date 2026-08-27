import React, { useState } from 'react';
import { useAuth, UserRole } from '../context/AuthContext';
import { MessageSquare, Mic, Globe, Shield } from 'lucide-react';
import logo from '../assets/logo.svg';

const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [role, setRole] = useState<UserRole>('admin');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username || !password) {
      setError('Please enter both username and password.');
      return;
    }
    const result = login(username, password, role);
    if (!result.success) {
      setError(result.error || 'Login failed');
    }
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
          <button type="submit" className="login-btn">Sign In</button>
          <div className="login-demo-tag">
            🔬 Prototype / Demo Environment
          </div>
        </form>
      </div>
    </div>
  );
};

export default LoginPage;
