"""
seed_knowledge.py
=================
Idempotent seed script for Meridian Hospital knowledge base.

- Reads actual departments and doctors from PostgreSQL
- Seeds 13 knowledge documents (one per category)
- Seeds corresponding knowledge chunks
- Uses ON CONFLICT DO UPDATE — safe to re-run multiple times
- All content is marked as POC SAMPLE INFORMATION in the source field

Run:
    python knowledge/seed_knowledge.py

Step 5.1 — Meridian Hospital POC
"""

import sys
import os
import json
import datetime

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config


def get_departments(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT id, department_name, description FROM departments ORDER BY id;")
    rows = cur.fetchall()
    cur.close()
    return [{"id": r[0], "name": r[1], "description": r[2]} for r in rows]


def get_doctors(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT d.id, d.display_name, d.specialization, d.qualification, d.experience_years,
               d.status, dept.department_name
        FROM doctors d
        JOIN departments dept ON d.department_id = dept.id
        WHERE d.status = 'ACTIVE'
        ORDER BY d.id;
    """)
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "id": r[0], "name": r[1], "specialization": r[2],
            "qualification": r[3], "experience": r[4],
            "status": r[5], "department": r[6]
        }
        for r in rows
    ]


def get_schedules(conn) -> list[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT d.display_name, dept.department_name, ds.day_of_week,
               ds.start_time, ds.end_time, ds.slot_duration_minutes
        FROM doctor_schedules ds
        JOIN doctors d ON ds.doctor_id = d.id
        JOIN departments dept ON d.department_id = dept.id
        ORDER BY d.id, ds.day_of_week;
    """)
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "doctor": r[0], "department": r[1], "day": r[2],
            "start": str(r[3])[:5], "end": str(r[4])[:5], "slot_mins": r[5]
        }
        for r in rows
    ]


def upsert_document(cur, doc_code, title, doc_type, content, source="MERIDIAN_HOSPITAL_POC") -> int:
    """Insert or update a knowledge document. Returns the document id."""
    cur.execute("""
        INSERT INTO knowledge_documents (document_code, title, document_type, content, source, language, version, status)
        VALUES (%s, %s, %s, %s, %s, 'ENGLISH', '1.0', 'ACTIVE')
        ON CONFLICT (document_code) DO UPDATE
            SET title = EXCLUDED.title,
                content = EXCLUDED.content,
                source = EXCLUDED.source,
                status = 'ACTIVE',
                updated_at = CURRENT_TIMESTAMP
        RETURNING id;
    """, (doc_code, title, doc_type, content, source))
    row = cur.fetchone()
    return row[0]


def upsert_chunk(cur, document_id, chunk_number, content, metadata=None):
    """Insert or replace a knowledge chunk (delete+insert for idempotency)."""
    # Delete existing chunk at this position for this document
    cur.execute(
        "DELETE FROM knowledge_chunks WHERE document_id = %s AND chunk_number = %s;",
        (document_id, chunk_number)
    )
    token_count = len(content.split())
    cur.execute("""
        INSERT INTO knowledge_chunks (document_id, chunk_number, content, token_count, metadata)
        VALUES (%s, %s, %s, %s, %s);
    """, (document_id, chunk_number, content, token_count, json.dumps(metadata or {})))


