"""
FastAPI backend for the AI RCM & Predictive Bed Allocation POC.
Run: uvicorn main:app --reload
(Requires hospital.db — run seed_data.py first)
"""
import json
import math
import random
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DB_PATH = "hospital.db"

app = FastAPI(
    title="Meridian Hospital — AI RCM & Bed Allocation API",
    description="Mock backend for the AI Revenue Cycle Management and Predictive Bed Allocation POC",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import api.agent_routes as agent_routes
app.include_router(agent_routes.router)

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from appointment_service import (
    AppointmentError, EntityNotFoundError, DoctorInactiveError,
    InvalidScheduleError, PastDateError, SlotUnavailableError,
    InvalidStatusTransitionError
)

@app.exception_handler(EntityNotFoundError)
def entity_not_found_handler(request: Request, exc: EntityNotFoundError):
    return JSONResponse(
        status_code=404,
        content={"success": False, "error_code": exc.error_code, "message": exc.message}
    )

@app.exception_handler(AppointmentError)
def appointment_error_handler(request: Request, exc: AppointmentError):
    return JSONResponse(
        status_code=400,
        content={"success": False, "error_code": exc.error_code, "message": exc.message}
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row) -> dict:
    d = dict(row)
    # Parse JSON fields
    if "risk_factors" in d and isinstance(d["risk_factors"], str):
        try:
            d["risk_factors"] = json.loads(d["risk_factors"])
        except Exception:
            d["risk_factors"] = []
    if "discharge_summary" in d:
        d["discharge_summary"] = bool(d["discharge_summary"])
    if "reviewed" in d:
        d["reviewed"] = bool(d["reviewed"])
    return d


def risk_level_from_score(score: int) -> str:
    if score <= 30:
        return "Low"
    elif score <= 60:
        return "Medium"
    elif score <= 80:
        return "High"
    return "Critical"


# ─── Claims endpoints ─────────────────────────────────────────────────────────

@app.get("/api/claims")
def list_claims(
    status: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, le=200),
):
    """Paginated, filterable list of all claims with risk summaries."""
    conn = get_db()
    c = conn.cursor()

    base_query = "SELECT * FROM claims WHERE 1=1"
    params = []

    if status:
        base_query += " AND status = ?"
        params.append(status)
    if risk_level:
        base_query += " AND risk_level = ?"
        params.append(risk_level)
    if provider:
        base_query += " AND insurance_provider = ?"
        params.append(provider)
    if search:
        base_query += " AND (patient_name LIKE ? OR id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    count_row = conn.execute(f"SELECT COUNT(*) FROM ({base_query})", params).fetchone()
    total = count_row[0]

    offset = (page - 1) * per_page
    rows = c.execute(
        base_query + " ORDER BY risk_score DESC, claim_date DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    conn.close()

    claims = []
    for row in rows:
        d = row_to_dict(row)
        claims.append({
            "id": d["id"],
            "patient_name": d["patient_name"],
            "patient_id": d["patient_id"],
            "insurance_provider": d["insurance_provider"],
            "procedure_category": d["procedure_category"],
            "amount": d["amount"],
            "status": d["status"],
            "claim_date": d["claim_date"],
            "risk_score": d["risk_score"],
            "risk_level": d["risk_level"],
        })

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "claims": claims,
    }


@app.get("/api/claims/{claim_id}")
def get_claim(claim_id: str):
    """Full claim detail with risk factors and recommendation."""
    conn = get_db()
    row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Claim not found")
    return row_to_dict(row)


@app.get("/api/claims/{claim_id}/risk")
def get_claim_risk(claim_id: str):
    """Risk analysis with explainability breakdown."""
    conn = get_db()
    row = conn.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Claim not found")
    d = row_to_dict(row)

    factors = d.get("risk_factors", [])
    factor_weights = {}
    for f in factors:
        if "discharge summary" in f.lower():
            factor_weights["Missing Discharge Summary"] = 30
        elif "authorization" in f.lower():
            factor_weights["No Prior Authorization"] = 25
        elif "unusual billing" in f.lower() or "billing amount" in f.lower():
            factor_weights["Unusual Billing Amount"] = 20
        elif "high-value" in f.lower():
            factor_weights["High-Value Claim"] = 10
        elif "rejected" in f.lower():
            factor_weights["Previously Rejected"] = 15
        elif "discharge date" in f.lower():
            factor_weights["Missing Discharge Date"] = 5
        elif "duplicate" in f.lower():
            factor_weights["Potential Duplicate"] = 20

    return {
        "claim_id": claim_id,
        "risk_score": d["risk_score"],
        "risk_level": d["risk_level"],
        "risk_factors": factors,
        "recommended_action": d["recommended_action"],
        "explainability": {
            "factor_weights": factor_weights,
            "max_score": 100,
            "methodology": "Rule-based weighted scoring",
        },
    }


