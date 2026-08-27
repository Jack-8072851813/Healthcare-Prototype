import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { patients } from '../../data/patients';
import { useNavigate } from 'react-router-dom';
import { Eye } from 'lucide-react';

const MyPatients: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const myPatients = patients.filter(p => p.assignedDoctorId === user?.loginId);

  return (
    <div>
      <div className="page-header">
        <h2>My Patients</h2>
        <p>Patients assigned to {user?.name} — {user?.department}</p>
        <span className="demo-badge">⚠️ DEMO DATA — Fictional Patient Records</span>
      </div>

      <div className="card">
        <div className="card-header">
          <h3>{myPatients.length} Patient{myPatients.length !== 1 ? 's' : ''}</h3>
        </div>
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Patient ID</th><th>Patient Name</th><th>Age</th><th>Gender</th>
                <th>Last Visit</th><th>Next Appointment</th><th>Status</th><th>Action</th>
              </tr>
            </thead>
            <tbody>
              {myPatients.map(p => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{p.id}</td>
                  <td style={{ fontWeight: 500 }}>{p.name}</td>
                  <td>{p.age}</td>
                  <td>{p.gender}</td>
                  <td>{p.lastVisit}</td>
                  <td>{p.nextAppointment}</td>
                  <td><span className={`status-badge ${p.status.toLowerCase()}`}>{p.status}</span></td>
                  <td>
                    <button className="btn btn-secondary btn-sm" onClick={() => navigate(`/doctor/patient-records/${p.id}`)}>
                      <Eye size={14} /> View
                    </button>
                  </td>
                </tr>
              ))}
              {myPatients.length === 0 && (
                <tr><td colSpan={8} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No patients assigned</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default MyPatients;
