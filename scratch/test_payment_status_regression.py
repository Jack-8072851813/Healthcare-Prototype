import sys
import os
import random
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.getcwd())
backend_dir = os.path.join(os.getcwd(), "backend")
sys.path.insert(0, backend_dir)

import db_config
import agent.agent_service as agent_service
import agent.state_manager as state_manager

def setup_test_patient_and_doctor():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        rand_val = random.randint(10000, 99999)
        phone = f"+1555999{rand_val}"
        p_code = f"P_PAY_{rand_val}"
        
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'Payment', 'Tester', %s, %s, '1988-03-15', 'Male', 'ACTIVE')
            RETURNING id;
        """, (p_code, phone, phone))
        pat_id = cur.fetchone()[0]

        cur.execute("SELECT id FROM doctors WHERE status = 'ACTIVE' LIMIT 1;")
        row = cur.fetchone()
        doc_id = row[0] if row else 1

        conn.commit()
        return {
            "phone": phone,
            "patient_id": pat_id,
            "patient_code": p_code,
            "doctor_id": doc_id
        }
    finally:
        cur.close()
        conn.close()


def run_payment_tests():
    print("==========================================")
    print("STARTING PAYMENT STATUS REGRESSION TEST SUITE")
    print("==========================================")

    data = setup_test_patient_and_doctor()
    conv = f"WA_{data['phone'].replace('+', '')}"
    print(f"[SETUP] Created patient {data['patient_code']} (ID: {data['patient_id']}) with phone {data['phone']}")

    # ----------------------------------------------------
    # TEST 1: Brand-New Unpaid Appointment Flow
    # ----------------------------------------------------
    print("\n--- TEST 1: Brand-New Unpaid Appointment Flow ---")
    res1 = agent_service.process_agent_message(conv, "", "btn_book_appt")
    res2 = agent_service.process_agent_message(conv, "", "Fever and cough consultation")
    
    # Pick doctor button if prompted
    doc_btns = [b for b in res2.get("interactive_buttons", []) if b.get("id", "").startswith("btn_doc_")]
    if doc_btns:
        res2 = agent_service.process_agent_message(conv, "", doc_btns[0]["id"])
    
    # Pick date button
    date_btns = [b for b in res2.get("interactive_buttons", []) if b.get("id", "").startswith("btn_date_")]
    if date_btns:
        res3 = agent_service.process_agent_message(conv, "", date_btns[0]["id"])
    else:
        res3 = agent_service.process_agent_message(conv, "", "btn_date_tomorrow")
    
    doc_btns = [b for b in res3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_doc_")]
    if doc_btns:
        res3 = agent_service.process_agent_message(conv, "", doc_btns[0]["id"])

    date_btns = [b for b in res3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_date_") and b["id"] != "btn_date_custom"]
    if date_btns:
        res3 = agent_service.process_agent_message(conv, "", date_btns[0]["id"])
        
    # Extract slot button from interactive_buttons
    slots = [b for b in res3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_slot_")]
    assert len(slots) > 0, f"Slots should be returned, got {res3.get('interactive_buttons')}"
    slot_id = slots[0]["id"]
    
    res4 = agent_service.process_agent_message(conv, "", slot_id)
    assert "Please confirm your appointment details" in res4["response"], "Should reach confirmation"
    
    # Confirm appointment -> should show Payment Required
    res5 = agent_service.process_agent_message(conv, "", "btn_confirm_appt")
    print("Payment Required Screen:", res5["response"].split('\n')[0])
    assert "Payment Required" in res5["response"], "Must show Payment Required"
    assert "already been paid" not in res5["response"], "Must NOT show Already Paid"
    
    # Select Paytm payment method
    res6 = agent_service.process_agent_message(conv, "", "btn_pay_paytm")
    print("Paytm Selection Output:", res6["response"].split('\n')[0])
    assert "Mock Payment" in res6["response"], "Must proceed to Mock Payment"
    assert "already been paid" not in res6["response"], "Must NOT say already been paid"
    
    # Execute Mock Payment
    res7 = agent_service.process_agent_message(conv, "", "btn_pay_exec")
    print("Payment Execution Output:", res7["response"].split('\n')[0])
    assert "confirmed" in res7["response"].lower() or "booking id" in res7["response"].lower(), "Must confirm appointment"
    
    state = state_manager.get_conversation_state(conv)
    booking_id_1 = state.get("booking_id")
    assert booking_id_1 is not None, "Booking ID must exist"
    print(f"[PASS] Test 1 Passed: Brand-new appointment {booking_id_1} paid and confirmed successfully.")

    # ----------------------------------------------------
    # TEST 2: Previous Paid Appointment Does NOT Block New Appointment
    # ----------------------------------------------------
    print("\n--- TEST 2: Previous Paid Appointment Does NOT Block New Appointment ---")
    # Start booking Appointment #2 on the same account that has paid booking_id_1
    res_b1 = agent_service.process_agent_message(conv, "", "btn_book_appt")
    res_b2 = agent_service.process_agent_message(conv, "", "Routine checkup")
    doc_btns = [b for b in res_b2.get("interactive_buttons", []) if b.get("id", "").startswith("btn_doc_")]
    if doc_btns:
        res_b2 = agent_service.process_agent_message(conv, "", doc_btns[0]["id"])
    
    date_btns = [b for b in res_b2.get("interactive_buttons", []) if b.get("id", "").startswith("btn_date_") and b["id"] != "btn_date_custom"]
    if date_btns:
        res_b3 = agent_service.process_agent_message(conv, "", date_btns[0]["id"])
    else:
        res_b3 = agent_service.process_agent_message(conv, "", "btn_date_tomorrow")
        
    date_btns = [b for b in res_b3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_date_") and b["id"] != "btn_date_custom"]
    if date_btns:
        res_b3 = agent_service.process_agent_message(conv, "", date_btns[0]["id"])
        
    slots_b = [b for b in res_b3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_slot_")]
    assert len(slots_b) > 0, "Slots should be returned for Appt 2"
    slot_id_b = slots_b[0]["id"]
    
    res_b4 = agent_service.process_agent_message(conv, "", slot_id_b)
    res_b5 = agent_service.process_agent_message(conv, "", "btn_confirm_appt")
    print("Appt #2 Payment Screen:", res_b5["response"].split('\n')[0])
    assert "Payment Required" in res_b5["response"], "Appt #2 must require payment"
    assert "already been paid" not in res_b5["response"], "Appt #2 must NOT say already paid"

    # Select Paytm for Appt #2
    res_b6 = agent_service.process_agent_message(conv, "", "btn_pay_paytm")
    print("Appt #2 Paytm Selection:", res_b6["response"].split('\n')[0])
    assert "Mock Payment" in res_b6["response"], "Appt #2 must allow payment method selection"
    assert "already been paid" not in res_b6["response"], "Appt #2 must NOT say already paid"
    print(f"[PASS] Test 2 Passed: Previous paid appointment {booking_id_1} does not block Appt #2 payment.")

    # ----------------------------------------------------
    # TEST 3: Duplicate Payment Protection for SAME Paid Appointment
    # ----------------------------------------------------
    print("\n--- TEST 3: Duplicate Payment Protection for SAME Paid Appointment ---")
    state_paid = state_manager.get_conversation_state(conv)
    # Simulate attempt to pay booking_id_1 again
    state_paid["conversation_state"] = None
    state_paid["booking_id"] = booking_id_1
    state_paid["entities"]["booking_id"] = booking_id_1
    
    is_paid, paid_b_id, paid_ref = agent_service.is_appointment_already_paid(state_paid)
    assert is_paid is True, f"Appointment {booking_id_1} should be detected as paid"
    assert paid_b_id == booking_id_1, "Returned booking_id must match target"
    print(f"[PASS] Test 3 Passed: Duplicate payment for same appointment {booking_id_1} is correctly detected as PAID.")

    print("\n==========================================")
    print("ALL PAYMENT REGRESSION TESTS PASSED! ✅")
    print("==========================================")

if __name__ == "__main__":
    run_payment_tests()
