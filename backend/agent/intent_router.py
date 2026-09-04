"""
intent_router.py
================
Patient Intent Router Agent for Meridian Hospital AI Patient Desk.

Architecture (updated — LLM-first):
  WhatsApp Webhook / Input Message
  -> Conversation Manager (agent_service.py)
  -> LLM Patient Intent Router  [PRIMARY]  (llm_intent_router.py)
      → if LLM unavailable or fails →
  -> Rule-Based Intent Router    [FALLBACK] (this module)
  -> Structured Intent/Context JSON
  -> Domain Agent / Service Handlers
  -> Database / Business Services
  -> Response

This module provides:
  - route_patient_message()       — deterministic rule-based router (FALLBACK)
  - route_patient_message_llm()   — thin wrapper that calls llm_intent_router
                                    (use this from agent_service.py as primary)
  - validate_doctor_department()  — database guard: doctor ↔ department validation
  - Structured logging ([ROUTER])

Supported intents (canonical 12):
  GREETING, PATIENT_REGISTRATION, BOOK_APPOINTMENT, DOCTOR_AVAILABILITY,
  CANCEL_APPOINTMENT, RESCHEDULE_APPOINTMENT, HOSPITAL_INFORMATION,
  APPOINTMENT_CONFIRMATION, APPOINTMENT_STATUS, PATIENT_DETAILS_UPDATE,
  DEPENDENT_BOOKING, UNKNOWN
"""

import sys
import os
import re
import json
import datetime
from typing import Dict, Any, Optional, List, Tuple

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.intent_detector as intent_detector
import agent.entity_extractor as entity_extractor
import agent.date_normalizer as date_normalizer
import agent.language_service as language_service
import agent.llm_service as llm_service


# Controlled Department Mapping Layer (Must match DB department_name)
DEPARTMENT_SYMPTOM_MAP = {
    "Dermatology": [
        "hair loss", "hair fall", "losing hair", "hair falling", "hair problem",
        "hair shedding", "hair is falling", "hair falls", "my hair is falling",
        "losing my hair", "am losing my hair", "i am losing my hair",
        "hair coming out", "hair came out", "hair drop", "thinning hair",
        "going bald", "getting bald",
        "bald", "baldness", "bald patches", "dandruff",
        "acne", "pimples", "skin rash", "skin allergy", "skin problem",
        "eczema", "psoriasis", "itching", "skin itching", "scalp", "itchy", "skin is itchy", "my skin is itchy", "itchy skin"
    ],
    "General Medicine": [
        "fever", "high fever", "cold", "cough", "flu", "viral fever",
        "general weakness", "body pain", "body ache", "fatigue", "vomiting",
        "diarrhea", "headache", "migraine", "stomach pain", "stomach ache",
        "nausea", "dizziness", "don't feel well", "not feeling well", "feel unwell", "unwell", "ill", "i have pain", "pain"
    ],
    "Cardiology": [
        "chest pain", "chest hurts", "my chest hurts", "chest hurting", "chest ache", "heart pain", "heart problem", "palpitations",
        "high blood pressure", "hypertension", "angina"
    ],
    "Pediatrics": [
        "child fever", "baby fever", "pediatric", "child health",
        "child growth", "infant illness", "kid fever", "child cold", "my son", "for my son", "my daughter", "for my daughter", "son", "daughter"
    ],
    "Orthopedics": [
        "joint pain", "bone pain", "fracture", "back pain", "knee pain",
        "leg pain", "shoulder pain", "arthritis", "spine pain"
    ],
    "ENT": [
        "ear pain", "earache", "hearing problem", "hearing loss",
        "sinus", "sinusitis", "throat problem", "sore throat", "tonsils",
        "nasal congestion", "running nose"
    ],
    "Gynecology": [
        "pregnancy", "pregnant", "period pain", "menstrual problem",
        "gynecology", "obstetrics", "women health"
    ],
    "Neurology": [
        "seizure", "numbness", "paralysis", "memory loss", "neurological"
    ]
}

