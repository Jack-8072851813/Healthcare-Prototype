// Synthetic claims data — mirrors the FastAPI /api/claims response shape.
// Used as offline fallback when the backend is not running.

export type ClaimStatus = 'Approved' | 'Rejected' | 'Pending' | 'Under Review';
export type RiskLevel = 'Low' | 'Medium' | 'High' | 'Critical';

export interface ClaimSummary {
  id: string;
  patient_name: string;
  patient_id: string;
  insurance_provider: string;
  procedure_category: string;
  amount: number;
  status: ClaimStatus;
  claim_date: string;
  risk_score: number;
  risk_level: RiskLevel;
}

export interface ClaimDetail extends ClaimSummary {
  discharge_date: string | null;
  authorization_number: string | null;
  discharge_summary: boolean;
  risk_factors: string[];
  recommended_action: string;
  reviewed: boolean;
}

export interface RCMDashboardData {
  total_claims: number;
  claims_at_risk: number;
  potential_revenue_leakage: number;
  first_pass_acceptance_rate: number;
  claims_by_status: { name: string; value: number }[];
  rejection_trend: { name: string; rejected: number; total: number }[];
  top_rejection_reasons: { reason: string; count: number }[];
  high_risk_claims: ClaimSummary[];
}

const PROVIDERS = [
  'Star Health', 'HDFC ERGO', 'Bajaj Allianz',
  'ICICI Lombard', 'New India Assurance', 'United India Insurance',
];
const CATEGORIES = [
  'Cardiology', 'Orthopaedics', 'General Surgery', 'Neurology',
  'Oncology', 'Paediatrics', 'Nephrology', 'Gastroenterology',
];
const PATIENTS = [
  'Arun Kumar', 'Priya Ramesh', 'Karthik Selvam', 'Meena Krishnan',
  'Suresh Babu', 'Lakshmi Devi', 'Rajan Pillai', 'Anitha Nair',
  'Balasubramanian R', 'Kavitha Sundaram', 'Dinesh Chandra', 'Usha Iyer',
  'Mohan Raj', 'Saranya Venkat', 'Vijay Shankar', 'Deepa Murugan',
  'Santhosh Kumar', 'Rekha Krishnaswamy', 'Prasad Narayanan', 'Geetha Raman',
];
const STATUSES: ClaimStatus[] = ['Approved', 'Rejected', 'Pending', 'Under Review'];

// Deterministic pseudo-random based on index
function seededRandom(seed: number): number {
  const x = Math.sin(seed + 1) * 10000;
  return x - Math.floor(x);
}

function pick<T>(arr: T[], seed: number): T {
  return arr[Math.floor(seededRandom(seed) * arr.length)];
}

const avgAmounts: Record<string, number> = {
  Cardiology: 147500, Orthopaedics: 105000, 'General Surgery': 55000,
  Neurology: 175000, Oncology: 290000, Paediatrics: 35000,
  Nephrology: 230000, Gastroenterology: 72500,
};

const riskIssues: Record<number, string[]> = {
  // missing discharge summary (i < 30)
};

