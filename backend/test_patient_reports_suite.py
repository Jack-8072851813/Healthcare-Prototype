"""
test_patient_reports_suite.py
==============================
Automated test suite for Patient Reports flow in Meridian Hospital AI Patient Desk.
Verifies:
- PATIENT_REPORTS intent displays report list
- Report detail tap displays report summary card
- Patient ID isolation (strictly filters by patient_id)
- [ Back to Reports ] button navigation
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

class TestPatientReportsSuite(unittest.TestCase):

    def setUp(self):
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT patient_id FROM patient_reports LIMIT 2;")
        rep_pats = cur.fetchall()
        cur.execute("SELECT id, patient_code FROM patients WHERE status = 'ACTIVE';")
        all_pats = {r[0]: r[1] for r in cur.fetchall()}

        self.pat1_id = rep_pats[0][0] if len(rep_pats) > 0 else 1
        self.pat1_code = all_pats.get(self.pat1_id, "P100001")
        self.pat2_id = rep_pats[1][0] if len(rep_pats) > 1 else (self.pat1_id + 1)
        self.pat2_code = all_pats.get(self.pat2_id, "P100002")

        cur.execute("UPDATE patients SET whatsapp_number = '919876543210' WHERE id = %s;", (self.pat1_id,))
        conn.commit()
        cur.close()
        conn.close()

        self.conv_code = f"WA_919876543210_TEST_REP_{os.urandom(4).hex()}"
        state = state_manager.get_conversation_state(self.conv_code, whatsapp_number="919876543210")
        state["patient_id"] = self.pat1_id
        state["patient_code"] = self.pat1_code
        state["language"] = "ENGLISH"
        agent_service.log_message_to_db(self.conv_code, "PATIENT", "Init state", "ENGLISH", "GREETING", state)
        state_manager.save_conversation_state(self.conv_code, state)

    def test_01_my_reports_intent_returns_report_list(self):
        """Requesting 'My Reports' should list available reports for the identified patient."""
        res = agent_service.process_agent_message(self.conv_code, None, "my reports")
        self.assertIn("Your Reports", res["response"])
        btn_ids = [b["id"] for b in res.get("interactive_buttons", [])]
        self.assertTrue(any(b.startswith("btn_report_") for b in btn_ids) or "btn_hosp_info" in btn_ids)

    def test_02_report_detail_tap_displays_summary_card(self):
        """Tapping a specific report button should display the report detail card."""
        res_list = agent_service.process_agent_message(self.conv_code, None, "my reports")
        btn_ids = [b["id"] for b in res_list.get("interactive_buttons", []) if b["id"].startswith("btn_report_")]
        if btn_ids:
            rep_btn = btn_ids[0]
            res = agent_service.process_agent_message(self.conv_code, None, rep_btn)
            self.assertIn("Report ID:", res["response"])
            self.assertIn("Summary:", res["response"])
            b_ids = [b["id"] for b in res.get("interactive_buttons", [])]
            self.assertIn("btn_my_reports", b_ids)

    def test_03_patient_isolation_prevents_access_to_other_patient_reports(self):
        """A patient cannot view report details belonging to another patient ID."""
        # Find a report belonging to pat2
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM patient_reports WHERE patient_id = %s LIMIT 1;", (self.pat2_id,))
        p2_rep = cur.fetchone()
        cur.close()
        conn.close()

        if p2_rep:
            other_rep_btn = f"btn_report_{p2_rep[0]}"
            res = agent_service.process_agent_message(self.conv_code, None, other_rep_btn)
            # Should NOT display report details of pat2
            self.assertNotIn("Report ID: REP", res["response"])

if __name__ == "__main__":
    unittest.main()
