import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db_config

def seed_reports():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Get patient IDs
        cur.execute("SELECT id, patient_code FROM patients;")
        rows = cur.fetchall()
        p_map = {row[1]: row[0] for row in rows if row[1]}
        
        p1 = p_map.get("P100001") or p_map.get("P001") or 1
        p2 = p_map.get("P100002") or p_map.get("P002") or 2
        p5 = p_map.get("P100005") or p_map.get("P005") or 5

        cur.execute("SELECT id FROM doctors ORDER BY id;")
        doc_rows = cur.fetchall()
        doc_ids = [r[0] for r in doc_rows] if doc_rows else [None]
        d1 = doc_ids[0] if doc_ids else None
        d2 = doc_ids[1] if len(doc_ids) > 1 else d1
        d3 = doc_ids[2] if len(doc_ids) > 2 else d1

        cur.execute("SELECT id FROM departments ORDER BY id;")
        dept_rows = cur.fetchall()
        dept_ids = [r[0] for r in dept_rows] if dept_rows else [None]
        dp1 = dept_ids[0] if dept_ids else None
        dp2 = dept_ids[1] if len(dept_ids) > 1 else dp1
        dp3 = dept_ids[2] if len(dept_ids) > 2 else dp1

        reports_data = [
            ("REP10001", p1, "Lab Test", "Blood Test (Complete Blood Count)", "2026-09-10", d1, dp1, "Available", "Hb: 14.2 g/dL, WBC: 7,500/mcL, Platelets: 250,000/mcL. All parameters within normal ranges."),
            ("REP10002", p1, "Cardiology", "ECG Report", "2026-09-08", d2, dp2, "Available", "Normal Sinus Rhythm. Heart rate 72 bpm. PR interval and QT duration within normal limits."),
            ("REP10003", p1, "Radiology", "CT Scan (Chest)", "2026-09-02", d3, dp3, "Available", "Clear lung fields bilaterally. No focal opacity, pleural effusion, or pneumothorax identified."),
            ("REP10004", p2, "Lab Test", "Lipid Profile Test", "2026-09-11", d1, dp1, "Available", "Total Cholesterol: 185 mg/dL, HDL: 48 mg/dL, LDL: 110 mg/dL, Triglycerides: 135 mg/dL."),
            ("REP10005", p5, "Pediatrics", "Pediatric Blood Panel", "2026-09-05", d1, dp1, "Available", "Pediatric Growth & CBC: Normal iron levels, Hemoglobin 12.5 g/dL, Immunizations up-to-date.")
        ]

        for ref, p_id, r_type, r_title, r_date, doc_id, dept_id, stat, summary in reports_data:
            cur.execute("""
                INSERT INTO patient_reports (report_reference, patient_id, report_type, report_title, report_date, doctor_id, department_id, status, summary)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (report_reference) DO NOTHING;
            """, (ref, p_id, r_type, r_title, r_date, doc_id, dept_id, stat, summary))

        conn.commit()
        print("[SEED_REPORTS] Patient reports seeded successfully.")
    except Exception as e:
        print(f"[SEED_REPORTS] Error seeding reports: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    seed_reports()
