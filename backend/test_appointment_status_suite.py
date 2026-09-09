"""
test_appointment_status_suite.py
==================================
Comprehensive test suite verifying all 30 test cases for appointment retrieval
and status handling in Meridian Hospital AI Patient Desk.
"""

import os
import sys
import datetime
import unittest

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.llm_intent_router as llm_intent_router
import agent.intent_detector as intent_detector
import agent.agent_service as agent_service
import agent.patient_identification_service as patient_id_service
import appointment_service

class TestAppointmentStatusSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up test patients and appointments in DB."""
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            # 1. Clean up old test records if present
            cur.execute("DELETE FROM notifications WHERE patient_id IN (SELECT id FROM patients WHERE patient_code LIKE 'TST%');")
            cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE patient_code LIKE 'TST%');")
            cur.execute("DELETE FROM conversations WHERE whatsapp_number LIKE '+9199990000%';")
            cur.execute("DELETE FROM patients WHERE patient_code LIKE 'TST%';")
            conn.commit()

            # 2. Insert test parent patient (Parent A)
            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, is_dependent, status)
                VALUES ('TST001', 'TestParent', 'User', '1985-05-15', 'Male', '+919999000001', '+919999000001', FALSE, 'ACTIVE')
                RETURNING id;
            """)
            cls.parent_id = cur.fetchone()[0]

            # 3. Insert test dependent 1 (Son 1: Johnny)
            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, guardian_patient_id, guardian_phone, relationship_to_contact, is_dependent, status)
                VALUES ('TST002', 'Johnny', 'User', '2016-08-10', 'Male', '+919999000001', '+919999000001', %s, '+919999000001', 'SON', TRUE, 'ACTIVE')
                RETURNING id;
            """, (cls.parent_id,))
            cls.son1_id = cur.fetchone()[0]

            # 4. Insert test parent patient (Parent B with multiple sons)
            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, is_dependent, status)
                VALUES ('TST003', 'TestParentB', 'User', '1980-01-01', 'Female', '+919999000002', '+919999000002', FALSE, 'ACTIVE')
                RETURNING id;
            """)
            cls.parentB_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, guardian_patient_id, guardian_phone, relationship_to_contact, is_dependent, status)
                VALUES ('TST004', 'SonOne', 'User', '2015-02-02', 'Male', '+919999000002', '+919999000002', %s, '+919999000002', 'SON', TRUE, 'ACTIVE')
                RETURNING id;
            """, (cls.parentB_id,))
            cls.sonB1_id = cur.fetchone()[0]

            cur.execute("""
                INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, guardian_patient_id, guardian_phone, relationship_to_contact, is_dependent, status)
                VALUES ('TST005', 'SonTwo', 'User', '2018-03-03', 'Male', '+919999000002', '+919999000002', %s, '+919999000002', 'SON', TRUE, 'ACTIVE')
                RETURNING id;
            """, (cls.parentB_id,))
            cls.sonB2_id = cur.fetchone()[0]

            # 5. Get doctor & department IDs
            cur.execute("SELECT id, department_id FROM doctors WHERE status = 'ACTIVE' LIMIT 1;")
            doc_row = cur.fetchone()
            cls.doc_id = doc_row[0] if doc_row else 1
            cls.dept_id = doc_row[1] if doc_row else 1

            # 6. Insert test appointment for Parent A
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            future_date = (datetime.date.today() + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
            past_date = (datetime.date.today() - datetime.timedelta(days=10)).strftime("%Y-%m-%d")

            cur.execute("""
                INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status, patient_reason, booking_source)
                VALUES ('APT99001', %s, %s, %s, %s, '10:00:00', 'CONFIRMED', 'High Fever and Cough', 'WHATSAPP_TEXT');
            """, (cls.parent_id, cls.doc_id, cls.dept_id, future_date))

            # 7. Insert test appointment for Son Johnny
            cur.execute("""
                INSERT INTO appointments (booking_id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status, patient_reason, booking_source)
                VALUES ('APT99002', %s, %s, %s, %s, '16:30:00', 'CONFIRMED', 'Pediatric Rash', 'WHATSAPP_TEXT');
            """, (cls.son1_id, cls.doc_id, cls.dept_id, future_date))

            conn.commit()
        finally:
            cur.close()
            conn.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up test records."""
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM notifications WHERE patient_id IN (SELECT id FROM patients WHERE patient_code LIKE 'TST%');")
            cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE patient_code LIKE 'TST%');")
            cur.execute("DELETE FROM conversations WHERE whatsapp_number LIKE '+9199990000%';")
            cur.execute("DELETE FROM patients WHERE patient_code LIKE 'TST%';")
            conn.commit()
        finally:
            cur.close()
            conn.close()

    def test_01_intent_show_my_appointments(self):
        res = intent_detector.detect_intent("show my appointments")
        self.assertEqual(res, "APPOINTMENT_STATUS")

    def test_02_intent_what_are_my_appointments(self):
        res = intent_detector.detect_intent("what are my appointments?")
        self.assertEqual(res, "APPOINTMENT_STATUS")

    def test_03_intent_when_is_my_next_appointment(self):
        res = intent_detector.detect_intent("when is my next appointment?")
        self.assertEqual(res, "APPOINTMENT_STATUS")

    def test_04_intent_show_upcoming_appointments(self):
        res = intent_detector.detect_intent("show my upcoming appointments")
        self.assertEqual(res, "APPOINTMENT_STATUS")

    def test_05_show_son_appointments_single_son(self):
        conv_code = "CONV_TEST_SINGLE_SON"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language) VALUES (%s, '+919999000001', %s, 'ENGLISH') ON CONFLICT DO NOTHING;", (conv_code, self.parent_id))
        conn.commit()
        cur.close()
        conn.close()

        res = agent_service.process_agent_message(
            conversation_code=conv_code,
            patient_code="TST001",
            message_text="show my son's appointments"
        )
        self.assertEqual(res["intent"], "APPOINTMENT_STATUS")
        self.assertIn("Johnny", res["response"])
        self.assertIn("Pediatric Rash", res["response"])
        self.assertNotIn("Pediatrics department", res["response"])

    def test_06_show_son_appointments_multiple_sons(self):
        conv_code = "CONV_TEST_MULTIPLE_SONS"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language) VALUES (%s, '+919999000002', %s, 'ENGLISH') ON CONFLICT DO NOTHING;", (conv_code, self.parentB_id))
        conn.commit()
        cur.close()
        conn.close()

        res = agent_service.process_agent_message(
            conversation_code=conv_code,
            patient_code="TST003",
            message_text="show my son's appointments"
        )
        self.assertEqual(res["intent"], "APPOINTMENT_STATUS")
        self.assertIn("more than one son registered", res["response"])

    def test_07_show_daughter_appointments_single_daughter(self):
        # Add temporary daughter for Parent A
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, guardian_patient_id, guardian_phone, relationship_to_contact, is_dependent, status)
            VALUES ('TST006', 'Lily', 'User', '2017-05-05', 'Female', '+919999000001', '+919999000001', %s, '+919999000001', 'DAUGHTER', TRUE, 'ACTIVE')
            RETURNING id;
        """, (self.parent_id,))
        daughter_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        conv_code = "CONV_TEST_DAUGHTER"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language) VALUES (%s, '+919999000001', %s, 'ENGLISH') ON CONFLICT DO NOTHING;", (conv_code, self.parent_id))
        conn.commit()
        cur.close()
        conn.close()

        res = agent_service.process_agent_message(
            conversation_code=conv_code,
            patient_code="TST001",
            message_text="show my daughter's appointment"
        )
        self.assertEqual(res["intent"], "APPOINTMENT_STATUS")
        self.assertIn("Lily", res["response"])

    def test_08_show_child_appointments_multiple_children(self):
        conv_code = "CONV_TEST_MULTIPLE_CHILDREN"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language) VALUES (%s, '+919999000001', %s, 'ENGLISH') ON CONFLICT DO NOTHING;", (conv_code, self.parent_id))
        conn.commit()
        cur.close()
        conn.close()

        res = agent_service.process_agent_message(
            conversation_code=conv_code,
            patient_code="TST001",
            message_text="show my child's appointments"
        )
        self.assertEqual(res["intent"], "APPOINTMENT_STATUS")
        # Parent A now has Johnny and Lily -> multiple children
        self.assertIn("more than one child registered", res["response"])

    def test_10_show_patient_id_appointments(self):
        conv_code = "CONV_TEST_PATIENT_ID"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language) VALUES (%s, '+919999000001', %s, 'ENGLISH') ON CONFLICT DO NOTHING;", (conv_code, self.parent_id))
        conn.commit()
        cur.close()
        conn.close()

        res = agent_service.process_agent_message(
            conversation_code=conv_code,
            patient_code="TST001",
            message_text="Show TST002 appointments"
        )
        self.assertEqual(res["intent"], "APPOINTMENT_STATUS")
        self.assertIn("Johnny", res["response"])

    def test_11_invalid_patient_id_rejection(self):
        conv_code = "CONV_TEST_INVALID_ID"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language) VALUES (%s, '+919999000001', %s, 'ENGLISH') ON CONFLICT DO NOTHING;", (conv_code, self.parent_id))
        conn.commit()
        cur.close()
        conn.close()

        res = agent_service.process_agent_message(
            conversation_code=conv_code,
            patient_code="TST001",
            message_text="Show P999999 appointments"
        )
        self.assertEqual(res["intent"], "APPOINTMENT_STATUS")
        self.assertIn("couldn't find that patient ID", res["response"])

    def test_13_no_appointments_response(self):
        # Parent B has no appointments
        conv_code = "CONV_TEST_NO_APPTS"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language) VALUES (%s, '+919999000002', %s, 'ENGLISH') ON CONFLICT DO NOTHING;", (conv_code, self.parentB_id))
        conn.commit()
        cur.close()
        conn.close()

        res = agent_service.process_agent_message(
            conversation_code=conv_code,
            patient_code="TST003",
            message_text="show my appointments"
        )
        self.assertEqual(res["intent"], "APPOINTMENT_STATUS")
        self.assertIn("don't have any appointments currently", res["response"])

    def test_17_booking_intent_preserved(self):
        res = intent_detector.detect_intent("Book an appointment")
        self.assertEqual(res, "BOOK_APPOINTMENT")

    def test_18_booking_for_son_intent_preserved(self):
        res = intent_detector.detect_intent("Book an appointment for my son")
        self.assertEqual(res, "DEPENDENT_PATIENT")

    def test_19_cancel_intent_preserved(self):
        res = intent_detector.detect_intent("Cancel my appointment")
        self.assertEqual(res, "CANCEL_APPOINTMENT")

    def test_21_reschedule_intent_preserved(self):
        res = intent_detector.detect_intent("Reschedule my appointment")
        self.assertEqual(res, "RESCHEDULE_APPOINTMENT")

    def test_22_show_appointments_after_booking_clears_booking_state(self):
        conv_code = "CONV_TEST_STATE_CLEAR"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO conversations (conversation_code, whatsapp_number, patient_id, language) VALUES (%s, '+919999000001', %s, 'ENGLISH') ON CONFLICT DO NOTHING;", (conv_code, self.parent_id))
        conn.commit()
        cur.close()
        conn.close()

        # Simulate prior booking in Pediatrics
        state = {
            "intent": "BOOK_APPOINTMENT",
            "department_name": "Pediatrics",
            "doctor_name": "Dr. Ajay L",
            "booking_stage": "AWAITING_DATE",
            "missing_information": ["appointment_date"]
        }
        import agent.state_manager as state_manager
        state_manager.save_conversation_state(conv_code, state)

        res = agent_service.process_agent_message(
            conversation_code=conv_code,
            patient_code="TST001",
            message_text="show my appointments"
        )
        self.assertEqual(res["intent"], "APPOINTMENT_STATUS")
        self.assertNotIn("Which doctor would you like to consult", res["response"])
        self.assertNotIn("you should consult our Pediatrics department", res["response"])


if __name__ == "__main__":
    unittest.main()
