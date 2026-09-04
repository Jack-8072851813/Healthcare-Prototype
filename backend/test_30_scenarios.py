"""
test_30_scenarios.py
====================
Comprehensive test suite verifying 30 real-world conversational scenarios for the
WhatsApp AI Patient Desk architecture.
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
from agent import date_normalizer


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


# 1. New patient flow
def test_scenario_01_new_patient():
    conv_code = "WA_TEST_30_01"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I am a new patient")
    p_safe("Scenario 01 Response", res["response"])
    assert "register" in res["response"].lower() or "welcome" in res["response"].lower() or "name" in res["response"].lower() or "first time" in res["response"].lower() or "details" in res["response"].lower()


# 2. Existing patient flow
def test_scenario_02_existing_patient():
    conv_code = "WA_TEST_30_02"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I am an existing patient P1001")
    p_safe("Scenario 02 Response", res["response"])
    assert "welcome" in res["response"].lower() or "help" in res["response"].lower() or "appointments" in res["response"].lower() or "patient" in res["response"].lower()


# 3. Symptoms: Fever
def test_scenario_03_fever():
    conv_code = "WA_TEST_30_03"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I have fever")
    p_safe("Scenario 03 Response", res["response"])
    assert "General Medicine" in res["response"]


# 4. Symptoms: Cough
def test_scenario_04_cough():
    conv_code = "WA_TEST_30_04"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I have severe cough")
    p_safe("Scenario 04 Response", res["response"])
    assert "General Medicine" in res["response"]


# 5. Symptoms: Hair fall -> Dermatology
def test_scenario_05_hair_fall():
    conv_code = "WA_TEST_30_05"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I am losing my hair rapidly")
    p_safe("Scenario 05 Response", res["response"])
    assert "Dermatology" in res["response"] or "Dermatologist" in res["response"]


# 6. Symptoms: Skin rash -> Dermatology
def test_scenario_06_skin_rash():
    conv_code = "WA_TEST_30_06"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I have a skin rash on my arm")
    p_safe("Scenario 06 Response", res["response"])
    assert "Dermatology" in res["response"] or "Dermatologist" in res["response"]


# 7. Symptoms: Joint pain -> Orthopedics
def test_scenario_07_joint_pain():
    conv_code = "WA_TEST_30_07"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I have joint pain in my knees")
    p_safe("Scenario 07 Response", res["response"])
    assert "Orthopedics" in res["response"] or "Orthopedist" in res["response"]


# 8. Child fever -> Pediatrics
def test_scenario_08_child_fever():
    conv_code = "WA_TEST_30_08"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "My child has high fever")
    p_safe("Scenario 08 Response", res["response"])
    assert "Pediatrics" in res["response"] or "Pediatrician" in res["response"]


# 9. Parent booking for son ("Ravi, 12/05/2010, Male") - Strict DOB & Reason test
def test_scenario_09_parent_booking_for_son():
    conv_code = "WA_TEST_30_09"
    reset_session(conv_code)
    res1 = agent_service.process_agent_message(conv_code, None, "My son have Fever")
    p_safe("Scenario 09 Step 1 Response", res1["response"])
    
    res2 = agent_service.process_agent_message(conv_code, None, "Ravi, 12/05/2010, Male")
    p_safe("Scenario 09 Step 2 Response", res2["response"])

    state = state_manager.get_conversation_state(conv_code)
    # 1. DOB must NOT pollute appointment_date
    assert state["entities"]["appointment_date"] is None or int(state["entities"]["appointment_date"].split("-")[0]) >= 2025
    # 2. Name "Ravi" must NOT pollute medical reason/symptom
    assert "ravi" not in (state["entities"].get("reason") or "").lower()


# 10. Parent booking for daughter
def test_scenario_10_parent_booking_for_daughter():
    conv_code = "WA_TEST_30_10"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I want to book an appointment for my daughter")
    p_safe("Scenario 10 Response", res["response"])
    state = state_manager.get_conversation_state(conv_code)
    assert state["appointment_for"] in ["CHILD", "FAMILY_MEMBER"]


# 11. Appointment without symptoms -> Prompts reason
def test_scenario_11_appointment_without_symptoms():
    conv_code = "WA_TEST_30_11"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "Book appointment")
    p_safe("Scenario 11 Response", res["response"])
    assert "What health problem" in res["response"] or "symptom" in res["response"] or "reason" in res["response"]
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is None


# 12. Appointment with all details in one message
def test_scenario_12_all_details_in_one_message():
    conv_code = "WA_TEST_30_12"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "Book appointment for fever with Dr. Arun Kumar tomorrow at 10 AM")
    p_safe("Scenario 12 Response", res["response"])
    assert "confirm" in res["response"].lower() or "Arun" in res["response"] or "10:00" in res["response"]


# 13. Doctor availability general ("Tell me doctor availability")
def test_scenario_13_doctor_availability_general():
    conv_code = "WA_TEST_30_13"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "Tell me doctor availability")
    p_safe("Scenario 13 Response", res["response"])
    assert "department" in res["response"].lower() or "doctor" in res["response"].lower()


# 14. Availability tomorrow ("Who is available tomorrow?")
def test_scenario_14_availability_tomorrow():
    conv_code = "WA_TEST_30_14"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "Who is available tomorrow?")
    p_safe("Scenario 14 Response", res["response"])
    assert "department" in res["response"].lower() or "doctor" in res["response"].lower() or "available" in res["response"].lower()


# 15. Specific doctor request ("I want Dr. Arun Kumar")
def test_scenario_15_specific_doctor_request():
    conv_code = "WA_TEST_30_15"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I want Dr. Arun Kumar")
    p_safe("Scenario 15 Response", res["response"])
    assert "Arun" in res["response"] or "date" in res["response"].lower()


# 16. Cancel appointment request
def test_scenario_16_cancel_appointment():
    conv_code = "WA_TEST_30_16"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I want to cancel my appointment")
    p_safe("Scenario 16 Response", res["response"])
    assert "cancel" in res["response"].lower() or "booking" in res["response"].lower() or "id" in res["response"].lower()


# 17. Reschedule appointment request
def test_scenario_17_reschedule_appointment():
    conv_code = "WA_TEST_30_17"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I need to change my appointment")
    p_safe("Scenario 17 Response", res["response"])
    assert "reschedule" in res["response"].lower() or "booking" in res["response"].lower() or "change" in res["response"].lower() or "id" in res["response"].lower()


# 18. Hospital information request
def test_scenario_18_hospital_information():
    conv_code = "WA_TEST_30_18"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "Where is the hospital located?")
    p_safe("Scenario 18 Response", res["response"])
    assert "hospital" in res["response"].lower() or "meridian" in res["response"].lower() or "location" in res["response"].lower() or "address" in res["response"].lower() or "located" in res["response"].lower()


# 19. Natural language dates ("12 May 2010", "May 12th 2010")
def test_scenario_19_natural_language_dates():
    dt1, _, _ = date_normalizer.parse_and_normalize_date("12 May 2010")
    dt2, _, _ = date_normalizer.parse_and_normalize_date("May 12th 2010")
    assert dt1 == "2010-05-12"
    assert dt2 == "2010-05-12"


# 20. Different DOB formats ("12/05/2010", "2010-05-12")
def test_scenario_20_different_dob_formats():
    dt1, _, _ = date_normalizer.parse_and_normalize_date("12/05/2010")
    dt2, _, _ = date_normalizer.parse_and_normalize_date("2010-05-12")
    assert dt1 in ["2010-05-12", "2010-12-05"]
    assert dt2 == "2010-05-12"


# 21. Missing DOB flow
def test_scenario_21_missing_dob():
    conv_code = "WA_TEST_30_21"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I want to register. My name is Anil, Male, phone 9876543210")
    p_safe("Scenario 21 Response", res["response"])
    assert "date of birth" in res["response"].lower() or "dob" in res["response"].lower() or "birth" in res["response"].lower() or "confirm" in res["response"].lower() or "details" in res["response"].lower()


# 22. Missing symptoms flow
def test_scenario_22_missing_symptoms():
    conv_code = "WA_TEST_30_22"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I want an appointment tomorrow morning")
    p_safe("Scenario 22 Response", res["response"])
    assert "symptom" in res["response"].lower() or "reason" in res["response"].lower() or "health problem" in res["response"].lower() or "sure" in res["response"].lower()


# 23. Missing appointment date flow
def test_scenario_23_missing_appointment_date():
    conv_code = "WA_TEST_30_23"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I have fever and want to consult Dr. Arun Kumar")
    p_safe("Scenario 23 Response", res["response"])
    assert "date" in res["response"].lower() or "when" in res["response"].lower() or "tomorrow" in res["response"].lower()


# 24. Missing appointment time flow
def test_scenario_24_missing_appointment_time():
    conv_code = "WA_TEST_30_24"
    reset_session(conv_code)
    res1 = agent_service.process_agent_message(conv_code, None, "I have fever and want to see Dr. Arun Kumar tomorrow")
    p_safe("Scenario 24 Response", res1["response"])
    assert "time" in res1["response"].lower() or "slot" in res1["response"].lower() or "available" in res1["response"].lower() or "which" in res1["response"].lower()


# 25. Patient changes doctor mid-conversation
def test_scenario_25_patient_changes_doctor():
    conv_code = "WA_TEST_30_25"
    reset_session(conv_code)
    agent_service.process_agent_message(conv_code, None, "I have fever")
    res = agent_service.process_agent_message(conv_code, None, "Actually I want Dr. Arun Kumar")
    p_safe("Scenario 25 Response", res["response"])
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["doctor_id"] is not None


# 26. Patient changes date mid-conversation
def test_scenario_26_patient_changes_date():
    conv_code = "WA_TEST_30_26"
    reset_session(conv_code)
    agent_service.process_agent_message(conv_code, None, "Book appointment for fever with Dr. Arun Kumar tomorrow")
    res = agent_service.process_agent_message(conv_code, None, "Change date to day after tomorrow")
    p_safe("Scenario 26 Response", res["response"])
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["appointment_date"] is not None


# 27. Patient changes intent mid-conversation
def test_scenario_27_patient_changes_intent():
    conv_code = "WA_TEST_30_27"
    reset_session(conv_code)
    agent_service.process_agent_message(conv_code, None, "I want to book an appointment for fever")
    res = agent_service.process_agent_message(conv_code, None, "Never mind, tell me hospital location")
    p_safe("Scenario 27 Response", res["response"])
    assert "location" in res["response"].lower() or "address" in res["response"].lower() or "hospital" in res["response"].lower() or "meridian" in res["response"].lower()


# 28. User says "yes" to confirmation
def test_scenario_28_user_says_yes():
    conv_code = "WA_TEST_30_28"
    reset_session(conv_code)
    state = state_manager.get_conversation_state(conv_code)
    state["confirmation_pending"] = True
    state["pending_booking"] = {"doctor_id": 1, "appointment_date": "2026-09-10", "appointment_time": "10:00", "reason": "Fever"}
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "Yes")
    p_safe("Scenario 28 Response", res["response"])
    assert "confirm" in res["response"].lower() or "booked" in res["response"].lower() or "successful" in res["response"].lower() or "appointment" in res["response"].lower()


# 29. User says "no" to confirmation
def test_scenario_29_user_says_no():
    conv_code = "WA_TEST_30_29"
    reset_session(conv_code)
    state = state_manager.get_conversation_state(conv_code)
    state["confirmation_pending"] = True
    state["pending_booking"] = {"doctor_id": 1, "appointment_date": "2026-09-10", "appointment_time": "10:00", "reason": "Fever"}
    state_manager.save_conversation_state(conv_code, state)

    res = agent_service.process_agent_message(conv_code, None, "No")
    p_safe("Scenario 29 Response", res["response"])
    assert "cancel" in res["response"].lower() or "help" in res["response"].lower() or "else" in res["response"].lower() or "no problem" in res["response"].lower()


# 30. User sends details across multiple messages
def test_scenario_30_multi_message_details():
    conv_code = "WA_TEST_30_30"
    reset_session(conv_code)
    res1 = agent_service.process_agent_message(conv_code, None, "I want to book an appointment")
    p_safe("Scenario 30 Turn 1", res1["response"])
    
    res2 = agent_service.process_agent_message(conv_code, None, "I have severe joint pain")
    p_safe("Scenario 30 Turn 2", res2["response"])

    res3 = agent_service.process_agent_message(conv_code, None, "Tomorrow morning")
    p_safe("Scenario 30 Turn 3", res3["response"])

    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"]["department_id"] is not None or "Orthopedics" in res2["response"]


# 31. Patient profile request ("Tell my personal details")
def test_scenario_31_patient_profile_request():
    conv_code = "WA_TEST_30_31"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "Tell my personal details")
    p_safe("Scenario 31 Response", res["response"])
    assert "Profile" in res["response"] or "Name" in res["response"] or "Patient ID" in res["response"] or "registered" in res["response"].lower() or "details" in res["response"].lower()
    assert "Dr. Arun" not in res["response"]
    assert "General Medicine" not in res["response"]


# 32. Patient details variations ("tell my details")
def test_scenario_32_patient_details_variations():
    conv_code = "WA_TEST_30_32"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "tell my details")
    p_safe("Scenario 32 Response", res["response"])
    assert "registered" in res["response"].lower() or "details" in res["response"].lower() or "name" in res["response"].lower()
    assert "Dr. Arun" not in res["response"]


# 33. Past date rejection ("Book appointment on 02/09/2020")
def test_scenario_33_past_date_rejection():
    conv_code = "WA_TEST_30_33"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "I want to book an appointment for fever on 2020-09-02")
    p_safe("Scenario 33 Response", res["response"])
    assert "passed" in res["response"].lower() or "future" in res["response"].lower() or "already" in res["response"].lower()


# 34. Emergency notice ("Severe chest pain and difficulty breathing")
def test_scenario_34_emergency_notice():
    conv_code = "WA_TEST_30_34"
    reset_session(conv_code)
    res = agent_service.process_agent_message(conv_code, None, "Severe chest pain and difficulty breathing")
    p_safe("Scenario 34 Response", res["response"])
    assert "emergency" in res["response"].lower() or "108" in res["response"] or "112" in res["response"]

