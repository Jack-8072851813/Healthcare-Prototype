export type Modality = 'CR' | 'DX';
export type TriagePriority = 'CRITICAL' | 'HIGH' | 'ROUTINE' | 'PROCESSING';
export type AIFindingType =
  | 'Possible Pneumothorax'
  | 'Possible Pneumonia'
  | 'Possible Pleural Effusion'
  | 'No Urgent Finding'
  | 'Analysis Pending';

export type AIStatus = 'Completed' | 'Processing' | 'Awaiting Analysis' | 'Failed';

export type ReviewStatus = 'Agree' | 'Disagree' | 'Needs Further Review' | 'Unreviewed';

export interface FindingProbabilities {
  pneumothorax: number;
  pneumonia: number;
  pleuralEffusion: number;
  noUrgentFinding: number;
}

export interface RadiologistFeedback {
  status: ReviewStatus;
  comments?: string;
  reviewedBy?: string;
  reviewedAt?: string;
}

export interface RadiologyStudy {
  id: string;
  patientId: string;
  modality: Modality;
  bodyPart: string;
  studyTime: string;
  studyDate: string;
  aiFinding: AIFindingType;
  confidenceScore: number; // 0 to 100
  priority: TriagePriority;
  aiStatus: AIStatus;
  modelVersion: string;
  inferenceTimeSeconds: number;
  probabilities: FindingProbabilities;
  heatmapRegion?: { x: number; y: number; radius: number; label: string };
  feedback: RadiologistFeedback;
  patientAge?: number;
  patientGender?: 'M' | 'F';
  referringPhysician?: string;
}

