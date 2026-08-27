import React from 'react';
import { Hospital, MapPin, Phone, Mail, Clock, Wifi, Heart, Stethoscope, Syringe, Shield } from 'lucide-react';
import logo from '../../assets/logo.svg';

const HospitalInfoPage: React.FC = () => {
  const facilities = [
    '300 Beds', '24/7 Emergency Care', 'Multispeciality Healthcare', 'Advanced Diagnostics',
    'Telemedicine', 'Dialysis Services', 'Critical Care', 'Cancer Care', 'Cardiac Care',
    'Operation Theatres', 'Pharmacy', 'Laboratory Services', 'Blood Bank', 'Ambulance Service'
  ];

  return (
    <div>
      <div className="page-header">
        <h2>Hospital Information</h2>
        <p>About Meridian Hospital — The Family Hospital</p>
      </div>

      {/* Main Overview */}
      <div className="hospital-overview">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
          <img src={logo} alt="Meridian Hospital" style={{ width: 64, height: 64, borderRadius: 12 }} />
          <div>
            <h3 style={{ fontSize: 22, display: 'block' }}>Meridian Hospital</h3>
            <p style={{ fontSize: 15, color: 'var(--primary)', fontWeight: 500 }}>The Family Hospital</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>Kolathur, Chennai</p>
          </div>
        </div>

        <p style={{ fontSize: 14, color: 'var(--text-secondary)', lineHeight: 1.8, maxWidth: 800, marginBottom: 20 }}>
          Meridian Hospital is a leading multispeciality hospital located in Kolathur, Chennai.
          We provide comprehensive healthcare services ranging from primary care to advanced
          specialized treatments. Our mission is to deliver compassionate, world-class medical
          care using the latest technology and AI-powered patient communication to ensure
          the best possible patient experience.
        </p>

        <h4 style={{ fontSize: 15, fontWeight: 600, marginBottom: 12, color: 'var(--text-primary)' }}>Facilities & Services</h4>
        <div className="hospital-facilities">
          {facilities.map(f => (
            <span key={f} className="facility-tag">
              <Shield size={14} /> {f}
            </span>
          ))}
        </div>

        <h4 style={{ fontSize: 15, fontWeight: 600, marginTop: 28, marginBottom: 16, color: 'var(--text-primary)' }}>Contact Information</h4>
        <div className="hospital-contact-grid">
          <div className="hospital-contact-item">
            <div className="icon"><MapPin size={18} /></div>
            <div>
              <label>Address</label>
              <p>46D, Jawaharlal Nehru Road,<br />200 Feet Ring Road,<br />Chennai – 600099</p>
            </div>
          </div>
          <div className="hospital-contact-item">
            <div className="icon"><Phone size={18} /></div>
            <div>
              <label>Main Contact</label>
              <p>044 6666 9910</p>
            </div>
          </div>
          <div className="hospital-contact-item">
            <div className="icon" style={{ background: 'var(--error-light)', color: 'var(--error)' }}><Phone size={18} /></div>
            <div>
              <label>Emergency</label>
              <p style={{ color: 'var(--error)', fontWeight: 600 }}>044 6666 9999</p>
            </div>
          </div>
          <div className="hospital-contact-item">
            <div className="icon"><Mail size={18} /></div>
            <div>
              <label>Email</label>
              <p>info@meridian-hospital.com</p>
            </div>
          </div>
          <div className="hospital-contact-item">
            <div className="icon"><Clock size={18} /></div>
            <div>
              <label>OPD Timings</label>
              <p>Mon–Sat: 8:00 AM – 8:00 PM</p>
            </div>
          </div>
          <div className="hospital-contact-item">
            <div className="icon" style={{ background: 'var(--success-light)', color: 'var(--success)' }}><Wifi size={18} /></div>
            <div>
              <label>Emergency</label>
              <p>Available 24/7</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HospitalInfoPage;