EMERGENCY_SYMPTOMS = [
    "chest pain", "can't breathe", "cannot breathe", "not breathing",
    "severe breathing problem", "breathing difficulty", "shortness of breath",
    "unconscious", "unconsciousness", "severe bleeding", "major bleeding",
    "stroke symptoms", "heart attack", "choking"
]

# Canonical 12 intents (aligned with llm_intent_router.SUPPORTED_INTENTS)
SUPPORTED_INTENTS = {
    "GREETING",
    "PATIENT_REGISTRATION",
    "BOOK_APPOINTMENT",
    "DOCTOR_AVAILABILITY",
    "CANCEL_APPOINTMENT",
    "RESCHEDULE_APPOINTMENT",
    "HOSPITAL_INFORMATION",
    "APPOINTMENT_CONFIRMATION",
    "APPOINTMENT_STATUS",
    "PATIENT_DETAILS_UPDATE",
    "DEPENDENT_BOOKING",
    "UNKNOWN",
    # Legacy / passthrough intents (kept for backward compat)
    "CHECK_DOCTOR_AVAILABILITY",
    "PRE_ADMISSION",
    "HUMAN_ESCALATION",
    "EMERGENCY",
}


def log_router_action(msg: str) -> None:
    """Prints structured audit log for Intent Router."""
    print(f"[ROUTER] {msg}")


def route_patient_message_llm(
    message_text: str,
    current_state: Optional[dict] = None,
    conversation_history: Optional[List] = None,
) -> dict:
    """
    PRIMARY router entry point (LLM-first).

    Delegates to llm_intent_router.route_patient_message_llm().
    If LLM is unavailable or fails, falls back to the deterministic
    rule-based route_patient_message() in this module.

    Logs:
      - original patient message
      - conversation state summary
      - LLM structured response
      - selected intent
      - extracted department
      - confidence
      - downstream agent
      - final response
    """
    import agent.llm_intent_router as llm_intent_router

    msg_clean = (message_text or "").strip()
    log_router_action(f"[PRIMARY] Input: \"{msg_clean}\"")
    log_router_action(
        f"[PRIMARY] Prior intent: {(current_state or {}).get('intent', 'None')} | "
        f"Dept: {(current_state or {}).get('department_name', 'None')}"
    )

    result = llm_intent_router.route_patient_message_llm(
        message_text=msg_clean,
        current_state=current_state or {},
        conversation_history=conversation_history or [],
    )

    log_router_action(
        f"[PRIMARY] Intent: {result.get('intent')} | "
        f"Department: {result.get('department')} | "
        f"Confidence: {result.get('confidence')} | "
        f"LLM-powered: {result.get('_llm_powered', False)} | "
        f"Downstream: {result.get('intent')}_HANDLER"
    )
    if result.get('needs_clarification'):
        log_router_action(f"[PRIMARY] Clarification needed: {result.get('clarification_question')}")
    if result.get('emergency'):
        log_router_action(f"[PRIMARY] ⚠️  EMERGENCY flagged by LLM router")

    return result


def check_emergency(message_text: str) -> bool:
    """Returns True if message contains an emergency symptom phrase."""
    msg_clean = message_text.lower().strip()
    return any(s in msg_clean for s in EMERGENCY_SYMPTOMS) or (intent_detector.detect_intent(message_text) == "EMERGENCY_GUIDANCE")



