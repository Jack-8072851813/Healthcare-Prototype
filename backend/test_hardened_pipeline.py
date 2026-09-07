"""
test_hardened_pipeline.py
==========================
Regression and unit tests for the hardened AI Patient Desk pipeline.

Covers all 5 confirmed failure cases plus unit tests for:
  - grounding_validator (6 adversarial cases)
  - message_aggregator (split-message merging)
  - conversation_stages (transition table)

Run with:
    cd backend
    pytest test_hardened_pipeline.py -v

No database connection required for unit tests (grounding_validator,
message_aggregator, conversation_stages are pure / in-memory).
"""

import sys
import os
import datetime
import time

# Ensure backend dir is importable
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest

# ---------------------------------------------------------------------------
# 1. Grounding Validator — unit tests (6 adversarial cases)
# ---------------------------------------------------------------------------
from agent.grounding_validator import validate_extraction


class TestGroundingValidator:
    """Adversarial inputs that must be rejected or nulled by the validator."""

    def _run(self, user_message: str, extracted: dict, pending_stage: str = None) -> dict:
        result = validate_extraction(
            user_message=user_message,
            conversation_state={},
            extracted_fields=extracted,
            pending_stage=pending_stage,
        )
        return result["cleaned"]

    # --- Case 1 (Failure #1): Greeting after booking context ---
    def test_greeting_nulls_medical_fields(self):
        """
        Patient sends 'Good Morning' after a prior booking session.
        LLM should have returned all entity fields null (prompt enforces this),
        but even if it leaks a prior medical_reason, grounding_validator must
        reject it because the current message contains no medical content.
        """
        msg = "Good Morning"
        extracted = {
            "intent": "GREETING",
            "medical_reason": "fever",  # hallucinated carryover
            "reason_raw_quote": None,   # no quote — not in message
            "appointment_date": "2026-09-06",
            "date_raw_quote": None,
            "doctor_name": None,
            "doctor_raw_quote": None,
            "patient_name": None,
            "patient_name_raw_quote": None,
            "appointment_time": None,
            "time_raw_quote": None,
        }
        cleaned = self._run(msg, extracted)
        assert cleaned["medical_reason"] is None, "medical_reason must be null for greeting"
        assert cleaned["appointment_date"] is None, "appointment_date must be null for greeting"

    # --- Case 2 (Failure #2): Doctor name must not leak into reason/condition ---
    def test_doctor_name_not_in_reason(self):
        """
        Booking flow: LLM sets reason='Dr. Sharma' (cross-field contamination).
        grounding_validator must reject this because reason equals a doctor name.
        """
        msg = "I want to book an appointment with Dr. Sharma"
        extracted = {
            "intent": "BOOK_APPOINTMENT",
            "medical_reason": "Dr. Sharma",      # contamination
            "reason_raw_quote": "Dr. Sharma",    # quote exists in message BUT fails cross-check
            "doctor_name": "Dr. Sharma",
            "doctor_raw_quote": "Dr. Sharma",
            "appointment_date": None,
            "date_raw_quote": None,
            "appointment_time": None,
            "time_raw_quote": None,
            "patient_name": None,
            "patient_name_raw_quote": None,
        }
        cleaned = self._run(msg, extracted)
        # Doctor passes (explicitly named by patient)
        assert cleaned["doctor_name"] == "Dr. Sharma"
        # Reason must be null (equals doctor name)
        assert cleaned["medical_reason"] is None, (
            "medical_reason must not equal doctor_name"
        )

    # --- Case 3 (Failure #3): Garbage/implausible patient name rejected ---
    def test_implausible_name_rejected(self):
        """
        Patient sends a garbled registration string.
        patient_name 'shs' or '123' must be rejected.
        """
        for bad_name in ["shs", "123", "x", "test", "null"]:
            msg = f"My name is {bad_name}"
            extracted = {
                "patient_name": bad_name,
                "patient_name_raw_quote": bad_name,
            }
            cleaned = self._run(msg, extracted)
            assert cleaned["patient_name"] is None, (
                f"patient_name '{bad_name}' should be rejected as implausible"
            )

    # --- Case 4 (Failure #4): Intent label must not appear in reason ---
    def test_intent_label_as_reason_rejected(self):
        """
        LLM sets medical_reason='Book Appointment' (echoing intent label).
        Must be rejected.
        """
        msg = "I want to book an appointment"
        extracted = {
            "intent": "BOOK_APPOINTMENT",
            "medical_reason": "Book Appointment",
            "reason_raw_quote": "book an appointment",
        }
        cleaned = self._run(msg, extracted)
        assert cleaned["medical_reason"] is None, (
            "Intent label must not appear in medical_reason"
        )

    # --- Case 5 (Failure #5): Hallucinated date without quote rejected ---
    def test_hallucinated_date_without_quote_rejected(self):
        """
        LLM returns an appointment_date that is NOT mentioned in the current message.
        No date_raw_quote provided → should be nulled.
        """
        msg = "I have hair problems"
        extracted = {
            "intent": "BOOK_APPOINTMENT",
            "medical_reason": "hair problems",
            "reason_raw_quote": "hair problems",
            "appointment_date": "2026-09-10",  # hallucinated
            "date_raw_quote": None,             # no quote
        }
        cleaned = self._run(msg, extracted)
        assert cleaned["appointment_date"] is None, (
            "appointment_date without grounding quote must be nulled"
        )

    # --- Case 5b: Stale carryover date from prior turn ---
    def test_stale_date_carryover_rejected(self):
        """
        Date was set in previous turn. LLM silently copies it into this turn's output.
        State has appointment_date='2026-09-10'. Current message has no date mention.
        The validator must detect the stale carryover and null it.
        """
        msg = "Actually I'd like morning slots"  # no date mentioned
        prior_state = {"entities": {"appointment_date": "2026-09-10"}}
        extracted = {
            "appointment_date": "2026-09-10",  # copied from prior state
            "date_raw_quote": None,
        }
        result = validate_extraction(
            user_message=msg,
            conversation_state=prior_state,
            extracted_fields=extracted,
            pending_stage=None,
        )
        assert result["cleaned"]["appointment_date"] is None, (
            "Stale date carryover from prior state must be rejected"
        )

    # --- Positive: Valid date with quote passes ---
    def test_valid_date_with_quote_passes(self):
        """Patient says 'tomorrow' → date extracted with quote 'tomorrow' → should pass."""
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        msg = "I want to book tomorrow"
        extracted = {
            "appointment_date": tomorrow,
            "date_raw_quote": "tomorrow",
        }
        cleaned = self._run(msg, extracted)
        assert cleaned["appointment_date"] == tomorrow, (
            "Valid future date with grounding quote must pass"
        )

    # --- Positive: Past date rejected ---
    def test_past_date_rejected(self):
        """Appointment date in the past must be rejected."""
        past = "2024-01-01"
        msg = "I want an appointment on 01 January 2024"
        extracted = {
            "appointment_date": past,
            "date_raw_quote": "01 January 2024",
        }
        cleaned = self._run(msg, extracted)
        assert cleaned["appointment_date"] is None, (
            "Past appointment_date must be rejected"
        )

    # --- Pending stage override: answer to AWAITING_DATE accepted without quote ---
    def test_awaiting_date_stage_allows_answer(self):
        """
        When pending_stage=AWAITING_DATE and patient directly answers with a date,
        the grounding_validator should accept it even without a raw_quote.
        """
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        msg = "Tomorrow"
        extracted = {
            "appointment_date": tomorrow,
            "date_raw_quote": "Tomorrow",  # quote present in this case
        }
        cleaned = self._run(msg, extracted, pending_stage="AWAITING_DATE")
        assert cleaned["appointment_date"] == tomorrow


