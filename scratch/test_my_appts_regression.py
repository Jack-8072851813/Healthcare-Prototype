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

def run_my_appts_tests():
    print("==========================================")
    print("STARTING MY APPOINTMENTS REGRESSION TEST SUITE")
    print("==========================================")

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        rand_val = random.randint(10000, 99999)
        phone_multi = f"+1555777{rand_val}"
        
        # Create Gil Christ (P9989) and John David (P2666) under phone_multi
        p_code_gil = f"P9989_{rand_val}"
        p_code_john = f"P2666_{rand_val}"
        
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'Gil', 'Christ', %s, %s, '1985-05-15', 'Male', 'ACTIVE')
            RETURNING id;
        """, (p_code_gil, phone_multi, phone_multi))
        gil_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'John', 'David', %s, %s, '1990-07-20', 'Male', 'ACTIVE')
            RETURNING id;
        """, (p_code_john, phone_multi, phone_multi))
        john_id = cur.fetchone()[0]

        conn.commit()
        print(f"[SETUP] Created Gil Christ (ID: {gil_id}) and John David (ID: {john_id}) under {phone_multi}")
        
        conv_multi = f"WA_{phone_multi.replace('+', '')}"
        
        # ----------------------------------------------------
        # TEST 1: Mandatory Workflow (Book & Retrieve John David's Appointment)
        # ----------------------------------------------------
        print("\n--- TEST 1: Mandatory Booking & My Appointments Retrieval ---")
        # Select John David
        res_sel = agent_service.process_agent_message(conv_multi, "", f"btn_select_pat_{john_id}")
        assert "John David" in res_sel["response"], "John David profile should be selected"
        
        # Book appointment
        res_b1 = agent_service.process_agent_message(conv_multi, "", "btn_book_appt")
        res_b2 = agent_service.process_agent_message(conv_multi, "", "Chest pain consultation")
        
        doc_btns = [b for b in res_b2.get("interactive_buttons", []) if b.get("id", "").startswith("btn_doc_")]
        if doc_btns:
            res_b2 = agent_service.process_agent_message(conv_multi, "", doc_btns[0]["id"])

        date_btns = [b for b in res_b2.get("interactive_buttons", []) if b.get("id", "").startswith("btn_date_") and b["id"] != "btn_date_custom"]
        if date_btns:
            res_b3 = agent_service.process_agent_message(conv_multi, "", date_btns[0]["id"])
        else:
            res_b3 = agent_service.process_agent_message(conv_multi, "", "btn_date_tomorrow")
            
        date_btns = [b for b in res_b3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_date_") and b["id"] != "btn_date_custom"]
        if date_btns:
            res_b3 = agent_service.process_agent_message(conv_multi, "", date_btns[0]["id"])

        slots_b = [b for b in res_b3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_slot_")]
        assert len(slots_b) > 0, "Slots required"
        slot_id_b = slots_b[0]["id"]
        
        res_b4 = agent_service.process_agent_message(conv_multi, "", slot_id_b)
        res_b5 = agent_service.process_agent_message(conv_multi, "", "btn_confirm_appt")
        res_b6 = agent_service.process_agent_message(conv_multi, "", "btn_pay_paytm")
        res_b7 = agent_service.process_agent_message(conv_multi, "", "btn_pay_exec")
        
        state_after_booking = state_manager.get_conversation_state(conv_multi)
        b_id_1 = state_after_booking.get("booking_id")
        assert b_id_1 is not None, "Booking ID must exist"
        print(f"Booked Appointment ID: {b_id_1}")
        
        # Retrieve My Appointments
        res_appts = agent_service.process_agent_message(conv_multi, "", "btn_my_appts")
        print("My Appointments Output:\n", res_appts["response"].split('\n')[0])
        assert b_id_1 in res_appts["response"], f"Appointment {b_id_1} must be present in My Appointments"
        assert "You don't have any upcoming appointments" not in res_appts["response"], "Must NOT say no upcoming appointments"
        print(f"[PASS] Test 1 Passed: Newly created appointment {b_id_1} is correctly retrieved in My Appointments.")

        # ----------------------------------------------------
        # TEST 2: Multiple Appointments For Same Patient
        # ----------------------------------------------------
        print("\n--- TEST 2: Multiple Appointments For Same Patient ---")
        # Book Appointment #2 for John David
        res2_b1 = agent_service.process_agent_message(conv_multi, "", "btn_book_appt")
        res2_b2 = agent_service.process_agent_message(conv_multi, "", "Routine checkup")
        doc_btns = [b for b in res2_b2.get("interactive_buttons", []) if b.get("id", "").startswith("btn_doc_")]
        if doc_btns:
            res2_b2 = agent_service.process_agent_message(conv_multi, "", doc_btns[0]["id"])

        date_btns = [b for b in res2_b2.get("interactive_buttons", []) if b.get("id", "").startswith("btn_date_") and b["id"] != "btn_date_custom"]
        if date_btns:
            res2_b3 = agent_service.process_agent_message(conv_multi, "", date_btns[0]["id"])
        else:
            res2_b3 = agent_service.process_agent_message(conv_multi, "", "btn_date_tomorrow")
            
        date_btns = [b for b in res2_b3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_date_") and b["id"] != "btn_date_custom"]
        if date_btns:
            res2_b3 = agent_service.process_agent_message(conv_multi, "", date_btns[0]["id"])

        slots_b2 = [b for b in res2_b3.get("interactive_buttons", []) if b.get("id", "").startswith("btn_slot_")]
        assert len(slots_b2) > 0, "Slots required"
        slot_id_b2 = slots_b2[0]["id"]
        
        res2_b4 = agent_service.process_agent_message(conv_multi, "", slot_id_b2)
        res2_b5 = agent_service.process_agent_message(conv_multi, "", "btn_confirm_appt")
        res2_b6 = agent_service.process_agent_message(conv_multi, "", "btn_pay_paytm")
        res2_b7 = agent_service.process_agent_message(conv_multi, "", "btn_pay_exec")
        
        state_after_booking_2 = state_manager.get_conversation_state(conv_multi)
        b_id_2 = state_after_booking_2.get("booking_id")
        assert b_id_2 is not None, "Booking ID 2 must exist"
        print(f"Booked Second Appointment ID: {b_id_2}")
        
        res_appts_2 = agent_service.process_agent_message(conv_multi, "", "btn_my_appts")
        assert b_id_1 in res_appts_2["response"], f"First appointment {b_id_1} must be present"
        assert b_id_2 in res_appts_2["response"], f"Second appointment {b_id_2} must be present"
        print(f"[PASS] Test 2 Passed: Both appointments {b_id_1} and {b_id_2} displayed in My Appointments.")

        # ----------------------------------------------------
        # TEST 3: Multiple Patients Data Isolation
        # ----------------------------------------------------
        print("\n--- TEST 3: Multiple Patients Data Isolation ---")
        # Switch to Gil Christ
        res_sw = agent_service.process_agent_message(conv_multi, "", "btn_switch_patient")
        res_sel_gil = agent_service.process_agent_message(conv_multi, "", f"btn_select_pat_{gil_id}")
        assert "Gil Christ" in res_sel_gil["response"], "Gil Christ should be selected"
        
        res_appts_gil = agent_service.process_agent_message(conv_multi, "", "btn_my_appts")
        print("Gil Christ My Appointments:", res_appts_gil["response"])
        assert b_id_1 not in res_appts_gil["response"], f"John David's appointment {b_id_1} must NOT appear for Gil Christ"
        assert b_id_2 not in res_appts_gil["response"], f"John David's appointment {b_id_2} must NOT appear for Gil Christ"
        print("[PASS] Test 3 Passed: Gil Christ does NOT see John David's appointments.")

        print("\n==========================================")
        print("ALL MY APPOINTMENTS REGRESSION TESTS PASSED! ✅")
        print("==========================================")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run_my_appts_tests()
