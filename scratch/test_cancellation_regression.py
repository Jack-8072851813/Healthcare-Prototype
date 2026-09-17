import sys
import os
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, backend_dir)

import db_config
import agent.agent_service as agent_service

import random

def setup_test_appointment():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM patients LIMIT 1;")
        p_row = cur.fetchone()
        pat_id = p_row[0] if p_row else 1

        cur.execute("SELECT id, department_id FROM doctors LIMIT 1;")
        d_row = cur.fetchone()
        doc_id, dept_id = d_row[0], d_row[1]

        booking_id = f"APT_TEST_{int(datetime.datetime.now().timestamp())}_{random.randint(100,999)}"
        test_date = (datetime.date.today() + datetime.timedelta(days=random.randint(15, 100))).strftime("%Y-%m-%d")
        test_time = f"{random.randint(8,16):02d}:30:00"

        cur.execute("""
            INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status, booking_source)
            VALUES (%s, %s, %s, %s, %s, %s, 'BOOKED', 'WHATSAPP_TEXT')
            RETURNING id;
        """, (booking_id, pat_id, doc_id, dept_id, test_date, test_time))
        appt_db_id = cur.fetchone()[0]
        conn.commit()
        return appt_db_id, booking_id, pat_id
    finally:
        cur.close()
        conn.close()

