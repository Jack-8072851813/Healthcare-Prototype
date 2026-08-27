import React from 'react';

interface OccupancyBarProps {
  occupied: number;
  total: number;
  label?: string;
  showNumbers?: boolean;
}

const OccupancyBar: React.FC<OccupancyBarProps> = ({
  occupied, total, label, showNumbers = true,
}) => {
  const pct = Math.round((occupied / total) * 100);
  const cls = pct >= 90 ? 'critical' : pct >= 75 ? 'high' : pct >= 50 ? 'medium' : 'low';

  return (
    <div className="occupancy-bar-wrap">
      {label && <div className="occupancy-bar-label">{label}</div>}
      <div className="occupancy-bar-track">
        <div
          className={`occupancy-bar-fill occ-${cls}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {showNumbers && (
        <div className="occupancy-bar-meta">
          <span className={`occ-pct occ-${cls}`}>{pct}%</span>
          <span className="occ-detail">{occupied}/{total} beds</span>
        </div>
      )}
    </div>
  );
};

export default OccupancyBar;
