import React from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { useAuth } from '../context/AuthContext';

const pageTitles: Record<string, string> = {
  '/admin/dashboard': 'Administration Dashboard',
  '/admin/patients': 'Patient Management',
  '/admin/doctors': 'Doctor Management',
  '/admin/appointments': 'Appointment Management',
  '/admin/departments': 'Departments & Specialties',
  '/admin/ai-desk': 'Meridian AI Patient Desk',
  '/admin/pre-admission': 'Pre-Admission Follow-up',
  '/admin/reports': 'Hospital Reports',
  '/admin/hospital-info': 'Hospital Information',
  '/admin/settings': 'Settings',
  '/doctor/dashboard': 'Doctor Dashboard',
  '/doctor/my-patients': 'My Patients',
  '/doctor/appointments': 'My Appointments',
  '/doctor/patient-records': 'Patient Records',
  '/doctor/clinical-notes': 'Clinical Notes',
  '/doctor/ai-requests': 'AI Patient Requests',
  '/doctor/admissions': 'Admissions',
  '/doctor/profile': 'Profile',
};

const AppLayout: React.FC = () => {
  const location = useLocation();
  const { user } = useAuth();

  const getTitle = () => {
    const basePath = location.pathname.replace(/\/[^/]+$/, '') === location.pathname
      ? location.pathname
      : Object.keys(pageTitles).find(k => location.pathname.startsWith(k)) || location.pathname;
    return pageTitles[basePath] || pageTitles[location.pathname] || 'Meridian Hospital';
  };

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-wrapper">
        <Header title={getTitle()} />
        <main className="main-content">
          <Outlet />
          <footer className="app-footer">
            Meridian Hospital | Kolathur, Chennai | Prototype / Demo Environment
          </footer>
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
