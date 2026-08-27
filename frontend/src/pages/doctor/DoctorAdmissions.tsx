import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { patients } from '../../data/patients';
import { preAdmissions } from '../../data/aiConversations';

const DoctorAdmissions: React.FC = () => {
  const { user } = useAuth();
  const myPatients = patients.filter(p => p.assignedDoctorId === user?.loginId);
  const myAdmissions = preAdmissions.filter(p => myPatients.some(mp => mp.id === p.patientId));

  return (
    <div>
      <div className="page-header">
        <h2>Admissions</h2>
        <p>Upcoming admissions for {user?.name}'s patients</p>
      </div>

      <div className="card">
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Patient</th><th>Admission Date</th><th>Department</th>
                <th>Notes</th><th>Documents</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {myAdmissions.map(a => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 500 }}>{a.patientName}</td>
                  <td>{a.admissionDate}</td>
                  <td>{a.department}</td>
                  <td style={{ fontSize: 13 }}>{a.notes}</td>
                  <td>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{a.documentsSubmitted}/{a.documentsRequired}</span>
                  </td>
                  <td><span className={`status-badge ${a.admissionStatus.toLowerCase()}`}>{a.admissionStatus}</span></td>
                </tr>
              ))}
              {myAdmissions.length === 0 && (
                <tr><td colSpan={6} style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>No upcoming admissions</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default DoctorAdmissions;
