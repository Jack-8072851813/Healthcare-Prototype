import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { patients } from '../../data/patients';
import { useNavigate } from 'react-router-dom';
import { Eye, Search } from 'lucide-react';
import { useState } from 'react';

const PatientRecords: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const myPatients = patients.filter(p => p.assignedDoctorId === user?.loginId);

  const filtered = myPatients.filter(p => !search ||
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div className="page-header">
        <h2>Patient Records</h2>
        <p>View detailed records for your patients</p>
        <span className="demo-badge">⚠️ DEMO DATA — Fictional Patient Records</span>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="search-bar" style={{ maxWidth: 320 }}>
            <Search size={18} />
            <input placeholder="Search patient records..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Patient ID</th><th>Name</th><th>Age</th><th>Gender</th>
                <th>Blood Group</th><th>Medical History</th><th>Last Visit</th><th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{p.id}</td>
                  <td style={{ fontWeight: 500 }}>{p.name}</td>
                  <td>{p.age}</td>
                  <td>{p.gender}</td>
                  <td>{p.bloodGroup}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {p.medicalHistory.slice(0, 2).map(m => (
                        <span key={m} className="intent-badge" style={{ fontSize: 10 }}>{m}</span>
                      ))}
                      {p.medicalHistory.length > 2 && (
                        <span className="intent-badge" style={{ fontSize: 10 }}>+{p.medicalHistory.length - 2}</span>
                      )}
                    </div>
                  </td>
                  <td>{p.lastVisit}</td>
                  <td>
                    <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/doctor/patient-records/${p.id}`)}>
                      <Eye size={14} /> View Record
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default PatientRecords;