def build_knowledge_documents(departments, doctors, schedules) -> list[dict]:
    """Build the full list of knowledge documents and their chunks from live DB data."""

    dept_list = "\n".join([f"  • {d['name']}: {d['description']}" for d in departments])
    dept_names = ", ".join([d["name"] for d in departments])

    doctor_list_parts = []
    for doc in doctors:
        doctor_list_parts.append(
            f"  • {doc['name']} ({doc['department']})\n"
            f"    Specialization: {doc['specialization']}\n"
            f"    Qualification: {doc['qualification']}\n"
            f"    Experience: {doc['experience']} years"
        )
    doctor_list = "\n".join(doctor_list_parts)

    schedule_parts = []
    for s in schedules:
        schedule_parts.append(
            f"  • {s['doctor']} ({s['department']}): {s['day']} "
            f"{s['start']} – {s['end']} (slots every {s['slot_mins']} minutes)"
        )
    schedule_list = "\n".join(schedule_parts)

    return [
        # ─── 1. HOSPITAL OVERVIEW ──────────────────────────────────────────────
        {
            "code": "KD_HOSPITAL_OVERVIEW",
            "title": "Meridian Hospital Overview",
            "type": "HOSPITAL_PROFILE",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "Meridian Hospital is a multispecialty hospital operated by Walfs India Private Limited. "
                        "It provides comprehensive outpatient (OPD) and inpatient care across multiple medical specialties. "
                        "The hospital is committed to delivering compassionate, technology-enabled healthcare services. "
                        "Meridian Hospital's AI Patient Desk helps patients with appointment scheduling, doctor availability, "
                        "hospital information, and pre-admission assistance through WhatsApp and voice interfaces.\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "HOSPITAL_OVERVIEW", "language": "ENGLISH"}
                }
            ]
        },

        # ─── 2. DEPARTMENTS ────────────────────────────────────────────────────
        {
            "code": "KD_DEPARTMENTS",
            "title": "Meridian Hospital Departments",
            "type": "DEPARTMENT",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        f"Meridian Hospital provides specialized medical care across the following departments:\n\n"
                        f"{dept_list}\n\n"
                        f"Patients can ask the AI Patient Desk to help identify the right department based on their "
                        f"symptoms or medical needs, and to book an OPD appointment directly.\n\n"
                        f"[POC SAMPLE INFORMATION — departments read from live database]"
                    ),
                    "meta": {"category": "DEPARTMENTS", "departments": [d["name"] for d in departments]}
                }
            ]
        },

        # ─── 3. DOCTORS ────────────────────────────────────────────────────────
        {
            "code": "KD_DOCTORS",
            "title": "Meridian Hospital Doctors",
            "type": "DOCTOR_INFORMATION",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        f"Meridian Hospital has the following active doctors available for OPD consultations:\n\n"
                        f"{doctor_list}\n\n"
                        f"To book an appointment with any of these doctors, simply tell the AI Patient Desk "
                        f"which doctor or department you need and your preferred date.\n\n"
                        f"[POC SAMPLE INFORMATION — doctors read from live database]"
                    ),
                    "meta": {"category": "DOCTORS", "doctor_count": len(doctors)}
                }
            ]
        },

        # ─── 4. OPD TIMINGS ────────────────────────────────────────────────────
        {
            "code": "KD_OPD_TIMINGS",
            "title": "Meridian Hospital OPD Timings",
            "type": "OPD_TIMING",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        f"Meridian Hospital OPD (Outpatient Department) consultation schedules:\n\n"
                        f"{schedule_list}\n\n"
                        f"Appointment slots are available every 30 minutes during scheduled hours. "
                        f"The AI Patient Desk shows live availability and can book a slot instantly.\n\n"
                        f"[POC SAMPLE INFORMATION — schedules read from live database]"
                    ),
                    "meta": {"category": "OPD_TIMINGS"}
                },
                {
                    "number": 2,
                    "content": (
                        "General OPD Guidelines:\n"
                        "• Please arrive 10–15 minutes before your appointment time.\n"
                        "• Bring a valid ID (Aadhaar card, PAN card, or passport).\n"
                        "• Emergency services are available 24 hours a day, 7 days a week.\n"
                        "• OPD consultations operate on a prior appointment basis.\n"
                        "• Walk-in patients may be accommodated subject to availability.\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "OPD_TIMINGS", "type": "guidelines"}
                }
            ]
        },

        # ─── 5. APPOINTMENT INFORMATION ────────────────────────────────────────
        {
            "code": "KD_APPOINTMENT_INFO",
            "title": "Meridian Hospital Appointment Information",
            "type": "APPOINTMENT_POLICY",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "How to book an appointment at Meridian Hospital:\n"
                        "• Through the AI Patient Desk (WhatsApp or voice)\n"
                        "• Tell the AI your preferred doctor or department and date\n"
                        "• The AI will show available time slots and confirm your booking\n"
                        "• You will receive a booking confirmation with your appointment ID\n\n"
                        "Cancellation Policy:\n"
                        "• Appointments can be cancelled at any time before the scheduled time\n"
                        "• Provide a reason for cancellation when prompted\n"
                        "• Cancelled slots are immediately made available to other patients\n\n"
                        "Rescheduling Policy:\n"
                        "• Appointments can be rescheduled to any available slot\n"
                        "• Provide your appointment ID and your preferred new date and time\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "APPOINTMENT_INFORMATION"}
                }
            ]
        },

        # ─── 6. HOSPITAL FACILITIES ────────────────────────────────────────────
        {
            "code": "KD_FACILITIES",
            "title": "Meridian Hospital Facilities",
            "type": "HOSPITAL_SERVICE",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "Meridian Hospital facilities and services include:\n\n"
                        "• OPD Consultation Rooms — Dedicated consultation rooms for each specialty\n"
                        "• Diagnostic Laboratory — Full-service pathology and blood work\n"
                        "• Radiology & Imaging — X-ray, ultrasound, and ECG services\n"
                        "• In-patient Wards — General and specialized wards with nursing care\n"
                        "• Emergency Department — 24/7 emergency care and stabilization\n"
                        "• Pharmacy — On-premise pharmacy with prescription fulfillment\n"
                        "• Ambulance Service — Emergency ambulance dispatch\n"
                        "• Patient Waiting Lounge — Air-conditioned waiting area with seating\n"
                        "• Wheelchair Access — Facilities are accessible to differently-abled patients\n"
                        "• Cafeteria — Light refreshments available for patients and visitors\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "HOSPITAL_FACILITIES"}
                }
            ]
        },

        # ─── 7. CONTACT INFORMATION ────────────────────────────────────────────
        {
            "code": "KD_CONTACT",
            "title": "Meridian Hospital Contact Information",
            "type": "HOSPITAL_PROFILE",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "Meridian Hospital Contact Information:\n\n"
                        "• General Enquiries: +91 99999 99999\n"
                        "• Emergency Helpline: +91 99999 00000 (24/7)\n"
                        "• Appointment Desk: +91 99999 11111\n"
                        "• Email: care@meridianhospital.in\n"
                        "• Website: www.meridianhospital.in (POC placeholder)\n"
                        "• WhatsApp AI Patient Desk: Available 24/7 for appointment booking "
                        "and hospital information\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "CONTACT_INFORMATION"}
                }
            ]
        },

        # ─── 8. LOCATION ───────────────────────────────────────────────────────
        {
            "code": "KD_LOCATION",
            "title": "Meridian Hospital Location and Directions",
            "type": "HOSPITAL_PROFILE",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "Meridian Hospital Location:\n\n"
                        "Address: 123 Healthcare Lane, Sector 4, Walfs India — 500001\n"
                        "Operated by: Walfs India Private Limited\n\n"
                        "How to reach Meridian Hospital:\n"
                        "• By Road: Accessible via Healthcare Lane off the main Sector 4 highway\n"
                        "• By Public Transport: Bus stops and auto-rickshaw stands are within 200 metres\n"
                        "• Parking: Free patient parking is available on the hospital premises\n"
                        "• Google Maps: Search for 'Meridian Hospital Walfs India' for directions\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "LOCATION"}
                }
            ]
        },

        # ─── 9. EMERGENCY INFORMATION ──────────────────────────────────────────
        {
            "code": "KD_EMERGENCY",
            "title": "Meridian Hospital Emergency Services",
            "type": "EMERGENCY",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "Emergency services at Meridian Hospital are available 24 hours a day, "
                        "7 days a week, 365 days a year.\n\n"
                        "Emergency contact: +91 99999 00000\n\n"
                        "For life-threatening emergencies such as chest pain, severe breathing difficulty, "
                        "stroke, major trauma, or loss of consciousness — please call emergency services "
                        "(112 or 108) immediately or proceed to the nearest emergency department without delay.\n\n"
                        "The Meridian Hospital Emergency Department provides:\n"
                        "• 24/7 emergency triage and stabilization\n"
                        "• Emergency surgery support\n"
                        "• Critical care monitoring\n"
                        "• Ambulance dispatch coordination\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "EMERGENCY_INFORMATION"}
                }
            ]
        },

        # ─── 10. PRE-ADMISSION ─────────────────────────────────────────────────
        {
            "code": "KD_PRE_ADMISSION",
            "title": "Meridian Hospital Pre-Admission Process",
            "type": "PRE_ADMISSION",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "Pre-Admission at Meridian Hospital:\n\n"
                        "For planned procedures and surgeries, Meridian Hospital offers a pre-admission "
                        "process to help patients prepare in advance.\n\n"
                        "Pre-Admission Steps:\n"
                        "1. Receive a referral or surgical recommendation from your doctor\n"
                        "2. Contact the hospital to schedule your pre-admission appointment\n"
                        "3. Complete pre-operative tests (blood work, ECG, imaging as required)\n"
                        "4. Meet with the care team to discuss your treatment plan\n"
                        "5. Complete consent and documentation forms\n"
                        "6. Receive admission instructions including fasting requirements\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "PRE_ADMISSION"}
                }
            ]
        },

        # ─── 11. ADMISSION DOCUMENTS ───────────────────────────────────────────
        {
            "code": "KD_ADMISSION_DOCS",
            "title": "Documents Required for Hospital Admission",
            "type": "ADMISSION",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "Documents required for admission at Meridian Hospital:\n\n"
                        "For OPD Appointments:\n"
                        "• Valid government-issued photo ID (Aadhaar card, PAN card, or passport)\n"
                        "• Previous medical records or prescriptions (if applicable)\n"
                        "• Insurance card or cashless authorization letter (if using health insurance)\n\n"
                        "For In-patient Admission:\n"
                        "• Valid government-issued photo ID (original + photocopy)\n"
                        "• Doctor's referral letter or surgical recommendation\n"
                        "• Previous diagnostic reports and prescriptions\n"
                        "• Health insurance card and pre-authorization (for insurance patients)\n"
                        "• Emergency contact details (name, relationship, phone number)\n"
                        "• Advance payment or insurance pre-authorization as required\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "ADMISSION_DOCUMENTS"}
                }
            ]
        },

        # ─── 12. PATIENT INSTRUCTIONS ──────────────────────────────────────────
        {
            "code": "KD_PATIENT_INSTRUCTIONS",
            "title": "Patient Instructions — What to Bring for Your Appointment",
            "type": "HOSPITAL_SERVICE",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "What to bring for your OPD appointment at Meridian Hospital:\n\n"
                        "• Valid photo ID (Aadhaar, PAN card, or passport)\n"
                        "• Your appointment confirmation ID (e.g., APT12345)\n"
                        "• Previous medical records, lab reports, or X-rays related to your condition\n"
                        "• A list of current medications you are taking\n"
                        "• Health insurance card (if applicable)\n"
                        "• A responsible adult companion if you expect a procedure\n\n"
                        "Tips for your visit:\n"
                        "• Arrive 10–15 minutes before your scheduled appointment time\n"
                        "• Wear comfortable clothing\n"
                        "• Inform the desk about any known allergies or medical conditions\n"
                        "• Carry sufficient cash or a payment card for consultation fees\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "PATIENT_INSTRUCTIONS"}
                }
            ]
        },

        # ─── 13. FAQ ───────────────────────────────────────────────────────────
        {
            "code": "KD_FAQ",
            "title": "Meridian Hospital Frequently Asked Questions",
            "type": "FAQ",
            "chunks": [
                {
                    "number": 1,
                    "content": (
                        "Frequently Asked Questions — Meridian Hospital\n\n"
                        "Q: Can I book an appointment through WhatsApp?\n"
                        "A: Yes! The AI Patient Desk on WhatsApp can book, cancel, or reschedule "
                        "OPD appointments 24/7.\n\n"
                        "Q: What departments does Meridian Hospital have?\n"
                        f"A: Meridian Hospital has departments in: {dept_names}.\n\n"
                        "Q: Is emergency care available at night?\n"
                        "A: Yes, the Emergency Department is open 24 hours a day, 7 days a week.\n\n"
                        "Q: Can I reschedule my appointment?\n"
                        "A: Yes, you can reschedule by telling the AI Patient Desk your appointment ID "
                        "and your preferred new date and time.\n\n"
                        "Q: How do I know if my appointment is confirmed?\n"
                        "A: You will receive a booking confirmation message with your appointment ID "
                        "immediately after booking.\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "FAQ"}
                },
                {
                    "number": 2,
                    "content": (
                        "Frequently Asked Questions (continued) — Meridian Hospital\n\n"
                        "Q: Does Meridian Hospital accept health insurance?\n"
                        "A: Meridian Hospital works with major health insurance providers. "
                        "Please bring your insurance card for verification at the time of visit.\n\n"
                        "Q: Is there a pharmacy in the hospital?\n"
                        "A: Yes, an on-premise pharmacy is available for prescription fulfillment.\n\n"
                        "Q: Are the doctors available every day?\n"
                        "A: OPD schedules vary by doctor. The AI Patient Desk can check real-time "
                        "availability for any doctor on any date.\n\n"
                        "Q: What should I do in a medical emergency?\n"
                        "A: For life-threatening emergencies, call 112 or 108 immediately, or proceed "
                        "directly to the Emergency Department. Do not wait for an appointment.\n\n"
                        "[POC SAMPLE INFORMATION]"
                    ),
                    "meta": {"category": "FAQ"}
                }
            ]
        },
    ]


