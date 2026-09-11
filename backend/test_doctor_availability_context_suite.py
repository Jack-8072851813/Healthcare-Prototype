import sys
import os
import pytest
import datetime
import pytz

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import db_config
from agent import agent_service, state_manager, tool_registry

# Dr. Ajay L is Doctor ID 14 (Department: Pediatrics, ID 19)
# Dr. Wilson M is Doctor ID 10 (Department: Dermatology, ID 21)
AJAY_DOC_ID = 14
AJAY_DOC_NAME = "Dr. Ajay L"
AJAY_DEPT_NAME = "Pediatrics"

WILSON_DOC_ID = 10
WILSON_DOC_NAME = "Dr. Wilson M"

def setup_clean_conversation(conv_code="WA_TEST_CTX_SUITE_100"):
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    state = state_manager.get_conversation_state(conv_code, whatsapp_number="9199999002")
    state["patient_id"] = 1
    state["entities"] = {
        "patient_id": 1,
        "doctor_id": None,
        "department_id": None,
        "appointment_date": None,
        "appointment_time": None,
        "booking_id": None,
        "reason": "Pediatric Consultation"
    }
    state["booking_stage"] = None
    state["previous_question"] = None
    state["confirmation_pending"] = False
    state["confirmation_details"] = {}
    state_manager.save_conversation_state(conv_code, state)
    return conv_code

# Test Case 1: Select Dr. Ajay L -> type "Friday"
def test_case_1_select_dr_ajay_l_type_friday():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC1")
    # Step 1: Select Dr. Ajay L via button
    res1 = agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")
    assert AJAY_DOC_NAME in res1["response"]

    # Step 2: Patient types "Friday"
    res2 = agent_service.process_agent_message(conv_code, None, "Friday")
    assert AJAY_DOC_NAME in res2["response"]
    assert WILSON_DOC_NAME not in res2["response"]
    assert "Dermatology" not in res2["response"]

# Test Case 2: Select Dr. Ajay L -> type "Tomorrow"
def test_case_2_select_dr_ajay_l_type_tomorrow():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC2")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")
    res2 = agent_service.process_agent_message(conv_code, None, "Tomorrow")
    assert AJAY_DOC_NAME in res2["response"]
    assert WILSON_DOC_NAME not in res2["response"]

# Test Case 3: Select Dr. Ajay L -> type "Monday"
def test_case_3_select_dr_ajay_l_type_monday():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC3")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")
    res2 = agent_service.process_agent_message(conv_code, None, "Monday")
    assert AJAY_DOC_NAME in res2["response"]
    assert WILSON_DOC_NAME not in res2["response"]

# Test Case 4: Select Dr. Ajay L -> click Friday button
def test_case_4_select_dr_ajay_l_click_friday_button():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC4")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")
    
    # Calculate next Friday date string YYYY-MM-DD
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.datetime.now(ist).date()
    days_ahead = (4 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_friday = (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    res2 = agent_service.process_agent_message(conv_code, None, f"btn_date_{next_friday}")
    assert AJAY_DOC_NAME in res2["response"]
    assert WILSON_DOC_NAME not in res2["response"]

# Test Case 5: Select Dr. Ajay L -> type "10 AM"
def test_case_5_select_dr_ajay_l_type_10am():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC5")
    # Select doctor via button tap and set date
    agent_service.process_agent_message(conv_code, None, "btn_doc_14")
    state = state_manager.get_conversation_state(conv_code)
    state["entities"]["appointment_date"] = "2026-09-15"
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "10 AM")
    # 10 AM must be interpreted as time slot for Dr. Ajay L, NOT a new doctor search
    assert AJAY_DOC_NAME in res["response"] or "confirm" in res["response"].lower() or "Available" in res["response"] or "10:00" in res["response"]
    assert WILSON_DOC_NAME not in res["response"]

# Test Case 6: Select Dr. Ajay L -> type "Change doctor"
def test_case_6_select_dr_ajay_l_type_change_doctor():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC6")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")
    
    res = agent_service.process_agent_message(conv_code, None, "Change doctor")
    # Explicit "Change doctor" MUST start doctor selection workflow
    assert "doctor" in res["response"].lower() or "department" in res["response"].lower()

