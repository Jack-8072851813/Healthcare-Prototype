import React, { useState, useEffect } from 'react';
import { Building2, Users, CalendarCheck, RefreshCw } from 'lucide-react';
import { fetchDepartments, type Department } from '../../services/dashboardApi';

const DEPT_COLORS = [
  '#4A90D9', '#5AAFA5', '#48BB78', '#ECC94B', '#F56565',
  '#9F7AEA', '#ED8936', '#38B2AC', '#E53E3E', '#805AD5',
];

const DepartmentPage: React.FC = () => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);

  const loadDepartments = async () => {
    setLoading(true);
    try {
      const res = await fetchDepartments();
      setDepartments(res.departments);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDepartments();
  }, []);

  return (
    <div>
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h2>Departments & Specialties</h2>
            <p>All active hospital departments — live from database</p>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={loadDepartments} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
          Loading departments...
        </div>
      ) : departments.length === 0 ? (
        <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
          No departments found in database.
        </div>
      ) : (
        <div className="dept-grid">
          {departments.map((d, idx) => (
            <div className="dept-card" key={d.id}>
              <div className="dept-card-icon" style={{ background: `${DEPT_COLORS[idx % DEPT_COLORS.length]}18`, color: DEPT_COLORS[idx % DEPT_COLORS.length] }}>
                <Building2 size={22} />
              </div>
              <h4>{d.department_name}</h4>
              <p style={{ fontSize: 12, color: 'var(--text-muted)', minHeight: 36 }}>
                {d.description || 'Specialized medical care and treatment.'}
              </p>
              <div className="dept-card-stats">
                <span className="dept-card-stat">
                  <Users size={12} style={{ display: 'inline', marginRight: 3 }} />
                  <strong>{d.doctor_count}</strong> Doctors
                </span>
                <span className="dept-card-stat">
                  <CalendarCheck size={12} style={{ display: 'inline', marginRight: 3 }} />
                  <strong>{d.today_appts}</strong> Today
                </span>
                <span
                  className={`status-badge ${d.status === 'ACTIVE' ? 'active' : 'inactive'}`}
                  style={{ marginLeft: 'auto' }}
                >
                  {d.status}
                </span>
              </div>
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
                {d.total_appts} total appointments
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DepartmentPage;
