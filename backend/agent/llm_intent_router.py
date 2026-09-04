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
    "PRE_ADMISSION":                "HOSPITAL_INFORMATION",
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

    # Try primary model, then fallback to gemini-3.6-flash
    for attempt_model in [model_name, "gemini-3.6-flash"]:
        attempt_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{attempt_model}:generateContent?key={LLM_API_KEY}"
        )
        try:
            res = requests.post(
                attempt_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
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
    entities        = current_state.get("entities", {})
    known_date      = entities.get("appointment_date", "")
    known_time      = entities.get("appointment_time", "")
    known_dept_id   = entities.get("department_id", "")
    known_doc_id    = entities.get("doctor_id", "")
    missing_info    = current_state.get("missing_information", [])
    confirm_pending = current_state.get("confirmation_pending", False)

    state_summary = json.dumps({
        "prior_intent":        prior_intent,
        "prior_department":    prior_dept,
        "prior_doctor_id":     known_doc_id,
        "known_date":          known_date,
        "known_time":          known_time,
        "booking_for":         appt_for,
        "relationship":        relationship,
        "missing_fields":      missing_info,
        "confirmation_pending": confirm_pending,
        "previous_question":   prev_question,
        "booking_stage":       booking_stage,
        "last_bot_message":    last_bot_msg,
    }, ensure_ascii=False)

    tomorrow_str = (_get_ist_now().date() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    prompt = f"""You are the Patient Intent Router for Meridian Hospital's AI Patient Desk.
Your ONLY job is to classify the patient's intent and extract structured entities from their message.

CRITICAL RULES — you MUST follow these:
1. DO NOT select, suggest, or invent any doctor name. Only extract the appropriate medical department.
2. DO NOT write to any database. You are a classification and extraction service only.
3. All extracted patient information will be validated by downstream deterministic services before any DB insertion.
4. If intent confidence is low or required information is ambiguous, return needs_clarification=true and provide a helpful clarification_question.
5. For DOB: if the numeric date is ambiguous (e.g. 08/09/2004 where both parts ≤ 12), set dob_is_ambiguous=true and do NOT guess.
6. For natural-language dates like "tomorrow", "next Monday", "Friday" — convert them using the current IST date below.
7. For short follow-up messages ("tomorrow", "5 PM", "yes", "cancel it") — interpret them using the conversation state below. Do NOT restart the conversation.
8. Handle spelling mistakes gracefully (e.g. "faver" = fever, "hair faling" = hair loss).

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
- PATIENT_DETAILS: Patient asking for personal details, patient ID, profile info ("tell me my details", "my patient ID", "show my info", "what details do you have about me")
- BOOK_APPOINTMENT: Booking a doctor appointment for symptoms, consultation, checkup ("I want an appointment", "book doctor", "need doctor for fever")
- DOCTOR_AVAILABILITY: Asking which doctors or slots are available ("which doctors are available?", "who is available tomorrow?", "any dermatologist available?")
- CANCEL_APPOINTMENT: Wants to cancel an existing appointment ("cancel my appointment", "I cannot come tomorrow")
- RESCHEDULE_APPOINTMENT: Wants to move/change date or time of existing appointment ("change my appointment", "move it to Friday")
- HOSPITAL_INFORMATION: Hospital location, address, timing, departments, contact info
- APPOINTMENT_CONFIRMATION: Patient confirms a pending appointment booking ("yes", "confirm", "ok", "proceed")
- APPOINTMENT_STATUS: Checking status of a booked appointment ("what is my appointment?", "my booking", "show my appointment")
- PATIENT_DETAILS_UPDATE: Updating personal info (name, phone, DOB, email)
- DEPENDENT_BOOKING: Booking for a family member (son, daughter, wife, husband, mother, father, child)
- EMERGENCY: Chest pain, severe difficulty breathing, sudden stroke, heavy bleeding, life-threatening emergency
- HUMAN_ESCALATION: Asking to talk to a human agent, staff, operator, or customer care
- GENERAL_MEDICAL_QUERY: General healthcare or medical advice question
- THANK_YOU: Thanking the bot ("thank you", "thanks", "appreciated")
- HELP: Asking for help or list of options
- UNKNOWN: Cannot determine intent; requires clarification

CONVERSATION HISTORY (last 6 turns):
{history_ctx}

CURRENT CONVERSATION STATE:
{state_summary}

PATIENT'S MESSAGE:
"{message_text}"

INSTRUCTIONS:
- Use the conversation state and history to resolve ambiguous short messages.
- If prior_intent is BOOK_APPOINTMENT and patient says "tomorrow", extract appointment_date=tomorrow's date.
- If confirmation_pending=true and patient says "yes"/"ok"/"sure", return intent=APPOINTMENT_CONFIRMATION.
- If prior_intent is BOOK_APPOINTMENT and patient says "cancel", return intent=CANCEL_APPOINTMENT.
- For DEPENDENT_BOOKING: extract relationship (SON/DAUGHTER/CHILD/SPOUSE/MOTHER/FATHER/SIBLING) and booking_for=DEPENDENT.
- For appointment_time: accept natural language ("morning"→"MORNING", "afternoon"→"AFTERNOON", "evening"→"EVENING", "10 AM"→"10:00", "5 PM"→"17:00", "10:30"→"10:30").
- For appointment_date: resolve relative dates to YYYY-MM-DD using today={today_str}.
- If patient mentions BOTH symptoms AND a date/time in one message, extract all of them.

Return ONLY a JSON object with these exact fields (no explanation, no markdown):
{{
  "intent": "<one of the supported intents above>",
  "confidence": <float 0.0-1.0>,
  "symptoms": [<list of symptom strings, or []>],
  "medical_reason": "<string or null>",
  "department": "<department name from the list above, or null>",
  "doctor_name": "<doctor name string ONLY if patient explicitly requested a specific doctor by name, otherwise null>",
  "patient_type": "EXISTING" | "FIRST_TIME" | null,
  "booking_for": "SELF" | "CHILD" | "FAMILY_MEMBER" | null,
  "relationship": "SON" | "DAUGHTER" | "CHILD" | "SPOUSE" | "MOTHER" | "FATHER" | "SIBLING" | "DEPENDENT" | null,
  "patient_name": "<string or null>",
  "date_of_birth": "<YYYY-MM-DD or null>",
  "dob_is_ambiguous": <true | false>,
  "gender": "Male" | "Female" | "Other" | null,
  "appointment_date": "<YYYY-MM-DD or null>",
  "appointment_time": "<HH:MM (24h) or MORNING/AFTERNOON/EVENING/NIGHT or null>",
  "needs_clarification": <true | false>,
  "clarification_question": "<question to ask patient, or null>",
  "missing_fields": [<list of field names still needed, or []>],
  "language": "ENGLISH" | "TAMIL" | "HINDI" | "TELUGU" | "MALAYALAM" | "KANNADA" | "URDU",
  "emergency": <true | false>
}}

EXAMPLES:

Patient: "I have fever and cough. I want to see a doctor tomorrow morning."
Response: {{"intent":"BOOK_APPOINTMENT","confidence":0.98,"symptoms":["fever","cough"],"medical_reason":"fever and cough","department":"General Medicine","doctor_name":null,"patient_type":null,"booking_for":"SELF","relationship":null,"patient_name":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":"{tomorrow_str}","appointment_time":"MORNING","needs_clarification":false,"clarification_question":null,"missing_fields":[],"language":"ENGLISH","emergency":false}}

Patient: "I have hair falling."
Response: {{"intent":"BOOK_APPOINTMENT","confidence":0.97,"symptoms":["hair loss"],"medical_reason":"hair falling","department":"Dermatology","doctor_name":null,"patient_type":null,"booking_for":"SELF","relationship":null,"patient_name":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":null,"appointment_time":null,"needs_clarification":false,"clarification_question":null,"missing_fields":["appointment_date","appointment_time"],"language":"ENGLISH","emergency":false}}

Patient: "I want to book an appointment for my son, he has fever."
Response: {{"intent":"BOOK_APPOINTMENT","confidence":0.98,"symptoms":["fever"],"medical_reason":"fever","department":"Pediatrics","doctor_name":null,"patient_type":null,"booking_for":"CHILD","relationship":"SON","patient_name":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":null,"appointment_time":null,"needs_clarification":false,"clarification_question":null,"missing_fields":["appointment_date"],"language":"ENGLISH","emergency":false}}

Patient: "I want Dr. Arun Kumar"
Response: {{"intent":"BOOK_APPOINTMENT","confidence":0.99,"symptoms":[],"medical_reason":null,"department":null,"doctor_name":"Dr. Arun Kumar","patient_type":null,"booking_for":"SELF","relationship":null,"patient_name":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":null,"appointment_time":null,"needs_clarification":false,"clarification_question":null,"missing_fields":[],"language":"ENGLISH","emergency":false}}

Patient: "asdfghjkl"
Response: {{"intent":"UNKNOWN","confidence":0.10,"symptoms":[],"medical_reason":null,"department":null,"doctor_name":null,"patient_type":null,"booking_for":null,"relationship":null,"patient_name":null,"date_of_birth":null,"dob_is_ambiguous":false,"gender":null,"appointment_date":null,"appointment_time":null,"needs_clarification":true,"clarification_question":"I'm sorry, I didn't understand that. Could you please tell me how I can help you today? For example: booking an appointment, doctor availability, or hospital information.","missing_fields":[],"language":"ENGLISH","emergency":false}}
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

    res_dict = {
        "intent":                intent,
        "confidence":            confidence,
        "symptoms":              symptoms,
        "medical_reason":        med_reason,
        "department":            dept,
        "doctor_name":           doc_name,
        "doctor_preference":     doc_name,  # for backward compatibility
        "patient_type":          pat_type,
        "booking_for":           booking_for,
        "relationship":          relationship,
        "patient_name":          parsed.get("patient_name"),
        "date_of_birth":         dob,
        "dob_is_ambiguous":      dob_is_ambiguous,
        "gender":                parsed.get("gender"),
        "appointment_date":      appointment_date,
        "appointment_time":      appointment_time,
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
                    d_clean = d_name.lower().replace("dr.", "").replace("dr", "").strip()
                    if d_clean and len(d_clean) > 2 and d_clean in msg_lower:
                        doc_pref = d_name
                        rule_result["doctor_id"] = d_id
                        break
            finally:
                cur.close()
                conn.close()

        if any(p in msg_lower for p in ["my personal details", "personal details", "tell my details", "show my details", "my patient profile", "my patient id", "patient id", "what is my id", "tell me my patient id", "my patient code", "my details", "patient information", "show details", "tell details", "what are my details", "show my DOB", "registered information"]):
            canonical_intent = "PATIENT_DETAILS"
            dept = None
            doc_pref = None

        if canonical_intent == "UNKNOWN" and (dept or doc_pref or rule_result.get("doctor_id")):
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

        old_appt_for = rule_result.get("appointment_for", "SELF") or "SELF"
        if old_appt_for in ["CHILD", "FAMILY_MEMBER"]:
            booking_for = "CHILD"
        else:
            booking_for = "SELF"

        rel = rule_result.get("relationship")
        if rel and canonical_intent == "BOOK_APPOINTMENT":
            canonical_intent = "DEPENDENT_BOOKING"
            booking_for = "CHILD"

        symptoms = rule_result.get("symptoms", [])
        reason = ", ".join(symptoms) if symptoms else None

        appt_d = rule_result.get("date")

        return {
            "intent":                canonical_intent,
            "confidence":            rule_result.get("confidence", 0.8),
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
                "SELECT id FROM conversations WHERE conversation_code = %s LIMIT 1;",
                (conversation_code,)
            )
            row = cur.fetchone()
            if not row:
                return []
            conv_id = row[0]

            cur.execute(
                """
                SELECT sender_type, message_text
                FROM messages
                WHERE conversation_id = %s
                  AND message_type = 'TEXT'
                  AND sender_type IN ('PATIENT', 'AI_AGENT')
                  AND message_text IS NOT NULL
                  AND message_text != ''
                ORDER BY id DESC
                LIMIT %s;
                """,
                (conv_id, max_turns * 2),  # fetch extra to account for system messages
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
