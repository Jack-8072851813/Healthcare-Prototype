"""
conversation_stages.py
======================
Explicit conversation state machine for the Meridian Hospital AI Patient Desk.

This module defines:
  1. Stage enum -- every named stage in the booking/registration flow
  2. FIELD_CLEAR_RULES -- which fields are cleared vs. carried-forward per stage transition
  3. STAGE_TRANSITIONS -- which stage to enter given (current_stage, validated_fields_present)
  4. merge_state() -- the authoritative function for updating conversation state

DESIGN PRINCIPLES
-----------------
- A field is ONLY written when it answers the question implied by the current stage.
- A bare greeting / off-topic message resets booking context but preserves patient identity.
- State transitions are driven by which validated fields are present, not raw LLM output.
- All state writes go through merge_state() -- no inline ad-hoc writes in agent_service.py.

CLEAR-VS-CARRY RULES (documented below per field group)
---------------------------------------------------------
Preserved across ALL transitions:
  - patient_id, contact_patient_id, phone, whatsapp_number, language
  - patient_info (name, DOB etc. from DB)

Cleared on GREETING (no extracted entities):
  - entities.condition / reason
  - entities.department_id
  - entities.doctor_id
  - entities.appointment_date
  - entities.appointment_time
  - department_name, doctor_name, specialty
  - booking_stage, previous_question, confirmation_pending
  - change_pending, change_pending_field
  - missing_information

Cleared on intent switch (e.g. BOOK -> CANCEL):
  - All booking-specific fields above EXCEPT patient_id

Carried forward across turns in the SAME booking flow:
  - department, reason/condition once confirmed
  - patient_id always

Never overwritten unless user explicitly provides new value:
  - registration_fields (incremental fill)
"""

from enum import Enum
from typing import Optional, Dict, Any, List


# ---------------------------------------------------------------------------
# Stage Enum
# ---------------------------------------------------------------------------
class Stage(str, Enum):
    # Session start
    NEW                      = "NEW"
    GREETING                 = "GREETING"

    # Booking flow
    AWAITING_REASON          = "AWAITING_REASON"
    AWAITING_DEPARTMENT_CONFIRM = "AWAITING_DEPARTMENT_CONFIRM"
    AWAITING_DOCTOR          = "AWAITING_DOCTOR"
    AWAITING_DATE            = "AWAITING_DATE"
    AWAITING_TIME            = "AWAITING_TIME"
    AWAITING_CONFIRMATION    = "AWAITING_CONFIRMATION"

    # Registration flow (one field at a time)
    REGISTERING_NAME         = "REGISTERING_NAME"
    REGISTERING_DOB          = "REGISTERING_DOB"
    REGISTERING_GENDER       = "REGISTERING_GENDER"
    REGISTERING_PHONE        = "REGISTERING_PHONE"
    REGISTERING_REASON       = "REGISTERING_REASON"
    REGISTRATION_CONFIRMING  = "REGISTRATION_CONFIRMING"

    # Cancel / reschedule
    AWAITING_CANCEL_CONFIRM  = "AWAITING_CANCEL_CONFIRM"
    AWAITING_RESCHEDULE_DATE = "AWAITING_RESCHEDULE_DATE"
    AWAITING_RESCHEDULE_TIME = "AWAITING_RESCHEDULE_TIME"

    # Terminal
    COMPLETE                 = "COMPLETE"
    UNKNOWN                  = "UNKNOWN"


# ---------------------------------------------------------------------------
# Fields that are ALWAYS preserved across any stage transition
# ---------------------------------------------------------------------------
ALWAYS_PRESERVE = frozenset({
    "patient_id",
    "contact_patient_id",
    "phone",
    "language",
    "patient_info",
    "conversation_id",
})

# ---------------------------------------------------------------------------
# Fields that are ALWAYS cleared on a GREETING with no extracted entities
# ---------------------------------------------------------------------------
GREETING_CLEAR_FIELDS = frozenset({
    # state-level
    "department_name",
    "doctor_name",
    "specialty",
    "booking_stage",
    "previous_question",
    "confirmation_pending",
    "confirmation_details",
    "change_pending",
    "change_pending_field",
    "missing_information",
    "appointment_for",    # but preserve if mid-dependent flow? no -- greeting resets
    "patient_relationship",
    "actual_patient_id",
    "actual_patient_name",
    "dependent_collection_stage",
    "pending_time_digit",
    "last_action",
    "interactive_buttons",
})