@app.patch("/api/claims/{claim_id}/review")
def mark_reviewed(claim_id: str):
    """Toggle the 'reviewed' flag on a claim (in-memory persistence via SQLite)."""
    conn = get_db()
    row = conn.execute("SELECT reviewed FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Claim not found")
    new_val = 0 if row["reviewed"] else 1
    conn.execute("UPDATE claims SET reviewed = ? WHERE id = ?", (new_val, claim_id))
    conn.commit()
    conn.close()
    return {"claim_id": claim_id, "reviewed": bool(new_val)}


# ─── RCM Dashboard ────────────────────────────────────────────────────────────

@app.get("/api/dashboard/rcm")
def rcm_dashboard():
    conn = get_db()

    total = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    at_risk = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE risk_level IN ('High', 'Critical')"
    ).fetchone()[0]
    leakage = conn.execute(
        "SELECT SUM(amount) FROM claims WHERE risk_level IN ('High', 'Critical') AND status != 'Approved'"
    ).fetchone()[0] or 0
    approved = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE status = 'Approved'"
    ).fetchone()[0]
    first_pass = round((approved / total) * 100, 1) if total else 0

    # Claims by status
    status_rows = conn.execute(
        "SELECT status, COUNT(*) as count FROM claims GROUP BY status"
    ).fetchall()
    by_status = [{"name": r["status"], "value": r["count"]} for r in status_rows]

    # Rejection trend (last 6 months, monthly)
    trend = []
    for m in range(5, -1, -1):
        dt = datetime.now() - timedelta(days=m * 30)
        month_str = dt.strftime("%b")
        yr = dt.strftime("%Y")
        lo = (dt - timedelta(days=15)).date().isoformat()
        hi = (dt + timedelta(days=15)).date().isoformat()
        rej = conn.execute(
            "SELECT COUNT(*) FROM claims WHERE status='Rejected' AND claim_date BETWEEN ? AND ?",
            (lo, hi),
        ).fetchone()[0]
        total_m = conn.execute(
            "SELECT COUNT(*) FROM claims WHERE claim_date BETWEEN ? AND ?",
            (lo, hi),
        ).fetchone()[0]
        trend.append({"name": month_str, "rejected": rej, "total": total_m})

    # Top rejection reasons (from risk_factors text)
    reason_counts: dict = {}
    rows = conn.execute(
        "SELECT risk_factors FROM claims WHERE status='Rejected'"
    ).fetchall()
    for row in rows:
        factors = json.loads(row["risk_factors"] or "[]")
        for f in factors:
            key = f.split("—")[0].strip()[:40]
            reason_counts[key] = reason_counts.get(key, 0) + 1
    top_reasons = sorted(
        [{"reason": k, "count": v} for k, v in reason_counts.items()],
        key=lambda x: -x["count"],
    )[:6]

    # High-risk claims
    hr_rows = conn.execute(
        "SELECT id, patient_name, insurance_provider, procedure_category, amount, status, claim_date, risk_score, risk_level "
        "FROM claims WHERE risk_level IN ('High','Critical') ORDER BY risk_score DESC LIMIT 10"
    ).fetchall()
    high_risk = [dict(r) for r in hr_rows]

    conn.close()
    return {
        "total_claims": total,
        "claims_at_risk": at_risk,
        "potential_revenue_leakage": round(leakage, 2),
        "first_pass_acceptance_rate": first_pass,
        "claims_by_status": by_status,
        "rejection_trend": trend,
        "top_rejection_reasons": top_reasons,
        "high_risk_claims": high_risk,
    }


