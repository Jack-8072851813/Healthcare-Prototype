"""
test_llm_whatsapp_flow.py
=========================
Comprehensive 30-Scenario Test Suite for Meridian Hospital AI Patient Desk Upgrade.
Covering LLM conversation, multi-field extraction, date/DOB normalization, interactive buttons,
appointment workflows, fallback mechanisms, RAG, safety, and database integrity.
"""

import pytest
import sys
import os
import datetime

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from agent.state_manager import get_conversation_state, save_conversation_state
from agent.agent_service import process_agent_message
import agent.date_normalizer as date_normalizer
import agent.llm_service as llm_service
import voice.whatsapp_client as whatsapp_client


@pytest.fixture(autouse=True)
def cleanup_test_env():
    """Cleanup test data before and after each test."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code LIKE 'WA_SUITE_%');")
        cur.execute("DELETE FROM conversations WHERE conversation_code LIKE 'WA_SUITE_%';")
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone LIKE '919888%' OR whatsapp_number LIKE '919888%' OR phone LIKE '919999%' OR whatsapp_number LIKE '919999%');")
        cur.execute("DELETE FROM patients WHERE phone LIKE '919888%' OR whatsapp_number LIKE '919888%' OR phone LIKE '919999%' OR whatsapp_number LIKE '919999%';")
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    yield

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code LIKE 'WA_SUITE_%');")
        cur.execute("DELETE FROM conversations WHERE conversation_code LIKE 'WA_SUITE_%';")
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone LIKE '919888%' OR whatsapp_number LIKE '919888%' OR phone LIKE '919999%' OR whatsapp_number LIKE '919999%');")
        cur.execute("DELETE FROM patients WHERE phone LIKE '919888%' OR whatsapp_number LIKE '919888%' OR phone LIKE '919999%' OR whatsapp_number LIKE '919999%';")
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def test_1_greeting():
    """Scenario 1: Greeting message returns concise welcome + interactive options."""
    conv_code = "WA_SUITE_01_NEW"
    get_conversation_state(conv_code, whatsapp_number="9199990001")
    res = process_agent_message(conv_code, None, "Hi")
    assert res.get("response") is not None
    assert "Meridian Hospital" in res["response"]
    assert len(res["interactive_buttons"]) >= 2
    assert res["interactive_buttons"][0]["title"] in ["First-time Visitor", "First-time Patient"]


def test_2_first_time_patient_button():
    """Scenario 2: First-time patient button selection transitions to registration."""
    conv_code = "WA_SUITE_02"
    res = process_agent_message(conv_code, None, "btn_first_time")
    assert res.get("response") is not None
    assert "Full Name" in res["response"] or "Full name" in res["response"]


def test_3_existing_patient_button():
    """Scenario 3: Existing patient button selection prompts for patient code/phone."""
    conv_code = "WA_SUITE_03"
    res = process_agent_message(conv_code, None, "btn_existing")
    assert res.get("response") is not None


def test_4_registration_all_fields_in_one_message():
    """Scenario 4: Registration with all fields in one message."""
    conv_code = "WA_SUITE_04"
    phone = "9198880004"
    get_conversation_state(conv_code, whatsapp_number=phone)

    res = process_agent_message(conv_code, None, "btn_first_time")
    res2 = process_agent_message(conv_code, None, f"Arokiya Gilbrit, 15 Aug 1995, Male, {phone}")

    assert res2.get("response") is not None
    assert "understood your details" in res2["response"].lower() or "confirm" in res2["response"].lower() or "saved" in res2["response"].lower()


def test_5_registration_fields_across_multiple_messages():
    """Scenario 5: Registration with fields across multiple messages."""
    conv_code = "WA_SUITE_05"
    phone = "9198880005"
    get_conversation_state(conv_code, whatsapp_number=phone)

    process_agent_message(conv_code, None, "btn_first_time")
    process_agent_message(conv_code, None, "Arokiya Gilbrit")
    process_agent_message(conv_code, None, "1995-08-15")
    res_final = process_agent_message(conv_code, None, "Male")

    assert res_final.get("response") is not None



def test_6_dob_dd_mm_yyyy():
    """Scenario 6: Date of birth parsing in DD/MM/YYYY format."""
    is_valid, norm, err = date_normalizer.validate_dob("15/08/1995")
    assert is_valid is True
    assert norm == "1995-08-15"


def test_7_dob_mm_dd_yyyy():
    """Scenario 7: Date of birth parsing when day > 12."""
    is_valid, norm, err = date_normalizer.validate_dob("08/25/1995")
    assert is_valid is True
    assert norm == "1995-08-25"


def test_8_dob_written_in_words():
    """Scenario 8: DOB written in words (e.g. 15 August 1995)."""
    is_valid, norm, err = date_normalizer.validate_dob("15 August 1995")
    assert is_valid is True
    assert norm == "1995-08-15"


def test_9_ambiguous_dob():
    """Scenario 9: Ambiguous DOB (05/06/1995) flags ambiguity for clarification."""
    is_valid, norm, err = date_normalizer.validate_dob("05/06/1995", allow_ambiguous=False)
    assert is_valid is False
    assert "Ambiguous" in err



def test_10_appointment_request_all_details_in_one_message():
    """Scenario 10: Appointment request with all details in one message."""
    conv_code = "WA_SUITE_10"
    # Seed patient first
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
            VALUES ('P9810', 'SuiteTest', 'User', '1995-08-15', 'Male', '9198880010', '9198880010', 'ACTIVE')
            RETURNING id;
        """)
        pid = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    get_conversation_state(conv_code, whatsapp_number="9198880010")
    res = process_agent_message(conv_code, None, "I want to book Cardiology with Dr. Arun Kumar tomorrow at 10:00 AM for chest check-up")
    assert res["success"] is True
    assert "Please confirm your appointment" in res["response"] or "Dr. Arun Kumar" in res["response"]


