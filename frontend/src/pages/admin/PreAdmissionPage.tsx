import React from 'react';
import { preAdmissions } from '../../data/aiConversations';
import { BedDouble, FileText, Bell, CheckCircle, AlertTriangle, MessageSquare } from 'lucide-react';

const PreAdmissionPage: React.FC = () => {
  const upcoming = preAdmissions.filter(p => p.admissionStatus === 'Scheduled').length;
  const docsPending = preAdmissions.filter(p => p.documentsSubmitted < p.documentsRequired).length;
  const followUpsDue = preAdmissions.filter(p => p.followUpStatus === 'Pending' || p.followUpStatus === 'Overdue').length;
  const completed = preAdmissions.filter(p => p.followUpStatus === 'Completed').length;

  return (
    <div>
      <div className="page-header">
        <h2>Pre-Admission Follow-up</h2>
        <p>Manage upcoming admissions and patient follow-ups</p>
      </div>

      {/* KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon blue"><BedDouble size={22} /></div></div>
          <div className="kpi-value">{upcoming}</div>
          <div className="kpi-label">Upcoming Admissions</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon amber"><FileText size={22} /></div></div>
          <div className="kpi-value">{docsPending}</div>
          <div className="kpi-label">Documents Pending</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon red"><Bell size={22} /></div></div>
          <div className="kpi-value">{followUpsDue}</div>
          <div className="kpi-label">Follow-ups Due</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-card-header"><div className="kpi-icon green"><CheckCircle size={22} /></div></div>
          <div className="kpi-value">{completed}</div>
          <div className="kpi-label">Completed</div>
        </div>
      </div>

      {/* AI Reminder Example */}
      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <h3><MessageSquare size={16} style={{ marginRight: 8 }} />AI Pre-Admission Reminder (Sample)</h3>
        </div>
        <div className="card-body">
          <div style={{ background: '#DCF8C6', padding: 16, borderRadius: 10, maxWidth: 440, fontSize: 14, lineHeight: 1.7, color: '#303030' }}>
            <p style={{ fontWeight: 600, marginBottom: 8 }}>📱 WhatsApp AI Reminder</p>
            <p>Dear <strong>Raj Kumar</strong>,</p>
            <p>This is a reminder from <strong>Meridian Hospital</strong> regarding your upcoming admission on <strong>30-Aug-2026</strong> for <strong>Cardiology</strong> under <strong>Dr. Surendhar G</strong>.</p>
            <p style={{ marginTop: 8 }}>📄 You have <strong>1 pending document(s)</strong> to submit.</p>
            <p style={{ marginTop: 8 }}>Please bring your pending documents and arrive by 8:00 AM.</p>
            <p style={{ marginTop: 8, fontSize: 12, color: '#666' }}>📞 Contact: 044 6666 9910 | 🏥 Meridian Hospital, Kolathur, Chennai</p>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card">
        <div className="card-header"><h3>Pre-Admission Records</h3></div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Patient</th><th>Admission Date</th><th>Department</th>
                <th>Doctor</th><th>Documents</th><th>Follow-up</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preAdmissions.map(p => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 500 }}>{p.patientName}</td>
                  <td>{p.admissionDate}</td>
                  <td>{p.department}</td>
                  <td>{p.doctor}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ flex: 1, height: 6, background: 'var(--border)', borderRadius: 3, overflow: 'hidden' }}>
                        <div style={{
                          height: '100%',
                          width: `${(p.documentsSubmitted / p.documentsRequired) * 100}%`,
                          background: p.documentsSubmitted === p.documentsRequired ? 'var(--success)' : 'var(--warning)',
                          borderRadius: 3,
                        }} />
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>
                        {p.documentsSubmitted}/{p.documentsRequired}
                      </span>
                    </div>
                  </td>
                  <td><span className={`status-badge ${p.followUpStatus.toLowerCase()}`}>{p.followUpStatus}</span></td>
                  <td><span className={`status-badge ${p.admissionStatus.toLowerCase()}`}>{p.admissionStatus}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default PreAdmissionPage;
