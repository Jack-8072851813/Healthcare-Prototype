"""
llm_intent_router.py
====================
LLM-Based Patient Intent Router Agent for Meridian Hospital AI Patient Desk.

Architecture:
  WhatsApp Webhook / Input Message
  -> Conversation Manager (agent_service.py)
  -> LLM Patient Intent Router  [THIS MODULE]  ← current_state + conversation_history
  -> Structured JSON Intent (strict schema)
  -> Existing Specialized Agents (BOOK, CANCEL, RESCHEDULE, ...)
  -> Database / Business Logic  (deterministic — LLM never writes DB)
  -> WhatsApp Response

Responsibilities:
  - Natural language understanding (NLU) as PRIMARY router
  - Context-aware interpretation of short/follow-up messages
    ("tomorrow", "5 PM", "yes", "cancel it", "for my son")
  - Semantic symptom → department mapping
    (hair loss → Dermatology; fever → General Medicine)
  - Multi-field entity extraction in a single pass
  - DOB ambiguity detection
  - Clarification question generation when intent/data is ambiguous
  - Strict structured JSON output
  - Comprehensive [LLM_ROUTER] structured audit logging
  - Graceful fallback to rule-based intent_router.route_patient_message()

CRITICAL RULES:
  - LLM must NOT select or invent a doctor.  Department only.
  - LLM must NOT modify the database.  Extraction/classification only.
  - All extracted information must be validated before any DB insertion.
  - Low-confidence or ambiguous → return needs_clarification: true.
"""

import os
import sys
import json
import re
import datetime
import traceback
import requests
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

# ---------------------------------------------------------------------------
# Lazy imports (avoid circular deps — agent_service imports us)
# ---------------------------------------------------------------------------
import agent.date_normalizer as date_normalizer
import agent.entity_extractor as entity_extractor
import agent.language_service as language_service
import db_config

# ---------------------------------------------------------------------------
# LLM provider config  (same env-vars as llm_service.py)
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
LLM_MODEL    = os.getenv("LLM_MODEL", "gemini-2.0-flash")
LLM_API_KEY  = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "")

# ---------------------------------------------------------------------------
# Supported Intents (must align with DB check constraints via intent_detector)
# ---------------------------------------------------------------------------
SUPPORTED_INTENTS = {
    "GREETING",
    "PATIENT_REGISTRATION",
    "NEW_PATIENT_REGISTRATION",
    "EXISTING_PATIENT",
    "PATIENT_DETAILS",
    "PATIENT_PROFILE",
    "PATIENT_ID",
    "BOOK_APPOINTMENT",
    "DOCTOR_AVAILABILITY",
    "CANCEL_APPOINTMENT",
    "RESCHEDULE_APPOINTMENT",
    "HOSPITAL_INFORMATION",
    "APPOINTMENT_CONFIRMATION",
    "APPOINTMENT_STATUS",
    "APPOINTMENT_DETAILS",
    "PATIENT_DETAILS_UPDATE",
    "DEPENDENT_BOOKING",
    "CHILD_APPOINTMENT",
    "SYMPTOM_DOCTOR_RECOMMENDATION",
    "GENERAL_MEDICAL_QUERY",
    "CONFIRM_APPOINTMENT",
    "CHANGE_APPOINTMENT_DETAILS",
    "PRE_ADMISSION",
    "EMERGENCY",
    "HUMAN_ESCALATION",
    "THANK_YOU",
    "HELP",
    "UNKNOWN",
    "CLARIFICATION_REQUIRED",
}

# Map LLM-returned intents → canonical router intents (backwards compat)
INTENT_NORMALISATION_MAP = {
    "CHECK_DOCTOR_AVAILABILITY":    "DOCTOR_AVAILABILITY",
    "REGISTER_PATIENT":             "PATIENT_REGISTRATION",
    "NEW_PATIENT_REGISTRATION":     "PATIENT_REGISTRATION",
    "IDENTIFY_PATIENT":             "PATIENT_REGISTRATION",
    "DEPENDENT_PATIENT":            "DEPENDENT_BOOKING",
    "CHILD_APPOINTMENT":            "DEPENDENT_BOOKING",
    "PRE_ADMISSION":                "PRE_ADMISSION",
    "DEPARTMENT_INFORMATION":       "HOSPITAL_INFORMATION",
    "HUMAN_ESCALATION":             "HUMAN_ESCALATION",
    "SYMPTOM_GUIDANCE":             "BOOK_APPOINTMENT",
    "SYMPTOM_DOCTOR_RECOMMENDATION": "BOOK_APPOINTMENT",
    "GENERAL_MEDICAL_QUERY":        "GENERAL_MEDICAL_QUERY",
    "MEDICAL_QUERY":                "GENERAL_MEDICAL_QUERY",
    "EMERGENCY_GUIDANCE":           "EMERGENCY",
    "EMERGENCY":                    "EMERGENCY",
    "APPOINTMENT_TIME":             "BOOK_APPOINTMENT",
    "APPOINTMENT_DATE":             "BOOK_APPOINTMENT",
    "CONFIRM_APPOINTMENT":          "APPOINTMENT_CONFIRMATION",
    "CHANGE_APPOINTMENT_DETAILS":   "RESCHEDULE_APPOINTMENT",
    "APPOINTMENT_DETAILS":          "APPOINTMENT_STATUS",
    "MY_APPOINTMENTS":              "APPOINTMENT_STATUS",
    "SHOW_MY_APPOINTMENTS":         "APPOINTMENT_STATUS",
    "SHOW_APPOINTMENTS":            "APPOINTMENT_STATUS",
    "VIEW_APPOINTMENTS":            "APPOINTMENT_STATUS",
    "CHECK_APPOINTMENT":            "APPOINTMENT_STATUS",
    "APPOINTMENT_QUERY":            "APPOINTMENT_STATUS",
    "MY_BOOKINGS":                  "APPOINTMENT_STATUS",
    "SHOW_BOOKING":                 "APPOINTMENT_STATUS",
    "DEPENDENT_APPOINTMENT":        "APPOINTMENT_STATUS",
    "SON_APPOINTMENT":              "APPOINTMENT_STATUS",
    "DAUGHTER_APPOINTMENT":         "APPOINTMENT_STATUS",
    "CHILD_APPOINTMENTS":           "APPOINTMENT_STATUS",
    "THANK_YOU":                    "THANK_YOU",
    "GOODBYE":                      "GREETING",
    "HELP":                         "HELP",
    "LANGUAGE_CHANGE":              "GREETING",
    "POST_BOOKING":                 "APPOINTMENT_STATUS",
    "PATIENT_PROFILE":              "PATIENT_DETAILS",
    "PATIENT_ID":                   "PATIENT_DETAILS",
    "MY_PATIENT_ID":                "PATIENT_DETAILS",
    "SHOW_PROFILE":                 "PATIENT_DETAILS",
    "PATIENT_INFORMATION":          "PATIENT_DETAILS",
}

# ---------------------------------------------------------------------------
# Departments that must match the DB department_name column exactly
# ---------------------------------------------------------------------------
VALID_DEPARTMENTS = {
    "General Medicine", "Cardiology", "Pediatrics",
    "Orthopedics", "Dermatology", "ENT", "Gynecology", "Neurology",
}

# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------
def _log(msg: str) -> None:
    """Structured audit log tagged [LLM_ROUTER]."""
    print(f"[LLM_ROUTER] {msg}")


# ---------------------------------------------------------------------------
# IST timestamp helper
# ---------------------------------------------------------------------------
def _get_ist_now() -> datetime.datetime:
    """Returns current datetime in Asia/Kolkata (IST = UTC+5:30)."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    ist_tz  = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return utc_now.astimezone(ist_tz)


def _get_ist_date_str() -> str:
    return _get_ist_now().strftime("%Y-%m-%d")

def _get_ist_datetime_str() -> str:
    return _get_ist_now().strftime("%Y-%m-%d %H:%M")

def _get_ist_weekday() -> str:
    return _get_ist_now().strftime("%A")


# ---------------------------------------------------------------------------
# LLM availability guard
# ---------------------------------------------------------------------------
def is_llm_available() -> bool:
    """Returns True when LLM provider and API key are configured."""
    return bool(LLM_API_KEY and LLM_PROVIDER in {"gemini", "google", "openai", "ollama"})


# ---------------------------------------------------------------------------
# Low-level Gemini call (JSON mode)
# ---------------------------------------------------------------------------
def _call_gemini(prompt: str) -> Optional[str]:
    """
    Calls Gemini REST generateContent endpoint with JSON response mode.
    Returns raw JSON text string or None on failure.
    """
    if not LLM_API_KEY:
        return None

    # Resolve correct Gemini model name for the REST API
    # gemini-2.5-flash → use gemini-2.5-flash (stable endpoint)
    # gemini-2.0-flash → use gemini-2.0-flash
    # others → fall back to gemini-1.5-flash-latest
    model_env = (LLM_MODEL or "").strip()
    if "3.6" in model_env:
        model_name = "gemini-3.6-flash"
    elif "2.5" in model_env:
        model_name = "gemini-2.5-flash"
    elif "2.0" in model_env:
        model_name = "gemini-2.0-flash"
    elif model_env:
        model_name = model_env
    else:
        model_name = "gemini-3.6-flash"

    ca_bundle = os.getenv("REQUESTS_CA_BUNDLE", "")
    verify_ssl = ca_bundle if ca_bundle and os.path.exists(ca_bundle) else True

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.05,
            "responseMimeType": "application/json",
        },
    }

    # Try primary model, then fallback models
    models_to_try = [model_name, "gemini-3.5-flash-lite", "gemini-2.5-flash"]
    seen = set()
    for attempt_model in [m for m in models_to_try if m and not (m in seen or seen.add(m))]:
        attempt_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{attempt_model}:generateContent?key={LLM_API_KEY}"
        )
        try:
            res = requests.post(
                attempt_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=2.0,
                verify=verify_ssl,
            )
            if res.status_code == 404 and attempt_model != "gemini-1.5-flash-latest":
                _log(f"Model {attempt_model} returned 404, trying gemini-1.5-flash-latest")
                continue
            res.raise_for_status()
            data = res.json()
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts:
                    return parts[0].get("text")
            break  # Got a valid response (even empty), no need to retry
        except Exception as exc:
            if "404" in str(exc) and attempt_model != "gemini-1.5-flash-latest":
                _log(f"Model {attempt_model} error ({exc}), trying fallback model")
                continue
            _log(f"Gemini API error: {exc}")
            break

    return None


# ---------------------------------------------------------------------------
# Low-level OpenAI call (JSON mode)
# ---------------------------------------------------------------------------
def _call_openai(prompt: str) -> Optional[str]:
    """Calls OpenAI chat/completions in JSON mode."""
    if not LLM_API_KEY:
        return None

    base_url = LLM_API_BASE or "https://api.openai.com/v1"
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": LLM_MODEL or "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert medical intake assistant for Meridian Hospital. "
                    "Your ONLY job is to classify patient intent and extract structured entities. "
                    "You NEVER select doctors. You NEVER write to any database. "
                    "Always return strict JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.05,
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        _log(f"OpenAI API error: {exc}")

    return None


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------
def _build_prompt(
    message_text: str,
    current_state: dict,
    conversation_history: List[dict],
) -> str:
    """
    Builds the complete structured prompt for the LLM Intent Router.
    Enforces the grounding extraction contract: every non-null entity
    must be accompanied by a *_raw_quote field containing the exact
    substring from the CURRENT user message that supports it.
    """
    now_str       = _get_ist_datetime_str()
    today_str     = _get_ist_date_str()
    weekday_str   = _get_ist_weekday()

    # --- Conversation history (last 6 turns) ---
    history_lines: List[str] = []
    for turn in (conversation_history or [])[-6:]:
        role = "Patient" if turn.get("sender") in {"PATIENT", "patient"} else "Bot"
        text = (turn.get("text") or turn.get("message_text") or "").strip()
        if text:
            history_lines.append(f"{role}: {text}")
    history_ctx = "\n".join(history_lines) if history_lines else "No prior conversation."

    # --- Current state summary ---
    prior_intent    = current_state.get("intent", "UNKNOWN")
    prior_dept      = current_state.get("department_name", "")
    last_bot_msg    = (current_state.get("last_bot_message") or "").strip()
    prev_question   = current_state.get("previous_question", "")
    booking_stage   = current_state.get("booking_stage", "")
    appt_for        = current_state.get("appointment_for", "SELF")
    relationship    = current_state.get("patient_relationship", "")
    if appt_for == "SELF" or current_state.get("appointment_subject") == "SELF" or current_state.get("booking_for") == "SELF":
        relationship = None
        appt_for = "SELF"
    entities        = current_state.get("entities", {})
    known_date      = entities.get("appointment_date", "")
    known_time      = entities.get("appointment_time", "")
    known_dept_id   = entities.get("department_id", "")
    known_doc_id    = entities.get("doctor_id", "")
    missing_info    = current_state.get("missing_information", [])
    confirm_pending = current_state.get("confirmation_pending", False)

    # Resolve doctor name for pronoun resolution ("when he will be available?")
    active_doctor_name = ""
    if known_doc_id:
        try:
            import db_config as _db_cfg
            _conn = _db_cfg.get_db_connection()
            _cur = _conn.cursor()
            try:
                _cur.execute("SELECT first_name, last_name FROM doctors WHERE id = %s;", (known_doc_id,))
                _row = _cur.fetchone()
                if _row:
                    active_doctor_name = f"Dr. {_row[0]} {_row[1] or ''}".strip()
            finally:
                _cur.close()
                _conn.close()
        except Exception:
            pass

    state_summary = json.dumps({
        "prior_intent":        prior_intent,
        "prior_department":    prior_dept,
        "prior_doctor_id":     known_doc_id,
        "active_doctor_name":  active_doctor_name,   # for pronoun resolution (he/him/his)
        "known_date":          known_date,
        "known_time":          known_time,
        "booking_for":         appt_for,
        "relationship":        relationship,
        "missing_fields":      missing_info,
        "confirmation_pending": confirm_pending,
        "previous_question":   prev_question,
        "booking_stage":       booking_stage,
        "last_bot_message":    last_bot_msg,
        "pending_stage":       booking_stage,
    }, ensure_ascii=False)

    tomorrow_str = (_get_ist_now().date() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    prompt = f"""You are the Patient Intent Router for Meridian Hospital's AI Patient Desk.
