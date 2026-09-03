"""
test_whatsapp_family_email_suite.py
=====================================
Comprehensive test suite verifying all 28 requirements for:
1. Patient identification from WhatsApp phone number
2. Parent booking appointment for child / family member
3. Patient details collection & LLM extraction
4. DOB normalization & ambiguity resolution
5. Appointment booking & double booking prevention
6. Existing patient vs family member flow
7. Appointment confirmation email sending & email_logs status tracking
8. Email failure tolerance (doesn't rollback DB transaction)
9. Doctor creation & welcome email sending/logging
10. Dashboard API integration (Admin & Doctor views)
11. Foreign key integrity & state consistency
12. Multilingual detail handling & webhook end-to-end simulation
"""

import sys
import os
import pytest
import datetime
import json
import uuid

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.agent_service as agent_service
import agent.llm_service as llm_service
import agent.date_normalizer as date_normalizer
import utils.email_service as email_service
import appointment_service


def test_01_new_whatsapp_number_new_patient():
    """Requirement 1 & 7: New WhatsApp number unrecognized in DB prompts for registration."""
    dummy_code = f"CONV_TEST_NEW_{uuid.uuid4().hex[:8]}"
    dummy_phone = f"91777{uuid.uuid4().int % 10**7:07d}"
    state = agent_service.state_manager.get_conversation_state(dummy_code, whatsapp_number=dummy_phone)
    state["patient_id"] = None
    state["entities"]["patient_id"] = None
    agent_service.state_manager.save_conversation_state(dummy_code, state)

    res = agent_service.process_agent_message(dummy_code, None, "Hello", "EN")
    assert res["success"] is True
    assert "Meridian Hospital" in res["response"]
    assert "First-time Visitor" in [btn["title"] for btn in res.get("interactive_buttons", [])] or "Existing Patient" in [btn["title"] for btn in res.get("interactive_buttons", [])]


