"""
Synthetic data seed script for the AI RCM & Bed Allocation POC.
Run once: python seed_data.py
Generates hospital.db with realistic synthetic claims and bed data.
"""
import sqlite3
import random
import json
from datetime import datetime, timedelta

DB_PATH = "hospital.db"

INSURANCE_PROVIDERS = [
    "Star Health", "HDFC ERGO", "Bajaj Allianz", "ICICI Lombard",
    "New India Assurance", "United India Insurance"
]

PROCEDURE_CATEGORIES = [
    "Cardiology", "Orthopaedics", "General Surgery", "Neurology",
    "Oncology", "Paediatrics", "Nephrology", "Gastroenterology"
]

PROCEDURE_AMOUNTS = {
    "Cardiology": (45000, 250000),
    "Orthopaedics": (30000, 180000),
    "General Surgery": (20000, 90000),
    "Neurology": (50000, 300000),
    "Oncology": (80000, 500000),
    "Paediatrics": (10000, 60000),
    "Nephrology": (60000, 400000),
    "Gastroenterology": (25000, 120000),
}

PATIENT_NAMES = [
    "Arun Kumar", "Priya Ramesh", "Karthik Selvam", "Meena Krishnan",
    "Suresh Babu", "Lakshmi Devi", "Rajan Pillai", "Anitha Nair",
    "Balasubramanian R", "Kavitha Sundaram", "Dinesh Chandra", "Usha Iyer",
    "Mohan Raj", "Saranya Venkat", "Vijay Shankar", "Deepa Murugan",
    "Santhosh Kumar", "Rekha Krishnaswamy", "Prasad Narayanan", "Geetha Raman",
    "Chandrasekhar M", "Nalini Gopalakrishnan", "Ramesh Babu", "Vasantha Kumari",
    "Senthil Kumar", "Parvathi Devi", "Jayakumar N", "Sumathi Raghunathan",
    "Venkatesh S", "Bhavani Subramaniam", "Ashok Kumar", "Radha Krishnan",
    "Muthuvel P", "Saraswathi R", "Sundaram K", "Kamala Devi",
    "Palaniswami G", "Valarmathi M", "Ezhumalai T", "Ponmalar S",
]

DEPARTMENTS = {
    "ICU":           {"total_beds": 20, "current_occupied": 17},
    "General Ward":  {"total_beds": 80, "current_occupied": 58},
    "Paediatric":    {"total_beds": 30, "current_occupied": 22},
    "Surgical":      {"total_beds": 40, "current_occupied": 31},
}


def compute_risk(claim: dict, avg_amounts: dict) -> tuple[int, str, list[str], str]:
    """Rule-based risk scoring. Returns (score, level, factors, recommended_action)."""
    score = 0
    factors = []

    # Flag 1: missing discharge summary
    if not claim["discharge_summary"]:
        score += 30
        factors.append("Missing discharge summary — mandatory document not uploaded")

    # Flag 2: missing authorization number
    if not claim["authorization_number"]:
        score += 25
        factors.append("No prior authorization number — insurance pre-approval not recorded")

    # Flag 3: unusual billing amount (> 2× category average)
    cat = claim["procedure_category"]
    avg = avg_amounts.get(cat, 1)
    if claim["amount"] > 2 * avg:
        score += 20
        pct = int((claim["amount"] / avg - 1) * 100)
        factors.append(f"Unusual billing amount — {pct}% above category average for {cat}")

    # Flag 4: high-value claim (> ₹2 lakh) adds base risk
    if claim["amount"] > 200000:
        score += 10
        factors.append("High-value claim (>₹2L) — requires enhanced scrutiny")

    # Flag 5: rejected status
    if claim["status"] == "Rejected":
        score += 15
        factors.append("Claim previously rejected — re-submission needs documentation review")

    # Flag 6: no discharge date
    if not claim["discharge_date"]:
        score += 5
        factors.append("Discharge date missing — admission record may be incomplete")

    score = min(score, 100)

    if score <= 30:
        level = "Low"
    elif score <= 60:
        level = "Medium"
    elif score <= 80:
        level = "High"
    else:
        level = "Critical"

    # Recommended action
    if score >= 81:
        action = "Immediately escalate to billing manager and legal team. Suspend claim until all issues are resolved."
    elif score >= 61:
        action = "Hold for senior billing executive review. Upload all missing documents before resubmission."
    elif score >= 31:
        action = "Flag for billing executive review. Verify insurance eligibility and upload missing documents."
    else:
        action = "Proceed with standard claim processing. Routine spot-check recommended."

    return score, level, factors, action


