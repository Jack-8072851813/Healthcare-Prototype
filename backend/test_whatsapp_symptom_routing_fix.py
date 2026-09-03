"""
test_whatsapp_symptom_routing_fix.py
======================================
Tests for WhatsApp AI Patient Desk doctor/department routing logic & available times state retainment.
"""

import sys
import os
import pytest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.agent_service as agent_service
import agent.entity_extractor as entity_extractor
import agent.state_manager as state_manager

def test_symptom_department_mapping_rules():
    """Verify symptom mapping to correct department."""
    assert entity_extractor.map_symptom_to_department_name("Hair falling") == "Dermatology"
    assert entity_extractor.map_symptom_to_department_name("hair fall") == "Dermatology"
    assert entity_extractor.map_symptom_to_department_name("excessive hair loss and bald patches") == "Dermatology"
    assert entity_extractor.map_symptom_to_department_name("acne and pimples") == "Dermatology"
    assert entity_extractor.map_symptom_to_department_name("skin rash and itching") == "Dermatology"
    assert entity_extractor.map_symptom_to_department_name("high fever and cold") == "General Medicine"
    assert entity_extractor.map_symptom_to_department_name("chest pain and heart palpitations") == "Cardiology"
    assert entity_extractor.map_symptom_to_department_name("my child has fever") == "Pediatrics"
    assert entity_extractor.map_symptom_to_department_name("knee joint pain and fracture") == "Orthopedics"
    assert entity_extractor.map_symptom_to_department_name("earache and sinus infection") == "ENT"

def test_hair_falling_symptom_booking_flow():
    """Verify 'Hair falling' routes to Dermatology and Dr. Wilson M without resetting."""
    conv_code = "FIX_TEST_HAIR_FRESH_100"
    
    # 0. Clean DB conversation if exists
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # 1. User says "Book appointment"
    res0 = agent_service.process_agent_message(conv_code, None, "Book appointment")
    assert "Which disease, symptom, or cause" in res0["response"]

    # 2. Send "Hair falling"
    res1 = agent_service.process_agent_message(conv_code, None, "Hair falling")
    text1 = res1["response"]
    assert "Dermatology" in text1
    assert "Dr. Wilson M" in text1 or "Wilson" in text1
    assert "General Medicine" not in text1
    assert "Dr. Arun Kumar" not in text1

    # Check updated state
    new_state = state_manager.get_conversation_state(conv_code)
    assert new_state["entities"]["department_id"] == 21  # Dermatology
    assert new_state["entities"]["doctor_id"] == 10       # Dr. Wilson M

    # 3. Send "Can you tell available times?"
    res2 = agent_service.process_agent_message(conv_code, None, "Can you tell available times?")
    text2 = res2["response"]
    assert "Dr. Wilson M" in text2
    assert "Which department" not in text2  # Must NOT reset department selection!

    # State check: Doctor and department must be retained!
    state_after = state_manager.get_conversation_state(conv_code)
    assert state_after["entities"]["department_id"] == 21
    assert state_after["entities"]["doctor_id"] == 10

def test_available_times_query_retains_state():
    """Verify asking available times after choosing doctor/date retains state and lists slots."""
    conv_code = "FIX_TEST_SLOTS_FRESH_100"
    
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # 1. User selects Dr. Arun Kumar on 2026-09-15
    res1 = agent_service.process_agent_message(conv_code, None, "I want to consult Dr. Arun Kumar on 2026-09-15 for fever")
    
    # 2. Query available times
    res2 = agent_service.process_agent_message(conv_code, None, "Can you tell available time?")
    text2 = res2["response"]
    assert "Dr. Arun Kumar" in text2
    assert "Which department" not in text2
    assert "Which disease" not in text2

    # State verify
    updated = state_manager.get_conversation_state(conv_code)
    assert updated["entities"]["doctor_id"] == 5
    assert updated["entities"]["department_id"] == 17
    assert updated["entities"]["appointment_date"] == "2026-09-15"