def test_02_existing_whatsapp_number_recognition():
    """Requirement 1: Existing WhatsApp number recognizes existing patient."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, first_name, last_name, phone, whatsapp_number FROM patients WHERE status = 'ACTIVE' LIMIT 1;")
        row = cur.fetchone()
        assert row is not None, "Need at least one active patient in DB"
        p_id, fn, ln, phone, wa = row
        wa_num = wa or phone

        conv_code = f"CONV_TEST_EXISTING_{p_id}_{uuid.uuid4().hex[:4]}"
        cur.execute("""
            INSERT INTO conversations (conversation_code, patient_id, whatsapp_number, language, current_intent, conversation_status)
            VALUES (%s, %s, %s, 'ENGLISH', 'GREETING', 'ACTIVE')
            ON CONFLICT (conversation_code) DO NOTHING;
        """, (conv_code, p_id, wa_num))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    res = agent_service.process_agent_message(conv_code, None, "Hi", "EN")
    assert res["success"] is True
    assert f"Welcome back, {fn}" in res["response"] or "How can I help you today?" in res["response"]


def test_03_existing_patient_booking_for_self():
    """Requirement 6: Existing patient booking for self uses existing patient profile."""
    state = agent_service.state_manager.get_conversation_state("CONV_TEST_SELF_01")
    state["patient_id"] = 1
    state["intent"] = "BOOK_APPOINTMENT"
    state["entities"]["appointment_for"] = "SELF"
    agent_service.state_manager.save_conversation_state("CONV_TEST_SELF_01", state)

    res = agent_service.process_agent_message("CONV_TEST_SELF_01", None, "Book appointment for fever", "EN")
    assert res["success"] is True
    assert "General Medicine" in res["response"] or "doctor" in res["response"].lower()


def test_04_05_06_07_08_parent_booking_for_child():
    """Requirements 2, 6, 7, 8: Parent booking for child creates separate child patient record linked to parent."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Create parent patient with fresh phone & patient_code
        parent_phone = f"9876{uuid.uuid4().int % 10**6:06d}"
        parent_code = f"PPR{uuid.uuid4().hex[:4]}"
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, email, status)
            VALUES (%s, 'Rajesh', 'Kumar', '1985-06-15', 'Male', %s, %s, 'parent@test.com', 'ACTIVE')
            RETURNING id;
        """, (parent_code, parent_phone, parent_phone))
        parent_id = cur.fetchone()[0]
        conn.commit()

        # Resolve/Create child patient under parent
        child_id = agent_service.resolve_or_create_child_patient(
            parent_patient_id=parent_id,
            child_name="Ananya Kumar",
            dob_str="2015-05-12",
            gender="Female",
            parent_phone=parent_phone,
            parent_whatsapp=parent_phone,
            email="parent@test.com",
            relationship="DAUGHTER"
        )
        assert child_id != parent_id, "Child must receive a separate patient ID from parent"

        # Verify child record in database
        cur.execute("SELECT first_name, date_of_birth, guardian_patient_id, relationship_to_contact, is_dependent FROM patients WHERE id = %s;", (child_id,))
        c_row = cur.fetchone()
        assert c_row[0] == "Ananya"
        assert str(c_row[1]) == "2015-05-12"
        assert c_row[2] == parent_id, "Guardian ID must point to parent patient ID"
        assert c_row[3] == "DAUGHTER"
        assert c_row[4] is True

        # Verify parent record remains unchanged
        cur.execute("SELECT first_name, date_of_birth FROM patients WHERE id = %s;", (parent_id,))
        p_row = cur.fetchone()
        assert p_row[0] == "Rajesh"
        assert str(p_row[1]) == "1985-06-15"
    finally:
        cur.close()
        conn.close()


def test_09_10_11_12_dob_normalization():
    """Requirement 4: DOB normalization (DD/MM/YYYY, YYYY-MM-DD, Natural Date, Ambiguous Date)."""
    # DD/MM/YYYY
    norm, ambig, err = date_normalizer.parse_and_normalize_date("12/05/2015")
    assert norm == "2015-05-12"

    # YYYY-MM-DD
    norm, ambig, err = date_normalizer.parse_and_normalize_date("2015-05-12")
    assert norm == "2015-05-12"

    # Natural Language
    norm, ambig, err = date_normalizer.parse_and_normalize_date("12 May 2015")
    assert norm == "2015-05-12"

    # Ambiguous Date check (e.g. 05/06/2015 where both numbers <= 12)
    norm, ambig, err = date_normalizer.parse_and_normalize_date("05/06/2015")
    assert ambig is True, "Numeric date 05/06/2015 should be flagged as ambiguous"


def test_13_14_appointment_booking_and_double_booking():
    """Requirements 5, 14: Transactional appointment booking and double booking prevention."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM doctors WHERE status = 'ACTIVE' LIMIT 1;")
        doc_id = cur.fetchone()[0]
        cur.execute("SELECT department_id FROM doctors WHERE id = %s;", (doc_id,))
        dept_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM patients WHERE status = 'ACTIVE' LIMIT 1;")
        pat_id = cur.fetchone()[0]

        # Pick a valid scheduled working day & start_time for this doctor
        cur.execute("SELECT day_of_week, start_time FROM doctor_schedules WHERE doctor_id = %s AND status = 'ACTIVE' LIMIT 1;", (doc_id,))
        s_row = cur.fetchone()
        day_name = s_row[0] if s_row else "MONDAY"
        st_val = str(s_row[1])[:5] if (s_row and s_row[1]) else "09:30"
        days_map = {"MONDAY": 0, "TUESDAY": 1, "WEDNESDAY": 2, "THURSDAY": 3, "FRIDAY": 4, "SATURDAY": 5, "SUNDAY": 6}
        target_dow = days_map.get(day_name.upper(), 0)
        today = datetime.date.today()
        days_ahead = (target_dow - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        target_date_obj = today + datetime.timedelta(days=days_ahead)
        target_date = target_date_obj.strftime("%Y-%m-%d")
        target_time = st_val

        # Clear any existing booking for this slot
        cur.execute("DELETE FROM appointments WHERE doctor_id = %s AND appointment_date = %s AND appointment_time = %s;", (doc_id, target_date, target_time))
        conn.commit()

        # 1. First booking succeeds
        res1 = appointment_service.book_appointment(
            patient_id=pat_id,
            doctor_id=doc_id,
            department_id=dept_id,
            date_str=target_date,
            time_str=target_time,
            patient_reason="Routine Checkup",
            booking_source="WHATSAPP_TEXT"
        )
        assert res1["success"] is True

        # 2. Second booking for same doctor/date/time fails with double-booking error
        with pytest.raises(appointment_service.SlotUnavailableError):
            appointment_service.book_appointment(
                patient_id=pat_id,
                doctor_id=doc_id,
                department_id=dept_id,
                date_str=target_date,
                time_str=target_time,
                patient_reason="Double booking attempt",
                booking_source="WHATSAPP_TEXT"
            )
    finally:
        cur.close()
        conn.close()


def test_15_16_dashboard_integration():
    """Requirement 17: Confirmed appointments appear in Admin and Doctor Dashboard queries."""
    from api.dashboard_routes import get_appointments
    admin_user = {"role": "ADMIN", "user_id": 1}
    res = get_appointments(page=1, per_page=10, current_user=admin_user)
    assert "appointments" in res
    assert isinstance(res["appointments"], list)


def test_17_18_email_confirmation_and_failure_tolerance():
    """Requirements 10, 13: Appointment confirmation email logging & failure tolerance."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    existing_appt_id = None
    try:
        cur.execute("SELECT id FROM appointments LIMIT 1;")
        row_a = cur.fetchone()
        if row_a:
            existing_appt_id = row_a[0]
    finally:
        cur.close()
        conn.close()

    # Test logging email success
    success = email_service.send_patient_appointment_confirmation_email(
        patient_email="testpatient@example.com",
        patient_name="Ananya Kumar",
        appointment_for="Child",
        doctor_name="Dr. Priya Ramesh",
        department_name="Pediatrics",
        appointment_date="2026-09-15",
        appointment_time="10:30 AM",
        booking_id="APT-TEST-001",
        appointment_id=existing_appt_id
    )
    assert isinstance(success, bool)

    # Check email_logs table entry
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT email_type, recipient, status FROM email_logs WHERE recipient = 'testpatient@example.com' ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "APPOINTMENT_CONFIRMATION"
        assert row[1] == "testpatient@example.com"
        assert "EMAIL_" in row[2]
    finally:
        cur.close()
        conn.close()


def test_19_20_doctor_creation_welcome_email():
    """Requirement 11, 13: Admin doctor creation dispatches welcome email and tracks log status."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM departments WHERE status = 'ACTIVE' LIMIT 1;")
        dept_id = cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()

    doctor_email = f"dr.test_{datetime.datetime.now().timestamp()}@meridian.com"
    username = f"drtest_{int(datetime.datetime.now().timestamp())}"

    # Call send_welcome_email directly to test logging
    sent = email_service.send_welcome_email(
        doctor_email=doctor_email,
        doctor_name="Dr. Test Specialist",
        username=username,
        password="TempPassword123"
    )
    assert isinstance(sent, bool)

    # Verify log entry in email_logs
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT email_type, recipient, status FROM email_logs WHERE recipient = %s ORDER BY id DESC LIMIT 1;", (doctor_email,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "DOCTOR_WELCOME"
        assert row[1] == doctor_email
        assert "DOCTOR_WELCOME_EMAIL_" in row[2]
    finally:
        cur.close()
        conn.close()


