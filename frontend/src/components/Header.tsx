import React from 'react';
import { useAuth } from '../context/AuthContext';
import { Bell, Search, Stethoscope } from 'lucide-react';

interface HeaderProps {
  title?: string;
}

const Header: React.FC<HeaderProps> = ({ title }) => {
  const { user } = useAuth();

  const getInitials = (name: string) =>
    name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

  const getRoleLabel = () => {
    if (user?.role === 'admin') return 'Administrator';
    return user?.department || 'Doctor';
  };

  return (
    <header className="header">
      <div className="header-left">
        <h1>{title || 'Dashboard'}</h1>
      </div>
      <div className="header-right">
        <button className="header-icon-btn" title="Search">
          <Search size={18} />
        </button>
        <button className="header-icon-btn" title="Notifications">
          <Bell size={18} />
          <span className="badge">3</span>
        </button>
        {user?.role === 'doctor' && (
          <button className="header-icon-btn" title="On Call">
            <Stethoscope size={18} />
          </button>
        )}
        <div className="header-user">
          <div className="header-user-avatar">
            {user ? getInitials(user.name) : 'U'}
          </div>
          <div className="header-user-info">
            <div className="name">{user?.name}</div>
            <div className="role">{getRoleLabel()}</div>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