SPECIALIST_MAP = {
    "dermatologist": "Dermatology",
    "dermatology": "Dermatology",
    "derma": "Dermatology",
    "general physician": "General Medicine",
    "general doctor": "General Medicine",
    "physician": "General Medicine",
    "general medicine": "General Medicine",
    "genearl medicine": "General Medicine",
    "generel medicine": "General Medicine",
    "genral medicine": "General Medicine",
    "gen medicine": "General Medicine",
    "gen med": "General Medicine",
    "cardiologist": "Cardiology",
    "cardiology": "Cardiology",
    "cardilogy": "Cardiology",
    "pediatrician": "Pediatrics",
    "pediatrics": "Pediatrics",
    "pediatrix": "Pediatrics",
    "orthopedist": "Orthopedics",
    "orthopedic": "Orthopedics",
    "orthopedics": "Orthopedics",
    "orthopaedics": "Orthopedics",
    "ent specialist": "ENT",
    "ent doctor": "ENT",
    "ent": "ENT",
    "gynecologist": "Gynecology",
    "gynecology": "Gynecology",
    "neurologist": "Neurology",
    "neurology": "Neurology"
}


def map_symptom_to_department(message_text: str, is_child: bool = False) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Maps natural language text to a canonical DB department, medical reason, and symptoms list.
    """
    msg_lower = message_text.lower().strip()
    found_symptoms = []
    mapped_department = None
    medical_reason = None

    # Check Specialist titles first
    for spec_key, dept_val in SPECIALIST_MAP.items():
        if re.search(r"\b" + re.escape(spec_key) + r"\b", msg_lower):
            mapped_department = dept_val
            medical_reason = f"{dept_val} consultation"
            break

    if not mapped_department:
        # Check Dermatology FIRST (hair, skin, scalp)
        for sym in DEPARTMENT_SYMPTOM_MAP["Dermatology"]:
            if sym in msg_lower:
                found_symptoms.append(sym)
                if not mapped_department:
                    mapped_department = "Dermatology"
                    medical_reason = sym

    # Next check specific departments (General Medicine LAST)
    if not mapped_department:
        SPECIFIC_DEPTS = ["Pediatrics", "Orthopedics", "Cardiology", "ENT", "Gynecology", "Neurology", "General Medicine"]
        for dept in SPECIFIC_DEPTS:
            sym_list = DEPARTMENT_SYMPTOM_MAP.get(dept, [])
            for sym in sym_list:
                if sym in msg_lower:
                    found_symptoms.append(sym)
                    if not mapped_department:
                        mapped_department = dept
                        medical_reason = sym

    # Explicit department keyword check
    if not mapped_department:
        dept_entities = entity_extractor.extract_entities(message_text)
        if dept_entities.get("department_name"):
            mapped_department = dept_entities["department_name"]
            medical_reason = message_text

    # Pediatrics override for child if general medicine or child symptoms
    if is_child and (mapped_department == "General Medicine" or not mapped_department):
        mapped_department = "Pediatrics"

    if not medical_reason and found_symptoms:
        medical_reason = found_symptoms[0]
    elif not medical_reason and message_text:
        medical_reason = message_text[:50].strip()

    return mapped_department, medical_reason, found_symptoms


def validate_doctor_department(doctor_id: int, target_department_name: str) -> bool:
    """
    Database guard: Ensures specified doctor belongs to the target department in PostgreSQL.
    Returns False if doctor is from a different department.
    """
    if not doctor_id or not target_department_name:
        return True

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT d.id, dept.department_name
            FROM doctors d
            JOIN departments dept ON d.department_id = dept.id
            WHERE d.id = %s AND d.status = 'ACTIVE';
        """, (doctor_id,))
        row = cur.fetchone()
        if not row:
            log_router_action(f"Doctor validation: Doctor ID {doctor_id} not found or inactive. Validation: FAILED")
            return False

        doc_dept = row[1]
        is_match = (doc_dept.lower() == target_department_name.lower())
        status_str = "PASSED" if is_match else "FAILED"
        log_router_action(f"Doctor validation: Requested department: {target_department_name} | Selected doctor department: {doc_dept} | Validation: {status_str}")
        return is_match
    except Exception as e:
        log_router_action(f"Doctor validation DB error: {e}")
        return False
    finally:
        cur.close()
        conn.close()


