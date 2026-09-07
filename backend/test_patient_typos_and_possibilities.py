"""
test_patient_typos_and_possibilities.py
========================================
Comprehensive automated test suite simulating real-world patient interactions
with human typos, misspellings, informal phrasing, and varied conversation flows.
"""

import sys
import os
import uuid

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from agent import agent_service
from agent import state_manager
from agent import entity_extractor
from agent import intent_router


def p(title, text):
    print(f"\n[{title}]:")
    clean = text.encode("ascii", errors="ignore").decode("ascii")
    print(clean)


def test_typo_greetings():
    print("\n==========================================")
    print("TEST 1: Typo Greetings & Informal Openings")
    print("==========================================")
    
    greetings = ["helo", "hii", "good mrning", "hey bot"]
    uid = uuid.uuid4().hex[:6]
    for idx, text in enumerate(greetings):
        conv = f"WA_TYPO_GREET_{uid}_{idx}"
        res = agent_service.process_agent_message(conv, None, text)
        p(f"Input: '{text}'", res["response"])
        assert "Welcome" in res["response"] or "Hello" in res["response"] or "help" in res["response"].lower()


def test_typo_symptom_routing():
    print("\n==========================================")
    print("TEST 2: Typo Symptoms & Department Mapping")
    print("==========================================")

    cases = [
        ("my nos is payning", "ENT"),
        ("nos pain", "ENT"),
        ("skinn rash and itchying", "Dermatology"),
        ("knne pain and joiont ach", "Orthopedics"),
        ("i hav fevr and couggh", "General Medicine"),
    ]

    for text, expected_dept in cases:
        dept = entity_extractor.map_symptom_to_department_name(text)
        print(f"Input: '{text}' -> Extracted Dept: '{dept}' (Expected: '{expected_dept}')")
        assert dept.lower() == expected_dept.lower()


def test_typo_doctor_lookup():
    print("\n==========================================")
    print("TEST 3: Typo Doctor Name Matching")
    print("==========================================")

    conv = f"WA_TYPO_DOC_{uuid.uuid4().hex[:6]}"
    res = agent_service.process_agent_message(conv, None, "is dr arun kumr avilable?")
    p("Input: 'is dr arun kumr avilable?'", res["response"])
    assert "Dr. Arun Kumar" in res["response"] or "General Medicine" in res["response"]


def test_typo_dependent_booking():
    print("\n==========================================")
    print("TEST 4: Typo Dependent Booking ('for my daughtr')")
    print("==========================================")

    conv = f"WA_TYPO_DEP_{uuid.uuid4().hex[:6]}"
    res = agent_service.process_agent_message(conv, None, "want to bok an appoinment for my daughtr")
    p("Input: 'want to bok an appoinment for my daughtr'", res["response"])
    state = state_manager.get_conversation_state(conv)
    assert state.get("appointment_for") in ["CHILD", "FAMILY_MEMBER"]
    assert "daughter" in res["response"].lower() or "dependent" in res["response"].lower() or "full name" in res["response"].lower()


def test_typo_appointment_status_query():
    print("\n==========================================")
    print("TEST 5: Typo Appointment Query ('check my appintment')")
    print("==========================================")

    conv = f"WA_TYPO_STAT_{uuid.uuid4().hex[:6]}"
    state = state_manager.get_default_state()
    state["conversation_id"] = conv
    state["patient_id"] = 1
    state_manager.save_conversation_state(conv, state)

    # Turn 1: Patient types with typo
    res1 = agent_service.process_agent_message(conv, None, "check my appintment")
    p("Turn 1 ('check my appintment')", res1["response"])
    
    # Turn 2: Patient sends booking ID with mixed case
    res2 = agent_service.process_agent_message(conv, None, "apt24321")
    p("Turn 2 ('apt24321')", res2["response"])
    assert "APT24321" in res2["response"] or "Appointment" in res2["response"]


def test_typo_cancellation_and_reschedule():
    print("\n==========================================")
    print("TEST 6: Typo Cancellation & Rescheduling")
    print("==========================================")

    # Cancellation
    conv_c = f"WA_TYPO_CNC_{uuid.uuid4().hex[:6]}"
    res_c = agent_service.process_agent_message(conv_c, None, "cancle my appoinment")
    p("Cancel Input ('cancle my appoinment')", res_c["response"])
    assert "booking ID" in res_c["response"] or "cancel" in res_c["response"].lower()

    # Reschedule
    conv_r = f"WA_TYPO_RSC_{uuid.uuid4().hex[:6]}"
    res_r = agent_service.process_agent_message(conv_r, None, "reschedul my appoinment")
    p("Reschedule Input ('reschedul my appoinment')", res_r["response"])
    assert "booking ID" in res_r["response"] or "reschedule" in res_r["response"].lower()


if __name__ == "__main__":
    test_typo_greetings()
    test_typo_symptom_routing()
    test_typo_doctor_lookup()
    test_typo_dependent_booking()
    test_typo_appointment_status_query()
    test_typo_cancellation_and_reschedule()
    print("\nAll Patient Typo & Real-World Possibility Tests Passed Successfully!")
