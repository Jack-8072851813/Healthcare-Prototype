import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { fetchPatients, type Patient } from '../../services/dashboardApi';
import { CheckCircle, FileText, Save, X } from 'lucide-react';

const ClinicalNotes: React.FC = () => {
  const { user } = useAuth();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loadingPatients, setLoadingPatients] = useState(true);

  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [visitType, setVisitType] = useState('Consultation');
  const [notes, setNotes] = useState('');
  const [followUpDate, setFollowUpDate] = useState('');
  const [showSuccess, setShowSuccess] = useState(false);
  const [savedNotes, setSavedNotes] = useState<Array<{
    patientName: string; date: string; type: string; notes: string; followUp: string
  }>>([]);

  const loadPatients = useCallback(async () => {
    setLoadingPatients(true);
    try {
      const res = await fetchPatients({ per_page: 100 });
      setPatients(res.patients);
    } finally {
      setLoadingPatients(false);
    }
  }, []);

  useEffect(() => { loadPatients(); }, [loadPatients]);

  const handleSave = () => {
    if (!selectedPatientId || !notes) return;
    const p = patients.find(pt => String(pt.id) === selectedPatientId);
    const patientName = p ? `${p.first_name} ${p.last_name}` : 'Unknown';
    setSavedNotes(prev => [{
      patientName,
      date: new Date().toISOString().split('T')[0],
      type: visitType,
      notes,
      followUp: followUpDate,
    }, ...prev]);
    setSelectedPatientId('');
    setNotes('');
    setFollowUpDate('');
    setShowSuccess(true);
    setTimeout(() => setShowSuccess(false), 3000);
  };

  const handleCancel = () => {
    setSelectedPatientId('');
    setNotes('');
    setFollowUpDate('');
  };

  return (
    <div>
      <div className="page-header">
        <h2>Clinical Notes</h2>
        <p>Add and view clinical notes for your patients — {user?.name}</p>
      </div>

      {showSuccess && <div className="success-alert"><CheckCircle size={16} /> Clinical note saved successfully.</div>}

      {/* Add Note Form */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header"><h3><FileText size={16} style={{ marginRight: 8 }} />Add Clinical Note</h3></div>
        <div className="card-body">
          <div className="grid-2" style={{ gap: 16, marginBottom: 16 }}>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Patient</label>
              <select value={selectedPatientId} onChange={e => setSelectedPatientId(e.target.value)}
                disabled={loadingPatients}>
                <option value="">{loadingPatients ? 'Loading patients...' : 'Select Patient'}</option>
                {patients.map(p => (
                  <option key={p.id} value={String(p.id)}>
                    {p.first_name} {p.last_name} ({p.patient_code})
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label>Visit Type</label>
              <select value={visitType} onChange={e => setVisitType(e.target.value)}>
                <option value="Consultation">Consultation</option>
                <option value="Follow-up">Follow-up</option>
                <option value="Emergency">Emergency</option>
                <option value="Procedure">Procedure</option>
                <option value="Telemedicine">Telemedicine</option>
              </select>
            </div>
          </div>
          <div className="form-group">
            <label>Clinical Notes</label>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="Enter clinical notes, observations, and treatment plan..."
              style={{
                width: '100%', minHeight: 140, padding: '12px 14px',
                border: '1.5px solid var(--border)', borderRadius: 'var(--radius-md)',
                fontSize: 14, fontFamily: 'inherit', background: 'var(--bg-primary)',
                resize: 'vertical',
              }}
            />
          </div>
          <div className="form-group">
            <label>Follow-up Date (Optional)</label>
            <input type="date" value={followUpDate} onChange={e => setFollowUpDate(e.target.value)} />
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="btn btn-primary" onClick={handleSave} disabled={!selectedPatientId || !notes}>
              <Save size={16} /> Save Note
            </button>
            <button className="btn btn-secondary" onClick={handleCancel}>
              <X size={16} /> Cancel
            </button>
          </div>
        </div>
      </div>

      {/* Saved Notes (session only) */}
      {savedNotes.length > 0 && (
        <div className="card">
          <div className="card-header"><h3>Recent Clinical Notes (This Session)</h3></div>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr><th>Patient</th><th>Date</th><th>Visit Type</th><th>Notes</th><th>Follow-up</th></tr>
              </thead>
              <tbody>
                {savedNotes.map((n, i) => (
                  <tr key={i}>
                    <td style={{ fontWeight: 500 }}>{n.patientName}</td>
                    <td>{n.date}</td>
                    <td><span className="intent-badge">{n.type}</span></td>
                    <td style={{ maxWidth: 300, fontSize: 13 }}>{n.notes.substring(0, 100)}{n.notes.length > 100 ? '...' : ''}</td>
                    <td>{n.followUp || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default ClinicalNotes;