# ─── Bed Allocation endpoints ─────────────────────────────────────────────────

@app.get("/api/beds")
def get_beds():
    conn = get_db()
    rows = conn.execute("SELECT * FROM departments").fetchall()
    conn.close()
    departments = []
    for row in rows:
        d = dict(row)
        d["available"] = d["total_beds"] - d["occupied"]
        d["occupancy_rate"] = round((d["occupied"] / d["total_beds"]) * 100, 1)
        departments.append(d)
    return {"departments": departments}


def _generate_forecast(horizon_hours: int, departments_data: list) -> list:
    """Rule-based forecast: historical admission rate × surge factor × time window."""
    seed_map = {6: 0.15, 12: 0.28, 24: 0.50, 168: 2.1}
    base_surge = seed_map.get(horizon_hours, 0.5)

    result = []
    for d in departments_data:
        # Add randomised realistic demand
        random.seed(d["name"] + str(horizon_hours))
        surge_factor = base_surge * random.uniform(0.8, 1.3)
        expected = math.ceil(d["available"] * surge_factor * random.uniform(0.7, 1.4))
        shortage = max(0, expected - d["available"])
        confidence = round(random.uniform(0.72, 0.94), 2)
        result.append({
            "department": d["name"],
            "available": d["available"],
            "expected_demand": expected,
            "shortage": shortage,
            "confidence": confidence,
        })
    return result


@app.get("/api/beds/forecast")
def bed_forecast(horizon: str = Query("24h")):
    """Predictive bed demand for a given time horizon."""
    horizon_map = {"6h": 6, "12h": 12, "24h": 24, "7d": 168}
    if horizon not in horizon_map:
        raise HTTPException(status_code=400, detail=f"Invalid horizon. Choose from: {list(horizon_map)}")

    conn = get_db()
    rows = conn.execute("SELECT * FROM departments").fetchall()
    conn.close()

    depts_data = []
    for row in rows:
        d = dict(row)
        d["available"] = d["total_beds"] - d["occupied"]
        depts_data.append(d)

    entries = _generate_forecast(horizon_map[horizon], depts_data)
    alerts = [
        f"⚠️  Predicted shortage of {e['shortage']} bed(s) in {e['department']} within {horizon}"
        for e in entries if e["shortage"] > 0
    ]

    return {
        "horizon": horizon,
        "generated_at": datetime.now().isoformat(),
        "entries": entries,
        "alerts": alerts,
    }


