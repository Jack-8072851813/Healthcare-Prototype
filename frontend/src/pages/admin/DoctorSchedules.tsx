import React, { useState, useEffect, useCallback } from 'react';
import { Clock, Calendar, Plus, Trash2, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import {
  fetchDoctors, fetchSchedules, createSchedule, deleteSchedule, format12HourTime,
  type Doctor, type DoctorSchedule
} from '../../services/dashboardApi';

const DAYS = ['MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', 'SUNDAY'];

const DoctorSchedules: React.FC = () => {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [schedules, setSchedules] = useState<DoctorSchedule[]>([]);
  const [selectedDoctorId, setSelectedDoctorId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');
  const [toastType, setToastType] = useState<'success' | 'error'>('success');

  // Form State
  const [formDoctorId, setFormDoctorId] = useState<string>('');
  const [formDay, setFormDay] = useState<string>('MONDAY');
  const [formStartTime, setFormStartTime] = useState<string>('09:00');
  const [formEndTime, setFormEndTime] = useState<string>('17:00');
  const [formSlotDuration, setFormSlotDuration] = useState<number>(30);
  const [submitting, setSubmitting] = useState(false);

  const showToast = (msg: string, type: 'success' | 'error' = 'success') => {
    setToast(msg);
    setToastType(type);
    setTimeout(() => setToast(''), 4000);
  };

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [docRes, schedRes] = await Promise.all([
        fetchDoctors(),
        fetchSchedules(selectedDoctorId ? Number(selectedDoctorId) : undefined),
      ]);
      setDoctors(docRes.doctors);
      setSchedules(schedRes.schedules);
    } finally {
      setLoading(false);
    }
  }, [selectedDoctorId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleAddSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formDoctorId) {
      showToast('❌ Please select a Doctor from the dropdown.', 'error');
      return;
    }
    if (!formStartTime || !formEndTime) {
      showToast('❌ Please specify both Shift Start Time and Shift End Time.', 'error');
      return;
    }
    if (formStartTime >= formEndTime) {
      showToast('❌ Shift End Time must be later than Shift Start Time.', 'error');
      return;
    }
    setSubmitting(true);
    try {
      const res = await createSchedule({
        doctor_id: Number(formDoctorId),
        day_of_week: formDay,
        start_time: formStartTime,
        end_time: formEndTime,
        slot_duration_minutes: Number(formSlotDuration),
        status: 'ACTIVE',
      });
      if (res.success) {
        showToast('✓ Doctor schedule configured successfully!');
        loadData();
      } else {
        showToast(`❌ ${res.error || 'Failed to add schedule'}`, 'error');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteSchedule = async (schedId: number) => {
    if (!window.confirm('Are you sure you want to remove this schedule slot?')) return;
    const ok = await deleteSchedule(schedId);
    if (ok) {
      showToast('✓ Schedule slot removed');
      loadData();
    } else {
      showToast('❌ Failed to delete schedule', 'error');
    }
  };

  const filteredSchedules = selectedDoctorId
    ? schedules.filter(s => s.doctor_id === Number(selectedDoctorId))
    : schedules;

  return (
    <div>
      <div className="page-header">
        <h2>Doctor Schedules & Timings</h2>
        <p>Configure doctor working days, daily shift start/end times, and appointment slot durations</p>
      </div>

      {toast && (
        <div className={toastType === 'success' ? 'success-alert' : 'error-alert'} style={{ marginBottom: 16 }}>
          {toastType === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />} {toast}
        </div>
      )}

      {/* Configure New Schedule Form */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-header">
          <h3><Clock size={16} style={{ marginRight: 8 }} />Configure Doctor Shift & Time Slot</h3>
        </div>
        <div className="card-body">
          <form onSubmit={handleAddSchedule} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, alignItems: 'end' }}>
            <div>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>
                Select Doctor <span style={{ color: '#E53E3E' }}>*</span>
              </label>
              <select
                value={formDoctorId}
                onChange={e => setFormDoctorId(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}
                required
              >
                <option value="">— Select Doctor —</option>
                {doctors.map(d => (
                  <option key={d.id} value={d.id}>
                    {d.display_name} ({d.department_name})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Day of Week</label>
              <select
                value={formDay}
                onChange={e => setFormDay(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}
              >
                {DAYS.map(day => (
                  <option key={day} value={day}>{day}</option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Shift Start Time</label>
              <input
                type="time"
                value={formStartTime}
                onChange={e => setFormStartTime(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}
                required
              />
            </div>

            <div>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Shift End Time</label>
              <input
                type="time"
                value={formEndTime}
                onChange={e => setFormEndTime(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}
                required
              />
            </div>

            <div>
              <label style={{ fontSize: 13, fontWeight: 600, display: 'block', marginBottom: 4 }}>Slot Duration (Mins)</label>
              <select
                value={formSlotDuration}
                onChange={e => setFormSlotDuration(Number(e.target.value))}
                style={{ width: '100%', padding: '8px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}
              >
                <option value={15}>15 mins</option>
                <option value={20}>20 mins</option>
                <option value={30}>30 mins</option>
                <option value={45}>45 mins</option>
                <option value={60}>60 mins</option>
              </select>
            </div>

            <div>
              <button type="submit" className="btn btn-primary" disabled={submitting} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                <Plus size={16} /> {submitting ? 'Saving...' : 'Add Schedule'}
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Schedules List */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <h3><Calendar size={16} style={{ marginRight: 6 }} />Configured Doctor Schedules</h3>
            <select
              value={selectedDoctorId}
              onChange={e => setSelectedDoctorId(e.target.value)}
              style={{ padding: '6px 12px', border: '1.5px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: 13 }}
            >
              <option value="">All Doctors</option>
              {doctors.map(d => (
                <option key={d.id} value={d.id}>{d.display_name}</option>
              ))}
            </select>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={loadData} disabled={loading} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <RefreshCw size={13} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} />
            Refresh
          </button>
        </div>

        <div className="table-container">
          {loading ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>Loading schedules...</div>
          ) : filteredSchedules.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text-muted)' }}>No schedule slots configured yet.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Doctor</th>
                  <th>Department</th>
                  <th>Specialization</th>
                  <th>Day</th>
                  <th>Start Time</th>
                  <th>End Time</th>
                  <th>Slot Duration</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredSchedules.map(s => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600 }}>{s.doctor_name}</td>
                    <td>{s.department_name}</td>
                    <td style={{ fontSize: 12 }}>{s.specialization}</td>
                    <td><span className="intent-badge" style={{ background: '#EBF8FF', color: '#2B6CB0', fontWeight: 600 }}>{s.day_of_week}</span></td>
                    <td style={{ fontWeight: 600 }}>{format12HourTime(s.start_time)}</td>
                    <td style={{ fontWeight: 600 }}>{format12HourTime(s.end_time)}</td>
                    <td>{s.slot_duration_minutes} mins</td>
                    <td><span className="status-badge active">{s.status}</span></td>
                    <td>
                      <button
                        className="btn btn-danger btn-sm"
                        onClick={() => handleDeleteSchedule(s.id)}
                        style={{ display: 'flex', alignItems: 'center', gap: 4 }}
                      >
                        <Trash2 size={13} /> Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div style={{ padding: '12px 22px', fontSize: 13, color: 'var(--text-muted)' }}>
          {filteredSchedules.length} schedule slot(s) active
        </div>
      </div>
    </div>
  );
};

export default DoctorSchedules;
