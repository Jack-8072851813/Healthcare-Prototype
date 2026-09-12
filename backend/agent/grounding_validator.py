"""
grounding_validator.py
======================
Pure, side-effect-free grounding and plausibility validator for the
Meridian Hospital AI Patient Desk.

PURPOSE
-------
The LLM extracts entities (condition, doctor, date, time, patient_name, etc.)
from the patient's message.  Without validation, these values flow directly
into conversation state and confirmation cards -- allowing hallucinated values,
cross-field contamination, and implausible data to reach patients.

This module provides a single public function:

    validate_extraction(
        user_message: str,
        conversation_state: dict,
        extracted_fields: dict,
        pending_stage: str = None,
    ) -> dict

It returns a cleaned `extracted_fields` dict where every field is either:
  - Kept as-is (supported by grounding evidence)
  - Nulled out with a logged reason

All logic is pure (no DB calls, no network, no global side effects).

GROUNDING RULES
---------------
1. Every non-null field must have a corresponding *_raw_quote that is a
   substring or paraphrase-traceable match of the CURRENT user message,
   OR the field is answering the exact pending_stage question.

2. condition/reason must NOT:
   - Equal any intent label (e.g. "Book Appointment", "BOOK_APPOINTMENT")
   - Equal or contain a doctor's name (cross-field contamination)
   - Be an empty string after stripping

3. patient_name must be plausible:
   - At least 2 alphabetic characters
   - Not a pure digit string
   - Not a single-character garbled token
   - Not one of the known garbage patterns

4. appointment_date must be >= today (delegated to the existing
   response_validator for the actual date check; here we just propagate nulls
   from raw_quote absence).

5. doctor / doctor_name: only kept if the doctor's name appears literally in
   the current message (no inference from prior turns).

6. Any field whose raw_quote is absent or empty is nulled unless it is the
   direct answer to pending_stage.
"""

import re
import datetime
from typing import Optional, Dict, Any, List, Tuple

# ---------------------------------------------------------------------------
# Intent labels that must NEVER appear in reason/condition
# ---------------------------------------------------------------------------
INTENT_LABELS = frozenset({
    "book appointment", "book_appointment", "booking appointment",
    "cancel appointment", "cancel_appointment", "cancellation",
    "reschedule appointment", "reschedule_appointment", "rescheduling",
    "register patient", "patient registration", "patient_registration",
    "register", "registration", "greeting", "hello", "hi",
    "doctor availability", "doctor_availability", "hospital information",
    "hospital_information", "appointment confirmation", "appointment_confirmation",
    "appointment status", "appointment_status", "unknown", "help",
    "book", "cancel", "reschedule", "new patient", "existing patient",
    "emergency", "escalation", "human escalation",
})

