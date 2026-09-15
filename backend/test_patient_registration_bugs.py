"""
test_patient_registration_bugs.py
===================================
Tests for the 3 targeted patient registration & conversation bug fixes:
1. Bug 1: Full name displaying "None" (e.g. "Edwin None") when single name is provided.
2. Bug 2: Registration completion menu displaying raw internal button IDs such as btn_patient_help.
3. Bug 3: Already registered patients being asked for registration details again.
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


def test_bug1_format_patient_full_name_single_name():
    """Verify format_patient_full_name handles single name, two names, three names, and cleans out None/null/."""
    # Single name
    assert agent_service.format_patient_full_name("Edwin", None) == "Edwin"
    assert agent_service.format_patient_full_name("Edwin", ".") == "Edwin"
    assert agent_service.format_patient_full_name("Edwin", "None") == "Edwin"
    assert agent_service.format_patient_full_name(full_name="Edwin None") == "Edwin"
    assert agent_service.format_patient_full_name(full_name="Edwin .") == "Edwin"
    
    # Double name
    assert agent_service.format_patient_full_name("Edwin", "Christ") == "Edwin Christ"
    assert agent_service.format_patient_full_name(full_name="Edwin Christ") == "Edwin Christ"
    
    # Triple name
    assert agent_service.format_patient_full_name("Edwin", "Christ Kumar") == "Edwin Christ Kumar"
    assert agent_service.format_patient_full_name(full_name="Edwin Christ Kumar") == "Edwin Christ Kumar"


def test_bug2_translated_buttons_no_raw_ids():
    """Verify btn_patient_help and all main menu buttons return human-readable titles, never raw IDs."""
    btn = language_service.get_translated_button("btn_patient_help", "ENGLISH")
    assert btn["title"] == "Talk to Staff"
    assert btn["id"] == "btn_patient_help"
    
    main_menu = language_service.get_main_menu_buttons("ENGLISH")
    titles = [b["title"] for b in main_menu]
    for b in main_menu:
        assert not b["title"].startswith("btn_")
    assert "Talk to Staff" in titles or "Customer Care" in titles or "Emergency" in titles


def test_bug1_and_bug2_registration_flow_single_name():
    """
    Test complete registration flow for a single-name patient 'Edwin'.
    Verifies:
    1. Name is stored & displayed as 'Edwin' (NOT 'Edwin None').
    2. Menu returned upon registration contains clean patient-facing titles (NO btn_patient_help raw ID).
    """
    conv_code = f"WA_TEST_REG_BUG_{os.urandom(4).hex()}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state["patient_identification_stage"] = "REGISTRATION"
    state["registration_fields"] = {
        "first_name": "Edwin",
        "last_name": None,
        "date_of_birth": "2004-09-08",
        "gender": "Male",
        "phone": "9999888877",
        "reason_for_visit": None
    }

    res = agent_service.handle_unknown_patient_identification_flow(conv_code, state, "Male", "ENGLISH", "btn_g_male")

    print("\n[Registration Response]:", res["response"])
    assert "Edwin None" not in res["response"]
    assert "Edwin ." not in res["response"]
    assert "Edwin" in res["response"]
    assert "Meridian Hospital" in res["response"]
    
    # Check interactive buttons menu
    buttons = res.get("interactive_buttons", [])
    assert len(buttons) > 0
    for b in buttons:
        assert not b["title"].startswith("btn_")
        assert "None" not in b["title"]


def test_bug3_already_registered_patient_not_reasked():
    """
    Test that an already registered patient sending a new message
    is NOT asked for Name, DOB, or Gender again.
    """
    # 1. Lookup an active patient in DB
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, whatsapp_number, first_name FROM patients WHERE whatsapp_number IS NOT NULL AND status = 'ACTIVE' LIMIT 1;")
    p_row = cur.fetchone()
    cur.close()
    conn.close()

    if not p_row:
        pytest.skip("No existing patient in DB to test Bug 3 regression")

    pat_id, wa_num, first_name = p_row
    conv_code = f"WA_{wa_num}"

    # Reset state to test automatic restoration of patient identity
    state = state_manager.get_default_state()
    state["conversation_id"] = conv_code
    state_manager.save_conversation_state(conv_code, state)

    # 2. Patient sends "Hi"
    res = agent_service.process_agent_message(conv_code, None, "Hi")
    print(f"\n[Existing Patient Response for {first_name}]:", res["response"])

    # Must NOT ask for registration details
    assert "Please provide your name" not in res["response"]
    assert "Please provide your date of birth" not in res["response"]
    assert "Please select your gender" not in res["response"]
    assert "Are you an existing patient or a first-time visitor" not in res["response"]
