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

def setup_clean_conversation(conv_code="WA_TEST_DATE_SUITE_100"):
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    state = state_manager.get_conversation_state(conv_code, whatsapp_number="9199999001")
    state["patient_id"] = 1
    state["entities"] = {
        "patient_id": 1,
        "doctor_id": None,
        "department_id": None,
        "appointment_date": None,
        "appointment_time": None,
        "booking_id": None,
        "reason": "General Checkup"
    }
    state["booking_stage"] = None
    state["previous_question"] = None
    state["confirmation_pending"] = False
    state["confirmation_details"] = {}
    state_manager.save_conversation_state(conv_code, state)
    return conv_code

# --- 1. Suggested date has real availability ---
def test_scenario_1_suggested_date_has_real_availability():
    conv_code = setup_clean_conversation("WA_TEST_DATE_S1")
    # Tap doctor button for Dr. Wilson M (ID 10)
    res = agent_service.process_agent_message(conv_code, None, "btn_doc_10")
    buttons = res.get("interactive_buttons", [])
    
    # Check if date buttons are returned
    date_buttons = [b for b in buttons if b["id"].startswith("btn_date_")]
    if date_buttons:
        for b in date_buttons:
            date_str = b["id"].replace("btn_date_", "")
            slot_res = tool_registry.tool_get_available_slots(conv_code, 10, date_str)
            slots = slot_res.get("slots", [])
            assert len(slots) > 0, f"Date button {b['id']} has 0 slots in DB!"

# --- 2. Suggested date with no availability is NEVER shown ---
def test_scenario_2_suggested_date_has_no_availability_never_shown():
    conv_code = setup_clean_conversation("WA_TEST_DATE_S2")
    # Dr. Wilson M (ID 10) works only Mon & Wed.
    valid_dates = agent_service.get_verified_doctor_available_dates(conv_code, 10, start_offset=1, max_days=14)
    valid_date_strings = {d["date"] for d in valid_dates}

    # Query every upcoming date for 14 days and ensure dates with 0 slots are NOT in valid_date_strings
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.datetime.now(ist).date()
    for offset in range(1, 15):
        d_str = (today + datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
        slot_res = tool_registry.tool_get_available_slots(conv_code, 10, d_str)
        slots = slot_res.get("slots", [])
        if len(slots) == 0:
            assert d_str not in valid_date_strings, f"Date {d_str} with 0 slots was incorrectly returned in valid_dates!"

# --- 3. Slot becomes unavailable after date selection ---
def test_scenario_3_slot_becomes_unavailable_after_date_selection():
    conv_code = setup_clean_conversation("WA_TEST_DATE_S3")
    state = state_manager.get_conversation_state(conv_code)
    state["entities"]["doctor_id"] = 5
    state["entities"]["appointment_date"] = "2026-09-15"
    state_manager.save_conversation_state(conv_code, state)

    # Tap a non-existent/unavailable slot e.g. btn_slot_04:00
    res = agent_service.process_agent_message(conv_code, None, "btn_slot_04:00")
    # Should decline slot 04:00 and provide updated slots/dates without crashing
    assert "no longer available" in res["response"] or "Available" in res["response"] or "Please choose" in res["response"]

# --- 4. Multiple available dates ---
def test_scenario_4_multiple_available_dates():
    conv_code = setup_clean_conversation("WA_TEST_DATE_S4")
    # Dr. Arun Kumar (ID 5) usually has multiple working days
    doc_info = agent_service.resolve_doctor_details(5)
    state = state_manager.get_conversation_state(conv_code)
    res = agent_service.build_verified_date_selection_response(conv_code, state, 5, doc_info)
    buttons = res.get("interactive_buttons", [])
    if len(buttons) > 1:
        assert all(b["id"].startswith("btn_date_") for b in buttons)
        assert "Available dates for Dr. Arun Kumar" in res["response"]

# --- 5. Only one available date (Auto-Advance) ---
def test_scenario_5_only_one_available_date(monkeypatch):
    conv_code = setup_clean_conversation("WA_TEST_DATE_S5")
    doc_info = agent_service.resolve_doctor_details(10)
    state = state_manager.get_conversation_state(conv_code)

    # Mock get_verified_doctor_available_dates to return exactly 1 date with multiple slots
    mock_dates = [{
        "date": "2026-09-28",
        "title": "Mon, Sep 28",
        "slots": ["09:00", "10:00"],
        "count": 2
    }]
    monkeypatch.setattr(agent_service, "get_verified_doctor_available_dates", lambda code, doc_id: mock_dates)

    res = agent_service.build_verified_date_selection_response(conv_code, state, 10, doc_info)
    # Must auto-advance directly to slot selection!
    buttons = res.get("interactive_buttons", [])
    assert len(buttons) == 2
    assert all(b["id"].startswith("btn_slot_") for b in buttons)
    assert "Available time slots for Dr. Wilson M on 2026-09-28" in res["response"]

# --- 6. No available dates ---
def test_scenario_6_no_available_dates(monkeypatch):
    conv_code = setup_clean_conversation("WA_TEST_DATE_S6")
    doc_info = agent_service.resolve_doctor_details(10)
    state = state_manager.get_conversation_state(conv_code)

    # Mock get_verified_doctor_available_dates to return []
    monkeypatch.setattr(agent_service, "get_verified_doctor_available_dates", lambda code, doc_id: [])

    res = agent_service.build_verified_date_selection_response(conv_code, state, 10, doc_info)
    buttons = res.get("interactive_buttons", [])
    assert len(buttons) == 0
    assert "has no available slots in the upcoming schedule" in res["response"]

# --- 7. Patient types a date instead of pressing a button ---
def test_scenario_7_patient_types_date_instead_of_button():
    conv_code = setup_clean_conversation("WA_TEST_DATE_S7")
    # First set doctor ID 10 in state
    state = state_manager.get_conversation_state(conv_code)
    state["entities"]["doctor_id"] = 10
    state["conversation_state"] = "DATE_REQUIRED"
    state_manager.save_conversation_state(conv_code, state)

    # Patient types "next Monday" or a specific date e.g. "Monday"
    res = agent_service.process_agent_message(conv_code, None, "Monday")
    assert res.get("response") is not None
    # Should recognize intent/date and offer slots or auto-advance
    assert "Available" in res["response"] or "confirm" in res["response"].lower() or "Doctor" in res["response"] or "reason" in res["response"].lower()

if __name__ == "__main__":
    pytest.main(["-v", __file__])