# Test Case 7: Select Dr. Ajay L -> "Friday" -> no slots
def test_case_7_select_dr_ajay_l_friday_no_slots(monkeypatch):
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC7")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")

    # Mock tool_get_available_slots to return [] for Friday
    monkeypatch.setattr(tool_registry, "tool_get_available_slots", lambda code, doc_id, date: {"success": True, "slots": []})

    res = agent_service.process_agent_message(conv_code, None, "Friday")
    # Must offer alternative dates for Dr. Ajay L, NOT switch to Dr. Wilson M!
    assert AJAY_DOC_NAME in res["response"]
    assert WILSON_DOC_NAME not in res["response"]

# Test Case 8: Select Dr. Ajay L -> "Friday" -> slots available
def test_case_8_select_dr_ajay_l_friday_slots_available(monkeypatch):
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC8")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")

    # Mock tool_get_available_slots to return slots for Dr. Ajay L
    monkeypatch.setattr(tool_registry, "tool_get_available_slots", lambda code, doc_id, date: {"success": True, "slots": ["09:00", "10:00", "11:00"]})

    res = agent_service.process_agent_message(conv_code, None, "Friday")
    assert AJAY_DOC_NAME in res["response"]
    assert "09:00" in res["response"] or "9:00 AM" in res["response"] or "10:00 AM" in res["response"]
    assert WILSON_DOC_NAME not in res["response"]

# Test Case 9: Select Dr. Ajay L -> previous stale context contains Dr. Wilson M
def test_case_9_select_dr_ajay_l_previous_stale_context_contains_dr_wilson():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC9")
    state = state_manager.get_conversation_state(conv_code)
    # Inject stale Dr. Wilson M in state initially
    state["entities"]["doctor_id"] = WILSON_DOC_ID
    state["selected_doctor_id"] = WILSON_DOC_ID
    state["selected_doctor_name"] = WILSON_DOC_NAME
    state["selected_department_id"] = 21
    state["selected_department_name"] = "Dermatology"
    state_manager.save_conversation_state(conv_code, state)

    # Now patient explicitly selects Dr. Ajay L
    res1 = agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")
    assert AJAY_DOC_NAME in res1["response"]
    assert WILSON_DOC_NAME not in res1["response"]

    # Subsequent follow up "Friday" MUST maintain Dr. Ajay L, NOT fall back to stale Dr. Wilson M
    res2 = agent_service.process_agent_message(conv_code, None, "Friday")
    assert AJAY_DOC_NAME in res2["response"]
    assert WILSON_DOC_NAME not in res2["response"]

# Test Case 10: Select Dr. Ajay L -> department Pediatrics
def test_case_10_select_dr_ajay_l_department_pediatrics():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC10")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")
    state = state_manager.get_conversation_state(conv_code)
    assert state["selected_department_name"] == AJAY_DEPT_NAME
    assert state["entities"]["department_id"] == 19

# Test Case 11: Select Dr. Ajay L -> "Friday" -> response department must not become Dermatology
def test_case_11_select_dr_ajay_l_friday_response_department_not_dermatology():
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC11")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")
    res2 = agent_service.process_agent_message(conv_code, None, "Friday")
    assert "Dermatology" not in res2["response"]

# Test Case 12: Select Dr. Ajay L -> "Friday" -> select slot -> slot belongs to Dr. Ajay L
def test_case_12_select_dr_ajay_l_friday_select_slot(monkeypatch):
    conv_code = setup_clean_conversation("WA_TEST_CTX_TC12")
    agent_service.process_agent_message(conv_code, None, f"btn_doc_{AJAY_DOC_ID}")

    # Mock tool_get_available_slots to return 09:00 for Dr. Ajay L
    monkeypatch.setattr(tool_registry, "tool_get_available_slots", lambda code, doc_id, date: {"success": True, "slots": ["09:00", "10:00"]})

    res2 = agent_service.process_agent_message(conv_code, None, "Friday")
    # Tap slot button btn_slot_09:00
    res3 = agent_service.process_agent_message(conv_code, None, "btn_slot_09:00")
    assert AJAY_DOC_NAME in res3["response"]
    assert WILSON_DOC_NAME not in res3["response"]
    assert "Doctor: Dr. Ajay L" in res3["response"] or "Dr. Ajay L" in res3["response"]

if __name__ == "__main__":
    pytest.main(["-v", __file__])
