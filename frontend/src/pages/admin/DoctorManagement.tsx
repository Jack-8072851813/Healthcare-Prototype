import React, { useState, useEffect, useCallback } from 'react';
import { Search, RefreshCw, ToggleLeft, ToggleRight, Plus, X, Save, Edit3 } from 'lucide-react';
import {
  fetchDoctors, updateDoctorStatus, fetchDepartments, createDoctor, updateDoctorByAdmin,
  isValidEmail, isValidPhone,
  type Doctor, type Department, type NewDoctorPayload
} from '../../services/dashboardApi';

const STATUS_CLASS: Record<string, string> = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  ON_LEAVE: 'pending',
};

interface DoctorForm {
  first_name: string;
  last_name: string;
  specialization: string;
  qualification: string;
  experience_years: string;
  phone: string;
  email: string;
  consultation_fee: string;
  department_id: string;
  username: string;
  password: string;
}

const INITIAL_FORM: DoctorForm = {
  first_name: '', last_name: '', specialization: '', qualification: '',
  experience_years: '', phone: '', email: '', consultation_fee: '',
  department_id: '', username: '', password: '',
};

const DoctorManagement: React.FC = () => {
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  // Add Doctor Modal
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<DoctorForm>(INITIAL_FORM);
  const [formErrors, setFormErrors] = useState<Partial<DoctorForm>>({});
  const [submitting, setSubmitting] = useState(false);

  // Edit Doctor Modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingDoctor, setEditingDoctor] = useState<Doctor | null>(null);
  const [editForm, setEditForm] = useState<Partial<DoctorForm>>({});
  const [editSubmitting, setEditSubmitting] = useState(false);

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast(msg);
    setToastType(type);
    setTimeout(() => setToast(''), 4000);
  };

  const loadDoctors = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchDoctors({
        search: search || undefined,
        department: deptFilter || undefined,
        status: statusFilter || undefined,
      });
      setDoctors(res.doctors);
    } finally {
      setLoading(false);
    }
  }, [search, deptFilter, statusFilter]);

  const loadDepartments = useCallback(async () => {
    const res = await fetchDepartments();
    setDepartments(res.departments);
  }, []);

  useEffect(() => {
    loadDepartments();
  }, [loadDepartments]);

  useEffect(() => {
    const timer = setTimeout(loadDoctors, 300);
    return () => clearTimeout(timer);
  }, [loadDoctors]);

  const toggleDoctorStatus = async (doctor: Doctor) => {
    const next = doctor.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    const ok = await updateDoctorStatus(doctor.id, next);
    if (ok) {
      showToast(`Dr. ${doctor.display_name} → ${next}`);
      loadDoctors();
    } else {
      showToast('❌ Status update failed.', 'error');
    }
  };

  const getInitials = (name: string) =>
    name.split(' ').filter(Boolean).map(n => n[0]).join('').toUpperCase().slice(0, 2);

  const validateForm = (): boolean => {
    const errors: Partial<DoctorForm> = {};
    if (!form.first_name.trim()) {
      errors.first_name = 'First name is required';
      showToast('❌ Please enter First Name', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.last_name.trim()) {
      errors.last_name = 'Last name is required';
      showToast('❌ Please enter Last Name', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.phone.trim()) {
      errors.phone = 'Phone number is required';
      showToast('❌ Please enter Phone Number', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!isValidPhone(form.phone)) {
      errors.phone = 'Phone number must be exactly 10 digits';
      showToast('❌ Phone number must contain exactly 10 digits (e.g. 9876543210)', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.email.trim()) {
      errors.email = 'Email address is required';
      showToast('❌ Please enter Email address', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!isValidEmail(form.email)) {
      errors.email = 'Valid email address required';
      showToast('❌ Please enter a valid Email address (e.g. doctor@meridian.com)', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.specialization.trim()) {
      errors.specialization = 'Specialization is required';
      showToast('❌ Please enter Specialization', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.qualification.trim()) {
      errors.qualification = 'Qualification is required';
      showToast('❌ Please enter Qualification', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.department_id) {
      errors.department_id = 'Department selection is required';
      showToast('❌ Please select a Department', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.experience_years || isNaN(Number(form.experience_years))) {
      errors.experience_years = 'Experience years required';
      showToast('❌ Please enter valid Experience in years', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.consultation_fee || isNaN(Number(form.consultation_fee))) {
      errors.consultation_fee = 'Fee required';
      showToast('❌ Please enter valid Consultation Fee', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.username.trim()) {
      errors.username = 'Username is required';
      showToast('❌ Please enter Username', 'error');
      setFormErrors(errors);
      return false;
    }
    if (!form.password) {
      errors.password = 'Password is required';
      showToast('❌ Please enter Password', 'error');
      setFormErrors(errors);
      return false;
    }
    if (form.password.length < 6) {
      errors.password = 'Password must be at least 6 characters';
      showToast('❌ Password must be at least 6 characters long', 'error');
      setFormErrors(errors);
      return false;
    }
    setFormErrors({});
    return true;
  };

  const handleAddDoctor = async () => {
    if (!validateForm()) return;
    setSubmitting(true);
    try {
      const payload: NewDoctorPayload = {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        specialization: form.specialization.trim(),
        qualification: form.qualification.trim(),
        experience_years: Number(form.experience_years),
        phone: form.phone.trim(),
        email: form.email.trim(),
        consultation_fee: Number(form.consultation_fee),
        department_id: Number(form.department_id),
        username: form.username.trim(),
        password: form.password,
      };
      const result = await createDoctor(payload);
      if (result.success) {
        showToast(`✓ Dr. ${form.first_name} ${form.last_name} added successfully! Welcome email sent to ${form.email}.`);
        setShowModal(false);
        setForm(INITIAL_FORM);
        setFormErrors({});
        loadDoctors();
      } else {
        showToast(`❌ ${result.error || 'Failed to create doctor'}`, 'error');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const openEditModal = (d: Doctor) => {
    setEditingDoctor(d);
    setEditForm({
      first_name: d.first_name || '',
      last_name: d.last_name || '',
      specialization: d.specialization || '',
      qualification: d.qualification || '',
      experience_years: String(d.experience_years || 0),
      phone: d.phone || '',
      email: d.email || '',
      consultation_fee: String(d.consultation_fee || 0),
      department_id: String(d.department_id || ''),
      username: '',
      password: '',
    });
    setShowEditModal(true);
  };

  const handleUpdateDoctor = async () => {
    if (!editingDoctor) return;
    if (editForm.email && !isValidEmail(editForm.email)) {
      showToast('❌ Please enter a valid Email address (e.g. doctor@meridian.com)', 'error');
      return;
    }
    if (editForm.phone && !isValidPhone(editForm.phone)) {
      showToast('❌ Phone number must contain exactly 10 digits', 'error');
      return;
    }
    if (editForm.password && editForm.password.trim() && editForm.password.trim().length < 6) {
      showToast('❌ Password must be at least 6 characters long', 'error');
      return;
    }
    setEditSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        first_name: editForm.first_name,
        last_name: editForm.last_name,
        specialization: editForm.specialization,
        qualification: editForm.qualification,
        experience_years: editForm.experience_years ? Number(editForm.experience_years) : undefined,
        phone: editForm.phone ? editForm.phone.trim() : undefined,
        email: editForm.email ? editForm.email.trim() : undefined,
        consultation_fee: editForm.consultation_fee ? Number(editForm.consultation_fee) : undefined,
        department_id: editForm.department_id ? Number(editForm.department_id) : undefined,
      };
      if (editForm.username && editForm.username.trim()) {
        payload.username = editForm.username.trim();
      }
      if (editForm.password && editForm.password.trim()) {
        payload.password = editForm.password.trim();
      }

      const res = await updateDoctorByAdmin(editingDoctor.id, payload);
      if (res.success) {
        showToast(`✓ Dr. ${editingDoctor.display_name} updated successfully!`);
        setShowEditModal(false);
        setEditingDoctor(null);
        loadDoctors();
      } else {
        showToast(`❌ ${res.error || 'Failed to update doctor'}`, 'error');
      }
    } finally {
      setEditSubmitting(false);
    }
  };

  const handleModalClose = () => {
    setShowModal(false);
    setForm(INITIAL_FORM);
    setFormErrors({});
  };

  const inputStyle = (hasError?: boolean) => ({
    padding: '8px 12px',
    border: `1.5px solid ${hasError ? '#E53E3E' : 'var(--border)'}`,
    borderRadius: 'var(--radius-sm)',
    fontSize: 13,
    fontFamily: 'inherit',
    background: 'var(--bg-primary)',
    width: '100%',
  });

  return (
    <div>
      <div className="page-header">
        <h2>Doctor Management</h2>
        <p>Manage doctor directory, credentials, schedules, and profile details</p>
      </div>

      {toast && (
        <div className={toastType === 'success' ? 'success-alert' : 'error-alert'}>
          {toast}
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div className="search-bar" style={{ maxWidth: 320 }}>
            <Search size={18} />
            <input
              placeholder="Search by name, specialization..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)}
              style={{ padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontFamily: 'inherit' }}>
              <option value="">All Departments</option>
              {departments.map(d => <option key={d.id} value={d.department_name}>{d.department_name}</option>)}
            </select>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
              style={{ padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontFamily: 'inherit' }}>
              <option value="">All Status</option>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
              <option value="ON_LEAVE">On Leave</option>
            </select>
            <button className="btn btn-secondary btn-sm" onClick={loadDoctors} disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              Refresh
            </button>
            <button className="btn btn-primary" onClick={() => setShowModal(true)}
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Plus size={16} /> Add New Doctor
            </button>
          </div>
        </div>

        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>Loading doctors...</div>
          ) : doctors.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>No doctors found.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Doctor</th>
                  <th>Specialization</th>
                  <th>Department</th>
                  <th>Qualification</th>
                  <th>Experience</th>
                  <th>Fee (₹)</th>
                  <th>Today's Appts</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {doctors.map(d => (
                  <tr key={d.id}>
                    <td style={{ fontWeight: 600, color: 'var(--primary)', fontSize: 12 }}>{d.doctor_code}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{
                          width: 34, height: 34, borderRadius: '50%',
                          background: 'var(--primary-lighter)', color: 'var(--primary)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 11, fontWeight: 700, flexShrink: 0
                        }}>
                          {getInitials(d.display_name)}
                        </div>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{d.display_name}</div>
                          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{d.email || '—'}</div>
                        </div>
                      </div>
                    </td>
                    <td style={{ fontSize: 12 }}>{d.specialization}</td>
                    <td style={{ fontSize: 13 }}>{d.department_name}</td>
                    <td style={{ fontSize: 12 }}>{d.qualification}</td>
                    <td style={{ fontSize: 13 }}>{d.experience_years} yrs</td>
                    <td style={{ fontSize: 13, fontWeight: 500 }}>₹{Number(d.consultation_fee).toLocaleString()}</td>
                    <td style={{ fontWeight: 700, textAlign: 'center', color: 'var(--primary)' }}>{d.today_appts}</td>
                    <td>
                      <span className={`status-badge ${STATUS_CLASS[d.status] || ''}`}>{d.status}</span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => openEditModal(d)}
                          title="Edit Details & Credentials"
                          style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          <Edit3 size={13} /> Edit
                        </button>
                        <button
                          className={`btn btn-sm ${d.status === 'ACTIVE' ? 'btn-danger' : 'btn-success'}`}
                          onClick={() => toggleDoctorStatus(d)}
                          title={d.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}
                          style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                        >
                          {d.status === 'ACTIVE'
                            ? <ToggleRight size={14} />
                            : <ToggleLeft size={14} />
                          }
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div style={{ padding: '12px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
          {loading ? 'Loading...' : `${doctors.length} doctor(s) shown`}
        </div>
      </div>

      {/* Add New Doctor Modal */}
      {showModal && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          padding: 20,
        }}>
          <div style={{
            background: 'var(--bg-primary)', borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: 680, maxHeight: '90vh', overflowY: 'auto',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '20px 24px', borderBottom: '1px solid var(--border)',
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Add New Doctor</h3>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>
                  A welcome email with login details will be sent to the registered email.
                </p>
              </div>
              <button onClick={handleModalClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
                <X size={22} />
              </button>
            </div>

            <div style={{ padding: '24px' }}>
              <div style={{ marginBottom: 20 }}>
                <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>Personal Information</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>First Name <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input style={inputStyle(!!formErrors.first_name)} value={form.first_name} onChange={e => {
                      const fn = e.target.value;
                      setForm(f => ({
                        ...f,
                        first_name: fn,
                        username: f.username || (fn && f.last_name ? `dr.${fn.toLowerCase()}.${f.last_name.toLowerCase()}`.replace(/\s+/g, '') : f.username)
                      }));
                    }} placeholder="e.g., James" />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Last Name <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input style={inputStyle(!!formErrors.last_name)} value={form.last_name} onChange={e => {
                      const ln = e.target.value;
                      setForm(f => ({
                        ...f,
                        last_name: ln,
                        username: f.username || (f.first_name && ln ? `dr.${f.first_name.toLowerCase()}.${ln.toLowerCase()}`.replace(/\s+/g, '') : f.username)
                      }));
                    }} placeholder="e.g., Rubert" />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Phone (10 Digits) <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input style={inputStyle(!!formErrors.phone)} value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} placeholder="e.g. 9876543210" maxLength={10} />
                    {formErrors.phone && <span style={{ fontSize: 11, color: '#E53E3E' }}>{formErrors.phone}</span>}
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Email (for Welcome Email) <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input type="email" style={inputStyle(!!formErrors.email)} value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="doctor@meridian.com" />
                    {formErrors.email && <span style={{ fontSize: 11, color: '#E53E3E' }}>{formErrors.email}</span>}
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: 20 }}>
                <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>Professional Information</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Specialization <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input style={inputStyle(!!formErrors.specialization)} value={form.specialization} onChange={e => setForm(f => ({ ...f, specialization: e.target.value }))} placeholder="e.g., Cardiologist" />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Qualification <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input style={inputStyle(!!formErrors.qualification)} value={form.qualification} onChange={e => setForm(f => ({ ...f, qualification: e.target.value }))} placeholder="e.g., MBBS, MD" />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Department <span style={{ color: '#E53E3E' }}>*</span></label>
                    <select style={inputStyle(!!formErrors.department_id)} value={form.department_id} onChange={e => setForm(f => ({ ...f, department_id: e.target.value }))}>
                      <option value="">Select Department</option>
                      {departments.map(d => <option key={d.id} value={d.id}>{d.department_name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Experience (years) <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input type="number" min="0" style={inputStyle(!!formErrors.experience_years)} value={form.experience_years} onChange={e => setForm(f => ({ ...f, experience_years: e.target.value }))} placeholder="e.g., 10" />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Consultation Fee (₹) <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input type="number" min="0" style={inputStyle(!!formErrors.consultation_fee)} value={form.consultation_fee} onChange={e => setForm(f => ({ ...f, consultation_fee: e.target.value }))} placeholder="e.g., 500" />
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: 24 }}>
                <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>Login Account</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Username <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input style={inputStyle(!!formErrors.username)} value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} placeholder="e.g., dr.james.rubert" />
                    {formErrors.username && <span style={{ fontSize: 11, color: '#E53E3E' }}>{formErrors.username}</span>}
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Password <span style={{ color: '#E53E3E' }}>*</span></label>
                    <input type="password" style={inputStyle(!!formErrors.password)} value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))} placeholder="Min 6 characters" />
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                <button className="btn btn-secondary" onClick={handleModalClose} disabled={submitting}>Cancel</button>
                <button className="btn btn-primary" onClick={handleAddDoctor} disabled={submitting} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Save size={15} /> {submitting ? 'Adding...' : 'Add Doctor'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Doctor Modal (Admin edit profile + username & password) */}
      {showEditModal && editingDoctor && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
          padding: 20,
        }}>
          <div style={{
            background: 'var(--bg-primary)', borderRadius: 'var(--radius-lg)',
            width: '100%', maxWidth: 680, maxHeight: '90vh', overflowY: 'auto',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '20px 24px', borderBottom: '1px solid var(--border)',
            }}>
              <div>
                <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Edit Doctor — {editingDoctor.display_name}</h3>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--text-muted)' }}>
                  Update doctor details, specialization, fee, username, and password.
                </p>
              </div>
              <button onClick={() => setShowEditModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
                <X size={22} />
              </button>
            </div>

            <div style={{ padding: '24px' }}>
              <div style={{ marginBottom: 20 }}>
                <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 12 }}>Personal & Professional</h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>First Name</label>
                    <input style={inputStyle()} value={editForm.first_name || ''} onChange={e => setEditForm(f => ({ ...f, first_name: e.target.value }))} />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Last Name</label>
                    <input style={inputStyle()} value={editForm.last_name || ''} onChange={e => setEditForm(f => ({ ...f, last_name: e.target.value }))} />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Phone</label>
                    <input style={inputStyle()} value={editForm.phone || ''} onChange={e => setEditForm(f => ({ ...f, phone: e.target.value }))} />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Email</label>
                    <input type="email" style={inputStyle()} value={editForm.email || ''} onChange={e => setEditForm(f => ({ ...f, email: e.target.value }))} />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Specialization</label>
                    <input style={inputStyle()} value={editForm.specialization || ''} onChange={e => setEditForm(f => ({ ...f, specialization: e.target.value }))} />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Qualification</label>
                    <input style={inputStyle()} value={editForm.qualification || ''} onChange={e => setEditForm(f => ({ ...f, qualification: e.target.value }))} />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Department</label>
                    <select style={inputStyle()} value={editForm.department_id || ''} onChange={e => setEditForm(f => ({ ...f, department_id: e.target.value }))}>
                      <option value="">Select Department</option>
                      {departments.map(d => <option key={d.id} value={d.id}>{d.department_name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Consultation Fee (₹)</label>
                    <input type="number" style={inputStyle()} value={editForm.consultation_fee || ''} onChange={e => setEditForm(f => ({ ...f, consultation_fee: e.target.value }))} />
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: 24, background: 'var(--bg-secondary)', padding: 16, borderRadius: 'var(--radius-md)' }}>
                <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--primary)', textTransform: 'uppercase', marginBottom: 12 }}>
                  Edit Login Credentials (Username & Password)
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>New Username (Optional)</label>
                    <input style={inputStyle()} value={editForm.username || ''} onChange={e => setEditForm(f => ({ ...f, username: e.target.value }))} placeholder="Leave empty to keep current" />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>New Password (Optional)</label>
                    <input type="password" style={inputStyle()} value={editForm.password || ''} onChange={e => setEditForm(f => ({ ...f, password: e.target.value }))} placeholder="Leave empty to keep current" />
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', paddingTop: 16, borderTop: '1px solid var(--border)' }}>
                <button className="btn btn-secondary" onClick={() => setShowEditModal(false)} disabled={editSubmitting}>Cancel</button>
                <button className="btn btn-primary" onClick={handleUpdateDoctor} disabled={editSubmitting} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Save size={15} /> {editSubmitting ? 'Saving...' : 'Save Doctor Details'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DoctorManagement;