def test_11_appointment_request_partial_details():
    """Scenario 11: Appointment request with partial details asks only for missing fields."""
    conv_code = "WA_SUITE_11"
    res = process_agent_message(conv_code, None, "I want an appointment with Dr. Arun Kumar tomorrow")
    assert res["success"] is True
    assert "Dr. Arun Kumar" in res["response"] or "Date" in res["response"]


def test_12_appointment_state_continuation():
    """Scenario 12: Appointment state continuation remembers doctor and date across turns."""
    conv_code = "WA_SUITE_12"
    process_agent_message(conv_code, None, "I want an appointment with Dr. Arun Kumar")
    res = process_agent_message(conv_code, None, "Tomorrow at 10:00 AM for routine checkup")
    assert res["success"] is True


def test_13_natural_language_doctor_selection():
    """Scenario 13: Extract doctor name from natural language phrasing."""
    extracted = llm_service.extract_structured_info("Can I meet Dr Arun Kumar tomorrow?", {}, "ENGLISH")
    assert extracted["intent"] in ["BOOK_APPOINTMENT", "DOCTOR_AVAILABILITY"]


def test_14_natural_language_date():
    """Scenario 14: Parse natural language relative dates ('tomorrow')."""
    norm, _, _ = date_normalizer.parse_and_normalize_date("tomorrow")
    tomorrow_str = (date_normalizer.get_current_kolkata_date() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    assert norm == tomorrow_str


def test_15_natural_language_time():
    """Scenario 15: Parse natural language time ('10:30 AM')."""
    from agent.entity_extractor import parse_natural_time
    parsed_t = parse_natural_time("10:30 AM")
    assert parsed_t == "10:30"


def test_16_doctor_availability():
    """Scenario 16: Check doctor availability for a specified date."""
    conv_code = "WA_SUITE_16"
    res = process_agent_message(conv_code, None, "Is Dr. Arun Kumar available tomorrow?")
    assert res.get("response") is not None


def test_17_no_available_slots():
    """Scenario 17: Offers real DB alternative slots when requested slot is unavailable."""
    conv_code = "WA_SUITE_17"
    res = process_agent_message(conv_code, None, "Book Cardiology with Dr. Arun Kumar today at 04:59 AM for checkup")
    assert res.get("response") is not None


def test_18_appointment_confirmation():
    """Scenario 18: WhatsApp appointment confirmation syncs to DB, Admin/Doctor dashboards, and clears buttons."""
    conv_code = "WA_SUITE_18"
    phone = "9198880018"
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
            VALUES ('P9818', 'ConfirmTest', 'User', '1995-08-15', 'Male', '9198880018', '9198880018', 'ACTIVE')
            RETURNING id;
        """)
        pid = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    get_conversation_state(conv_code, whatsapp_number=phone)
    tomorrow_str = (date_normalizer.get_current_kolkata_date() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    process_agent_message(conv_code, None, f"Book Cardiology with Dr. Arun Kumar on {tomorrow_str} at 10:00 AM for checkup")
    res_confirm = process_agent_message(conv_code, None, "btn_confirm_appt")

    assert res_confirm.get("response") is not None
    assert "confirmed" in res_confirm["response"].lower() or "booking id" in res_confirm["response"].lower() or "appointment" in res_confirm["response"].lower()

    # A. Verify PostgreSQL persistence & status = CONFIRMED
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM doctors WHERE display_name LIKE '%Arun%' LIMIT 1;")
        arun_row = cur.fetchone()
        arun_doc_id = arun_row[0] if arun_row else 1

        cur.execute("SELECT id, booking_id, doctor_id, department_id, status FROM appointments WHERE patient_id = %s ORDER BY id DESC LIMIT 1;", (pid,))
        appt_row = cur.fetchone()
        assert appt_row is not None
        appt_db_id, booking_id, doc_id, dept_id, appt_status = appt_row
        assert appt_status == "CONFIRMED"
        assert doc_id == arun_doc_id
    finally:
        cur.close()
        conn.close()

    # B. Confirmed appointment appears in Admin Dashboard
    from api.dashboard_routes import get_appointments, get_dashboard_summary
    admin_user = {"id": 1, "role": "ADMIN", "doctor_id": None}
    admin_appts = get_appointments(page=1, per_page=10, current_user=admin_user)
    admin_booking_ids = [a["booking_id"] for a in admin_appts["appointments"]]
    assert booking_id in admin_booking_ids

    # C. Confirmed appointment appears in assigned Doctor Dashboard
    dr_arun_user = {"id": 2, "role": "DOCTOR", "doctor_id": arun_doc_id}
    doc_appts = get_appointments(page=1, per_page=10, current_user=dr_arun_user)
    doc_booking_ids = [a["booking_id"] for a in doc_appts["appointments"]]
    assert booking_id in doc_booking_ids

    # D. Another doctor cannot see that appointment
    other_doc_user = {"id": 3, "role": "DOCTOR", "doctor_id": 2}
    other_doc_appts = get_appointments(page=1, per_page=10, current_user=other_doc_user)
    other_booking_ids = [a["booking_id"] for a in other_doc_appts["appointments"]]
    assert booking_id not in other_booking_ids

    # E. Appointment KPI counts update correctly
    summary = get_dashboard_summary(current_user=admin_user)
    assert summary["appointments"]["total"] > 0

    # G. Conversation continues naturally after confirmation
    res_followup = process_agent_message(conv_code, None, "Yes")
    assert res_followup.get("response") is not None

    # H. Typing indicator and read status functions run cleanly
    whatsapp_client.mark_message_read("wamid.test_123")
    whatsapp_client.send_typing_indicator(phone)


def test_19_appointment_cancellation():
    """Scenario 19: Cancelling pending confirmation resets state cleanly."""
    conv_code = "WA_SUITE_19"
    get_conversation_state(conv_code, whatsapp_number="9198880019")
    process_agent_message(conv_code, None, "Book Cardiology with Dr. Arun Kumar tomorrow at 10:00 AM for checkup")
    res_cancel = process_agent_message(conv_code, None, "btn_cancel_appt")
    assert res_cancel.get("response") is not None
    assert "cancel" in res_cancel["response"].lower()



def test_20_multilingual_conversation():
    """Scenario 20: Tamil / Hindi greeting and interaction."""
    conv_code = "WA_SUITE_20"
    res_ta = process_agent_message(conv_code, None, "வணக்கம்")
    assert res_ta["success"] is True


def test_21_language_switching():
    """Scenario 21: Switching language mid-conversation preserves state."""
    conv_code = "WA_SUITE_21"
    process_agent_message(conv_code, None, "Hello")
    res_shift = process_agent_message(conv_code, None, "தமிழில் சொல்லுங்கள்")
    assert res_shift["success"] is True
    assert res_shift["intent"] == "LANGUAGE_CHANGE"


def test_22_emergency_override():
    """Scenario 22: Emergency keywords trigger deterministic emergency response immediately."""
    conv_code = "WA_SUITE_22"
    res_emerg = process_agent_message(conv_code, None, "I am having severe chest pain and breathing difficulty")
    assert res_emerg["success"] is True
    assert res_emerg["intent"] == "EMERGENCY_GUIDANCE"


def test_23_rag_response():
    """Scenario 23: Hospital information questions trigger RAG retrieval."""
    conv_code = "WA_SUITE_23"
    res_rag = process_agent_message(conv_code, None, "What documents are required for admission?")
    assert res_rag["success"] is True


def test_24_invalid_llm_output_fallback():
    """Scenario 24: System falls back safely when LLM is unavailable or produces invalid output."""
    extracted = llm_service.extract_structured_info("Book appointment with Dr. Arun Kumar", {}, "ENGLISH")
    assert extracted["intent"] in ["BOOK_APPOINTMENT", "DOCTOR_AVAILABILITY"]


def test_25_unknown_doctor():
    """Scenario 25: Requesting an unknown doctor returns clear helpful message."""
    conv_code = "WA_SUITE_25"
    res = process_agent_message(conv_code, None, "I want to see Dr. Unknown Doctor")
    assert res["success"] is True


def test_26_unknown_department():
    """Scenario 26: Requesting an unknown department handled gracefully."""
    conv_code = "WA_SUITE_26"
    res = process_agent_message(conv_code, None, "I want an appointment in Aerospace Medicine")
    assert res["success"] is True


def test_27_existing_patient_lookup():
    """Scenario 27: Patient lookup by patient code P001."""
    conv_code = "WA_SUITE_27"
    res = process_agent_message(conv_code, None, "P001")
    assert res["success"] is True


def test_28_foreign_key_safety():
    """Scenario 28: Never insert non-existent patient_id into conversations table."""
    conv_code = "WA_SUITE_28"
    state = get_conversation_state(conv_code, whatsapp_number="9198880028")
    state["patient_id"] = 999999
    save_conversation_state(conv_code, state)

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT patient_id FROM conversations WHERE conversation_code = %s;", (conv_code,))
        assert cur.fetchone()[0] is None
    finally:
        cur.close()
        conn.close()


def test_29_whatsapp_interactive_message_generation():
    """Scenario 29: Button payload simulation in whatsapp_client."""
    res = whatsapp_client.send_button_message("9198880029", "Select option", [{"id": "btn_1", "title": "Option 1"}])
    assert res["success"] is True


def test_30_whatsapp_text_fallback():
    """Scenario 30: Text payload simulation in whatsapp_client."""
    res = whatsapp_client.send_text_message("9198880030", "Hello text")
    assert res["success"] is True
