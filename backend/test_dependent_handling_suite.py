"""
test_dependent_handling_suite.py
==================================
Comprehensive Automated Test Suite for Patient/Dependent Handling in WhatsApp AI Patient Desk.

Covers all 24 required scenarios:
1. Self appointment works normally.
2. "My son has fever" with no registered son (Case A - Prompt for details).
3. New son registration (create dependent record).
4. One registered son -> automatically select (Case B).
5. Two registered sons -> ask clarification (Case C).
6. Three registered sons -> ask clarification.
7. One daughter -> automatically select.
8. Multiple daughters -> ask clarification.
9. Multiple children with different genders -> ask clarification for "My child".
10. "Tell me my son's details" with one son -> directly show details.
11. "Tell me my son's details" with multiple sons -> ask Patient ID/name.
12. Patient ID resolves correct dependent.
13. Invalid Patient ID handled gracefully.
14. Unauthorized Patient ID (belonging to another account) is rejected.
15. DOB never becomes appointment date.
16. Appointment reason never becomes doctor name.
17. Topic switching ("Actually, tell me my patient ID") switches to PATIENT_DETAILS.
18. Short reply "Ravi" resolves dependent when in AWAITING_DEPENDENT_SELECTION stage.
19. "My daughter" with one daughter auto-selects.
20. "My child" with multiple children asks clarification.
21. Existing appointment flow remains working.
22. Existing cancellation flow remains working.
23. Existing reschedule flow remains working.
24. Existing WhatsApp webhook endpoint remains working.
"""

import sys
import os
import unittest
import json
import random

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from agent import agent_service, state_manager, patient_identification_service, llm_intent_router


