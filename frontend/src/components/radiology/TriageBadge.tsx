import React from 'react';
import type { TriagePriority } from '../../data/radiology/studies';
import { AlertCircle, AlertTriangle, CheckCircle, Clock } from 'lucide-react';

interface TriageBadgeProps {
  priority: TriagePriority;
  size?: 'sm' | 'md';
  showIcon?: boolean;
}

const config: Record<
  TriagePriority,
  { label: string; className: string; icon: React.ReactNode }
> = {
  CRITICAL: {
    label: 'CRITICAL',
    className: 'triage-badge triage-critical',
    icon: <AlertCircle size={12} />,
  },
  HIGH: {
    label: 'HIGH',
    className: 'triage-badge triage-high',
    icon: <AlertTriangle size={12} />,
  },
  ROUTINE: {
    label: 'ROUTINE',
    className: 'triage-badge triage-routine',
    icon: <CheckCircle size={12} />,
  },
  PROCESSING: {
    label: 'PROCESSING',
    className: 'triage-badge triage-processing',
    icon: <Clock size={12} className="spin-icon" />,
  },
};

const TriageBadge: React.FC<TriageBadgeProps> = ({
  priority,
  size = 'md',
  showIcon = true,
}) => {
  const item = config[priority] || config.ROUTINE;

  return (
    <span className={`${item.className} ${size === 'sm' ? 'triage-badge-sm' : ''}`}>
      {showIcon && item.icon}
      <span>{item.label}</span>
    </span>
  );
};

export default TriageBadge;
