import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure backend directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent import language_service, agent_service, state_manager

class TestTalkToStaffContactsSuite(unittest.TestCase):

    def test_english_contact_details_on_button_exec(self):
        conv_code = "TEST_STAFF_ENG"
        state = {
            "conversation_code": conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "entities": {},
            "interactive_buttons": []
        }
        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):
            res = agent_service.process_agent_message(conv_code, None, "btn_talk_staff_exec")
            
            resp = res["response"]
            self.assertEqual(res["intent"], "HUMAN_ESCALATION")
            self.assertIn("044 6666 9910", resp)
            self.assertIn("044 6666 9999", resp)
            self.assertIn("info@meridian-hospital.com", resp)
            self.assertIn("#46D, Jawaharlal Nehru Road", resp)
            self.assertIn("I am connecting you with a hospital staff member", resp)

    def test_tamil_contact_details_on_button_exec(self):
        conv_code = "TEST_STAFF_TAM"
        state = {
            "conversation_code": conv_code,
            "language": "TAMIL",
            "patient_id": 1,
            "entities": {},
            "interactive_buttons": []
        }
        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):
            res = agent_service.process_agent_message(conv_code, None, "btn_talk_staff_exec")
            
            resp = res["response"]
            self.assertEqual(res["intent"], "HUMAN_ESCALATION")
            self.assertIn("044 6666 9910", resp)
            self.assertIn("044 6666 9999", resp)
            self.assertIn("info@meridian-hospital.com", resp)
            self.assertIn("மருத்துவமனை உதவி குழுவுடன் உங்களை இணைக்கிறேன்", resp)

    def test_hindi_contact_details_on_button_exec(self):
        conv_code = "TEST_STAFF_HIN"
        state = {
            "conversation_code": conv_code,
            "language": "HINDI",
            "patient_id": 1,
            "entities": {},
            "interactive_buttons": []
        }
        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):
            res = agent_service.process_agent_message(conv_code, None, "btn_talk_staff_exec")
            
            resp = res["response"]
            self.assertEqual(res["intent"], "HUMAN_ESCALATION")
            self.assertIn("044 6666 9910", resp)
            self.assertIn("044 6666 9999", resp)
            self.assertIn("मैं आपको अस्पताल के कर्मचारी से जोड़ रहा हूं", resp)

    def test_continue_with_ai_button(self):
        conv_code = "TEST_CONT_AI"
        state = {
            "conversation_code": conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "entities": {},
            "interactive_buttons": []
        }
        with patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):
            res = agent_service.process_agent_message(conv_code, None, "btn_continue_ai")
            
            self.assertEqual(res["intent"], "GREETING")
            self.assertIn("Welcome back! How can I help you today?", res["response"])

    def test_text_escalation_triggers_contacts_and_open_status(self):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [(1, 1), None]  # (conv_id, pat_id), no open escalation
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        conv_code = "TEST_TEXT_ESC"
        state = {
            "conversation_code": conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "entities": {},
            "interactive_buttons": []
        }

        with patch("db_config.get_db_connection", return_value=mock_conn), \
             patch("agent.agent_service.state_manager.get_conversation_state", return_value=state), \
             patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("agent.agent_service.log_agent_action"):

            res = agent_service.process_agent_message(conv_code, None, "I want to talk to staff")
            resp = res["response"]
            
            self.assertEqual(res["intent"], "HUMAN_ESCALATION")
            self.assertIn("044 6666 9910", resp)
            self.assertIn("044 6666 9999", resp)
            self.assertIn("info@meridian-hospital.com", resp)
            self.assertIn("Status: 🟡 OPEN", resp)

    def test_no_fake_numbers_or_placeholders(self):
        for lang in ["ENGLISH", "TAMIL", "HINDI", "TELUGU", "MALAYALAM", "KANNADA", "URDU"]:
            resp = language_service.get_talk_to_staff_contact_response(lang)
            self.assertNotIn("POC SAMPLE", resp)
            self.assertNotIn("+91 99999", resp)
            self.assertNotIn("+91 88888", resp)
            self.assertNotIn("sample@", resp)
            self.assertIn("044 6666 9910", resp)
            self.assertIn("044 6666 9999", resp)

if __name__ == "__main__":
    unittest.main()
