import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import logo from '../assets/logo.svg';
import {
  LayoutDashboard, Users, UserCog, CalendarCheck, Building2,
  Bot, ClipboardList, BarChart3, Hospital, Settings, LogOut,
  ChevronLeft, ChevronRight, Stethoscope, FileText, BellRing,
  UserCircle, ClipboardPlus, AlertCircle, Clock,
} from 'lucide-react';

interface MenuItem {
  label: string;
  icon: React.ElementType;
  path: string;
}

const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  const adminMenuItems: MenuItem[] = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/admin/dashboard' },
    { label: 'Patients', icon: Users, path: '/admin/patients' },
    { label: 'Doctors', icon: UserCog, path: '/admin/doctors' },
    { label: 'Doctor Schedules', icon: Clock, path: '/admin/schedules' },
    { label: 'Appointments', icon: CalendarCheck, path: '/admin/appointments' },
    { label: 'Departments', icon: Building2, path: '/admin/departments' },
    { label: 'AI Patient Desk', icon: Bot, path: '/admin/ai-desk' },
    { label: 'Human Escalation', icon: AlertCircle, path: '/admin/escalations' },
    { label: 'Pre-Admission', icon: ClipboardList, path: '/admin/pre-admission' },
    { label: 'Reports', icon: BarChart3, path: '/admin/reports' },
    { label: 'Hospital Information', icon: Hospital, path: '/admin/hospital-info' },
    { label: 'Settings', icon: Settings, path: '/admin/settings' },
  ];

  const doctorMenuItems: MenuItem[] = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/doctor/dashboard' },
    { label: 'Appointments', icon: CalendarCheck, path: '/doctor/appointments' },
    { label: 'Patient Records', icon: FileText, path: '/doctor/patient-records' },
    { label: 'Clinical Notes', icon: ClipboardPlus, path: '/doctor/clinical-notes' },
    { label: 'AI Patient Requests', icon: BellRing, path: '/doctor/ai-requests' },
    { label: 'Admissions', icon: ClipboardList, path: '/doctor/admissions' },
    { label: 'Profile', icon: UserCircle, path: '/doctor/profile' },
  ];

  const menuItems = user?.role === 'admin' ? adminMenuItems : doctorMenuItems;

  const isActive = (path: string) =>
    location.pathname === path || (path !== '/admin/dashboard' && path !== '/doctor/dashboard' && location.pathname.startsWith(path));

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <nav className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <img src={logo} alt="Meridian Hospital" className="sidebar-logo" />
        {!collapsed && (
          <div className="sidebar-brand">
            <h3>Meridian Hospital</h3>
            <span>The Family Hospital</span>
          </div>
        )}
      </div>

      <div className="sidebar-nav">
        <div className="sidebar-section-title">
          {collapsed ? '—' : 'NAVIGATION'}
        </div>
        {menuItems.map(item => (
          <div
            key={item.path}
            className={`sidebar-item ${isActive(item.path) ? 'active' : ''}`}
            onClick={() => navigate(item.path)}
            title={collapsed ? item.label : ''}
          >
            <item.icon />
            <span>{item.label}</span>
          </div>
        ))}

        <div className="sidebar-section-title" style={{ marginTop: 8 }}>
          {collapsed ? '—' : ''}
        </div>
        <div className="sidebar-item" onClick={handleLogout}>
          <LogOut />
          <span>Logout</span>
        </div>
      </div>

      <div className="sidebar-footer">
        <button className="sidebar-toggle" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </nav>
  );
};

export default Sidebar;
