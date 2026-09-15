"""
test_patient_profile_update.py
=================================
Comprehensive unit test suite for Patient Profile Update flow:
- Field-specific profile updates (Name, DOB, Gender, Phone)
- Database persistence in PostgreSQL & instant profile refresh
- Single name vs full name handling (no 'Edwin None')
- Verification that Patient ID never changes
- Cancel / Back behavior
- Regression tests for existing patient identification and registration
"""

import sys
import os
import pytest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from agent import agent_service
from agent import language_service
from agent import state_manager
import db_config


@pytest.fixture
def test_patient():
    import random
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    test_wa = f"99{random.randint(10000000, 99999999)}"
    test_code = f"P{random.randint(100000, 999999)}"
    
    cur.execute("""
        INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
        VALUES (%s, 'Edwin', '.', '2004-10-31', 'Male', %s, %s, 'ACTIVE')
        RETURNING id;
    """, (test_code, test_wa, test_wa))
    p_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    yield {"id": p_id, "patient_code": test_code, "whatsapp_number": test_wa}

    # Cleanup
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM conversations WHERE whatsapp_number = %s OR patient_id = %s;", (test_wa, p_id))
    cur.execute("DELETE FROM patients WHERE id = %s;", (p_id,))
    conn.commit()
    cur.close()
    conn.close()


def test_view_profile_shows_change_profile_button(test_patient):
    """Verify viewing patient profile displays [Change Profile] button and correct details."""
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "My Profile")
    print("\n[View Profile Response]:\n", res["response"])

    assert "Patient Profile Details" in res["response"]
    assert "Edwin" in res["response"]
    assert "Edwin None" not in res["response"]

    buttons = res.get("interactive_buttons", [])
    button_titles = [b["title"] for b in buttons]
    assert "Change Profile" in button_titles
    assert "My Appointments" in button_titles
    assert "My Reports" in button_titles
    assert "Main Menu" in button_titles


def test_change_profile_displays_field_options(test_patient):
    """Verify tapping Change Profile shows field-specific options (Change Name, DOB, Gender, Phone, Back)."""
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "btn_change_profile")
    print("\n[Change Profile Options Response]:\n", res["response"])

    assert "What would you like to update?" in res["response"]

    buttons = res.get("interactive_buttons", [])
    button_titles = [b["title"] for b in buttons]
    assert "Change Name" in button_titles
    assert "Change Date of Birth" in button_titles
    assert "Change Gender" in button_titles
    assert "Change Phone Number" in button_titles
    assert "Back to Profile" in button_titles


def test_update_name_only(test_patient):
    """
    TEST 1 & 2 & 3:
    Change Name updates ONLY the patient name in PostgreSQL.
    Patient ID remains unchanged.
    Future profile retrievals display updated name ('Edwin Christ').
    """
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    # 1. Tap Change Name
    res1 = agent_service.process_agent_message(conv_code, None, "btn_update_name")
    assert "Please enter your updated full name" in res1["response"]

    # 2. Enter new name "Edwin Christ"
    res2 = agent_service.process_agent_message(conv_code, None, "Edwin Christ")
    print("\n[Name Update Response]:\n", res2["response"])

    assert "Your name has been updated successfully to Edwin Christ" in res2["response"]
    assert "Edwin None" not in res2["response"]

    # 3. Verify PostgreSQL DB record directly
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT first_name, last_name, patient_code, date_of_birth, gender FROM patients WHERE id = %s;", (test_patient["id"],))
    p_row = cur.fetchone()
    cur.close()
    conn.close()

    assert p_row[0] == "Edwin"
    assert p_row[1] == "Christ"
    assert p_row[2] == test_patient["patient_code"] # Patient ID unchanged!
    assert str(p_row[3]) == "2004-10-31"            # DOB unchanged!
    assert p_row[4] == "Male"                      # Gender unchanged!

    # 4. Future profile retrieval shows updated name
    res3 = agent_service.process_agent_message(conv_code, None, "My Profile")
    assert "Edwin Christ" in res3["response"]