Your ONLY job is to classify the patient's intent and extract structured entities from their message.

=== GROUNDING CONTRACT — MANDATORY ===
You MUST NOT infer, assume, or invent any field. Every non-null entity you extract
(doctor_name, appointment_date, appointment_time, medical_reason, patient_name)
MUST be accompanied by a *_raw_quote field containing the EXACT substring or
clear paraphrase from the CURRENT user message that supports it.

RULES FOR EACH FIELD:
1. medical_reason / condition:
   - ONLY extract if the patient describes a symptom or medical reason in THIS message.
   - NEVER put a doctor's name, department name, or intent label (e.g. "Book Appointment") into this field.
   - If no symptom is mentioned in THIS message → set medical_reason=null.

2. doctor_name:
   - ONLY if the patient explicitly names a specific doctor in THIS message (e.g. "I want Dr. Arun").
   - NEVER invent, infer, or suggest a doctor name. Department routing only.
   - If not explicitly mentioned → doctor_name=null.

3. appointment_date:
   - ONLY if the patient mentions a date or relative day ("tomorrow", "Friday", "next Monday") in THIS message.
   - Convert relative dates using today={today_str}.
   - If no date in THIS message and pending_stage is AWAITING_DATE, you may interpret a short reply as the date answer.
   - Otherwise → appointment_date=null.

4. appointment_time:
   - ONLY if the patient mentions a time ("5 PM", "morning", "10:30") in THIS message.
   - If pending_stage is AWAITING_TIME, a short reply ("morning", "5", "PM") may be the time answer.
   - Otherwise → appointment_time=null.

5. patient_name:
   - ONLY if the patient explicitly provides their name in THIS message.
   - Must look like a real human name (at least 2 letters, not just digits or garbage).
   - Otherwise → patient_name=null.

6. NEVER carry forward values from history silently — if a prior turn had a date and this turn does not mention it, output null for appointment_date.
   Exception: if pending_stage matches (e.g. AWAITING_DATE, AWAITING_TIME, AWAITING_BOOKING_ID) and this message is a direct answer, you may extract from the answer.
7. If pending_stage is AWAITING_BOOKING_ID, the bot explicitly asked the patient for their booking ID (e.g., APT10001). A short reply or alphanumeric reply is expected to be the booking ID answer. Do NOT reclassify into BOOK_APPOINTMENT or DOCTOR_AVAILABILITY unless the user explicitly requests a different command.

=== END GROUNDING CONTRACT ===

CRITICAL RULES:
1. DO NOT select, suggest, or invent any doctor name. Only extract the appropriate medical department.
2. DO NOT write to any database. You are a classification and extraction service only.
3. If intent confidence is low or required information is ambiguous, return needs_clarification=true.
4. For DOB: if the numeric date is ambiguous (e.g. 08/09/2004 where both parts ≤ 12), set dob_is_ambiguous=true and do NOT guess.
5. Handle spelling mistakes gracefully (e.g. "faver" = fever, "hair faling" = hair loss).
6. For GREETING messages with no medical content → return GREETING intent, all entity fields null.

CURRENT DATE & TIME (IST): {now_str}  ({weekday_str})
TODAY: {today_str}

HOSPITAL DEPARTMENTS (must match exactly one of these names or null):
- General Medicine
- Cardiology
- Pediatrics
- Orthopedics
- Dermatology
- ENT
- Gynecology
- Neurology

SYMPTOM → DEPARTMENT SEMANTIC MAPPING (use semantic understanding, not just keywords):
- Hair loss, hair falling, hair thinning, baldness, dandruff, scalp problems, acne, pimples, skin rash, eczema, psoriasis, itching, skin allergy, skin infection → Dermatology
- Fever, cold, cough, flu, viral fever, body ache, weakness, fatigue, vomiting, diarrhea, headache, migraine, stomach pain, nausea, dizziness, sore throat, runny nose, sneezing → General Medicine
- Chest pain (non-emergency), palpitations, high blood pressure, hypertension, heart problems → Cardiology
- Child fever, baby illness, infant, toddler, pediatric consultation → Pediatrics
- Joint pain, bone pain, fracture, back pain, knee pain, shoulder pain, arthritis, spine pain → Orthopedics
- Ear pain, earache, hearing problems, sinus, throat problems, tonsils, nasal congestion → ENT
- Pregnancy, menstrual problems, period pain, women's health, gynecological → Gynecology
- Seizure, numbness, paralysis, memory loss, migraine (neurological), vertigo, nerve pain → Neurology

SUPPORTED INTENTS (return exactly one):
- GREETING: Hello, hi, good morning, any opening message
- PATIENT_REGISTRATION: New patient wanting to register, first-time visitor
- PATIENT_DETAILS: Asking for personal or dependent details, patient ID, profile info, DOB, son's details, daughter's details, child's details, "What is my patient ID?", "Tell me my details", "Show my patient information", "What is my son's patient ID?", "Show my daughter's details", "Tell me my child's DOB", "What is my son's patient number?". Do NOT classify as BOOK_APPOINTMENT unless the user explicitly asks to book an appointment.
- BOOK_APPOINTMENT: Booking a NEW doctor appointment for symptoms, consultation, checkup ("book an appointment", "I want to see a doctor", "book appointment for my son", "my son needs an appointment")
- DOCTOR_AVAILABILITY: Asking which doctors or slots are available. Also triggered by contextual pronoun references when a doctor is already known in state (e.g. "show doctor availability", "when he will be available?", "when is he available?", "what days is he available?", "when can I see him?", "show his availability", "when is the doctor available?", "what are his available dates?"). Use active_doctor_name from state for pronoun resolution.
- CANCEL_APPOINTMENT: Wants to cancel an existing appointment ("cancel my appointment", "cancel my son's appointment")
- RESCHEDULE_APPOINTMENT: Wants to move/change date or time of existing appointment ("reschedule my appointment", "change my appointment")
- HOSPITAL_INFORMATION: Hospital location, address, timing, departments, contact info
- APPOINTMENT_CONFIRMATION: Patient confirms a pending appointment booking ("yes", "confirm", "ok", "proceed")
- APPOINTMENT_STATUS: Querying, viewing, or checking status of existing appointments ("show my appointments", "show my appointment", "what are my appointments?", "do I have an appointment?", "when is my appointment?", "when is my next appointment?", "show my upcoming appointments", "show my son's appointments", "show my son's booking", "what is my son's appointment?", "show my daughter's appointment", "what appointments does my daughter have?", "what is my child's appointment?", "show P00125 appointments"). DO NOT classify as BOOK_APPOINTMENT!
- PATIENT_DETAILS_UPDATE: Updating personal info (name, phone, DOB, email)
- DEPENDENT_BOOKING: Booking a NEW appointment for a family member (son, daughter, wife, husband, mother, father, child)
- PRE_ADMISSION: Pre-admission registration, clearance, confirming admission ("confirm admission", "btn_confirm_admission"), cancelling admission ("cancel admission"), pre-admission requirements or documents
- EMERGENCY: Chest pain, severe difficulty breathing, sudden stroke, heavy bleeding, life-threatening emergency
- HUMAN_ESCALATION: Asking to talk to a human agent, staff, operator, or customer care
- GENERAL_MEDICAL_QUERY: General healthcare or medical advice question
- THANK_YOU: Thanking the bot ("thank you", "thanks", "appreciated")
- HELP: Asking for help or list of options
- UNKNOWN: Cannot determine intent; requires clarification

