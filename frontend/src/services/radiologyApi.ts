/**
 * Service API for Meridian AI Radiology Triage Assistant.
 * Connects to FastAPI backend (`http://localhost:8000/api/radiology/*`)
 * with fallback to local synthetic state if backend is offline.
 */

import {
  SYNTHETIC_STUDIES,
  PROTOTYPE_PERFORMANCE_METRICS,
  getSyntheticRadiologyDashboardSummary,
  type RadiologyStudy,
  type RadiologyDashboardSummary,
  type ModelPerformanceMetric,
  type ReviewStatus,
  type AIFindingType,
  type TriagePriority,
} from '../data/radiology/studies';

const BASE_URL = 'http://localhost:8000';
const TIMEOUT_MS = 2000;

// Local in-memory state for prototype fallback when backend is unavailable
let localStudies: RadiologyStudy[] = [...SYNTHETIC_STUDIES];
let isBackendAvailable: boolean | null = null;

async function checkBackendHealth(): Promise<boolean> {
  if (isBackendAvailable !== null) return isBackendAvailable;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
    const res = await fetch(`${BASE_URL}/health`, { signal: controller.signal });
    clearTimeout(timer);
    isBackendAvailable = res.ok;
  } catch {
    isBackendAvailable = false;
  }
  return isBackendAvailable;
}

export interface FetchStudiesParams {
  priority?: string;
  search?: string;
}

export async function fetchRadiologyDashboard(): Promise<RadiologyDashboardSummary> {
  const healthy = await checkBackendHealth();
  if (healthy) {
    try {
      const res = await fetch(`${BASE_URL}/api/radiology/dashboard`);
      if (res.ok) return await res.json();
    } catch {
      // Fallback
    }
  }
  return getSyntheticRadiologyDashboardSummary(localStudies);
}

export async function fetchRadiologyStudies(params?: FetchStudiesParams): Promise<RadiologyStudy[]> {
  const healthy = await checkBackendHealth();
  if (healthy) {
    try {
      const query = new URLSearchParams();
      if (params?.priority && params.priority !== 'All') query.set('priority', params.priority);
      if (params?.search) query.set('search', params.search);
      const res = await fetch(`${BASE_URL}/api/radiology/studies?${query.toString()}`);
      if (res.ok) return await res.json();
    } catch {
      // Fallback
    }
  }

  // Local fallback logic
  let filtered = [...localStudies];

  if (params?.priority && params.priority !== 'All') {
    if (params.priority === 'Awaiting Analysis') {
      filtered = filtered.filter(s => s.aiStatus === 'Processing' || s.aiStatus === 'Awaiting Analysis');
    } else {
      filtered = filtered.filter(s => s.priority === params.priority);
    }
  }

  if (params?.search) {
    const q = params.search.toLowerCase();
    filtered = filtered.filter(
      s => s.id.toLowerCase().includes(q) || s.patientId.toLowerCase().includes(q) || s.aiFinding.toLowerCase().includes(q)
    );
  }

  // Priority sorting: CRITICAL -> HIGH -> ROUTINE -> PROCESSING, then oldest first
  const priorityRank: Record<TriagePriority, number> = {
    CRITICAL: 1,
    HIGH: 2,
    ROUTINE: 3,
    PROCESSING: 4,
  };

  filtered.sort((a, b) => {
    const rankDiff = priorityRank[a.priority] - priorityRank[b.priority];
    if (rankDiff !== 0) return rankDiff;
    return a.studyTime.localeCompare(b.studyTime);
  });

  return filtered;
}

export async function fetchRadiologyStudy(id: string): Promise<RadiologyStudy | null> {
  const healthy = await checkBackendHealth();
  if (healthy) {
    try {
      const res = await fetch(`${BASE_URL}/api/radiology/studies/${id}`);
      if (res.ok) return await res.json();
    } catch {
      // Fallback
    }
  }
  const found = localStudies.find(s => s.id.toLowerCase() === id.toLowerCase());
  return found || null;
}

export interface AnalyzeRequest {
  studyId?: string;
  modality?: 'CR' | 'DX';
  bodyPart?: string;
  imageFileName?: string;
}

