import React from 'react';
import { departments } from '../../data/departments';
import {
  Heart, Shield, Activity, Baby, Bone, ScanLine, GitBranch, Droplets,
  Brain, HeartPulse, Siren, Stethoscope, Sparkles, Wind, Pill, Zap,
  Scissors, SmilePlus, Clipboard, Syringe, Building2
} from 'lucide-react';

const iconMap: Record<string, React.ReactNode> = {
  Heart: <Heart size={22} />, Shield: <Shield size={22} />, Activity: <Activity size={22} />,
  Baby: <Baby size={22} />, Bone: <Bone size={22} />, ScanLine: <ScanLine size={22} />,
  GitBranch: <GitBranch size={22} />, Droplets: <Droplets size={22} />, Brain: <Brain size={22} />,
  HeartPulse: <HeartPulse size={22} />, Siren: <Siren size={22} />, Stethoscope: <Stethoscope size={22} />,
  Sparkles: <Sparkles size={22} />, Wind: <Wind size={22} />, Pill: <Pill size={22} />,
  Zap: <Zap size={22} />, Slice: <Scissors size={22} />, SmilePlus: <SmilePlus size={22} />,
  Clipboard: <Clipboard size={22} />, Syringe: <Syringe size={22} />, Scissors: <Scissors size={22} />,
};

const DepartmentPage: React.FC = () => {
  return (
    <div>
      <div className="page-header">
        <h2>Departments & Specialties</h2>
        <p>Browse all departments and specialties at Meridian Hospital</p>
      </div>

      <div className="dept-grid">
        {departments.map(d => (
          <div className="dept-card" key={d.id}>
            <div className="dept-card-icon">
              {iconMap[d.icon] || <Building2 size={22} />}
            </div>
            <h4>{d.name}</h4>
            <p>{d.description}</p>
            <div className="dept-card-stats">
              <span className="dept-card-stat"><strong>{d.doctorsCount}</strong> Doctors</span>
              <span className="dept-card-stat"><strong>{d.todayAppointments}</strong> Today</span>
              <span className={`status-badge ${d.availability.toLowerCase()}`} style={{ marginLeft: 'auto' }}>
                {d.availability}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default DepartmentPage;
