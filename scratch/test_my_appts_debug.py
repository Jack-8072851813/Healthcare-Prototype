import sys
import os
import random

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.getcwd())
backend_dir = os.path.join(os.getcwd(), "backend")
sys.path.insert(0, backend_dir)

import db_config
import agent.agent_service as agent_service
import agent.state_manager as state_manager

def debug_my_appts():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        rand_val = random.randint(10000, 99999)
        phone = f"+1555888{rand_val}"
        
        # 1. Create Gil Christ (P9989) and John David (P2666) under same phone
        p_code_gil = f"P9989_{rand_val}"
        p_code_john = f"P2666_{rand_val}"
        
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'Gil', 'Christ', %s, %s, '1985-05-15', 'Male', 'ACTIVE')
            RETURNING id;
        """, (p_code_gil, phone, phone))
        gil_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'John', 'David', %s, %s, '1990-07-20', 'Male', 'ACTIVE')
            RETURNING id;
        """, (p_code_john, phone, phone))
        john_id = cur.fetchone()[0]

        conn.commit()
        print(f"[SETUP] Created Gil Christ (ID: {gil_id}, Code: {p_code_gil}) and John David (ID: {john_id}, Code: {p_code_john}) under {phone}")
        
        conv = f"WA_{phone.replace('+', '')}"
        
        # 2. Select John David
        res_sel = agent_service.process_agent_message(conv, "", f"btn_select_pat_{john_id}")
        print("Selected Patient Response:", res_sel["response"].split('\n')[0])
        
        state_after_sel = state_manager.get_conversation_state(conv)
        print("State after selection:", "selected_patient_id =", state_after_sel.get("selected_patient_id"), "patient_id =", state_after_sel.get("patient_id"))
        
        # 3. Book appointment for John David
        res_b1 = agent_service.process_agent_message(conv, "", "btn_book_appt")
        res_b2 = agent_service.process_agent_message(conv, "", "Chest pain consultation")
        
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
        assert len(slots_b) > 0, f"Slots required, got {res_b3.get('interactive_buttons')}"
        slot_id_b = slots_b[0]["id"]
        
        res_b4 = agent_service.process_agent_message(conv, "", slot_id_b)
        res_b5 = agent_service.process_agent_message(conv, "", "btn_confirm_appt")
        res_b6 = agent_service.process_agent_message(conv, "", "btn_pay_paytm")
        res_b7 = agent_service.process_agent_message(conv, "", "btn_pay_exec")
        
        print("Booking Confirmation Output:", res_b7["response"].split('\n')[0])
        state_after_booking = state_manager.get_conversation_state(conv)
        b_id = state_after_booking.get("booking_id")
        print("State after booking:", "booking_id =", b_id, "selected_patient_id =", state_after_booking.get("selected_patient_id"), "patient_id =", state_after_booking.get("patient_id"))
        
        # Check DB appointment record
        cur.execute("SELECT id, booking_id, patient_id, doctor_id, appointment_date, appointment_time, status FROM appointments WHERE booking_id = %s;", (b_id,))
        appt_db_row = cur.fetchone()
        print("DB Appointment Row:", appt_db_row)

        # 4. Now user clicks 'My Appointments'
        res_appts = agent_service.process_agent_message(conv, "", "btn_my_appts")
        print("My Appointments Output:\n", res_appts["response"])
        print("My Appointments Buttons:", res_appts.get("interactive_buttons"))
        
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    debug_my_appts()
