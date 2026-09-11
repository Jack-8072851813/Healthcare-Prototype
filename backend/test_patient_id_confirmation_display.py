"""
Unit/Integration Tests for Patient ID Display in Confirmation Messages
Verifies that Patient ID (patient_code) is displayed in both confirmation preview and success messages.
"""
import json
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import agent_service, state_manager


class TestPatientIDDisplay(unittest.TestCase):

    def test_preview_message_includes_patient_id(self):
        conv_code = "CONV_TEST_PAT_ID"
        state = {
            "conversation_code": conv_code,
            "conversation_state": "TIME_SELECTION",
            "entities": {
                "doctor_id": 10,
                "department_id": 2,
                "appointment_date": "2026-09-15",
                "appointment_time": None,
                "reason": "Nose pain"
            },
            "patient_id": 1,
            "patient_code": "P100002",
            "language": "ENGLISH",
            "intent": "BOOK_APPOINTMENT"
        }

        last_query = [""]

        def mock_execute(query, params=None):
            last_query[0] = query

        def mock_fetchone():
            q = last_query[0].lower()
            if "from conversations" in q:
                return (1, 1, "919999999999", "ENGLISH", "BOOK_APPOINTMENT")
            elif "from messages" in q:
                return (json.dumps(state),)
            elif "from doctors" in q:
                return (2,)
            elif "from patients" in q:
                if "id = %s and status" in q or "id = $1 and status" in q:
                    return (1,)
                return ("Gil", "Christ", "2004-08-15", "Male", "P100002")
            return None

        with patch("agent.agent_service.tool_registry.tool_get_available_slots") as mock_slots, \
             patch("agent.agent_service.resolve_doctor_details") as mock_doc, \
             patch("db_config.get_db_connection") as mock_conn:

            mock_slots.return_value = {"success": True, "slots": ["10:00"]}
            mock_doc.return_value = {"id": 10, "name": "Dr. James R", "department": "ENT"}

            mock_cur = MagicMock()
            mock_cur.execute.side_effect = mock_execute
            mock_cur.fetchone.side_effect = mock_fetchone
            mock_conn.return_value.cursor.return_value = mock_cur

            resp = agent_service.process_agent_message(conv_code, None, "btn_slot_10:00")

            resp_text = resp["response"]
            self.assertIn("Patient: Gil Christ", resp_text)
            self.assertIn("Patient ID: P100002", resp_text)
            self.assertIn("Doctor: Dr. James R", resp_text)

    def test_dependent_preview_message_includes_dependent_patient_id(self):
        conv_code = "CONV_TEST_DEP_PAT_ID"
        state = {
            "conversation_code": conv_code,
            "conversation_state": "TIME_SELECTION",
            "entities": {
                "doctor_id": 10,
                "department_id": 2,
                "appointment_date": "2026-09-15",
                "appointment_time": None,
                "reason": "Fever"
            },
            "patient_id": 1,
            "patient_code": "P100001",
            "dependent_patient_id": 5,
            "dependent_patient_code": "P100005",
            "appointment_for": "CHILD",
            "language": "ENGLISH",
            "intent": "BOOK_APPOINTMENT"
        }

        last_query = [""]

        def mock_execute(query, params=None):
            last_query[0] = query

        def mock_fetchone():
            q = last_query[0].lower()
            if "from conversations" in q:
                return (1, 1, "919999999999", "ENGLISH", "BOOK_APPOINTMENT")
            elif "from messages" in q:
                return (json.dumps(state),)
            elif "from doctors" in q:
                return (2,)
            elif "from patients" in q:
                if "id = %s and status" in q or "id = $1 and status" in q:
                    return (5,)
                return ("Junior", "Christ", "2018-05-10", "Male", "P100005")
            return None

        with patch("agent.agent_service.tool_registry.tool_get_available_slots") as mock_slots, \
             patch("agent.agent_service.resolve_doctor_details") as mock_doc, \
             patch("db_config.get_db_connection") as mock_conn:

            mock_slots.return_value = {"success": True, "slots": ["10:00"]}
            mock_doc.return_value = {"id": 10, "name": "Dr. James R", "department": "ENT"}

            mock_cur = MagicMock()
            mock_cur.execute.side_effect = mock_execute
            mock_cur.fetchone.side_effect = mock_fetchone
            mock_conn.return_value.cursor.return_value = mock_cur

            resp = agent_service.process_agent_message(conv_code, None, "btn_slot_10:00")

            resp_text = resp["response"]
            self.assertIn("Patient: Junior Christ", resp_text)
            self.assertIn("Patient ID: P100005", resp_text)


if __name__ == "__main__":
    unittest.main()


