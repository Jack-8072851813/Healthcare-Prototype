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
    model_name = LLM_MODEL
    if "2.5" in model_name:
        model_name = "gemini-1.5-flash"
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
        print(f"[LLM] Gemini API call error: {e}")
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
        "first_name": None,
        "last_name": None,
        "date_of_birth": None,
        "gender": None,
        "phone": None,
        "department": None,
        "doctor": None,
        "appointment_date": None,
        "appointment_time": None,
        "booking_id": None,
        "reason": None,
        "confidence": 0.95
    }

    # Attempt LLM extraction if active
    if is_llm_active():
        prompt = f"""
        Extract structured information from the following patient WhatsApp message for a hospital desk assistant.

        Context Intent: {current_state.get('intent')}
        Patient Language: {language}

        Message: "{message_text}"

        Return a strictly valid JSON object with the following fields:
        {{
          "intent": "BOOK_APPOINTMENT" | "REGISTER_PATIENT" | "IDENTIFY_PATIENT" | "CANCEL_APPOINTMENT" | "RESCHEDULE_APPOINTMENT" | "APPOINTMENT_STATUS" | "DOCTOR_AVAILABILITY" | "HOSPITAL_INFORMATION" | "DEPARTMENT_INFORMATION" | "SYMPTOM_GUIDANCE" | "PRE_ADMISSION" | "HUMAN_ESCALATION" | "GREETING",
          "patient_type": "FIRST_TIME" | "EXISTING" | null,
          "first_name": string or null,
          "last_name": string or null,
          "date_of_birth": string or null (e.g. "1995-08-15" or natural date),
          "gender": "Male" | "Female" | "Other" | null,
          "phone": string or null,
          "department": string or null,
          "doctor": string or null,
          "appointment_date": string or null (e.g. "tomorrow", "2026-09-02"),
          "appointment_time": string or null (e.g. "10:30 AM", "Morning"),
          "booking_id": string or null,
          "reason": string or null
        }}
        """
        raw_llm = None
        if LLM_PROVIDER in ["gemini", "google"]:
            raw_llm = _call_gemini_api(prompt)
        elif LLM_PROVIDER == "openai":
            raw_llm = _call_openai_api(prompt)

        if raw_llm:
            try:
                parsed = json.loads(raw_llm)
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

    # 3. Entity Extractor lookup (doctor, department, date, time, booking_id, symptoms)
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
        # Resolve doctor display name
        from agent.agent_service import resolve_doctor_details
        doc_info = resolve_doctor_details(rule_entities["doctor_id"])
        extracted_data["doctor"] = doc_info["name"]
        extracted_data["department"] = doc_info["department"]

    # 4. Multi-field Registration extraction (Name, DOB, Gender, Phone)
    if current_state.get("intent") == "REGISTER_PATIENT" or extracted_data["intent"] == "REGISTER_PATIENT":
        # Extract phone
        match_phone = re.search(r"\b(\d{10,12})\b", text_lower)
        if match_phone:
            extracted_data["phone"] = match_phone.group(1)

        # Extract gender
        if re.search(r"\b(male|man|m)\b", text_lower):
            extracted_data["gender"] = "Male"
        elif re.search(r"\b(female|woman|f)\b", text_lower):
            extracted_data["gender"] = "Female"
        elif re.search(r"\b(other)\b", text_lower):
            extracted_data["gender"] = "Other"

        # Normalize DOB
        norm_dob, is_ambig, _ = date_normalizer.parse_and_normalize_date(text_clean)
        if norm_dob:
            extracted_data["date_of_birth"] = norm_dob

        # Multi-field name extraction if comma/newline separated
        parts = [p.strip() for p in re.split(r"[,;\n]+", text_clean) if p.strip()]
        if len(parts) >= 2:
            potential_name = parts[0]
            # Avoid using keywords as name
            if not any(kw in potential_name.lower() for kw in ["register", "my name", "dob", "phone", "male", "female"]):
                name_words = potential_name.split()
                extracted_data["first_name"] = name_words[0].capitalize()
                if len(name_words) > 1:
                    extracted_data["last_name"] = " ".join(name_words[1:]).capitalize()
                else:
                    extracted_data["last_name"] = "User"

        # Also match "My name is X"
        match_name = re.search(r"my name is ([a-zA-Z\s]+)", text_lower)
        if match_name:
            n_str = match_name.group(1).strip()
            name_words = n_str.split()
            extracted_data["first_name"] = name_words[0].capitalize()
            if len(name_words) > 1:
                extracted_data["last_name"] = " ".join(name_words[1:]).capitalize()

    return extracted_data
