import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { fetchDashboardSummary, updateDoctorSelfProfile, isValidEmail, isValidPhone, type DashboardSummary } from '../../services/dashboardApi';
import { Mail, Phone, Building2, Stethoscope, Edit3, Save, X, CheckCircle, Lock, User } from 'lucide-react';
import logo from '../../assets/logo.svg';

const DoctorProfile: React.FC = () => {
  const { user } = useAuth();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  // Edit Mode state
  const [editMode, setEditMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState('');
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  const [form, setForm] = useState({
    first_name: '',
    last_name: '',
    phone: '',
    email: '',
    specialization: '',
    qualification: '',
    username: '',
    password: '',
  });

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast(msg);
    setToastType(type);
    setTimeout(() => setToast(''), 4000);
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const s = await fetchDashboardSummary();
      setSummary(s);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleStartEdit = () => {
    const names = (user?.name || '').split(' ');
    setForm({
      first_name: names[0] || '',
      last_name: names.slice(1).join(' ') || '',
      phone: '',
      email: '',
      specialization: '',
      qualification: '',
      username: user?.username || '',
      password: '',
    });
    setEditMode(true);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.email && !isValidEmail(form.email)) {
      showToast('❌ Please enter a valid Email address (e.g. doctor@meridian.com)', 'error');
      return;
    }
    if (form.phone && !isValidPhone(form.phone)) {
      showToast('❌ Phone number must contain exactly 10 digits', 'error');
      return;
    }
    if (form.password && form.password.trim() && form.password.trim().length < 6) {
      showToast('❌ Password must be at least 6 characters long', 'error');
      return;
    }
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      if (form.first_name) payload.first_name = form.first_name.trim();
      if (form.last_name) payload.last_name = form.last_name.trim();
      if (form.phone) payload.phone = form.phone.trim();
      if (form.email) payload.email = form.email.trim();
      if (form.specialization) payload.specialization = form.specialization.trim();
      if (form.qualification) payload.qualification = form.qualification.trim();
      if (form.username && form.username !== user?.username) payload.username = form.username.trim();
      if (form.password) payload.password = form.password;

      const res = await updateDoctorSelfProfile(payload);
      if (res.success) {
        showToast('✓ Profile and login credentials updated successfully!');
        setEditMode(false);
        // Update local session username if changed
        if (form.username && user) {
          user.username = form.username;
          user.loginId = form.username;
          sessionStorage.setItem('meridian_user', JSON.stringify(user));
        }
      } else {
        showToast(`❌ ${res.error || 'Failed to update profile'}`, 'error');
      }
    } finally {
      setSaving(false);
    }
  };

  const getInitials = (name: string) => name.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2);

  if (loading) {
    return <div style={{ padding: 60, textAlign: 'center', color: 'var(--text-muted)' }}>Loading profile...</div>;
  }

  return (
    <div>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>Doctor Profile</h2>
          <p>Your professional profile, contact details, and account credentials</p>
        </div>
        {!editMode ? (
          <button className="btn btn-primary" onClick={handleStartEdit} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Edit3 size={15} /> Edit My Profile & Credentials
          </button>
        ) : (
          <button className="btn btn-secondary" onClick={() => setEditMode(false)} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <X size={15} /> Cancel Editing
          </button>
        )}
      </div>

      {toast && (
        <div className={toastType === 'success' ? 'success-alert' : 'error-alert'} style={{ marginBottom: 16 }}>
          <CheckCircle size={16} /> {toast}
        </div>
      )}

      {/* Profile Header */}
      <div className="profile-header">
        <div className="profile-avatar">
          {user?.name ? getInitials(user.name) : '?'}
        </div>
        <div className="profile-info">
          <h2>{user?.name || 'Doctor'}</h2>
          <div className="meta">
            {user?.department && (
              <span><Building2 size={14} /> {user.department}</span>
            )}
            <span><User size={14} /> Username: <strong>{user?.username}</strong></span>
            <span className="status-badge active">ACTIVE</span>
          </div>
        </div>
      </div>

      {editMode ? (
        <form onSubmit={handleSaveProfile} className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <h3><Edit3 size={16} style={{ marginRight: 8 }} />Edit Personal Details & Security Credentials</h3>
          </div>
          <div className="card-body">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 20 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>First Name</label>
                <input
                  value={form.first_name}
                  onChange={e => setForm(f => ({ ...f, first_name: e.target.value }))}
                  style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Last Name</label>
                <input
                  value={form.last_name}
                  onChange={e => setForm(f => ({ ...f, last_name: e.target.value }))}
                  style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Phone Number</label>
                <input
                  value={form.phone}
                  onChange={e => setForm(f => ({ ...f, phone: e.target.value }))}
                  placeholder="+91 9876543210"
                  style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Email Address</label>
                <input
                  type="email"
                  value={form.email}
                  onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  placeholder="doctor@meridian.com"
                  style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Specialization</label>
                <input
                  value={form.specialization}
                  onChange={e => setForm(f => ({ ...f, specialization: e.target.value }))}
                  placeholder="e.g. Cardiologist"
                  style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)' }}
                />
              </div>

              <div>
                <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Qualification</label>
                <input
                  value={form.qualification}
                  onChange={e => setForm(f => ({ ...f, qualification: e.target.value }))}
                  placeholder="e.g. MBBS, MD"
                  style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)' }}
                />
              </div>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: 16, borderRadius: 'var(--radius-md)', marginBottom: 20 }}>
              <h4 style={{ fontSize: 14, fontWeight: 700, color: 'var(--primary)', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                <Lock size={15} /> Update Username & Password
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>New Username</label>
                  <input
                    value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-primary)' }}
                  />
                </div>

                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>New Password</label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    placeholder="Enter new password to change"
                    style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', background: 'var(--bg-primary)' }}
                  />
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button type="button" className="btn btn-secondary" onClick={() => setEditMode(false)} disabled={saving}>Cancel</button>
              <button type="submit" className="btn btn-primary" disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Save size={15} /> {saving ? 'Saving...' : 'Save Profile Changes'}
              </button>
            </div>
          </div>
        </form>
      ) : null}

      <div className="profile-grid">
        <div className="card">
          <div className="card-header"><h3>Professional Information</h3></div>
          <div className="card-body">
            <div className="info-row"><label>Full Name</label><span>{user?.name || '—'}</span></div>
            <div className="info-row"><label>Username</label><span>{user?.username || '—'}</span></div>
            <div className="info-row"><label>Department</label><span>{user?.department || '—'}</span></div>
            <div className="info-row"><label>Role</label><span style={{ textTransform: 'capitalize' }}>{user?.role || '—'}</span></div>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><h3>Today's Stats</h3></div>
          <div className="card-body">
            <div className="info-row">
              <label>Today's Appointments</label>
              <span style={{ fontWeight: 700, color: 'var(--primary)', fontSize: 18 }}>
                {loading ? '—' : summary?.appointments.today ?? 0}
              </span>
            </div>
            <div className="info-row">
              <label>My Patients (Total)</label>
              <span style={{ fontWeight: 700, fontSize: 18 }}>
                {loading ? '—' : summary?.patients.total ?? 0}
              </span>
            </div>
            <div className="info-row">
              <label>Upcoming</label>
              <span style={{ fontWeight: 700, fontSize: 18 }}>
                {loading ? '—' : summary?.appointments.upcoming ?? 0}
              </span>
            </div>
            <div className="info-row">
              <label>Open Escalations</label>
              <span style={{ fontWeight: 700, color: summary?.escalations.open ? '#E53E3E' : 'inherit', fontSize: 18 }}>
                {loading ? '—' : summary?.escalations.open ?? 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 12, background: 'var(--primary-lightest)', borderRadius: 'var(--radius-lg)' }}>
          <img src={logo} alt="Meridian Hospital" style={{ width: 36, height: 36, borderRadius: 8 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Meridian Hospital</div>
            <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>The Family Hospital · Kolathur, Chennai</div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DoctorProfile;
