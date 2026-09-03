"""
llm_service.py
==============
LLM Conversation & Structured Entity Extraction Service for Meridian Hospital AI Patient Desk.

Integrates LLM capabilities (Gemini / OpenAI / Ollama) for natural language understanding,
multi-field extraction, and response generation, with seamless deterministic fallbacks.
"""

import os
import sys
import json
import re
import requests
from typing import Dict, Any, Optional

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import agent.intent_detector as intent_detector
import agent.entity_extractor as entity_extractor
import agent.date_normalizer as date_normalizer

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "")


def is_llm_active() -> bool:
    """Returns True if LLM provider and API key are configured for live requests."""
    return bool(LLM_API_KEY and LLM_PROVIDER in ["gemini", "openai", "ollama", "google"])


def _call_gemini_api(prompt: str) -> Optional[str]:
    """Call Gemini REST API generateContent."""
    if not LLM_API_KEY:
        return None
    model_name = "gemini-2.0-flash" if "2.0" in LLM_MODEL or "2.5" in LLM_MODEL else "gemini-1.5-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={LLM_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
    }
    try:
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=8)
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text")
    except Exception as e:
        # LLM fallback to rule-based engine
        pass
    return None


def _call_openai_api(prompt: str) -> Optional[str]:
    """Call OpenAI REST API chat/completions."""
    if not LLM_API_KEY:
        return None
    base_url = LLM_API_BASE or "https://api.openai.com/v1"
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": LLM_MODEL or "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a healthcare assistant extracting structured entities in JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=8)
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[LLM] OpenAI API call error: {e}")
    return None


