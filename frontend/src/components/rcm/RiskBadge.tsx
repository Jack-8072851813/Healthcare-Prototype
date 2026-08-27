import React from 'react';
import type { RiskLevel } from '../../data/rcm/claims';

interface RiskBadgeProps {
  level: RiskLevel;
  score?: number;
  size?: 'sm' | 'md';
}

const config: Record<RiskLevel, { label: string; className: string }> = {
  Low:      { label: 'Low Risk',      className: 'risk-badge risk-low' },
  Medium:   { label: 'Medium Risk',   className: 'risk-badge risk-medium' },
  High:     { label: 'High Risk',     className: 'risk-badge risk-high' },
  Critical: { label: 'Critical Risk', className: 'risk-badge risk-critical' },
};

const RiskBadge: React.FC<RiskBadgeProps> = ({ level, score, size = 'md' }) => {
  const { label, className } = config[level];
  return (
    <span className={`${className} ${size === 'sm' ? 'risk-badge-sm' : ''}`}>
      {score !== undefined && <span className="risk-score-dot">{score}</span>}
      {label}
    </span>
  );
};

export default RiskBadge;
