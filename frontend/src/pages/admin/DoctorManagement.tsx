import React from 'react';
import { doctors } from '../../data/doctors';
import { Search, Eye } from 'lucide-react';
import { useState } from 'react';

const DoctorManagement: React.FC = () => {
  const [search, setSearch] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const departments = [...new Set(doctors.map(d => d.department))].sort();

  const filtered = doctors.filter(d => {
    const matchSearch = !search || d.name.toLowerCase().includes(search.toLowerCase()) || d.department.toLowerCase().includes(search.toLowerCase());
    const matchDept = !deptFilter || d.department === deptFilter;
    return matchSearch && matchDept;
  });

  return (
    <div>
      <div className="page-header">
        <h2>Doctor Management</h2>
        <p>View all doctors at Meridian Hospital</p>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="search-bar" style={{ maxWidth: 320 }}>
            <Search size={18} />
            <input placeholder="Search doctors..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)} style={{ padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontFamily: 'inherit' }}>
            <option value="">All Departments</option>
            {departments.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th><th>Doctor</th><th>Specialization</th><th>Department</th>
                <th>Qualification</th><th>Experience</th><th>OPD Timings</th>
                <th>Today's Appts</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(d => (
                <tr key={d.id}>
                  <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{d.id}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'var(--primary-lighter)', color: 'var(--primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, flexShrink: 0 }}>
                        {d.avatar}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14 }}>{d.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{d.email}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ fontSize: 13 }}>{d.specialization}</td>
                  <td>{d.department}</td>
                  <td style={{ fontSize: 12 }}>{d.qualification}</td>
                  <td>{d.experience}</td>
                  <td style={{ fontSize: 12 }}>{d.opdTimings}</td>
                  <td style={{ fontWeight: 600, textAlign: 'center' }}>{d.todayAppointments}</td>
                  <td><span className={`status-badge ${d.status.toLowerCase().replace(' ', '-')}`}>{d.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DoctorManagement;
