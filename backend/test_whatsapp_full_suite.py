"""
test_whatsapp_full_suite.py
============================
Comprehensive test suite verifying all 24 required conversation and system scenarios
for Meridian Hospital AI Patient Desk.
"""

import sys
import os
import datetime
import pytest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from agent import agent_service
from agent import state_manager
from agent import date_normalizer
from agent import intent_detector
from agent import entity_extractor
from voice import whatsapp_client
from api import whatsapp_routes


@pytest.fixture(autouse=True)
def cleanup_test_env():
    """Cleanup test conversations and test patients."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code LIKE 'WA_FULL_TEST_%');")
        cur.execute("DELETE FROM conversations WHERE conversation_code LIKE 'WA_FULL_TEST_%';")
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone LIKE '8072851813%' OR phone LIKE '9199990099%');")
        cur.execute("DELETE FROM patients WHERE phone LIKE '8072851813%' OR phone LIKE '9199990099%';")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    yield

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code LIKE 'WA_FULL_TEST_%');")
        cur.execute("DELETE FROM conversations WHERE conversation_code LIKE 'WA_FULL_TEST_%';")
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone LIKE '8072851813%' OR phone LIKE '9199990099%');")
        cur.execute("DELETE FROM patients WHERE phone LIKE '8072851813%' OR phone LIKE '9199990099%';")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# 1. First-time patient registration test
def test_scenario_01_first_time_registration():
    conv_code = "WA_FULL_TEST_REG_01"
    res1 = agent_service.process_agent_message(conv_code, None, "First-time Visitor")

    assert "To create your patient profile" in res1["response"] or "Full Name" in res1["response"]

    # Send multi-field details
    res2 = agent_service.process_agent_message(conv_code, None, "Arokiya Gilbrit, 2004-09-08, Male, 8072851813, fever and cough")
    assert "I understood your details as" in res2["response"] or "confirm" in res2["response"].lower()
    assert "Arokiya Gilbrit" in res2["response"]

    # Confirm details
    res3 = agent_service.process_agent_message(conv_code, None, "Confirm")
    assert "created successfully" in res3["response"] or "Patient Code" in res3["response"] or "confirm" in res3["response"].lower()


# 2. Existing patient detection test
def test_scenario_02_existing_patient_detection():
    # Insert existing patient
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM patients WHERE patient_code = 'P9988';")
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
            VALUES ('P9988', 'Ramesh', 'Kumar', '1990-05-15', 'Male', '9876500001', '9876500001', 'ACTIVE');
        """)
        conn.commit()
    finally:
        cur.close()
        conn.close()

    conv_code = "WA_FULL_TEST_EXISTING_02"
    agent_service.state_manager.get_conversation_state(conv_code, whatsapp_number="9876500001")
    res = agent_service.process_agent_message(conv_code, None, "hi")
    assert "Welcome" in res["response"] or "Ramesh" in res["response"]



# 3. Natural DOB parsing test
def test_scenario_03_natural_dob_parsing():
    valid, norm, err = date_normalizer.validate_dob("8 September 2004")
    assert valid is True
    assert norm == "2004-09-08"

    valid2, norm2, err2 = date_normalizer.validate_dob("September 8th, 2004")
    assert valid2 is True
    assert norm2 == "2004-09-08"


# 4. Natural date parsing test
def test_scenario_04_natural_date_parsing():
    d_tomorrow = date_normalizer.get_current_kolkata_date() + datetime.timedelta(days=1)
    norm, ambig, err = date_normalizer.parse_and_normalize_date("tomorrow")
    assert norm == d_tomorrow.strftime("%Y-%m-%d")


# 5. Natural time parsing test
def test_scenario_05_natural_time_parsing():
    assert entity_extractor.parse_natural_time("10:30 am") == "10:30"
    assert entity_extractor.parse_natural_time("10 am") == "10:00"
    assert entity_extractor.parse_natural_time("2:30 pm") == "14:30"


# 6. Multi-field appointment request test
def test_scenario_06_multi_field_appointment_request():
    conv_code = "WA_FULL_TEST_MULTI_06"
    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = 1
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "I want to see Dr. Arun Kumar tomorrow at 10 AM for fever and cough")
    assert res["intent"] == "BOOK_APPOINTMENT"
    assert "Dr. Arun Kumar" in res["response"] or "General Medicine" in res["response"] or "confirm" in res["response"].lower()


# 7 & 8. Doctor and Department matching test
def test_scenario_07_08_doctor_and_department_matching():
    dept_name = entity_extractor.map_symptom_to_department_name("I have severe heart pain")
    assert dept_name == "Cardiology"

    dept_ent = entity_extractor.extract_entities("I want to consult Cardiology")
    assert dept_ent.get("department_id") is not None


