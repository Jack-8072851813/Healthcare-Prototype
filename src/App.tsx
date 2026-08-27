import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import AppLayout from './components/AppLayout';

// Admin Pages
import AdminDashboard from './pages/admin/AdminDashboard';
import PatientManagement from './pages/admin/PatientManagement';
import PatientProfile from './pages/admin/PatientProfile';
import DoctorManagement from './pages/admin/DoctorManagement';
import AppointmentManagement from './pages/admin/AppointmentManagement';
import DepartmentPage from './pages/admin/DepartmentPage';
import AIPatientDesk from './pages/admin/AIPatientDesk';
import PreAdmissionPage from './pages/admin/PreAdmissionPage';
import ReportsPage from './pages/admin/ReportsPage';
import HospitalInfoPage from './pages/admin/HospitalInfoPage';
import SettingsPage from './pages/admin/SettingsPage';

// Doctor Pages
import DoctorDashboard from './pages/doctor/DoctorDashboard';
import MyPatients from './pages/doctor/MyPatients';
import DoctorAppointments from './pages/doctor/DoctorAppointments';
import PatientRecords from './pages/doctor/PatientRecords';
import ClinicalNotes from './pages/doctor/ClinicalNotes';
import AIPatientRequests from './pages/doctor/AIPatientRequests';
import DoctorAdmissions from './pages/doctor/DoctorAdmissions';
import DoctorProfile from './pages/doctor/DoctorProfile';

const ProtectedRoute: React.FC<{ children: React.ReactNode; role?: 'admin' | 'doctor' }> = ({ children, role }) => {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (role && user?.role !== role) {
    return <Navigate to={user?.role === 'admin' ? '/admin/dashboard' : '/doctor/dashboard'} replace />;
  }
  return <>{children}</>;
};

const AuthRedirect: React.FC = () => {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Navigate to={user?.role === 'admin' ? '/admin/dashboard' : '/doctor/dashboard'} replace />;
};

const AppRoutes: React.FC = () => {
  const { isAuthenticated, user } = useAuth();

  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={isAuthenticated ? <Navigate to={user?.role === 'admin' ? '/admin/dashboard' : '/doctor/dashboard'} replace /> : <LoginPage />} />

      {/* Admin Routes */}
      <Route path="/admin" element={<ProtectedRoute role="admin"><AppLayout /></ProtectedRoute>}>
        <Route path="dashboard" element={<AdminDashboard />} />
        <Route path="patients" element={<PatientManagement />} />
        <Route path="patients/:id" element={<PatientProfile />} />
        <Route path="doctors" element={<DoctorManagement />} />
        <Route path="appointments" element={<AppointmentManagement />} />
        <Route path="departments" element={<DepartmentPage />} />
        <Route path="ai-desk" element={<AIPatientDesk />} />
        <Route path="pre-admission" element={<PreAdmissionPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="hospital-info" element={<HospitalInfoPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>

      {/* Doctor Routes */}
      <Route path="/doctor" element={<ProtectedRoute role="doctor"><AppLayout /></ProtectedRoute>}>
        <Route path="dashboard" element={<DoctorDashboard />} />
        <Route path="my-patients" element={<MyPatients />} />
        <Route path="appointments" element={<DoctorAppointments />} />
        <Route path="patient-records" element={<PatientRecords />} />
        <Route path="patient-records/:id" element={<PatientProfile />} />
        <Route path="clinical-notes" element={<ClinicalNotes />} />
        <Route path="ai-requests" element={<AIPatientRequests />} />
        <Route path="admissions" element={<DoctorAdmissions />} />
        <Route path="profile" element={<DoctorProfile />} />
      </Route>

      {/* Redirect */}
      <Route path="/" element={<AuthRedirect />} />
      <Route path="*" element={<AuthRedirect />} />
    </Routes>
  );
};

const App: React.FC = () => (
  <BrowserRouter>
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  </BrowserRouter>
);

export default App;
