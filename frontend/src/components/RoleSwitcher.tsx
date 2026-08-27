import React, { useState } from 'react';
import { useDemoRole, type DemoRole } from '../context/RoleContext';
import { UserCog, ChevronUp, ChevronDown } from 'lucide-react';

const ROLES: { value: DemoRole; label: string; desc: string; color: string }[] = [
  { value: 'admin',       label: 'Hospital Administrator', desc: 'Full system overview', color: '#4A90D9' },
  { value: 'billing',     label: 'Billing Executive',      desc: 'Revenue Cycle focus',  color: '#E8850A' },
  { value: 'bed-manager', label: 'Bed Manager',            desc: 'Bed Allocation focus', color: '#5AAFA5' },
];

const RoleSwitcher: React.FC = () => {
  const { demoRole, setDemoRole } = useDemoRole();
  const [open, setOpen] = useState(false);

  const current = ROLES.find(r => r.value === demoRole) || ROLES[0];

  return (
    <div className="role-switcher">
      <button className="role-switcher-btn" onClick={() => setOpen(o => !o)} type="button">
        <UserCog size={14} />
        <span>Demo: {current.label}</span>
        {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>

      {open && (
        <div className="role-switcher-menu">
          <div className="role-switcher-title">Switch Demo Persona</div>
          {ROLES.map(r => (
            <button
              key={r.value}
              className={`role-switcher-option ${demoRole === r.value ? 'active' : ''}`}
              onClick={() => { setDemoRole(r.value); setOpen(false); }}
              type="button"
              style={{ '--role-color': r.color } as React.CSSProperties}
            >
              <span className="role-dot" />
              <div>
                <div className="role-option-label">{r.label}</div>
                <div className="role-option-desc">{r.desc}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

export default RoleSwitcher;