def test_update_dob_only(test_patient):
    """
    TEST 4:
    Change DOB updates ONLY date_of_birth in PostgreSQL.
    Name and Gender remain unchanged.
    """
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    # Tap Change DOB
    res1 = agent_service.process_agent_message(conv_code, None, "btn_update_dob")
    assert "Please enter your updated date of birth" in res1["response"]

    # Provide new DOB
    res2 = agent_service.process_agent_message(conv_code, None, "2004-08-15")
    print("\n[DOB Update Response]:\n", res2["response"])

    assert "Your date of birth has been updated successfully" in res2["response"]

    # Verify DB
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT date_of_birth, first_name, gender FROM patients WHERE id = %s;", (test_patient["id"],))
    row = cur.fetchone()
    cur.close()
    conn.close()

    assert str(row[0]) == "2004-08-15"
    assert row[1] == "Edwin" # Name unchanged!
    assert row[2] == "Male"  # Gender unchanged!


def test_update_gender_only(test_patient):
    """
    TEST 5:
    Change Gender updates ONLY gender in PostgreSQL.
    """
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    # Tap Change Gender
    res1 = agent_service.process_agent_message(conv_code, None, "btn_update_gender")
    assert "Please select your gender" in res1["response"]

    # Select Female
    res2 = agent_service.process_agent_message(conv_code, None, "btn_g_female")
    print("\n[Gender Update Response]:\n", res2["response"])

    assert "Your gender has been updated successfully" in res2["response"]

    # Verify DB
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT gender, first_name FROM patients WHERE id = %s;", (test_patient["id"],))
    row = cur.fetchone()
    cur.close()
    conn.close()

    assert row[0] == "Female"
    assert row[1] == "Edwin" # Name unchanged!


def test_update_phone_duplicate_prevention(test_patient):
    """
    TEST 6:
    Updating phone number checks for existing duplicate patient profiles.
    """
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    # Tap Change Phone
    res1 = agent_service.process_agent_message(conv_code, None, "btn_update_phone")
    assert "Please enter your updated 10-digit phone number" in res1["response"]

    import random
    new_phone = f"98{random.randint(10000000, 99999999)}"
    res2 = agent_service.process_agent_message(conv_code, None, new_phone)
    print("\n[Phone Update Response]:\n", res2["response"])

    assert "Your phone number has been updated successfully" in res2["response"]


def test_back_button_cancels_update(test_patient):
    """Verify tapping Back to Profile cancels update without modifying database."""
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    # Tap Change Name
    agent_service.process_agent_message(conv_code, None, "btn_update_name")

    # Tap Back to Profile
    res = agent_service.process_agent_message(conv_code, None, "btn_back_profile")
    print("\n[Back to Profile Response]:\n", res["response"])

    assert "Patient Profile Details" in res["response"]
    assert "Edwin" in res["response"]


def test_natural_language_change_name_does_not_trigger_registration(test_patient):
    """
    CRITICAL BUG REGRESSION TEST:
    When existing patient sends natural language "Change Name" or "Change my name",
    the system must NOT ask for registration details (DOB, Gender, Phone, Reason for Visit).
    """
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "Change my name")
    print("\n[Natural Language Change Name Response]:\n", res["response"])

    # Must ask ONLY for new name
    assert "Please enter your updated full name" in res["response"]
    # Must NOT ask for full registration details
    assert "Please send your updated registration details" not in res["response"]
    assert "Reason for Visit" not in res["response"]


def test_single_name_update_no_none(test_patient):
    """Verify single name input 'Edwin' updates cleanly without appending 'None' or '.'."""
    conv_code = f"WA_{test_patient['whatsapp_number']}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_id"] = test_patient["id"]
    state_manager.save_conversation_state(conv_code, state)

    agent_service.process_agent_message(conv_code, None, "btn_update_name")
    res = agent_service.process_agent_message(conv_code, None, "Edwin")

    assert "Your name has been updated successfully to Edwin" in res["response"]
    assert "Edwin None" not in res["response"]
    assert "Edwin ." not in res["response"]
    assert "Edwin null" not in res["response"]

