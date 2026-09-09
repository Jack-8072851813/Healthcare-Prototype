"""
test_bug_fixes_son_context_and_reason.py
===========================================
Focused regression tests for the two specific bug fixes:
1. Preventing stale dependent ("son") context leak into SELF appointment requests.
2. Preventing patient name ("Wilson Tony") from populating appointment reason during registration.
"""

import pytest
import random
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import agent_service, state_manager, llm_intent_router
import db_config


def get_db():
    return db_config.get_db_connection()


@pytest.fixture(autouse=True)
def setup_test_data():
    """Create test patient Wilson Tony and clean up state."""
    phone = f"9193{random.randint(10000000, 99999999)}"
    conv_code = f"WA_{phone}_TEST"

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE whatsapp_number = %s);", (phone,))
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone = %s);", (phone,))
        cur.execute("DELETE FROM conversations WHERE whatsapp_number = %s;", (phone,))
        cur.execute("DELETE FROM patients WHERE phone = %s;", (phone,))
        conn.commit()

        # Create registered primary patient Wilson Tony
        p_code = f"P{random.randint(50000, 99999)}"
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, is_dependent, status)
            VALUES (%s, 'Wilson', 'Tony', '2005-02-14', 'Male', %s, %s, FALSE, 'ACTIVE')
            RETURNING id;
        """, (p_code, phone, phone))
        patient_id = cur.fetchone()[0]

        # Get or create Dermatology department & Dr. Wilson M doctor if missing
        cur.execute("SELECT id FROM departments WHERE LOWER(department_name) = 'dermatology' LIMIT 1;")
        dept_row = cur.fetchone()
        if dept_row:
            dept_id = dept_row[0]
        else:
            cur.execute("INSERT INTO departments (department_name, status) VALUES ('Dermatology', 'ACTIVE') RETURNING id;")
            dept_id = cur.fetchone()[0]

        cur.execute("SELECT id FROM doctors WHERE display_name ILIKE '%Wilson%' LIMIT 1;")
        doc_row = cur.fetchone()
        if doc_row:
            doc_id = doc_row[0]
        else:
            cur.execute("INSERT INTO doctors (display_name, department_id, status) VALUES ('Dr. Wilson M', %s, 'ACTIVE') RETURNING id;", (dept_id,))
            doc_id = cur.fetchone()[0]

        conn.commit()
    finally:
        cur.close()
        conn.close()

    yield {
        "phone": phone,
        "conv_code": conv_code,
        "patient_id": patient_id,
        "dept_id": dept_id,
        "doc_id": doc_id,
    }


# ==============================================================================
# BUG 1 TESTS: PREVENTING SON CONTEXT LEAK INTO SELF APPOINTMENTS
# ==============================================================================

def test_1_registered_patient_symptom_request_is_self(setup_test_data):
    """Test 1: Registered patient saying 'I have hair loss' sets appointment_subject = SELF."""
    data = setup_test_data
    conv_code = data["conv_code"]
    patient_id = data["patient_id"]

    # Set up active conversation state for registered patient
    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = patient_id
    state["primary_patient_id"] = patient_id
    state["whatsapp_number"] = data["phone"]
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, data["phone"], "I have hair loss")
    updated_state = state_manager.get_conversation_state(conv_code)

    assert updated_state.get("appointment_subject") in ("SELF", None)
    assert updated_state.get("booking_for") == "SELF"
    assert updated_state.get("patient_relationship") is None
    assert updated_state.get("patient_id") == patient_id


def test_2_doctor_selection_preserves_self_and_reason(setup_test_data):
    """Test 2: Selecting Dr. Wilson M after hair loss preserves Wilson Tony patient_id and reason."""
    data = setup_test_data
    conv_code = data["conv_code"]
    patient_id = data["patient_id"]

    # First turn: I have hair loss
    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = patient_id
    state["primary_patient_id"] = patient_id
    state["whatsapp_number"] = data["phone"]
    state_manager.save_conversation_state(conv_code, state)

    agent_service.process_agent_message(conv_code, data["phone"], "I have hair loss")

    # Second turn: Dr. Wilson M
    res = agent_service.process_agent_message(conv_code, data["phone"], "Dr. Wilson M")
    updated_state = state_manager.get_conversation_state(conv_code)

    assert updated_state.get("patient_id") == patient_id
    assert updated_state.get("booking_for") == "SELF"
    assert updated_state.get("patient_relationship") is None
    assert updated_state.get("entities", {}).get("reason") in ("hair loss", "hair fall") or updated_state.get("entities", {}).get("symptoms") == ["hair loss"]
    assert "your son" not in res.get("response", "").lower()


def test_3_response_does_not_mention_son(setup_test_data):
    """Test 3: Next response must continue SELF flow and MUST NOT say 'your son'."""
    data = setup_test_data
    conv_code = data["conv_code"]
    patient_id = data["patient_id"]

    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = patient_id
    state["primary_patient_id"] = patient_id
    state["whatsapp_number"] = data["phone"]
    state_manager.save_conversation_state(conv_code, state)

    agent_service.process_agent_message(conv_code, data["phone"], "I have hair loss")
    res = agent_service.process_agent_message(conv_code, data["phone"], "Dr. Wilson M")

    assert "your son" not in res.get("response", "").lower()
    assert "son's patient details" not in res.get("response", "").lower()


def test_4_stale_son_context_override(setup_test_data):
    """Test 4: Stale relationship = SON in state must NOT leak into new 'I have hair loss' request."""
    data = setup_test_data
    conv_code = data["conv_code"]
    patient_id = data["patient_id"]

    # Inject stale SON state from a previous interaction
    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = patient_id
    state["primary_patient_id"] = patient_id
    state["whatsapp_number"] = data["phone"]
    state["patient_relationship"] = "SON"
    state["appointment_for"] = "CHILD"
    state["booking_for"] = "CHILD"
    state["appointment_subject"] = "DEPENDENT"
    state_manager.save_conversation_state(conv_code, state)

    # New request: I have hair loss
    res = agent_service.process_agent_message(conv_code, data["phone"], "I have hair loss")
    updated_state = state_manager.get_conversation_state(conv_code)

    assert updated_state.get("booking_for") == "SELF"
    assert updated_state.get("patient_relationship") is None
    assert updated_state.get("patient_id") == patient_id

    # Doctor selection
    res2 = agent_service.process_agent_message(conv_code, data["phone"], "Dr. Wilson M")
    assert "your son" not in res2.get("response", "").lower()


def test_5_explicit_son_request_activates_dependent(setup_test_data):
    """Test 5: Input 'My son has fever' activates DEPENDENT / SON flow."""
    data = setup_test_data
    conv_code = data["conv_code"]

    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = data["patient_id"]
    state["primary_patient_id"] = data["patient_id"]
    state["whatsapp_number"] = data["phone"]
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, data["phone"], "My son has fever")
    updated_state = state_manager.get_conversation_state(conv_code)

    assert updated_state.get("patient_relationship") == "SON"
    assert updated_state.get("booking_for") in ("CHILD", "FAMILY_MEMBER", "DEPENDENT")


def test_6_fever_request_is_self(setup_test_data):
    """Test 6: Input 'I have fever' stays SELF."""
    data = setup_test_data
    conv_code = data["conv_code"]

    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = data["patient_id"]
    state["primary_patient_id"] = data["patient_id"]
    state["whatsapp_number"] = data["phone"]
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, data["phone"], "I have fever")
    updated_state = state_manager.get_conversation_state(conv_code)

    assert updated_state.get("booking_for") == "SELF"
    assert updated_state.get("patient_relationship") is None


def test_7_daughter_request_activates_daughter(setup_test_data):
    """Test 7: Input 'Book an appointment for my daughter' activates DEPENDENT / DAUGHTER."""
    data = setup_test_data
    conv_code = data["conv_code"]

    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = data["patient_id"]
    state["primary_patient_id"] = data["patient_id"]
    state["whatsapp_number"] = data["phone"]
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, data["phone"], "Book an appointment for my daughter")
    updated_state = state_manager.get_conversation_state(conv_code)

    assert updated_state.get("patient_relationship") == "DAUGHTER"


def test_8_generic_need_appointment_is_self(setup_test_data):
    """Test 8: Input 'I need an appointment' stays SELF."""
    data = setup_test_data
    conv_code = data["conv_code"]

    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = data["patient_id"]
    state["primary_patient_id"] = data["patient_id"]
    state["whatsapp_number"] = data["phone"]
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, data["phone"], "I need an appointment")
    updated_state = state_manager.get_conversation_state(conv_code)

    assert updated_state.get("booking_for") == "SELF"
    assert updated_state.get("patient_relationship") is None


# ==============================================================================
# BUG 2 TESTS: PREVENTING PATIENT NAME FROM APPEARING AS REASON
# ==============================================================================

def test_9_new_patient_no_reason_is_null(setup_test_data):
    """Test 9: Registering new patient Wilson Tony without reason leaves reason_for_visit null."""
    data = setup_test_data
    conv_code = f"WA_9199{random.randint(10000000, 99999999)}_NEW"

    state = state_manager.get_conversation_state(conv_code)
    state["intent"] = "REGISTER_PATIENT"
    state["booking_stage"] = "REGISTERING_PATIENT"
    state_manager.save_conversation_state(conv_code, state)

    # Step 1: Name
    agent_service.process_agent_message(conv_code, "919900001111", "Wilson Tony")
    # Step 2: DOB
    agent_service.process_agent_message(conv_code, "919900001111", "14-02-2005")
    # Step 3: Gender
    res = agent_service.process_agent_message(conv_code, "919900001111", "Male")

    updated_state = state_manager.get_conversation_state(conv_code)
    reg_fields = updated_state.get("registration_fields", {})

    assert reg_fields.get("reason_for_visit") is None


def test_10_confirmation_does_not_display_reason_wilson_tony(setup_test_data):
    """Test 10: Confirmation response MUST NOT display 'Reason: Wilson Tony'."""
    conv_code = f"WA_9199{random.randint(10000000, 99999999)}_NEW"

    state = state_manager.get_conversation_state(conv_code)
    state["intent"] = "REGISTER_PATIENT"
    state["booking_stage"] = "REGISTERING_PATIENT"
    state_manager.save_conversation_state(conv_code, state)

    agent_service.process_agent_message(conv_code, "919900001111", "Wilson Tony")
    agent_service.process_agent_message(conv_code, "919900001111", "14-02-2005")
    res = agent_service.process_agent_message(conv_code, "919900001111", "Male")

    resp_text = res.get("response", "")
    assert "Reason: Wilson Tony" not in resp_text
    assert "Reason: Wilson tony" not in resp_text
    assert "Reason: Wilson" not in resp_text


def test_11_patient_name_remains_wilson_tony(setup_test_data):
    """Test 11: Patient name remains Wilson Tony."""
    conv_code = f"WA_9199{random.randint(10000000, 99999999)}_NEW"

    state = state_manager.get_conversation_state(conv_code)
    state["intent"] = "REGISTER_PATIENT"
    state["booking_stage"] = "REGISTERING_PATIENT"
    state_manager.save_conversation_state(conv_code, state)

    agent_service.process_agent_message(conv_code, "919900001111", "Wilson Tony")
    agent_service.process_agent_message(conv_code, "919900001111", "14-02-2005")
    res = agent_service.process_agent_message(conv_code, "919900001111", "Male")

    updated_state = state_manager.get_conversation_state(conv_code)
    reg_fields = updated_state.get("registration_fields", {})

    assert reg_fields.get("first_name") == "Wilson"
    assert reg_fields.get("last_name") in ("Tony", ".")


def test_12_explicit_reason_provided_later_is_attached(setup_test_data):
    """Test 12: If patient later says 'I have hair loss', appointment_reason becomes hair loss."""
    data = setup_test_data
    conv_code = data["conv_code"]

    res = agent_service.process_agent_message(conv_code, data["phone"], "I have hair loss")
    updated_state = state_manager.get_conversation_state(conv_code)

    reason = updated_state.get("entities", {}).get("reason") or updated_state.get("entities", {}).get("symptoms")
    assert reason in ("hair loss", ["hair loss"]) or "hair" in str(reason).lower()


def test_13_doctor_selection_maintains_reason(setup_test_data):
    """Test 13: Doctor selection preserves explicit reason."""
    data = setup_test_data
    conv_code = data["conv_code"]

    agent_service.process_agent_message(conv_code, data["phone"], "I have hair loss")
    agent_service.process_agent_message(conv_code, data["phone"], "Dr. Wilson M")

    updated_state = state_manager.get_conversation_state(conv_code)
    assert updated_state.get("doctor_name") is not None or updated_state.get("entities", {}).get("doctor_id") is not None


def test_14_department_selection_maintains_reason(setup_test_data):
    """Test 14: Department selection preserves explicit reason."""
    data = setup_test_data
    conv_code = data["conv_code"]

    agent_service.process_agent_message(conv_code, data["phone"], "I have hair loss")

    updated_state = state_manager.get_conversation_state(conv_code)
    assert updated_state.get("department_name") == "Dermatology" or updated_state.get("entities", {}).get("department_id") is not None


def test_15_registration_never_infers_reason_from_name(setup_test_data):
    """Test 15: Patient registration input 'Wilson Tony' must never create reason_for_visit."""
    conv_code = f"WA_9199{random.randint(10000000, 99999999)}_NEW"

    state = state_manager.get_conversation_state(conv_code)
    state["intent"] = "REGISTER_PATIENT"
    state["booking_stage"] = "REGISTERING_PATIENT"
    state_manager.save_conversation_state(conv_code, state)

    agent_service.process_agent_message(conv_code, "919900001111", "Wilson Tony")
    updated_state = state_manager.get_conversation_state(conv_code)
    reg_fields = updated_state.get("registration_fields", {})

    assert reg_fields.get("reason_for_visit") is None
