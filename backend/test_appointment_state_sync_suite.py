import sys
import os
import unittest
import uuid

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from agent import agent_service, state_manager
import db_config

class TestAppointmentStateSyncSuite(unittest.TestCase):
    def setUp(self):
        self.code = f"SYNC_TEST_{uuid.uuid4().hex[:8]}"

    def test_01_existing_patient_flow_intact(self):
        res = agent_service.process_agent_message(self.code, "P001", "Hi")
        self.assertIn(res["intent"], ["GREETING", "IDENTIFY_PATIENT", "PATIENT_DETAILS", "BOOK_APPOINTMENT"])
        self.assertIsNotNone(res.get("response"))

    def test_02_tamil_clinical_request_routing_and_language(self):
        # Tamil clinical request for skin/dermatology complaint
        res = agent_service.process_agent_message(self.code, "P001", "எனக்கு தோலில் அரிப்பு மற்றும் சொறி உள்ளது")
        self.assertEqual(res["language"], "TAMIL")
        state = state_manager.get_conversation_state(self.code)
        # Should set language to TAMIL and identify medical complaint
        self.assertEqual(state.get("language"), "TAMIL")
        self.assertIn("response", res)

    def test_03_doctor_selection_returns_valid_schedule_dates(self):
        res = agent_service.process_agent_message(self.code, "P001", "Show available doctors")
        state = state_manager.get_conversation_state(self.code)
        doc_id = state.get("selected_doctor_id") or 5
        dates = agent_service.get_verified_doctor_available_dates(self.code, int(doc_id))
        self.assertIsInstance(dates, list)

    def test_04_date_selection_queries_doctor_id_and_date(self):
        res1 = agent_service.process_agent_message(self.code, "P001", "I want to see Dr. Arun Kumar")
        state = state_manager.get_conversation_state(self.code)
        doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id") or 5
        dates = agent_service.get_verified_doctor_available_dates(self.code, int(doc_id))
        if dates:
            target_date = dates[0]["date"]
            res2 = agent_service.process_agent_message(self.code, "P001", f"btn_date_{target_date}")
            state2 = state_manager.get_conversation_state(self.code)
            self.assertEqual(state2["entities"]["appointment_date"], target_date)

    def test_05_available_date_has_at_least_one_slot(self):
        dates = agent_service.get_verified_doctor_available_dates(self.code, 5)
        for d in dates:
            self.assertGreater(d["count"], 0)
            self.assertGreater(len(d["slots"]), 0)

    def test_06_available_time_slots_real(self):
        res = agent_service.tool_registry.tool_get_available_slots(self.code, 5, "2026-09-14")
        self.assertTrue(res["success"])
        slots = res.get("slots", [])
        self.assertIsInstance(slots, list)

    def test_07_click_time_sets_slot_id_and_preserves_date(self):
        dates = agent_service.get_verified_doctor_available_dates(self.code, 5)
        if dates:
            target_date = dates[0]["date"]
            target_slot = dates[0]["slots"][0]
            # Setup state with date
            state = state_manager.get_conversation_state(self.code)
            state["department_name"] = "General Medicine"
            state["selected_department_name"] = "General Medicine"
            state["selected_doctor_id"] = 5
            state["selected_doctor_name"] = "Dr. Arun Kumar"
            state["entities"]["doctor_id"] = 5
            state["entities"]["appointment_date"] = target_date
            state_manager.save_conversation_state(self.code, state)
            agent_service.log_message_to_db(self.code, "USER", "Setup state", "ENGLISH", "BOOK_APPOINTMENT", state)

            res = agent_service.process_agent_message(self.code, "P001", f"btn_slot_{target_slot}")
            state_after = state_manager.get_conversation_state(self.code)
            self.assertEqual(state_after["entities"]["appointment_date"], target_date)
            self.assertEqual(state_after["entities"]["appointment_time"], target_slot)

    def test_08_preview_matches_workflow_canonical_state(self):
        state = state_manager.get_conversation_state(self.code)
        state["department_name"] = "General Medicine"
        state["selected_department_name"] = "General Medicine"
        state["selected_doctor_id"] = 5
        state["selected_doctor_name"] = "Dr. Arun Kumar"
        state["entities"]["doctor_id"] = 5
        state["entities"]["appointment_date"] = "2026-09-14"
        state["entities"]["appointment_time"] = "11:30"
        state_manager.save_conversation_state(self.code, state)
        agent_service.log_message_to_db(self.code, "USER", "Setup state", "ENGLISH", "BOOK_APPOINTMENT", state)

        res = agent_service.process_agent_message(self.code, "P001", "btn_slot_11:30")
        state_after = state_manager.get_conversation_state(self.code)
        self.assertEqual(state_after["entities"]["appointment_date"], "2026-09-14")
        self.assertEqual(state_after["entities"]["appointment_time"], "11:30")

    def test_09_confirm_appointment_preserves_date_without_missing_date_error(self):
        state = state_manager.get_conversation_state(self.code)
        state["patient_id"] = 1
        state["department_name"] = "General Medicine"
        state["selected_department_name"] = "General Medicine"
        state["selected_doctor_id"] = 5
        state["selected_doctor_name"] = "Dr. Arun Kumar"
        state["entities"]["doctor_id"] = 5
        state["entities"]["department_id"] = 17
        state["entities"]["appointment_date"] = "2026-09-14"
        state["entities"]["appointment_time"] = "11:30"
        state["confirmation_pending"] = True
        state["conversation_state"] = "CONFIRMATION_PENDING"
        state_manager.save_conversation_state(self.code, state)
        agent_service.log_message_to_db(self.code, "USER", "Setup state", "ENGLISH", "BOOK_APPOINTMENT", state)

        res = agent_service.process_agent_message(self.code, "P001", "Confirm Appointment")
        self.assertNotIn("Appointment date is required", res["response"])
        state_after = state_manager.get_conversation_state(self.code)
        # Must require payment before confirming
        self.assertIn(state_after.get("conversation_state"), ["PAYMENT_METHOD_REQUIRED", "MOCK_PAYMENT_PROMPT", "AWAITING_PAYMENT"])

    def test_10_payment_required_before_final_confirmation(self):
        state = state_manager.get_conversation_state(self.code)
        state["patient_id"] = 1
        state["department_name"] = "General Medicine"
        state["selected_department_name"] = "General Medicine"
        state["selected_doctor_id"] = 5
        state["selected_doctor_name"] = "Dr. Arun Kumar"
        state["entities"]["doctor_id"] = 5
        state["entities"]["department_id"] = 17
        state["entities"]["appointment_date"] = "2026-09-14"
        state["entities"]["appointment_time"] = "11:30"
        state["confirmation_pending"] = True
        state["conversation_state"] = "CONFIRMATION_PENDING"
        state_manager.save_conversation_state(self.code, state)
        agent_service.log_message_to_db(self.code, "USER", "Setup state", "ENGLISH", "BOOK_APPOINTMENT", state)

        res = agent_service.process_agent_message(self.code, "P001", "btn_confirm_appt")
        self.assertNotIn("successfully booked", res["response"].lower())
        self.assertIn("payment", res["response"].lower())

    def test_11_date_change_clears_time_and_slot(self):
        state = state_manager.get_conversation_state(self.code)
        state["department_name"] = "General Medicine"
        state["selected_department_name"] = "General Medicine"
        state["selected_doctor_id"] = 5
        state["selected_doctor_name"] = "Dr. Arun Kumar"
        state["entities"]["doctor_id"] = 5
        state["entities"]["appointment_date"] = "2026-09-14"
        state["entities"]["appointment_time"] = "11:30"
        state["selected_slot_id"] = "slot_5_2026-09-14_11:30"
        state_manager.save_conversation_state(self.code, state)
        agent_service.log_message_to_db(self.code, "USER", "Setup state", "ENGLISH", "BOOK_APPOINTMENT", state)

        res = agent_service.process_agent_message(self.code, "P001", "btn_date_2026-09-15")
        state_after = state_manager.get_conversation_state(self.code)
        self.assertEqual(state_after["entities"]["appointment_date"], "2026-09-15")
        self.assertIsNone(state_after["entities"]["appointment_time"])

    def test_12_doctor_change_clears_date_time_slot(self):
        state = state_manager.get_conversation_state(self.code)
        state["selected_doctor_id"] = 1
        state["entities"]["doctor_id"] = 1
        state["entities"]["appointment_date"] = "2026-09-14"
        state["entities"]["appointment_time"] = "11:30"
        state["selected_slot_id"] = "slot_1_2026-09-14_11:30"
        state_manager.save_conversation_state(self.code, state)

        res = agent_service.process_agent_message(self.code, "P001", "Change doctor")
        state_after = state_manager.get_conversation_state(self.code)
        self.assertIsNone(state_after.get("selected_doctor_id"))
        self.assertIsNone(state_after["entities"].get("doctor_id"))
        self.assertIsNone(state_after["entities"].get("appointment_date"))
        self.assertIsNone(state_after["entities"].get("appointment_time"))

    def test_13_reschedule_flow_intact(self):
        state = state_manager.get_conversation_state(self.code)
        state["intent"] = "RESCHEDULE_APPOINTMENT"
        state_manager.save_conversation_state(self.code, state)
        res = agent_service.process_agent_message(self.code, "P001", "Reschedule my appointment")
        self.assertIn(res["intent"], ["RESCHEDULE_APPOINTMENT", "APPOINTMENT_STATUS"])

    def test_14_multilingual_tamil_workflow(self):
        res = agent_service.process_agent_message(self.code, "P001", "வணக்கம்")
        self.assertEqual(res["language"], "TAMIL")
        state = state_manager.get_conversation_state(self.code)
        self.assertEqual(state.get("language"), "TAMIL")

    def test_15_language_switch_natural(self):
        res1 = agent_service.process_agent_message(self.code, "P001", "எனக்கு appointment வேண்டும்")
        self.assertEqual(res1["language"], "TAMIL")
        res2 = agent_service.process_agent_message(self.code, "P001", "Show available doctors")
        self.assertEqual(res2["language"], "ENGLISH")

    def test_16_short_context_message_preserves_language(self):
        res1 = agent_service.process_agent_message(self.code, "P001", "வணக்கம்")
        self.assertEqual(res1["language"], "TAMIL")
        res2 = agent_service.process_agent_message(self.code, "P001", "11:30")
        self.assertEqual(res2["language"], "TAMIL")

if __name__ == "__main__":
    unittest.main()