function buildClaim(i: number): ClaimDetail {
  const cat = pick(CATEGORIES, i * 7);
  const provider = pick(PROVIDERS, i * 3 + 1);
  const patientName = pick(PATIENTS, i * 5 + 2);
  const patientId = `P${10000 + ((i * 137) % 89999)}`;
  const claimId = `CLM${(1000 + i).toString().padStart(4, '0')}`;
  const daysAgo = Math.floor(seededRandom(i * 11) * 180);
  const claimDate = new Date(Date.now() - daysAgo * 86400000).toISOString().split('T')[0];
  const dischargeDate = new Date(Date.now() - (daysAgo - 5) * 86400000).toISOString().split('T')[0];

  const baseAmount = avgAmounts[cat] * (0.4 + seededRandom(i * 13) * 1.2);
  const statusIdx = Math.floor(seededRandom(i * 17) * 10);
  const status: ClaimStatus = statusIdx < 5 ? 'Approved' : statusIdx < 7 ? 'Pending'
    : statusIdx < 9 ? 'Rejected' : 'Under Review';

  let amount = Math.round(baseAmount / 100) * 100;
  let hasDischarge = seededRandom(i * 19) > 0.1;
  let authNum: string | null = `AUTH${100000 + Math.floor(seededRandom(i * 23) * 899999)}`;
  let hasDischDate = seededRandom(i * 29) > 0.05;

  const factors: string[] = [];
  let score = 0;

  if (i < 30) { hasDischarge = false; }
  if (i >= 30 && i < 50) { authNum = null; }
  if (i >= 50 && i < 75) { amount = Math.round(avgAmounts[cat] * (2.2 + seededRandom(i) * 1.3) / 100) * 100; }
  if (i >= 75 && i < 95) { hasDischarge = false; authNum = null; }

  if (!hasDischarge) { score += 30; factors.push('Missing discharge summary — mandatory document not uploaded'); }
  if (!authNum) { score += 25; factors.push('No prior authorization number — insurance pre-approval not recorded'); }
  if (amount > avgAmounts[cat] * 2) {
    const pct = Math.round((amount / avgAmounts[cat] - 1) * 100);
    score += 20;
    factors.push(`Unusual billing amount — ${pct}% above category average for ${cat}`);
  }
  if (amount > 200000) { score += 10; factors.push('High-value claim (>₹2L) — requires enhanced scrutiny'); }
  if (status === 'Rejected') { score += 15; factors.push('Claim previously rejected — re-submission needs documentation review'); }
  if (!hasDischDate) { score += 5; factors.push('Discharge date missing — admission record may be incomplete'); }

  score = Math.min(score, 100);
  const riskLevel: RiskLevel = score <= 30 ? 'Low' : score <= 60 ? 'Medium' : score <= 80 ? 'High' : 'Critical';

  let recommendedAction = 'Proceed with standard claim processing. Routine spot-check recommended.';
  if (score >= 81) recommendedAction = 'Immediately escalate to billing manager and legal team. Suspend claim until all issues are resolved.';
  else if (score >= 61) recommendedAction = 'Hold for senior billing executive review. Upload all missing documents before resubmission.';
  else if (score >= 31) recommendedAction = 'Flag for billing executive review. Verify insurance eligibility and upload missing documents.';

  return {
    id: claimId, patient_name: patientName, patient_id: patientId,
    insurance_provider: provider, procedure_category: cat,
    amount, status, claim_date: claimDate,
    discharge_date: hasDischDate ? dischargeDate : null,
    authorization_number: authNum,
    discharge_summary: hasDischarge,
    risk_score: score, risk_level: riskLevel,
    risk_factors: factors, recommended_action: recommendedAction,
    reviewed: false,
  };
}

export const mockClaims: ClaimDetail[] = Array.from({ length: 260 }, (_, i) => buildClaim(i));

export const mockRCMDashboard: RCMDashboardData = (() => {
  const total = mockClaims.length;
  const atRisk = mockClaims.filter(c => c.risk_level === 'High' || c.risk_level === 'Critical').length;
  const leakage = mockClaims
    .filter(c => (c.risk_level === 'High' || c.risk_level === 'Critical') && c.status !== 'Approved')
    .reduce((sum, c) => sum + c.amount, 0);
  const approved = mockClaims.filter(c => c.status === 'Approved').length;

  const byStatus = STATUSES.map(s => ({
    name: s, value: mockClaims.filter(c => c.status === s).length,
  }));

  const rejectionTrend = Array.from({ length: 6 }, (_, m) => {
    const dt = new Date(Date.now() - (5 - m) * 30 * 86400000);
    return {
      name: dt.toLocaleString('default', { month: 'short' }),
      rejected: 8 + Math.floor(seededRandom(m * 7) * 20),
      total: 40 + Math.floor(seededRandom(m * 11) * 20),
    };
  });

  const reasonCounts: Record<string, number> = {};
  mockClaims.filter(c => c.status === 'Rejected').forEach(c => {
    c.risk_factors.forEach(f => {
      const key = f.split('—')[0].trim().slice(0, 40);
      reasonCounts[key] = (reasonCounts[key] || 0) + 1;
    });
  });
  const topReasons = Object.entries(reasonCounts)
    .sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([reason, count]) => ({ reason, count }));

  const highRisk = mockClaims
    .filter(c => c.risk_level === 'High' || c.risk_level === 'Critical')
    .sort((a, b) => b.risk_score - a.risk_score).slice(0, 10);

  return {
    total_claims: total,
    claims_at_risk: atRisk,
    potential_revenue_leakage: Math.round(leakage),
    first_pass_acceptance_rate: Math.round((approved / total) * 1000) / 10,
    claims_by_status: byStatus,
    rejection_trend: rejectionTrend,
    top_rejection_reasons: topReasons,
    high_risk_claims: highRisk,
  };
})();
