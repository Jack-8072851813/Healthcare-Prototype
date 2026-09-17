import sys
import os
import datetime
import random

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
sys.path.insert(0, backend_dir)

import db_config
import agent.agent_service as agent_service
import agent.patient_identification_service as patient_id_service

def setup_multi_patient_data():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        rand_suffix = random.randint(10000, 99999)
        single_phone = f"+1555000{rand_suffix}"
        multi_phone = f"+1555669{rand_suffix}"

        # 1. Single patient setup
        p_code1 = f"P_SNG_{rand_suffix}"
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'Single', 'Patient', %s, %s, '1990-01-01', 'Male', 'ACTIVE')
            RETURNING id;
        """, (p_code1, single_phone, single_phone))
        sng_pat_id = cur.fetchone()[0]

        # 2. Multi patient setup (3 profiles under same WhatsApp number)
        p_code_gil = f"P_GIL_{rand_suffix}"
        p_code_ani = f"P_ANI_{rand_suffix}"
        p_code_rah = f"P_RAH_{rand_suffix}"

        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'Gil', 'Christ', %s, %s, '1985-05-15', 'Male', 'ACTIVE')
            RETURNING id;
        """, (p_code_gil, multi_phone, multi_phone))
        gil_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'Anitha', 'Nair', %s, %s, '1992-08-20', 'Female', 'ACTIVE')
            RETURNING id;
        """, (p_code_ani, multi_phone, multi_phone))
        anitha_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, phone, whatsapp_number, date_of_birth, gender, status)
            VALUES (%s, 'Rahul', 'Kumar', %s, %s, '1995-12-10', 'Male', 'ACTIVE')
            RETURNING id;
        """, (p_code_rah, multi_phone, multi_phone))
        rahul_id = cur.fetchone()[0]

        conn.commit()

        return {
            "single_phone": single_phone,
            "single_pat_id": sng_pat_id,
            "single_code": p_code1,
            "multi_phone": multi_phone,
            "gil_id": gil_id,
            "gil_code": p_code_gil,
            "anitha_id": anitha_id,
            "anitha_code": p_code_ani,
            "rahul_id": rahul_id,
            "rahul_code": p_code_rah
        }
    finally:
        cur.close()
        conn.close()