class TestDependentHandlingSuite(unittest.TestCase):

    def setUp(self):
        """Setup test primary patient and clean state before each test."""
        self.test_phone = f"9198{random.randint(10000000, 99999999)}"
        self.conv_code = f"WA_{self.test_phone}_TEST"

        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            # Clean existing test data for this phone
            cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE whatsapp_number = %s);", (self.test_phone,))
            cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone = %s OR whatsapp_number = %s OR guardian_phone = %s);", (self.test_phone, self.test_phone, self.test_phone))
            cur.execute("DELETE FROM conversations WHERE whatsapp_number = %s;", (self.test_phone,))
            cur.execute("DELETE FROM patients WHERE phone = %s OR whatsapp_number = %s OR guardian_phone = %s;", (self.test_phone, self.test_phone, self.test_phone))
            conn.commit()

            # Create Primary Patient
            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, is_dependent, status)
                VALUES (%s, 'Ramesh', 'Kumar', '1985-06-15', 'Male', %s, %s, FALSE, 'ACTIVE')
                RETURNING id;
            """, (f"P{random.randint(50000, 99999)}", self.test_phone, self.test_phone))
            self.primary_patient_id = cur.fetchone()[0]

            # Create Conversation
            cur.execute("""
                INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language, conversation_status)
                VALUES (%s, %s, %s, 'ENGLISH', 'ACTIVE')
                RETURNING id;
            """, (self.conv_code, self.test_phone, self.primary_patient_id))
            self.conv_id = cur.fetchone()[0]

            cur.execute("SELECT d.id, d.department_id FROM doctors d JOIN departments dep ON d.department_id = dep.id WHERE d.status = 'ACTIVE' LIMIT 1;")
            d_row = cur.fetchone()
            if not d_row:
                cur.execute("INSERT INTO departments (department_name, status) VALUES ('Pediatrics', 'ACTIVE') RETURNING id;")
                dept_id = cur.fetchone()[0]
                cur.execute("INSERT INTO doctors (display_name, department_id, status) VALUES ('Dr. Ajay L', %s, 'ACTIVE') RETURNING id;", (dept_id,))
                doc_id = cur.fetchone()[0]
                self.test_doc_id = doc_id
                self.test_dept_id = dept_id
            else:
                self.test_doc_id = d_row[0]
                self.test_dept_id = d_row[1]
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def _create_dependent(self, first_name, last_name, dob, gender, rel):
        """Helper to seed a dependent under the test primary patient."""
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            p_code = f"P{random.randint(10000, 49999)}"
            cur.execute("""
                INSERT INTO patients (
                    patient_code, first_name, last_name, date_of_birth, gender,
                    phone, whatsapp_number, guardian_patient_id, guardian_phone,
                    relationship_to_contact, is_dependent, status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, 'ACTIVE')
                RETURNING id;
            """, (p_code, first_name, last_name, dob, gender, self.test_phone, self.test_phone, self.primary_patient_id, self.test_phone, rel))
            dep_id = cur.fetchone()[0]
            conn.commit()
            return {"id": dep_id, "patient_code": p_code, "full_name": f"{first_name} {last_name}".strip()}
        finally:
            cur.close()
            conn.close()

    # 1. Self appointment works normally
    def test_01_self_appointment(self):
        res = agent_service.process_agent_message(self.conv_code, f"P{self.primary_patient_id}", "I have fever, want to book appointment")
        self.assertIn("General Medicine", res["response"])
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("patient_id"), self.primary_patient_id)

    # 2. "My son has fever" with no registered son (Case A)
    def test_02_son_fever_no_registered_son(self):
        res = agent_service.process_agent_message(self.conv_code, None, "My son has fever. I want to book an appointment.")
        self.assertIn("Full name", res["response"])
        self.assertIn("Date of birth", res["response"])
        self.assertIn("Gender", res["response"])
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("pending_stage"), "REGISTERING_NEW_DEPENDENT")

    # 3. New son registration during booking flow
    def test_03_new_son_registration(self):
        # Step 1: Initiate
        agent_service.process_agent_message(self.conv_code, None, "My son has fever. I want to book an appointment.")
        # Step 2: Provide details
        res = agent_service.process_agent_message(self.conv_code, None, "Ravi Kumar, 12 May 2015, Male")
        self.assertTrue("Ravi Kumar" in res["response"] or "General Medicine" in res["response"] or "doctor" in res["response"])
        deps = patient_identification_service.get_dependents_for_parent(self.primary_patient_id, self.test_phone)
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0]["first_name"], "Ravi")

    # 4. One registered son -> automatically select (Case B)
    def test_04_one_registered_son_autoselect(self):
        dep = self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        res = agent_service.process_agent_message(self.conv_code, None, "My son has fever. I want to book an appointment.")
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("patient_id"), dep["id"])
        self.assertTrue(state.get("dependent_collected"))

    # 5. Two registered sons -> ask clarification (Case C)
    def test_05_two_registered_sons_ask_clarification(self):
        dep1 = self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        dep2 = self._create_dependent("Arjun", "Kumar", "2017-08-20", "Male", "SON")
        res = agent_service.process_agent_message(self.conv_code, None, "My son has fever. I want to book an appointment.")
        self.assertIn("more than one son", res["response"].lower())
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("pending_stage"), "AWAITING_DEPENDENT_SELECTION")

    # 6. Three registered sons -> ask clarification
    def test_06_three_registered_sons(self):
        self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        self._create_dependent("Arjun", "Kumar", "2017-08-20", "Male", "SON")
        self._create_dependent("Karan", "Kumar", "2019-01-10", "Male", "SON")
        res = agent_service.process_agent_message(self.conv_code, None, "My son has fever.")
        self.assertIn("more than one son", res["response"].lower())

    # 7. One daughter -> automatically select
    def test_07_one_daughter_autoselect(self):
        dep = self._create_dependent("Priya", "Kumar", "2018-03-14", "Female", "DAUGHTER")
        res = agent_service.process_agent_message(self.conv_code, None, "My daughter has cough.")
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("patient_id"), dep["id"])

    # 8. Multiple daughters -> ask clarification
    def test_08_multiple_daughters_clarification(self):
        self._create_dependent("Priya", "Kumar", "2018-03-14", "Female", "DAUGHTER")
        self._create_dependent("Ananya", "Kumar", "2020-07-22", "Female", "DAUGHTER")
        res = agent_service.process_agent_message(self.conv_code, None, "My daughter has cough.")
        self.assertIn("more than one daughter", res["response"].lower())

    # 9. Multiple children with different genders -> ask clarification for "My child"
    def test_09_multiple_children_different_genders(self):
        self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        self._create_dependent("Priya", "Kumar", "2018-03-14", "Female", "DAUGHTER")
        res = agent_service.process_agent_message(self.conv_code, None, "My child has fever.")
        self.assertIn("more than one child", res["response"].lower())

    # 10. "Tell me my son's details" with one son -> directly show details
    def test_10_son_details_one_son(self):
        dep = self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        res = agent_service.process_agent_message(self.conv_code, None, "Tell me my son's details.")
        self.assertIn("Ravi Kumar", res["response"])
        self.assertIn(dep["patient_code"], res["response"])

    # 11. "Tell me my son's details" with multiple sons -> ask Patient ID/name
    def test_11_son_details_multiple_sons(self):
        self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        self._create_dependent("Arjun", "Kumar", "2017-08-20", "Male", "SON")
        res = agent_service.process_agent_message(self.conv_code, None, "Tell me my son's details.")
        self.assertIn("more than one son", res["response"].lower())

    # 12. Patient ID resolves correct dependent
    def test_12_patient_id_resolves_dependent(self):
        dep1 = self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        dep2 = self._create_dependent("Arjun", "Kumar", "2017-08-20", "Male", "SON")
        # Initiate
        agent_service.process_agent_message(self.conv_code, None, "My son has fever.")
        # Provide patient code
        res = agent_service.process_agent_message(self.conv_code, None, dep1["patient_code"])
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("patient_id"), dep1["id"])

    # 13. Invalid Patient ID handled gracefully
    def test_13_invalid_patient_id(self):
        self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        self._create_dependent("Arjun", "Kumar", "2017-08-20", "Male", "SON")
        agent_service.process_agent_message(self.conv_code, None, "My son has fever.")
        res = agent_service.process_agent_message(self.conv_code, None, "P999999")
        self.assertIn("couldn't find", res["response"].lower())

    # 14. Unauthorized Patient ID (belonging to another account) is rejected
    def test_14_unauthorized_patient_id_rejected(self):
        # Create unrelated patient
        unrelated_code = f"P{random.randint(80000, 89999)}"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM patients WHERE patient_code = %s;", (unrelated_code,))
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
            VALUES (%s, 'Unrelated', 'User', '1990-01-01', 'Female', '919999988888', '919999988888', 'ACTIVE')
            RETURNING id;
        """, (unrelated_code,))
        other_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        res = agent_service.process_agent_message(self.conv_code, None, f"Show details for {unrelated_code}")
        self.assertIn("couldn't find that patient id under your registered whatsapp number", res["response"].lower())

    # 15. DOB never becomes appointment date
    def test_15_dob_never_becomes_appointment_date(self):
        res = agent_service.process_agent_message(self.conv_code, None, "My son Ravi Kumar, born 12 May 2015, Male. He has fever.")
        state = state_manager.get_conversation_state(self.conv_code)
        appt_d = state.get("entities", {}).get("appointment_date")
        self.assertNotEqual(appt_d, "2015-05-12")

    # 16. Appointment reason never becomes doctor name
    def test_16_reason_never_becomes_doctor_name(self):
        res = agent_service.process_agent_message(self.conv_code, None, "I want to book an appointment for fever")
        state = state_manager.get_conversation_state(self.conv_code)
        doc_n = state.get("doctor_name")
        self.assertNotEqual(doc_n, "fever")

    # 17. Topic switching ("Actually, tell me my patient ID")
    def test_17_topic_switching(self):
        self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        self._create_dependent("Arjun", "Kumar", "2017-08-20", "Male", "SON")
        # Step 1: Booking
        agent_service.process_agent_message(self.conv_code, None, "My son has fever.")
        # Step 2: Topic switch
        res = agent_service.process_agent_message(self.conv_code, None, "Actually, tell me my patient ID.")
        self.assertTrue("patient id" in res["response"].lower() or "details" in res["response"].lower())
        self.assertEqual(res["intent"], "PATIENT_DETAILS")

    # 18. Short reply "Ravi" resolves dependent when in AWAITING_DEPENDENT_SELECTION stage
    def test_18_short_reply_name_resolves(self):
        dep1 = self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        dep2 = self._create_dependent("Arjun", "Kumar", "2017-08-20", "Male", "SON")
        agent_service.process_agent_message(self.conv_code, None, "My son has fever.")
        res = agent_service.process_agent_message(self.conv_code, None, "Ravi")
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("patient_id"), dep1["id"])

    # 19. "My daughter" with one daughter auto-selects
    def test_19_my_daughter_one_daughter_autoselect(self):
        dep = self._create_dependent("Priya", "Kumar", "2018-03-14", "Female", "DAUGHTER")
        res = agent_service.process_agent_message(self.conv_code, None, "My daughter has stomach pain.")
        state = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state.get("patient_id"), dep["id"])

    # 20. "My child" with multiple children asks clarification
    def test_20_my_child_multiple_children(self):
        self._create_dependent("Ravi", "Kumar", "2015-05-12", "Male", "SON")
        self._create_dependent("Priya", "Kumar", "2018-03-14", "Female", "DAUGHTER")
        res = agent_service.process_agent_message(self.conv_code, None, "My child has a cough.")
        self.assertIn("more than one child", res["response"].lower())

    # 21. Existing appointment flow remains working
    def test_21_existing_appointment_flow(self):
        res1 = agent_service.process_agent_message(self.conv_code, None, "I want to book an appointment for fever")
        self.assertIn("General Medicine", res1["response"])

    # 22. Existing cancellation flow remains working
    def test_22_cancellation_flow(self):
        res = agent_service.process_agent_message(self.conv_code, None, "I want to cancel my appointment")
        self.assertTrue("booking id" in res["response"].lower() or "cancel" in res["response"].lower())

    # 23. Existing reschedule flow remains working
    def test_23_reschedule_flow(self):
        res = agent_service.process_agent_message(self.conv_code, None, "I want to reschedule my appointment")
        self.assertTrue("reschedule" in res["response"].lower() or "booking id" in res["response"].lower() or "date" in res["response"].lower())

    # 24. Existing WhatsApp webhook integration point function
    def test_24_whatsapp_webhook_service_call(self):
        res = agent_service.process_agent_message(self.conv_code, None, "Hello")
        self.assertIn("response", res)
        self.assertIn("intent", res)

    # 25. Completed appointment + "ok" → GREETING / ACKNOWLEDGEMENT (No Pediatrics/Doctor leak)
    def test_25_completed_appointment_ok_resets_workflow(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "POST_BOOKING"
        state["previous_question"] = "post_booking_help"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "ok")
        self.assertEqual(res["intent"], "GREETING")
        self.assertIn("welcome", res["response"].lower())
        self.assertNotIn("pediatrics", res["response"].lower())
        self.assertNotIn("dr.", res["response"].lower())

    # 26. Completed appointment + "okay" → GREETING / ACKNOWLEDGEMENT
    def test_26_completed_appointment_okay_resets_workflow(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "POST_BOOKING"
        state["previous_question"] = "post_booking_help"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "okay")
        self.assertEqual(res["intent"], "GREETING")
        self.assertIn("welcome", res["response"].lower())

    # 27. Completed appointment + "thanks" → ACKNOWLEDGEMENT
    def test_27_completed_appointment_thanks(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "POST_BOOKING"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "thanks")
        self.assertEqual(res["intent"], "GREETING")
        self.assertIn("welcome", res["response"].lower())

    # 28. Completed appointment + "hi" → GREETING
    def test_28_completed_appointment_hi_greeting(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "POST_BOOKING"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "hi")
        self.assertEqual(res["intent"], "GREETING")

    # 29. Completed appointment + "hello" → GREETING
    def test_29_completed_appointment_hello_greeting(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "POST_BOOKING"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "hello")
        self.assertEqual(res["intent"], "GREETING")

    # 30. Completed appointment + "I want another appointment" → BOOK_APPOINTMENT
    def test_30_completed_appointment_new_booking(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "POST_BOOKING"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "I want another appointment for fever")
        self.assertEqual(res["intent"], "BOOK_APPOINTMENT")

    # 31. Completed appointment + "What's my patient ID?" → PATIENT_DETAILS
    def test_31_completed_appointment_patient_id_request(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "POST_BOOKING"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "What's my patient ID?")
        self.assertEqual(res["intent"], "PATIENT_DETAILS")

    # 32. Confirmation question + "yes" -> CONFIRM_APPOINTMENT
    def test_32_confirmation_question_yes(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "BOOK_APPOINTMENT"
        state["booking_stage"] = "AWAITING_CONFIRMATION"
        state["confirmation_pending"] = True
        state["patient_id"] = self.primary_patient_id
        state["entities"]["patient_id"] = self.primary_patient_id
        state["entities"]["doctor_id"] = self.test_doc_id
        state["entities"]["department_id"] = self.test_dept_id
        state["entities"]["appointment_date"] = "2026-09-15"
        state["entities"]["appointment_time"] = "14:30"
        state["entities"]["reason"] = "fever"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "yes")
        self.assertIn("confirmed", res["response"].lower())

    # 33. Hospital information button/request
    def test_33_hospital_info_button(self):
        res = agent_service.process_agent_message(self.conv_code, None, "btn_hosp_info")
        self.assertEqual(res["intent"], "HOSPITAL_INFORMATION")

    # 34. Appointment reason persisted in DB is fever (not doctor name)
    def test_34_appointment_reason_persisted_in_db(self):
        dep = self._create_dependent("Johnny", "Kumar", "2010-12-20", "Male", "SON")
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "BOOK_APPOINTMENT"
        state["booking_stage"] = "AWAITING_CONFIRMATION"
        state["confirmation_pending"] = True
        state["patient_id"] = dep["id"]
        state["dependent_patient_id"] = dep["id"]
        state["entities"]["patient_id"] = dep["id"]
        state["entities"]["doctor_id"] = self.test_doc_id
        state["entities"]["department_id"] = self.test_dept_id
        state["entities"]["appointment_date"] = "2026-09-15"
        state["entities"]["appointment_time"] = "14:30"
        state["entities"]["reason"] = "fever"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "confirm")
        self.assertIn("confirmed", res["response"].lower())

        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT patient_reason, patient_id FROM appointments WHERE conversation_id = %s ORDER BY id DESC LIMIT 1;", (self.conv_id,))
            row = cur.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row[0], "fever")
            self.assertEqual(row[1], dep["id"])
        finally:
            cur.close()
            conn.close()

    # 35. Selecting doctor does not change reason
    def test_35_selecting_doctor_does_not_change_reason(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "BOOK_APPOINTMENT"
        state["booking_stage"] = "AWAITING_DOCTOR"
        state["patient_id"] = self.primary_patient_id
        state["entities"]["patient_id"] = self.primary_patient_id
        state["entities"]["reason"] = "fever"
        state_manager.save_conversation_state(self.conv_code, state)

        agent_service.process_agent_message(self.conv_code, None, "Dr. Arun Kumar")
        state_after = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state_after["entities"]["reason"], "fever")

    # 36. Selecting department does not change reason
    def test_36_selecting_department_does_not_change_reason(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "BOOK_APPOINTMENT"
        state["booking_stage"] = "AWAITING_DEPARTMENT_CONFIRM"
        state["patient_id"] = self.primary_patient_id
        state["entities"]["patient_id"] = self.primary_patient_id
        state["entities"]["reason"] = "fever"
        state_manager.save_conversation_state(self.conv_code, state)

        agent_service.process_agent_message(self.conv_code, None, "Pediatrics")
        state_after = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state_after["entities"]["reason"], "fever")

    # 37. Selecting date/time does not change reason
    def test_37_selecting_date_time_does_not_change_reason(self):
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "BOOK_APPOINTMENT"
        state["booking_stage"] = "AWAITING_DATE"
        state["patient_id"] = self.primary_patient_id
        state["entities"]["patient_id"] = self.primary_patient_id
        state["entities"]["doctor_id"] = self.test_doc_id
        state["entities"]["department_id"] = self.test_dept_id
        state["entities"]["reason"] = "fever"
        state_manager.save_conversation_state(self.conv_code, state)

        agent_service.process_agent_message(self.conv_code, None, "15/09/2026 10:00 AM")
        state_after = state_manager.get_conversation_state(self.conv_code)
        self.assertEqual(state_after["entities"]["reason"], "fever")

    # 38. Dependent appointment created against dependent ID in DB
    def test_38_dependent_appointment_created_against_dependent_id(self):
        dep = self._create_dependent("Johnny", "Kumar", "2010-12-20", "Male", "SON")
        state = state_manager.get_conversation_state(self.conv_code)
        state["intent"] = "BOOK_APPOINTMENT"
        state["booking_stage"] = "AWAITING_CONFIRMATION"
        state["confirmation_pending"] = True
        state["patient_id"] = dep["id"]
        state["dependent_patient_id"] = dep["id"]
        state["entities"]["patient_id"] = dep["id"]
        state["entities"]["doctor_id"] = self.test_doc_id
        state["entities"]["department_id"] = self.test_dept_id
        state["entities"]["appointment_date"] = "2026-09-16"
        state["entities"]["appointment_time"] = "14:30"
        state["entities"]["reason"] = "fever"
        state_manager.save_conversation_state(self.conv_code, state)

        res = agent_service.process_agent_message(self.conv_code, None, "yes")
        self.assertIn("confirmed", res["response"].lower())

        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT patient_id FROM appointments WHERE conversation_id = %s ORDER BY id DESC LIMIT 1;", (self.conv_id,))
            row = cur.fetchone()
            self.assertEqual(row[0], dep["id"])
        finally:
            cur.close()
            conn.close()

    # 39. No duplicate dependent records created
    def test_39_no_duplicate_dependent_records(self):
        dep = self._create_dependent("Johnny", "Kumar", "2010-12-20", "Male", "SON")
        deps_before = patient_identification_service.get_dependents_for_parent(self.primary_patient_id, self.test_phone)
        self.assertEqual(len(deps_before), 1)

        # Trigger Case B auto-selection
        agent_service.process_agent_message(self.conv_code, None, "My son has fever.")
        deps_after = patient_identification_service.get_dependents_for_parent(self.primary_patient_id, self.test_phone)
        self.assertEqual(len(deps_after), 1)

    # 40. Full end-to-end dependent booking flow
    def test_40_full_end_to_end_dependent_booking_flow(self):
        # Step 1: Initiate for son (Case A - No son)
        res1 = agent_service.process_agent_message(self.conv_code, None, "My son has fever. I want to book an appointment.")
        self.assertIn("Full name", res1["response"])

        # Step 2: Register son
        res2 = agent_service.process_agent_message(self.conv_code, None, "Johnny Kumar, 20 Dec 2010, Male")
        self.assertTrue("Johnny" in res2["response"] or "doctor" in res2["response"] or "Pediatrics" in res2["response"] or "General Medicine" in res2["response"])

        # Check DB dependent creation
        deps = patient_identification_service.get_dependents_for_parent(self.primary_patient_id, self.test_phone)
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0]["first_name"], "Johnny")


if __name__ == "__main__":
    unittest.main()
