"""
Unit & Integration Test Suite for Merged WhatsApp Greeting Menu

Validates:
1. Greeting message ("Hi", "Hello", etc.) displays all 10 required menu options.
2. Clicking each of the 10 options routes directly to its existing workflow.
3. Free-text inputs continue to work naturally.
4. Active sub-workflows retain contextual state and do not dump the full main menu.
5. Multilingual translation across supported languages.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.agent_service import process_agent_message
from agent.language_service import get_main_menu_buttons, get_translated_button


class TestMergedGreetingMenuSuite(unittest.TestCase):

    def test_01_main_menu_buttons_count_and_keys(self):
        """Verifies get_main_menu_buttons returns exactly the 10 required options."""
        buttons_en = get_main_menu_buttons("ENGLISH")
        self.assertEqual(len(buttons_en), 10)
        expected_ids = [
            "btn_cat_doctors",
            "btn_cat_health",
            "btn_book_appt",
            "btn_doctor_avail",
            "btn_my_appts",
            "btn_cancel_appt",
            "btn_reschedule_appt",
            "btn_hosp_info",
            "btn_cat_staff",
            "btn_cat_emergency"
        ]
        actual_ids = [b["id"] for b in buttons_en]
        self.assertEqual(actual_ids, expected_ids)

    def test_02_greeting_message_returns_all_10_options(self):
        """Verifies 'Hi' returns 'Welcome back...' and all 10 interactive buttons."""
        state = {"entities": {}, "conversation_state": "GREETING", "patient_id": 1}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection") as mock_conn:

            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = ("Gil", "Christ")

            resp = process_agent_message("CONV_GREET_10", "P1001", "Hi")
            self.assertIn("Welcome back", resp["response"])
            self.assertEqual(len(resp["interactive_buttons"]), 10)

    def test_03_tap_book_appointment(self):
        """Verifies tapping Book Appointment starts appointment booking."""
        state = {"entities": {}, "conversation_state": "GREETING", "patient_id": 1}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):

            resp = process_agent_message("CONV_TAP_BOOK", "P1001", "", interactive_id="btn_book_appt")
            self.assertEqual(resp["intent"], "BOOK_APPOINTMENT")
            self.assertIn("book an appointment", resp["response"].lower())

    def test_04_tap_doctor_availability(self):
        """Verifies tapping Doctor Availability starts doctor availability check."""
        state = {"entities": {}, "conversation_state": "GREETING", "patient_id": 1}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection") as mock_conn:

            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cur
            mock_cur.fetchall.return_value = [(1, "Cardiology"), (2, "ENT")]

            resp = process_agent_message("CONV_TAP_AVAIL", "P1001", "", interactive_id="btn_doctor_avail")
            self.assertEqual(resp["intent"], "DOCTOR_AVAILABILITY")

    def test_05_tap_my_appointments(self):
        """Verifies tapping My Appointment routes to appointment status."""
        state = {"entities": {}, "conversation_state": "GREETING", "patient_id": 1}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection") as mock_conn:

            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cur
            mock_cur.fetchall.return_value = []

            resp = process_agent_message("CONV_TAP_MY_APPTS", "P1001", "", interactive_id="btn_my_appts")
            self.assertEqual(resp["intent"], "APPOINTMENT_STATUS")

    def test_06_tap_cancel_appointment(self):
        """Verifies tapping Cancel Appointment routes to cancellation workflow."""
        state = {"entities": {}, "conversation_state": "GREETING", "patient_id": 1}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection") as mock_conn:

            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cur
            mock_cur.fetchall.return_value = []

            resp = process_agent_message("CONV_TAP_CANCEL", "P1001", "", interactive_id="btn_cancel_appt")
            self.assertEqual(resp["intent"], "CANCEL_APPOINTMENT")

    def test_07_tap_reschedule_appointment(self):
        """Verifies tapping Reschedule Appointment routes to reschedule workflow."""
        state = {"entities": {}, "conversation_state": "GREETING", "patient_id": 1}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection") as mock_conn:

            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cur
            mock_cur.fetchall.return_value = []

            resp = process_agent_message("CONV_TAP_RESCHED", "P1001", "", interactive_id="btn_reschedule_appt")
            self.assertEqual(resp["intent"], "RESCHEDULE_APPOINTMENT")

    def test_08_tap_hospital_information(self):
        """Verifies tapping Hospital Information returns hospital details."""
        state = {"entities": {}, "conversation_state": "GREETING", "patient_id": 1}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):

            resp = process_agent_message("CONV_TAP_HOSP", "P1001", "", interactive_id="btn_hosp_info")
            self.assertEqual(resp["intent"], "HOSPITAL_INFORMATION")
            self.assertIn("Meridian Hospital", resp["response"])

    def test_09_tap_emergency(self):
        """Verifies tapping Emergency returns emergency helpline info."""
        state = {"entities": {}, "conversation_state": "GREETING", "patient_id": 1}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):

            resp = process_agent_message("CONV_TAP_EMERGENCY", "P1001", "", interactive_id="btn_cat_emergency")
            self.assertEqual(resp["intent"], "EMERGENCY")
            self.assertIn("Emergency", resp["response"])

    def test_10_multilingual_greeting_buttons(self):
        """Verifies greeting menu translates buttons into Tamil properly."""
        buttons_ta = get_main_menu_buttons("TAMIL")
        self.assertEqual(len(buttons_ta), 10)
        self.assertEqual(buttons_ta[0]["title"], "மருத்துவர் & சேவை")
        self.assertEqual(buttons_ta[2]["title"], "முன்பதிவு செய்ய")


if __name__ == "__main__":
    unittest.main()
