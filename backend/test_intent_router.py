"""
test_intent_router.py
=====================
Comprehensive Test Suite for Patient Intent Router Agent (backend/agent/intent_router.py).

Verifies:
  1. All 25 required scenario test cases (symptoms, intents, dates, DOB, multilingual, emergency).
  2. Doctor Department Isolation Guard against PostgreSQL database.
"""

import sys
import os
import pytest
import datetime

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.intent_router as intent_router


def test_1_fever_routing():
    res = intent_router.route_patient_message("I have fever")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["department"] == "General Medicine"
    assert res["emergency"] is False


def test_2_hair_fall_routing():
    res = intent_router.route_patient_message("I have hair fall")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["department"] == "Dermatology"


def test_3_skin_itching_routing():
    res = intent_router.route_patient_message("My skin is itching")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["department"] == "Dermatology"


def test_4_chest_pain_emergency():
    res = intent_router.route_patient_message("I have chest pain")
    assert res["intent"] == "EMERGENCY"
    assert res["emergency"] is True
    assert res["department"] == "EMERGENCY"


def test_5_want_appointment():
    res = intent_router.route_patient_message("I want an appointment")
    assert res["intent"] == "BOOK_APPOINTMENT"


def test_6_book_doctor_tomorrow():
    res = intent_router.route_patient_message("Book a doctor for tomorrow")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["date"] is not None


def test_7_cancel_appointment():
    res = intent_router.route_patient_message("I want to cancel my appointment")
    assert res["intent"] == "CANCEL_APPOINTMENT"


def test_8_move_appointment():
    res = intent_router.route_patient_message("Can I move my appointment?")
    assert res["intent"] == "RESCHEDULE_APPOINTMENT"


def test_9_who_is_available_tomorrow():
    res = intent_router.route_patient_message("Who is available tomorrow?")
    assert res["intent"] == "CHECK_DOCTOR_AVAILABILITY"


def test_10_hospital_info():
    res = intent_router.route_patient_message("I want information about the hospital")
    assert res["intent"] == "HOSPITAL_INFORMATION"


def test_11_book_for_son():
    res = intent_router.route_patient_message("I want to book for my son")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["appointment_for"] == "CHILD"
    assert res["relationship"] == "SON"


def test_12_daughter_has_fever():
    res = intent_router.route_patient_message("My daughter has fever")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["appointment_for"] == "CHILD"
    assert res["relationship"] == "DAUGHTER"
    assert res["department"] in ["Pediatrics", "General Medicine"]


def test_13_son_skin_problem():
    res = intent_router.route_patient_message("My son has a skin problem")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["appointment_for"] == "CHILD"
    assert res["relationship"] == "SON"
    assert res["department"] == "Dermatology"


def test_14_need_dermatologist():
    res = intent_router.route_patient_message("I need a dermatologist")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["department"] == "Dermatology"


def test_15_need_general_physician():
    res = intent_router.route_patient_message("I need a general physician")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["department"] == "General Medicine"


def test_16_tomorrow_at_5_pm():
    res = intent_router.route_patient_message("tomorrow at 5 PM")
    assert res["date"] is not None
    assert res["time"] == "17:00"


def test_17_date_format_slash():
    res = intent_router.route_patient_message("05/09/2026")
    assert res["date"] == "2026-09-05"


def test_18_date_format_words():
    res = intent_router.route_patient_message("September 5th")
    assert res["date"] == "2026-09-05"


def test_19_dob_format_numeric():
    res = intent_router.route_patient_message("08/09/2004")
    assert res["dob"] == "2004-09-08"


def test_20_dob_format_words():
    res = intent_router.route_patient_message("September 8, 2004")
    assert res["dob"] == "2004-09-08"


def test_21_multilingual_fever():
    res = intent_router.route_patient_message("எனக்கு காய்ச்சல் இருக்கு")
    assert res["intent"] in ["BOOK_APPOINTMENT", "GREETING", "PATIENT_REGISTRATION"]
    assert res["language"] == "TAMIL"


def test_22_multilingual_appointment():
    res = intent_router.route_patient_message("எனக்கு டாக்டரை பார்க்க வேண்டும்")
    assert res["language"] == "TAMIL"


def test_23_mixed_language_message():
    res = intent_router.route_patient_message("fever headache இருக்கு")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert res["department"] == "General Medicine"


def test_24_ambiguous_intent():
    res = intent_router.route_patient_message("something unclear")
    assert "intent" in res
    assert res["confidence"] <= 1.0


def test_25_emergency_message_cannot_breathe():
    res = intent_router.route_patient_message("can't breathe")
    assert res["intent"] == "EMERGENCY"
    assert res["emergency"] is True


def test_26_doctor_department_isolation_guard():
    """
    Database isolation test: Ensures a doctor from General Medicine
    is NEVER validated for Dermatology.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Get a doctor ID belonging to General Medicine
        cur.execute("""
            SELECT d.id, d.first_name, dept.department_name
            FROM doctors d
            JOIN departments dept ON d.department_id = dept.id
            WHERE dept.department_name = 'General Medicine' AND d.status = 'ACTIVE'
            LIMIT 1;
        """)
        gen_med_doc = cur.fetchone()
        if gen_med_doc:
            doc_id, doc_name, dept_name = gen_med_doc
            # Validate this General Medicine doctor against Dermatology target
            is_valid_for_dermatology = intent_router.validate_doctor_department(doc_id, "Dermatology")
            assert is_valid_for_dermatology is False, f"Doctor {doc_name} (General Med) was wrongly validated for Dermatology!"

            # Validate this General Medicine doctor against General Medicine target
            is_valid_for_gen_med = intent_router.validate_doctor_department(doc_id, "General Medicine")
            assert is_valid_for_gen_med is True
    finally:
        cur.close()
        conn.close()