# entity sub-fields cleared on greeting
GREETING_CLEAR_ENTITY_FIELDS = frozenset({
    "doctor_id",
    "department_id",
    "appointment_date",
    "appointment_time",
    "booking_id",
    "reason",
    "symptoms",
})

# ---------------------------------------------------------------------------
# Fields cleared on ANY intent switch (between booking / cancel / reschedule)
# ---------------------------------------------------------------------------
INTENT_SWITCH_CLEAR_FIELDS = frozenset({
    "department_name",
    "doctor_name",
    "specialty",
    "booking_stage",
    "previous_question",
    "confirmation_pending",
    "confirmation_details",
    "change_pending",
    "change_pending_field",
    "missing_information",
    "pending_time_digit",
})

INTENT_SWITCH_CLEAR_ENTITY_FIELDS = frozenset({
    "doctor_id",
    "department_id",
    "appointment_date",
    "appointment_time",
    "booking_id",
    "reason",
})

# Intent pairs that trigger a full clear
INTENT_SWITCH_PAIRS = frozenset({
    ("BOOK_APPOINTMENT",       "CANCEL_APPOINTMENT"),
    ("BOOK_APPOINTMENT",       "RESCHEDULE_APPOINTMENT"),
    ("CANCEL_APPOINTMENT",     "BOOK_APPOINTMENT"),
    ("CANCEL_APPOINTMENT",     "RESCHEDULE_APPOINTMENT"),
    ("CANCEL_APPOINTMENT",     "DOCTOR_AVAILABILITY"),
    ("RESCHEDULE_APPOINTMENT", "BOOK_APPOINTMENT"),
    ("RESCHEDULE_APPOINTMENT", "CANCEL_APPOINTMENT"),
    ("RESCHEDULE_APPOINTMENT", "DOCTOR_AVAILABILITY"),
    ("REGISTER_PATIENT",       "BOOK_APPOINTMENT"),
    ("IDENTIFY_PATIENT",       "BOOK_APPOINTMENT"),
    ("GREETING",               "DOCTOR_AVAILABILITY"),
})

# ---------------------------------------------------------------------------
# Stage transition table
# key: current_stage
# value: dict mapping "condition" -> next_stage
# Conditions are evaluated in order; first match wins.
# ---------------------------------------------------------------------------
# (Implemented as explicit function below for clarity.)

