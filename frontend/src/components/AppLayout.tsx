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
  // AI Modules
  '/admin/overview': 'AI Module Overview',
  '/admin/revenue-cycle': 'Revenue Cycle Management',
  '/admin/revenue-cycle/claims': 'Claims Management',
  '/admin/bed-allocation': 'Predictive Bed Allocation',
  '/admin/bed-allocation/forecast': 'Bed Demand Forecast',
  // AI Radiology Triage Assistant
  '/admin/radiology': 'Meridian AI Radiology Triage Assistant',
  '/admin/radiology/worklist': 'AI Triage Radiology Worklist',
  '/admin/radiology/analyze': 'Analyze New Chest X-Ray',
  '/admin/radiology/performance': 'AI Model Performance Metrics',
  '/admin/radiology/pipeline': 'Databricks AI Pipeline Architecture',
  '/admin/radiology/architecture': 'System Architecture Overview',
  '/admin/radiology/about': 'About Radiology Triage PoC',
  // Doctor
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
    // Exact match first
    if (pageTitles[location.pathname]) return pageTitles[location.pathname];
    // Dynamic route matching
    if (location.pathname.match(/\/admin\/radiology\/studies\/CXR/)) return 'Chest X-Ray Study Detail';
    if (location.pathname.match(/\/admin\/revenue-cycle\/claims\/CLM/)) return 'Claim Detail';
    if (location.pathname.match(/\/admin\/patients\/P/)) return 'Patient Profile';
    if (location.pathname.match(/\/doctor\/patient-records\//)) return 'Patient Records';
    // Prefix match
    const match = Object.keys(pageTitles).find(k => location.pathname.startsWith(k));
    return match ? pageTitles[match] : 'Meridian Hospital';
  };

  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-wrapper">
        <Header title={getTitle()} />
        <main className="main-content">
          <Outlet />
          <footer className="app-footer">
            Meridian Hospital | Kolathur, Chennai | AI RCM & Bed Allocation POC — Demo Environment
          </footer>
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
