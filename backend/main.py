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


@app.get("/health")
def health():
    return {"status": "ok", "service": "Meridian AI RCM & Bed Allocation API"}
