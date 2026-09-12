"""
test_emergency_and_hospital_data_suite.py
==========================================
Automated test suite for Emergency Routing & Official Meridian Hospital Data.
Verifies:
- Emergency intent overrides appointment booking with 24/7 hotline 044 6666 9999
- Medical safety warning present ("Do not wait for an appointment for an emergency")
- Hospital contact info returns official numbers (044 6666 9910 / 044 6666 9999 / info@meridian-hospital.com)
- Hospital info overview describes 300-bed multi-super-specialty hospital in Chennai
- All patient-facing responses are completely free of '[POC SAMPLE INFORMATION]' and fake +91 99999 numbers
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

class TestEmergencyAndHospitalDataSuite(unittest.TestCase):

    def setUp(self):
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, patient_code FROM patients WHERE status = 'ACTIVE' LIMIT 1;")
        row = cur.fetchone()
        cur.close()
        conn.close()

        self.pat_id = row[0] if row else 1
        self.pat_code = row[1] if row else "P100001"

        self.conv_code = f"WA_919876543210_TEST_EMG_{os.urandom(4).hex()}"
        state = state_manager.get_conversation_state(self.conv_code, whatsapp_number="919876543210")
        state["patient_id"] = self.pat_id
        state["patient_code"] = self.pat_code
        state["language"] = "ENGLISH"
        agent_service.log_message_to_db(self.conv_code, "PATIENT", "Init state", "ENGLISH", "GREETING", state)
        state_manager.save_conversation_state(self.conv_code, state)

    def test_01_emergency_trigger_returns_official_emergency_details(self):
        """Saying 'Emergency' should override booking and return official 044 6666 9999 helpline."""
        res = agent_service.process_agent_message(self.conv_code, None, "Medical emergency")
        resp = res["response"]

        self.assertIn("MERIDIAN HOSPITAL EMERGENCY", resp)
        self.assertIn("044 6666 9999", resp)
        self.assertIn("044 6666 9910", resp)
        self.assertIn("Jawaharlal Nehru Road", resp)
        self.assertIn("Do not wait for an appointment for an emergency", resp)

        # Ensure NO fake numbers or POC placeholder text
        self.assertNotIn("99999 00000", resp)
        self.assertNotIn("99999 99999", resp)
        self.assertNotIn("99999 11111", resp)
        self.assertNotIn("POC SAMPLE INFORMATION", resp)

    def test_02_give_contact_numbers_returns_official_contacts(self):
        """Asking for contact numbers returns official Meridian phone, email, and address."""
        res = agent_service.process_agent_message(self.conv_code, None, "Give contact numbers")
        resp = res["response"]

        self.assertIn("044 6666 9910", resp)
        self.assertIn("044 6666 9999", resp)
        self.assertIn("info@meridian-hospital.com", resp)
        self.assertIn("Jawaharlal Nehru Road", resp)
        self.assertNotIn("POC SAMPLE INFORMATION", resp)
        self.assertNotIn("99999 00000", resp)

    def test_03_tell_me_about_meridian_hospital(self):
        """Asking about Meridian Hospital returns verified 300-bed hospital overview."""
        res = agent_service.process_agent_message(self.conv_code, None, "Tell me about Meridian Hospital")
        resp = res["response"]

        self.assertIn("Meridian Hospital", resp)
        self.assertIn("300-bed", resp)
        self.assertIn("044 6666 9999", resp)
        self.assertIn("Jawaharlal Nehru Road", resp)
        self.assertNotIn("POC SAMPLE INFORMATION", resp)

    def test_04_no_poc_sample_information_in_knowledge_retrieval(self):
        """RAG knowledge queries must never return '[POC SAMPLE INFORMATION]'."""
        res = agent_service.process_agent_message(self.conv_code, None, "What departments exist at Meridian Hospital?")
        resp = res["response"]
        self.assertNotIn("POC SAMPLE INFORMATION", resp)
        self.assertNotIn("123 Healthcare Lane", resp)

if __name__ == "__main__":
    unittest.main()
