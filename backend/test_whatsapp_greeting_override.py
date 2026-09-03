"""
test_whatsapp_greeting_override.py
===================================
Tests that sending a greeting message ("hi", "hello") during an active transaction
workflow (e.g. BOOK_APPOINTMENT) correctly overrides the intent to GREETING,
resets stale booking state, and responds with the Meridian Hospital AI Patient Conversational Desk greeting message.
"""

import sys
import os
import pytest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from agent import agent_service
from agent import state_manager


def test_greeting_overrides_active_booking_intent():
    conv_code = "WA_TEST_GREETING_OVERRIDE_1001"
    
    # 1. Setup clean initial state
    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = 1 # Valid test patient
    state["entities"] = {
        "patient_id": 1,
        "doctor_id": 5,
        "department_id": 17,
        "appointment_date": "2026-09-03",
        "appointment_time": None,
        "booking_id": None,
        "reason": "Fever"
    }
    state["booking_stage"] = "AWAITING_SYMPTOM"
    state["confirmation_pending"] = False
    state_manager.save_conversation_state(conv_code, state)

    # 2. Patient sends "hi" during ongoing booking stage
    res = agent_service.process_agent_message(conv_code, None, "hi")
    print("\n[Greeting Override Response]:", res["response"])

    assert res["intent"] == "GREETING"
    assert "Welcome" in res["response"]

    # 3. Check that stale booking flags were cleared in saved state
    updated_state = state_manager.get_conversation_state(conv_code)
    assert updated_state["booking_stage"] is None
    assert updated_state["previous_question"] is None
    assert updated_state["confirmation_pending"] is False