def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Claims table ─────────────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS claims")
    c.execute("""
        CREATE TABLE claims (
            id TEXT PRIMARY KEY,
            patient_name TEXT,
            patient_id TEXT,
            insurance_provider TEXT,
            procedure_category TEXT,
            amount REAL,
            status TEXT,
            claim_date TEXT,
            discharge_date TEXT,
            authorization_number TEXT,
            discharge_summary INTEGER,
            risk_score INTEGER,
            risk_level TEXT,
            risk_factors TEXT,
            recommended_action TEXT,
            reviewed INTEGER DEFAULT 0
        )
    """)

    # Compute category averages (midpoints of ranges)
    avg_amounts = {cat: (lo + hi) / 2 for cat, (lo, hi) in PROCEDURE_AMOUNTS.items()}

    claims = []
    used_keys = set()  # for duplicate detection

    # Generate ~260 claims over the last 6 months
    base_date = datetime.now()
    statuses = ["Approved", "Rejected", "Pending", "Under Review"]
    status_weights = [0.50, 0.15, 0.25, 0.10]

    for i in range(260):
        cat = random.choice(PROCEDURE_CATEGORIES)
        lo, hi = PROCEDURE_AMOUNTS[cat]
        provider = random.choice(INSURANCE_PROVIDERS)
        days_ago = random.randint(0, 180)
        claim_dt = base_date - timedelta(days=days_ago)
        discharge_dt = claim_dt + timedelta(days=random.randint(2, 14))

        patient_name = random.choice(PATIENT_NAMES)
        patient_id = f"P{random.randint(10000, 99999)}"
        claim_id = f"CLM{1000 + i:04d}"

        # Normal amount
        amount = round(random.uniform(lo, hi), 2)

        status = random.choices(statuses, weights=status_weights)[0]
        auth_num = f"AUTH{random.randint(100000, 999999)}" if random.random() > 0.12 else None
        has_discharge = random.random() > 0.10
        has_discharge_date = random.random() > 0.05

        # Seed intentional issues in ~120 claims
        seeded_issue = False
        if i < 30:
            # Group A: missing discharge summary
            has_discharge = False
            seeded_issue = True
        elif i < 50:
            # Group B: missing authorization
            auth_num = None
            seeded_issue = True
        elif i < 75:
            # Group C: unusual billing amount (3× average)
            amount = round(avg_amounts[cat] * random.uniform(2.1, 3.5), 2)
            seeded_issue = True
        elif i < 95:
            # Group D: both missing docs
            has_discharge = False
            auth_num = None
            seeded_issue = True
        elif i < 120:
            # Group E: duplicates — reuse an earlier claim's key tuple
            if used_keys and i % 5 == 0:
                earlier = claims[random.randint(0, len(claims) - 1)]
                patient_name = earlier["patient_name"]
                patient_id = earlier["patient_id"]
                claim_dt = datetime.fromisoformat(earlier["claim_date"])
                amount = earlier["amount"]
            seeded_issue = True

        dup_key = (patient_id, claim_dt.date().isoformat(), round(amount, -2))
        is_duplicate = dup_key in used_keys and i >= 95
        if is_duplicate:
            # patch factors later in compute_risk — mark via a special flag
            pass
        used_keys.add(dup_key)

        claim = {
            "id": claim_id,
            "patient_name": patient_name,
            "patient_id": patient_id,
            "insurance_provider": provider,
            "procedure_category": cat,
            "amount": amount,
            "status": status,
            "claim_date": claim_dt.date().isoformat(),
            "discharge_date": discharge_dt.date().isoformat() if has_discharge_date else None,
            "authorization_number": auth_num,
            "discharge_summary": has_discharge,
        }

        score, level, factors, action = compute_risk(claim, avg_amounts)

        # Inject duplicate flag
        if is_duplicate:
            factors.append("Potential duplicate — same patient, date, and amount as an earlier claim")
            score = min(score + 20, 100)
            if score <= 30:
                level = "Low"
            elif score <= 60:
                level = "Medium"
            elif score <= 80:
                level = "High"
            else:
                level = "Critical"

        claim.update({
            "risk_score": score,
            "risk_level": level,
            "risk_factors": json.dumps(factors),
            "recommended_action": action,
        })
        claims.append(claim)

    c.executemany("""
        INSERT INTO claims VALUES (
            :id, :patient_name, :patient_id, :insurance_provider, :procedure_category,
            :amount, :status, :claim_date, :discharge_date, :authorization_number,
            :discharge_summary, :risk_score, :risk_level, :risk_factors, :recommended_action, 0
        )
    """, claims)

    # ── Beds table ────────────────────────────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS departments")
    c.execute("""
        CREATE TABLE departments (
            name TEXT PRIMARY KEY,
            total_beds INTEGER,
            occupied INTEGER
        )
    """)
    c.executemany("INSERT INTO departments VALUES (?, ?, ?)", [
        (name, d["total_beds"], d["current_occupied"])
        for name, d in DEPARTMENTS.items()
    ])

    # ── Admissions log (30-day history) ──────────────────────────────────────
    c.execute("DROP TABLE IF EXISTS admissions")
    c.execute("""
        CREATE TABLE admissions (
            id TEXT PRIMARY KEY,
            department TEXT,
            admitted_date TEXT,
            discharged_date TEXT,
            patient_name TEXT
        )
    """)

    admissions = []
    for i in range(400):
        dept = random.choice(list(DEPARTMENTS.keys()))
        admit_dt = base_date - timedelta(days=random.randint(0, 30))
        stay_days = random.randint(2, 12)
        discharge_dt = admit_dt + timedelta(days=stay_days)
        discharged = discharge_dt.date().isoformat() if discharge_dt < base_date else None
        admissions.append((
            f"ADM{i:04d}",
            dept,
            admit_dt.date().isoformat(),
            discharged,
            random.choice(PATIENT_NAMES),
        ))

    c.executemany("INSERT INTO admissions VALUES (?, ?, ?, ?, ?)", admissions)

    conn.commit()
    conn.close()

    total_claims = len(claims)
    at_risk = sum(1 for cl in claims if cl["risk_level"] in ("High", "Critical"))
    print(f"✅  Seeded {total_claims} claims — {at_risk} high/critical risk")
    print(f"✅  Seeded {len(DEPARTMENTS)} departments with bed data")
    print(f"✅  Seeded {len(admissions)} admission records (30-day history)")
    print(f"📁  Database: {DB_PATH}")


if __name__ == "__main__":
    seed()
