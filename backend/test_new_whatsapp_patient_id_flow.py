import sys
import os
import unittest
import uuid
import re

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from agent.agent_service import process_agent_message
from agent import state_manager, language_service


class TestNewWhatsAppPatientIDFlow(unittest.TestCase):

    def setUp(self):
        """Cleanup test numbers and patients before each test."""
        self.test_wa_1 = "919888111001"
        self.test_wa_2 = "919888111002"
        self.test_wa_3 = "919888111003"
        self.test_wa_4 = "919888111004"
        self.test_wa_5 = "919888111005"
        self.test_wa_6 = "919888111006"
        self.test_wa_7 = "919888111007"
        self.test_wa_8 = "919888111008"
        self.test_wa_9 = "919888111009"
        self.test_wa_10 = "919888111010"

        all_phones = [
            self.test_wa_1, self.test_wa_2, self.test_wa_3, self.test_wa_4, self.test_wa_5,
            self.test_wa_6, self.test_wa_7, self.test_wa_8, self.test_wa_9, self.test_wa_10
        ]

        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            for ph in all_phones:
                cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE phone = %s OR whatsapp_number = %s);", (ph, ph))
                cur.execute("DELETE FROM conversations WHERE whatsapp_number = %s OR conversation_code LIKE %s;", (ph, f"WA_{ph}_%"))
                cur.execute("DELETE FROM patients WHERE phone = %s OR whatsapp_number = %s;", (ph, ph))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("setUp error:", e)
        finally:
            cur.close()
            conn.close()

    def test_1_unknown_whatsapp_first_time_visitor_step_by_step(self):
        """TEST 1: Unknown WhatsApp number -> First-time Visitor -> Name -> DOB -> Gender -> Phone auto-retrieved -> Registration -> Thank-you -> Main Menu."""
        conv_code = f"WA_{self.test_wa_1}_101"

        # Turn 1: Initial greeting from unknown number
        res1 = process_agent_message(conv_code, patient_code=None, message_text="Hi hospital")
        self.assertIn("Welcome to Meridian Hospital", res1["response"])
        self.assertIn("Are you an existing patient or a first-time visitor?", res1["response"])
        btn_titles = [b.get("title") if isinstance(b, dict) else b for b in res1["interactive_buttons"]]
        self.assertTrue(any("First-time" in str(b) for b in btn_titles))

        # Turn 2: Click First-time Visitor
        res2 = process_agent_message(conv_code, patient_code=None, message_text="btn_first_time")
        self.assertIn("Please provide your name", res2["response"])

        # Turn 3: Provide Name
        res3 = process_agent_message(conv_code, patient_code=None, message_text="Robert Swamy")
        self.assertIn("Please provide your date of birth", res3["response"])

        # Turn 4: Provide DOB
        res4 = process_agent_message(conv_code, patient_code=None, message_text="15 August 1995")
        self.assertIn("Please select your gender", res4["response"])

        # Turn 5: Select Gender Male
        res5 = process_agent_message(conv_code, patient_code=None, message_text="btn_g_male")
        self.assertIn("Your registration with Meridian Hospital is complete", res5["response"])
        self.assertIn("Patient ID:", res5["response"])
        self.assertIn("How can I help you today?", res5["response"])

        # Verify patient record was created in DB
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, patient_code, first_name, phone, whatsapp_number FROM patients WHERE whatsapp_number = %s;", (self.test_wa_1,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[2], "Robert")
        self.assertEqual(row[4], self.test_wa_1)

    def test_2_unknown_whatsapp_existing_patient_id_lookup(self):
        """TEST 2: Unknown WhatsApp number -> Existing Patient -> Patient ID -> Existing patient retrieved -> Confirmation -> Main Menu."""
        # Create an existing patient in DB under a different phone
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM patients WHERE patient_code = 'P9901';")
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, status)
            VALUES ('P9901', 'Alice', 'Walker', '1990-05-20', 'Female', '9199990001', 'ACTIVE')
            RETURNING id;
        """)
        exist_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()

        conv_code = f"WA_{self.test_wa_2}_102"

        # Turn 1: Initial message
        res1 = process_agent_message(conv_code, patient_code=None, message_text="Hello")
        self.assertIn("Welcome to Meridian Hospital", res1["response"])

        # Turn 2: Click Existing Patient
        res2 = process_agent_message(conv_code, patient_code=None, message_text="Existing Patient")
        self.assertIn("Please provide your Patient ID", res2["response"])

        # Turn 3: Enter Patient ID P9901
        res3 = process_agent_message(conv_code, patient_code=None, message_text="P9901")
        self.assertIn("Thank you. I found your patient record", res3["response"])
        self.assertIn("P9901", res3["response"])
        self.assertIn("Alice", res3["response"])
        self.assertIn("How can I help you today?", res3["response"])

        # Verify WhatsApp number is linked in DB
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT whatsapp_number FROM patients WHERE id = %s;", (exist_id,))
        linked_wa = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(linked_wa, self.test_wa_2)

    def test_3_unknown_whatsapp_all_details_in_one_message(self):
        """TEST 3: Unknown WhatsApp number -> First-time Visitor -> All registration details in one message."""
        conv_code = f"WA_{self.test_wa_3}_103"

        # Turn 1: Initial message with all registration details
        res1 = process_agent_message(
            conv_code,
            patient_code=None,
            message_text="I am a first-time visitor. My name is John Smith, DOB 15/08/2004, male."
        )
        self.assertIn("Your registration with Meridian Hospital is complete", res1["response"])
        self.assertIn("Patient ID:", res1["response"])

    def test_4_unknown_whatsapp_invalid_patient_id_retry(self):
        """TEST 4: Unknown WhatsApp number -> Existing Patient -> Invalid Patient ID -> Error -> Retry -> No patient created."""
        conv_code = f"WA_{self.test_wa_4}_104"

        # Turn 1: Initial message
        process_agent_message(conv_code, patient_code=None, message_text="Hi")

        # Turn 2: Select Existing Patient
        res2 = process_agent_message(conv_code, patient_code=None, message_text="Existing Patient")

        # Turn 3: Enter invalid ID P999999
        res3 = process_agent_message(conv_code, patient_code=None, message_text="P999999")
        self.assertIn("couldn't find a patient record with that Patient ID", res3["response"])
        btn_titles = [b.get("title") if isinstance(b, dict) else b for b in res3["interactive_buttons"]]
        self.assertTrue(any("Try Again" in str(b) for b in btn_titles))

        # Verify no fake patient was created in DB
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM patients WHERE whatsapp_number = %s;", (self.test_wa_4,))
        cnt = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(cnt, 0)

    def test_5_existing_whatsapp_number_bypasses_gate(self):
        """TEST 5: Existing WhatsApp number -> Existing patient recognized -> Existing flow remains unchanged."""
        # Create patient in DB with whatsapp_number = self.test_wa_5
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM patients WHERE patient_code = 'P9905';")
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
            VALUES ('P9905', 'Karthik', 'Raja', '1988-12-10', 'Male', '919888111005', '919888111005', 'ACTIVE');
        """)
        conn.commit()
        cur.close()
        conn.close()

        conv_code = f"WA_{self.test_wa_5}_105"

        # First message from recognized number
        res1 = process_agent_message(conv_code, patient_code=None, message_text="Hello")
        self.assertNotIn("Are you an existing patient or a first-time visitor?", res1["response"])

    def test_6_duplicate_phone_check_before_creation(self):
        """TEST 6: Unknown number attempts First-time Visitor -> Registration -> Final duplicate phone check -> No duplicate patient created."""
        pre_existing_phone = "9199990006"
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM patients WHERE phone = %s;", (pre_existing_phone,))
        cur.execute("""
            INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, status)
            VALUES ('P9906', 'Meena', 'Kumari', '1992-04-14', 'Female', %s, 'ACTIVE');
        """, (pre_existing_phone,))
        conn.commit()
        cur.close()
        conn.close()

        conv_code = f"WA_{self.test_wa_6}_106"

        res1 = process_agent_message(conv_code, patient_code=None, message_text="First-time Visitor")
        res2 = process_agent_message(conv_code, patient_code=None, message_text="Meena Kumari, 14/04/1992, Female, 9199990006")
        self.assertIn("complete", res2["response"].lower())

        # Verify only 1 patient record exists for pre_existing_phone
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM patients WHERE phone = %s;", (pre_existing_phone,))
        cnt = cur.fetchone()[0]
        cur.close()
        conn.close()
        self.assertEqual(cnt, 1)


    def test_7_tamil_registration_flow(self):
        """TEST 7: Tamil registration flow."""
        conv_code = f"WA_{self.test_wa_7}_107"

        res1 = process_agent_message(conv_code, patient_code=None, message_text="வணக்கம்")
        self.assertIn("நோயாளியா", res1["response"])

        res2 = process_agent_message(conv_code, patient_code=None, message_text="முதல் முறை வருபவர்", language_override="TAMIL")
        self.assertIn("பெயரை", res2["response"])

    def test_8_hindi_registration_flow(self):
        """TEST 8: Hindi registration flow."""
        conv_code = f"WA_{self.test_wa_8}_108"

        res1 = process_agent_message(conv_code, patient_code=None, message_text="नमस्ते")
        self.assertIn("स्वागत", res1["response"])

    def test_9_voice_message_unknown_number(self):
        """TEST 9: Voice message from unknown number -> enters patient identification flow."""
        conv_code = f"WA_{self.test_wa_9}_109"

        res1 = process_agent_message(conv_code, patient_code=None, message_text="Hello I want to book an appointment")
        self.assertIn("Welcome to Meridian Hospital", res1["response"])
        self.assertIn("Are you an existing patient or a first-time visitor?", res1["response"])

    def test_10_after_identification_book_appointment(self):
        """TEST 10: After successful identification -> Book Appointment -> existing appointment flow works unchanged."""
        conv_code = f"WA_{self.test_wa_10}_110"

        # Complete registration
        process_agent_message(conv_code, patient_code=None, message_text="First-time Visitor")
        process_agent_message(conv_code, patient_code=None, message_text="David Miller, 10/10/1985, Male")

        # Now click Book Appointment
        res = process_agent_message(conv_code, patient_code=None, message_text="btn_book_appt")
        self.assertTrue("department" in res["response"].lower() or "doctor" in res["response"].lower() or "appointment" in res["response"].lower())


if __name__ == "__main__":
    unittest.main()
