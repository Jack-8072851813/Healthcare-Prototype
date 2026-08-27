import React, { useState } from 'react';
import { appointments } from '../../data/appointments';
import { Search, Filter, Eye, CheckCircle, XCircle, RefreshCw } from 'lucide-react';

const AppointmentManagement: React.FC = () => {
  const [search, setSearch] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [localAppointments, setLocalAppointments] = useState(appointments);
  const [successMsg, setSuccessMsg] = useState('');

  const departments = [...new Set(appointments.map(a => a.department))].sort();

  const filtered = localAppointments.filter(a => {
    const matchSearch = !search || a.patientName.toLowerCase().includes(search.toLowerCase()) || a.doctorName.toLowerCase().includes(search.toLowerCase()) || a.id.toLowerCase().includes(search.toLowerCase());
    const matchDate = !dateFilter || a.date === dateFilter;
    const matchDept = !deptFilter || a.department === deptFilter;
    const matchStatus = !statusFilter || a.status === statusFilter;
    return matchSearch && matchDate && matchDept && matchStatus;
  });

  const updateStatus = (id: string, status: typeof appointments[0]['status']) => {
    setLocalAppointments(prev => prev.map(a => a.id === id ? { ...a, status } : a));
    setSuccessMsg(`Appointment ${id} has been ${status.toLowerCase()}.`);
    setTimeout(() => setSuccessMsg(''), 3000);
  };

  return (
    <div>
      <div className="page-header">
        <h2>Appointment Management</h2>
        <p>View and manage all appointments at Meridian Hospital</p>
      </div>

      {successMsg && <div className="success-alert"><CheckCircle size={16} /> {successMsg}</div>}

      <div className="card">
        <div className="card-header" style={{ flexWrap: 'wrap', gap: 12 }}>
          <div className="search-bar" style={{ maxWidth: 300 }}>
            <Search size={18} />
            <input placeholder="Search appointments..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <Filter size={16} style={{ color: 'var(--text-muted)' }} />
            <input type="date" value={dateFilter} onChange={e => setDateFilter(e.target.value)} style={{ padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13, fontFamily: 'inherit' }} />
            <select value={deptFilter} onChange={e => setDeptFilter(e.target.value)}>
              <option value="">All Departments</option>
              {departments.map(d => <option key={d} value={d}>{d}</option>)}
            </select>
            <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
              <option value="">All Status</option>
              <option value="Confirmed">Confirmed</option>
              <option value="Pending">Pending</option>
              <option value="Completed">Completed</option>
              <option value="Cancelled">Cancelled</option>
            </select>
          </div>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th><th>Patient</th><th>Doctor</th><th>Department</th>
                <th>Date</th><th>Time</th><th>Type</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(a => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{a.id}</td>
                  <td style={{ fontWeight: 500 }}>{a.patientName}</td>
                  <td>{a.doctorName}</td>
                  <td>{a.department}</td>
                  <td>{a.date}</td>
                  <td>{a.time}</td>
                  <td><span className="intent-badge">{a.type}</span></td>
                  <td><span className={`status-badge ${a.status.toLowerCase()}`}>{a.status}</span></td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {a.status === 'Pending' && (
                        <button className="btn btn-success btn-sm" onClick={() => updateStatus(a.id, 'Confirmed')} title="Confirm">
                          <CheckCircle size={13} />
                        </button>
                      )}
                      {(a.status === 'Confirmed' || a.status === 'Pending') && (
                        <>
                          <button className="btn btn-secondary btn-sm" title="Reschedule"><RefreshCw size={13} /></button>
                          <button className="btn btn-danger btn-sm" onClick={() => updateStatus(a.id, 'Cancelled')} title="Cancel">
                            <XCircle size={13} />
                          </button>
                        </>
                      )}
                    </div>
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

export default AppointmentManagement;
