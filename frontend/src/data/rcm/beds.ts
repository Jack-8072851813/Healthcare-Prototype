// Synthetic bed & department data — mirrors FastAPI /api/beds and /api/dashboard/beds response shapes.

export interface Department {
  name: string;
  total_beds: number;
  occupied: number;
  available: number;
  occupancy_rate: number;
}

export interface BedForecastEntry {
  department: string;
  available: number;
  expected_demand: number;
  shortage: number;
  confidence: number;
}

export interface BedForecastResponse {
  horizon: string;
  generated_at: string;
  entries: BedForecastEntry[];
  alerts: string[];
}

export interface BedDashboardData {
  total_beds: number;
  occupied: number;
  available: number;
  predicted_shortage: number;
  occupancy_rate: number;
  departments: Department[];
  forecast_summary: BedForecastEntry[];
  occupancy_trend: { name: string; current: number; predicted: number }[];
}

export interface AdmissionForecast {
  time_horizons: string[];
  departments: string[];
  data: { department: string; current: number; '6h': number; '12h': number; '24h': number; '7d': number }[];
}

const DEPT_CONFIG = [
  { name: 'ICU',          total_beds: 20, occupied: 17 },
  { name: 'General Ward', total_beds: 80, occupied: 58 },
  { name: 'Paediatric',   total_beds: 30, occupied: 22 },
  { name: 'Surgical',     total_beds: 40, occupied: 31 },
];

function seededRandom(seed: number): number {
  const x = Math.sin(seed + 1) * 10000;
  return x - Math.floor(x);
}

function buildDepartments(): Department[] {
  return DEPT_CONFIG.map(d => ({
    ...d,
    available: d.total_beds - d.occupied,
    occupancy_rate: Math.round((d.occupied / d.total_beds) * 1000) / 10,
  }));
}

function buildForecast(horizon: string, depts: Department[]): BedForecastResponse {
  const surgeMap: Record<string, number> = { '6h': 0.15, '12h': 0.28, '24h': 0.50, '7d': 2.1 };
  const baseSurge = surgeMap[horizon] || 0.5;

  const entries: BedForecastEntry[] = depts.map((d, i) => {
    const seed = (d.name.length * 17 + i * 31 + horizon.length) % 1000;
    const surge = baseSurge * (0.8 + seededRandom(seed) * 0.5);
    const expected = Math.ceil(d.available * surge * (0.7 + seededRandom(seed + 1) * 0.7));
    const shortage = Math.max(0, expected - d.available);
    return {
      department: d.name,
      available: d.available,
      expected_demand: expected,
      shortage,
      confidence: Math.round((0.72 + seededRandom(seed + 2) * 0.22) * 100) / 100,
    };
  });

  const alerts = entries
    .filter(e => e.shortage > 0)
    .map(e => `⚠️  Predicted shortage of ${e.shortage} bed(s) in ${e.department} within ${horizon}`);

  return { horizon, generated_at: new Date().toISOString(), entries, alerts };
}

export const mockDepartments: Department[] = buildDepartments();

export const mockBedForecasts: Record<string, BedForecastResponse> = {
  '6h':  buildForecast('6h',  mockDepartments),
  '12h': buildForecast('12h', mockDepartments),
  '24h': buildForecast('24h', mockDepartments),
  '7d':  buildForecast('7d',  mockDepartments),
};

export const mockBedDashboard: BedDashboardData = (() => {
  const total = mockDepartments.reduce((s, d) => s + d.total_beds, 0);
  const occupied = mockDepartments.reduce((s, d) => s + d.occupied, 0);
  const available = total - occupied;
  const occ_rate = Math.round((occupied / total) * 1000) / 10;
  const fc24 = mockBedForecasts['24h'].entries;
  const predicted_shortage = fc24.reduce((s, e) => s + e.shortage, 0);

  const occupancy_trend = Array.from({ length: 8 }, (_, i) => {
    const dt = new Date(Date.now() - (7 - i) * 86400000);
    const seed = i * 13;
    const cur = Math.min(Math.round(occupied * (0.88 + seededRandom(seed) * 0.17)), total);
    const pred = Math.min(Math.round(cur * (1.0 + seededRandom(seed + 1) * 0.08)), total);
    return {
      name: dt.toLocaleDateString('en-IN', { weekday: 'short' }),
      current: cur,
      predicted: pred,
    };
  });

  return {
    total_beds: total,
    occupied,
    available,
    predicted_shortage,
    occupancy_rate: occ_rate,
    departments: mockDepartments,
    forecast_summary: fc24,
    occupancy_trend,
  };
})();

export const mockAdmissionForecast: AdmissionForecast = (() => {
  const horizons = ['6h', '12h', '24h', '7d'] as const;
  const data = mockDepartments.map(d => {
    const entry: Record<string, number | string> = { department: d.name, current: d.occupied };
    horizons.forEach(h => {
      const fc = buildForecast(h, [d]);
      entry[h] = fc.entries[0].expected_demand;
    });
    return entry as AdmissionForecast['data'][0];
  });
  return { time_horizons: [...horizons], departments: mockDepartments.map(d => d.name), data };
})();
