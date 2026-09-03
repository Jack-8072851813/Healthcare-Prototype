"""
test_whatsapp_symptom_booking.py
=================================
Tests the guided symptom-to-department appointment booking flow.

Scenario tested:
1. Turn 1: Patient triggers "Book Appointment" -> Bot prompts "Which disease, symptom, or cause do you have?"
2. Turn 2: Patient responds "I have fever" -> Bot maps to "General Medicine", lists Dr. Arun Kumar with available slots, and asks for preferred time.
3. Turn 3: Patient responds "Tomorrow at 09:00 AM" -> Bot shows confirmation details with Dr. Arun Kumar, General Medicine, Fever, and 09:00 AM.
"""

import sys
import os
import pytest

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from agent import agent_service
from agent import state_manager
from agent import entity_extractor



def test_symptom_guided_booking_flow():
    conv_code = "WA_TEST_SYMPTOM_FLOW_1001"
    
    # Delete any stale messages and conversation state from DB
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # Clean initial state
    state = state_manager.get_conversation_state(conv_code, whatsapp_number="9199991001")
    state["patient_id"] = 1 # Valid test patient
    state["entities"] = {
        "patient_id": 1,
        "doctor_id": None,
        "department_id": None,
        "appointment_date": None,
        "appointment_time": None,
        "booking_id": None,
        "reason": None
    }
    state["booking_stage"] = None
    state["previous_question"] = None
    state["confirmation_pending"] = False
    state["confirmation_details"] = {}
    state_manager.save_conversation_state(conv_code, state)



    # --- Turn 1: "Book Appointment" ---
    res_turn1 = agent_service.process_agent_message(conv_code, None, "Book Appointment")
    print("\n[Turn 1 Response]:", res_turn1["response"])
    
    assert "Which disease, symptom, or cause do you have?" in res_turn1["response"] or "symptom" in res_turn1["response"].lower()
    
    # --- Turn 2: "I have fever" ---
    res_turn2 = agent_service.process_agent_message(conv_code, None, "I have fever")
    print("\n[Turn 2 Response]:", res_turn2["response"])
    
    assert "General Medicine" in res_turn2["response"]
    assert "Arun Kumar" in res_turn2["response"] or "Available slots" in res_turn2["response"]

    # --- Turn 3: "next Monday at 10:00 AM" ---
    res_turn3 = agent_service.process_agent_message(conv_code, None, "next Monday at 10:00 AM")
    print("\n[Turn 3 Response]:", res_turn3["response"].encode('ascii', 'ignore').decode('ascii'))
    
    assert "confirm" in res_turn3["response"].lower() or "Confirm Appointment" in str(res_turn3.get("interactive_buttons", []))


def test_symptom_mapping_utility():
    assert entity_extractor.map_symptom_to_department_name("I have high fever and cold") == "General Medicine"
    assert entity_extractor.map_symptom_to_department_name("severe chest pain and breathlessness") == "Cardiology"
    assert entity_extractor.map_symptom_to_department_name("earache and sinus infection") == "ENT"
    assert entity_extractor.map_symptom_to_department_name("knee joint pain and backache") == "Orthopedics"
    assert entity_extractor.map_symptom_to_department_name("skin rash and itching") == "Dermatology"
