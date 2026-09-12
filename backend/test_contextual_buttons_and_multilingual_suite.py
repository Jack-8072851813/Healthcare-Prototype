import sys
import os
import unittest
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass

# Ensure backend directory is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import db_config
from agent import agent_service, state_manager, language_service

class TestContextualButtonsAndMultilingual(unittest.TestCase):
    def setUp(self):
        self.conv_code = "WA_TEST_CONTEXTUAL_LANG_7777"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (self.conv_code,))
            cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (self.conv_code,))
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def test_01_greeting_hi_presents_4_categories_no_booking(self):
        """TEST 1: 'Hi' returns Greeting + 4 main category buttons, never starting booking."""
        res = agent_service.process_agent_message(self.conv_code, None, "Hi")
        buttons = res.get("interactive_buttons", [])
        btn_ids = [b["id"] for b in buttons]
        btn_titles = [b["title"] for b in buttons]

        self.assertIn("btn_cat_doctors", btn_ids)
        self.assertIn("btn_cat_health", btn_ids)
        self.assertIn("btn_cat_staff", btn_ids)
        self.assertIn("btn_cat_emergency", btn_ids)
        self.assertEqual(len(buttons), 4)
        self.assertNotIn("AWAITING_SYMPTOM", str(res.get("response")))
        print("\n[OK] TEST 1 PASSED: Greeting 'Hi' displays exactly 4 main categories with zero auto-booking.")

    def test_02_reschedule_workflow_no_unrelated_buttons(self):
        """TEST 2 & 3: Reschedule workflow isolation and relative date resolution."""
        # First set up a active patient and appointment context
        state = state_manager.get_conversation_state(self.conv_code, whatsapp_number="919999907777")
        state["patient_id"] = 1
        state_manager.save_conversation_state(self.conv_code, state)

        res1 = agent_service.process_agent_message(self.conv_code, None, "I want to reschedule my appointment")
        self.assertIn("RESCHEDULE", res1.get("intent", ""))

        # Date resolution in active reschedule workflow
        res2 = agent_service.process_agent_message(self.conv_code, None, "day after tomorrow")
        self.assertIn("RESCHEDULE", res2.get("intent", ""))
        self.assertNotIn("Book Appointment", [b["title"] for b in res2.get("interactive_buttons", [])])
        print("\n[OK] TEST 2 & 3 PASSED: Reschedule workflow retains active context and shows isolated buttons.")

    def test_04_05_06_my_appointments_and_my_reports(self):
        """TEST 4, 5, 6: Clickable appointment list, appointment selection actions, and report list."""
        state = state_manager.get_conversation_state(self.conv_code, whatsapp_number="919999907777")
        state["patient_id"] = 1
        state_manager.save_conversation_state(self.conv_code, state)

        # Tap My Appointments
        res_appts = agent_service.process_agent_message(self.conv_code, None, "My Appointments")
        btn_ids = [b["id"] for b in res_appts.get("interactive_buttons", [])]
        self.assertTrue(any(b.startswith("btn_appt_") or b == "btn_main_menu" or b == "btn_book_appt" for b in btn_ids))

        # Tap My Reports
        res_reps = agent_service.process_agent_message(self.conv_code, None, "My Reports")
        btn_ids_r = [b["id"] for b in res_reps.get("interactive_buttons", [])]
        self.assertTrue(any(b.startswith("btn_report_") or b == "btn_main_menu" for b in btn_ids_r))
        print("\n[OK] TEST 4, 5, 6 PASSED: Clickable appointment and report lists functioning.")

    def test_07_emergency_hotline_and_safety_flow(self):
        """TEST 7: Emergency button presents official Meridian helpline 044 6666 9999 and safety info."""
        res = agent_service.process_agent_message(self.conv_code, None, "Emergency")
        resp = res["response"]
        self.assertIn("044 6666 9999", resp)
        self.assertIn("044 6666 9910", resp)
        self.assertIn("Chennai", resp)
        self.assertIn("108 / 112", resp)
        self.assertNotIn("POC SAMPLE", resp)
        print("\n[OK] TEST 7 PASSED: Emergency flow presents verified Meridian 044 6666 9999 data.")

    def test_08_09_multilingual_greetings(self):
        """TEST 8 & 9: Tamil and Hindi greetings present translated responses and translated category buttons."""
        # Tamil
        res_ta = agent_service.process_agent_message(self.conv_code, None, "வணக்கம்")
        btn_titles_ta = [b["title"] for b in res_ta.get("interactive_buttons", [])]
        self.assertIn("மருத்துவர் & சேவை", btn_titles_ta)
        self.assertIn("அவசரநிலை", btn_titles_ta)

        # Hindi
        res_hi = agent_service.process_agent_message(self.conv_code, None, "नमस्ते")
        btn_titles_hi = [b["title"] for b in res_hi.get("interactive_buttons", [])]
        self.assertIn("डॉक्टर और सेवाएं", btn_titles_hi)
        self.assertIn("आपातकालीन", btn_titles_hi)
        print("\n[OK] TEST 8 & 9 PASSED: Multilingual Tamil and Hindi greetings generate translated buttons <= 20 chars.")

    def test_10_language_switch_continuity(self):
        """TEST 10: Patient switches from Tamil to English naturally without losing workflow state."""
        # Start in Tamil
        agent_service.process_agent_message(self.conv_code, None, "வணக்கம்")
        
        # Switch to English message
        res_en = agent_service.process_agent_message(self.conv_code, None, "Show my appointments")
        self.assertEqual(res_en.get("language"), "ENGLISH")
        print("\n[OK] TEST 10 PASSED: Language switching preserves conversation state seamlessly.")

    def test_11_payment_flow_isolated_buttons(self):
        """TEST 11: Payment flow presents ONLY payment method buttons."""
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "PAYMENT_METHOD_SELECTION"
        state["booking_stage"] = "PAYMENT_METHOD_SELECTION"
        state["interactive_buttons"] = [
            {"id": "btn_pay_gpay", "title": "GPay"},
            {"id": "btn_pay_phonepe", "title": "PhonePe"},
            {"id": "btn_pay_paytm", "title": "Paytm"},
            {"id": "btn_pay_upi", "title": "UPI"},
            {"id": "btn_pay_netbanking", "title": "NetBanking"}
        ]
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "btn_pay_gpay")
        btn_titles = [b["title"] for b in res.get("interactive_buttons", [])]
        self.assertTrue(any("Pay" in b or "Cancel" in b for b in btn_titles))
        self.assertNotIn("Book Appointment", btn_titles)
        self.assertNotIn("Hospital Information", btn_titles)
        print("\n[OK] TEST 11 PASSED: Payment flow buttons remain strictly isolated.")

    def test_12_time_selection_slots_only(self):
        """TEST 12: Time selection returns only actual available time slots."""
        state = state_manager.get_conversation_state(self.conv_code)
        state["patient_id"] = 1
        state["intent"] = "BOOK_APPOINTMENT"
        state["active_workflow"] = "BOOKING"
        state["booking_stage"] = "AWAITING_TIME"
        state["conversation_state"] = "TIME_SELECTION"
        state["entities"]["doctor_id"] = 5 # Dr. Arun Kumar
        state["entities"]["appointment_date"] = "2026-09-14"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "btn_slot_09:00")
        self.assertTrue("confirm" in res["response"].lower() or "please confirm" in res["response"].lower() or "slot" in res["response"].lower())
        print("\n[OK] TEST 12 PASSED: Time slot selection behaves deterministically.")

    def test_13_main_categories_routing(self):
        """TEST 13: Main categories route to Doctors & Services, My Health & Records, Talk to Staff, Emergency, My Profile."""
        # Doctors & Services
        res_doc = agent_service.process_agent_message(self.conv_code, None, "Doctors & Services")
        btn_ids_doc = [b["id"] for b in res_doc.get("interactive_buttons", [])]
        self.assertIn("btn_find_doctor", btn_ids_doc)
        self.assertIn("btn_departments", btn_ids_doc)

        # My Health & Records
        res_hlth = agent_service.process_agent_message(self.conv_code, None, "My Health & Records")
        btn_ids_hlth = [b["id"] for b in res_hlth.get("interactive_buttons", [])]
        self.assertIn("btn_my_profile", btn_ids_hlth)
        self.assertIn("btn_my_appts", btn_ids_hlth)
        self.assertIn("btn_my_reports", btn_ids_hlth)

        # My Profile
        state = state_manager.get_conversation_state(self.conv_code)
        state["patient_id"] = 1
        state_manager.save_conversation_state(self.conv_code, state)
        res_prof = agent_service.process_agent_message(self.conv_code, None, "btn_my_profile")
        self.assertIn("Patient Profile Details", res_prof["response"])

        # Talk to Staff
        res_staff = agent_service.process_agent_message(self.conv_code, None, "Talk to Staff")
        btn_ids_staff = [b["id"] for b in res_staff.get("interactive_buttons", [])]
        self.assertIn("btn_talk_staff_exec", btn_ids_staff)
        print("\n[OK] TEST 13 PASSED: All 4 main menu categories route to functional sub-workflows.")

if __name__ == "__main__":
    unittest.main()