# ---------------------------------------------------------------------------
# 2. Message Aggregator — unit tests
# ---------------------------------------------------------------------------
from agent.message_aggregator import MessageAggregator


class TestMessageAggregator:
    """Tests for the debounce-based message aggregator."""

    def test_single_message_buffered(self):
        """A single message is buffered (window stays open)."""
        agg = MessageAggregator(window_seconds=60.0)  # very long window
        result = agg.add("+919876543210", "Hello doctor")
        # Should be buffering — returns None
        assert result is None

    def test_split_messages_merged_on_flush(self):
        """
        Two rapid messages are concatenated when flush is called.
        Simulates "5" then "PM" → should merge to "5 PM".
        """
        agg = MessageAggregator(window_seconds=60.0)
        agg.add("+919876543210", "5")
        # Second message arrives — window still open
        agg.add("+919876543210", "PM")
        # Manually flush
        merged = agg.flush("+919876543210")
        assert merged == "5 PM", f"Expected '5 PM', got '{merged}'"

    def test_split_messages_time_window(self):
        """
        Two messages within the window are merged.
        Uses a very short window (0.3 s) and checks flush after window expires.
        """
        flushed = []
        agg = MessageAggregator(window_seconds=0.3)

        def _cb(phone, text):
            flushed.append(text)

        agg.set_flush_callback(_cb)
        agg.add("+911234567890", "I want")
        time.sleep(0.05)  # small gap
        agg.add("+911234567890", "fever appointment")
        time.sleep(0.5)   # wait for window to expire
        assert len(flushed) == 1, "Should have one flushed item"
        assert "fever appointment" in flushed[0], f"Unexpected merged text: {flushed[0]}"
        assert "I want" in flushed[0], f"First fragment missing: {flushed[0]}"

    def test_different_senders_independent(self):
        """Two different senders have independent buffers."""
        agg = MessageAggregator(window_seconds=60.0)
        agg.add("phone_A", "Hello")
        agg.add("phone_B", "Goodbye")
        merged_a = agg.flush("phone_A")
        merged_b = agg.flush("phone_B")
        assert merged_a == "Hello"
        assert merged_b == "Goodbye"

    def test_separator_digits_and_unit(self):
        """'5' + 'PM' should be joined with a space."""
        agg = MessageAggregator(window_seconds=60.0)
        agg.add("test_num", "5")
        agg.add("test_num", "PM")
        merged = agg.flush("test_num")
        assert merged == "5 PM"

    def test_flush_immediate(self):
        """flush_immediate merges pending and new text, returns immediately."""
        agg = MessageAggregator(window_seconds=60.0)
        agg.add("flush_test", "I want to book")
        merged = agg.flush_immediate("flush_test", "tomorrow")
        assert "I want to book" in merged
        assert "tomorrow" in merged


