import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import logo from '../assets/logo.svg';
import RoleSwitcher from './RoleSwitcher';
import {
  LayoutDashboard, Users, UserCog, CalendarCheck, Building2,
  Bot, ClipboardList, BarChart3, Hospital, Settings, LogOut,
  ChevronLeft, ChevronRight, Stethoscope, FileText, BellRing,
  UserCircle, ClipboardPlus, Layers, CreditCard, BedDouble, TrendingUp,
} from 'lucide-react';

interface MenuItem {
  label: string;
  icon: React.ElementType;
  path: string;
  children?: { label: string; path: string }[];
}

const Sidebar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const [expandedGroup, setExpandedGroup] = useState<string | null>('ai-modules');

  const adminMenuItems: MenuItem[] = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/admin/dashboard' },
    { label: 'Patients', icon: Users, path: '/admin/patients' },
    { label: 'Doctors', icon: UserCog, path: '/admin/doctors' },
    { label: 'Appointments', icon: CalendarCheck, path: '/admin/appointments' },
    { label: 'Departments', icon: Building2, path: '/admin/departments' },
    { label: 'AI Patient Desk', icon: Bot, path: '/admin/ai-desk' },
    { label: 'Pre-Admission', icon: ClipboardList, path: '/admin/pre-admission' },
    { label: 'Reports', icon: BarChart3, path: '/admin/reports' },
    { label: 'Hospital Information', icon: Hospital, path: '/admin/hospital-info' },
    { label: 'Settings', icon: Settings, path: '/admin/settings' },
  ];

  const aiModuleItems: MenuItem[] = [
    { label: 'Overview', icon: Layers, path: '/admin/overview' },
    {
      label: 'Revenue Cycle',
      icon: CreditCard,
      path: '/admin/revenue-cycle',
      children: [
        { label: 'RCM Dashboard', path: '/admin/revenue-cycle' },
        { label: 'Claims', path: '/admin/revenue-cycle/claims' },
      ],
    },
    {
      label: 'Bed Allocation',
      icon: BedDouble,
      path: '/admin/bed-allocation',
      children: [
        { label: 'Bed Dashboard', path: '/admin/bed-allocation' },
        { label: 'Forecast', path: '/admin/bed-allocation/forecast' },
      ],
    },
  ];

  const doctorMenuItems: MenuItem[] = [
    { label: 'Dashboard', icon: LayoutDashboard, path: '/doctor/dashboard' },
    { label: 'My Patients', icon: Users, path: '/doctor/my-patients' },
    { label: 'Appointments', icon: CalendarCheck, path: '/doctor/appointments' },
    { label: 'Patient Records', icon: FileText, path: '/doctor/patient-records' },
    { label: 'Clinical Notes', icon: ClipboardPlus, path: '/doctor/clinical-notes' },
    { label: 'AI Patient Requests', icon: BellRing, path: '/doctor/ai-requests' },
    { label: 'Admissions', icon: ClipboardList, path: '/doctor/admissions' },
    { label: 'Profile', icon: UserCircle, path: '/doctor/profile' },
  ];

  const menuItems = user?.role === 'admin' ? adminMenuItems : doctorMenuItems;

  const isActive = (path: string) =>
    location.pathname === path || (path !== '/admin/dashboard' && location.pathname.startsWith(path));

  const handleLogout = () => { logout(); navigate('/login'); };

  const toggleGroup = (key: string) => {
    setExpandedGroup(g => g === key ? null : key);
  };

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
        {/* Standard Nav */}
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

        {/* AI Modules section (admin only) */}
        {user?.role === 'admin' && !collapsed && (
          <>
            <div
              className="sidebar-section-title sidebar-section-clickable"
              onClick={() => toggleGroup('ai-modules')}
              style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
            >
              <span>AI MODULES</span>
              <TrendingUp size={12} style={{ color: 'var(--primary)', opacity: 0.7 }} />
            </div>
            {(expandedGroup === 'ai-modules') && aiModuleItems.map(item => (
              <div key={item.path}>
                <div
                  className={`sidebar-item ${isActive(item.path) ? 'active' : ''}`}
                  onClick={() => {
                    navigate(item.path);
                    if (item.children) toggleGroup(item.label);
                  }}
                >
                  <item.icon />
                  <span>{item.label}</span>
                  {item.children && (
                    <span style={{ marginLeft: 'auto', fontSize: 10, opacity: 0.5 }}>
                      {expandedGroup === item.label ? '▲' : '▼'}
                    </span>
                  )}
                </div>
                {item.children && expandedGroup === item.label && (
                  <div className="sidebar-submenu">
                    {item.children.map(child => (
                      <div
                        key={child.path}
                        className={`sidebar-subitem ${location.pathname === child.path ? 'active' : ''}`}
                        onClick={() => navigate(child.path)}
                      >
                        {child.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
            {expandedGroup !== 'ai-modules' && (
              <div
                className="sidebar-item"
                onClick={() => toggleGroup('ai-modules')}
                style={{ opacity: 0.6, fontSize: 12 }}
              >
                <Layers />
                <span>AI Modules (collapsed)</span>
              </div>
            )}
          </>
        )}

        {/* Collapsed AI modules icon */}
        {user?.role === 'admin' && collapsed && (
          <>
            <div className="sidebar-section-title">—</div>
            {aiModuleItems.map(item => (
              <div
                key={item.path}
                className={`sidebar-item ${isActive(item.path) ? 'active' : ''}`}
                onClick={() => navigate(item.path)}
                title={item.label}
              >
                <item.icon />
                <span>{item.label}</span>
              </div>
            ))}
          </>
        )}

        <div className="sidebar-section-title" style={{ marginTop: 8 }}>
          {collapsed ? '—' : ''}
        </div>
        <div className="sidebar-item" onClick={handleLogout}>
          <LogOut />
          <span>Logout</span>
        </div>
      </div>

      {/* Role Switcher (admin only, uncollapsed) */}
      {user?.role === 'admin' && !collapsed && (
        <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border-light)' }}>
          <RoleSwitcher />
        </div>
      )}

      <div className="sidebar-footer">
        <button className="sidebar-toggle" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </nav>
  );
};

export default Sidebar;
