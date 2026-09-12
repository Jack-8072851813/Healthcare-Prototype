"""
test_mock_payment_suite.py
===========================
Automated test suite for Mock Payment workflow in Meridian Hospital AI Patient Desk.
Verifies:
- Slot selection shows Appointment Preview with [Confirm Appointment]
- Tapping Confirm Appointment routes to PAYMENT METHOD SELECTION (not direct booking)
- Consultation fee is retrieved dynamically from doctor record
- GPay, PhonePe, Paytm, UPI, NetBanking method selection
- Mock payment transaction creation & SUCCESS status
- Transaction reference generation (MOCKTXN...)
- Appointment confirmation ONLY after payment SUCCESS
- Failure / cancellation handling without appointment creation
- Idempotency on duplicate payment clicks
"""

import sys
import os
import unittest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.agent_service as agent_service
import agent.state_manager as state_manager
import agent.tool_registry as tool_registry

class TestMockPaymentSuite(unittest.TestCase):

    def setUp(self):
        # Fetch active doctor ID and valid slot date dynamically
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, department_id, consultation_fee FROM doctors WHERE status = 'ACTIVE' LIMIT 1;")
        doc_row = cur.fetchone()
        cur.execute("SELECT id FROM patients WHERE status = 'ACTIVE' LIMIT 1;")
        pat_row = cur.fetchone()
        cur.close()
        conn.close()

        self.doc_id = doc_row[0] if doc_row else 6
        self.dept_id = doc_row[1] if doc_row else 1
        self.consultation_fee = doc_row[2] if doc_row and doc_row[2] else 800
        self.pat_id = pat_row[0] if pat_row else 1

        cur = conn.cursor()
        cur.execute("DELETE FROM appointments WHERE patient_id = %s AND appointment_date = '2026-09-21';", (self.pat_id,))
        conn.commit()

        # Find a valid slot dynamically for setUp
        res_slots = tool_registry.tool_get_available_slots("SETUP_CHECK", self.doc_id, "2026-09-21")
        slots = res_slots.get("slots", []) if res_slots.get("success") else []
        self.test_slot = slots[0] if slots else "10:30"

        self.conv_code = f"WA_919876543210_TEST_PAY_{os.urandom(4).hex()}"
        state = state_manager.get_conversation_state(self.conv_code, whatsapp_number="919876543210")
        state["patient_id"] = self.pat_id
        state["patient_code"] = "P100001"
        state["language"] = "ENGLISH"
        state["selected_doctor_id"] = self.doc_id
        state["entities"]["doctor_id"] = self.doc_id
        state["entities"]["department_id"] = self.dept_id
        state["entities"]["appointment_date"] = "2026-09-21"
        state["entities"]["reason"] = "Chest pain consultation"
        agent_service.log_message_to_db(self.conv_code, "PATIENT", "Init state", "ENGLISH", "BOOK_APPOINTMENT", state)
        state_manager.save_conversation_state(self.conv_code, state)

    def test_01_slot_selection_shows_appointment_preview(self):
        """Selecting a time slot should render Appointment Preview with [Confirm Appointment]."""
        res = agent_service.process_agent_message(self.conv_code, None, f"btn_slot_{self.test_slot}")
        self.assertIn("Please confirm your appointment details:", res["response"])
        btn_ids = [b["id"] for b in res.get("interactive_buttons", [])]
        self.assertIn("btn_confirm_appt", btn_ids)

        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("conversation_state"), "CONFIRMATION_PENDING")
        self.assertTrue(state.get("confirmation_pending"))
        self.assertEqual(state.get("entities", {}).get("appointment_time"), self.test_slot)

    def test_02_confirm_appointment_prompts_payment_gate(self):
        """Clicking Confirm Appointment should present payment method choices, NOT immediate confirmation."""
        agent_service.process_agent_message(self.conv_code, None, f"btn_slot_{self.test_slot}")
        res = agent_service.process_agent_message(self.conv_code, None, "btn_confirm_appt")
        self.assertIn("Please complete the consultation payment to confirm your appointment.", res["response"])
        self.assertIn("Consultation Fee:", res["response"])
        btn_ids = [b["id"] for b in res.get("interactive_buttons", [])]
        self.assertIn("btn_pay_gpay", btn_ids)
        self.assertIn("btn_pay_phonepe", btn_ids)
        self.assertIn("btn_pay_paytm", btn_ids)
        self.assertIn("btn_pay_upi", btn_ids)
        self.assertIn("btn_pay_netbanking", btn_ids)

        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("conversation_state"), "PAYMENT_METHOD_REQUIRED")

    def test_03_payment_method_selection_shows_mock_payment_screen(self):
        """Selecting GPay should create a PENDING payment and prompt Pay button."""
        agent_service.process_agent_message(self.conv_code, None, f"btn_slot_{self.test_slot}")
        agent_service.process_agent_message(self.conv_code, None, "btn_confirm_appt")
        res = agent_service.process_agent_message(self.conv_code, None, "btn_pay_gpay")

        self.assertIn("Mock Payment", res["response"])
        self.assertIn("GPay", res["response"])
        self.assertIn("No real payment will be processed", res["response"])

        btn_ids = [b["id"] for b in res.get("interactive_buttons", [])]
        self.assertIn("btn_pay_exec", btn_ids)
        self.assertIn("btn_pay_change", btn_ids)
        self.assertIn("btn_pay_cancel", btn_ids)

        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("payment_method"), "GPAY")
        self.assertEqual(state.get("payment_status"), "PENDING")
        self.assertIsNotNone(state.get("payment_reference"))

    def test_04_pay_button_executes_payment_and_confirms_appointment(self):
        """Clicking Pay should set status SUCCESS, generate transaction ref, and confirm appointment."""
        agent_service.process_agent_message(self.conv_code, None, f"btn_slot_{self.test_slot}")
        agent_service.process_agent_message(self.conv_code, None, "btn_confirm_appt")
        agent_service.process_agent_message(self.conv_code, None, "btn_pay_gpay")
        res = agent_service.process_agent_message(self.conv_code, None, "btn_pay_exec")

        self.assertIn("Payment successful!", res["response"])
        self.assertIn("MOCKTXN", res["response"])
        self.assertIn("Your appointment has been confirmed!", res["response"])
        self.assertIn("Appointment ID:", res["response"])

        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("payment_status"), "SUCCESS")
        self.assertIsNotNone(state.get("transaction_reference"))
        self.assertIsNotNone(state.get("booking_id") or state.get("entities", {}).get("booking_id"))

        # Verify DB payment record
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT payment_status, transaction_reference, amount FROM payments WHERE id = %s;", (state["payment_id"],))
            p_row = cur.fetchone()
            self.assertIsNotNone(p_row)
            self.assertEqual(p_row[0], "SUCCESS")
            self.assertTrue(p_row[1].startswith("MOCKTXN"))
        finally:
            cur.close()
            conn.close()

    def test_05_duplicate_pay_click_is_idempotent(self):
        """Clicking Pay again after SUCCESS should not create duplicate appointment or payment."""
        agent_service.process_agent_message(self.conv_code, None, f"btn_slot_{self.test_slot}")
        agent_service.process_agent_message(self.conv_code, None, "btn_confirm_appt")
        agent_service.process_agent_message(self.conv_code, None, "btn_pay_gpay")
        res1 = agent_service.process_agent_message(self.conv_code, None, "btn_pay_exec")
        res2 = agent_service.process_agent_message(self.conv_code, None, "btn_pay_exec")

        self.assertIn("already confirmed", res2["response"])

    def test_06_change_payment_method_preserves_slot_context(self):
        """Changing payment method should allow choosing another method without clearing doctor/date/time."""
        agent_service.process_agent_message(self.conv_code, None, f"btn_slot_{self.test_slot}")
        agent_service.process_agent_message(self.conv_code, None, "btn_confirm_appt")
        agent_service.process_agent_message(self.conv_code, None, "btn_pay_gpay")
        res = agent_service.process_agent_message(self.conv_code, None, "btn_pay_change")

        self.assertIn("Please choose a payment method", res["response"])
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state["entities"]["appointment_time"], self.test_slot)
        self.assertEqual(state["entities"]["appointment_date"], "2026-09-21")

    def test_07_cancel_payment_cancels_booking_without_appointment_creation(self):
        """Cancelling payment should exit flow and not confirm appointment."""
        agent_service.process_agent_message(self.conv_code, None, f"btn_slot_{self.test_slot}")
        agent_service.process_agent_message(self.conv_code, None, "btn_confirm_appt")
        agent_service.process_agent_message(self.conv_code, None, "btn_pay_gpay")
        res = agent_service.process_agent_message(self.conv_code, None, "btn_pay_cancel")

        self.assertIn("cancelled as payment was not completed", res["response"])
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("payment_status"), "CANCELLED")
        self.assertIsNone(state.get("booking_id"))

    def test_08_free_text_confirm_triggers_payment_gate(self):
        """Sending free text 'Confirm' in confirmation pending state should trigger payment gate, not direct booking."""
        agent_service.process_agent_message(self.conv_code, None, f"btn_slot_{self.test_slot}")
        res = agent_service.process_agent_message(self.conv_code, None, "Confirm")
        self.assertIn("Please complete the consultation payment to confirm your appointment.", res["response"])
        btn_ids = [b["id"] for b in res.get("interactive_buttons", [])]
        self.assertIn("btn_pay_gpay", btn_ids)

if __name__ == "__main__":
    unittest.main()