def run_tests():
    print("==========================================")
    print("STARTING MULTI-PATIENT REGRESSION TEST SUITE")
    print("==========================================")

    data = setup_multi_patient_data()
    print(f"\n[SETUP] Single phone: {data['single_phone']} (ID: {data['single_pat_id']})")
    print(f"[SETUP] Multi phone: {data['multi_phone']} (Gil: {data['gil_id']}, Anitha: {data['anitha_id']}, Rahul: {data['rahul_id']})")

    # ----------------------------------------------------
    # TEST 1: Single patient direct flow (Rule 1 & 13)
    # ----------------------------------------------------
    print("\n--- TEST 1: Single Patient Direct Flow (Rule 1) ---")
    conv_sng = f"WA_{data['single_phone'].replace('+', '')}"
    res1 = agent_service.process_agent_message(conv_sng, "", "btn_my_profile")
    print("Single Patient Output:", res1["response"])
    print("Buttons:", res1["interactive_buttons"])
    assert "Patient Profile Details" in res1["response"], "Single patient should directly view profile"
    assert data['single_code'] in res1["response"], "Single patient code should be in profile response"
    assert "Which patient would you like to access?" not in res1["response"], "No selection prompt for single patient"
    print("[PASS] Test 1 Passed: Single patient opens profile directly without selection prompt.")

    # ----------------------------------------------------
    # TEST 2: Multiple patients selection prompt (Rule 2)
    # ----------------------------------------------------
    print("\n--- TEST 2: Multiple Patients Prompt (Rule 2) ---")
    conv_multi = f"WA_{data['multi_phone'].replace('+', '')}"
    res2 = agent_service.process_agent_message(conv_multi, "", "btn_my_profile")
    print("Multi Patient Prompt Output:", res2["response"])
    print("Buttons:", res2["interactive_buttons"])
    assert "I found multiple patient profiles linked to this WhatsApp number" in res2["response"], "Should prompt for patient selection"
    btn_titles = [b["title"] for b in res2["interactive_buttons"]]
    assert any("Gil" in t for t in btn_titles), "Should include Gil in buttons"
    assert any("Anitha" in t for t in btn_titles), "Should include Anitha in buttons"
    assert any("Rahul" in t for t in btn_titles), "Should include Rahul in buttons"
    print("[PASS] Test 2 Passed: Multiple patient profiles trigger interactive selection buttons.")

    # ----------------------------------------------------
    # TEST 3: Patient Selection & Profile Display (Rule 3)
    # ----------------------------------------------------
    print("\n--- TEST 3: Select Gil Christ Profile (Rule 3) ---")
    res3 = agent_service.process_agent_message(conv_multi, "", f"btn_select_pat_{data['gil_id']}")
    print("Gil Profile Output:", res3["response"])
    assert "Patient Profile Details" in res3["response"], "Profile card should render"
    assert "Gil Christ" in res3["response"], "Only Gil's name should be displayed"
    assert data['gil_code'] in res3["response"], "Only Gil's patient code should be displayed"
    assert "Anitha" not in res3["response"], "Anitha info should NOT be present"
    print("[PASS] Test 3 Passed: Selecting Gil Christ displays ONLY Gil Christ's profile.")

    # ----------------------------------------------------
    # TEST 4: Persistence Across Workflow (Rule 4)
    # ----------------------------------------------------
    print("\n--- TEST 4: Selection Persistence (Rule 4) ---")
    res4 = agent_service.process_agent_message(conv_multi, "", "btn_my_appts")
    print("My Appointments Output:", res4["response"])
    assert "Which patient" not in res4["response"], "Should NOT prompt for patient selection again"
    state = agent_service.state_manager.get_conversation_state(conv_multi)
    assert state.get("selected_patient_id") == data["gil_id"], "Gil's patient ID must persist in state"
    print("[PASS] Test 4 Passed: selected_patient_id persists for subsequent actions.")

    # ----------------------------------------------------
    # TEST 5: Switch Patient (Rule 5)
    # ----------------------------------------------------
    print("\n--- TEST 5: Switch Patient to Anitha (Rule 5) ---")
    res5_sw = agent_service.process_agent_message(conv_multi, "", "btn_switch_patient")
    print("Switch Prompt Output:", res5_sw["response"])
    assert "I found multiple patient profiles" in res5_sw["response"], "Switch patient should present prompt"

    res5_sel = agent_service.process_agent_message(conv_multi, "", f"btn_select_pat_{data['anitha_id']}")
    print("Anitha Profile Output:", res5_sel["response"])
    assert "Anitha Nair" in res5_sel["response"], "Anitha's name should be displayed"
    assert data['anitha_code'] in res5_sel["response"], "Anitha's patient code should be displayed"
    assert "Gil" not in res5_sel["response"], "Gil info should NOT be present"
    state_sw = agent_service.state_manager.get_conversation_state(conv_multi)
    assert state_sw.get("selected_patient_id") == data["anitha_id"], "Selected patient should now be Anitha"
    print("[PASS] Test 5 Passed: Patient successfully switched to Anitha.")

    # ----------------------------------------------------
    # TEST 6: Ownership Security Validation (Rule 6)
    # ----------------------------------------------------
    print("\n--- TEST 6: Patient Ownership Security Check (Rule 6) ---")
    res6_fake = agent_service.process_agent_message(conv_multi, "", "btn_select_pat_999999")
    print("Unlinked Patient Selection Output:", res6_fake["response"])
    assert "Access denied" in res6_fake["response"], "Unlinked patient selection must be denied"

    res6_text = agent_service.process_agent_message(conv_multi, "", "P100999")
    print("Unlinked Code Text Output:", res6_text["response"])
    assert "Access denied" in res6_text["response"], "Unlinked patient code text input must be denied"
    print("[PASS] Test 6 Passed: Unlinked patient access is strictly denied.")

    # ----------------------------------------------------
    # TEST 7: General Hospital Questions (Rule 9)
    # ----------------------------------------------------
    print("\n--- TEST 7: General Hospital Questions (Rule 9) ---")
    # Reset selected_patient_id to test general query
    state_sw["selected_patient_id"] = None
    agent_service.state_manager.save_conversation_state(conv_multi, state_sw)

    res7 = agent_service.process_agent_message(conv_multi, "", "btn_hosp_info")
    print("General Info Output:", res7["response"])
    assert "Meridian Hospital Information" in res7["response"], "General hospital info should respond directly"
    assert "Which patient" not in res7["response"], "General questions do NOT require patient selection"
    print("[PASS] Test 7 Passed: General hospital questions work directly without patient selection.")

    # ----------------------------------------------------
    # TEST 8: Book Appointment Flow Protection (Rule 10)
    # ----------------------------------------------------
    print("\n--- TEST 8: Book Appointment Selection Gate (Rule 10) ---")
    res8 = agent_service.process_agent_message(conv_multi, "", "btn_book_appt")
    print("Book Appt Prompt Output:", res8["response"])
    assert "I found multiple patient profiles" in res8["response"], "Booking appt should prompt for patient selection first"

    res8_sel = agent_service.process_agent_message(conv_multi, "", f"btn_select_pat_{data['rahul_id']}")
    print("Book Appt Post-Selection Output:", res8_sel["response"])
    assert "Rahul" in res8_sel["response"], "Rahul should be selected for appointment booking"
    assert "describe the reason" in res8_sel["response"], "Booking workflow continues after selection"
    print("[PASS] Test 8 Passed: Book Appointment prompts patient selection before booking workflow.")

    print("\n==========================================")
    print("ALL MULTI-PATIENT REGRESSION TESTS PASSED! ✅")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