CONVERSATION HISTORY (last 6 turns):
{history_ctx}

CURRENT CONVERSATION STATE (including pending_stage — the question the bot just asked):
{state_summary}

PATIENT'S MESSAGE:
"{message_text}"

INSTRUCTIONS:
- NEW CLINICAL COMPLAINT PRIORITY: When the patient provides a disease, symptom, health complaint, or reason for consultation (including short phrases like "Nose pain", "Ear bleeding", "Throat pain", "Hair Fall problem", "I have Nose pain"), ALWAYS classify intent as BOOK_APPOINTMENT, extract medical_reason, reason_raw_quote, and determine the appropriate department (e.g. Dermatology for hair loss/scalp, ENT for ear/nose/throat, General Medicine for fever/cough), even if an active appointment workflow or previous question exists.
- Do NOT force a new clinical complaint into a currently pending date, time, or doctor field.
- Do NOT carry forward stale doctor or date values when a new clinical complaint is provided in THIS message.
- Use the conversation state and history to resolve ambiguous short messages.
- If pending_stage=AWAITING_DATE and patient says "tomorrow", extract appointment_date=tomorrow's date with date_raw_quote="tomorrow".
- If pending_stage=AWAITING_BOOKING_ID, keep intent as APPOINTMENT_STATUS or CANCEL_APPOINTMENT and do not switch to BOOK_APPOINTMENT.
- If confirmation_pending=true and patient says "yes"/"ok"/"sure", return intent=APPOINTMENT_CONFIRMATION.
- For DEPENDENT_BOOKING or DEPENDENT APPOINTMENT_STATUS: extract relationship (SON/DAUGHTER/CHILD/SPOUSE/MOTHER/FATHER/SIBLING) and booking_for=DEPENDENT / CHILD.
- For APPOINTMENT_STATUS: extract appointment_subject="SELF" (if asking "my appointments") or "DEPENDENT" (if asking "my son's appointments", "my daughter's appointments", "my child's appointments").
- For APPOINTMENT_STATUS with Patient ID or Name: extract patient_reference="P00125" or "Johnny".
- For appointment_time: accept natural language ("morning"→"MORNING", "afternoon"→"AFTERNOON", "evening"→"EVENING", "10 AM"→"10:00", "5 PM"→"17:00").
- For appointment_date: resolve relative dates to YYYY-MM-DD using today={today_str}.
- For a pure greeting ("Good morning", "Hi", "Hello") with no medical content: intent=GREETING, all entity fields=null.
- PRONOUN RESOLUTION: If state contains active_doctor_name (e.g. "Dr. Wilson M") and the patient uses pronouns like "he", "him", "his", "the doctor" in an availability question ("when he will be available?", "when is he available?", "show his availability", "when can I see him?"), return intent=DOCTOR_AVAILABILITY and doctor_name=active_doctor_name.
- Do NOT route "show doctor availability", "when is he available?", or "what days is he available?" to BOOK_APPOINTMENT.
- Do NOT route "show my appointments" or "when is my appointment?" to DOCTOR_AVAILABILITY.

Return ONLY a JSON object with these exact fields (no explanation, no markdown):
{{
  "intent": "<one of the supported intents above>",
  "confidence": <float 0.0-1.0>,
  "appointment_subject": "SELF" | "DEPENDENT" | null,
  "patient_reference": "<extracted patient ID like P00125 or name like Johnny, or null>",
  "time_filter": "UPCOMING" | "PAST" | "NEXT" | "ALL" | null,
  "symptoms": [<list of symptom strings, or []>],
  "medical_reason": "<symptom/visit-reason extracted from THIS message, or null>",
  "reason_raw_quote": "<exact substring from THIS message that supports medical_reason, or null>",
  "department": "<department name from the list above, or null>",
  "doctor_name": "<doctor name ONLY if patient explicitly requested a specific doctor in THIS message, otherwise null>",
  "doctor_raw_quote": "<exact substring from THIS message that supports doctor_name, or null>",
  "patient_type": "EXISTING" | "FIRST_TIME" | null,
  "booking_for": "SELF" | "CHILD" | "FAMILY_MEMBER" | null,
  "relationship": "SON" | "DAUGHTER" | "CHILD" | "SPOUSE" | "MOTHER" | "FATHER" | "SIBLING" | "DEPENDENT" | null,
  "patient_name": "<patient name ONLY if explicitly given in THIS message, or null>",
  "patient_name_raw_quote": "<exact substring from THIS message that supports patient_name, or null>",
  "date_of_birth": "<YYYY-MM-DD or null>",
  "dob_is_ambiguous": <true | false>,
  "gender": "Male" | "Female" | "Other" | null,
  "appointment_date": "<YYYY-MM-DD ONLY if date mentioned in THIS message, or null>",
  "date_raw_quote": "<exact substring from THIS message that supports appointment_date, or null>",
  "appointment_time": "<HH:MM (24h) or MORNING/AFTERNOON/EVENING/NIGHT ONLY if time in THIS message, or null>",
  "time_raw_quote": "<exact substring from THIS message that supports appointment_time, or null>",
  "needs_clarification": <true | false>,
  "clarification_question": "<question to ask patient, or null>",
  "missing_fields": [<list of field names still needed, or []>],
  "language": "ENGLISH" | "TAMIL" | "HINDI" | "TELUGU" | "MALAYALAM" | "KANNADA" | "URDU",
  "emergency": <true | false>
}}

EXAMPLES (showing raw_quote usage):

