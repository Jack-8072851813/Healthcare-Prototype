import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent import agent_service, state_manager, tool_registry

class TestAllMockPaymentRequirements(unittest.TestCase):

    def setUp(self):
        self.conv_code = "TEST_PAYMENT_REQ"

    def test_01_confirm_appointment_does_not_create_appointment(self):
        """Tapping Confirm Appointment presents payment options, NO appointment is created."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "patient_code": "P001",
            "confirmation_pending": True,
            "entities": {
                "doctor_id": 10,
                "department_id": 21,
                "appointment_date": "2026-09-16",
                "appointment_time": "11:30",
                "reason": "Consultation"
            },
            "interactive_buttons": []
        }
        mock_doc = {"id": 10, "name": "Dr. Wilson M", "department": "Dermatology", "consultation_fee": 900}
        mock_slots = {"success": True, "slots": ["09:00", "11:30"]}

        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("agent.agent_service.resolve_doctor_details", return_value=mock_doc), \
             patch("agent.tool_registry.tool_get_available_slots", return_value=mock_slots), \
             patch("agent.tool_registry.tool_book_appointment") as mock_book:

            res = agent_service.process_agent_message(self.conv_code, None, "btn_confirm_appt")
            
            # Assert NO booking call occurred
            mock_book.assert_not_called()
            
            # Assert payment options returned
            self.assertIn("Payment Required", res["response"])
            self.assertIn("Consultation Fee: ₹900", res["response"])
            buttons = [b["id"] for b in res.get("interactive_buttons", [])]
            self.assertIn("btn_pay_gpay", buttons)
            self.assertIn("btn_pay_phonepe", buttons)

    def test_02_select_gpay_creates_pending_payment_prompt(self):
        """Selecting GPay creates PENDING payment record and displays Pay prompt."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "patient_code": "P001",
            "entities": {
                "doctor_id": 10,
                "department_id": 21,
                "appointment_date": "2026-09-16",
                "appointment_time": "11:30",
                "reason": "Consultation"
            },
            "interactive_buttons": []
        }
        mock_doc = {"id": 10, "name": "Dr. Wilson M", "department": "Dermatology", "consultation_fee": 900}
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = (101,)
        mock_conn.cursor.return_value = mock_cur

        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection", return_value=mock_conn), \
             patch("agent.agent_service.resolve_doctor_details", return_value=mock_doc), \
             patch("agent.tool_registry.tool_book_appointment") as mock_book:

            res = agent_service.process_agent_message(self.conv_code, None, "btn_pay_gpay")
            
            mock_book.assert_not_called()
            self.assertEqual(state.get("payment_method"), "GPAY")
            self.assertEqual(state.get("payment_status"), "PENDING")
            self.assertIn("Mock Payment", res["response"])
            self.assertIn("Pay ₹900", [b["title"] for b in res.get("interactive_buttons", [])])

    def test_03_mock_payment_success_creates_appointment(self):
        """Tapping Pay button executes payment and confirms appointment."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "patient_code": "P001",
            "payment_id": 101,
            "payment_method": "GPAY",
            "payment_amount": 900,
            "entities": {
                "doctor_id": 10,
                "department_id": 21,
                "appointment_date": "2026-09-16",
                "appointment_time": "11:30",
                "reason": "Consultation"
            },
            "interactive_buttons": []
        }
        mock_doc = {"id": 10, "name": "Dr. Wilson M", "department": "Dermatology", "consultation_fee": 900}
        mock_slots = {"success": True, "slots": ["11:30"]}
        mock_booking = {"success": True, "data": {"booking_id": "APT99999"}}
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = ("Wilson", "Tony", "1990-01-01", "Male", "P001")
        mock_conn.cursor.return_value = mock_cur

        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection", return_value=mock_conn), \
             patch("agent.agent_service.resolve_doctor_details", return_value=mock_doc), \
             patch("agent.tool_registry.tool_get_available_slots", return_value=mock_slots), \
             patch("agent.tool_registry.tool_book_appointment", return_value=mock_booking):

            res = agent_service.process_agent_message(self.conv_code, None, "btn_pay_exec")
            
            self.assertEqual(state.get("payment_status"), "SUCCESS")
            self.assertEqual(state.get("booking_id"), "APT99999")
            self.assertIn("Payment successful!", res["response"])
            self.assertIn("APT99999", res["response"])

    def test_04_cancel_payment_exits_without_booking(self):
        """Cancelling payment marks payment CANCELLED and does NOT create appointment."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "payment_id": 101,
            "entities": {
                "doctor_id": 10,
                "appointment_date": "2026-09-16",
                "appointment_time": "11:30"
            },
            "interactive_buttons": []
        }
        mock_conn = MagicMock()

        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection", return_value=mock_conn), \
             patch("agent.tool_registry.tool_book_appointment") as mock_book:

            res = agent_service.process_agent_message(self.conv_code, None, "btn_pay_cancel")
            
            mock_book.assert_not_called()
            self.assertEqual(state.get("payment_status"), "CANCELLED")
            self.assertIn("cancelled", res["response"].lower())

    def test_05_dynamic_doctor_fee_used(self):
        """Different doctors pass their respective consultation fees to payment prompt."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "confirmation_pending": True,
            "entities": {
                "doctor_id": 6,
                "department_id": 18,
                "appointment_date": "2026-09-22",
                "appointment_time": "14:00"
            },
            "interactive_buttons": []
        }
        mock_doc = {"id": 6, "name": "Dr. Priya Ramesh", "department": "Cardiology", "consultation_fee": 1200}
        mock_slots = {"success": True, "slots": ["14:00"]}

        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("agent.agent_service.resolve_doctor_details", return_value=mock_doc), \
             patch("agent.tool_registry.tool_get_available_slots", return_value=mock_slots):

            res = agent_service.process_agent_message(self.conv_code, None, "btn_confirm_appt")
            self.assertIn("Consultation Fee: ₹1200", res["response"])

if __name__ == "__main__":
    unittest.main()
