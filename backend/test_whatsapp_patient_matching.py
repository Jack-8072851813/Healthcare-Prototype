"""
test_whatsapp_patient_matching.py
==================================
Tests for WhatsApp phone normalization, existing patient auto-matching,
and multi-day session handling.
"""

import pytest
import sys
import os
import time

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from utils.phone_utils import normalize_phone, get_phone_query_params
from agent.state_manager import get_conversation_state, save_conversation_state, resolve_valid_patient_id
from agent.agent_service import process_agent_message
from api.whatsapp_routes import get_or_create_whatsapp_session


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data before and after each test."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code LIKE 'WA_TEST_NORM_%');")
        cur.execute("DELETE FROM conversations WHERE conversation_code LIKE 'WA_TEST_NORM_%' OR whatsapp_number LIKE '%988800%';")
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone LIKE '%988800%' OR whatsapp_number LIKE '%988800%' OR patient_code LIKE 'P980%');")
        cur.execute("DELETE FROM patients WHERE phone LIKE '%988800%' OR whatsapp_number LIKE '%988800%' OR patient_code LIKE 'P980%';")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Cleanup error:", e)
    finally:
        cur.close()
        conn.close()

    yield

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code LIKE 'WA_TEST_NORM_%');")
        cur.execute("DELETE FROM conversations WHERE conversation_code LIKE 'WA_TEST_NORM_%' OR whatsapp_number LIKE '%988800%';")
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone LIKE '%988800%' OR whatsapp_number LIKE '%988800%' OR patient_code LIKE 'P980%');")
        cur.execute("DELETE FROM patients WHERE phone LIKE '%988800%' OR whatsapp_number LIKE '%988800%' OR patient_code LIKE 'P980%';")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Post-test cleanup error:", e)
    finally:
        cur.close()
        conn.close()


def test_phone_utils_normalization():
    """Test phone normalization utility functions."""
    assert normalize_phone("919876543210") == "9876543210"
    assert normalize_phone("+91 98765 43210") == "9876543210"
    assert normalize_phone("09876543210") == "9876543210"
    assert normalize_phone("9876543210") == "9876543210"
    assert normalize_phone("") == ""

    params = get_phone_query_params("+91 98765 43210")
    assert params == ("+91 98765 43210", "+91 98765 43210", "9876543210", "9876543210")


def test_existing_patient_10digit_phone_matching():
    """
    Test that a patient created in hospital system with 10-digit phone '9888000001'
    is automatically matched when messaging from Meta WhatsApp '919888000001'.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, status)
            VALUES ('P9801', 'Arun', 'Kumar', '1988-03-15', 'Male', '9888000001', 'ACTIVE')
            RETURNING id;
        """)
        patient_id = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    conv_code = "WA_TEST_NORM_001"
    wa_number = "919888000001"

    # Get conversation state
    state = get_conversation_state(conv_code, whatsapp_number=wa_number)
    assert state["patient_id"] == patient_id
    assert state["entities"]["patient_id"] == patient_id

    # Process greeting message
    res = process_agent_message(conv_code, patient_code=None, message_text="Hi")
    assert res["success"] is True
    assert "Welcome back" in res["response"] and "Arun" in res["response"]


def test_formatted_phone_matching_in_identify_patient():
    """
    Test matching patient by 10-digit phone when patient in DB has '+91 98880 00002'.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, status)
            VALUES ('P9802', 'Priya', 'Ramanan', '1992-07-20', 'Female', '+91 98880 00002', 'ACTIVE')
            RETURNING id;
        """)
        patient_id = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    conv_code = "WA_TEST_NORM_002_ID"
    # Turn 1: User indicates they are an existing patient with an unregistered phone number
    get_conversation_state(conv_code, whatsapp_number="919888999999")
    res_turn1 = process_agent_message(conv_code, patient_code=None, message_text="Existing patient")
    assert res_turn1["success"] is True
    assert "couldn't find a patient profile" in res_turn1["response"] or "register" in res_turn1["response"].lower()

    # Turn 2: User provides their formatted 10-digit mobile number
    res_turn2 = process_agent_message(conv_code, patient_code=None, message_text="9888000002")
    assert res_turn2["success"] is True
    assert "Welcome" in res_turn2["response"]


def test_next_day_chatting_session_expiration():
    """
    Test that messaging after >24h of inactivity auto-closes the old session
    and starts a new clean session while retaining patient identity.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, status)
            VALUES ('P9803', 'Suresh', 'Raina', '1986-11-27', 'Male', '9888000003', 'ACTIVE')
            RETURNING id;
        """)
        patient_id = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    wa_number = "919888000003"
    conv_code = f"WA_{wa_number}"

    # Day 1 session
    state = get_conversation_state(conv_code, whatsapp_number=wa_number)
    assert state["patient_id"] == patient_id
    process_agent_message(conv_code, patient_code=None, message_text="Hi")

    # Manually backdate last_message_at in DB to 25 hours ago
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE conversations 
            SET last_message_at = CURRENT_TIMESTAMP - INTERVAL '25 hours' 
            WHERE conversation_code = %s;
        """, (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # Day 2 chat ("tomorrow")
    new_session_code = get_or_create_whatsapp_session(wa_number)
    assert new_session_code != conv_code or new_session_code.startswith(f"WA_{wa_number}")

    # Verify old session was marked COMPLETED
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT conversation_status FROM conversations WHERE conversation_code = %s;", (conv_code,))
        row = cur.fetchone()
        assert row[0] == 'COMPLETED'
    finally:
        cur.close()
        conn.close()

    # Process Day 2 message with new session code
    res_day2 = process_agent_message(new_session_code, patient_code=None, message_text="Hello")
    assert res_day2["success"] is True
    assert "Welcome back" in res_day2["response"] and "Suresh" in res_day2["response"]