def next_stage(current: Stage, validated_fields: dict, intent: str) -> Stage:
    """
    Determine the next conversation stage given the current stage,
    the set of validated fields present after this turn, and the intent.

    Parameters
    ----------
    current : Stage
    validated_fields : dict  -- output of grounding_validator (non-null fields only)
    intent : str

    Returns
    -------
    Stage -- the stage to enter next
    """
    has = lambda f: bool(validated_fields.get(f))

    # Registration flow
    if current == Stage.REGISTERING_NAME:
        return Stage.REGISTERING_DOB if has("patient_name") else Stage.REGISTERING_NAME
    if current == Stage.REGISTERING_DOB:
        return Stage.REGISTERING_GENDER if has("date_of_birth") else Stage.REGISTERING_DOB
    if current == Stage.REGISTERING_GENDER:
        return Stage.REGISTERING_PHONE if has("gender") else Stage.REGISTERING_GENDER
    if current == Stage.REGISTERING_PHONE:
        return Stage.REGISTERING_REASON if has("phone") else Stage.REGISTERING_PHONE
    if current == Stage.REGISTERING_REASON:
        return Stage.REGISTRATION_CONFIRMING if has("reason") else Stage.REGISTERING_REASON
    if current == Stage.REGISTRATION_CONFIRMING:
        return Stage.COMPLETE if has("confirmed") else Stage.REGISTRATION_CONFIRMING

    # Booking flow
    if current in (Stage.NEW, Stage.GREETING):
        if intent == "BOOK_APPOINTMENT":
            if has("condition") or has("department"):
                return Stage.AWAITING_DATE
            return Stage.AWAITING_REASON
        if intent == "REGISTER_PATIENT":
            return Stage.REGISTERING_NAME

    if current == Stage.AWAITING_REASON:
        if has("condition") or has("department"):
            return Stage.AWAITING_DATE
        return Stage.AWAITING_REASON

    if current == Stage.AWAITING_DATE:
        if has("appointment_date"):
            return Stage.AWAITING_TIME
        return Stage.AWAITING_DATE

    if current == Stage.AWAITING_TIME:
        if has("appointment_time"):
            return Stage.AWAITING_CONFIRMATION
        return Stage.AWAITING_TIME

    if current == Stage.AWAITING_CONFIRMATION:
        if has("confirmed"):
            return Stage.COMPLETE
        return Stage.AWAITING_CONFIRMATION

    # Reschedule / cancel
    if current == Stage.AWAITING_RESCHEDULE_DATE:
        if has("appointment_date"):
            return Stage.AWAITING_RESCHEDULE_TIME
        return Stage.AWAITING_RESCHEDULE_DATE
    if current == Stage.AWAITING_RESCHEDULE_TIME:
        if has("appointment_time"):
            return Stage.AWAITING_CANCEL_CONFIRM
        return Stage.AWAITING_RESCHEDULE_TIME

    return current  # no transition


# ---------------------------------------------------------------------------
# Field write rules per stage
# Only write a field if it answers the implied question of the current stage.
# ---------------------------------------------------------------------------
STAGE_ACCEPTS_FIELDS: Dict[Stage, List[str]] = {
    Stage.AWAITING_REASON:           ["condition", "department"],
    Stage.AWAITING_DEPARTMENT_CONFIRM: ["department", "condition"],
    Stage.AWAITING_DATE:             ["appointment_date"],
    Stage.AWAITING_TIME:             ["appointment_time"],
    Stage.AWAITING_CONFIRMATION:     ["confirmed"],
    Stage.REGISTERING_NAME:          ["patient_name"],
    Stage.REGISTERING_DOB:           ["date_of_birth"],
    Stage.REGISTERING_GENDER:        ["gender"],
    Stage.REGISTERING_PHONE:         ["phone"],
    Stage.REGISTERING_REASON:        ["reason"],
    Stage.REGISTRATION_CONFIRMING:   ["confirmed"],
    Stage.AWAITING_RESCHEDULE_DATE:  ["appointment_date"],
    Stage.AWAITING_RESCHEDULE_TIME:  ["appointment_time"],
    Stage.AWAITING_CANCEL_CONFIRM:   ["confirmed"],
}

# These fields are ALWAYS accepted regardless of stage
# (because they add new information without overwriting context)
ALWAYS_ACCEPTED_FIELDS = frozenset({
    "patient_name",   # only if not already set
    "doctor_name",    # only if patient explicitly requested
    "language",
    "booking_for",
    "patient_relationship",
    "condition",
    "department",
    "reason",
    "symptoms",
})