export async function analyzeChestXRay(req: AnalyzeRequest): Promise<RadiologyStudy> {
  const healthy = await checkBackendHealth();
  if (healthy) {
    try {
      const res = await fetch(`${BASE_URL}/api/radiology/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
      });
      if (res.ok) return await res.json();
    } catch {
      // Fallback
    }
  }

  // Local simulated inference result generator
  const generatedId = req.studyId || `CXR-2026-${String(localStudies.length + 10).padStart(3, '0')}`;
  
  // Simulated prediction outcomes (deterministic seed based on ID)
  const outcomes: { finding: AIFindingType; priority: TriagePriority; conf: number; probs: { pneumothorax: number; pneumonia: number; pleuralEffusion: number; noUrgentFinding: number } }[] = [
    {
      finding: 'Possible Pneumothorax',
      priority: 'CRITICAL',
      conf: 93,
      probs: { pneumothorax: 93, pneumonia: 14, pleuralEffusion: 9, noUrgentFinding: 5 },
    },
    {
      finding: 'Possible Pneumonia',
      priority: 'HIGH',
      conf: 86,
      probs: { pneumothorax: 6, pneumonia: 86, pleuralEffusion: 38, noUrgentFinding: 10 },
    },
    {
      finding: 'Possible Pleural Effusion',
      priority: 'HIGH',
      conf: 81,
      probs: { pneumothorax: 7, pneumonia: 31, pleuralEffusion: 81, noUrgentFinding: 15 },
    },
    {
      finding: 'No Urgent Finding',
      priority: 'ROUTINE',
      conf: 94,
      probs: { pneumothorax: 2, pneumonia: 4, pleuralEffusion: 3, noUrgentFinding: 94 },
    },
  ];

  const selected = outcomes[localStudies.length % outcomes.length];

  const now = new Date();
  const newStudy: RadiologyStudy = {
    id: generatedId,
    patientId: `PT-${Math.floor(1000 + Math.random() * 9000)}`,
    modality: req.modality || 'CR',
    bodyPart: req.bodyPart || 'CHEST',
    studyTime: now.toTimeString().split(' ')[0],
    studyDate: now.toISOString().split('T')[0],
    aiFinding: selected.finding,
    confidenceScore: selected.conf,
    priority: selected.priority,
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.8,
    probabilities: selected.probs,
    heatmapRegion: selected.priority !== 'ROUTINE' ? { x: 65, y: 45, radius: 24, label: selected.finding } : undefined,
    feedback: { status: 'Unreviewed' },
    patientAge: 45,
    patientGender: 'M',
    referringPhysician: 'Dr. S. Ramanathan (Emergency Medicine)',
  };

  // Add to local state (prepend so it shows up at top)
  localStudies = [newStudy, ...localStudies];
  return newStudy;
}

export async function submitRadiologistFeedback(
  id: string,
  feedback: { status: ReviewStatus; comments?: string }
): Promise<RadiologyStudy | null> {
  const healthy = await checkBackendHealth();
  if (healthy) {
    try {
      const res = await fetch(`${BASE_URL}/api/radiology/studies/${id}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(feedback),
      });
      if (res.ok) return await res.json();
    } catch {
      // Fallback
    }
  }

  const idx = localStudies.findIndex(s => s.id.toLowerCase() === id.toLowerCase());
  if (idx !== -1) {
    localStudies[idx] = {
      ...localStudies[idx],
      feedback: {
        status: feedback.status,
        comments: feedback.comments,
        reviewedBy: 'Dr. V. Kapoor (Radiology)',
        reviewedAt: new Date().toISOString().replace('T', ' ').slice(0, 16),
      },
    };
    return localStudies[idx];
  }
  return null;
}

export async function fetchModelPerformanceMetrics(): Promise<ModelPerformanceMetric[]> {
  const healthy = await checkBackendHealth();
  if (healthy) {
    try {
      const res = await fetch(`${BASE_URL}/api/radiology/performance`);
      if (res.ok) return await res.json();
    } catch {
      // Fallback
    }
  }
  return PROTOTYPE_PERFORMANCE_METRICS;
}
