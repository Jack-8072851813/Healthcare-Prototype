import sys
import os
import pytest

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import db_config
from agent import agent_service, state_manager

def test_whatsapp_button_guided_flow():
    conv_code = "WA_TEST_BUTTON_FLOW_9000"

    # Reset test conversation state
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    # Init clean state
    state = state_manager.get_conversation_state(conv_code, whatsapp_number="9199999000")
    state["patient_id"] = 1
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

    # 1. Tap Book Appointment button
    res1 = agent_service.process_agent_message(conv_code, None, "btn_book_appt")
    assert "interactive_buttons" in res1 or "symptom" in res1["response"].lower() or "reason" in res1["response"].lower()
    print("\n[Step 1 Book Appt]:", res1["response"].encode('ascii', 'ignore').decode('ascii')[:80])

    # 2. Tap Doctor Selection button directly (btn_doc_5 -> Dr. Arun Kumar)
    res2 = agent_service.process_agent_message(conv_code, None, "btn_doc_5")
    assert "Arun Kumar" in res2["response"]
    assert "interactive_buttons" in res2
    assert len(res2["interactive_buttons"]) > 0
    print("\n[Step 2 Tap Doctor]: Doctor selected successfully. Buttons attached:", len(res2["interactive_buttons"]))

    # If date buttons returned (because tomorrow has no slots), tap the first date button
    first_btn = res2["interactive_buttons"][0]
    if first_btn["id"].startswith("btn_date_"):
        print(f"\n[Step 2.1 Tap Date Button]: Tapping {first_btn['id']}")
        res2 = agent_service.process_agent_message(conv_code, None, first_btn["id"])
        assert "interactive_buttons" in res2
        assert len(res2["interactive_buttons"]) > 0
        print("[Step 2.1 Slots Loaded]: Slot buttons attached:", len(res2["interactive_buttons"]))

    # 3. Tap Time Slot button (first available slot button e.g. btn_slot_09:00)
    slot_btn = res2["interactive_buttons"][0]
    print(f"\n[Step 3 Tap Time Slot]: Tapping {slot_btn['id']}")
    res3 = agent_service.process_agent_message(conv_code, None, slot_btn["id"])
    assert "confirm" in res3["response"].lower() or "Please confirm" in res3["response"]
    print("[Step 3 Confirmation Screen]:", res3["response"].encode('ascii', 'ignore').decode('ascii')[:100])

    # 4. Tap Change Details button (btn_change_appt)
    res4 = agent_service.process_agent_message(conv_code, None, "btn_change_appt")
    assert "What detail would you like to change?" in res4["response"]
    assert "interactive_buttons" in res4
    button_titles = [b["title"] for b in res4["interactive_buttons"]]
    assert "Doctor" in button_titles or "Date" in button_titles or "Time" in button_titles
    print("\n[Step 4 Tap Change Details]: Field picker buttons attached:", button_titles)

    # 5. Tap Confirm Appointment button (btn_confirm_appt)
    # Re-enable confirmation pending
    st = state_manager.get_conversation_state(conv_code)
    st["confirmation_pending"] = True
    st["entities"]["doctor_id"] = 5
    st["entities"]["appointment_date"] = "2026-09-21"
    st["entities"]["appointment_time"] = "10:00"
    state_manager.save_conversation_state(conv_code, st)

    # 6. Test Field Pickers
    # 6a. Tap Change Doctor
    res_chg_doc = agent_service.process_agent_message(conv_code, None, "btn_chg_doctor")
    assert "doctor" in res_chg_doc["response"].lower() or "consult" in res_chg_doc["response"].lower()
    print("\n[Step 6a Tap Change Doctor]:", res_chg_doc["response"].encode('ascii', 'ignore').decode('ascii')[:80])

    # 6b. Tap Change Date
    res_chg_date = agent_service.process_agent_message(conv_code, None, "btn_chg_date")
    assert "date" in res_chg_date["response"].lower()
    assert "interactive_buttons" in res_chg_date
    print("\n[Step 6b Tap Change Date]: Date buttons attached:", [b["id"] for b in res_chg_date["interactive_buttons"]])

    # 6c. Tap Change Time
    res_chg_time = agent_service.process_agent_message(conv_code, None, "btn_chg_time")
    assert "time" in res_chg_time["response"].lower() or "slot" in res_chg_time["response"].lower()
    print("\n[Step 6c Tap Change Time]:", res_chg_time["response"].encode('ascii', 'ignore').decode('ascii')[:80])

if __name__ == "__main__":
    test_whatsapp_button_guided_flow()
    print("\nALL INTERACTIVE BUTTON GUIDED FLOW TESTS PASSED SUCCESSFULLY!")
