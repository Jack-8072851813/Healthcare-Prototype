import unittest
import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from agent.agent_service import process_agent_message
from agent.language_service import get_translated_button

class TestGenderButtonFix(unittest.TestCase):

    def test_translated_button_gender_english(self):
        btn_m = get_translated_button("btn_g_male", "ENGLISH")
        btn_f = get_translated_button("btn_g_female", "ENGLISH")
        btn_o = get_translated_button("btn_g_other", "ENGLISH")

        self.assertEqual(btn_m["title"], "Male")
        self.assertEqual(btn_f["title"], "Female")
        self.assertEqual(btn_o["title"], "Other")

    def test_translated_button_gender_tamil(self):
        btn_m = get_translated_button("btn_g_male", "TAMIL")
        btn_f = get_translated_button("btn_g_female", "TAMIL")
        btn_o = get_translated_button("btn_g_other", "TAMIL")

        self.assertEqual(btn_m["title"], "ஆண்")
        self.assertEqual(btn_f["title"], "பெண்")
        self.assertEqual(btn_o["title"], "மற்றவை")

    def test_gender_selection_flow_interactive_buttons(self):
        conv_code = "TEST_GENDER_BTN_FLOW_999"
        # Turn 1: Initial greeting
        res1 = process_agent_message(conv_code, patient_code=None, message_text="Hi")
        # Turn 2: Select first time visitor
        res2 = process_agent_message(conv_code, patient_code=None, message_text="btn_first_time")
        # Turn 3: Name
        res3 = process_agent_message(conv_code, patient_code=None, message_text="Deepa T")
        # Turn 4: DOB
        res4 = process_agent_message(conv_code, patient_code=None, message_text="10/10/1990")

        self.assertIn("Please select your gender", res4["response"])
        buttons = res4.get("interactive_buttons", [])
        self.assertEqual(len(buttons), 3)
        titles = [b["title"] for b in buttons]
        self.assertEqual(titles, ["Male", "Female", "Other"])

        # Turn 5: Click Female button
        res5 = process_agent_message(conv_code, patient_code=None, message_text="btn_g_female")
        self.assertIn("Your registration with Meridian Hospital is complete", res5["response"])

if __name__ == "__main__":
    unittest.main()
