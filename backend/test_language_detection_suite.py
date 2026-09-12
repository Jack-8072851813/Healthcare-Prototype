"""
test_language_detection_suite.py
================================
Automated test suite for Automatic Language Detection & Multilingual Persistence.
Verifies:
- Tamil greeting -> Tamil response
- Tamil appointment request -> Booking flow remains in Tamil
- Hindi greeting -> Hindi response
- Telugu greeting -> Telugu response
- Patient switches Tamil -> English -> English response without resetting workflow state
- Short messages ("yes", "10 AM") during Tamil flow -> Continue Tamil
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
import agent.language_service as language_service

class TestLanguageDetectionSuite(unittest.TestCase):

    def test_10_tamil_greeting(self):
        """Tamil greeting should return a Tamil response."""
        conv_code = f"WA_919876543210_LANG_10_{os.urandom(4).hex()}"
        res = agent_service.process_agent_message(conv_code, None, "வணக்கம்")
        self.assertIn("வணக்கம்", res["response"])
        self.assertEqual(res["language"], "TAMIL")

        state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(state["language"], "TAMIL")

    def test_11_tamil_appointment_request(self):
        """Tamil appointment booking request should keep language as TAMIL."""
        conv_code = f"WA_919876543210_LANG_11_{os.urandom(4).hex()}"
        agent_service.process_agent_message(conv_code, None, "வணக்கம்")
        res = agent_service.process_agent_message(conv_code, None, "எனக்கு ஒரு appointment வேண்டும்")
        self.assertEqual(res["language"], "TAMIL")

        state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(state["language"], "TAMIL")

    def test_12_hindi_greeting(self):
        """Hindi greeting should return a Hindi response."""
        conv_code = f"WA_919876543210_LANG_12_{os.urandom(4).hex()}"
        res = agent_service.process_agent_message(conv_code, None, "नमस्ते")
        self.assertIn("नमस्ते", res["response"])
        self.assertEqual(res["language"], "HINDI")

        state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(state["language"], "HINDI")

    def test_13_telugu_greeting(self):
        """Telugu greeting should return a Telugu response."""
        conv_code = f"WA_919876543210_LANG_13_{os.urandom(4).hex()}"
        res = agent_service.process_agent_message(conv_code, None, "నమస్తే")
        self.assertIn("నమస్తే", res["response"])
        self.assertEqual(res["language"], "TELUGU")

        state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(state["language"], "TELUGU")

    def test_14_patient_switches_tamil_to_english(self):
        """Switching from Tamil to English should change response language without resetting state entities."""
        conv_code = f"WA_919876543210_LANG_14_{os.urandom(4).hex()}"
        agent_service.process_agent_message(conv_code, None, "வணக்கம்")
        state = state_manager.get_conversation_state(conv_code)
        state["entities"]["doctor_id"] = 6
        state["entities"]["appointment_date"] = "2026-09-21"
        state_manager.save_conversation_state(conv_code, state)

        res = agent_service.process_agent_message(conv_code, None, "Show my appointments")
        self.assertEqual(res["language"], "ENGLISH")

        new_state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(new_state["entities"]["doctor_id"], 6)
        self.assertEqual(new_state["entities"]["appointment_date"], "2026-09-21")

    def test_15_short_message_yes_preserves_tamil_context(self):
        """Sending 'yes' inside a Tamil conversation should NOT switch conversation language to English."""
        conv_code = f"WA_919876543210_LANG_15_{os.urandom(4).hex()}"
        agent_service.process_agent_message(conv_code, None, "வணக்கம்")
        state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(state["language"], "TAMIL")

        res = agent_service.process_agent_message(conv_code, None, "yes")
        self.assertEqual(res["language"], "TAMIL")
        new_state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(new_state["language"], "TAMIL")

    def test_16_short_message_10_am_preserves_tamil_context(self):
        """Sending '10 AM' inside a Tamil conversation should NOT switch conversation language to English."""
        conv_code = f"WA_919876543210_LANG_16_{os.urandom(4).hex()}"
        agent_service.process_agent_message(conv_code, None, "வணக்கம்")
        state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(state["language"], "TAMIL")

        res = agent_service.process_agent_message(conv_code, None, "10 AM")
        self.assertEqual(res["language"], "TAMIL")
        new_state = state_manager.get_conversation_state(conv_code)
        self.assertEqual(new_state["language"], "TAMIL")

if __name__ == "__main__":
    unittest.main()