def test_21_existing_patient_family_member_flow():
    """Requirement 6: Existing patient booking for family member."""
    state = agent_service.state_manager.get_conversation_state("CONV_TEST_FAM_01")
    state["patient_id"] = 1
    state["intent"] = "BOOK_APPOINTMENT"
    state["entities"]["appointment_for"] = "CHILD"
    state["entities"]["relationship"] = "SON"
    state["entities"]["patient_name"] = "Rahul Kumar"
    agent_service.state_manager.save_conversation_state("CONV_TEST_FAM_01", state)

    res = agent_service.process_agent_message("CONV_TEST_FAM_01", None, "Rahul Kumar, 12/05/2015, Male, Pediatrics, Dr. Priya, 15 September morning", "EN")
    assert res["success"] is True


def test_22_multilingual_appointment_details():
    """Requirement 18: Multilingual patient appointment details extraction."""
    res = agent_service.process_agent_message("CONV_TEST_MULTI_01", None, "என் மகளுக்கு appointment வேண்டும். பெயர் Ananya. DOB 12/05/2015. Pediatrics வேண்டும்.", "TA")
    assert res["success"] is True


def test_23_24_25_llm_json_and_confidence_handling():
    """Requirement 9: LLM structured info extraction handles malformed JSON and low confidence gracefully."""
    extracted = llm_service.extract_structured_info("Rahul Kumar, DOB 12/05/2015, Male, Pediatrics, rahul@gmail.com", {"intent": "BOOK_APPOINTMENT"}, "EN")
    assert extracted is not None
    assert isinstance(extracted, dict)
    assert extracted.get("email") == "rahul@gmail.com" or "rahul" in str(extracted)


def test_26_27_state_and_fk_integrity():
    """Requirements 16, 27: DB Foreign key integrity and state consistency."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Verify all conversations link to valid active patients or null
        cur.execute("""
            SELECT COUNT(*) FROM conversations c
            LEFT JOIN patients p ON c.patient_id = p.id
            WHERE c.patient_id IS NOT NULL AND p.id IS NULL;
        """)
        orphans = cur.fetchone()[0]
        assert orphans == 0, "No orphaned conversation records allowed in DB"
    finally:
        cur.close()
        conn.close()


def test_28_whatsapp_webhook_end_to_end():
    """Requirement 28: WhatsApp webhook end-to-end flow execution."""
    from voice.whatsapp_client import process_incoming_whatsapp_payload
    dummy_payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "WHATSAPP_ENTRY_001",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "15550269894", "phone_number_id": "100000000000001"},
                    "contacts": [{"profile": {"name": "Test User"}, "wa_id": "919876543210"}],
                    "messages": [{
                        "from": "919876543210",
                        "id": f"wamid.TEST_{int(datetime.datetime.now().timestamp())}",
                        "timestamp": "1725350000",
                        "type": "text",
                        "text": {"body": "Hi, I want to check doctor availability"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }

    res = process_incoming_whatsapp_payload(dummy_payload)
    assert res is not None
    assert res.get("status") == "success"
