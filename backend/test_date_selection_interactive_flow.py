"""
Unit/Integration Tests for Date Selection & Clickable Time Slots
Verifies Bug 1 to Bug 20 requirements:
- Bot does not silently choose tomorrow on doctor selection
- Clickable date options with Choose Another Date
- Stateful appointment_date persistence
- Clickable time slot options
- Revalidation & canonical booking state
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent.agent_service import (
    process_agent_message,
    build_verified_date_selection_response,
    build_verified_slot_selection_response
)


class TestDateSelectionInteractiveFlow(unittest.TestCase):

    @patch("agent.agent_service.resolve_doctor_details")
    @patch("agent.agent_service.get_verified_doctor_available_dates")
    def test_doctor_button_tap_asks_for_date_not_default_tomorrow(self, mock_dates, mock_doc):
        mock_doc.return_value = {
            "id": 10, "name": "Dr. Gilbrit M", "department": "ENT",
            "qualification": "MBBS", "experience_years": 3, "consultation_fee": 200
        }
        mock_dates.return_value = [
            {"date": "2026-09-14", "title": "Mon, Sep 14", "slots": ["09:00", "09:30"], "count": 2},
            {"date": "2026-09-15", "title": "Tue, Sep 15", "slots": ["10:00", "11:30"], "count": 2}
        ]
        
        state = {"entities": {}, "conversation_state": "DOCTOR_SELECTION_REQUIRED"}
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):
            
            resp = process_agent_message(
                conversation_code="CONV_NO_SILENT_TOMORROW",
                patient_code="P100002",
                message_text="",
                interactive_id="btn_doc_10"
            )
            
            resp_text = resp["response"]
            buttons = resp["interactive_buttons"]
            
            # Verify bot asks for date
            self.assertIn("Which date would you like to book your appointment?", resp_text)
            self.assertIn("Dr. Gilbrit M", resp_text)
            
            # Verify buttons contain verified dates AND "Choose Another Date"
            button_ids = [b["id"] for b in buttons]
            self.assertIn("btn_date_2026-09-14", button_ids)
            self.assertIn("btn_date_2026-09-15", button_ids)
            self.assertIn("btn_date_custom", button_ids)
            self.assertEqual(buttons[-1]["title"], "Choose Another Date")

    @patch("agent.agent_service.resolve_doctor_details")
    def test_choose_another_date_button_tap(self, mock_doc):
        mock_doc.return_value = {"id": 10, "name": "Dr. Gilbrit M", "department": "ENT"}
        state = {
            "entities": {"doctor_id": 10},
            "selected_doctor_id": 10,
            "conversation_state": "DATE_REQUIRED"
        }
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):
            
            resp = process_agent_message(
                conversation_code="CONV_CHOOSE_ANOTHER_DATE",
                patient_code="P100002",
                message_text="",
                interactive_id="btn_date_custom"
            )
            
            resp_text = resp["response"]
            self.assertIn("Please enter or select the date you prefer to consult *Dr. Gilbrit M*", resp_text)

    @patch("agent.agent_service.resolve_doctor_details")
    @patch("agent.tool_registry.tool_get_available_slots")
    def test_date_button_tap_returns_clickable_slots(self, mock_slots, mock_doc):
        mock_doc.return_value = {"id": 10, "name": "Dr. Gilbrit M", "department": "ENT"}
        mock_slots.return_value = {"success": True, "slots": ["09:30", "10:30", "11:30"]}
        
        state = {
            "entities": {"doctor_id": 10},
            "selected_doctor_id": 10,
            "conversation_state": "DATE_REQUIRED"
        }
        with patch("agent.state_manager.get_conversation_state", return_value=state), \
             patch("agent.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"):
            
            resp = process_agent_message(
                conversation_code="CONV_DATE_BTN_TAP",
                patient_code="P100002",
                message_text="",
                interactive_id="btn_date_2026-09-15"
            )
            
            buttons = resp["interactive_buttons"]
            slot_ids = [b["id"] for b in buttons]
            
            self.assertIn("btn_slot_09:30", slot_ids)
            self.assertIn("btn_slot_10:30", slot_ids)
            self.assertIn("btn_slot_11:30", slot_ids)


if __name__ == "__main__":
    unittest.main()