def run_seed():
    conn = db_config.get_db_connection()
    cur = conn.cursor()

    try:
        print("Reading live database data...")
        departments = get_departments(conn)
        doctors = get_doctors(conn)
        schedules = get_schedules(conn)

        print(f"  Departments found: {len(departments)}")
        print(f"  Active doctors found: {len(doctors)}")
        print(f"  Schedule entries found: {len(schedules)}")

        documents = build_knowledge_documents(departments, doctors, schedules)

        print(f"\nSeeding {len(documents)} knowledge documents...")
        total_chunks = 0

        for doc in documents:
            doc_id = upsert_document(
                cur,
                doc_code=doc["code"],
                title=doc["title"],
                doc_type=doc["type"],
                content=doc["chunks"][0]["content"],  # Main content on document
            )
            print(f"  [OK] {doc['code']} -> id={doc_id}")

            for chunk in doc["chunks"]:
                upsert_chunk(
                    cur,
                    document_id=doc_id,
                    chunk_number=chunk["number"],
                    content=chunk["content"],
                    metadata=chunk.get("meta", {})
                )
                total_chunks += 1

        conn.commit()
        print(f"\nSeed complete: {len(documents)} documents, {total_chunks} chunks loaded.")

        # Verify
        cur.execute("SELECT COUNT(*) FROM knowledge_documents WHERE status = 'ACTIVE';")
        doc_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM knowledge_chunks;")
        chunk_count = cur.fetchone()[0]
        print(f"\nDatabase state:")
        print(f"  Active knowledge_documents: {doc_count}")
        print(f"  knowledge_chunks: {chunk_count}")

    except Exception as e:
        conn.rollback()
        print(f"Seed failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    run_seed()