@app.get("/api/admissions/forecast")
def admissions_forecast():
    """Multi-horizon admission surge prediction per department."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM departments").fetchall()
    conn.close()

    depts_data = [dict(r) for r in rows]
    for d in depts_data:
        d["available"] = d["total_beds"] - d["occupied"]

    horizons = ["6h", "12h", "24h", "7d"]
    horizon_hours = {"6h": 6, "12h": 12, "24h": 24, "7d": 168}

    data = []
    for dept in depts_data:
        entry = {"department": dept["name"], "current": dept["occupied"]}
        for h in horizons:
            fc = _generate_forecast(horizon_hours[h], [dept])[0]
            entry[h] = fc["expected_demand"]
        data.append(entry)

    return {
        "time_horizons": horizons,
        "departments": [d["name"] for d in depts_data],
        "data": data,
    }


@app.get("/api/dashboard/beds")
def beds_dashboard():
    conn = get_db()
    rows = conn.execute("SELECT * FROM departments").fetchall()
    conn.close()

    depts_data = []
    for row in rows:
        d = dict(row)
        d["available"] = d["total_beds"] - d["occupied"]
        d["occupancy_rate"] = round((d["occupied"] / d["total_beds"]) * 100, 1)
        depts_data.append(d)

    total_beds = sum(d["total_beds"] for d in depts_data)
    occupied = sum(d["occupied"] for d in depts_data)
    available = total_beds - occupied
    occ_rate = round((occupied / total_beds) * 100, 1) if total_beds else 0

    # 24h forecast for predicted shortage
    fc_entries = _generate_forecast(24, depts_data)
    predicted_shortage = sum(e["shortage"] for e in fc_entries)

    # 7-day occupancy trend (simulated)
    trend = []
    for i in range(7, -1, -1):
        dt = datetime.now() - timedelta(days=i)
        random.seed(str(dt.date()))
        occ = round(occupied * random.uniform(0.88, 1.05))
        occ = min(occ, total_beds)
        pred_occ = round(occ * random.uniform(1.0, 1.08))
        trend.append({
            "name": dt.strftime("%a"),
            "current": occ,
            "predicted": min(pred_occ, total_beds),
        })

    return {
        "total_beds": total_beds,
        "occupied": occupied,
        "available": available,
        "predicted_shortage": predicted_shortage,
        "occupancy_rate": occ_rate,
        "departments": depts_data,
        "forecast_summary": fc_entries,
        "occupancy_trend": trend,
    }


# ─── Radiology Endpoints ──────────────────────────────────────────────────────

# In-memory store fallback for radiology demo when DB isn't updated
RADIOLOGY_MOCK_DATA = [
    {
        "id": "CXR-2026-017",
        "patientId": "PT-9821",
        "modality": "CR",
        "bodyPart": "CHEST",
        "studyTime": "08:14:22",
        "studyDate": "2026-08-27",
        "aiFinding": "Possible Pneumothorax",
        "confidenceScore": 94,
        "priority": "CRITICAL",
        "aiStatus": "Completed",
        "modelVersion": "chest-xray-triage-v1",
        "inferenceTimeSeconds": 1.8,
        "probabilities": {"pneumothorax": 94, "pneumonia": 12, "pleuralEffusion": 8, "noUrgentFinding": 4},
        "heatmapRegion": {"x": 72, "y": 35, "radius": 22, "label": "Right Pleural Air Space / Visceral Line"},
        "feedback": {"status": "Unreviewed"},
        "patientAge": 48,
        "patientGender": "M",
        "referringPhysician": "Dr. S. Ramanathan (Emergency Medicine)",
    },
    {
        "id": "CXR-2026-011",
        "patientId": "PT-9043",
        "modality": "CR",
        "bodyPart": "CHEST",
        "studyTime": "08:42:05",
        "studyDate": "2026-08-27",
        "aiFinding": "Possible Pneumonia",
        "confidenceScore": 87,
        "priority": "HIGH",
        "aiStatus": "Completed",
        "modelVersion": "chest-xray-triage-v1",
        "inferenceTimeSeconds": 1.6,
        "probabilities": {"pneumothorax": 5, "pneumonia": 87, "pleuralEffusion": 42, "noUrgentFinding": 9},
        "heatmapRegion": {"x": 32, "y": 58, "radius": 26, "label": "Right Lower Lobe Consolidation"},
        "feedback": {"status": "Agree", "comments": "Concur with AI finding. Right lower lobe opacity consistent with acute consolidation.", "reviewedBy": "Dr. V. Kapoor (Radiology)", "reviewedAt": "2026-08-27 09:15"},
        "patientAge": 62,
        "patientGender": "F",
        "referringPhysician": "Dr. A. Sundaram (Pulmonology)",
    },
    {
        "id": "CXR-2026-009",
        "patientId": "PT-8712",
        "modality": "DX",
        "bodyPart": "CHEST",
        "studyTime": "09:05:18",
        "studyDate": "2026-08-27",
        "aiFinding": "Possible Pleural Effusion",
        "confidenceScore": 82,
        "priority": "HIGH",
        "aiStatus": "Completed",
        "modelVersion": "chest-xray-triage-v1",
        "inferenceTimeSeconds": 1.9,
        "probabilities": {"pneumothorax": 8, "pneumonia": 34, "pleuralEffusion": 82, "noUrgentFinding": 14},
        "heatmapRegion": {"x": 28, "y": 72, "radius": 24, "label": "Left Costophrenic Angle Blunting"},
        "feedback": {"status": "Unreviewed"},
        "patientAge": 55,
        "patientGender": "M",
        "referringPhysician": "Dr. M. Joseph (General Medicine)",
    },
    {
        "id": "CXR-2026-021",
        "patientId": "PT-9988",
        "modality": "CR",
        "bodyPart": "CHEST",
        "studyTime": "10:30:15",
        "studyDate": "2026-08-27",
        "aiFinding": "No Urgent Finding",
        "confidenceScore": 91,
        "priority": "ROUTINE",
        "aiStatus": "Completed",
        "modelVersion": "chest-xray-triage-v1",
        "inferenceTimeSeconds": 1.5,
        "probabilities": {"pneumothorax": 2, "pneumonia": 5, "pleuralEffusion": 3, "noUrgentFinding": 91},
        "feedback": {"status": "Unreviewed"},
        "patientAge": 42,
        "patientGender": "F",
        "referringPhysician": "Dr. P. Nair (Occupational Health)",
    },
]


@app.get("/api/radiology/dashboard")
def get_radiology_dashboard():
    total = len(RADIOLOGY_MOCK_DATA)
    critical = sum(1 for s in RADIOLOGY_MOCK_DATA if s["priority"] == "CRITICAL")
    high = sum(1 for s in RADIOLOGY_MOCK_DATA if s["priority"] == "HIGH")
    routine = sum(1 for s in RADIOLOGY_MOCK_DATA if s["priority"] == "ROUTINE")
    awaiting = sum(1 for s in RADIOLOGY_MOCK_DATA if s["aiStatus"] in ["Processing", "Awaiting Analysis"])
    return {
        "totalStudies": total,
        "critical": critical,
        "high": high,
        "routine": routine,
        "awaitingAnalysis": awaiting,
        "agreementRate": 94,
    }


@app.get("/api/radiology/studies")
def get_radiology_studies(
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    res = list(RADIOLOGY_MOCK_DATA)
    if priority and priority != "All":
        if priority == "Awaiting Analysis":
            res = [s for s in res if s["aiStatus"] in ["Processing", "Awaiting Analysis"]]
        else:
            res = [s for s in res if s["priority"] == priority]
    if search:
        q = search.lower()
        res = [s for s in res if q in s["id"].lower() or q in s["patientId"].lower() or q in s["aiFinding"].lower()]

    rank = {"CRITICAL": 1, "HIGH": 2, "ROUTINE": 3, "PROCESSING": 4}
    res.sort(key=lambda s: (rank.get(s["priority"], 5), s["studyTime"]))
    return res


@app.get("/api/radiology/studies/{study_id}")
def get_radiology_study(study_id: str):
    for s in RADIOLOGY_MOCK_DATA:
        if s["id"].lower() == study_id.lower():
            return s
    raise HTTPException(status_code=404, detail="Study not found")


@app.post("/api/radiology/analyze")
def analyze_radiology_study(payload: dict):
    study_id = payload.get("studyId") or f"CXR-2026-{len(RADIOLOGY_MOCK_DATA)+10:03d}"
    now = datetime.now()
    new_study = {
        "id": study_id,
        "patientId": f"PT-{random.randint(1000, 9999)}",
        "modality": payload.get("modality", "CR"),
        "bodyPart": payload.get("bodyPart", "CHEST"),
        "studyTime": now.strftime("%H:%M:%S"),
        "studyDate": now.strftime("%Y-%m-%d"),
        "aiFinding": "Possible Pneumothorax",
        "confidenceScore": 94,
        "priority": "CRITICAL",
        "aiStatus": "Completed",
        "modelVersion": "chest-xray-triage-v1",
        "inferenceTimeSeconds": 1.8,
        "probabilities": {"pneumothorax": 94, "pneumonia": 12, "pleuralEffusion": 8, "noUrgentFinding": 4},
        "heatmapRegion": {"x": 72, "y": 35, "radius": 22, "label": "Right Pleural Air Space"},
        "feedback": {"status": "Unreviewed"},
        "patientAge": 45,
        "patientGender": "M",
        "referringPhysician": "Dr. S. Ramanathan (Emergency Medicine)",
    }
    RADIOLOGY_MOCK_DATA.insert(0, new_study)
    return new_study


@app.post("/api/radiology/studies/{study_id}/feedback")
def submit_radiology_feedback(study_id: str, payload: dict):
    for s in RADIOLOGY_MOCK_DATA:
        if s["id"].lower() == study_id.lower():
            s["feedback"] = {
                "status": payload.get("status", "Agree"),
                "comments": payload.get("comments"),
                "reviewedBy": "Dr. V. Kapoor (Radiology)",
                "reviewedAt": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            return s
    raise HTTPException(status_code=404, detail="Study not found")


@app.get("/api/radiology/performance")
def get_radiology_performance():
    return [
        {
            "finding": "Pneumothorax",
            "sensitivity": 0.942, "specificity": 0.985, "precision": 0.915, "recall": 0.942,
            "f1Score": 0.928, "auroc": 0.978, "sampleCount": 450, "truePositives": 98,
            "falsePositives": 9, "falseNegatives": 6, "trueNegatives": 337,
        },
        {
            "finding": "Pneumonia / Lung Opacity",
            "sensitivity": 0.895, "specificity": 0.941, "precision": 0.868, "recall": 0.895,
            "f1Score": 0.881, "auroc": 0.952, "sampleCount": 620, "truePositives": 170,
            "falsePositives": 26, "falseNegatives": 20, "trueNegatives": 404,
        },
        {
            "finding": "Pleural Effusion",
            "sensitivity": 0.918, "specificity": 0.963, "precision": 0.892, "recall": 0.918,
            "f1Score": 0.905, "auroc": 0.966, "sampleCount": 510, "truePositives": 124,
            "falsePositives": 15, "falseNegatives": 11, "trueNegatives": 360,
        },
    ]


@app.get("/health")
def health():
    return {"status": "ok", "service": "Meridian AI RCM, Bed Allocation & Radiology API"}


# ─── Appointment Service Endpoints ──────────────────────────────────────────

class BookAppointmentRequest(BaseModel):
    patient_id: int
    doctor_id: int
    department_id: int
    appointment_date: str
    appointment_time: str
    patient_reason: Optional[str] = None
    booking_source: Optional[str] = "ADMIN"
    created_by_user_id: Optional[int] = None

class CancelAppointmentRequest(BaseModel):
    reason: str
    cancelled_by_user_id: Optional[int] = None

class RescheduleAppointmentRequest(BaseModel):
    new_date: str
    new_time: str
    reason: str
    rescheduled_by_user_id: Optional[int] = None


@app.get("/api/doctors/{doctor_id}/availability")
def api_get_doctor_availability(doctor_id: int, date: str = Query(..., description="Date in YYYY-MM-DD format")):
    import appointment_service
    res = appointment_service.get_doctor_availability(doctor_id, date)
    return res


@app.get("/api/doctors/{doctor_id}/slots")
def api_get_available_slots(doctor_id: int, date: str = Query(..., description="Date in YYYY-MM-DD format")):
    import appointment_service
    slots = appointment_service.get_available_slots(doctor_id, date)
    return slots


@app.post("/api/appointments", status_code=201)
def api_book_appointment(payload: BookAppointmentRequest):
    import appointment_service
    res = appointment_service.book_appointment(
        patient_id=payload.patient_id,
        doctor_id=payload.doctor_id,
        department_id=payload.department_id,
        date_str=payload.appointment_date,
        time_str=payload.appointment_time,
        patient_reason=payload.patient_reason,
        booking_source=payload.booking_source,
        created_by_user_id=payload.created_by_user_id
    )
    return res


@app.get("/api/appointments/{booking_id}")
def api_get_appointment(booking_id: str, patient_id: Optional[int] = Query(None)):
    import appointment_service
    res = appointment_service.get_appointment(booking_id, patient_id)
    return res


@app.get("/api/patients/{patient_id}/appointments")
def api_get_patient_appointments(patient_id: int):
    import appointment_service
    res = appointment_service.get_patient_appointments(patient_id)
    return res


@app.post("/api/appointments/{booking_id}/cancel")
def api_cancel_appointment(booking_id: str, payload: CancelAppointmentRequest):
    import appointment_service
    res = appointment_service.cancel_appointment(
        booking_id=booking_id,
        reason=payload.reason,
        cancelled_by_user_id=payload.cancelled_by_user_id
    )
    return res


@app.post("/api/appointments/{booking_id}/reschedule")
def api_reschedule_appointment(booking_id: str, payload: RescheduleAppointmentRequest):
    import appointment_service
    res = appointment_service.reschedule_appointment(
        booking_id=booking_id,
        new_date_str=payload.new_date,
        new_time_str=payload.new_time,
        reason=payload.reason,
        rescheduled_by_user_id=payload.rescheduled_by_user_id
    )
    return res