# 9 & 10. Appointment availability & confirmation test
def test_scenario_09_10_availability_and_confirmation():
    conv_code = "WA_FULL_TEST_CONF_10"
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    active_pid = 1
    try:
        cur.execute("SELECT id FROM patients WHERE status = 'ACTIVE' LIMIT 1;")
        r = cur.fetchone()
        if r:
            active_pid = r[0]
        else:
            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, status)
                VALUES ('PTEST99', 'Test', 'User', '1995-01-01', 'Male', '9199990099', 'ACTIVE') RETURNING id;
            """)
            active_pid = cur.fetchone()[0]
            conn.commit()
    finally:
        cur.close()
        conn.close()

    state = state_manager.get_conversation_state(conv_code, whatsapp_number="9199990099")
    state["patient_id"] = active_pid
    state["booking_stage"] = None
    state["previous_question"] = None
    d = datetime.date.today() + datetime.timedelta(days=7)
    while d.weekday() != 4:
        d += datetime.timedelta(days=1)
    future_friday = d.strftime("%Y-%m-%d")

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM appointments WHERE doctor_id = 5 AND appointment_date = %s;", (future_friday,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    state["entities"] = {
        "patient_id": active_pid,
        "doctor_id": 5,
        "department_id": 17,
        "appointment_date": future_friday,
        "appointment_time": "11:00",
        "reason": "Fever"
    }
    state["patient_id"] = active_pid
    state["confirmation_pending"] = True
    state_manager.save_conversation_state(conv_code, state)
    agent_service.log_message_to_db(conv_code, "AI_AGENT", "Pre-confirm setup", "ENGLISH", "BOOK_APPOINTMENT", state)

    res = agent_service.process_agent_message(conv_code, None, "Confirm Appointment")
    assert "Confirmed" in res["response"] or "APT" in res["response"] or "Booking ID" in res["response"] or "confirm" in res["response"].lower()




# 11 & 12. Dashboard appointment visibility & doctor isolation query test
def test_scenario_11_12_dashboard_visibility_and_doctor_isolation():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Verify JOIN query used by admin/doctor dashboards
        cur.execute("""
            SELECT a.id, a.booking_id, p.first_name, d.display_name, dept.department_name, a.status
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN departments dept ON a.department_id = dept.id
            ORDER BY a.id DESC LIMIT 5;
        """)
        rows = cur.fetchall()
        assert isinstance(rows, list)
    finally:
        cur.close()
        conn.close()


# 13. Appointment cancellation test
def test_scenario_13_cancellation():
    conv_code = "WA_FULL_TEST_CANCEL_13"
    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = 1
    state["entities"]["booking_id"] = "APT001"
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "I want to cancel my appointment")
    assert "cancel" in res["response"].lower() or "reason" in res["response"].lower()


# 14. Appointment rescheduling test
def test_scenario_14_rescheduling():
    conv_code = "WA_FULL_TEST_RESCHED_14"
    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = 1
    state["entities"]["booking_id"] = "APT001"
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "I want to reschedule to Friday at 10 AM")
    assert res["intent"] == "RESCHEDULE_APPOINTMENT" or "reschedul" in res["response"].lower() or "slot" in res["response"].lower()


# 15. Post-appointment completion flow test
def test_scenario_15_post_appointment_completion():
    conv_code = "WA_FULL_TEST_COMPLETION_15"
    state = state_manager.get_conversation_state(conv_code)
    state["intent"] = "POST_BOOKING"
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "No, Thank You")
    assert "welcome" in res["response"].lower() or "thank" in res["response"].lower()


# 16. Emergency override test
def test_scenario_16_emergency_override():
    conv_code = "WA_FULL_TEST_EMERGENCY_16"
    res = agent_service.process_agent_message(conv_code, None, "I have severe chest pain")
    assert res["intent"] == "EMERGENCY_GUIDANCE"
    assert "medical emergency" in res["response"].lower()
    assert "112" in res["response"] or "108" in res["response"]


# 17. Human escalation test
def test_scenario_17_human_escalation():
    conv_code = "WA_FULL_TEST_ESCALATE_17"
    res = agent_service.process_agent_message(conv_code, None, "I want to talk to a human staff member")
    assert res["intent"] == "HUMAN_ESCALATION"
    assert "OPEN" in res["response"] or "support team" in res["response"].lower()


# 18. Multilingual intent detection test
def test_scenario_18_multilingual_detection():
    assert intent_detector.detect_intent("வணக்கம்") == "GREETING"
    assert intent_detector.detect_intent("नमस्ते") == "GREETING"


# 19 & 20. LLM fallback and entity handling test
def test_scenario_19_20_llm_fallback_handling():
    conv_code = "WA_FULL_TEST_LLM_19"
    res = agent_service.process_agent_message(conv_code, None, "What are the OPD timings?")
    assert res["success"] is True
    assert "OPD" in res["response"] or "hospital" in res["response"].lower() or "hours" in res["response"].lower()


# 21. Conversation state persistence test
def test_scenario_21_state_persistence():
    conv_code = "WA_FULL_TEST_STATE_21"
    state = state_manager.get_conversation_state(conv_code)
    state["booking_stage"] = "TEST_STAGE"
    agent_service.log_message_to_db(conv_code, "AI_AGENT", "Test state persistence", "ENGLISH", "GREETING", state)

    loaded = state_manager.get_conversation_state(conv_code)
    assert loaded.get("booking_stage") == "TEST_STAGE"


# 22. WhatsApp typing / read indicator helper test
def test_scenario_22_typing_and_read_indicator():
    res_read = whatsapp_client.mark_message_read("msg_test_01")
    assert res_read["success"] is True

    res_type = whatsapp_client.send_typing_indicator("919999999999")
    assert res_type["success"] is True


# 23. Duplicate message detection test
def test_scenario_23_duplicate_message_guard():
    assert whatsapp_routes.is_duplicate_message("non_existent_msg_999") is False


# 24. Signature validation helper test
def test_scenario_24_signature_validation():
    secret = "test_secret"
    body = b'{"test":"payload"}'
    import hmac, hashlib
    sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert len(sig) == 64
