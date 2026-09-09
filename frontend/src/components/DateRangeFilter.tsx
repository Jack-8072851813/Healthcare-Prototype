import React, { useState, useEffect } from 'react';
import { Calendar, ChevronDown } from 'lucide-react';

export type DatePreset =
  | 'today'
  | 'yesterday'
  | 'tomorrow'
  | 'this_week'
  | 'last_week'
  | 'this_month'
  | 'last_month'
  | 'next_7_days'
  | 'next_30_days'
  | 'custom';

export interface DateRangeValue {
  dateFrom: string;
  dateTo: string;
  preset: DatePreset;
  displayLabel: string;
}

interface DateRangeFilterProps {
  initialPreset?: DatePreset;
  initialFrom?: string;
  initialTo?: string;
  onChange: (value: DateRangeValue) => void;
  className?: string;
}

export function toYMD(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function formatFriendlyDate(ymd: string): string {
  if (!ymd) return '';
  const parts = ymd.split('-');
  if (parts.length !== 3) return ymd;
  const d = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

export function calculateDateRange(preset: DatePreset, customFrom?: string, customTo?: string): { from: string; to: string; label: string } {
  const now = new Date();
  const todayYMD = toYMD(now);

  switch (preset) {
    case 'today':
      return { from: todayYMD, to: todayYMD, label: `Today (${formatFriendlyDate(todayYMD)})` };
    case 'yesterday': {
      const y = new Date(now);
      y.setDate(y.getDate() - 1);
      const yYMD = toYMD(y);
      return { from: yYMD, to: yYMD, label: `Yesterday (${formatFriendlyDate(yYMD)})` };
    }
    case 'tomorrow': {
      const t = new Date(now);
      t.setDate(t.getDate() + 1);
      const tYMD = toYMD(t);
      return { from: tYMD, to: tYMD, label: `Tomorrow (${formatFriendlyDate(tYMD)})` };
    }
    case 'this_week': {
      const day = now.getDay();
      const diff = (day + 6) % 7; // distance from Monday
      const monday = new Date(now);
      monday.setDate(monday.getDate() - diff);
      const sunday = new Date(monday);
      sunday.setDate(sunday.getDate() + 6);
      const f = toYMD(monday);
      const to = toYMD(sunday);
      return { from: f, to, label: `This Week (${formatFriendlyDate(f)} – ${formatFriendlyDate(to)})` };
    }
    case 'last_week': {
      const day = now.getDay();
      const diff = (day + 6) % 7;
      const lastMonday = new Date(now);
      lastMonday.setDate(lastMonday.getDate() - diff - 7);
      const lastSunday = new Date(lastMonday);
      lastSunday.setDate(lastSunday.getDate() + 6);
      const f = toYMD(lastMonday);
      const to = toYMD(lastSunday);
      return { from: f, to, label: `Last Week (${formatFriendlyDate(f)} – ${formatFriendlyDate(to)})` };
    }
    case 'this_month': {
      const first = new Date(now.getFullYear(), now.getMonth(), 1);
      const last = new Date(now.getFullYear(), now.getMonth() + 1, 0);
      const f = toYMD(first);
      const to = toYMD(last);
      return { from: f, to, label: `This Month (${formatFriendlyDate(f)} – ${formatFriendlyDate(to)})` };
    }
    case 'last_month': {
      const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      const last = new Date(now.getFullYear(), now.getMonth(), 0);
      const f = toYMD(first);
      const to = toYMD(last);
      return { from: f, to, label: `Last Month (${formatFriendlyDate(f)} – ${formatFriendlyDate(to)})` };
    }
    case 'next_7_days': {
      const next7 = new Date(now);
      next7.setDate(next7.getDate() + 7);
      const f = todayYMD;
      const to = toYMD(next7);
      return { from: f, to, label: `Next 7 Days (${formatFriendlyDate(f)} – ${formatFriendlyDate(to)})` };
    }
    case 'next_30_days': {
      const next30 = new Date(now);
      next30.setDate(next30.getDate() + 30);
      const f = todayYMD;
      const to = toYMD(next30);
      return { from: f, to, label: `Next 30 Days (${formatFriendlyDate(f)} – ${formatFriendlyDate(to)})` };
    }
    case 'custom':
    default: {
      const f = customFrom || todayYMD;
      const to = customTo || todayYMD;
      return { from: f, to, label: `Custom (${formatFriendlyDate(f)} – ${formatFriendlyDate(to)})` };
    }
  }
}

export const DateRangeFilter: React.FC<DateRangeFilterProps> = ({
  initialPreset = 'this_month',
  initialFrom,
  initialTo,
  onChange,
  className = '',
}) => {
  const [preset, setPreset] = useState<DatePreset>(initialPreset);
  const [customFrom, setCustomFrom] = useState<string>(initialFrom || toYMD(new Date()));
  const [customTo, setCustomTo] = useState<string>(initialTo || toYMD(new Date()));

  useEffect(() => {
    const { from, to, label } = calculateDateRange(preset, customFrom, customTo);
    onChange({
      dateFrom: from,
      dateTo: to,
      preset,
      displayLabel: label,
    });
  }, [preset, customFrom, customTo]);

  return (
    <div
      className={`date-range-filter-container ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        flexWrap: 'wrap',
        background: 'var(--bg-secondary)',
        padding: '6px 12px',
        borderRadius: 'var(--radius-md, 8px)',
        border: '1px solid var(--border)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--primary)', fontWeight: 600, fontSize: 13 }}>
        <Calendar size={15} />
        <span>Date Range:</span>
      </div>

      <select
        value={preset}
        onChange={(e) => setPreset(e.target.value as DatePreset)}
        style={{
          padding: '6px 12px',
          border: '1.5px solid var(--border)',
          borderRadius: 'var(--radius-sm, 6px)',
          fontSize: 13,
          fontWeight: 500,
          background: 'var(--bg-primary)',
          color: 'var(--text-primary)',
          cursor: 'pointer',
        }}
      >
        <option value="today">Today</option>
        <option value="yesterday">Yesterday</option>
        <option value="tomorrow">Tomorrow</option>
        <option value="this_week">This Week</option>
        <option value="last_week">Last Week</option>
        <option value="this_month">This Month</option>
        <option value="last_month">Last Month</option>
        <option value="next_7_days">Next 7 Days</option>
        <option value="next_30_days">Next 30 Days</option>
        <option value="custom">Custom Date Range</option>
      </select>

      {preset === 'custom' && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <input
            type="date"
            value={customFrom}
            onChange={(e) => setCustomFrom(e.target.value)}
            style={{
              padding: '5px 8px',
              border: '1.5px solid var(--border)',
              borderRadius: 'var(--radius-sm, 6px)',
              fontSize: 12,
              background: 'var(--bg-primary)',
              color: 'var(--text-primary)',
            }}
          />
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>→</span>
          <input
            type="date"
            value={customTo}
            onChange={(e) => setCustomTo(e.target.value)}
            style={{
              padding: '5px 8px',
              border: '1.5px solid var(--border)',
              borderRadius: 'var(--radius-sm, 6px)',
              fontSize: 12,
              background: 'var(--bg-primary)',
              color: 'var(--text-primary)',
            }}
          />
        </div>
      )}
    </div>
  );
};

export default DateRangeFilter;
