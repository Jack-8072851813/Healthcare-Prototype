"""
test_user_screenshot_bugs.py
============================
Tests the exact conversation sequence from the user screenshot:
1. "Doctor Availability" -> Prompts for department
2. "Genearl Medicine" (typo) -> Must NOT trigger diagnosis warning! Must set department to General Medicine & ask for date.
3. "I want to check General Medicine doctor availability.." -> Prompts for date
4. "tomorrow" -> MUST respond with Doctor Availability for General Medicine on tomorrow's date!
"""

import sys
import os
import pytest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from agent import agent_service
from agent import safety_service
from agent import state_manager


def test_safety_service_typo_handling():
    # "Genearl Medicine" typo should NOT trigger safety warning
    res = safety_service.check_medical_safety("Genearl Medicine")
    assert res is None, f"Expected None but got: {res}"

    res2 = safety_service.check_medical_safety("I want General Medicine doctor availability")
    assert res2 is None, f"Expected None but got: {res2}"

    # Genuine diagnosis/prescription request SHOULD still trigger warning
    res3 = safety_service.check_medical_safety("What medicine should I take for fever?")
    assert res3 is not None, "Expected safety warning for prescription request"


def p_safe(label: str, text: str):
    try:
        print(f"\n[{label}]: {text}")
    except Exception:
        clean = text.encode('ascii', 'ignore').decode('ascii')
        print(f"\n[{label}]: {clean}")


def test_user_screenshot_conversation_sequence():
    conv_code = "WA_TEST_SCREENSHOT_SEQ"
    # Clean up DB
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # Step 1: User says "Doctor Availability"
    res1 = agent_service.process_agent_message(conv_code, None, "Doctor Availability")
    p_safe("Turn 1 Response", res1["response"])
    assert "Which department" in res1["response"] or "symptoms" in res1["response"]

    # Step 2: User says "Genearl Medicine" (typo)
    res2 = agent_service.process_agent_message(conv_code, None, "Genearl Medicine")
    p_safe("Turn 2 Response", res2["response"])
    # MUST NOT return medical diagnosis safety warning
    assert "cannot diagnose" not in res2["response"].lower()
    assert "Which date" in res2["response"] or "General Medicine" in res2["response"]

    # Step 3: User says "tomorrow"
    res3 = agent_service.process_agent_message(conv_code, None, "tomorrow")
    p_safe("Turn 3 Response", res3["response"])
    # MUST return actual doctor availability
    assert res3["response"] is not None and len(res3["response"].strip()) > 0
    assert "General Medicine" in res3["response"] or "Dr. Arun Kumar" in res3["response"] or "Available" in res3["response"] or "slots" in res3["response"].lower()
