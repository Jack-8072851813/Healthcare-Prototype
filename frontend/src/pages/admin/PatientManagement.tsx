import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Filter, Eye, ChevronLeft, ChevronRight, RefreshCw, MessageSquare } from 'lucide-react';
import { fetchPatients, type Patient } from '../../services/dashboardApi';

const PatientManagement: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [page, setPage] = useState(1);
  const perPage = 15;

  const [patients, setPatients] = useState<Patient[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchPatients({ search: search || undefined, status: statusFilter || undefined, page, per_page: perPage });
      setPatients(res.patients);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch {
      setError('Failed to load patients from database.');
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter, page]);

  useEffect(() => {
    const timer = setTimeout(loadPatients, 300);
    return () => clearTimeout(timer);
  }, [loadPatients]);

  const calcAge = (dob: string) => {
    if (!dob) return '—';
    const diff = Date.now() - new Date(dob).getTime();
    return Math.floor(diff / (365.25 * 24 * 3600 * 1000));
  };

  return (
    <div>
      <div className="page-header">
        <h2>Patient Management</h2>
        <p>All registered patients — live data from hospital database</p>
      </div>

      {error && (
        <div className="error-alert" style={{ marginBottom: 16 }}>
          ⚠️ {error}
        </div>
      )}

      <div className="card">
        <div className="card-header">
          <div className="search-bar" style={{ maxWidth: 320 }}>
            <Search size={18} />
            <input
              placeholder="Search by name, phone, ID..."
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
            />
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <Filter size={16} style={{ color: 'var(--text-muted)' }} />
            <select value={statusFilter} onChange={e => { setStatusFilter(e.target.value); setPage(1); }}>
              <option value="">All Status</option>
              <option value="ACTIVE">Active</option>
              <option value="INACTIVE">Inactive</option>
            </select>
            <button className="btn btn-secondary btn-sm" onClick={loadPatients} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
              Refresh
            </button>
          </div>
        </div>

        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              Loading patients...
            </div>
          ) : patients.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
              {search || statusFilter ? 'No patients match your filters.' : 'No patients registered yet.'}
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
                  <th>WhatsApp</th>
                  <th>City</th>
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
                    <td style={{ fontSize: 12 }}>
                      {p.whatsapp_number
                        ? <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><MessageSquare size={12} color="#25D366" />{p.whatsapp_number}</span>
                        : <span style={{ color: 'var(--text-muted)' }}>—</span>
                      }
                    </td>
                    <td>{p.city || '—'}</td>
                    <td>
                      {p.blood_group
                        ? <span className="intent-badge" style={{ background: '#FEF3C7', color: '#92400E' }}>{p.blood_group}</span>
                        : '—'
                      }
                    </td>
                    <td style={{ fontSize: 12 }}>{p.created_at ? new Date(p.created_at).toLocaleDateString() : '—'}</td>
                    <td>
                      <span className={`status-badge ${p.status === 'ACTIVE' ? 'active' : 'inactive'}`}>
                        {p.status}
                      </span>
                    </td>
                    <td>
                      <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/admin/patients/${p.id}`)}>
                        <Eye size={14} /> View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="pagination" style={{ padding: '16px 22px' }}>
          <span className="pagination-info">
            {loading ? 'Loading...' : `Showing ${Math.min((page - 1) * perPage + 1, total)}–${Math.min(page * perPage, total)} of ${total} patients`}
          </span>
          <div className="pagination-buttons">
            <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}><ChevronLeft size={14} /></button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              const pg = i + Math.max(1, page - 3);
              if (pg > totalPages) return null;
              return (
                <button key={pg} className={page === pg ? 'active' : ''} onClick={() => setPage(pg)}>{pg}</button>
              );
            })}
            <button disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}><ChevronRight size={14} /></button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PatientManagement;
