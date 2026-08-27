import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { appointments } from '../../data/appointments';
import { CheckCircle, XCircle } from 'lucide-react';

const DoctorAppointments: React.FC = () => {
  const { user } = useAuth();
  const [localAppts, setLocalAppts] = useState(appointments);
  const [successMsg, setSuccessMsg] = useState('');

  const myAppts = localAppts.filter(a => a.doctorId === user?.loginId);

  const updateStatus = (id: string, status: typeof appointments[0]['status']) => {
    setLocalAppts(prev => prev.map(a => a.id === id ? { ...a, status } : a));
    setSuccessMsg(`Appointment ${id} — ${status}`);
    setTimeout(() => setSuccessMsg(''), 3000);
  };

  return (
    <div>
      <div className="page-header">
        <h2>My Appointments</h2>
        <p>Appointments for {user?.name} — {user?.department}</p>
      </div>

      {successMsg && <div className="success-alert"><CheckCircle size={16} /> {successMsg}</div>}

      <div className="card">
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th><th>Patient</th><th>Date</th><th>Time</th><th>Type</th><th>Status</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {myAppts.map(a => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{a.id}</td>
                  <td style={{ fontWeight: 500 }}>{a.patientName}</td>
                  <td>{a.date}</td>
                  <td>{a.time}</td>
                  <td><span className="intent-badge">{a.type}</span></td>
                  <td><span className={`status-badge ${a.status.toLowerCase()}`}>{a.status}</span></td>
                  <td>
                    <div style={{ display: 'flex', gap: 4 }}>
                      {a.status === 'Confirmed' && (
                        <button className="btn btn-success btn-sm" onClick={() => updateStatus(a.id, 'Completed')}>
                          <CheckCircle size={13} /> Complete
                        </button>
                      )}
                      {a.status === 'Pending' && (
                        <button className="btn btn-primary btn-sm" onClick={() => updateStatus(a.id, 'Confirmed')}>
                          <CheckCircle size={13} /> Confirm
                        </button>
                      )}
                      {(a.status === 'Confirmed' || a.status === 'Pending') && (
                        <button className="btn btn-danger btn-sm" onClick={() => updateStatus(a.id, 'Cancelled')}>
                          <XCircle size={13} />
                        </button>
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

export default DoctorAppointments;
