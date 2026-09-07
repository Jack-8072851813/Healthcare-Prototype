"""
test_doctor_query_fix.py
========================
Tests that sending 'Doctor Availability' followed by 'Dr. James' (or a specific doctor name)
returns Dr. James's details and availability slots, without outputting a generic greeting ("Welcome back...").
"""

import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from agent import agent_service
from agent import state_manager


def test_doctor_availability_query_flow():
    conv_code = "WA_TEST_DOC_QUERY_1001"

    # Reset state
    state = state_manager.get_conversation_state(conv_code)
    state["patient_id"] = 1
    state["intent"] = "GREETING"
    state["entities"] = {
        "patient_id": 1,
        "doctor_id": None,
        "department_id": None,
        "appointment_date": None,
        "appointment_time": None,
        "booking_id": None,
        "reason": None,
        "symptoms": []
    }
    state_manager.save_conversation_state(conv_code, state)

    # Turn 1: Patient taps/types "Doctor Availability"
    res1 = agent_service.process_agent_message(conv_code, None, "Doctor Availability")
    print("\n[Turn 1 Response]:", res1["response"].encode("ascii", errors="ignore").decode("ascii"))
    assert res1["intent"] == "DOCTOR_AVAILABILITY"
    assert "Doctors & Availability" in res1["response"] or "active doctors" in res1["response"].lower()

    # Turn 2: Patient types "Dr. James"
    res2 = agent_service.process_agent_message(conv_code, None, "Dr. James")
    print("\n[Turn 2 Response]:", res2["response"].encode("ascii", errors="ignore").decode("ascii"))

    # Verify that generic greeting is NOT returned
    assert "Welcome back" not in res2["response"]

    # Verify that Dr. James's details and availability/slots are in the response
    assert "Dr. James" in res2["response"] or "James" in res2["response"]
    assert "ENT" in res2["response"] or "Department" in res2["response"]
    assert "Available" in res2["response"] or "slots" in res2["response"].lower()


if __name__ == "__main__":
    test_doctor_availability_query_flow()
    print("\nAll doctor query tests passed successfully!")