Patient: "show my appointments"
Response: {{"intent":"APPOINTMENT_STATUS","confidence":0.99,"appointment_subject":"SELF","patient_reference":null,"time_filter":"ALL","symptoms":[],"medical_reason":null,"reason_raw_quote":null,"department":null,"doctor_name":null,"doctor_raw_quote":null,"patient_type":null,"booking_for":"SELF","relationship":null,"patient_name":null,"patient_name_raw_quote":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":null,"date_raw_quote":null,"appointment_time":null,"time_raw_quote":null,"needs_clarification":false,"clarification_question":null,"missing_fields":[],"language":"ENGLISH","emergency":false}}

Patient: "show my son's appointments"
Response: {{"intent":"APPOINTMENT_STATUS","confidence":0.99,"appointment_subject":"DEPENDENT","patient_reference":null,"time_filter":"ALL","symptoms":[],"medical_reason":null,"reason_raw_quote":null,"department":null,"doctor_name":null,"doctor_raw_quote":null,"patient_type":null,"booking_for":"CHILD","relationship":"SON","patient_name":null,"patient_name_raw_quote":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":null,"date_raw_quote":null,"appointment_time":null,"time_raw_quote":null,"needs_clarification":false,"clarification_question":null,"missing_fields":[],"language":"ENGLISH","emergency":false}}

Patient: "what is my daughter's appointment?"
Response: {{"intent":"APPOINTMENT_STATUS","confidence":0.99,"appointment_subject":"DEPENDENT","patient_reference":null,"time_filter":"ALL","symptoms":[],"medical_reason":null,"reason_raw_quote":null,"department":null,"doctor_name":null,"doctor_raw_quote":null,"patient_type":null,"booking_for":"CHILD","relationship":"DAUGHTER","patient_name":null,"patient_name_raw_quote":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":null,"date_raw_quote":null,"appointment_time":null,"time_raw_quote":null,"needs_clarification":false,"clarification_question":null,"missing_fields":[],"language":"ENGLISH","emergency":false}}

Patient: "Show P00125 appointments"
Response: {{"intent":"APPOINTMENT_STATUS","confidence":0.99,"appointment_subject":"DEPENDENT","patient_reference":"P00125","time_filter":"ALL","symptoms":[],"medical_reason":null,"reason_raw_quote":null,"department":null,"doctor_name":null,"doctor_raw_quote":null,"patient_type":null,"booking_for":null,"relationship":null,"patient_name":null,"patient_name_raw_quote":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":null,"date_raw_quote":null,"appointment_time":null,"time_raw_quote":null,"needs_clarification":false,"clarification_question":null,"missing_fields":[],"language":"ENGLISH","emergency":false}}

Patient: "I have fever and cough. I want to see a doctor tomorrow morning."
Response: {{"intent":"BOOK_APPOINTMENT","confidence":0.98,"appointment_subject":"SELF","patient_reference":null,"time_filter":null,"symptoms":["fever","cough"],"medical_reason":"fever and cough","reason_raw_quote":"fever and cough","department":"General Medicine","doctor_name":null,"doctor_raw_quote":null,"patient_type":null,"booking_for":"SELF","relationship":null,"patient_name":null,"patient_name_raw_quote":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":"{tomorrow_str}","date_raw_quote":"tomorrow","appointment_time":"MORNING","time_raw_quote":"morning","needs_clarification":false,"clarification_question":null,"missing_fields":[],"language":"ENGLISH","emergency":false}}
"""
    return prompt


# ---------------------------------------------------------------------------
# JSON cleanup and parsing
# ---------------------------------------------------------------------------
def _parse_llm_json(raw: str) -> Optional[dict]:
    """
    Cleans and parses LLM JSON response.
    Handles markdown code fences and minor formatting issues.
    """
    if not raw:
        return None

    clean = raw.strip()

    # Strip markdown code fences
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-z]*\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)
        clean = clean.strip()

    # Try direct parse
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        pass

    # Try to extract first JSON object
    match = re.search(r"\{[\s\S]*\}", clean)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Validation and normalisation of LLM output
# ---------------------------------------------------------------------------
def _validate_and_normalise(parsed: dict, message_text: str, current_state: dict) -> dict:
    """
    Validates the LLM-returned dict:
    - Normalises intent → canonical supported intent
    - Validates department against VALID_DEPARTMENTS
    - Resolves date strings to YYYY-MM-DD using date_normalizer
    - Resolves time strings to HH:MM using entity_extractor
    - Enforces doctor_preference = null (no LLM doctor selection)
    - Clamps confidence to [0.0, 1.0]
    Returns a clean, validated structured intent dict.
    """
    if not isinstance(parsed, dict):
        return _fallback_structure()

    # --- Intent normalisation ---
    raw_intent = str(parsed.get("intent", "UNKNOWN")).upper()
    intent = INTENT_NORMALISATION_MAP.get(raw_intent, raw_intent)
    if intent not in SUPPORTED_INTENTS:
        intent = "UNKNOWN"

    # --- Confidence ---
    try:
        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.5

    # --- Department validation ---
    dept = parsed.get("department")
    if dept and dept not in VALID_DEPARTMENTS:
        # Try case-insensitive fix
        dept_lower = dept.lower()
        found = next((d for d in VALID_DEPARTMENTS if d.lower() == dept_lower), None)
        dept = found  # None if not found

    # --- Doctor Name (extracted ONLY if explicitly requested by patient) ---
    doc_name = parsed.get("doctor_name") or parsed.get("doctor_preference")
    if doc_name:
        doc_name = str(doc_name).strip()
        if not doc_name or doc_name.lower() in ["null", "none"]:
            doc_name = None

    # --- Symptoms ---
    symptoms = parsed.get("symptoms", [])
    if isinstance(symptoms, str):
        symptoms = [symptoms]
    elif not isinstance(symptoms, list):
        symptoms = []
    symptoms = [str(s).strip() for s in symptoms if str(s).strip()]

    # --- Medical Reason ---
    med_reason = parsed.get("medical_reason")
    if not med_reason and symptoms:
        med_reason = ", ".join(symptoms)

    # --- DOB & DOB Ambiguity ---
    dob_raw = parsed.get("date_of_birth") or parsed.get("patient_dob") or parsed.get("dob")
    dob = None
    dob_is_ambiguous = bool(parsed.get("dob_is_ambiguous", False))
    if dob_raw and str(dob_raw).strip().lower() not in ["null", "none", ""]:
        norm_dob, is_amb, _ = date_normalizer.parse_and_normalize_date(str(dob_raw))
        dob = norm_dob if norm_dob else str(dob_raw).strip()
        dob_is_ambiguous = dob_is_ambiguous or is_amb

    # --- Appointment Date (STRICT SEPARATION FROM DOB) ---
    appt_date_raw = parsed.get("appointment_date")
    appointment_date = None
    if appt_date_raw and str(appt_date_raw).strip().lower() not in ["null", "none", ""]:
        norm_date, _, _ = date_normalizer.parse_and_normalize_date(str(appt_date_raw))
        if norm_date:
            try:
                today_yr = _get_ist_now().year
                parsed_yr = int(norm_date.split("-")[0])
                # Appointment date MUST be in current or future year
                if parsed_yr >= today_yr:
                    appointment_date = norm_date
            except Exception:
                appointment_date = norm_date
        else:
            appointment_date = str(appt_date_raw).strip()

    # --- Appointment Time ---
    appt_time_raw = parsed.get("appointment_time")
    appointment_time = None
    if appt_time_raw and str(appt_time_raw).strip().lower() not in ["null", "none", ""]:
        parsed_t = entity_extractor.parse_natural_time(str(appt_time_raw))
        appointment_time = parsed_t if parsed_t else str(appt_time_raw).strip()

    # --- Patient Type ---
    pat_type = parsed.get("patient_type")
    if pat_type and str(pat_type).upper() in {"EXISTING", "FIRST_TIME"}:
        pat_type = str(pat_type).upper()
    else:
        pat_type = None

    # --- booking_for ---
    booking_for = str(parsed.get("booking_for", "SELF") or "SELF").upper()
    if booking_for in {"DEPENDENT", "CHILD"}:
        booking_for = "CHILD"
    elif booking_for in {"FAMILY", "FAMILY_MEMBER"}:
        booking_for = "FAMILY_MEMBER"
    else:
        booking_for = "SELF"

    # --- Relationship ---
    relationship = parsed.get("relationship")
    if relationship:
        relationship = str(relationship).upper()
        valid_rels = {"SON", "DAUGHTER", "CHILD", "SPOUSE", "MOTHER", "FATHER", "SIBLING", "DEPENDENT"}
        if relationship not in valid_rels:
            relationship = "DEPENDENT"

    # --- Appointment Subject & Patient Reference for APPOINTMENT_STATUS ---
    appt_subj = parsed.get("appointment_subject")
    if appt_subj and str(appt_subj).upper() in {"SELF", "DEPENDENT"}:
        appt_subj = str(appt_subj).upper()
    elif relationship or booking_for in {"CHILD", "DEPENDENT", "FAMILY_MEMBER"}:
        appt_subj = "DEPENDENT"
    else:
        appt_subj = "SELF"

    pat_ref = parsed.get("patient_reference")
    if pat_ref and str(pat_ref).strip().lower() not in {"null", "none", ""}:
        pat_ref = str(pat_ref).strip()
    else:
        pat_ref = None

    time_filter = parsed.get("time_filter")
    if time_filter and str(time_filter).upper() in {"UPCOMING", "PAST", "NEXT", "ALL"}:
        time_filter = str(time_filter).upper()
    else:
        time_filter = "ALL"

    # If DEPENDENT_BOOKING detected, ensure booking_for=CHILD
    if intent == "DEPENDENT_BOOKING":
        booking_for = "CHILD"

    # --- Missing fields ---
    missing_fields = parsed.get("missing_fields", [])
    if not isinstance(missing_fields, list):
        missing_fields = []

    # --- Clarification ---
    needs_clarification = bool(parsed.get("needs_clarification", False))
    clarification_question = parsed.get("clarification_question")
    if not needs_clarification:
        clarification_question = None

    # --- Language ---
    lang = str(parsed.get("language", "ENGLISH")).upper()
    valid_langs = {"ENGLISH", "TAMIL", "HINDI", "TELUGU", "MALAYALAM", "KANNADA", "URDU"}
    if lang not in valid_langs:
        lang = "ENGLISH"

    # --- Emergency flag ---
    emergency = bool(parsed.get("emergency", False))

    # --- Pass through raw_quote fields for grounding_validator ---
    def _clean_quote(q) -> Optional[str]:
        if not q or str(q).strip().lower() in ("null", "none", ""):
            return None
        return str(q).strip()

    res_dict = {
        "intent":                intent,
        "confidence":            confidence,
        "appointment_subject":   appt_subj,
        "patient_reference":     pat_ref,
        "time_filter":           time_filter,
        "symptoms":              symptoms,
        "medical_reason":        med_reason,
        "reason_raw_quote":      _clean_quote(parsed.get("reason_raw_quote")),
        "department":            dept,
        "doctor_name":           doc_name,
        "doctor_raw_quote":      _clean_quote(parsed.get("doctor_raw_quote")),
        "doctor_preference":     doc_name,  # for backward compatibility
        "patient_type":          pat_type,
        "booking_for":           booking_for,
        "relationship":          relationship,
        "patient_name":          parsed.get("patient_name"),
        "patient_name_raw_quote": _clean_quote(parsed.get("patient_name_raw_quote")),
        "date_of_birth":         dob,
        "dob_is_ambiguous":      dob_is_ambiguous,
        "gender":                parsed.get("gender"),
        "appointment_date":      appointment_date,
        "date_raw_quote":        _clean_quote(parsed.get("date_raw_quote")),
        "appointment_time":      appointment_time,
        "time_raw_quote":        _clean_quote(parsed.get("time_raw_quote")),
        "needs_clarification":   needs_clarification,
        "clarification_question": clarification_question,
        "missing_fields":        missing_fields,
        "language":              lang,
        "emergency":             emergency,
        "_llm_powered":          True,
    }
    
    print(f"[INTENT_AGENT] Intent: {res_dict['intent']} (Confidence: {res_dict['confidence']})")
    print(f"[EXTRACTED_ENTITIES] Symptoms: {res_dict['symptoms']} | Reason: {res_dict['medical_reason']} | Doctor: {res_dict['doctor_name']} | Date: {res_dict['appointment_date']} | Time: {res_dict['appointment_time']} | Booking For: {res_dict['booking_for']}")
    if res_dict['department']:
        print(f"[DEPARTMENT] Department Identified: {res_dict['department']}")
        
    return res_dict


def _fallback_structure() -> dict:
    """Returns a minimal UNKNOWN intent structure for error cases."""
    return {
        "intent":                "UNKNOWN",
        "confidence":            0.0,
        "symptoms":              [],
        "medical_reason":        None,
        "department":            None,
        "doctor_name":           None,
        "doctor_preference":     None,
        "patient_type":          None,
        "booking_for":           "SELF",
        "relationship":          None,
        "patient_name":          None,
        "date_of_birth":         None,
        "dob_is_ambiguous":      False,
        "gender":                None,
        "appointment_date":      None,
        "appointment_time":      None,
        "needs_clarification":   False,
        "clarification_question": None,
        "missing_fields":        [],
        "language":              "ENGLISH",
        "emergency":             False,
        "_llm_powered":          False,
    }


# ---------------------------------------------------------------------------
# Rule-based fallback adapter
# ---------------------------------------------------------------------------
def _rule_based_fallback(
    message_text: str,
    current_state: dict,
) -> dict:
    """
    Calls the existing deterministic intent_router.route_patient_message()
    and adapts its output to the new structured schema.
    Used when LLM is unavailable or returns malformed output.
    """
    try:
        import agent.intent_router as intent_router
        import agent.intent_detector as intent_detector
        msg_lower = message_text.lower()
        rule_result = intent_router.route_patient_message(message_text, current_state)

        old_intent = rule_result.get("intent", "UNKNOWN")
        canonical_intent = INTENT_NORMALISATION_MAP.get(old_intent, old_intent)
        if canonical_intent not in SUPPORTED_INTENTS:
            canonical_intent = "UNKNOWN"

        dept = rule_result.get("department")
        doc_pref = rule_result.get("doctor_preference")

        if not doc_pref and ("dr" in msg_lower or "doctor" in msg_lower):
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT id, display_name FROM doctors WHERE status = 'ACTIVE';")
                for d_id, d_name in cur.fetchall():
                    parts = re.findall(r"\b\w+\b", d_name.lower())
                    for p in parts:
                        if len(p) > 2 and p not in ["dr", "dr.", "kumar", "ramesh", "mr", "mrs", "ms"]:
                            if re.search(r"\b" + re.escape(p) + r"\b", msg_lower):
                                doc_pref = d_name
                                rule_result["doctor_id"] = d_id
                                break
                    if doc_pref:
                        break
            finally:
                cur.close()
                conn.close()

        # Fast-path for Pre-Admission intents
        _pre_adm_kws = ["pre-admission", "preadmission", "confirm admission", "cancel admission", "admission clearance", "btn_confirm_admission", "btn_cancel_admission", "btn_admission_help"]
        if any(p in msg_lower for p in _pre_adm_kws) or current_state.get("intent") == "PRE_ADMISSION":
            canonical_intent = "PRE_ADMISSION"

        # Detect: "my son details", "son's profile", "my daughter details", "dependent details", etc.
        _dep_detail_kws = [
            "son detail", "son's detail", "my son detail", "son profile", "son information", "son info",
            "daughter detail", "daughter's detail", "my daughter detail", "daughter profile", "daughter information",
            "child detail", "child's detail", "my child detail", "child profile", "dependent detail",
            "family member detail", "wife detail", "husband detail", "mother detail", "father detail",
            "show my son", "tell my son", "show son", "tell son", "son data", "daughter data",
            "my family member detail", "family detail", "son's patient id", "daughter's patient id",
            "child's dob", "my son's patient number", "my daughter's patient id", "my child's patient id",
            "son patient id", "daughter patient id", "child patient id", "son's dob", "daughter's dob", "child's details"
        ]
        _dep_detail_hit = any(p in msg_lower for p in _dep_detail_kws)

        if any(p in msg_lower for p in ["my personal details", "personal details", "tell my details", "show my details", "my patient profile", "my patient id", "patient id", "what is my id", "tell me my patient id", "my patient code", "my details", "patient information", "show details", "tell details", "what are my details", "show my DOB", "registered information"]) or _dep_detail_hit:
            canonical_intent = "PATIENT_DETAILS"
            dept = None
            doc_pref = None
            if _dep_detail_hit:
                rule_result["query_for_dependent"] = True
                # Try to extract the dependent's name from the message
                # e.g. "Aron's details" → "Aron", "tell me my son Aron details" → "Aron"
                import re as _re
                _name_match = _re.search(
                    r"(?:my son|my daughter|my child|my wife|my husband|my mother|my father|for)\s+([A-Z][a-z]+)",
                    message_text, _re.IGNORECASE
                ) or _re.search(
                    r"([A-Z][a-z]+)(?:'s|s)?\s+(?:detail|profile|information|data)",
                    message_text, _re.IGNORECASE
                )
                if _name_match:
                    rule_result["dependent_name_hint"] = _name_match.group(1).strip()

        # Detect relationship context statements like "Aron is my son" — store context, don't book
        _rel_context_patterns = [
            r"\b(\w+)\s+is\s+my\s+(son|daughter|child|wife|husband|mother|father|brother|sister)\b",
            r"\bmy\s+(son|daughter|child)'?s?\s+name\s+is\s+(\w+)\b",
        ]
        for _pat in _rel_context_patterns:
            import re as _re2
            _m = _re2.search(_pat, msg_lower)
            if _m:
                canonical_intent = "PATIENT_DETAILS"
                rule_result["relationship_context_only"] = True
                rule_result["query_for_dependent"] = True
                dept = None
                doc_pref = None
                break

        # Only map UNKNOWN to BOOK_APPOINTMENT if the message itself contained medical content (not pure greeting/ack)
        has_new_medical_info = bool(rule_result.get("symptoms") or rule_result.get("doctor_preference") or (dept and any(w in msg_lower for w in ["appointment", "doctor", "consult", "book", "symptom", "fever", "pain"])))
        if canonical_intent == "UNKNOWN" and has_new_medical_info:
            if current_state.get("intent") == "DOCTOR_AVAILABILITY":
                canonical_intent = "DOCTOR_AVAILABILITY"
            else:
                canonical_intent = "BOOK_APPOINTMENT"
        if any(p in msg_lower for p in ["hospital location", "location", "address", "where is the hospital", "hospital info", "contact info", "where is hospital", "tell me hospital"]):
            canonical_intent = "HOSPITAL_INFORMATION"
        elif canonical_intent not in {"RESCHEDULE_APPOINTMENT", "CANCEL_APPOINTMENT"}:
            if any(p in msg_lower for p in [
                "shift my appointment", "shift appointment", "shift to",
                "move appointment", "move my appointment",
                "change appointment", "change my appointment",
                "can we shift", "can you shift",
            ]):
                canonical_intent = "RESCHEDULE_APPOINTMENT"

        detected_rule_intent = intent_detector.detect_intent(message_text, current_state.get("intent"))
        if detected_rule_intent == "APPOINTMENT_STATUS" or any(p in msg_lower for p in ["show my appointment", "show my appointments", "my son's appointment", "my daughter's appointment", "my child's appointment", "show appointments"]):
            canonical_intent = "APPOINTMENT_STATUS"
            dept = None
            doc_pref = None

        old_appt_for = rule_result.get("appointment_for", "SELF") or "SELF"
        if old_appt_for in ["CHILD", "FAMILY_MEMBER"]:
            booking_for = "CHILD"
        else:
            booking_for = "SELF"

        rel = rule_result.get("relationship")
        if not rel:
            import re as _re_rel
            if _re_rel.search(r"\b(son|boy)\b", msg_lower):
                rel = "SON"
            elif _re_rel.search(r"\b(daughter|girl)\b", msg_lower):
                rel = "DAUGHTER"
            elif _re_rel.search(r"\b(child|kid)\b", msg_lower):
                rel = "CHILD"

        if canonical_intent == "APPOINTMENT_STATUS":
            dept = None
            doc_pref = None
            appt_subj = "DEPENDENT" if (rel or any(w in msg_lower for w in ["son", "daughter", "child", "kid"])) else "SELF"
            if appt_subj == "DEPENDENT":
                booking_for = "CHILD"
        else:
            appt_subj = "SELF"

        import re as _re_ref
        _ref_m = _re_ref.search(r"\b(P\d{3,6}|PAT\d{4,6}|TST\d{3,6})\b", message_text, _re_ref.IGNORECASE)
        pat_ref = _ref_m.group(1).upper() if _ref_m else None

        if rel and canonical_intent == "BOOK_APPOINTMENT":
            canonical_intent = "DEPENDENT_BOOKING"
            booking_for = "CHILD"

        symptoms = rule_result.get("symptoms", [])
        reason = ", ".join(symptoms) if symptoms else None

        appt_d = rule_result.get("date")

        return {
            "intent":                canonical_intent,
            "confidence":            rule_result.get("confidence", 0.98),
            "appointment_subject":   appt_subj,
            "patient_reference":     pat_ref,
            "time_filter":           "ALL",
            "symptoms":              symptoms,
            "medical_reason":        reason,
            "department":            dept,
            "doctor_name":           rule_result.get("doctor_preference"),
            "doctor_preference":     rule_result.get("doctor_preference"),
            "patient_type":          None,
            "booking_for":           booking_for,
            "relationship":          rel,
            "patient_name":          None,
            "date_of_birth":         rule_result.get("dob"),
            "dob_is_ambiguous":      False,
            "gender":                None,
            "appointment_date":      appt_d,
            "appointment_time":      rule_result.get("time"),
            "needs_clarification":   False,
            "clarification_question": None,
            "missing_fields":        [],
            "language":              rule_result.get("language", "ENGLISH"),
            "emergency":             rule_result.get("emergency", False),
            "_llm_powered":          False,
        }
    except Exception as exc:
        _log(f"Rule-based fallback error: {exc}")
        return _fallback_structure()


# ---------------------------------------------------------------------------
# Main Public API
# ---------------------------------------------------------------------------
def route_patient_message_llm(
    message_text: str,
    current_state: Optional[dict] = None,
    conversation_history: Optional[List[dict]] = None,
) -> dict:
    """
    PRIMARY ENTRY POINT: LLM-powered Patient Intent Router.

    Accepts the patient's raw message text, the current conversation state,
    and recent conversation history.

    Returns a strictly structured dict containing:
      - intent (one of SUPPORTED_INTENTS)
      - confidence
      - symptoms
      - department (DB-compatible name; never a doctor)
      - booking_for (SELF | DEPENDENT)
      - relationship
      - patient_name, date_of_birth, dob_is_ambiguous, gender
      - appointment_date (YYYY-MM-DD), appointment_time (HH:MM or PERIOD)
      - doctor_preference (always None — DB determines actual doctor)
      - needs_clarification, clarification_question
      - missing_fields
      - language, emergency
      - _llm_powered (bool — True if LLM was used, False if rule-based fallback)

    LOGGING:
      Logs the following at each invocation:
        [LLM_ROUTER] Patient message
        [LLM_ROUTER] Conversation state summary
        [LLM_ROUTER] LLM raw response (truncated)
        [LLM_ROUTER] Selected intent
        [LLM_ROUTER] Extracted department
        [LLM_ROUTER] Confidence
        [LLM_ROUTER] Downstream agent
        [LLM_ROUTER] Final structured response

    FALLBACK:
      If LLM is unavailable or returns invalid JSON, falls back to
      the deterministic intent_router.route_patient_message().
    """
    if current_state is None:
        current_state = {}
    if conversation_history is None:
        conversation_history = []

    msg_clean = (message_text or "").strip()

    # --- Structured Log: Input ---
    _log(f"=== NEW ROUTING REQUEST ===")
    _log(f"Patient message      : \"{msg_clean}\"")
    _log(f"Prior intent         : {current_state.get('intent', 'None')}")
    _log(f"Prior department     : {current_state.get('department_name', 'None')}")
    _log(f"Booking for          : {current_state.get('appointment_for', 'SELF')}")
    _log(f"Missing info         : {current_state.get('missing_information', [])}")
    _log(f"Confirmation pending : {current_state.get('confirmation_pending', False)}")
    _log(f"LLM available        : {is_llm_available()}")

    # --- Fast-path: empty message ---
    if not msg_clean:
        _log("Empty message — returning UNKNOWN")
        return _fallback_structure()

    # --- Fast-path: pre-admission buttons & explicit keywords ---
    _pre_adm_btns = {"btn_confirm_admission", "btn_cancel_admission", "btn_admission_help"}
    _pre_adm_phrases = {"confirm admission", "cancel admission", "pre-admission", "preadmission clearance", "confirm pre-admission", "cancel pre-admission", "need assistance"}
    if msg_clean in _pre_adm_btns or msg_clean.lower() in _pre_adm_phrases or (msg_clean.lower() == "confirm" and current_state.get("intent") == "PRE_ADMISSION"):
        _log("Fast-path pre-admission button/keyword detected — returning intent PRE_ADMISSION")
        return {
            "intent":                "PRE_ADMISSION",
            "confidence":            1.0,
            "symptoms":              [],
            "medical_reason":        None,
            "department":            None,
            "doctor_name":           None,
            "doctor_preference":     None,
            "patient_type":          None,
            "booking_for":           "SELF",
            "relationship":          None,
            "patient_name":          None,
            "date_of_birth":         None,
            "dob_is_ambiguous":      False,
            "gender":                None,
            "appointment_date":      None,
            "appointment_time":      None,
            "needs_clarification":   False,
            "clarification_question": None,
            "missing_fields":        [],
            "language":              "ENGLISH",
            "emergency":             False,
            "_llm_powered":          False,
        }

    # --- LLM Path ---
    if is_llm_available():
        prompt = _build_prompt(msg_clean, current_state, conversation_history)

        raw_response: Optional[str] = None
        try:
            if LLM_PROVIDER in {"gemini", "google"}:
                raw_response = _call_gemini(prompt)
            elif LLM_PROVIDER == "openai":
                raw_response = _call_openai(prompt)
        except Exception as exc:
            _log(f"LLM call exception: {exc}\n{traceback.format_exc()}")

        _log(f"LLM raw response     : {(raw_response or '')[:400]}")

        if raw_response:
            parsed = _parse_llm_json(raw_response)
            if parsed:
                structured = _validate_and_normalise(parsed, msg_clean, current_state)

                # --- Structured Log: Output ---
                _log(f"Selected intent      : {structured['intent']}")
                _log(f"Extracted department : {structured['department']}")
                _log(f"Symptoms             : {structured['symptoms']}")
                _log(f"Booking for          : {structured['booking_for']}")
                _log(f"Relationship         : {structured['relationship']}")
                _log(f"Appointment date     : {structured['appointment_date']}")
                _log(f"Appointment time     : {structured['appointment_time']}")
                _log(f"DOB                  : {structured['date_of_birth']} (ambiguous={structured['dob_is_ambiguous']})")
                _log(f"Confidence           : {structured['confidence']}")
                _log(f"Needs clarification  : {structured['needs_clarification']}")
                _log(f"Emergency            : {structured['emergency']}")
                _log(f"Downstream agent     : {structured['intent']}_HANDLER")
                _log(f"LLM-powered          : True")
                _log(f"=== END ROUTING ===")

                return structured
            else:
                _log("JSON parse failed — falling back to rule-based engine")
        else:
            _log("LLM returned no response — falling back to rule-based engine")

    # --- Rule-Based Fallback ---
    _log("Using rule-based fallback router")
    result = _rule_based_fallback(msg_clean, current_state)

    _log(f"Selected intent      : {result['intent']}")
    _log(f"Extracted department : {result['department']}")
    _log(f"Confidence           : {result['confidence']}")
    _log(f"LLM-powered          : False")
    _log(f"Downstream agent     : {result['intent']}_HANDLER")
    _log(f"=== END ROUTING (fallback) ===")

    return result


# ---------------------------------------------------------------------------
# Convenience: get conversation history from DB
# ---------------------------------------------------------------------------
def get_recent_conversation_history(conversation_code: str, max_turns: int = 6) -> List[dict]:
    """
    Fetches the last `max_turns` messages from the DB for the given conversation.
    Returns a list of dicts: [{"sender": "PATIENT"|"AI_AGENT", "text": "..."}]
    """
    try:
        import db_config
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT m.sender_type, m.message_text
                FROM messages m
                JOIN conversations c ON m.conversation_id = c.id
                WHERE c.conversation_code = %s
                  AND m.message_type = 'TEXT'
                  AND m.sender_type IN ('PATIENT', 'AI_AGENT')
                  AND m.message_text IS NOT NULL
                  AND m.message_text != ''
                ORDER BY m.id DESC
                LIMIT %s;
                """,
                (conversation_code, max_turns * 2),  # fetch extra to account for system messages
            )
            rows = cur.fetchall()

            # Reverse to chronological order
            turns = []
            for sender, text in reversed(rows):
                if text and text.strip():
                    turns.append({"sender": sender, "text": text.strip()})
            return turns[-max_turns:]
        finally:
            cur.close()
            conn.close()
    except Exception as exc:
        _log(f"get_recent_conversation_history error: {exc}")
        return []