# ---------------------------------------------------------------------------
# 3. Conversation Stages — transition table unit tests
# ---------------------------------------------------------------------------
from agent.conversation_stages import (
    Stage, next_stage, merge_state, get_next_missing_reg_field,
    build_incremental_reg_prompt, REG_FIELD_ORDER
)


class TestConversationStages:

    def test_greeting_clears_booking_context(self):
        """GREETING intent with no entities should clear booking fields."""
        state = {
            "entities": {
                "patient_id": 42,
                "doctor_id": 7,
                "department_id": 3,
                "appointment_date": "2026-09-10",
                "appointment_time": "09:00",
                "reason": "fever",
                "symptoms": ["fever"],
                "booking_id": None,
            },
            "department_name": "General Medicine",
            "doctor_name": "Dr. Arun",
            "confirmation_pending": True,
            "previous_question": "would_you_like_to_book_this_appointment",
            "booking_stage": "AWAITING_CONFIRMATION",
            "patient_id": 42,
        }
        result = merge_state(state, {}, intent="GREETING", previous_intent="BOOK_APPOINTMENT")

        assert result["entities"]["appointment_date"] is None
        assert result["entities"]["appointment_time"] is None
        assert result["entities"]["doctor_id"] is None
        assert result["entities"]["department_id"] is None
        assert result["entities"]["reason"] is None
        # Patient identity must be preserved
        assert result["patient_id"] == 42

    def test_registration_stage_transitions(self):
        """Registration stages advance correctly as fields are validated."""
        # REGISTERING_NAME → should advance to REGISTERING_DOB when name is present
        stage = next_stage(Stage.REGISTERING_NAME, {"patient_name": "Arokiya"}, "REGISTER_PATIENT")
        assert stage == Stage.REGISTERING_DOB

        # REGISTERING_DOB → REGISTERING_GENDER
        stage = next_stage(Stage.REGISTERING_DOB, {"date_of_birth": "2004-09-08"}, "REGISTER_PATIENT")
        assert stage == Stage.REGISTERING_GENDER

        # Missing field → stays at current stage
        stage = next_stage(Stage.REGISTERING_NAME, {}, "REGISTER_PATIENT")
        assert stage == Stage.REGISTERING_NAME

    def test_booking_date_advances_to_time(self):
        """After date is validated, stage advances to AWAITING_TIME."""
        stage = next_stage(Stage.AWAITING_DATE, {"appointment_date": "2026-09-10"}, "BOOK_APPOINTMENT")
        assert stage == Stage.AWAITING_TIME

    def test_booking_time_advances_to_confirmation(self):
        """After time is validated, stage advances to AWAITING_CONFIRMATION."""
        stage = next_stage(Stage.AWAITING_TIME, {"appointment_time": "09:00"}, "BOOK_APPOINTMENT")
        assert stage == Stage.AWAITING_CONFIRMATION

    def test_incremental_reg_missing_field_order(self):
        """get_next_missing_reg_field returns fields in expected order."""
        reg = {}
        fields_collected = []
        for _ in REG_FIELD_ORDER:
            f = get_next_missing_reg_field(reg)
            if f is None:
                break
            fields_collected.append(f)
            reg[f] = "dummy_value"
        assert fields_collected == REG_FIELD_ORDER

    def test_incremental_reg_prompt_acknowledges_capture(self):
        """build_incremental_reg_prompt includes acknowledgement of captured field."""
        prompt = build_incremental_reg_prompt(
            reg_fields={"first_name": "Arokiya"},
            just_captured="first_name",
            just_value="Arokiya",
        )
        assert "Arokiya" in prompt
        assert "date of birth" in prompt.lower()

    def test_intent_switch_clears_booking_entities(self):
        """Switching from BOOK_APPOINTMENT to CANCEL_APPOINTMENT clears stale booking state."""
        state = {
            "entities": {
                "patient_id": 1,
                "doctor_id": 5,
                "department_id": 2,
                "appointment_date": "2026-09-10",
                "appointment_time": "09:00",
                "reason": "fever",
                "symptoms": ["fever"],
                "booking_id": None,
            },
            "department_name": "General Medicine",
            "booking_stage": "AWAITING_TIME",
            "patient_id": 1,
        }
        result = merge_state(
            state,
            validated_fields={},  # no new entities
            intent="CANCEL_APPOINTMENT",
            previous_intent="BOOK_APPOINTMENT",
        )
        # Booking-specific fields cleared
        assert result["entities"]["appointment_date"] is None
        assert result["entities"]["appointment_time"] is None
        # Patient identity preserved
        assert result["patient_id"] == 1