# ---------------------------------------------------------------------------
# merge_state() -- the authoritative state-write function
# ---------------------------------------------------------------------------
def merge_state(
    state: dict,
    validated_fields: dict,
    intent: str,
    previous_intent: str = None,
    log_prefix: str = "[STATE_MERGE]",
) -> dict:
    """
    Apply validated_fields to state according to stage lifecycle rules.

    Parameters
    ----------
    state : dict          -- current conversation state (mutated in-place AND returned)
    validated_fields : dict -- output of grounding_validator (only non-null, validated values)
    intent : str          -- the detected intent for this turn
    previous_intent : str -- the intent from the previous turn (for switch detection)
    log_prefix : str      -- logging prefix

    Returns
    -------
    dict -- the mutated state (same object as input, returned for chaining)
    """

    def _log(msg: str) -> None:
        print(f"{log_prefix} {msg}")

    if not isinstance(state.get("entities"), dict):
        state["entities"] = {}

    current_stage_raw = state.get("booking_stage") or "GREETING"
    try:
        current_stage = Stage(current_stage_raw)
    except ValueError:
        current_stage = Stage.GREETING

    # ------------------------------------------------------------------
    # 1. Handle GREETING -- always clear booking context
    # ------------------------------------------------------------------
    is_greeting = intent == "GREETING"
    no_medical_entities = not any(
        validated_fields.get(f)
        for f in ("condition", "department", "appointment_date", "appointment_time",
                  "doctor_name", "reason")
    )

    if is_greeting and no_medical_entities:
        _log("GREETING with no entities -- clearing booking context")
        for field in GREETING_CLEAR_FIELDS:
            if field in state:
                state[field] = [] if isinstance(state[field], list) else (
                    False if isinstance(state[field], bool) else None
                )
        for field in GREETING_CLEAR_ENTITY_FIELDS:
            state["entities"][field] = [] if field == "symptoms" else None
        state["booking_stage"] = Stage.GREETING.value
        return state

    # ------------------------------------------------------------------
    # 2. Handle intent switch -- clear stale cross-intent entities
    # ------------------------------------------------------------------
    if previous_intent and (previous_intent, intent) in INTENT_SWITCH_PAIRS:
        _log(f"Intent switch {previous_intent}->{intent} -- clearing stale booking fields")
        for field in INTENT_SWITCH_CLEAR_FIELDS:
            if field in state:
                state[field] = [] if isinstance(state[field], list) else (
                    False if isinstance(state[field], bool) else None
                )
        for field in INTENT_SWITCH_CLEAR_ENTITY_FIELDS:
            state["entities"][field] = None

    # ------------------------------------------------------------------
    # 3. Write validated fields according to stage rules
    # ------------------------------------------------------------------
    accepted_for_stage = set(STAGE_ACCEPTS_FIELDS.get(current_stage, []))

    # For stages not yet in a strict collection phase, accept all fields
    permissive_stages = {Stage.GREETING, Stage.NEW, Stage.UNKNOWN}
    permissive = current_stage in permissive_stages

    for field, value in validated_fields.items():
        if value is None:
            continue  # grounding_validator nulled it -- skip

        if field in ALWAYS_PRESERVE:
            continue  # identity fields handled elsewhere

        if field in ALWAYS_ACCEPTED_FIELDS:
            _accept_field(state, field, value, _log, permissive=True)
            continue

        if permissive or field in accepted_for_stage:
            _accept_field(state, field, value, _log, permissive=permissive)
        else:
            _log(f"  SKIP {field}={value!r} (not accepted at stage {current_stage.value})")

    # ------------------------------------------------------------------
    # 4. Advance stage
    # ------------------------------------------------------------------
    new_stage = next_stage(current_stage, validated_fields, intent)
    if new_stage != current_stage:
        _log(f"Stage transition: {current_stage.value} -> {new_stage.value}")
        state["booking_stage"] = new_stage.value

    return state


def _accept_field(state: dict, field: str, value: Any, log_fn, permissive: bool = False) -> None:
    """Write a single validated field into the appropriate state location."""

    # Entity sub-fields
    ENTITY_FIELDS = {
        "appointment_date": "appointment_date",
        "appointment_time": "appointment_time",
        "doctor_id":        "doctor_id",
        "department_id":    "department_id",
        "condition":        "reason",     # condition -> stored as reason in entities
        "reason":           "reason",
        "symptoms":         "symptoms",
        "booking_id":       "booking_id",
    }
    # State-level fields
    STATE_FIELDS = {
        "department":           "department_name",
        "department_name":      "department_name",
        "doctor_name":          "doctor_name",
        "patient_name":         "full_name",
        "language":             "language",
        "booking_for":          "appointment_for",
        "patient_relationship": "patient_relationship",
        "gender":               lambda s, v: _set_reg_field(s, "gender", v),
        "date_of_birth":        lambda s, v: _set_reg_field(s, "date_of_birth", v),
        "phone":                lambda s, v: _set_reg_field(s, "phone", v),
    }

    if field in ENTITY_FIELDS:
        entity_key = ENTITY_FIELDS[field]
        existing = state["entities"].get(entity_key)
        if existing and not permissive:
            log_fn(f"  CARRY  {field} (already set: {existing!r})")
            return
        state["entities"][entity_key] = value
        log_fn(f"  WRITE  entities[{entity_key}] = {value!r}")

    elif field in STATE_FIELDS:
        target = STATE_FIELDS[field]
        if callable(target):
            target(state, value)
        else:
            existing = state.get(target)
            if existing and not permissive:
                log_fn(f"  CARRY  {field} (already set: {existing!r})")
                return
            if target == "department_name" and existing and existing != value:
                log_fn(f"  DEPT CHANGE {existing!r} -> {value!r}: clearing stale doctor selection")
                state["doctor_name"] = None
                if "doctor_id" in state.get("entities", {}):
                    state["entities"]["doctor_id"] = None
            state[target] = value
            log_fn(f"  WRITE  state[{target}] = {value!r}")


