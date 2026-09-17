import sys
import os
sys.path.insert(0, os.getcwd())
backend_dir = os.path.join(os.getcwd(), "backend")
sys.path.insert(0, backend_dir)

import agent.agent_service as agent_service
from scratch.test_multi_patient_regression import setup_multi_patient_data

data = setup_multi_patient_data()
phone = data['multi_phone'].replace('+', '')

test_intents = [
    "my profile",
    "show my profile",
    "view profile",
    "my appointments",
    "book appointment",
    "my reports"
]

print("=== TESTING MULTI-PATIENT INTENTS ===")
for i, msg in enumerate(test_intents):
    conv = f"WA_{phone}_{i}"
    res = agent_service.process_agent_message(conv, "", msg)
    first_line = res["response"].split('\n')[0]
    print(f"Input: '{msg}' -> Response line 1: {first_line}")
    assert "I found multiple patient profiles" in res["response"], f"Failed for '{msg}'"

print("\n✅ SUCCESS: All patient-specific intents prompt for patient selection when multiple patients exist!")