export const SYNTHETIC_STUDIES: RadiologyStudy[] = [
  {
    id: 'CXR-2026-017',
    patientId: 'PT-9821',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '08:14:22',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pneumothorax',
    confidenceScore: 94,
    priority: 'CRITICAL',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.8,
    probabilities: { pneumothorax: 94, pneumonia: 12, pleuralEffusion: 8, noUrgentFinding: 4 },
    heatmapRegion: { x: 72, y: 35, radius: 22, label: 'Right Pleural Air Space / Visceral Line' },
    feedback: { status: 'Unreviewed' },
    patientAge: 48,
    patientGender: 'M',
    referringPhysician: 'Dr. S. Ramanathan (Emergency Medicine)',
  },
  {
    id: 'CXR-2026-011',
    patientId: 'PT-9043',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '08:42:05',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pneumonia',
    confidenceScore: 87,
    priority: 'HIGH',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.6,
    probabilities: { pneumothorax: 5, pneumonia: 87, pleuralEffusion: 42, noUrgentFinding: 9 },
    heatmapRegion: { x: 32, y: 58, radius: 26, label: 'Right Lower Lobe Consolidation' },
    feedback: { status: 'Agree', comments: 'Concur with AI finding. Right lower lobe opacity consistent with acute consolidation.', reviewedBy: 'Dr. V. Kapoor (Radiology)', reviewedAt: '2026-08-27 09:15' },
    patientAge: 62,
    patientGender: 'F',
    referringPhysician: 'Dr. A. Sundaram (Pulmonology)',
  },
  {
    id: 'CXR-2026-009',
    patientId: 'PT-8712',
    modality: 'DX',
    bodyPart: 'CHEST',
    studyTime: '09:05:18',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pleural Effusion',
    confidenceScore: 82,
    priority: 'HIGH',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.9,
    probabilities: { pneumothorax: 8, pneumonia: 34, pleuralEffusion: 82, noUrgentFinding: 14 },
    heatmapRegion: { x: 28, y: 72, radius: 24, label: 'Left Costophrenic Angle Blunting' },
    feedback: { status: 'Unreviewed' },
    patientAge: 55,
    patientGender: 'M',
    referringPhysician: 'Dr. M. Joseph (General Medicine)',
  },
  {
    id: 'CXR-2026-015',
    patientId: 'PT-9934',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '09:22:40',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pneumothorax',
    confidenceScore: 91,
    priority: 'CRITICAL',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.7,
    probabilities: { pneumothorax: 91, pneumonia: 18, pleuralEffusion: 15, noUrgentFinding: 6 },
    heatmapRegion: { x: 25, y: 30, radius: 20, label: 'Apical Pneumothorax Rim' },
    feedback: { status: 'Unreviewed' },
    patientAge: 31,
    patientGender: 'M',
    referringPhysician: 'Dr. S. Ramanathan (Emergency Medicine)',
  },
  {
    id: 'CXR-2026-004',
    patientId: 'PT-7611',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '09:45:12',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pneumonia',
    confidenceScore: 84,
    priority: 'HIGH',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.8,
    probabilities: { pneumothorax: 4, pneumonia: 84, pleuralEffusion: 22, noUrgentFinding: 11 },
    heatmapRegion: { x: 68, y: 52, radius: 25, label: 'Perihilar Patchy Infiltrates' },
    feedback: { status: 'Unreviewed' },
    patientAge: 71,
    patientGender: 'F',
    referringPhysician: 'Dr. K. Swaminathan (Internal Medicine)',
  },
  {
    id: 'CXR-2026-008',
    patientId: 'PT-8290',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '10:02:33',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pleural Effusion',
    confidenceScore: 78,
    priority: 'HIGH',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.9,
    probabilities: { pneumothorax: 6, pneumonia: 28, pleuralEffusion: 78, noUrgentFinding: 18 },
    heatmapRegion: { x: 74, y: 70, radius: 22, label: 'Right Costophrenic Sulcus Opacification' },
    feedback: { status: 'Unreviewed' },
    patientAge: 64,
    patientGender: 'M',
    referringPhysician: 'Dr. N. Deshmukh (Cardiology)',
  },
  {
    id: 'CXR-2026-003',
    patientId: 'PT-7105',
    modality: 'DX',
    bodyPart: 'CHEST',
    studyTime: '10:15:00',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pneumothorax',
    confidenceScore: 96,
    priority: 'CRITICAL',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.7,
    probabilities: { pneumothorax: 96, pneumonia: 9, pleuralEffusion: 11, noUrgentFinding: 3 },
    heatmapRegion: { x: 75, y: 28, radius: 24, label: 'Tension Pneumothorax Rim Right Apex' },
    feedback: { status: 'Agree', comments: 'Urgent notification sent to ICU team. Large right apical pneumothorax confirmed.', reviewedBy: 'Dr. V. Kapoor (Radiology)', reviewedAt: '2026-08-27 10:20' },
    patientAge: 29,
    patientGender: 'M',
    referringPhysician: 'Dr. S. Ramanathan (Trauma/Emergency)',
  },
  {
    id: 'CXR-2026-021',
    patientId: 'PT-9988',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '10:30:15',
    studyDate: '2026-08-27',
    aiFinding: 'No Urgent Finding',
    confidenceScore: 91,
    priority: 'ROUTINE',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.5,
    probabilities: { pneumothorax: 2, pneumonia: 5, pleuralEffusion: 3, noUrgentFinding: 91 },
    feedback: { status: 'Unreviewed' },
    patientAge: 42,
    patientGender: 'F',
    referringPhysician: 'Dr. P. Nair (Occupational Health)',
  },
  {
    id: 'CXR-2026-022',
    patientId: 'PT-9989',
    modality: 'DX',
    bodyPart: 'CHEST',
    studyTime: '10:45:00',
    studyDate: '2026-08-27',
    aiFinding: 'No Urgent Finding',
    confidenceScore: 95,
    priority: 'ROUTINE',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.4,
    probabilities: { pneumothorax: 1, pneumonia: 3, pleuralEffusion: 2, noUrgentFinding: 95 },
    feedback: { status: 'Unreviewed' },
    patientAge: 38,
    patientGender: 'M',
    referringPhysician: 'Dr. M. Joseph (General Medicine)',
  },
  {
    id: 'CXR-2026-023',
    patientId: 'PT-9990',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '11:00:20',
    studyDate: '2026-08-27',
    aiFinding: 'No Urgent Finding',
    confidenceScore: 89,
    priority: 'ROUTINE',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.6,
    probabilities: { pneumothorax: 3, pneumonia: 7, pleuralEffusion: 5, noUrgentFinding: 89 },
    feedback: { status: 'Unreviewed' },
    patientAge: 51,
    patientGender: 'F',
    referringPhysician: 'Dr. K. Swaminathan (Internal Medicine)',
  },
  {
    id: 'CXR-2026-024',
    patientId: 'PT-9991',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '11:15:40',
    studyDate: '2026-08-27',
    aiFinding: 'No Urgent Finding',
    confidenceScore: 93,
    priority: 'ROUTINE',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.5,
    probabilities: { pneumothorax: 2, pneumonia: 4, pleuralEffusion: 3, noUrgentFinding: 93 },
    feedback: { status: 'Unreviewed' },
    patientAge: 27,
    patientGender: 'M',
    referringPhysician: 'Dr. A. Sundaram (Outpatient Clinic)',
  },
  {
    id: 'CXR-2026-025',
    patientId: 'PT-9992',
    modality: 'DX',
    bodyPart: 'CHEST',
    studyTime: '11:30:10',
    studyDate: '2026-08-27',
    aiFinding: 'No Urgent Finding',
    confidenceScore: 88,
    priority: 'ROUTINE',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.7,
    probabilities: { pneumothorax: 4, pneumonia: 8, pleuralEffusion: 6, noUrgentFinding: 88 },
    feedback: { status: 'Unreviewed' },
    patientAge: 66,
    patientGender: 'F',
    referringPhysician: 'Dr. N. Deshmukh (Cardiology)',
  },
  {
    id: 'CXR-2026-026',
    patientId: 'PT-9993',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '11:42:00',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pneumonia',
    confidenceScore: 76,
    priority: 'HIGH',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.8,
    probabilities: { pneumothorax: 5, pneumonia: 76, pleuralEffusion: 31, noUrgentFinding: 18 },
    heatmapRegion: { x: 35, y: 48, radius: 20, label: 'Mid-zone interstitial markings' },
    feedback: { status: 'Unreviewed' },
    patientAge: 59,
    patientGender: 'M',
    referringPhysician: 'Dr. A. Sundaram (Pulmonology)',
  },
  {
    id: 'CXR-2026-027',
    patientId: 'PT-9994',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '11:55:10',
    studyDate: '2026-08-27',
    aiFinding: 'Possible Pleural Effusion',
    confidenceScore: 79,
    priority: 'HIGH',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.9,
    probabilities: { pneumothorax: 7, pneumonia: 29, pleuralEffusion: 79, noUrgentFinding: 16 },
    heatmapRegion: { x: 26, y: 68, radius: 22, label: 'Left costophrenic angle blunting' },
    feedback: { status: 'Unreviewed' },
    patientAge: 73,
    patientGender: 'F',
    referringPhysician: 'Dr. M. Joseph (General Medicine)',
  },
  {
    id: 'CXR-2026-028',
    patientId: 'PT-9995',
    modality: 'DX',
    bodyPart: 'CHEST',
    studyTime: '12:05:00',
    studyDate: '2026-08-27',
    aiFinding: 'No Urgent Finding',
    confidenceScore: 92,
    priority: 'ROUTINE',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.5,
    probabilities: { pneumothorax: 2, pneumonia: 5, pleuralEffusion: 4, noUrgentFinding: 92 },
    feedback: { status: 'Unreviewed' },
    patientAge: 45,
    patientGender: 'M',
    referringPhysician: 'Dr. P. Nair (Pre-Op Assessment)',
  },
  {
    id: 'CXR-2026-029',
    patientId: 'PT-9996',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '12:12:30',
    studyDate: '2026-08-27',
    aiFinding: 'No Urgent Finding',
    confidenceScore: 94,
    priority: 'ROUTINE',
    aiStatus: 'Completed',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 1.6,
    probabilities: { pneumothorax: 1, pneumonia: 3, pleuralEffusion: 3, noUrgentFinding: 94 },
    feedback: { status: 'Unreviewed' },
    patientAge: 53,
    patientGender: 'F',
    referringPhysician: 'Dr. K. Swaminathan (Internal Medicine)',
  },
  {
    id: 'CXR-2026-030',
    patientId: 'PT-9997',
    modality: 'CR',
    bodyPart: 'CHEST',
    studyTime: '12:20:00',
    studyDate: '2026-08-27',
    aiFinding: 'Analysis Pending',
    confidenceScore: 0,
    priority: 'PROCESSING',
    aiStatus: 'Awaiting Analysis',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 0,
    probabilities: { pneumothorax: 0, pneumonia: 0, pleuralEffusion: 0, noUrgentFinding: 0 },
    feedback: { status: 'Unreviewed' },
    patientAge: 60,
    patientGender: 'M',
    referringPhysician: 'Dr. S. Ramanathan (Emergency Medicine)',
  },
  {
    id: 'CXR-2026-031',
    patientId: 'PT-9998',
    modality: 'DX',
    bodyPart: 'CHEST',
    studyTime: '12:25:15',
    studyDate: '2026-08-27',
    aiFinding: 'Analysis Pending',
    confidenceScore: 0,
    priority: 'PROCESSING',
    aiStatus: 'Processing',
    modelVersion: 'chest-xray-triage-v1',
    inferenceTimeSeconds: 0,
    probabilities: { pneumothorax: 0, pneumonia: 0, pleuralEffusion: 0, noUrgentFinding: 0 },
    feedback: { status: 'Unreviewed' },
    patientAge: 34,
    patientGender: 'F',
    referringPhysician: 'Dr. A. Sundaram (Pulmonology)',
  },
];

