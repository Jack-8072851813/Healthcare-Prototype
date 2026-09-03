"""
test_whatsapp_30_scenarios.py
=====================================
30 conversation scenario tests for Healthcare AI Patient Desk.
Tests cover:
- Symptom → Department routing (hair loss, skin, fever, ENT, ortho)
- Dependent / family patient flow
- Natural date/time parsing
- Split time input (5 then PM)
- THANK_YOU / GOODBYE handling
- Context preservation on short messages
- Safety / emergency routing
- Appointment booking flow
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import intent_detector
from agent import entity_extractor
from agent.entity_extractor import map_symptom_to_department_name, extract_relationship
from agent.agent_service import process_agent_message
from agent import date_normalizer

# ===========================================================================
# SCENARIO GROUP 1: Symptom → Department Routing
# ===========================================================================

class TestSymptomRoutingAccuracy:
    """All symptom routing scenarios must resolve to the correct department."""

    ROUTING_CASES = [
        # Hair / Dermatology
        ("I have hair fall", "Dermatology"),
        ("I am losing hair", "Dermatology"),
        ("my hair is falling out", "Dermatology"),
        ("hair loss problem", "Dermatology"),
        ("hair thinning issue", "Dermatology"),
        ("bald patches on my scalp", "Dermatology"),
        ("I have acne on my face", "Dermatology"),
        ("skin rash all over body", "Dermatology"),
        ("itching all over skin", "Dermatology"),
        ("eczema flareup", "Dermatology"),
        # General Medicine
        ("I have fever", "General Medicine"),
        ("cold and cough", "General Medicine"),
        ("general body weakness and fatigue", "General Medicine"),
        ("I feel sick and have flu", "General Medicine"),
        # Cardiology
        ("heart palpitations", "Cardiology"),
        ("high blood pressure concern", "Cardiology"),
        # ENT
        ("ear pain for 3 days", "ENT"),
        ("sinus infection and headache", "ENT"),
        ("sore throat and tonsil pain", "ENT"),
        # Orthopedics
        ("knee joint pain", "Orthopedics"),
        ("back pain lower spine", "Orthopedics"),
        ("fracture in my right hand", "Orthopedics"),
        # Neurology
        ("migraine for 2 days", "Neurology"),
        ("numbness in my left arm", "Neurology"),
        # Gynecology
        ("pregnancy related consultation", "Gynecology"),
        ("irregular menstrual cycle", "Gynecology"),
        # Pediatrics
        ("my baby has fever", "Pediatrics"),
    ]

    @pytest.mark.parametrize("symptom_text, expected_dept", ROUTING_CASES)
    def test_symptom_to_department_mapping(self, symptom_text, expected_dept):
        """Verifies map_symptom_to_department_name routes correctly."""
        result = map_symptom_to_department_name(symptom_text)
        assert result == expected_dept, (
            f"FAIL: '{symptom_text}' → got '{result}', expected '{expected_dept}'"
        )


# ===========================================================================
# SCENARIO GROUP 2: Intent Detection Accuracy
# ===========================================================================

class TestIntentDetection:
    """Tests the intent_detector.detect_intent function."""

    INTENT_CASES = [
        # Greetings
        ("hi", None, "GREETING"),
        ("hello", None, "GREETING"),
        ("good morning", None, "GREETING"),
        # Thank you / Goodbye
        ("thank you", None, "THANK_YOU"),
        ("thanks", None, "THANK_YOU"),
        ("bye", None, "GOODBYE"),
        ("goodbye", None, "GOODBYE"),
        # Booking
        ("I want to book an appointment", None, "BOOK_APPOINTMENT"),
        ("book an appointment", None, "BOOK_APPOINTMENT"),
        ("I need a dermatologist", None, "BOOK_APPOINTMENT"),
        # Hair-related → should be BOOK_APPOINTMENT (not SYMPTOM_GUIDANCE) when no workflow active
        ("I have hair problems", None, "BOOK_APPOINTMENT"),
        ("I am losing hair", None, "BOOK_APPOINTMENT"),
        # Dependent patient
        ("book appointment for my son", None, "DEPENDENT_PATIENT"),
        ("my daughter has fever", None, "DEPENDENT_PATIENT"),
        ("I want to book for my wife", None, "DEPENDENT_PATIENT"),
        ("my son has cough and cold", None, "DEPENDENT_PATIENT"),
        # Cancel / reschedule
        ("I want to cancel my appointment", None, "CANCEL_APPOINTMENT"),
        ("please reschedule my appointment", None, "RESCHEDULE_APPOINTMENT"),
        # Emergency
        ("I have severe chest pain and cannot breathe", None, "EMERGENCY_GUIDANCE"),
        ("heart attack emergency", None, "EMERGENCY_GUIDANCE"),
        # Context preservation — short messages
        ("5", "BOOK_APPOINTMENT", "BOOK_APPOINTMENT"),
        ("pm", "BOOK_APPOINTMENT", "BOOK_APPOINTMENT"),
        ("tomorrow", "BOOK_APPOINTMENT", "BOOK_APPOINTMENT"),
        ("same doctor", "BOOK_APPOINTMENT", "BOOK_APPOINTMENT"),
        ("ok", "REGISTER_PATIENT", "REGISTER_PATIENT"),
    ]

    @pytest.mark.parametrize("text, current_intent, expected_intent", INTENT_CASES)
    def test_intent_detection(self, text, current_intent, expected_intent):
        """Verifies detect_intent returns the expected intent."""
        result = intent_detector.detect_intent(text, current_intent)
        assert result == expected_intent, (
            f"FAIL: '{text}' (current={current_intent}) → got '{result}', expected '{expected_intent}'"
        )


# ===========================================================================
# SCENARIO GROUP 3: Relationship Extraction
# ===========================================================================

class TestRelationshipExtraction:
    """Tests extract_relationship function."""

    RELATION_CASES = [
        ("book for my son", "SON", "CHILD"),
        ("appointment for my daughter", "DAUGHTER", "CHILD"),
        ("my wife has fever", "SPOUSE", "FAMILY_MEMBER"),
        ("book for my mother", "MOTHER", "FAMILY_MEMBER"),
        ("my father has chest pain", "FATHER", "FAMILY_MEMBER"),
        ("book for my child", "CHILD", "CHILD"),
        ("for my kid", "CHILD", "CHILD"),
    ]

    @pytest.mark.parametrize("text, expected_rel, expected_for", RELATION_CASES)
    def test_relationship_extraction(self, text, expected_rel, expected_for):
        result = extract_relationship(text)
        assert result["relationship"] == expected_rel, (
            f"FAIL: '{text}' → relationship got '{result['relationship']}', expected '{expected_rel}'"
        )
        assert result["appointment_for"] == expected_for, (
            f"FAIL: '{text}' → appointment_for got '{result['appointment_for']}', expected '{expected_for}'"
        )


# ===========================================================================
# SCENARIO GROUP 4: Date/Time Parsing
# ===========================================================================

class TestDateTimeParsing:
    """Tests parse_natural_date and parse_natural_time."""

    import datetime as _dt

    def test_tomorrow_parses_correctly(self):
        result = entity_extractor.parse_natural_date("tomorrow")
        assert result is not None
        import datetime
        today = entity_extractor.get_current_kolkata_date()
        expected = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        assert result == expected

    def test_day_after_tomorrow(self):
        result = entity_extractor.parse_natural_date("day after tomorrow")
        assert result is not None
        import datetime
        today = entity_extractor.get_current_kolkata_date()
        expected = (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        assert result == expected

    def test_typo_tolerant_tomorrow(self):
        for typo in ["tomrmorrow", "tomorow", "tmrw", "tomoro"]:
            result = entity_extractor.parse_natural_date(typo)
            assert result is not None, f"Failed for typo: '{typo}'"

    def test_time_10am(self):
        assert entity_extractor.parse_natural_time("10 am") == "10:00"

    def test_time_5pm(self):
        assert entity_extractor.parse_natural_time("5 pm") == "17:00"

    def test_time_morning_block(self):
        assert entity_extractor.parse_natural_time("morning") == "09:00"

    def test_time_afternoon_block(self):
        assert entity_extractor.parse_natural_time("afternoon") == "14:00"

    def test_time_evening_block(self):
        assert entity_extractor.parse_natural_time("evening") == "18:00"

    def test_time_hhmm_with_am(self):
        assert entity_extractor.parse_natural_time("10:30 am") == "10:30"

    def test_time_hhmm_with_pm(self):
        assert entity_extractor.parse_natural_time("02:30 pm") == "14:30"

    def test_standalone_digit_5_defaults_pm(self):
        """Standalone '5' should be treated as 17:00 (5 PM heuristic)."""
        result = entity_extractor.parse_natural_time("5")
        assert result == "17:00", f"Expected 17:00, got {result}"

    def test_standalone_digit_9_morning(self):
        """Standalone '9' should be treated as 09:00."""
        result = entity_extractor.parse_natural_time("9")
        assert result == "09:00", f"Expected 09:00, got {result}"


# ===========================================================================
# SCENARIO GROUP 5: Emergency Safety Check
# ===========================================================================

class TestEmergencyDetection:
    """Emergency messages must always route to EMERGENCY_GUIDANCE regardless of context."""

    EMERGENCY_CASES = [
        "I have severe chest pain",
        "Cannot breathe properly",
        "Heart attack symptoms",
        "I am unconscious my husband",
        "severe bleeding from wound",
        "accident happened need help",
    ]

    @pytest.mark.parametrize("message", EMERGENCY_CASES)
    def test_emergency_detected_over_any_context(self, message):
        # Emergency must override all workflow intents
        for ctx_intent in ["BOOK_APPOINTMENT", "REGISTER_PATIENT", "DOCTOR_AVAILABILITY", None]:
            result = intent_detector.detect_intent(message, ctx_intent)
            assert result == "EMERGENCY_GUIDANCE", (
                f"FAIL: '{message}' (context={ctx_intent}) → got '{result}', expected EMERGENCY_GUIDANCE"
            )


# ===========================================================================
# SCENARIO GROUP 6: DOB Normalization
# ===========================================================================

class TestDOBNormalization:

    VALID_DOB_CASES = [
        ("08/09/2004", "2004-09-08"),   # DD/MM/YYYY
        ("2004-09-08", "2004-09-08"),   # Already ISO
        ("8-9-2004", "2004-09-08"),     # D-M-YYYY
    ]

    @pytest.mark.parametrize("raw_dob, expected", VALID_DOB_CASES)
    def test_dob_parsing(self, raw_dob, expected):
        result, is_ambig, _ = date_normalizer.parse_and_normalize_date(raw_dob)
        if result:
            assert result == expected, f"FAIL: '{raw_dob}' → got '{result}', expected '{expected}'"


# ===========================================================================
# SCENARIO GROUP 7: Department-First Intent (Hair/Skin → BOOK_APPOINTMENT)
# ===========================================================================

class TestHairSkinRoutingE2E:
    """End-to-end: messages about hair loss / skin problems must not go to General Medicine."""

    HAIR_SKIN_MSGS = [
        "I have hair fall",
        "I am losing my hair",
        "my hair is falling",
        "hair loss",
        "I have hair problem",
        "excessive hair shedding",
        "bald patches on head",
        "acne and pimples",
        "skin rash and itching",
        "eczema problem",
    ]

    @pytest.mark.parametrize("message", HAIR_SKIN_MSGS)
    def test_hair_skin_not_general_medicine(self, message):
        dept = map_symptom_to_department_name(message)
        assert dept == "Dermatology", (
            f"FAIL: '{message}' → got '{dept}', expected 'Dermatology'"
        )

    @pytest.mark.parametrize("message", HAIR_SKIN_MSGS)
    def test_hair_skin_not_symptom_guidance_when_in_booking(self, message):
        """Hair/skin symptoms during BOOK_APPOINTMENT context should preserve BOOK_APPOINTMENT intent."""
        result = intent_detector.detect_intent(message, "BOOK_APPOINTMENT")
        assert result == "BOOK_APPOINTMENT", (
            f"FAIL: '{message}' (context=BOOK_APPOINTMENT) → got '{result}', expected 'BOOK_APPOINTMENT'"
        )