# ---------------------------------------------------------------------------
# Garbled / implausible name patterns
# ---------------------------------------------------------------------------
# A name is implausible if it:
#   - Has fewer than 2 distinct alphabetic characters
#   - Is all digits
#   - Matches known test/garbage strings
GARBAGE_NAME_PATTERNS = [
    re.compile(r"^\d+$"),                     # all digits
    re.compile(r"^[^a-zA-Z]*$"),              # no letters at all
    re.compile(r"^.{1}$"),                    # single char
    re.compile(r"^(test|patient|user|admin|null|none|na|n/a|shs|xxx)$", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def _log(msg: str, log_list: List[str]) -> None:
    full = f"[GROUNDING] {msg}"
    print(full)
    log_list.append(full)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def validate_extraction(
    user_message: str,
    conversation_state: dict,
    extracted_fields: dict,
    pending_stage: Optional[str] = None,
) -> dict:
    """
    Validate and clean LLM-extracted fields before they touch conversation state.

    Parameters
    ----------
    user_message : str
        The raw text the patient sent in THIS turn.
    conversation_state : dict
        Current conversation state (read-only; used to detect stale carryover).
    extracted_fields : dict
        Raw output from llm_intent_router._validate_and_normalise(), extended
        to include *_raw_quote fields.
    pending_stage : str, optional
        The stage the bot is currently waiting on (e.g. "AWAITING_DATE").
        Fields that answer this stage are allowed even without a current-message quote.

    Returns
    -------
    dict with keys:
        "cleaned" : dict  -- same shape as extracted_fields but with bad values nulled
        "grounding_log" : list[str]  -- human-readable reasons for each decision
        "rejected_fields" : list[str]  -- names of fields that were nulled
    """
    cleaned = dict(extracted_fields)  # shallow copy
    grounding_log: List[str] = []
    rejected_fields: List[str] = []

    msg_lower = user_message.lower().strip()

    _log(f"--- Grounding validation START ---", grounding_log)
    _log(f"User message: \"{user_message[:200]}\"", grounding_log)
    _log(f"Pending stage: {pending_stage}", grounding_log)

    # ------------------------------------------------------------------
    # 1. Validate condition / reason / medical_reason
    # ------------------------------------------------------------------
    for field_key in ("condition", "medical_reason", "reason"):
        raw_val = cleaned.get(field_key)
        if not raw_val:
            continue
        val = str(raw_val).strip()
        val_lower = val.lower()
        # Reject button IDs or system command strings as medical reason
        if val_lower.startswith("btn_") or val_lower in ["yes", "no", "confirm", "cancel", "ok", "sure", "today", "tomorrow"]:
            _log(
                f"REJECT {field_key}={val!r} -- equals a button ID or system command",
                grounding_log,
            )
            cleaned[field_key] = None
            rejected_fields.append(field_key)
            continue

        # 1a. Check against intent labels
        if val_lower in INTENT_LABELS:
            _log(
                f"REJECT {field_key}={val!r} -- equals an intent label",
                grounding_log,
            )
            cleaned[field_key] = None
            rejected_fields.append(field_key)
            continue

        # 1b. Check if value equals or contains doctor/department name (cross-contamination guard)
        doctor_name = cleaned.get("doctor_name") or cleaned.get("doctor") or ""
        dept_name = cleaned.get("department_name") or cleaned.get("department") or ""
        has_doc_dept_kw = any(kw in val_lower for kw in [
            "dr.", "dr ", "doctor", "pediatrics", "cardiology", "dermatology",
            "orthopedics", "general medicine", "neurology", "gynecology", "urology", "ent"
        ])
        if (doctor_name and _is_name_match(val_lower, doctor_name.lower())) or (dept_name and _is_name_match(val_lower, dept_name.lower())) or has_doc_dept_kw:
            _log(
                f"REJECT {field_key}={val!r} -- equals or contains doctor/department name",
                grounding_log,
            )
            cleaned[field_key] = None
            rejected_fields.append(field_key)
            continue

        # 1c. Grounding check: quote must trace back to the message
        raw_quote_key = f"reason_raw_quote"
        quote = cleaned.get(raw_quote_key) or ""
        if not _is_grounded(val, quote, msg_lower, pending_stage, "AWAITING_REASON"):
            _log(
                f"REJECT {field_key}={val!r} -- no grounding evidence in current message "
                f"(quote={quote!r})",
                grounding_log,
            )
            cleaned[field_key] = None
            rejected_fields.append(field_key)
            continue

        _log(f"PASS   {field_key}={val!r}", grounding_log)

    # ------------------------------------------------------------------
    # 2. Validate doctor / doctor_name
    # ------------------------------------------------------------------
    for field_key in ("doctor_name", "doctor", "doctor_preference"):
        raw_val = cleaned.get(field_key)
        if not raw_val:
            continue
        val = str(raw_val).strip()

        # Doctor must be explicitly named in the CURRENT message
        doctor_quote = cleaned.get("doctor_raw_quote") or ""
        if not _is_grounded(val, doctor_quote, msg_lower, None, None):
            _log(
                f"REJECT {field_key}={val!r} -- doctor not mentioned in current message",
                grounding_log,
            )
            cleaned[field_key] = None
            if field_key not in rejected_fields:
                rejected_fields.append(field_key)
            continue

        _log(f"PASS   {field_key}={val!r}", grounding_log)

    # ------------------------------------------------------------------
    # 3. Validate appointment_date
    # ------------------------------------------------------------------
    raw_date = cleaned.get("appointment_date")
    if raw_date:
        date_quote = cleaned.get("date_raw_quote") or ""
        if not _is_grounded(raw_date, date_quote, msg_lower, pending_stage, "AWAITING_DATE"):
            _log(
                f"REJECT appointment_date={raw_date!r} -- not grounded in current message",
                grounding_log,
            )
            cleaned["appointment_date"] = None
            rejected_fields.append("appointment_date")
        else:
            # Also reject past dates
            is_past, reason = _check_date_future(raw_date)
            if is_past:
                _log(f"REJECT appointment_date={raw_date!r} -- {reason}", grounding_log)
                cleaned["appointment_date"] = None
                rejected_fields.append("appointment_date")
            else:
                _log(f"PASS   appointment_date={raw_date!r}", grounding_log)

    # ------------------------------------------------------------------
    # 4. Validate appointment_time
    # ------------------------------------------------------------------
    raw_time = cleaned.get("appointment_time")
    if raw_time:
        time_quote = cleaned.get("time_raw_quote") or ""
        if not _is_grounded(raw_time, time_quote, msg_lower, pending_stage, "AWAITING_TIME"):
            _log(
                f"REJECT appointment_time={raw_time!r} -- not grounded in current message",
                grounding_log,
            )
            cleaned["appointment_time"] = None
            rejected_fields.append("appointment_time")
        else:
            _log(f"PASS   appointment_time={raw_time!r}", grounding_log)

    # ------------------------------------------------------------------
    # 5. Validate patient_name
    # ------------------------------------------------------------------
    raw_name = cleaned.get("patient_name")
    if raw_name:
        name_quote = cleaned.get("patient_name_raw_quote") or ""
        plausible, reason = _is_plausible_name(raw_name)
        if not plausible:
            _log(
                f"REJECT patient_name={raw_name!r} -- {reason}",
                grounding_log,
            )
            cleaned["patient_name"] = None
            rejected_fields.append("patient_name")
        elif not _is_grounded(raw_name, name_quote, msg_lower, pending_stage, "REGISTERING_NAME"):
            _log(
                f"REJECT patient_name={raw_name!r} -- not grounded in current message",
                grounding_log,
            )
            cleaned["patient_name"] = None
            rejected_fields.append("patient_name")
        else:
            _log(f"PASS   patient_name={raw_name!r}", grounding_log)

    # ------------------------------------------------------------------
    # 5b. Validate date_of_birth / patient_dob
    # ------------------------------------------------------------------
    for dob_key in ("date_of_birth", "patient_dob"):
        raw_dob = cleaned.get(dob_key)
        if raw_dob:
            val_dob = str(raw_dob).strip()
            import agent.date_normalizer as date_normalizer
            is_valid_dob, norm_dob, err_reason = date_normalizer.validate_dob(val_dob, allow_ambiguous=True)
            if not is_valid_dob or not norm_dob:
                _log(f"REJECT {dob_key}={val_dob!r} -- not a valid date of birth ({err_reason})", grounding_log)
                cleaned[dob_key] = None
                if dob_key not in rejected_fields:
                    rejected_fields.append(dob_key)
            else:
                dob_quote = cleaned.get("dob_raw_quote") or cleaned.get("date_of_birth_raw_quote") or ""
                if not _is_grounded(val_dob, dob_quote, msg_lower, pending_stage, "REGISTERING_DOB") and pending_stage not in ["REGISTERING_DOB", "REGISTERING_NEW_DEPENDENT"]:
                    if not _value_mentioned_in_message(val_dob, msg_lower) and not _value_mentioned_in_message(str(raw_dob), msg_lower):
                        _log(f"REJECT {dob_key}={val_dob!r} -- date of birth not mentioned in current message", grounding_log)
                        cleaned[dob_key] = None
                        if dob_key not in rejected_fields:
                            rejected_fields.append(dob_key)
                    else:
                        cleaned[dob_key] = norm_dob
                        _log(f"PASS   {dob_key}={norm_dob!r}", grounding_log)
                else:
                    cleaned[dob_key] = norm_dob
                    _log(f"PASS   {dob_key}={norm_dob!r}", grounding_log)

    # ------------------------------------------------------------------
    # 5c. Validate gender
    # ------------------------------------------------------------------
    raw_gender = cleaned.get("gender")
    if raw_gender:
        g_clean = str(raw_gender).strip().capitalize()
        if g_clean in ["Male", "Female", "Other"]:
            cleaned["gender"] = g_clean
            _log(f"PASS   gender={g_clean!r}", grounding_log)
        else:
            _log(f"REJECT gender={raw_gender!r} -- invalid gender value", grounding_log)
            cleaned["gender"] = None
            if "gender" not in rejected_fields:
                rejected_fields.append("gender")

    # ------------------------------------------------------------------
    # 6. Validate department (must be a known valid department string)
    # ------------------------------------------------------------------
    raw_dept = cleaned.get("department")
    if raw_dept:
        _log(f"PASS   department={raw_dept!r} (validated by llm_intent_router)", grounding_log)

    # ------------------------------------------------------------------
    # 7. Stale carryover guard -- detect if LLM silently repeated prior state
    # ------------------------------------------------------------------
    state_date = (conversation_state.get("entities") or {}).get("appointment_date")
    state_doctor = conversation_state.get("doctor_name")

    if cleaned.get("appointment_date") and cleaned["appointment_date"] == state_date:
        # Date is same as prior state -- only keep if it was also mentioned now
        date_quote = cleaned.get("date_raw_quote") or ""
        if not _quote_in_message(date_quote, msg_lower) and not _value_mentioned_in_message(
            cleaned["appointment_date"], msg_lower
        ):
            _log(
                f"REJECT appointment_date={cleaned['appointment_date']!r} -- stale carryover "
                f"from previous turn, not re-mentioned",
                grounding_log,
            )
            cleaned["appointment_date"] = None
            if "appointment_date" not in rejected_fields:
                rejected_fields.append("appointment_date")

    if cleaned.get("doctor_name") and cleaned.get("doctor_name") == state_doctor:
        doctor_quote = cleaned.get("doctor_raw_quote") or ""
        if not _quote_in_message(doctor_quote, msg_lower) and not _value_mentioned_in_message(
            cleaned["doctor_name"], msg_lower
        ):
            _log(
                f"REJECT doctor_name={cleaned['doctor_name']!r} -- stale carryover, "
                f"not mentioned in current message",
                grounding_log,
            )
            cleaned["doctor_name"] = None
            if "doctor_name" not in rejected_fields:
                rejected_fields.append("doctor_name")

    # ------------------------------------------------------------------
    # 8. Relationship grounding check -- null out ungrounded dependent relationships in SELF queries
    # ------------------------------------------------------------------
    rel_val = cleaned.get("relationship")
    state_subj = conversation_state.get("appointment_subject") or conversation_state.get("booking_for")
    if rel_val and state_subj == "SELF":
        _dep_grnd_re = re.compile(r"\b(son|daughter|child|kid|boy|girl|father|mother|spouse|wife|husband|brother|sister|sibling|dependent)\b", re.IGNORECASE)
        if not _dep_grnd_re.search(msg_lower) and pending_stage not in ["REGISTERING_NEW_DEPENDENT", "AWAITING_DEPENDENT_SELECTION"]:
            _log(
                f"REJECT relationship={rel_val!r} -- ungrounded dependent relationship in SELF query",
                grounding_log,
            )
            cleaned["relationship"] = None
            cleaned["booking_for"] = "SELF"
            cleaned["appointment_subject"] = "SELF"
            if "relationship" not in rejected_fields:
                rejected_fields.append("relationship")

    # ------------------------------------------------------------------
    # 9. Confirmation validation -- set confirmed=True if affirmative during confirmation_pending
    # ------------------------------------------------------------------
    is_conf_pending = conversation_state.get("confirmation_pending") or pending_stage in ("AWAITING_CONFIRMATION", "CONFIRMATION")
    msg_clean_conf = user_message.lower().strip().rstrip("!.,")
    if is_conf_pending and (msg_clean_conf in ["yes", "yeah", "yep", "sure", "confirm", "btn_confirm_appt", "confirm appointment", "ok", "okay"] or any(w in msg_clean_conf for w in ["confirm", "yes"])):
        cleaned["confirmed"] = True
        _log("PASS   confirmed=True (affirmative confirmation response)", grounding_log)

    _log(f"--- Grounding validation END. Rejected: {rejected_fields} ---", grounding_log)

    return {
        "cleaned": cleaned,
        "grounding_log": grounding_log,
        "rejected_fields": rejected_fields,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_grounded(
    value: str,
    raw_quote: str,
    msg_lower: str,
    pending_stage: Optional[str],
    answer_stage: Optional[str],
) -> bool:
    """
    Returns True if `value` is grounded in the current message.

    A value is grounded if:
    - Its raw_quote is a substring of msg_lower, OR
    - The value itself (lowercased) appears in msg_lower, OR
    - The current pending_stage == answer_stage (user is answering the pending question)
    """
    if pending_stage and answer_stage and pending_stage == answer_stage:
        return True  # user is directly answering the question we asked

    if _quote_in_message(raw_quote, msg_lower):
        return True

    if _value_mentioned_in_message(value, msg_lower):
        return True

    return False


def _quote_in_message(quote: str, msg_lower: str) -> bool:
    """Check if a raw quote (lowercased) appears in the message."""
    if not quote:
        return False
    return quote.lower().strip() in msg_lower


def _value_mentioned_in_message(value: str, msg_lower: str) -> bool:
    """
    Check if a value or any of its significant words appear in the message.
    Uses fuzzy substring matching for short values (dates, times, names).
    """
    if not value:
        return False
    val_lower = str(value).lower().strip()

    # Direct match
    if val_lower in msg_lower:
        return True

    # For dates: check if components appear (e.g. "tomorrow" -> tomorrow)
    # For times: check if digits/periods appear
    RELATIVE_DATE_WORDS = {
        "tomorrow", "today", "monday", "tuesday", "wednesday",
        "thursday", "friday", "saturday", "sunday",
        "morning", "afternoon", "evening", "night",
        "next week", "this week",
    }
    if val_lower in RELATIVE_DATE_WORDS and val_lower in msg_lower:
        return True

    # For HH:MM times: check if the digits appear
    time_match = re.match(r"^(\d{1,2}):(\d{2})$", val_lower)
    if time_match:
        hour = time_match.group(1)
        if hour in msg_lower:
            return True

    # For YYYY-MM-DD dates: check if year or a date component appears
    date_match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", val_lower)
    if date_match:
        day = str(int(date_match.group(3)))
        month_num = int(date_match.group(2))
        MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
                  "jul", "aug", "sep", "oct", "nov", "dec"]
        month_abbr = MONTHS[month_num - 1] if 1 <= month_num <= 12 else ""
        if day in msg_lower or month_abbr in msg_lower:
            return True

    # For multi-word values: check if any significant word (>3 chars) is in msg
    words = [w for w in val_lower.split() if len(w) > 3]
    if words and any(w in msg_lower for w in words):
        return True

    return False


def _is_name_match(a: str, b: str) -> bool:
    """Returns True if name 'a' and 'b' are substantially the same."""
    # Normalize and compare
    a_clean = re.sub(r"\bdr\.?\s*", "", a).strip()
    b_clean = re.sub(r"\bdr\.?\s*", "", b).strip()
    if not a_clean or not b_clean:
        return False
    # Exact or substring
    return a_clean == b_clean or a_clean in b_clean or b_clean in a_clean


def _is_plausible_name(name: str) -> Tuple[bool, str]:
    """
    Returns (is_plausible: bool, reason: str).
    A name is plausible if it has at least 2 alphabetic characters and
    doesn't match known garbage patterns.
    """
    if not name or not name.strip():
        return False, "empty name"

    name_stripped = name.strip()

    # Check garbage patterns
    for pattern in GARBAGE_NAME_PATTERNS:
        if pattern.match(name_stripped):
            return False, f"matches garbage pattern: {pattern.pattern}"

    # Must have at least 2 alphabetic characters total
    alpha_chars = [c for c in name_stripped if c.isalpha()]
    if len(alpha_chars) < 2:
        return False, f"fewer than 2 alphabetic characters ({len(alpha_chars)} found)"

    # Must not be purely numeric (already covered but belt+suspenders)
    if name_stripped.isdigit():
        return False, "all digits"

    # Should have at least one word of length >= 2
    words = name_stripped.split()
    if not any(len(w) >= 2 for w in words):
        return False, "no word of length >= 2"

    return True, "ok"


def _check_date_future(date_str: str) -> Tuple[bool, str]:
    """
    Returns (is_past: bool, reason: str).
    is_past=True means the date is before today and should be rejected.
    """
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        if d < today:
            return True, f"date {date_str} is in the past (today={today})"
        return False, "ok"
    except ValueError:
        return False, "could not parse date (pass through)"
