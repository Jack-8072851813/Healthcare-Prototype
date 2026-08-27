"""Pydantic models for the AI RCM & Bed Allocation POC backend."""
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class ClaimStatus(str, Enum):
    approved = "Approved"
    rejected = "Rejected"
    pending = "Pending"
    under_review = "Under Review"


class RiskLevel(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"
    critical = "Critical"


class Claim(BaseModel):
    id: str
    patient_name: str
    patient_id: str
    insurance_provider: str
    procedure_category: str
    amount: float
    status: ClaimStatus
    claim_date: str
    discharge_date: Optional[str]
    authorization_number: Optional[str]
    discharge_summary: bool
    risk_score: int
    risk_level: RiskLevel
    risk_factors: List[str]
    recommended_action: str
    reviewed: bool = False


class ClaimSummary(BaseModel):
    id: str
    patient_name: str
    insurance_provider: str
    procedure_category: str
    amount: float
    status: ClaimStatus
    claim_date: str
    risk_score: int
    risk_level: RiskLevel


class RiskAnalysis(BaseModel):
    claim_id: str
    risk_score: int
    risk_level: RiskLevel
    risk_factors: List[str]
    recommended_action: str
    explainability: dict


class RCMDashboard(BaseModel):
    total_claims: int
    claims_at_risk: int
    potential_revenue_leakage: float
    first_pass_acceptance_rate: float
    claims_by_status: List[dict]
    rejection_trend: List[dict]
    top_rejection_reasons: List[dict]
    high_risk_claims: List[ClaimSummary]


class Department(BaseModel):
    name: str
    total_beds: int
    occupied: int
    available: int
    occupancy_rate: float


class BedForecastEntry(BaseModel):
    department: str
    available: int
    expected_demand: int
    shortage: int
    confidence: float


class BedForecast(BaseModel):
    horizon: str
    generated_at: str
    entries: List[BedForecastEntry]
    alerts: List[str]


class BedTurnaround(BaseModel):
    bed_id: str
    department: str
    patient_name: str
    admitted_date: str
    predicted_release: str
    confidence: float


class BedDashboardData(BaseModel):
    total_beds: int
    occupied: int
    available: int
    predicted_shortage: int
    occupancy_rate: float
    departments: List[Department]
    forecast_summary: List[dict]
    occupancy_trend: List[dict]


class AdmissionForecast(BaseModel):
    time_horizons: List[str]
    departments: List[str]
    data: List[dict]


# ── Radiology Models ──────────────────────────────────────────────────────────

class TriagePriorityEnum(str, Enum):
    critical = "CRITICAL"
    high = "HIGH"
    routine = "ROUTINE"
    processing = "PROCESSING"


class RadiologyStudyModel(BaseModel):
    id: str
    patientId: str
    modality: str
    bodyPart: str
    studyTime: str
    studyDate: str
    aiFinding: str
    confidenceScore: int
    priority: TriagePriorityEnum
    aiStatus: str
    modelVersion: str
    inferenceTimeSeconds: float
    probabilities: dict
    heatmapRegion: Optional[dict] = None
    feedback: dict
    patientAge: Optional[int] = None
    patientGender: Optional[str] = None
    referringPhysician: Optional[str] = None


class RadiologyDashboardSummaryModel(BaseModel):
    totalStudies: int
    critical: int
    high: int
    routine: int
    awaitingAnalysis: int
    agreementRate: int


class RadiologyFeedbackRequest(BaseModel):
    status: str
    comments: Optional[str] = None


class AnalyzeXRayRequest(BaseModel):
    studyId: Optional[str] = None
    modality: Optional[str] = "CR"
    bodyPart: Optional[str] = "CHEST"
    imageFileName: Optional[str] = None

