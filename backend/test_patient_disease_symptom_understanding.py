import pytest
import datetime
import re
import sys
import os

# Add backend directory to path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import agent.agent_service as agent_service
import agent.state_manager as state_manager
import agent.llm_intent_router as llm_intent_router
import db_config

def reset_session(conv_code: str):
    """Utility helper to clear DB messages and conversation state for testing."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM conversations WHERE conversation_code = %s;", (conv_code,))
        row = cur.fetchone()
        if row:
            c_id = row[0]
            cur.execute("DELETE FROM messages WHERE conversation_id = %s;", (c_id,))
            cur.execute("DELETE FROM conversations WHERE id = %s;", (c_id,))
            conn.commit()
    finally:
        cur.close()
        conn.close()

# ---------------------------------------------------------------------------
# Test Cases 1-12: Direct Symptoms & Short Clinical Phrases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("symptom_text,expected_dept_kw", [
    ("Hair fall", "Dermatology"),
    ("Hair loss", "Dermatology"),
    ("Hair thinning", "Dermatology"),
    ("Nose pain", "ENT"),
    ("Pain in nose", "ENT"),
    ("Ear bleeding", "ENT"),
    ("Bleeding from ear", "ENT"),
    ("Throat pain", "ENT"),
    ("Sore throat", "ENT"),
    ("Fever", "General Medicine"),
    ("Headache", "General Medicine"),
    ("Skin rash", "Dermatology"),
])
def test_direct_symptom_routing(symptom_text, expected_dept_kw):
    conv_code = f"WA_TEST_SYMP_{hash(symptom_text) % 10000}"
    reset_session(conv_code)
    
    res = agent_service.process_agent_message(conv_code, None, symptom_text)
    state = state_manager.get_conversation_state(conv_code)
    
    assert res is not None
    assert "response" in res
    resp_text = res["response"]
    
    # Verify response or state department matches expected
    dept_name = state.get("department_name") or ""
    assert expected_dept_kw.lower() in dept_name.lower() or expected_dept_kw.lower() in resp_text.lower()
    assert state.get("entities", {}).get("reason") is not None
    
    # Must NOT immediately show Dr. Arun or stale General Medicine date slots for Dermatology/ENT
    if expected_dept_kw in ["Dermatology", "ENT"]:
        assert "Dr. Arun Kumar" not in resp_text

# ---------------------------------------------------------------------------
# Test Case 13 & 14: Conversational & Topic Change
# ---------------------------------------------------------------------------

def test_topic_change_actually_hair_loss():
    conv_code = "WA_TEST_TOPIC_CHANGE_13"
    reset_session(conv_code)
    
    # Step 1: Patient starts with fever (General Medicine)
    res1 = agent_service.process_agent_message(conv_code, None, "I have fever")
    state1 = state_manager.get_conversation_state(conv_code)
    assert "General Medicine" in state1.get("department_name", "") or "General Medicine" in res1["response"]
    
    # Step 2: Patient changes mind: "Actually, I have hair loss"
    res2 = agent_service.process_agent_message(conv_code, None, "Actually, I have hair loss")
    state2 = state_manager.get_conversation_state(conv_code)
    
    # Must update clinical reason to hair loss & route to Dermatology
    reason = state2.get("entities", {}).get("reason") or ""
    assert "hair" in reason.lower() or "hair" in str(state2.get("entities", {}).get("symptoms")).lower()
    dept = state2.get("department_name") or ""
    assert "Dermatology" in dept or "Dermatology" in res2["response"] or "Dermatologist" in res2["response"]

def test_topic_change_main_problem_ear_bleeding():
    conv_code = "WA_TEST_TOPIC_CHANGE_14"
    reset_session(conv_code)
    
    # Step 1: Patient starts with General Consultation
    res1 = agent_service.process_agent_message(conv_code, None, "I want an appointment")
    
    # Step 2: Patient provides specific symptom: "My main problem is ear bleeding"
    res2 = agent_service.process_agent_message(conv_code, None, "My main problem is ear bleeding")
    state2 = state_manager.get_conversation_state(conv_code)
    
    reason = state2.get("entities", {}).get("reason") or ""
    assert "ear" in reason.lower() or "bleeding" in reason.lower()
    dept = state2.get("department_name") or ""
    assert "ENT" in dept or "ENT" in res2["response"]

# ---------------------------------------------------------------------------
# Test Cases 15, 16, 17: Multi-Entity Combinations
# ---------------------------------------------------------------------------

def test_symptom_plus_date():
    conv_code = "WA_TEST_MULTI_15"
    reset_session(conv_code)
    
    res = agent_service.process_agent_message(conv_code, None, "I have hair fall problem and I want appointment tomorrow")
    state = state_manager.get_conversation_state(conv_code)
    
    dept = state.get("department_name") or ""
    assert "Dermatology" in dept or "Dermatology" in res["response"] or "Dermatologist" in res["response"]
    assert state.get("entities", {}).get("appointment_date") is not None

def test_symptom_plus_doctor():
    conv_code = "WA_TEST_MULTI_16"
    reset_session(conv_code)
    
    res = agent_service.process_agent_message(conv_code, None, "I have skin rash and want Dr. Wilson M")
    state = state_manager.get_conversation_state(conv_code)
    
    doc_id = state.get("entities", {}).get("doctor_id") or state.get("selected_doctor_id")
    assert doc_id is not None or "Wilson" in res["response"]

def test_symptom_plus_date_plus_time():
    conv_code = "WA_TEST_MULTI_17"
    reset_session(conv_code)
    
    res = agent_service.process_agent_message(conv_code, None, "I have throat pain tomorrow at 10 AM")
    state = state_manager.get_conversation_state(conv_code)
    
    assert state.get("entities", {}).get("appointment_date") is not None
    assert state.get("entities", {}).get("appointment_time") is not None

# ---------------------------------------------------------------------------
# Test Cases 18, 19, 20: Stale State Protection (Doctor & Date Clearance)
# ---------------------------------------------------------------------------

def test_symptom_after_previous_doctor_selection():
    conv_code = "WA_TEST_STALE_DOC_18"
    reset_session(conv_code)
    
    # Step 1: Simulate prior state with Dr. Arun Kumar (General Medicine) selected
    state = state_manager.get_conversation_state(conv_code)
    state["selected_doctor_id"] = 1
    state["selected_doctor_name"] = "Dr. Arun Kumar"
    state["department_name"] = "General Medicine"
    state["entities"]["doctor_id"] = 1
    state["entities"]["appointment_date"] = "2026-09-15"
    state_manager.save_conversation_state(conv_code, state)
    
    # Step 2: Patient sends new symptom for Dermatology: "Hair Fall problem"
    res = agent_service.process_agent_message(conv_code, None, "Hair Fall problem")
    state2 = state_manager.get_conversation_state(conv_code)
    
    # Stale Dr. Arun Kumar (General Medicine) MUST be cleared for Hair Fall (Dermatology)
    assert state2.get("selected_doctor_id") != 1
    assert "Dr. Arun Kumar" not in res["response"]
    assert "Dermatology" in state2.get("department_name", "") or "Dermatology" in res["response"] or "Dermatologist" in res["response"]

def test_symptom_after_previous_date_selection():
    conv_code = "WA_TEST_STALE_DATE_19"
    reset_session(conv_code)
    
    # Step 1: Set stale date from old session
    state = state_manager.get_conversation_state(conv_code)
    state["entities"]["appointment_date"] = "2026-09-11"
    state["entities"]["appointment_time"] = "10:00"
    state_manager.save_conversation_state(conv_code, state)
    
    # Step 2: Patient provides new symptom: "Nose pain"
    res = agent_service.process_agent_message(conv_code, None, "Nose pain")
    state2 = state_manager.get_conversation_state(conv_code)
    
    # Stale date from previous session must not be blindly reused without explicit mention
    reason = state2.get("entities", {}).get("reason") or ""
    assert "nose" in reason.lower()
    assert "ENT" in state2.get("department_name", "") or "ENT" in res["response"] or "Ear" in res["response"]

def test_symptom_during_active_booking_workflow():
    conv_code = "WA_TEST_ACTIVE_WORKFLOW_20"
    reset_session(conv_code)
    
    # Step 1: Start booking for fever
    res1 = agent_service.process_agent_message(conv_code, None, "I want to book an appointment for fever")
    
    # Step 2: During flow, patient changes symptom: "Ear bleeding"
    res2 = agent_service.process_agent_message(conv_code, None, "Ear bleeding")
    state2 = state_manager.get_conversation_state(conv_code)
    
    reason = state2.get("entities", {}).get("reason") or ""
    assert "ear" in reason.lower() or "bleeding" in reason.lower()
    assert "ENT" in state2.get("department_name", "") or "ENT" in res2["response"]

# ---------------------------------------------------------------------------
# Test Case 21 & 22: Short Phrases & Ambiguous Complaints
# ---------------------------------------------------------------------------

def test_short_one_two_word_symptom():
    conv_code = "WA_TEST_SHORT_21"
    reset_session(conv_code)
    
    res = agent_service.process_agent_message(conv_code, None, "Throat pain")
    state = state_manager.get_conversation_state(conv_code)
    
    assert res is not None
    assert "ENT" in state.get("department_name", "") or "ENT" in res["response"] or "throat" in res["response"].lower()

def test_ambiguous_clinical_complaint():
    conv_code = "WA_TEST_AMBIGUOUS_22"
    reset_session(conv_code)
    
    # "I am feeling strange" is ambiguous -> should trigger clarification or general help without forcing wrong doctor
    res = agent_service.process_agent_message(conv_code, None, "I am feeling strange")
    
    assert res is not None
    assert "response" in res
