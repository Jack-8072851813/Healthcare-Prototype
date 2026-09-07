import pytest
import datetime
import db_config
from agent import agent_service, state_manager, tool_registry

def test_fix1_department_label_matches_queried_doctors():
    """Fix 1: Department label shown to patient must match actual department returned by DB."""
    conv_code = f"TEST_FIX1_{int(datetime.datetime.now().timestamp())}"
    
    # 1. Send symptom "Nose pain" (maps to ENT department)
    res = agent_service.process_agent_message(conv_code, None, "Nose pain")
    response_text = res["response"]
    
    # Verify response contains ENT and does NOT fall back to General Medicine label for ENT doctors
    assert "ENT" in response_text or "Ear, Nose" in response_text
    assert "General Medicine" not in response_text, f"Expected ENT department label, got: {response_text}"

    # 2. Test "hair fall" (maps to Dermatology)
    conv_code_2 = f"TEST_FIX1_DERM_{int(datetime.datetime.now().timestamp())}"
    res2 = agent_service.process_agent_message(conv_code_2, None, "hair fall")
    response_text_2 = res2["response"]
    assert "Dermatology" in response_text_2
    assert "General Medicine" not in response_text_2

def test_fix2_invalid_out_of_hours_time_rejected():
    """Fix 2: Invalid/out-of-hours time slot (e.g. 12 AM) must be rejected with available slots list."""
    conv_code = f"TEST_FIX2_{int(datetime.datetime.now().timestamp())}"
    
    # 1. Initiate booking with doctor and date
    res1 = agent_service.process_agent_message(conv_code, None, "Book appointment with Dr. Arun Kumar for tomorrow")
    
    # 2. Provide out-of-hours time "12 AM"
    res2 = agent_service.process_agent_message(conv_code, None, "12 AM")
    response_text = res2["response"]
    
    # Verify bot rejected the time and presented available slots
    assert "not available" in response_text or "Available slots" in response_text
    
    # Ensure invalid time was cleared from state
    state = state_manager.get_conversation_state(conv_code)
    assert state["entities"].get("appointment_time") is None

def test_fix3_structured_button_taps_direct_routing():
    """Fix 3: Button taps with interactive_id route directly and btn_other_services returns distinct content."""
    conv_code = f"TEST_FIX3_{int(datetime.datetime.now().timestamp())}"
    
    # 1. Tap "Other Services" via interactive_id
    res_other = agent_service.process_agent_message(
        conversation_code=conv_code,
        patient_code=None,
        message_text="Other Services",
        interactive_id="btn_other_services"
    )
    text_other = res_other["response"]
    assert "Other Hospital Services" in text_other
    assert "Laboratory & Diagnostics" in text_other or "Pharmacy" in text_other
    assert text_other != "Meridian Hospital Information"

    # 2. Tap "Doctor Information" button via interactive_id
    res_doc = agent_service.process_agent_message(
        conversation_code=conv_code,
        patient_code=None,
        message_text="Doctor Information",
        interactive_id="btn_doctor_avail"
    )
    # Should route directly without symptom extraction error
    assert res_doc["intent"] in ["DOCTOR_AVAILABILITY", "BOOK_APPOINTMENT", "HOSPITAL_INFORMATION"]

def test_fix4_dependent_booking_subflow():
    """Fix 4: Dependent booking ('My son...') prompts for dependent info and creates dependent patient."""
    conv_code = f"TEST_FIX4_{int(datetime.datetime.now().timestamp())}"
    
    # 1. Send dependent symptom phrase
    res1 = agent_service.process_agent_message(conv_code, None, "My son has hair falling problem")
    text1 = res1["response"]
    
    # Bot must ask for dependent's full name first
    assert "dependent" in text1.lower() or "son" in text1.lower() or "full name" in text1.lower()
    
    # 2. Provide son's name
    res2 = agent_service.process_agent_message(conv_code, None, "Rohan Sharma")
    text2 = res2["response"]
    assert "date of birth" in text2.lower()
    
    # 3. Provide DOB
    res3 = agent_service.process_agent_message(conv_code, None, "10/05/2015")
    text3 = res3["response"]
    assert "gender" in text3.lower()
    
    # 4. Provide gender
    res4 = agent_service.process_agent_message(conv_code, None, "Male")
    
    # State verify: patient_id must belong to dependent, dependent_collected must be True
    state = state_manager.get_conversation_state(conv_code)
    assert state.get("dependent_collected") is True
    assert state.get("patient_id") is not None

def test_fix5_awaiting_booking_id_protection():
    """Fix 5: When in AWAITING_BOOKING_ID, off-format replies must be rejected and not reclassify intent."""
    conv_code = f"TEST_FIX5_{int(datetime.datetime.now().timestamp())}"
    
    # 1. User asks for appointment status with missing booking ID
    res1 = agent_service.process_agent_message(conv_code, None, "Check my appointment status")
    assert "booking ID" in res1["response"] or "Booking ID" in res1["response"]
    
    # 2. Reply with an off-format text (e.g. a doctor's name "Dr. Arun Kumar")
    res2 = agent_service.process_agent_message(conv_code, None, "Dr. Arun Kumar")
    text2 = res2["response"]
    
    # Bot must reject the input as invalid booking ID and re-ask, NOT start doctor selection flow
    assert "doesn't look like a valid Booking ID" in text2 or "valid Booking ID" in text2
    assert "Which doctor" not in text2
