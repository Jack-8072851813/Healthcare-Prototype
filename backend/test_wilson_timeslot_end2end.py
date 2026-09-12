import unittest
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agent import agent_service, state_manager, tool_registry
import voice.whatsapp_client as whatsapp_client

class TestWilsonTimeSlotEndToEnd(unittest.TestCase):

    def setUp(self):
        self.conv_code = "TEST_WILSON_SLOTS"

    def test_01_wilson_16_slots_generates_valid_meta_list_payload(self):
        """
        Verify that Dr. Wilson M on Sep 16 (16 slots) generates interactive slot buttons
        and that send_button_message produces a Meta-compliant interactive list payload (<= 10 rows).
        """
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "entities": {
                "doctor_id": 10,
                "department_id": 21,
                "appointment_date": "2026-09-16",
                "appointment_time": None
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
        mock_slots = [
            "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
            "12:00", "12:30", "13:00", "13:30", "14:00", "14:30",
            "15:00", "15:30", "16:00", "16:30"
        ]

        with patch("agent.agent_service.state_manager.save_conversation_state"), \
             patch("agent.agent_service.log_message_to_db"), \
             patch("voice.whatsapp_client.is_mock_mode", return_value=True):

            res = agent_service.build_verified_slot_selection_response(
                self.conv_code, state, 10, mock_doc, "2026-09-16", mock_slots, current_lang="ENGLISH"
            )
            buttons = res.get("interactive_buttons", [])
            self.assertEqual(len(buttons), 16)
            self.assertEqual(buttons[0]["id"], "btn_slot_09:00")
            self.assertEqual(buttons[5]["id"], "btn_slot_11:30")

            # Capture outbound Meta interactive payload
            with patch("voice.whatsapp_client.log_outbound_simulation") as mock_log:
                send_res = whatsapp_client.send_button_message(
                    "919876543210",
                    res["response"],
                    buttons,
                    list_button_title=res.get("list_button_title", "Choose a time ▼")
                )
                self.assertTrue(send_res.get("success"))
                
                # Verify payload structure sent to Meta
                args, kwargs = mock_log.call_args
                payload_type, to_num, payload = args
                self.assertEqual(payload_type, "interactive_list")
                interactive = payload.get("interactive", {})
                self.assertEqual(interactive.get("type"), "list")
                sections = interactive.get("action", {}).get("sections", [])
                self.assertEqual(len(sections), 1)
                rows = sections[0].get("rows", [])
                
                # Crucial assertion: Meta API limit enforced (max 10 rows)
                self.assertLessEqual(len(rows), 10)
                self.assertEqual(rows[0]["id"], "btn_slot_09:00")
                self.assertEqual(rows[0]["title"], "09:00 AM")
                self.assertEqual(rows[5]["id"], "btn_slot_11:30")
                self.assertEqual(rows[5]["title"], "11:30 AM")

    def test_02_clicking_slot_1130_updates_state_and_triggers_preview(self):
        """
        Verify that when the patient clicks [11:30 AM] (ID: btn_slot_11:30),
        the backend updates doctor_id, department_id, appointment_date, appointment_time,
        and transitions to CONFIRMATION_PENDING (Appointment Preview).
        """
        state = {
            "conversation_code": self.conv_code,
            "language": "ENGLISH",
            "patient_id": 1,
            "patient_code": "P001",
            "intent": "BOOK_APPOINTMENT",
            "selected_doctor_id": 10,
            "entities": {
                "doctor_id": 10,
                "department_id": 21,
                "appointment_date": "2026-09-16",
                "appointment_time": None,
                "reason": "Dermatology consultation"
            },
            "interactive_buttons": []
        }
        mock_doc = {"id": 10, "name": "Dr. Wilson M", "department": "Dermatology", "consultation_fee": 900}
        mock_slots = {"success": True, "slots": ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00"]}
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
            
            # Assert state updated accurately
            self.assertEqual(state["entities"]["doctor_id"], 10)
            self.assertEqual(state["entities"]["appointment_date"], "2026-09-16")
            self.assertEqual(state["entities"]["appointment_time"], "11:30")
            self.assertEqual(state["conversation_state"], "CONFIRMATION_PENDING")
            self.assertTrue(state["confirmation_pending"])

            # Assert preview buttons generated (Confirm Appointment, Change Details, Cancel)
            preview_buttons = [b["title"] for b in res.get("interactive_buttons", [])]
            self.assertIn("Confirm Appointment", preview_buttons)

if __name__ == "__main__":
    unittest.main()