def route_patient_message(message_text: str, current_state: Optional[dict] = None) -> dict:
    """
    Main Patient Intent Router Agent.
    Analyzes incoming patient message and returns structured JSON context.
    """
    if current_state is None:
        current_state = {}

    msg_clean = message_text.strip()
    msg_lower = msg_clean.lower()

    # 1. Priority 0 Emergency Safety Evaluation
    if check_emergency(msg_clean):
        log_router_action(f"Input: \"{msg_clean}\" | Intent: EMERGENCY | Medical Reason: Emergency | Department: EMERGENCY | Confidence: 1.0")
        return {
            "intent": "EMERGENCY",
            "sub_intent": "SAFETY_OVERRIDE",
            "language": "ENGLISH",
            "symptoms": ["emergency"],
            "medical_reason": "Emergency Medical Situation",
            "department": "EMERGENCY",
            "patient_type": current_state.get("patient_type", "EXISTING"),
            "appointment_for": current_state.get("appointment_for", "SELF"),
            "relationship": current_state.get("patient_relationship"),
            "date": None,
            "time": None,
            "dob": None,
            "confidence": 1.0,
            "emergency": True,
            "entities": {}
        }

    # 2. Language Detection
    lang = language_service.detect_language(msg_clean)

    # 3. Base Intent Detector
    raw_intent = intent_detector.detect_intent(msg_clean, current_state.get("intent"))

    # 4. Dependent / Family Member Context Extraction
    rel_info = entity_extractor.extract_relationship(msg_clean)
    appointment_for = rel_info.get("appointment_for") or current_state.get("appointment_for") or "SELF"
    relationship = rel_info.get("relationship") or current_state.get("patient_relationship")
    is_child = (appointment_for == "CHILD" or relationship in ["SON", "DAUGHTER", "CHILD", "KID"])

    # 5. Symptom & Department Mapping
    dept, medical_reason, symptoms = map_symptom_to_department(msg_clean, is_child=is_child)
    if not dept and current_state.get("department_name"):
        dept = current_state["department_name"]

    # 6. Date, Time & DOB Extraction
    extracted_entities = entity_extractor.extract_entities(msg_clean)
    
    extracted_date = extracted_entities.get("appointment_date")
    norm_d, is_ambig_d, _ = date_normalizer.parse_and_normalize_date(msg_clean)
    if norm_d and not re.search(r"\b(19\d\d|200\d|201\d)\b", msg_clean):
        extracted_date = norm_d

    extracted_time = extracted_entities.get("appointment_time")

    # DOB extraction if date pattern matches past year/DOB context
    extracted_dob = None
    if re.search(r"\b(19\d\d|200\d|201\d)\b", msg_clean) or "dob" in msg_lower or "born" in msg_lower:
        is_valid_dob, norm_dob, _ = date_normalizer.validate_dob(msg_clean, allow_ambiguous=True)
        if is_valid_dob and norm_dob:
            extracted_dob = norm_dob

    # 7. Map Raw Intent to 12 Supported Router Intents
    router_intent = "UNKNOWN"
    sub_intent = None

    if any(p in msg_lower for p in ["move my appointment", "change my appointment", "reschedule my appointment", "reschedule appointment"]):
        router_intent = "RESCHEDULE_APPOINTMENT"
    elif raw_intent in ["GREETING", "THANK_YOU", "GOODBYE"]:
        router_intent = "GREETING"
    elif raw_intent in ["REGISTER_PATIENT", "IDENTIFY_PATIENT"]:
        router_intent = "PATIENT_REGISTRATION"
    elif raw_intent in ["BOOK_APPOINTMENT", "APPOINTMENT_TIME", "APPOINTMENT_DATE", "DEPENDENT_PATIENT"]:
        router_intent = "BOOK_APPOINTMENT"
        if raw_intent == "DEPENDENT_PATIENT" or appointment_for == "CHILD":
            sub_intent = "DEPENDENT_BOOKING"
    elif raw_intent == "DOCTOR_AVAILABILITY":
        router_intent = "CHECK_DOCTOR_AVAILABILITY"
    elif raw_intent == "CANCEL_APPOINTMENT":
        router_intent = "CANCEL_APPOINTMENT"
    elif raw_intent == "RESCHEDULE_APPOINTMENT":
        router_intent = "RESCHEDULE_APPOINTMENT"
    elif raw_intent in ["HOSPITAL_INFORMATION", "DEPARTMENT_INFORMATION"]:
        router_intent = "HOSPITAL_INFORMATION"
    elif raw_intent == "PRE_ADMISSION":
        router_intent = "PRE_ADMISSION"
    elif raw_intent == "APPOINTMENT_STATUS":
        router_intent = "APPOINTMENT_STATUS"
    elif raw_intent == "HUMAN_ESCALATION":
        router_intent = "HUMAN_ESCALATION"
    elif raw_intent == "SYMPTOM_GUIDANCE":
        router_intent = "BOOK_APPOINTMENT"
        sub_intent = "SYMPTOM_GUIDANCE"
    elif raw_intent == "DEPENDENT_BOOKING":
        router_intent = "DEPENDENT_BOOKING"
    elif raw_intent == "APPOINTMENT_CONFIRMATION":
        router_intent = "APPOINTMENT_CONFIRMATION"
    elif raw_intent == "PATIENT_REGISTRATION":
        router_intent = "PATIENT_REGISTRATION"
    elif raw_intent == "PATIENT_DETAILS_UPDATE":
        router_intent = "PATIENT_DETAILS_UPDATE"

    # Context Retention Rule: If in active BOOK_APPOINTMENT flow and patient provides symptom/date/time
    curr_intent = current_state.get("intent")
    if curr_intent == "BOOK_APPOINTMENT" and router_intent in ["UNKNOWN", "GREETING", "HOSPITAL_INFORMATION"] and (symptoms or dept or extracted_date or extracted_time):
        router_intent = "BOOK_APPOINTMENT"

    # Natural Language Phrases Fallbacks
    if router_intent == "UNKNOWN":
        if any(p in msg_lower for p in ["see a doctor", "consult someone", "book a doctor", "need an appointment", "want an appointment", "book appointment"]):
            router_intent = "BOOK_APPOINTMENT"
        elif any(p in msg_lower for p in ["connect me with staff", "talk to human", "speak with receptionist", "need help"]):
            router_intent = "HUMAN_ESCALATION"
        elif any(p in msg_lower for p in ["cancel my appointment", "cancel appointment"]):
            router_intent = "CANCEL_APPOINTMENT"
        elif any(p in msg_lower for p in ["move my appointment", "change my appointment"]):
            router_intent = "RESCHEDULE_APPOINTMENT"
        elif any(p in msg_lower for p in ["who is available", "doctors are available"]):
            router_intent = "CHECK_DOCTOR_AVAILABILITY"

    patient_type = "FIRST_TIME" if "first" in msg_lower else "EXISTING"
    confidence = 0.98 if router_intent != "UNKNOWN" else 0.50

    log_router_action(
        f"Input: \"{msg_clean}\" | Intent: {router_intent} | Medical Reason: {medical_reason or 'None'} | "
        f"Department: {dept or 'None'} | Confidence: {confidence}"
    )

    if appointment_for == "CHILD":
        log_router_action(f"Input: \"{msg_clean}\" | Intent: BOOK_APPOINTMENT | Appointment For: CHILD | Relationship: {relationship}")

    return {
        "intent": router_intent,
        "sub_intent": sub_intent,
        "language": lang,
        "symptoms": symptoms,
        "medical_reason": medical_reason or "",
        "department": dept,
        "patient_type": patient_type,
        "appointment_for": appointment_for,
        "relationship": relationship,
        "date": extracted_date,
        "time": extracted_time,
        "dob": extracted_dob,
        "confidence": confidence,
        "emergency": False,
        "entities": extracted_entities
    }

