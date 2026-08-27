/**
 * API client for the Meridian AI RCM & Bed Allocation backend.
 * Tries the FastAPI backend first; falls back to in-memory mock data if unavailable.
 */

import { mockClaims, mockRCMDashboard, type ClaimDetail, type RCMDashboardData } from '../data/rcm/claims';
import {
  mockBedDashboard, mockBedForecasts, mockAdmissionForecast,
  type BedDashboardData, type BedForecastResponse, type AdmissionForecast,
} from '../data/rcm/beds';

// Re-export types so consumers can import them from this single module
export type { ClaimDetail, RCMDashboardData } from '../data/rcm/claims';
export type { BedDashboardData, BedForecastResponse, AdmissionForecast } from '../data/rcm/beds';

const BASE_URL = 'http://localhost:8000';
const TIMEOUT_MS = 2000;

// Track backend availability to avoid repeated slow timeouts
let _backendAvailable: boolean | null = null;

async function checkBackend(): Promise<boolean> {
  if (_backendAvailable !== null) return _backendAvailable;
  try {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const res = await fetch(`${BASE_URL}/health`, { signal: controller.signal });
    clearTimeout(t);
    _backendAvailable = res.ok;
  } catch {
    _backendAvailable = false;
  }
  return _backendAvailable;
}

async function apiFetch<T>(path: string): Promise<T | null> {
  const available = await checkBackend();
  if (!available) return null;
  try {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), 5000);
    const res = await fetch(`${BASE_URL}${path}`, { signal: controller.signal });
    clearTimeout(t);
    if (!res.ok) return null;
    return res.json() as Promise<T>;
  } catch {
    _backendAvailable = false;
    return null;
  }
}

// ── Claims ────────────────────────────────────────────────────────────────────

export interface ClaimsListResponse {
  total: number;
  page: number;
  per_page: number;
  claims: Omit<ClaimDetail, 'risk_factors' | 'recommended_action' | 'reviewed' | 'discharge_date' | 'authorization_number' | 'discharge_summary'>[];
}

export async function fetchClaims(params?: {
  status?: string; risk_level?: string; provider?: string;
  search?: string; page?: number; per_page?: number;
}): Promise<ClaimsListResponse> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.risk_level) qs.set('risk_level', params.risk_level);
  if (params?.provider) qs.set('provider', params.provider);
  if (params?.search) qs.set('search', params.search);
  if (params?.page) qs.set('page', String(params.page));
  if (params?.per_page) qs.set('per_page', String(params.per_page));

  const data = await apiFetch<ClaimsListResponse>(`/api/claims?${qs}`);
  if (data) return data;

  // Fallback
  let filtered = mockClaims;
  if (params?.status) filtered = filtered.filter(c => c.status === params.status);
  if (params?.risk_level) filtered = filtered.filter(c => c.risk_level === params.risk_level);
  if (params?.provider) filtered = filtered.filter(c => c.insurance_provider === params.provider);
  if (params?.search) {
    const q = params.search.toLowerCase();
    filtered = filtered.filter(c => c.patient_name.toLowerCase().includes(q) || c.id.toLowerCase().includes(q));
  }
  const page = params?.page || 1;
  const per_page = params?.per_page || 50;
  const start = (page - 1) * per_page;
  return {
    total: filtered.length,
    page, per_page,
    claims: filtered.slice(start, start + per_page).sort((a, b) => b.risk_score - a.risk_score),
  };
}

export async function fetchClaim(id: string): Promise<ClaimDetail | null> {
  const data = await apiFetch<ClaimDetail>(`/api/claims/${id}`);
  if (data) return data;
  return mockClaims.find(c => c.id === id) || null;
}

export async function fetchClaimRisk(id: string) {
  const data = await apiFetch(`/api/claims/${id}/risk`);
  if (data) return data;
  const claim = mockClaims.find(c => c.id === id);
  if (!claim) return null;
  return {
    claim_id: id, risk_score: claim.risk_score, risk_level: claim.risk_level,
    risk_factors: claim.risk_factors, recommended_action: claim.recommended_action,
    explainability: { methodology: 'Rule-based weighted scoring', max_score: 100, factor_weights: {} },
  };
}

export async function markClaimReviewed(id: string): Promise<boolean> {
  const available = await checkBackend();
  if (available) {
    try {
      const res = await fetch(`${BASE_URL}/api/claims/${id}/review`, { method: 'PATCH' });
      if (res.ok) return true;
    } catch {}
  }
  // Fallback: mutate in-memory (best effort)
  const claim = mockClaims.find(c => c.id === id);
  if (claim) claim.reviewed = !claim.reviewed;
  return true;
}

export async function fetchRCMDashboard(): Promise<RCMDashboardData> {
  const data = await apiFetch<RCMDashboardData>('/api/dashboard/rcm');
  return data || mockRCMDashboard;
}

// ── Beds ──────────────────────────────────────────────────────────────────────

export async function fetchBedDashboard(): Promise<BedDashboardData> {
  const data = await apiFetch<BedDashboardData>('/api/dashboard/beds');
  return data || mockBedDashboard;
}

export async function fetchBedForecast(horizon: '6h' | '12h' | '24h' | '7d'): Promise<BedForecastResponse> {
  const data = await apiFetch<BedForecastResponse>(`/api/beds/forecast?horizon=${horizon}`);
  return data || mockBedForecasts[horizon];
}

export async function fetchAdmissionForecast(): Promise<AdmissionForecast> {
  const data = await apiFetch<AdmissionForecast>('/api/admissions/forecast');
  return data || mockAdmissionForecast;
}
