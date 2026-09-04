"""
test_whatsapp_architecture_fix.py
===================================
Comprehensive test suite verifying the fixed WhatsApp Patient Desk conversation architecture
and testing all 16 required scenarios.
"""

import sys
import os
import pytest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from agent import agent_service
from agent import state_manager
from agent import llm_intent_router


def reset_session(conv_code: str):
    """Resets conversation and messages in DB for a clean test run."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def p_safe(label: str, text: str):
    try:
        print(f"\n[{label}]: {text}")
    except Exception:
        clean = text.encode('ascii', 'ignore').decode('ascii')
        print(f"\n[{label}]: {clean}")


def test_scenario_1_book_appointment():
    """Scenario 1: 'Book appointment' without symptom or doctor preference."""
    conv_code = "WA_TEST_ARCH_01"
    reset_session(conv_code)
    
    res = agent_service.process_agent_message(conv_code, None, "Book appointment")
    p_safe("Scenario 1 Response", res["response"])

    # 1. Must NOT select any doctor
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None
    assert state["doctor_name"] is None

    # 2. Must ask for symptom/reason
    assert "Sure! I can help you book an appointment" in res["response"]
    assert "What health problem, symptom, or reason" in res["response"] or "health problem" in res["response"]


def test_scenario_2_hair_fall():
    """Scenario 2: 'I have hair fall' -> Dermatology."""
    conv_code = "WA_TEST_ARCH_02"
    reset_session(conv_code)
    
    res = agent_service.process_agent_message(conv_code, None, "I have hair fall")
    p_safe("Scenario 2 Response", res["response"])

    assert "Dermatology" in res["response"] or "Dermatologist" in res["response"]
    assert "Which doctor" in res["response"] or "available" in res["response"]
    
    state = state_manager.get_conversation_state(conv_code)
    # Doctor should NOT be auto-selected
    assert state["entities"]["doctor_id"] is None


def test_scenario_3_fever():
    """Scenario 3: 'I have fever' -> General Medicine."""
    conv_code = "WA_TEST_ARCH_03"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I have fever")
    p_safe("Scenario 3 Response", res["response"])

    assert "General Medicine" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None


def test_scenario_4_fever_and_cough():
    """Scenario 4: 'I have fever and cough' -> General Medicine."""
    conv_code = "WA_TEST_ARCH_04"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I have fever and cough")
    p_safe("Scenario 4 Response", res["response"])

    assert "General Medicine" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None


def test_scenario_5_chest_hurts():
    """Scenario 5: 'My chest hurts' -> Cardiology."""
    conv_code = "WA_TEST_ARCH_05"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "My chest hurts")
    p_safe("Scenario 5 Response", res["response"])

    assert "Cardiology" in res["response"] or "Cardiologist" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None


def test_scenario_6_knee_pain():
    """Scenario 6: 'I have knee pain' -> Orthopedics."""
    conv_code = "WA_TEST_ARCH_06"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I have knee pain")
    p_safe("Scenario 6 Response", res["response"])

    assert "Orthopedics" in res["response"] or "Orthopedist" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None


def test_scenario_7_dermatologist():
    """Scenario 7: 'I want a dermatologist' -> Dermatology."""
    conv_code = "WA_TEST_ARCH_07"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I want a dermatologist")
    p_safe("Scenario 7 Response", res["response"])

    assert "Dermatology" in res["response"] or "Dermatologist" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None


def test_scenario_8_explicit_doctor_request():
    """Scenario 8: 'I want Dr. Arun Kumar' -> Explicit Doctor Selection."""
    conv_code = "WA_TEST_ARCH_08"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I want Dr. Arun Kumar")
    p_safe("Scenario 8 Response", res["response"])

    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is not None
    assert "Arun" in res["response"] or (state.get("doctor_name") and "Arun" in state["doctor_name"])


def test_scenario_9_tomorrow_morning():
    """Scenario 9: 'I need an appointment tomorrow morning' without symptom."""
    conv_code = "WA_TEST_ARCH_09"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I need an appointment tomorrow morning")
    p_safe("Scenario 9 Response", res["response"])

    state = state_manager.get_conversation_state(conv_code)
    # Doctor should NOT be assigned
    assert state["entities"]["doctor_id"] is None
    assert "reason" in res["response"].lower() or "symptom" in res["response"].lower() or "health problem" in res["response"].lower() or "sure" in res["response"].lower()


def test_scenario_10_child_fever():
    """Scenario 10: 'I want to book an appointment for my son, he has fever' -> Pediatrics."""
    conv_code = "WA_TEST_ARCH_10"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I want to book an appointment for my son, he has fever")
    p_safe("Scenario 10 Response", res["response"])

    assert "Pediatrics" in res["response"] or "Pediatrician" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["appointment_for"] in ["CHILD", "FAMILY_MEMBER"]
    assert state["entities"]["doctor_id"] is None


def test_scenario_11_for_daughter():
    """Scenario 11: 'I want to book for my daughter'."""
    conv_code = "WA_TEST_ARCH_11"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I want to book for my daughter")
    p_safe("Scenario 11 Response", res["response"])

    state = state_manager.get_conversation_state(conv_code)
    assert state["appointment_for"] in ["CHILD", "FAMILY_MEMBER"]
    assert state["entities"]["doctor_id"] is None


def test_scenario_12_dont_feel_well():
    """Scenario 12: 'I don't feel well' -> Ambiguous Symptom Prompt."""
    conv_code = "WA_TEST_ARCH_12"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I don't feel well")
    p_safe("Scenario 12 Response", res["response"])

    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None
    assert "describe" in res["response"].lower() or "symptom" in res["response"].lower() or "health issue" in res["response"].lower()


def test_scenario_13_have_pain():
    """Scenario 13: 'I have pain' -> Ambiguous Pain Prompt."""
    conv_code = "WA_TEST_ARCH_13"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I have pain")
    p_safe("Scenario 13 Response", res["response"])

    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None
    assert "Could you tell me where you are experiencing the pain" in res["response"] or "chest" in res["response"].lower() or "where" in res["response"].lower()


def test_scenario_14_skin_itchy():
    """Scenario 14: 'My skin is itchy' -> Dermatology."""
    conv_code = "WA_TEST_ARCH_14"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "My skin is itchy")
    p_safe("Scenario 14 Response", res["response"])

    assert "Dermatology" in res["response"] or "Dermatologist" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None


def test_scenario_15_acne():
    """Scenario 15: 'I have acne' -> Dermatology."""
    conv_code = "WA_TEST_ARCH_15"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I have acne")
    p_safe("Scenario 15 Response", res["response"])

    assert "Dermatology" in res["response"] or "Dermatologist" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None


def test_scenario_16_pregnant():
    """Scenario 16: 'I am pregnant' -> Gynecology."""
    conv_code = "WA_TEST_ARCH_16"
    reset_session(conv_code)

    res = agent_service.process_agent_message(conv_code, None, "I am pregnant")
    p_safe("Scenario 16 Response", res["response"])

    assert "Gynecology" in res["response"] or "Gynecologist" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None
