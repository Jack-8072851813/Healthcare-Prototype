import React, { useState } from 'react';
import { UserPlus, X, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { addPatientWhatsApp, type AddPatientWhatsAppResponse } from '../services/dashboardApi';

interface AddPatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: (res: AddPatientWhatsAppResponse) => void;
}

const AddPatientModal: React.FC<AddPatientModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [whatsappNumber, setWhatsappNumber] = useState('+91 ');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  if (!isOpen) return null;

  const handleClose = () => {
    setError('');
    setSuccessMsg('');
    setWhatsappNumber('+91 ');
    onClose();
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccessMsg('');

    const raw = whatsappNumber.trim();
    const digits = raw.replace(/\D/g, '');

    if (!raw || digits.length < 10) {
      setError('Please enter a valid WhatsApp number.');
      return;
    }

    setLoading(true);
    try {
      const res = await addPatientWhatsApp(raw);
      if (res.success) {
        setSuccessMsg(res.message || 'Welcome message successfully sent.');
        if (onSuccess) onSuccess(res);
        setTimeout(() => {
          handleClose();
        }, 2200);
      } else {
        setError(res.error || res.message || 'Please enter a valid WhatsApp number.');
      }
    } catch {
      setError('Please enter a valid WhatsApp number.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" style={{
      position: 'fixed',
      inset: 0,
      background: 'rgba(0, 0, 0, 0.65)',
      backdropFilter: 'blur(4px)',
      zIndex: 9999,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 16
    }}>
      <div className="modal-card" style={{
        background: 'var(--bg-card, #ffffff)',
        border: '1px solid var(--border, #e2e8f0)',
        borderRadius: 16,
        padding: 24,
        width: '100%',
        maxWidth: 440,
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1)',
        color: 'var(--text-primary, #1e293b)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: 10, margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--primary, #1d4ed8)' }}>
            <UserPlus size={22} />
            + Add Patients
          </h3>
          <button
            onClick={handleClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted, #64748b)', padding: 4 }}
          >
            <X size={20} />
          </button>
        </div>

        {error && (
          <div style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            color: '#991b1b',
            padding: '10px 14px',
            borderRadius: 8,
            fontSize: 13,
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <AlertCircle size={16} />
            {error}
          </div>
        )}

        {successMsg && (
          <div style={{
            background: '#f0fdf4',
            border: '1px solid #bbf7d0',
            color: '#166534',
            padding: '10px 14px',
            borderRadius: 8,
            fontSize: 13,
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 8
          }}>
            <CheckCircle size={16} />
            {successMsg}
          </div>
        )}

        <form onSubmit={handleSave}>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 8, color: 'var(--text-secondary, #475569)' }}>
              Patient WhatsApp Number
            </label>
            <input
              type="text"
              placeholder="+91 98765 43210"
              value={whatsappNumber}
              onChange={e => setWhatsappNumber(e.target.value)}
              disabled={loading || !!successMsg}
              style={{
                width: '100%',
                padding: '12px 14px',
                fontSize: 15,
                borderRadius: 10,
                border: '1.5px solid var(--border, #cbd5e1)',
                background: 'var(--bg-primary, #f8fafc)',
                color: 'var(--text-primary, #0f172a)',
                outline: 'none',
                boxSizing: 'border-box'
              }}
              autoFocus
            />
            <span style={{ fontSize: 12, color: 'var(--text-muted, #64748b)', marginTop: 6, display: 'block' }}>
              Sending will dispatch the Meridian Hospital welcome WhatsApp message.
            </span>
          </div>

          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 24 }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleClose}
              disabled={loading}
              style={{
                padding: '10px 18px',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer',
                border: '1px solid var(--border, #cbd5e1)',
                background: 'transparent'
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || !!successMsg}
              style={{
                padding: '10px 22px',
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 600,
                cursor: 'pointer',
                background: 'var(--primary, #1d4ed8)',
                color: '#ffffff',
                border: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: 8
              }}
            >
              {loading && <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />}
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AddPatientModal;