def _set_reg_field(state: dict, field: str, value: Any) -> None:
    """Helper: write a field into registration_fields sub-dict."""
    if not isinstance(state.get("registration_fields"), dict):
        state["registration_fields"] = {}
    state["registration_fields"][field] = value


# ---------------------------------------------------------------------------
# Helpers for registration incremental flow
# ---------------------------------------------------------------------------
REG_FIELD_ORDER = [
    "first_name",
    "date_of_birth",
    "gender",
    "phone",
    "reason_for_visit",
]

REG_FIELD_QUESTIONS = {
    "first_name":      "What is the patient's full name?",
    "date_of_birth":   "What is the date of birth? (format: DD Month YYYY, e.g. 08 September 2004)",
    "gender":          "What is the gender? (Male / Female / Other)",
    "phone":           "What is the contact phone number?",
    "reason_for_visit": "What is the reason for the visit? (e.g. fever, hair loss, knee pain)",
}

REG_FIELD_STAGE = {
    "first_name":      Stage.REGISTERING_NAME,
    "date_of_birth":   Stage.REGISTERING_DOB,
    "gender":          Stage.REGISTERING_GENDER,
    "phone":           Stage.REGISTERING_PHONE,
    "reason_for_visit": Stage.REGISTERING_REASON,
}


def get_next_missing_reg_field(reg_fields: dict) -> Optional[str]:
    """Return the first missing registration field name, or None if all filled."""
    for field in REG_FIELD_ORDER:
        val = reg_fields.get(field)
        if not val or str(val).strip() == "":
            return field
    return None


def build_incremental_reg_prompt(
    reg_fields: dict,
    just_captured: str = None,
    just_value: str = None,
) -> str:
    """
    Build a targeted registration prompt acknowledging what was captured
    and asking only for the next missing field.

    Parameters
    ----------
    reg_fields    : current registration_fields dict
    just_captured : field name just captured (for acknowledgement)
    just_value    : value just captured (for acknowledgement)

    Returns
    -------
    str -- message to send to patient
    """
    lines = []

    if just_captured and just_value:
        friendly = just_captured.replace("_", " ").title()
        lines.append(f"✅ Got it! *{friendly}*: {just_value}")

    next_field = get_next_missing_reg_field(reg_fields)
    if next_field is None:
        lines.append(
            "\n📋 Thank you! Here's what I have:\n"
            + _format_reg_summary(reg_fields)
            + "\n\nShall I complete your registration? (Reply *Confirm* or *Edit*)"
        )
    else:
        lines.append("\n" + REG_FIELD_QUESTIONS[next_field])

    return "\n".join(lines).strip()


def _format_reg_summary(reg_fields: dict) -> str:
    labels = {
        "first_name":      "Name",
        "date_of_birth":   "Date of Birth",
        "gender":          "Gender",
        "phone":           "Phone",
        "reason_for_visit": "Reason for Visit",
    }
    lines = []
    for f in REG_FIELD_ORDER:
        val = reg_fields.get(f, "--")
        lines.append(f"• {labels[f]}: {val or '--'}")
    return "\n".join(lines)