def extract_structured_info(message_text: str, current_state: dict, language: str = "ENGLISH") -> Dict[str, Any]:
    """
    Extracts structured intent and multi-field information from patient message.
    Uses LLM if configured; otherwise falls back to deterministic rule-based extraction.
    """
    extracted_data = {
        "intent": None,
        "patient_type": None,
        "appointment_for": None,
        "relationship": None,
        "actual_patient_name": None,
        "patient_name": None,
        "first_name": None,
        "last_name": None,
        "date_of_birth": None,
        "gender": None,
        "phone": None,
        "email": None,
        "symptoms": [],
        "department": None,
        "doctor": None,
        "appointment_date": None,
        "appointment_time": None,
        "booking_id": None,
        "reason": None,
        "confidence": 0.95
    }

    # Build session context for LLM
    entities = current_state.get("entities", {})
    session_ctx = {}
    if entities.get("doctor_id"):
        session_ctx["known_doctor_id"] = entities["doctor_id"]
    if entities.get("department_id"):
        session_ctx["known_department_id"] = entities["department_id"]
    if entities.get("appointment_date"):
        session_ctx["known_date"] = entities["appointment_date"]
    if entities.get("appointment_time"):
        session_ctx["known_time"] = entities["appointment_time"]
    if current_state.get("patient_relationship"):
        session_ctx["patient_relationship"] = current_state["patient_relationship"]

    # Attempt LLM extraction if active
    if is_llm_active():
        prompt = f"""
You are an entity extractor for Meridian Hospital WhatsApp AI Patient Desk.
Extract structured information from the patient message below.

Current conversation intent: {current_state.get('intent', 'UNKNOWN')}
Known session context: {json.dumps(session_ctx)}
Patient language: {language}

Patient message: "{message_text}"

Meridian Hospital departments: General Medicine, Cardiology, Pediatrics, Orthopedics, Dermatology, ENT, Gynecology, Neurology.

Symptom → Department mapping rules:
- Hair fall, hair loss, bald, scalp, acne, pimples, skin rash, itching, eczema → Dermatology
- Fever, cold, cough, general weakness, flu → General Medicine
- Chest pain (non-emergency), heart, palpitations, blood pressure → Cardiology
- Child fever, son/daughter illness, pediatric → Pediatrics
- Joint pain, bone pain, fracture, back pain → Orthopedics
- Ear pain, hearing, sinus, throat, tonsil → ENT
- Pregnancy, menstrual problems → Gynecology
- Migraine, seizure, nerve, numbness → Neurology

Return ONLY a valid JSON object with these exact fields:
{{
  "intent": one of ["GREETING","BOOK_APPOINTMENT","REGISTER_PATIENT","IDENTIFY_PATIENT",
    "DEPENDENT_PATIENT","CANCEL_APPOINTMENT","RESCHEDULE_APPOINTMENT",
    "APPOINTMENT_STATUS","APPOINTMENT_CONFIRMATION","DOCTOR_AVAILABILITY",
    "HOSPITAL_INFORMATION","DEPARTMENT_INFORMATION","SYMPTOM_GUIDANCE",
    "PRE_ADMISSION","HUMAN_ESCALATION","EMERGENCY_GUIDANCE",
    "THANK_YOU","GOODBYE","UNKNOWN"],
  "patient_type": "FIRST_TIME" | "EXISTING" | null,
  "appointment_for": "SELF" | "CHILD" | "FAMILY_MEMBER" | null,
  "relationship": "SON" | "DAUGHTER" | "CHILD" | "MOTHER" | "FATHER" | "SPOUSE" | "SIBLING" | "DEPENDENT" | null,
  "actual_patient_name": string or null (name of dependent/family member if appointment is for them),
  "patient_name": string or null (name of the person sending the message),
  "first_name": string or null,
  "last_name": string or null,
  "date_of_birth": "YYYY-MM-DD" or null (normalize ALL date formats to YYYY-MM-DD; return null if ambiguous),
  "gender": "Male" | "Female" | "Other" | null,
  "phone": string or null,
  "email": string or null,
  "symptoms": array of symptom strings (e.g. ["hair loss", "scalp itching"]) or [],
  "department": "General Medicine" | "Cardiology" | "Pediatrics" | "Orthopedics" | "Dermatology" | "ENT" | "Gynecology" | "Neurology" | null,
  "doctor": string or null,
  "appointment_date": "YYYY-MM-DD" or natural language ("tomorrow", "next monday") or null,
  "appointment_time": "HH:MM" (24h) or natural ("10:30 AM", "morning") or null,
  "booking_id": string or null,
  "reason": string or null,
  "confidence": number between 0.0 and 1.0
}}

IMPORTANT: For DOB, normalize ALL formats to YYYY-MM-DD. If the date is ambiguous (e.g. 05/06/2004 could be May 6 or June 5), return null for date_of_birth.
        """
        raw_llm = None
        if LLM_PROVIDER in ["gemini", "google"]:
            raw_llm = _call_gemini_api(prompt)
        elif LLM_PROVIDER == "openai":
            raw_llm = _call_openai_api(prompt)

        if raw_llm:
            try:
                clean_raw = raw_llm.strip()
                if clean_raw.startswith("```"):
                    import re as _re
                    clean_raw = _re.sub(r"^```[a-z]*\n?", "", clean_raw)
                    clean_raw = _re.sub(r"\n?```$", "", clean_raw)
                parsed = json.loads(clean_raw)
                if isinstance(parsed, dict):
                    print(f"[LLM] Extracted fields via LLM: {parsed}")
                    for k in extracted_data.keys():
                        if k in parsed and parsed[k] is not None:
                            extracted_data[k] = parsed[k]
                    return extracted_data
            except Exception as e:
                print(f"[LLM] JSON parse error: {e}")

    # Deterministic Rule-Based & Regex Extraction Fallback
    text_clean = message_text.strip()
    text_lower = text_clean.lower()

    # 1. Intent Detection
    extracted_data["intent"] = intent_detector.detect_intent(text_clean, current_state.get("intent"))

    # 2. Patient Type Selection
    if any(w in text_lower for w in ["first time", "first-time", "new patient", "first_time", "btn_first_time"]):
        extracted_data["patient_type"] = "FIRST_TIME"
        extracted_data["intent"] = "REGISTER_PATIENT"
    elif any(w in text_lower for w in ["existing patient", "existing", "registered patient", "btn_existing"]):
        extracted_data["patient_type"] = "EXISTING"
        extracted_data["intent"] = "IDENTIFY_PATIENT"

    # 3. Family member & relationship extraction (using enhanced extractor)
    rel_info = entity_extractor.extract_relationship(text_clean)
    if rel_info.get("appointment_for"):
        extracted_data["appointment_for"] = rel_info["appointment_for"]
        extracted_data["relationship"] = rel_info["relationship"]

    # 4. Email Extraction
    match_email = re.search(r"\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b", text_clean)
    if match_email:
        extracted_data["email"] = match_email.group(1)

    # 5. Entity Extractor lookup (doctor, department, date, time, booking_id, symptoms)
    rule_entities = entity_extractor.extract_entities(text_clean)

    if rule_entities.get("appointment_date"):
        extracted_data["appointment_date"] = rule_entities["appointment_date"]

    if rule_entities.get("appointment_time"):
        extracted_data["appointment_time"] = rule_entities["appointment_time"]

    if rule_entities.get("booking_id"):
        extracted_data["booking_id"] = rule_entities["booking_id"]

    if rule_entities.get("reason"):
        extracted_data["reason"] = rule_entities["reason"]

    # Doctor and Department text matching
    if rule_entities.get("doctor_id"):
        try:
            from agent.agent_service import resolve_doctor_details
            doc_info = resolve_doctor_details(rule_entities["doctor_id"])
            extracted_data["doctor"] = doc_info["name"]
            extracted_data["department"] = doc_info["department"]
        except Exception:
            pass

    # 6. Symptom → Department mapping (rule-based fallback)
    dept_from_symptom = entity_extractor.map_symptom_to_department_name(text_clean)
    if dept_from_symptom and not extracted_data.get("department"):
        extracted_data["department"] = dept_from_symptom
    # Build symptoms list from message
    symptom_keywords = [
        "hair fall", "hair loss", "losing hair", "bald", "acne", "pimples", "skin rash",
        "eczema", "itching", "fever", "cold", "cough", "headache", "migraine",
        "chest pain", "joint pain", "bone pain", "ear pain", "pregnancy",
        "weakness", "fatigue", "vomiting", "diarrhea", "back pain"
    ]
    found_syms = [k for k in symptom_keywords if k in text_lower]
    if found_syms:
        extracted_data["symptoms"] = found_syms

    # 7. Multi-field Registration & Single Message Parsing (Name, DOB, Gender, Phone, Email)
    # Extract phone
    match_phone = re.search(r"\b(\d{10,12})\b", text_lower)
    if match_phone:
        extracted_data["phone"] = match_phone.group(1)

    # Extract gender
    if re.search(r"\b(male|man)\b", text_lower) and not re.search(r"\b(female|woman)\b", text_lower):
        extracted_data["gender"] = "Male"
    elif re.search(r"\b(female|woman)\b", text_lower):
        extracted_data["gender"] = "Female"
    elif re.search(r"\b(other)\b", text_lower):
        extracted_data["gender"] = "Other"

    # Normalize DOB if present (only if message contains date-like content)
    if re.search(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b", text_clean) or re.search(r"\b\d{4}[-/.]\d{2}[-/.]\d{2}\b", text_clean):
        norm_dob, is_ambig, _ = date_normalizer.parse_and_normalize_date(text_clean)
        if norm_dob:
            extracted_data["date_of_birth"] = norm_dob


    # Multi-field name extraction if comma/newline separated
    parts = [p.strip() for p in re.split(r"[,;\n]+", text_clean) if p.strip()]
    if len(parts) >= 2:
        potential_name = parts[0]
        if not any(kw in potential_name.lower() for kw in [
            "register", "my name", "dob", "phone", "male", "female",
            "book", "appointment", "hi", "hello", "morning", "afternoon", "evening"
        ]):
            name_words = potential_name.split()
            extracted_data["patient_name"] = potential_name
            extracted_data["first_name"] = name_words[0].capitalize()
            if len(name_words) > 1:
                extracted_data["last_name"] = " ".join(name_words[1:]).capitalize()
            else:
                extracted_data["last_name"] = "."

    # Match "My name is X", "name: X", "X is my name"
    match_name = re.search(r"(?:my\s+name\s+is|name\s*:|patient\s*:)\s*([a-zA-Z\s\.]+)", text_lower)
    if match_name:
        n_str = match_name.group(1).strip()
        name_words = n_str.split()
        extracted_data["patient_name"] = n_str.title()
        extracted_data["first_name"] = name_words[0].capitalize()
        if len(name_words) > 1:
            extracted_data["last_name"] = " ".join(name_words[1:]).capitalize()

    return extracted_data


def _call_gemini_freetext(prompt: str, system_instruction: str = None):
    """Call Gemini for free-text (non-JSON) conversational responses."""
    if not LLM_API_KEY:
        return None
    model_name = "gemini-2.0-flash" if "2.0" in LLM_MODEL or "2.5" in LLM_MODEL else "gemini-1.5-flash-latest"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={LLM_API_KEY}"
    contents = []
    if system_instruction:
        contents.append({"role": "user", "parts": [{"text": system_instruction}]})
        contents.append({"role": "model", "parts": [{"text": "Understood. I am the Meridian Hospital AI Patient Desk."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    payload = {"contents": contents, "generationConfig": {"temperature": 0.3, "maxOutputTokens": 512, "responseMimeType": "application/json"}}
    try:
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=10)
        res.raise_for_status()
        data = res.json()
        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            if parts:
                return parts[0].get("text")
    except Exception as e:
        print(f"[LLM] Gemini freetext call error: {e}")
    return None


def llm_classify_intent_and_respond(message_text: str, current_state: dict, language: str = "ENGLISH", conversation_history: list = None) -> dict:
    """
    LLM-powered fallback for UNKNOWN intents.
    Sends full hospital context + conversation history to Gemini and gets back
    both intent classification and a proper patient response.
    Returns: {intent, response, confidence, route_to_handler, detected_department, detected_doctor, detected_date, detected_time}
    """
    if not is_llm_active():
        return {"intent": "UNKNOWN", "response": None, "confidence": "LOW", "route_to_handler": False}

    history_lines = []
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = "Patient" if turn.get("sender") == "PATIENT" else "Bot"
            history_lines.append(f"{role}: {turn.get('text', '')}")
    history_ctx = "\n".join(history_lines) if history_lines else "No prior messages."

    entities = current_state.get("entities", {})
    ctx_parts = []
    if entities.get("doctor_id"):
        ctx_parts.append(f"Doctor ID: {entities['doctor_id']}")
    if entities.get("department_id"):
        ctx_parts.append(f"Department ID: {entities['department_id']}")
    if entities.get("appointment_date"):
        ctx_parts.append(f"Date: {entities['appointment_date']}")
    if entities.get("appointment_time"):
        ctx_parts.append(f"Time: {entities['appointment_time']}")
    session_ctx = ", ".join(ctx_parts) if ctx_parts else "None"
    prior_intent = current_state.get("intent", "UNKNOWN")

    system_instruction = (
        "You are the AI Patient Desk Assistant for Meridian Hospital. "
        "You help patients via WhatsApp with: booking appointments, checking doctor availability, "
        "cancelling/rescheduling appointments, checking appointment status, hospital information, "
        "pre-admission guidance, symptom-to-department routing, and patient registration.\n\n"
        "Meridian Hospital departments: General Medicine, Cardiology, Pediatrics, Orthopedics, Dermatology, ENT, Gynecology, Neurology.\n\n"
        "Active doctors:\n"
        "- Dr. Arun Kumar (General Medicine) — Schedule: Mon-Fri\n"
        "- Dr. Priya Ramesh (Cardiology) — Schedule: Mon-Thu\n"
        "- Dr. Wilson M (Dermatology) — Schedule: Mon, Wed\n"
        "- Dr. James R (ENT) — Schedule: Tue, Thu\n\n"
        "Symptom → Department routing rules:\n"
        "- Hair fall/loss, bald, acne, pimples, skin rash, eczema, itching → Dermatology\n"
        "- Fever, cold, cough, general weakness → General Medicine\n"
        "- Chest pain (non-emergency), heart, palpitations → Cardiology\n"
        "- Child/son/daughter/baby illness → Pediatrics\n"
        "- Joint pain, bone pain, fracture → Orthopedics\n"
        "- Ear pain, hearing, sinus, throat → ENT\n"
        "- Pregnancy, menstrual → Gynecology\n"
        "- Migraine, seizure, nerve → Neurology\n\n"
        "Intent taxonomy: GREETING, BOOK_APPOINTMENT, REGISTER_PATIENT, IDENTIFY_PATIENT, "
        "DEPENDENT_PATIENT, CANCEL_APPOINTMENT, RESCHEDULE_APPOINTMENT, APPOINTMENT_STATUS, "
        "APPOINTMENT_CONFIRMATION, DOCTOR_AVAILABILITY, HOSPITAL_INFORMATION, PRE_ADMISSION, "
        "SYMPTOM_GUIDANCE, HUMAN_ESCALATION, EMERGENCY_GUIDANCE, THANK_YOU, GOODBYE, UNKNOWN.\n\n"
        f"Respond in the patient language: {language}. "
        "Be concise, warm and professional. Keep WhatsApp reply under 250 words. "
        "Use *bold* sparingly. No markdown headers. "
        "set route_to_handler=true only for transactional intents needing backend action "
        "(BOOK_APPOINTMENT, CANCEL_APPOINTMENT, RESCHEDULE_APPOINTMENT, DOCTOR_AVAILABILITY, "
        "APPOINTMENT_STATUS, REGISTER_PATIENT, DEPENDENT_PATIENT). "
        "set route_to_handler=false for HOSPITAL_INFORMATION, SYMPTOM_GUIDANCE, GREETING, "
        "THANK_YOU, GOODBYE, general questions."
    )

    prompt = (
        f"Conversation history:\n{history_ctx}\n\n"
        f"Session state (prior intent: {prior_intent}): {session_ctx}\n\n"
        f'Patient just said: "{message_text}"\n\n'
        'Respond ONLY with a JSON object with these exact keys:\n'
        '{"intent":"<intent>","response":"<WhatsApp reply>","confidence":"HIGH|MEDIUM|LOW",'
        '"route_to_handler":true|false,"detected_department":"<dept or null>",'
        '"detected_doctor":"<doctor name or null>","detected_date":"<date or null>","detected_time":"<time or null>"}'
    )

    raw = None
    if LLM_PROVIDER in ["gemini", "google"]:
        raw = _call_gemini_freetext(prompt, system_instruction)
    elif LLM_PROVIDER == "openai":
        raw = _call_openai_api(prompt)

    if not raw:
        return {"intent": "UNKNOWN", "response": None, "confidence": "LOW", "route_to_handler": False}

    try:
        clean = raw.strip()
        if clean.startswith("```"):
            import re as _re
            clean = _re.sub(r"^```[a-z]*\n?", "", clean)
            clean = _re.sub(r"\n?```$", "", clean)
        parsed = json.loads(clean)
        print(f"[LLM] Fallback: intent={parsed.get('intent')}, conf={parsed.get('confidence')}, route={parsed.get('route_to_handler')}")
        return {
            "intent": parsed.get("intent", "UNKNOWN"),
            "response": parsed.get("response"),
            "confidence": parsed.get("confidence", "LOW"),
            "route_to_handler": bool(parsed.get("route_to_handler", False)),
            "detected_department": parsed.get("detected_department"),
            "detected_doctor": parsed.get("detected_doctor"),
            "detected_date": parsed.get("detected_date"),
            "detected_time": parsed.get("detected_time"),
        }
    except Exception as e:
        print(f"[LLM] Fallback JSON parse error: {e} | Raw: {raw[:300]}")
        return {"intent": "UNKNOWN", "response": None, "confidence": "LOW", "route_to_handler": False}