export interface ModelPerformanceMetric {
  finding: string;
  sensitivity: number;
  specificity: number;
  precision: number;
  recall: number;
  f1Score: number;
  auroc: number;
  sampleCount: number;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  trueNegatives: number;
}

export const PROTOTYPE_PERFORMANCE_METRICS: ModelPerformanceMetric[] = [
  {
    finding: 'Pneumothorax',
    sensitivity: 0.942,
    specificity: 0.985,
    precision: 0.915,
    recall: 0.942,
    f1Score: 0.928,
    auroc: 0.978,
    sampleCount: 450,
    truePositives: 98,
    falsePositives: 9,
    falseNegatives: 6,
    trueNegatives: 337,
  },
  {
    finding: 'Pneumonia / Lung Opacity',
    sensitivity: 0.895,
    specificity: 0.941,
    precision: 0.868,
    recall: 0.895,
    f1Score: 0.881,
    auroc: 0.952,
    sampleCount: 620,
    truePositives: 170,
    falsePositives: 26,
    falseNegatives: 20,
    trueNegatives: 404,
  },
  {
    finding: 'Pleural Effusion',
    sensitivity: 0.918,
    specificity: 0.963,
    precision: 0.892,
    recall: 0.918,
    f1Score: 0.905,
    auroc: 0.966,
    sampleCount: 510,
    truePositives: 124,
    falsePositives: 15,
    falseNegatives: 11,
    trueNegatives: 360,
  },
];

export interface RadiologyDashboardSummary {
  totalStudies: number;
  critical: number;
  high: number;
  routine: number;
  awaitingAnalysis: number;
  agreementRate: number;
}

export function getSyntheticRadiologyDashboardSummary(studies: RadiologyStudy[]): RadiologyDashboardSummary {
  const critical = studies.filter(s => s.priority === 'CRITICAL').length;
  const high = studies.filter(s => s.priority === 'HIGH').length;
  const routine = studies.filter(s => s.priority === 'ROUTINE').length;
  const awaitingAnalysis = studies.filter(s => s.aiStatus === 'Processing' || s.aiStatus === 'Awaiting Analysis').length;
  
  const reviewed = studies.filter(s => s.feedback.status !== 'Unreviewed');
  const agreed = reviewed.filter(s => s.feedback.status === 'Agree').length;
  const agreementRate = reviewed.length > 0 ? Math.round((agreed / reviewed.length) * 100) : 94;

  return {
    totalStudies: studies.length,
    critical,
    high,
    routine,
    awaitingAnalysis,
    agreementRate,
  };
}