# ---------------------------------------------------------------------------
# 4. End-to-end regression tests (mock LLM output — no actual LLM call)
# ---------------------------------------------------------------------------
class TestRegressionCases:
    """
    All 5 confirmed failure cases as regression tests.
    These test the full grounding + stage merge pipeline with mock LLM output.
    No DB calls required.
    """

    def _pipeline(self, user_message: str, mock_llm_output: dict,
                  state: dict = None, pending_stage: str = None) -> dict:
        """
        Simulate the core pipeline:
        1. grounding_validator validates mock LLM output
        2. conversation_stages.merge_state writes to state
        Returns the merged state.
        """
        if state is None:
            state = {"entities": {
                "patient_id": None, "doctor_id": None, "department_id": None,
                "appointment_date": None, "appointment_time": None,
                "booking_id": None, "reason": None, "symptoms": []
            }}
        result = validate_extraction(
            user_message=user_message,
            conversation_state=state,
            extracted_fields=mock_llm_output,
            pending_stage=pending_stage or state.get("booking_stage"),
        )
        cleaned = result["cleaned"]
        intent = mock_llm_output.get("intent", "GREETING")
        merge_state(state, cleaned, intent=intent)
        return state

    # --- Regression 1: Greeting after booking → no medical fields in response ---
    def test_regression_1_greeting_resets_context(self):
        """
        Patient sends 'Good Morning' after a full booking session.
        State should be reset: no appointment_date, no reason, etc.
        """
        prior_state = {
            "patient_id": 42,
            "entities": {
                "patient_id": 42,
                "doctor_id": 7,
                "department_id": 3,
                "appointment_date": "2026-09-10",
                "appointment_time": "09:00",
                "reason": "fever",
                "symptoms": ["fever"],
                "booking_id": None,
            },
            "department_name": "General Medicine",
            "booking_stage": "AWAITING_CONFIRMATION",
            "confirmation_pending": True,
        }
        # LLM correctly returns GREETING with all nulls
        mock_llm = {
            "intent": "GREETING",
            "confidence": 0.99,
            "medical_reason": None, "reason_raw_quote": None,
            "appointment_date": None, "date_raw_quote": None,
            "appointment_time": None, "time_raw_quote": None,
            "doctor_name": None, "doctor_raw_quote": None,
            "patient_name": None, "patient_name_raw_quote": None,
        }
        final_state = self._pipeline("Good Morning", mock_llm, state=prior_state)
        assert final_state["entities"]["appointment_date"] is None
        assert final_state["entities"]["reason"] is None
        assert final_state["entities"]["doctor_id"] is None

    # --- Regression 2: Confirmation card must not show doctor name in reason ---
    def test_regression_2_doctor_not_in_reason(self):
        """
        LLM outputs medical_reason='Dr. Sharma' (cross-field contamination).
        After grounding_validator, reason must be null.
        """
        mock_llm = {
            "intent": "BOOK_APPOINTMENT",
            "confidence": 0.9,
            "medical_reason": "Dr. Sharma",
            "reason_raw_quote": "Dr. Sharma",
            "doctor_name": "Dr. Sharma",
            "doctor_raw_quote": "Dr. Sharma",
            "appointment_date": None, "date_raw_quote": None,
            "appointment_time": None, "time_raw_quote": None,
            "patient_name": None, "patient_name_raw_quote": None,
        }
        state = self._pipeline(
            "I want to see Dr. Sharma",
            mock_llm,
        )
        assert state["entities"]["reason"] is None, (
            "Doctor name must not appear in reason field"
        )

    # --- Regression 3: Incremental registration - bot asks one field at a time ---
    def test_regression_3_incremental_registration(self):
        """
        Patient starts registration. The stage machine must track which field
        is missing and return only the next question.
        """
        reg_fields = {}
        # Step 1: nothing filled yet → ask for name
        first_missing = get_next_missing_reg_field(reg_fields)
        assert first_missing == "first_name"

        # Step 2: name collected → ask for DOB
        reg_fields["first_name"] = "Arokiya Gilbrit"
        second_missing = get_next_missing_reg_field(reg_fields)
        assert second_missing == "date_of_birth"

        # Step 3: DOB collected → ask for gender
        reg_fields["date_of_birth"] = "2004-09-08"
        third_missing = get_next_missing_reg_field(reg_fields)
        assert third_missing == "gender"

        # All filled → None
        for f in REG_FIELD_ORDER:
            reg_fields[f] = "value"
        assert get_next_missing_reg_field(reg_fields) is None

    # --- Regression 4: Garbage name rejected in registration ---
    def test_regression_4_garbage_name_rejected(self):
        """
        Patient sends a garbled string 'shs' as their name.
        grounding_validator must reject it.
        """
        mock_llm = {
            "patient_name": "shs",
            "patient_name_raw_quote": "shs",
            "intent": "PATIENT_REGISTRATION",
        }
        result = validate_extraction(
            user_message="shs",
            conversation_state={},
            extracted_fields=mock_llm,
            pending_stage="REGISTERING_NAME",
        )
        assert result["cleaned"]["patient_name"] is None

    # --- Regression 5: Hallucinated doctor + date on "hair problems" message ---
    def test_regression_5_hallucinated_entities_rejected(self):
        """
        Patient sends 'I have hair problems for that which doctor is available'.
        LLM hallucinates a doctor name and a specific date.
        Both must be null after grounding validation (no quotes in message).
        """
        msg = "I have hair problems for that which doctor is available"
        mock_llm = {
            "intent": "DOCTOR_AVAILABILITY",
            "confidence": 0.85,
            "medical_reason": "hair problems",
            "reason_raw_quote": "hair problems",
            "department": "Dermatology",
            "doctor_name": "Dr. Raju Sharma",     # hallucinated
            "doctor_raw_quote": None,              # no quote
            "appointment_date": "2026-09-08",     # hallucinated
            "date_raw_quote": None,               # no quote
            "appointment_time": None,
            "time_raw_quote": None,
            "patient_name": None,
            "patient_name_raw_quote": None,
        }
        result = validate_extraction(
            user_message=msg,
            conversation_state={},
            extracted_fields=mock_llm,
        )
        cleaned = result["cleaned"]
        assert cleaned["doctor_name"] is None, "Hallucinated doctor must be rejected"
        assert cleaned["appointment_date"] is None, "Hallucinated date must be rejected"
        assert cleaned["medical_reason"] == "hair problems", "Valid reason must pass"

    # --- Regression 5b: Split message "5" + "PM" merged to "5 PM" ---
    def test_regression_5b_split_message_merged(self):
        """
        Patient sends '5' in one message and 'PM' in the next.
        MessageAggregator must merge them to '5 PM'.
        """
        agg = MessageAggregator(window_seconds=60.0)
        agg.add("+919876543210", "5")
        agg.add("+919876543210", "PM")
        merged = agg.flush("+919876543210")
        assert merged == "5 PM", f"Split time message not merged correctly: '{merged}'"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Running regression tests directly (not via pytest)...")
    
    # Run all tests manually for quick validation
    gv = TestGroundingValidator()
    gv.test_greeting_nulls_medical_fields()
    print("  [OK]  test_greeting_nulls_medical_fields")
    gv.test_doctor_name_not_in_reason()
    print("  [OK]  test_doctor_name_not_in_reason")
    gv.test_implausible_name_rejected()
    print("  [OK]  test_implausible_name_rejected")
    gv.test_intent_label_as_reason_rejected()
    print("  [OK]  test_intent_label_as_reason_rejected")
    gv.test_hallucinated_date_without_quote_rejected()
    print("  [OK]  test_hallucinated_date_without_quote_rejected")
    gv.test_stale_date_carryover_rejected()
    print("  [OK]  test_stale_date_carryover_rejected")
    gv.test_valid_date_with_quote_passes()
    print("  [OK]  test_valid_date_with_quote_passes")
    gv.test_past_date_rejected()
    print("  [OK]  test_past_date_rejected")
    gv.test_awaiting_date_stage_allows_answer()
    print("  [OK]  test_awaiting_date_stage_allows_answer")

    ma = TestMessageAggregator()
    ma.test_single_message_buffered()
    print("  [OK]  test_single_message_buffered")
    ma.test_split_messages_merged_on_flush()
    print("  [OK]  test_split_messages_merged_on_flush")
    ma.test_split_messages_time_window()
    print("  [OK]  test_split_messages_time_window")
    ma.test_different_senders_independent()
    print("  [OK]  test_different_senders_independent")
    ma.test_separator_digits_and_unit()
    print("  [OK]  test_separator_digits_and_unit")
    ma.test_flush_immediate()
    print("  [OK]  test_flush_immediate")

    cs = TestConversationStages()
    cs.test_greeting_clears_booking_context()
    print("  [OK]  test_greeting_clears_booking_context")
    cs.test_registration_stage_transitions()
    print("  [OK]  test_registration_stage_transitions")
    cs.test_booking_date_advances_to_time()
    print("  [OK]  test_booking_date_advances_to_time")
    cs.test_booking_time_advances_to_confirmation()
    print("  [OK]  test_booking_time_advances_to_confirmation")
    cs.test_incremental_reg_missing_field_order()
    print("  [OK]  test_incremental_reg_missing_field_order")
    cs.test_incremental_reg_prompt_acknowledges_capture()
    print("  [OK]  test_incremental_reg_prompt_acknowledges_capture")
    cs.test_intent_switch_clears_booking_entities()
    print("  [OK]  test_intent_switch_clears_booking_entities")

    reg = TestRegressionCases()
    reg.test_regression_1_greeting_resets_context()
    print("  [OK]  test_regression_1_greeting_resets_context")
    reg.test_regression_2_doctor_not_in_reason()
    print("  [OK]  test_regression_2_doctor_not_in_reason")
    reg.test_regression_3_incremental_registration()
    print("  [OK]  test_regression_3_incremental_registration")
    reg.test_regression_4_garbage_name_rejected()
    print("  [OK]  test_regression_4_garbage_name_rejected")
    reg.test_regression_5_hallucinated_entities_rejected()
    print("  [OK]  test_regression_5_hallucinated_entities_rejected")
    reg.test_regression_5b_split_message_merged()
    print("  [OK]  test_regression_5b_split_message_merged")

    print("\n[ALL PASS] All regression and unit tests PASSED.")
