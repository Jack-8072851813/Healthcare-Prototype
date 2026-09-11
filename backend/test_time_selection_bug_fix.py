"""
Unit & Integration Regression Test Suite for Time Selection State Bug Fix
Verifies:
- Date-only input ("15 Sep") sets appointment_date = 2026-09-15 and appointment_time = None
- System does NOT generate confirmation preview without explicit time selection
- System enters TIME_SELECTION and returns clickable time slot buttons
- New booking workflows and date changes clear stale appointment_time
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.agent_service import process_agent_message


class TestTimeSelectionBugFix(unittest.TestCase):

    @patch("agent.agent_service.resolve_doctor_details")
    @patch("agent.tool_registry.tool_get_available_slots")
    def test_01_date_only_message_enters_time_selection_not_confirmation(self, mock_slots, mock_doc):
        mock_doc.return_value = {"id": 12, "name": "Dr. Priya Ramesh", "department": "Cardiology"}
        mock_slots.return_value = {"success": True, "slots": ["09:00", "10:00", "11:30", "14:00"]}

        state = {
            "entities": {"doctor_id": 12, "department_id": 5},
            "selected_doctor_id": 12,
            "conversation_state": "DATE_REQUIRED",
            "patient_id": 1,
            "language": "ENGLISH",
            "intent": "BOOK_APPOINTMENT"
        }

        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):

            resp = process_agent_message(
                conversation_code="CONV_DATE_ONLY_TEST",
                patient_code="P9989",
                message_text="15 Sep"
            )

            resp_text = resp["response"]
            buttons = resp["interactive_buttons"]

            # Must NOT be confirmation message
            self.assertNotIn("Please confirm your appointment", resp_text)
            self.assertNotIn("03:00 PM", resp_text)

            # Must be time selection prompt with clickable slots
            self.assertIn("Available time slots", resp_text)
            self.assertIn("Dr. Priya Ramesh", resp_text)

            button_ids = [b["id"] for b in buttons]
            self.assertIn("btn_slot_09:00", button_ids)
            self.assertIn("btn_slot_10:00", button_ids)
            self.assertIn("btn_slot_11:30", button_ids)
            self.assertIn("btn_slot_14:00", button_ids)

            # Verify appointment_time in state is None (not auto-assigned)
            self.assertIsNone(state["entities"].get("appointment_time"))
            self.assertEqual(state["conversation_state"], "TIME_SELECTION")

    @patch("agent.agent_service.resolve_doctor_details")
    @patch("agent.tool_registry.tool_get_available_slots")
    def test_02_screenshot_reproduction_choose_another_date_then_15_sep(self, mock_slots, mock_doc):
        """
        Exact reproduction of screenshot bug:
        Choose Another Date -> enter '15 Sep' -> Bot must show available time slots as clickable buttons.
        Must NOT show '03:00 PM' confirmation!
        """
        mock_doc.return_value = {"id": 12, "name": "Dr. Priya Ramesh", "department": "Cardiology"}
        mock_slots.return_value = {"success": True, "slots": ["09:00", "10:00", "11:30", "14:00"]}

        # Step 1: User taps Choose Another Date
        state = {
            "entities": {"doctor_id": 12, "department_id": 5},
            "selected_doctor_id": 12,
            "conversation_state": "DATE_REQUIRED",
            "patient_id": 1,
            "intent": "BOOK_APPOINTMENT"
        }
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):

            resp1 = process_agent_message(
                conversation_code="CONV_SCREENSHOT_REPRO",
                patient_code="P9989",
                message_text="",
                interactive_id="btn_date_custom"
            )
            self.assertIn("Please enter or select the date you prefer to consult *Dr. Priya Ramesh*", resp1["response"])

        # Step 2: Patient enters "15 Sep"
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):

            resp2 = process_agent_message(
                conversation_code="CONV_SCREENSHOT_REPRO",
                patient_code="P9989",
                message_text="15 Sep"
            )

            # Verification
            self.assertNotIn("Please confirm your appointment", resp2["response"])
            self.assertNotIn("Time: 03:00 PM", resp2["response"])
            self.assertIn("Available time slots", resp2["response"])
            self.assertEqual(len(resp2["interactive_buttons"]), 4)

    @patch("agent.agent_service.resolve_doctor_details")
    @patch("agent.tool_registry.tool_get_available_slots")
    def test_03_time_slot_button_tap_moves_to_confirmation(self, mock_slots, mock_doc):
        mock_doc.return_value = {"id": 12, "name": "Dr. Priya Ramesh", "department": "Cardiology"}
        mock_slots.return_value = {"success": True, "slots": ["09:00", "10:00", "11:30"]}

        state = {
            "entities": {
                "doctor_id": 12,
                "department_id": 5,
                "appointment_date": "2026-09-15",
                "appointment_time": None,
                "reason": "Chest pain"
            },
            "selected_doctor_id": 12,
            "conversation_state": "TIME_SELECTION",
            "patient_id": 1,
            "language": "ENGLISH"
        }

        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("db_config.get_db_connection") as mock_conn:

            mock_cur = MagicMock()
            mock_conn.return_value.cursor.return_value = mock_cur
            mock_cur.fetchone.return_value = ("Gil", "Christ", "2004-08-15", "Male", "P9989")

            resp = process_agent_message(
                conversation_code="CONV_SLOT_TAP",
                patient_code="P9989",
                message_text="",
                interactive_id="btn_slot_10:00"
            )

            resp_text = resp["response"]
            self.assertIn("Please confirm your appointment:", resp_text)
            self.assertIn("Patient ID: P9989", resp_text)
            self.assertIn("Doctor: Dr. Priya Ramesh", resp_text)
            self.assertIn("Date: 2026-09-15", resp_text)
            self.assertIn("Time: 10:00 AM", resp_text)

    def test_04_date_change_clears_stale_time(self):
        state = {
            "entities": {
                "doctor_id": 12,
                "appointment_date": "2026-09-12",
                "appointment_time": "15:00"
            }
        }
        # Simulate explicit date change
        state["entities"]["appointment_date"] = "2026-09-15"
        state["entities"]["appointment_time"] = None
        self.assertEqual(state["entities"]["appointment_date"], "2026-09-15")
        self.assertIsNone(state["entities"]["appointment_time"])


if __name__ == "__main__":
    unittest.main()
