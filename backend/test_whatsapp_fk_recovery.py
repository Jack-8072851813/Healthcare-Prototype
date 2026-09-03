import pytest
import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from agent.state_manager import get_conversation_state, save_conversation_state, resolve_valid_patient_id
from agent.agent_service import process_agent_message


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Cleanup test data before and after each test."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Clean up test conversations & patients with test prefix/numbers
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code LIKE 'WA_TEST_%');")
        cur.execute("DELETE FROM conversations WHERE conversation_code LIKE 'WA_TEST_%';")
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone LIKE '91999900%' OR whatsapp_number LIKE '91999900%');")
        cur.execute("DELETE FROM patients WHERE phone LIKE '91999900%' OR whatsapp_number LIKE '91999900%';")
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
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code LIKE 'WA_TEST_%');")
        cur.execute("DELETE FROM conversations WHERE conversation_code LIKE 'WA_TEST_%';")
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone LIKE '91999900%' OR whatsapp_number LIKE '91999900%');")
        cur.execute("DELETE FROM patients WHERE phone LIKE '91999900%' OR whatsapp_number LIKE '91999900%';")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Post-test cleanup error:", e)
    finally:
        cur.close()
        conn.close()


def test_valid_patient_id():
    """Test 1: Process message with a valid, existing patient_id."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Create a valid test patient
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
            VALUES ('P9966', 'ValidTest', 'User', '1990-01-01', 'Male', '9199990001', '9199990001', 'ACTIVE')
            RETURNING id;
        """)
        valid_pid = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    conv_code = "WA_TEST_001"
    # Get state for existing patient WhatsApp number
    state = get_conversation_state(conv_code, whatsapp_number="9199990001")
    assert state["patient_id"] == valid_pid
    assert state["entities"]["patient_id"] == valid_pid

    # Save state
    save_conversation_state(conv_code, state)

    # Verify conversation row in DB has valid patient_id
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT patient_id FROM conversations WHERE conversation_code = %s;", (conv_code,))
        db_pid = cur.fetchone()[0]
        assert db_pid == valid_pid
    finally:
        cur.close()
        conn.close()


def test_missing_patient_id():
    """Test 2: Process message for unregistered user (missing patient_id)."""
    conv_code = "WA_TEST_002"
    phone = "9199990002"

    state = get_conversation_state(conv_code, whatsapp_number=phone)
    assert state["patient_id"] is None
    assert state["entities"]["patient_id"] is None

    res = process_agent_message(conv_code, patient_code=None, message_text="Hello hospital")
    assert res["success"] is True

    # Verify DB patient_id is NULL
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT patient_id FROM conversations WHERE conversation_code = %s;", (conv_code,))
        db_pid = cur.fetchone()[0]
        assert db_pid is None
    finally:
        cur.close()
        conn.close()


def test_stale_non_existent_patient_id():
    """Test 3: Recover gracefully when state contains stale/non-existent patient_id (e.g. 999999)."""
    conv_code = "WA_TEST_003"
    stale_pid = 999999

    # Create conversation state with a stale patient_id
    state = get_conversation_state(conv_code, whatsapp_number="9199990003")
    state["patient_id"] = stale_pid
    state["entities"]["patient_id"] = stale_pid

    # save_conversation_state should NOT raise ForeignKeyViolation
    save_conversation_state(conv_code, state)

    # Verify stale patient_id was cleared/reconciled to NULL because 999999 is not in patients table
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT patient_id FROM conversations WHERE conversation_code = %s;", (conv_code,))
        db_pid = cur.fetchone()[0]
        assert db_pid is None
    finally:
        cur.close()
        conn.close()

    # Further message processing must complete successfully without error
    res = process_agent_message(conv_code, patient_code=None, message_text="What are your visiting hours?")
    assert res["success"] is True


def test_new_whatsapp_user():
    """Test 4: New WhatsApp user initial interaction and subsequent status."""
    conv_code = "WA_TEST_004"
    phone = "9199990004"

    # Pre-create session for this whatsapp number
    get_conversation_state(conv_code, whatsapp_number=phone)

    res = process_agent_message(conv_code, patient_code=None, message_text="Hi")
    assert res["success"] is True

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT patient_id, whatsapp_number FROM conversations WHERE conversation_code = %s;", (conv_code,))
        row = cur.fetchone()
        assert row[0] is None
        assert row[1] == phone
    finally:
        cur.close()
        conn.close()


def test_existing_whatsapp_user_reconciliation():
    """Test 5: Auto-matching existing user by WhatsApp number when stale patient_id is provided."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
            VALUES ('P9905', 'ExistingUser', 'Test', '1990-01-01', 'Male', '9199990005', '9199990005', 'ACTIVE')
            RETURNING id;
        """)
        real_pid = cur.fetchone()[0]
        conn.commit()
    finally:
        cur.close()
        conn.close()

    conv_code = "WA_TEST_005"
    # Force stale patient_id=888888 in get_conversation_state call
    state = get_conversation_state(conv_code, whatsapp_number="9199990005")
    state["patient_id"] = 888888  # stale reference

    save_conversation_state(conv_code, state)

    # Re-retrieve conversation state
    retrieved_state = get_conversation_state(conv_code, whatsapp_number="9199990005")
    # Must reconcile stale 888888 to real_pid via phone match
    assert retrieved_state["patient_id"] == real_pid


def test_registration_flow_after_stale_session_recovery():
    """Test 6: Completing patient registration after recovering from a stale session."""
    conv_code = "WA_TEST_006"
    phone = "9199990006"

    # Start with stale session state
    state = get_conversation_state(conv_code, whatsapp_number=phone)
    state["patient_id"] = 777777  # stale ID
    save_conversation_state(conv_code, state)

    # User initiates registration
    res1 = process_agent_message(conv_code, patient_code=None, message_text="Register patient")
    assert res1["success"] is True

    # Provide registration details together
    res2 = process_agent_message(conv_code, patient_code=None, message_text="John Doe, 1990-05-15, Male, 9199990006, General Consultation")
    res_final = process_agent_message(conv_code, patient_code=None, message_text="Confirm")

    assert ("created successfully" in res_final["response"]) or ("Patient Code" in res_final["response"])

    # Verify newly created patient ID is saved on conversation
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT patient_id FROM conversations WHERE conversation_code = %s;", (conv_code,))
        new_pid = cur.fetchone()[0]
        assert new_pid is not None

        cur.execute("SELECT first_name, phone FROM patients WHERE id = %s;", (new_pid,))
        p_row = cur.fetchone()
        assert p_row[0] == "John"
        assert p_row[1] == phone
    finally:
        cur.close()
        conn.close()
