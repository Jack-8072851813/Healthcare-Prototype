import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { fetchPatients, type Patient } from '../../services/dashboardApi';
import { Eye, Search, RefreshCw } from 'lucide-react';

const MyPatients: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [patients, setPatients] = useState<Patient[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // Backend auto-scopes to this doctor's patients via JWT
      const res = await fetchPatients({ search: search || undefined, per_page: 100 });
      setPatients(res.patients);
    } catch {
      setError('Failed to load patients.');
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    const timer = setTimeout(loadPatients, 300);
    return () => clearTimeout(timer);
  }, [loadPatients]);

  const calcAge = (dob: string) => {
    if (!dob) return '—';
    return Math.floor((Date.now() - new Date(dob).getTime()) / (365.25 * 24 * 3600 * 1000));
  };

  return (
    <div>
      <div className="page-header">
        <h2>My Patients</h2>
        <p>Patients assigned to {user?.name}{user?.department ? ` — ${user?.department}` : ''}</p>
      </div>

      {error && <div className="error-alert" style={{ marginBottom: 16 }}>⚠️ {error}</div>}

      <div className="card">
        <div className="card-header">
          <div className="search-bar" style={{ maxWidth: 320 }}>
            <Search size={18} />
            <input
              placeholder="Search by name, phone, ID..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              {loading ? 'Loading...' : `${patients.length} patient(s)`}
            </span>
            <button className="btn btn-secondary btn-sm" onClick={loadPatients} disabled={loading}
              style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              Refresh
            </button>
          </div>
        </div>
        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>Loading patients...</div>
          ) : patients.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              {search ? 'No patients match your search.' : 'No patients assigned yet.'}
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Patient ID</th>
                  <th>Patient Name</th>
                  <th>Age</th>
                  <th>Gender</th>
                  <th>Phone</th>
                  <th>Blood Group</th>
                  <th>Registered</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {patients.map(p => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{p.patient_code}</td>
                    <td style={{ fontWeight: 500 }}>{p.first_name} {p.last_name}</td>
                    <td>{calcAge(p.date_of_birth)}</td>
                    <td>{p.gender}</td>
                    <td style={{ fontSize: 12 }}>{p.phone}</td>
                    <td>
                      {p.blood_group
                        ? <span className="intent-badge" style={{ background: '#FEF3C7', color: '#92400E' }}>{p.blood_group}</span>
                        : '—'}
                    </td>
                    <td style={{ fontSize: 12 }}>{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                    <td>
                      <span className={`status-badge ${p.status === 'ACTIVE' ? 'active' : 'inactive'}`}>{p.status}</span>
                    </td>
                    <td>
                      <button className="btn btn-secondary btn-sm"
                        onClick={() => navigate(`/doctor/patient-records/${p.id}`)}>
                        <Eye size={14} /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
};

export default MyPatients;