def run_tests():
    print("==========================================")
    print("STARTING CANCELLATION REGRESSION TEST SUITE")
    print("==========================================")
    
    appt_db_id, booking_id, pat_id = setup_test_appointment()
    conv_code = f"CONV_TEST_{booking_id}"
    
    print(f"\n[SETUP] Created active appointment DB_ID={appt_db_id}, Booking_ID={booking_id}, Patient_ID={pat_id}")
    
    # ----------------------------------------------------
    # TEST 1: Cancel active appointment via button flow
    # ----------------------------------------------------
    print("\n--- TEST 1: Cancel Active Appointment ---")
    state = agent_service.state_manager.get_conversation_state(conv_code)
    if not state.get("conversation_id"):
        state["conversation_id"] = conv_code
    state["patient_id"] = pat_id
    agent_service.state_manager.save_conversation_state(conv_code, state)

    # Tap "Cancel Appointment"
    res1 = agent_service.process_agent_message(conv_code, "+919999999999", f"btn_cancel_existing_{appt_db_id}")
    print("Prompt Output:", res1["response"])
    print("Buttons:", res1["interactive_buttons"])
    assert "Are you sure you want to cancel" in res1["response"], "Prompt should ask confirmation"
    button_titles = [b["title"] for b in res1["interactive_buttons"]]
    assert "Yes, Cancel" in button_titles, "Should show 'Yes, Cancel' button"
    assert "Keep Appointment" in button_titles, "Should show 'Keep Appointment' button"

    # Tap "Yes, Cancel"
    res2 = agent_service.process_agent_message(conv_code, "+919999999999", f"btn_exec_cancel_{booking_id}")
    print("\nCancellation Success Output:", res2["response"])
    print("Buttons:", res2["interactive_buttons"])
    assert "✅ *Appointment Cancelled Successfully*" in res2["response"], "Success card header missing"
    assert booking_id in res2["response"], "Booking ID missing in success card"
    assert "The appointment slot has been released." in res2["response"], "Slot release message missing"
    assert "book another appointment" not in res2["response"].lower(), "BUG 11 VIOLATION: Should NOT prompt for new booking!"
    
    # Verify DB Status
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM appointments WHERE id = %s;", (appt_db_id,))
    db_status = cur.fetchone()[0]
    cur.close()
    conn.close()
    assert db_status == "CANCELLED", f"Expected status CANCELLED, got {db_status}"
    print("[PASS] Test 1 Passed: Active appointment cancelled, DB updated, slot released, neutral success response sent.")

    # ----------------------------------------------------
    # TEST 2: Already Cancelled View hides "Cancel Appointment"
    # ----------------------------------------------------
    print("\n--- TEST 2: Already Cancelled Appointment View (Bug 1) ---")
    res_view = agent_service.process_agent_message(conv_code, "+919999999999", f"btn_appt_{appt_db_id}")
    print("View Output:", res_view["response"])
    print("Buttons:", res_view["interactive_buttons"])
    view_titles = [b["title"] for b in res_view["interactive_buttons"]]
    assert "Cancel Appointment" not in view_titles, "BUG 1 VIOLATION: 'Cancel Appointment' button shown for CANCELLED appointment!"
    assert "Reschedule Appointment" not in view_titles, "Reschedule button should also be hidden for CANCELLED appointment!"
    assert "Back to My Appointments" in view_titles or "Main Menu" in view_titles, "Standard navigation buttons expected"
    print("[PASS] Test 2 Passed: 'Cancel Appointment' button is hidden for CANCELLED appointments.")

    # ----------------------------------------------------
    # TEST 3 & TEST 5: Double Cancellation & Idempotency (Bugs 2 & 5)
    # ----------------------------------------------------
    print("\n--- TEST 3: Repeated Cancellation Attempt (Bugs 2 & 5) ---")
    res_repeat = agent_service.process_agent_message(conv_code, "+919999999999", f"btn_exec_cancel_{booking_id}")
    print("Repeat Exec Output:", res_repeat["response"])
    assert "This appointment has already been cancelled." in res_repeat["response"], "Idempotency response missing"
    
    res_cancel_btn = agent_service.process_agent_message(conv_code, "+919999999999", f"btn_cancel_existing_{appt_db_id}")
    print("Repeat Cancel Btn Output:", res_cancel_btn["response"])
    assert "This appointment has already been cancelled." in res_cancel_btn["response"], "Idempotency response missing"
    print("[PASS] Test 3 Passed: Double cancellation prevented with clear message.")

    # ----------------------------------------------------
    # TEST 4: Keep Appointment
    # ----------------------------------------------------
    print("\n--- TEST 4: Keep Appointment Flow ---")
    appt_db_id2, booking_id2, pat_id2 = setup_test_appointment()
    res_k1 = agent_service.process_agent_message(conv_code, "+919999999999", f"btn_cancel_existing_{appt_db_id2}")
    res_k2 = agent_service.process_agent_message(conv_code, "+919999999999", "btn_my_appts") # Keep Appointment taps btn_my_appts
    
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM appointments WHERE id = %s;", (appt_db_id2,))
    db_status2 = cur.fetchone()[0]
    cur.close()
    conn.close()
    assert db_status2 == "BOOKED", f"Status should remain BOOKED, got {db_status2}"
    print("[PASS] Test 4 Passed: 'Keep Appointment' leaves appointment status unchanged.")

    # ----------------------------------------------------
    # TEST 5: Patient Ownership Validation (Bug 6)
    # ----------------------------------------------------
    print("\n--- TEST 5: Patient Ownership Validation (Bug 6) ---")
    state_other = agent_service.state_manager.get_conversation_state("CONV_OTHER")
    state_other["patient_id"] = 999999  # Wrong patient ID
    agent_service.state_manager.save_conversation_state("CONV_OTHER", state_other)
    
    res_own1 = agent_service.process_agent_message("CONV_OTHER", "+918888888888", f"btn_cancel_existing_{appt_db_id2}")
    print("Ownership Reject Output:", res_own1["response"])
    assert "does not match selected patient" in res_own1["response"] or "could not be found" in res_own1["response"], "Ownership mismatch should be rejected"
    
    res_own2 = agent_service.process_agent_message("CONV_OTHER", "+918888888888", f"btn_exec_cancel_{booking_id2}")
    print("Ownership Exec Reject Output:", res_own2["response"])
    assert "does not belong" in res_own2["response"] or "could not be found" in res_own2["response"], "Ownership mismatch should be rejected"
    print("[PASS] Test 5 Passed: Patient ownership validated before cancellation.")

    # ----------------------------------------------------
    # TEST 6: Text reply "Yes, Cancel" (Bugs 3 & 9)
    # ----------------------------------------------------
    print("\n--- TEST 6: Text Reply 'Yes, Cancel' (Bugs 3 & 9) ---")
    appt_db_id3, booking_id3, pat_id3 = setup_test_appointment()
    conv_code3 = f"CONV_TEST_{booking_id3}"
    state3 = agent_service.state_manager.get_conversation_state(conv_code3)
    state3["patient_id"] = pat_id3
    agent_service.state_manager.save_conversation_state(conv_code3, state3)

    agent_service.process_agent_message(conv_code3, "+917777777777", f"btn_cancel_existing_{appt_db_id3}")
    res_text_cancel = agent_service.process_agent_message(conv_code3, "+917777777777", "Yes, Cancel")
    print("Text Reply Cancel Output:", res_text_cancel["response"])
    assert "✅ *Appointment Cancelled Successfully*" in res_text_cancel["response"], "Text reply 'Yes, Cancel' failed to cancel"
    assert "What health problem" not in res_text_cancel["response"], "Should NOT route to BOOK_APPOINTMENT!"
    print("[PASS] Test 6 Passed: Text reply 'Yes, Cancel' executes cancellation correctly.")

    print("\n==========================================")
    print("ALL CANCELLATION REGRESSION TESTS PASSED! ✅")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
