import React, { useState, useEffect, useCallback } from 'react';
import {
  fetchPreAdmissions, createPreAdmission, updatePreAdmissionStatus,
  sendPreAdmissionNotification, fetchPreAdmissionConversation,
  fetchDoctors, fetchDepartments, fetchPatients,
  format12HourTime,
  type PreAdmissionItem, type Doctor, type Department, type Patient
} from '../../services/dashboardApi';
import {
  BedDouble, FileText, Bell, CheckCircle, MessageSquare, RefreshCw,
  Plus, Search, Filter, AlertTriangle, Eye, Send, X, Clock, User, Check, ShieldAlert
} from 'lucide-react';

const STATUS_OPTIONS = [
  'PENDING', 'CONTACTED', 'CONFIRMED', 'DOCUMENTS_PENDING',
  'READY', 'ESCALATED', 'COMPLETED', 'CANCELLED'
];

const ADMISSION_TYPES = ['INPATIENT', 'SURGERY', 'DAYCARE'];

const PreAdmissionPage: React.FC = () => {
  const [preAdmissions, setPreAdmissions] = useState<PreAdmissionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' } | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');

  // Auxiliary data for modal
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);

  // Modals
  const [showAddModal, setShowAddModal] = useState(false);
  const [showChatModal, setShowChatModal] = useState(false);
  const [showStatusModal, setShowStatusModal] = useState(false);

  // Selected item state
  const [selectedPa, setSelectedPa] = useState<PreAdmissionItem | null>(null);
  const [chatData, setChatData] = useState<{
    patient_name: string;
    conversation?: any;
    messages: any[];
  } | null>(null);
  const [chatLoading, setChatLoading] = useState(false);

  // Form State
  const [formPatientId, setFormPatientId] = useState('');
  const [formDoctorId, setFormDoctorId] = useState('');
  const [formDeptId, setFormDeptId] = useState('');
  const [formType, setFormType] = useState('INPATIENT');
  const [formDate, setFormDate] = useState('');
  const [formTime, setFormTime] = useState('09:00');
  const [formInstructions, setFormInstructions] = useState('');
  const [formRemarks, setFormRemarks] = useState('');
  const [formDocs, setFormDocs] = useState('Government ID, Insurance Card, Doctor Referral Note');
  const [submitting, setSubmitting] = useState(false);

  // Status update form
  const [newStatus, setNewStatus] = useState('');
  const [subDocs, setSubDocs] = useState('');
  const [statusRemarks, setStatusRemarks] = useState('');

  const showToastMsg = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchPreAdmissions({
        search: search || undefined,
        status: statusFilter || undefined,
        admission_type: typeFilter || undefined,
        admission_date: dateFilter || undefined
      });
      setPreAdmissions(res.pre_admissions);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, typeFilter, dateFilter]);

  useEffect(() => {
    const t = setTimeout(loadData, 300);
    return () => clearTimeout(t);
  }, [loadData]);

  // Load auxiliary lists on mount
  useEffect(() => {
    fetchDoctors().then(res => setDoctors(res.doctors || []));
    fetchDepartments().then(res => setDepartments(res.departments || []));
    fetchPatients({ per_page: 100 }).then(res => setPatients(res.patients || []));
  }, []);

  // Handle Doctor change in modal to auto-select department
  const handleDoctorSelect = (docIdStr: string) => {
    setFormDoctorId(docIdStr);
    const selectedDoc = doctors.find(d => String(d.id) === docIdStr);
    if (selectedDoc) {
      setFormDeptId(String(selectedDoc.department_id));
    }
  };

  // Open Chat Modal
  const handleOpenChat = async (pa: PreAdmissionItem) => {
    setSelectedPa(pa);
    setShowChatModal(true);
    setChatLoading(true);
    try {
      const res = await fetchPreAdmissionConversation(pa.id);
      setChatData(res);
    } finally {
      setChatLoading(false);
    }
  };

  // Trigger Notification
  const handleNotify = async (id: number) => {
    showToastMsg('Sending WhatsApp notification...', 'success');
    const res = await sendPreAdmissionNotification(id);
    if (res.success) {
      showToastMsg(`✓ WhatsApp admission notification sent successfully! (${res.whatsapp_number || ''})`, 'success');
      loadData();
    } else {
      showToastMsg(`❌ Notification failed: ${res.error || 'Unknown error'}`, 'error');
    }
  };

  // Create Admission Submission
  const handleCreateAdmission = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formPatientId || !formDoctorId || !formDeptId || !formDate || !formType) {
      showToastMsg('Please fill all required fields.', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const res = await createPreAdmission({
        patient_id: Number(formPatientId),
        doctor_id: Number(formDoctorId),
        department_id: Number(formDeptId),
        admission_type: formType,
        expected_admission_date: formDate,
        expected_checkin_time: formTime,
        instructions: formInstructions,
        remarks: formRemarks,
        pending_documents: formDocs
      });
      if (res.success) {
        showToastMsg(`✓ Admission registered! Code: ${res.pre_admission_code}. WhatsApp message dispatched.`, 'success');
        setShowAddModal(false);
        // Reset form
        setFormPatientId('');
        setFormDoctorId('');
        setFormDeptId('');
        setFormDate('');
        loadData();
      } else {
        showToastMsg(`❌ Registration failed: ${res.error || 'Database error'}`, 'error');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // Open Status Update Modal
  const handleOpenStatusModal = (pa: PreAdmissionItem) => {
    setSelectedPa(pa);
    setNewStatus(pa.status);
    setSubDocs(pa.submitted_documents || '');
    setStatusRemarks(pa.remarks || '');
    setShowStatusModal(true);
  };

  // Submit Status Update
  const handleUpdateStatusSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPa) return;
    setSubmitting(true);
    try {
      const res = await updatePreAdmissionStatus(selectedPa.id, {
        status: newStatus,
        submitted_documents: subDocs,
        remarks: statusRemarks
      });
      if (res.success) {
        showToastMsg('✓ Pre-admission record updated successfully!', 'success');
        setShowStatusModal(false);
        loadData();
      } else {
        showToastMsg(`❌ Update failed: ${res.error}`, 'error');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // KPIs
  const totalCount = preAdmissions.length;
  const pendingCount = preAdmissions.filter(p => p.status === 'PENDING' || p.status === 'CONTACTED').length;
  const confirmedCount = preAdmissions.filter(p => p.status === 'CONFIRMED' || p.status === 'READY' || p.status === 'READY_FOR_ADMISSION').length;
  const escalatedCount = preAdmissions.filter(p => p.status === 'ESCALATED').length;
  const completedCount = preAdmissions.filter(p => p.status === 'COMPLETED').length;

  return (
    <div>
      {toast && (
        <div className={toast.type === 'success' ? 'success-alert' : 'error-alert'} style={{ marginBottom: 16 }}>
          {toast.msg}
        </div>
      )}

      <div className="page-header">
        <div>
          <h2>Patient Admission & Pre-Admission Follow-up</h2>
          <p>Register pre-admissions, manage lifecycle, track documents, and view live WhatsApp interactions.</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => setShowAddModal(true)}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          <Plus size={16} /> Register Admission
        </button>
      </div>

      {/* KPI Cards */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon blue"><BedDouble size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : totalCount}</div>
          <div className="kpi-label">Total Pre-Admissions</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon amber"><Clock size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : pendingCount}</div>
          <div className="kpi-label">Pending / Contacted</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon green"><CheckCircle size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : confirmedCount}</div>
          <div className="kpi-label">Confirmed & Ready</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon red"><ShieldAlert size={22} /></div></div>
          <div className="kpi-value">{loading ? '—' : escalatedCount}</div>
          <div className="kpi-label">Escalated (Needs Staff)</div>
        </div>
      </div>

      {/* Filters Card */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header" style={{ flexWrap: 'wrap', gap: 12 }}>
          <div className="search-bar" style={{ maxWidth: 300, flex: 1 }}>
            <Search size={16} />
            <input
              placeholder="Search code, patient, phone..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Filter size={15} style={{ color: 'var(--text-muted)' }} />

            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All Statuses</option>
              {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>

            <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
              <option value="">All Admission Types</option>
              {ADMISSION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>

            <input
              type="date"
              value={dateFilter}
              onChange={e => setDateFilter(e.target.value)}
              style={{
                padding: '6px 10px',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                fontSize: 13,
                background: 'var(--bg-primary)'
              }}
            />

            {(search || statusFilter || typeFilter || dateFilter) && (
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => { setSearch(''); setStatusFilter(''); setTypeFilter(''); setDateFilter(''); }}
              >
                Clear Filters
              </button>
            )}

            <button className="btn btn-secondary btn-sm" onClick={loadData} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              Refresh
            </button>
          </div>
        </div>

        {/* Data Table */}
        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>Loading pre-admissions...</div>
          ) : preAdmissions.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>No pre-admission records found.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Patient Details</th>
                  <th>Type</th>
                  <th>Expected Date & Time</th>
                  <th>Department & Doctor</th>
                  <th>Status</th>
                  <th>WhatsApp Notif</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {preAdmissions.map(pa => (
                  <tr key={pa.id}>
                    <td style={{ fontWeight: 700, color: 'var(--primary)', fontSize: 13 }}>{pa.pre_admission_code}</td>
                    <td>
                      <div style={{ fontWeight: 600 }}>{pa.patient_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>ID: {pa.patient_code} | {pa.patient_phone}</div>
                    </td>
                    <td>
                      <span className="intent-badge" style={{ background: pa.admission_type === 'SURGERY' ? '#FEE2E2' : '#E0F2FE', color: pa.admission_type === 'SURGERY' ? '#991B1B' : '#0369A1' }}>
                        {pa.admission_type}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>{pa.expected_admission_date}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Check-in: {format12HourTime(pa.expected_checkin_time)}</div>
                    </td>
                    <td>
                      <div style={{ fontWeight: 500 }}>Dr. {pa.doctor_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{pa.department_name}</div>
                    </td>
                    <td>
                      <span
                        className={`status-badge ${
                          pa.status === 'CONFIRMED' || pa.status === 'READY' || pa.status === 'COMPLETED' ? 'active' :
                          pa.status === 'ESCALATED' ? 'pending' :
                          pa.status === 'CANCELLED' ? 'inactive' : 'pending'
                        }`}
                        style={{ cursor: 'pointer' }}
                        onClick={() => handleOpenStatusModal(pa)}
                        title="Click to update status"
                      >
                        {pa.status}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge ${pa.notification_status === 'SENT' ? 'active' : pa.notification_status === 'FAILED' ? 'inactive' : 'pending'}`}>
                        {pa.notification_status}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 6 }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleNotify(pa.id)}
                          title="Resend WhatsApp Notification"
                        >
                          <Send size={13} />
                        </button>
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleOpenChat(pa)}
                          title="View Patient WhatsApp Conversation"
                        >
                          <MessageSquare size={13} /> Chat
                        </button>
                        <button
                          className="btn btn-primary btn-sm"
                          onClick={() => handleOpenStatusModal(pa)}
                        >
                          Update
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ── Modal: Register New Admission ──────────────────────────────────── */}
      {showAddModal && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: 640 }}>
            <div className="modal-header">
              <h3><BedDouble size={18} style={{ marginRight: 8 }} />Register New Pre-Admission</h3>
              <button className="modal-close" onClick={() => setShowAddModal(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleCreateAdmission}>
              <div className="modal-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

                <div style={{ gridColumn: 'span 2' }}>
                  <label className="form-label" style={{ fontWeight: 600 }}>Select Patient *</label>
                  <select
                    className="form-control"
                    value={formPatientId}
                    onChange={e => setFormPatientId(e.target.value)}
                    required
                  >
                    <option value="">-- Select Registered Patient --</option>
                    {patients.map(p => (
                      <option key={p.id} value={p.id}>
                        {p.first_name} {p.last_name} ({p.patient_code}) — {p.phone}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Attending Doctor *</label>
                  <select
                    className="form-control"
                    value={formDoctorId}
                    onChange={e => handleDoctorSelect(e.target.value)}
                    required
                  >
                    <option value="">-- Select Doctor --</option>
                    {doctors.map(d => (
                      <option key={d.id} value={d.id}>
                        Dr. {d.display_name} ({d.specialization})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Department *</label>
                  <select
                    className="form-control"
                    value={formDeptId}
                    onChange={e => setFormDeptId(e.target.value)}
                    required
                  >
                    <option value="">-- Select Department --</option>
                    {departments.map(d => (
                      <option key={d.id} value={d.id}>
                        {d.department_name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Admission Type *</label>
                  <select
                    className="form-control"
                    value={formType}
                    onChange={e => setFormType(e.target.value)}
                    required
                  >
                    {ADMISSION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Expected Date *</label>
                  <input
                    type="date"
                    className="form-control"
                    value={formDate}
                    onChange={e => setFormDate(e.target.value)}
                    required
                  />
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Expected Check-in Time</label>
                  <input
                    type="time"
                    className="form-control"
                    value={formTime}
                    onChange={e => setFormTime(e.target.value)}
                  />
                </div>

                <div style={{ gridColumn: 'span 2' }}>
                  <label className="form-label" style={{ fontWeight: 600 }}>Required / Pending Documents</label>
                  <input
                    type="text"
                    className="form-control"
                    value={formDocs}
                    onChange={e => setFormDocs(e.target.value)}
                    placeholder="e.g. Government ID, Health Insurance Card, Doctor Referral Note"
                  />
                </div>

                <div style={{ gridColumn: 'span 2' }}>
                  <label className="form-label" style={{ fontWeight: 600 }}>Special Instructions for Patient</label>
                  <textarea
                    className="form-control"
                    rows={2}
                    value={formInstructions}
                    onChange={e => setFormInstructions(e.target.value)}
                    placeholder="e.g. Fast 8 hours prior to check-in. Bring regular medications."
                  />
                </div>

                <div style={{ gridColumn: 'span 2' }}>
                  <label className="form-label" style={{ fontWeight: 600 }}>Internal Remarks</label>
                  <textarea
                    className="form-control"
                    rows={2}
                    value={formRemarks}
                    onChange={e => setFormRemarks(e.target.value)}
                    placeholder="Physician notes, bed category requests, etc."
                  />
                </div>

              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Registering & Sending WhatsApp...' : 'Register Admission'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: Update Status & Documents ──────────────────────────────── */}
      {showStatusModal && selectedPa && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <h3>Update Pre-Admission Status ({selectedPa.pre_admission_code})</h3>
              <button className="modal-close" onClick={() => setShowStatusModal(false)}><X size={18} /></button>
            </div>
            <form onSubmit={handleUpdateStatusSubmit}>
              <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Admission Status</label>
                  <select
                    className="form-control"
                    value={newStatus}
                    onChange={e => setNewStatus(e.target.value)}
                  >
                    {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Submitted Documents</label>
                  <input
                    type="text"
                    className="form-control"
                    value={subDocs}
                    onChange={e => setSubDocs(e.target.value)}
                    placeholder="e.g. Aadhaar Card, Insurance Approval Letter"
                  />
                </div>

                <div>
                  <label className="form-label" style={{ fontWeight: 600 }}>Remarks / Notes</label>
                  <textarea
                    className="form-control"
                    rows={3}
                    value={statusRemarks}
                    onChange={e => setStatusRemarks(e.target.value)}
                    placeholder="Follow-up notes, patient response, etc."
                  />
                </div>
              </div>
              <div className="modal-footer">
                <button type="button" className="btn btn-secondary" onClick={() => setShowStatusModal(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary" disabled={submitting}>
                  {submitting ? 'Saving...' : 'Save Updates'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Modal: WhatsApp Conversation View ────────────────────────────── */}
      {showChatModal && selectedPa && (
        <div className="modal-backdrop">
          <div className="modal-content" style={{ maxWidth: 640, maxHeight: '85vh', display: 'flex', flexDirection: 'column' }}>
            <div className="modal-header">
              <div>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <MessageSquare size={18} color="#25D366" />
                  WhatsApp Conversation — {selectedPa.patient_name}
                </h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  Code: {selectedPa.pre_admission_code} | Phone: {selectedPa.patient_phone}
                </span>
              </div>
              <button className="modal-close" onClick={() => setShowChatModal(false)}><X size={18} /></button>
            </div>

            <div className="modal-body" style={{ flex: 1, overflowY: 'auto', background: '#F0F2F5', padding: 16 }}>
              {chatLoading ? (
                <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading conversation history...</div>
              ) : !chatData || !chatData.messages || chatData.messages.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                  No WhatsApp messages exchanged yet for this pre-admission.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {chatData.messages.map((m: any) => {
                    const isPatient = m.sender_type === 'PATIENT';
                    return (
                      <div
                        key={m.id}
                        style={{
                          alignSelf: isPatient ? 'flex-start' : 'flex-end',
                          maxWidth: '80%',
                          background: isPatient ? '#FFFFFF' : '#DCF8C6',
                          padding: '10px 14px',
                          borderRadius: 12,
                          boxShadow: '0 1px 2px rgba(0,0,0,0.1)',
                          fontSize: 13,
                          lineHeight: 1.5
                        }}
                      >
                        <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 4, color: isPatient ? '#0284C7' : '#15803D' }}>
                          {isPatient ? '👤 Patient' : '🤖 AI Agent'} {m.intent ? `(${m.intent})` : ''}
                        </div>
                        <div style={{ whiteSpace: 'pre-wrap' }}>{m.message_text}</div>
                        <div style={{ fontSize: 10, color: '#888', marginTop: 4, textAlign: 'right' }}>
                          {m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ background: '#FFF' }}>
              <button className="btn btn-secondary" onClick={() => setShowChatModal(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PreAdmissionPage;

