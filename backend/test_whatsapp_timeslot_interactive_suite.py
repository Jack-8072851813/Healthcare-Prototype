import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent import agent_service, language_service, state_manager, tool_registry

class TestWhatsAppTimeSlotInteractiveSuite(unittest.TestCase):

    def setUp(self):
        self.conv_code = "TEST_WA_SLOT_INTERACTIVE"

    def test_01_build_verified_slot_selection_response_has_no_plain_bullets(self):
        """Test Case 1: build_verified_slot_selection_response generates interactive options and NO plain bullet text."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "entities": {
                "doctor_id": 10,
                "department_id": 2,
                "appointment_date": "2026-09-16",
                "appointment_time": None,
                "reason": "Skin consultation"
            },
            "interactive_buttons": []
        }
        mock_doc = {
            "id": 10,
            "name": "Dr. Wilson M",
            "department": "Dermatology",
            "qualification": "MD Dermatology",
            "experience_years": 12,
            "consultation_fee": 900
        }
        mock_slots = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]

        with patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):

            res = agent_service.build_verified_slot_selection_response(
                self.conv_code, state, 10, mock_doc, "2026-09-16", mock_slots, current_lang="ENGLISH"
            )
            resp_text = res["response"]
            buttons = res.get("interactive_buttons", [])

            # Assert NO plain text bullet list is in response_text
            self.assertNotIn("• 09:00 AM", resp_text)
            self.assertNotIn("• 09:30 AM", resp_text)
            
            # Assert clean header and prompt present
            self.assertIn("Available time slots", resp_text)
            self.assertIn("Dr. Wilson M", resp_text)
            self.assertIn("Dermatology", resp_text)
            self.assertIn("Please select an available time slot below:", resp_text)

            # Assert genuine interactive slot buttons generated
            self.assertEqual(len(buttons), 6)
            self.assertEqual(buttons[0]["id"], "btn_slot_09:00")
            self.assertEqual(buttons[0]["title"], "09:00 AM")
            self.assertEqual(buttons[5]["id"], "btn_slot_11:30")
            self.assertEqual(buttons[5]["title"], "11:30 AM")

    def test_02_dr_arun_kumar_valid_date_interactive(self):
        """Test Case 2: Dr. Arun Kumar on future date returns interactive options."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "intent": "BOOK_APPOINTMENT",
            "selected_doctor_id": 5,
            "entities": {
                "doctor_id": 5,
                "department_id": 1,
                "appointment_date": "2026-09-15",
                "appointment_time": None,
                "reason": "General Checkup"
            },
            "interactive_buttons": []
        }
        mock_doc = {"id": 5, "name": "Dr. Arun Kumar", "department": "General Medicine", "consultation_fee": 500}
        mock_slots = {"success": True, "slots": ["10:00", "11:00"]}

        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("agent.agent_service.resolve_doctor_details", return_value=mock_doc), \
             patch("agent.tool_registry.tool_get_available_slots", return_value=mock_slots):

            res = agent_service.process_agent_message(self.conv_code, None, "btn_date_2026-09-15")
            buttons = res.get("interactive_buttons", [])
            self.assertEqual(len(buttons), 2)
            self.assertEqual(buttons[0]["id"], "btn_slot_10:00")
            self.assertEqual(buttons[0]["title"], "10:00 AM")

    def test_04_date_with_zero_availability_fallbacks_to_date_selection(self):
        """Test Case 4: Date with 0 slots falls back gracefully to date selection response."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "intent": "BOOK_APPOINTMENT",
            "selected_doctor_id": 5,
            "entities": {
                "doctor_id": 5,
                "department_id": 1,
                "appointment_date": "2026-09-15",
                "appointment_time": None
            },
            "interactive_buttons": []
        }
        mock_doc = {"id": 5, "name": "Dr. Arun Kumar", "department": "General Medicine", "qualification": "MBBS", "experience_years": 10, "consultation_fee": 500}
        mock_slots = {"success": True, "slots": []}

        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("agent.agent_service.resolve_doctor_details", return_value=mock_doc), \
             patch("agent.tool_registry.tool_get_available_slots", return_value=mock_slots), \
             patch("agent.agent_service.get_verified_doctor_available_dates", return_value=[{"date": "2026-09-16", "title": "Tomorrow", "count": 4, "slots": ["09:00", "10:00"]}]):

            res = agent_service.process_agent_message(self.conv_code, None, "btn_date_2026-09-15")
            self.assertIn("Dr. Arun Kumar", res["response"])

    def test_06_patient_clicks_slot_updates_state_and_previews(self):
        """Test Case 6: Patient taps [btn_slot_11:30] -> state updated & transitions to CONFIRMATION_PENDING."""
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "patient_code": "P001",
            "intent": "BOOK_APPOINTMENT",
            "selected_doctor_id": 10,
            "entities": {
                "doctor_id": 10,
                "department_id": 2,
                "appointment_date": "2026-09-16",
                "appointment_time": None,
                "reason": "Dermatology check"
            },
            "interactive_buttons": []
        }
        mock_doc = {"id": 10, "name": "Dr. Wilson M", "department": "Dermatology", "consultation_fee": 900}
        mock_slots = {"success": True, "slots": ["09:00", "11:30"]}
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = ("Wilson", "Tony", "1990-01-01", "Male", "P001")
        mock_conn.cursor.return_value = mock_cur

        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection", return_value=mock_conn), \
             patch("agent.agent_service.resolve_doctor_details", return_value=mock_doc), \
             patch("agent.tool_registry.tool_get_available_slots", return_value=mock_slots):

            res = agent_service.process_agent_message(self.conv_code, None, "btn_slot_11:30")
            
            self.assertEqual(state["entities"]["appointment_time"], "11:30")
            self.assertEqual(state["conversation_state"], "CONFIRMATION_PENDING")
            self.assertTrue(state["confirmation_pending"])
            self.assertIn("Confirm Appointment", [b["title"] for b in res.get("interactive_buttons", [])])

    def test_10_multilingual_slot_selection_headers(self):
        """Test Case 10: Multilingual headers for Tamil, Hindi, and English."""
        mock_doc = {"id": 10, "name": "Dr. Wilson M", "department": "Dermatology"}
        slots = ["09:00", "10:00"]

        # Tamil
        state_tam = {"conversation_code": "TAM_TEST", "language": "TAMIL", "entities": {}}
        res_tam = agent_service.build_verified_slot_selection_response("TAM_TEST", state_tam, 10, mock_doc, "2026-09-16", slots, current_lang="TAMIL")
        self.assertIn("கிடைக்கும் நேரங்கள்", res_tam["response"])

        # Hindi
        state_hin = {"conversation_code": "HIN_TEST", "language": "HINDI", "entities": {}}
        res_hin = agent_service.build_verified_slot_selection_response("HIN_TEST", state_hin, 10, mock_doc, "2026-09-16", slots, current_lang="HINDI")
        self.assertIn("उपलब्ध समय स्लॉट", res_hin["response"])

        # English
        state_eng = {"conversation_code": "ENG_TEST", "language": "ENGLISH", "entities": {}}
        res_eng = agent_service.build_verified_slot_selection_response("ENG_TEST", state_eng, 10, mock_doc, "2026-09-16", slots, current_lang="ENGLISH")
        self.assertIn("Available time slots", res_eng["response"])

if __name__ == "__main__":
    unittest.main()
