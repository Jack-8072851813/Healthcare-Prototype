import sys
import os
import datetime
import re

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.intent_detector as intent_detector
import agent.entity_extractor as entity_extractor
import agent.state_manager as state_manager
import agent.language_service as language_service
import agent.safety_service as safety_service
import agent.tool_registry as tool_registry
import knowledge.knowledge_service as knowledge_service
import agent.llm_service as llm_service
import agent.date_normalizer as date_normalizer

def log_message_to_db(conversation_code: str, sender_type: str, message_text: str, language: str, intent: str, metadata: dict = None):
    """Inserts a conversation message into the messages table."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM conversations WHERE conversation_code = %s;", (conversation_code,))
        row = cur.fetchone()
        if not row:
            return
        conv_id = row[0]
        
        # Valid sender types check constraint
        valid_senders = ['PATIENT', 'AI_AGENT', 'SYSTEM', 'ADMIN', 'DOCTOR']
        db_sender = sender_type if sender_type in valid_senders else 'AI_AGENT'
        
        # Write to messages table
        import json
        cur.execute("""
            INSERT INTO messages (conversation_id, sender_type, message_type, message_text, language, intent, metadata)
            VALUES (%s, %s, 'TEXT', %s, %s, %s, %s);
        """, (conv_id, db_sender, message_text, language, intent, json.dumps(metadata) if metadata else None))
        conn.commit()
    except Exception as e:
        print("Failed to log message to DB:", str(e))
    finally:
        cur.close()
        conn.close()

def resolve_doctor_details(doctor_id: int) -> dict:
    """Helper to query doctor name and department from the database."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT d.display_name, dept.department_name 
            FROM doctors d
            JOIN departments dept ON d.department_id = dept.id
            WHERE d.id = %s;
        """, (doctor_id,))
        row = cur.fetchone()
        if row:
            return {"name": row[0], "department": row[1]}
        return {"name": "Doctor", "department": "General Medicine"}
    finally:
        cur.close()
        conn.close()

def process_agent_message(conversation_code: str, patient_code: str, message_text: str, language_override: str = None) -> dict:
    """
    Core NLP Orchestration:
    1. Loads or initializes state.
    2. Runs medical safety checks.
    3. Handles language preferences.
    4. Detects intent and extracts entities.
    5. Dispatches tools or queries missing slots.
    6. Logs the conversational steps and returns the response payload.
    """
    # 1. Load conversation state
    state = state_manager.get_conversation_state(conversation_code)
    
    # Resolve patient ID from patient_code if passed from the payload
    if not state.get("patient_id") and patient_code:
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id FROM patients WHERE patient_code = %s AND status = 'ACTIVE';", (patient_code,))
            row = cur.fetchone()
            if row:
                state["patient_id"] = row[0]
                state["entities"]["patient_id"] = row[0]
                cur.execute("UPDATE conversations SET patient_id = %s WHERE conversation_code = %s;", (row[0], conversation_code))
                conn.commit()
        except Exception as e:
            conn.rollback()
            print("Failed to resolve patient code:", e)
        finally:
            cur.close()
            conn.close()

    # Pre-resolve patient ID from active phone if not associated yet
    if not state.get("patient_id"):
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
            row = cur.fetchone()
            if row:
                w_num = row[0]
                cur.execute("SELECT id, patient_code FROM patients WHERE (phone = %s OR whatsapp_number = %s) AND status = 'ACTIVE' LIMIT 1;", (w_num, w_num))
                p_row = cur.fetchone()
                if p_row:
                    state["patient_id"] = p_row[0]
                    state["entities"]["patient_id"] = p_row[0]
                    cur.execute("UPDATE conversations SET patient_id = %s WHERE conversation_code = %s;", (p_row[0], conversation_code))
                    conn.commit()
        except Exception as e:
            conn.rollback()
            print("Failed to auto-resolve patient by phone:", e)
        finally:
            cur.close()
            conn.close()

    # Apply override if specified
    if language_override:
        state["language"] = language_override.upper()
        
    current_lang = state["language"]

    # Log incoming patient message
    # Detect intent of this single turn for audit
    turn_intent = intent_detector.detect_intent(message_text, state["intent"])
    log_message_to_db(conversation_code, "PATIENT", message_text, current_lang, turn_intent)

    # 2. Medical Safety Check
    safety_response = safety_service.check_medical_safety(message_text, current_lang)
    if safety_response:
        # Override intent to EMERGENCY_GUIDANCE if chest pain, etc.
        turn_is_emergency = intent_detector.detect_intent(message_text, state["intent"]) == "EMERGENCY_GUIDANCE"
        final_intent = "EMERGENCY_GUIDANCE" if turn_is_emergency else "SYMPTOM_GUIDANCE"
        log_message_to_db(conversation_code, "AI_AGENT", safety_response, current_lang, final_intent, state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": current_lang,
            "intent": final_intent,
            "response": safety_response,
            "missing_information": [],
            "tool_called": None
        }

    # 3. Language Shift Detection
    lang_shift = language_service.detect_language_shift(message_text)
    if lang_shift:
        state["language"] = lang_shift
        state["intent"] = "LANGUAGE_CHANGE"
        lang_msg = language_service.translate_response("LANGUAGE_CHANGED", lang_shift)
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", lang_msg, lang_shift, "LANGUAGE_CHANGE", state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": lang_shift,
            "intent": "LANGUAGE_CHANGE",
            "response": lang_msg,
            "missing_information": [],
            "tool_called": None
        }

    # 4. Intent & Entity processing
    detected_intent = intent_detector.detect_intent(message_text, state["intent"])
    
    # Contextual Confirmation Handling (YES/NO)
    msg_cleaned = message_text.lower().strip()
    is_affirmative = msg_cleaned in ["yes", "sure", "ok", "okay", "please do", "yes please", "yeah", "yup", "சரி", "ஆம்", "हाँ", "हाँ जी", "అవును", "ശരി", "അതെ", "ಹೌದು", "جی", "جی ہاں"]
    is_negative = msg_cleaned in ["no", "no thanks", "not now", "nope", "nay", "இல்லை", "வேண்டாம்", "नहीं", "नहीं धन्यवाद", "వద్దు", "లేదు", "വേണ്ട", "ഇല്ല", "ಬೇಡ", "ಇಲ್ಲ", "نہیں"]
    
    # OK clean text fallback if no question active
    if msg_cleaned in ["ok", "okay"] and not state.get("previous_question"):
        state["intent"] = "GREETING"
        log_message_to_db(conversation_code, "AI_AGENT", "Sure. How can I help you?", current_lang, "GREETING", state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": current_lang,
            "intent": "GREETING",
            "response": "Sure. How can I help you?",
            "missing_information": [],
            "tool_called": None
        }

    if (is_affirmative or is_negative) and state.get("previous_question") and state["intent"] not in ["REGISTER_PATIENT", "IDENTIFY_PATIENT"]:
        prev_q = state["previous_question"]
        if is_affirmative:
            if prev_q == "would_you_like_to_check_available_doctors":
                detected_intent = "BOOK_APPOINTMENT"
                state["intent"] = "BOOK_APPOINTMENT"
                state["previous_question"] = None
            elif prev_q == "would_you_like_to_book_this_appointment":
                detected_intent = "BOOK_APPOINTMENT"
                state["intent"] = "BOOK_APPOINTMENT"
                state["previous_question"] = None
            elif prev_q == "would_you_like_to_cancel_this_appointment":
                detected_intent = "CANCEL_APPOINTMENT"
                state["intent"] = "CANCEL_APPOINTMENT"
                state["previous_question"] = None
            elif prev_q == "would_you_like_to_reschedule_it":
                detected_intent = "RESCHEDULE_APPOINTMENT"
                state["intent"] = "RESCHEDULE_APPOINTMENT"
                state["previous_question"] = None
            elif prev_q == "would_you_like_to_check_tomorrow_slots":
                import datetime
                import pytz
                ist = pytz.timezone('Asia/Kolkata')
                tomorrow_date = (datetime.datetime.now(ist) + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
                state["entities"]["appointment_date"] = tomorrow_date
                state["entities"]["appointment_time"] = None
                detected_intent = "BOOK_APPOINTMENT"
                state["intent"] = "BOOK_APPOINTMENT"
                state["previous_question"] = None
        elif is_negative:
            detected_intent = "GREETING"
            state["intent"] = "GREETING"
            state["previous_question"] = None
            state["entities"] = {
                "patient_id": state["patient_id"],
                "doctor_id": None,
                "department_id": None,
                "appointment_date": None,
                "appointment_time": None,
                "booking_id": None,
                "reason": None
            }

    # If the user changed the intent, transition state intent
    if detected_intent != "UNKNOWN" and detected_intent != state["intent"]:
        previous_intent = state["intent"]
        state["intent"] = detected_intent
        
        # Clear entities only if transitioning between unrelated transaction types
        clear_pairs = [
            ("BOOK_APPOINTMENT", "CANCEL_APPOINTMENT"),
            ("BOOK_APPOINTMENT", "RESCHEDULE_APPOINTMENT"),
            ("CANCEL_APPOINTMENT", "BOOK_APPOINTMENT"),
            ("CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT"),
            ("RESCHEDULE_APPOINTMENT", "BOOK_APPOINTMENT"),
            ("RESCHEDULE_APPOINTMENT", "CANCEL_APPOINTMENT"),
            ("REGISTER_PATIENT", "BOOK_APPOINTMENT"),
            ("IDENTIFY_PATIENT", "BOOK_APPOINTMENT")
        ]
        if (previous_intent, detected_intent) in clear_pairs:
            state["entities"] = {
                "patient_id": state["patient_id"],
                "doctor_id": None,
                "department_id": None,
                "appointment_date": None,
                "appointment_time": None,
                "booking_id": None,
                "reason": None
            }

    # Extract new entities and merge them
    extracted = entity_extractor.extract_entities(message_text)
    
    # If the user explicitly mentions a NEW doctor or NEW department different from current, clear slot selections
    new_doc_id = extracted.get("doctor_id")
    new_dept_id = extracted.get("department_id")
    curr_doc_id = state["entities"].get("doctor_id")
    curr_dept_id = state["entities"].get("department_id")

    if not state.get("confirmation_pending"):
        if (new_doc_id and new_doc_id != curr_doc_id) or (new_dept_id and new_dept_id != curr_dept_id and not new_doc_id):
            state["entities"]["appointment_date"] = None
            state["entities"]["appointment_time"] = None
            state["entities"]["reason"] = None
            state["previous_question"] = None
        
    for k, v in extracted.items():
        if v is not None:
            state["entities"][k] = v

    # Associate patient_id dynamically if patient_code is provided
    if state["entities"]["patient_id"]:
        state["patient_id"] = state["entities"]["patient_id"]

    # 5. Core Intent Workflows
    intent = state["intent"]
    response_text = ""
    tool_called = None
    missing_info = []

    if intent == "GREETING":
        state["interactive_buttons"] = []
        msg_l = message_text.lower().strip()
        is_first_time = any(w in msg_l for w in ["first time", "first-time", "btn_first_time", "new patient", "1"])
        is_existing = any(w in msg_l for w in ["existing patient", "existing", "btn_existing", "2"])

        if is_first_time:
            state["intent"] = "REGISTER_PATIENT"
            state["patient_type"] = "FIRST_TIME"
            response_text = "Great! I'll help you get registered. Please send the following details together in one message:\n\n• Full name\n• Date of birth\n• Gender\n• Mobile number (if different)\n\nExample:\nArokiya Gilbrit, 15 Aug 1995, Male"
        elif is_existing:
            state["intent"] = "IDENTIFY_PATIENT"
            state["patient_type"] = "EXISTING"
            response_text = "Please enter your Patient Code (e.g. P001), registered mobile number, or full name and date of birth to access your record."
        elif state.get("patient_id"):
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT first_name FROM patients WHERE id = %s;", (state["patient_id"],))
                row = cur.fetchone()
                p_name = row[0] if row else "Patient"
                response_text = f"Welcome back to Meridian Hospital, {p_name}. How can I help you today?"
                state["interactive_buttons"] = [
                    {"id": "btn_book_appt", "title": "Book Appointment"},
                    {"id": "btn_doctor_avail", "title": "Doctor Availability"},
                    {"id": "btn_hosp_info", "title": "Hospital Information"}
                ]
            finally:
                cur.close()
                conn.close()
        else:
            response_text = "Hello! Welcome to Meridian Hospital. I'm your AI Patient Desk Assistant. I can help with appointments, doctor availability, cancellations, hospital information, and pre-admission assistance.\n\nPlease select an option below:"
            state["interactive_buttons"] = [
                {"id": "btn_first_time", "title": "First-time Patient"},
                {"id": "btn_existing", "title": "Existing Patient"}
            ]

    elif intent == "IDENTIFY_PATIENT":
        state["interactive_buttons"] = []
        match_pat = re.search(r"\b(p\d+)\b", message_text.lower())
        match_phone = re.search(r"\b(\d{10,12})\b", message_text.lower())
        resolved_patient = None
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            if match_pat:
                p_code = match_pat.group(1).upper()
                cur.execute("SELECT id, first_name FROM patients WHERE patient_code = %s AND status = 'ACTIVE';", (p_code,))
                resolved_patient = cur.fetchone()
            elif match_phone:
                phone_num = match_phone.group(1)
                cur.execute("SELECT id, first_name FROM patients WHERE (phone = %s OR whatsapp_number = %s) AND status = 'ACTIVE' LIMIT 1;", (phone_num, phone_num))
                resolved_patient = cur.fetchone()
        finally:
            cur.close()
            conn.close()
            
        if resolved_patient:
            pat_id, first_name = resolved_patient
            state["patient_id"] = pat_id
            state["entities"]["patient_id"] = pat_id
            state["intent"] = "GREETING"
            state["previous_question"] = None
            
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("UPDATE conversations SET patient_id = %s WHERE conversation_code = %s;", (pat_id, conversation_code))
                conn.commit()
            except Exception:
                conn.rollback()
            finally:
                cur.close()
                conn.close()
            
            response_text = f"Welcome back to Meridian Hospital, {first_name}. How can I help you today?"
            state["interactive_buttons"] = [
                {"id": "btn_book_appt", "title": "Book Appointment"},
                {"id": "btn_doctor_avail", "title": "Doctor Availability"},
                {"id": "btn_hosp_info", "title": "Hospital Information"}
            ]
        else:
            response_text = "I couldn't find a matching patient record. Please check your patient code (e.g. P001), or are you visiting us for the first time?"
            state["interactive_buttons"] = [
                {"id": "btn_first_time", "title": "First-time Patient"},
                {"id": "btn_existing", "title": "Existing Patient"}
            ]

    elif intent == "REGISTER_PATIENT":
        state["interactive_buttons"] = []
        llm_info = llm_service.extract_structured_info(message_text, state, current_lang)
        reg_fields = state.get("registration_fields") or {
            "first_name": None, "last_name": None, "date_of_birth": None, "gender": None, "phone": None
        }

        # Merge extracted registration fields
        if llm_info.get("first_name"):
            reg_fields["first_name"] = llm_info["first_name"]
            reg_fields["last_name"] = llm_info.get("last_name") or reg_fields.get("last_name") or "."
        if llm_info.get("gender"):
            reg_fields["gender"] = llm_info["gender"]
        if llm_info.get("phone"):
            reg_fields["phone"] = llm_info["phone"]

        # Direct text fallback parsing
        msg_raw = message_text.strip()
        match_phone = re.search(r"\b(\d{10,12})\b", msg_raw)
        if match_phone:
            reg_fields["phone"] = match_phone.group(1)

        intent_keywords = ["register", "registration", "patient", "book", "appointment", "btn_first_time", "btn_existing", "hi", "hello"]
        is_command_msg = any(kw in msg_raw.lower() for kw in intent_keywords)

        if msg_raw.lower() in ["male", "female", "other"]:
            reg_fields["gender"] = msg_raw.capitalize()
        elif not is_command_msg and not reg_fields.get("first_name") and len(msg_raw.split()) in [1, 2] and not any(c.isdigit() for c in msg_raw):
            parts = msg_raw.split(None, 1)
            reg_fields["first_name"] = parts[0].capitalize()
            reg_fields["last_name"] = parts[1].capitalize() if len(parts) > 1 else "."
        elif not is_command_msg and reg_fields.get("first_name") and (reg_fields.get("last_name") in [None, "."]) and len(msg_raw.split()) == 1 and not any(c.isdigit() for c in msg_raw) and msg_raw.lower() not in ["male", "female", "other"]:
            reg_fields["last_name"] = msg_raw.capitalize()

        dob_candidate = llm_info.get("date_of_birth") or message_text
        is_valid_dob, norm_dob, dob_err = date_normalizer.validate_dob(dob_candidate)
        if is_valid_dob and norm_dob:
            reg_fields["date_of_birth"] = norm_dob
        elif dob_err and ("Date of birth" in dob_err or "Ambiguous date" in dob_err or "future" in dob_err):
            if not reg_fields.get("date_of_birth"):
                response_text = dob_err
                state["registration_fields"] = reg_fields
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                return {
                    "success": True,
                    "conversation_id": conversation_code,
                    "language": current_lang,
                    "intent": intent,
                    "response": response_text,
                    "missing_information": ["date_of_birth"],
                    "tool_called": None,
                    "interactive_buttons": []
                }

        conn = db_config.get_db_connection()
        cur = conn.cursor()
        whatsapp_val = "919999999999"
        try:
            cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
            w_row = cur.fetchone()
            if w_row and w_row[0]:
                whatsapp_val = w_row[0]
        finally:
            cur.close()
            conn.close()

        phone_val = reg_fields.get("phone") or (whatsapp_val if whatsapp_val and whatsapp_val != "919999999999" else None)
        if reg_fields.get("first_name") and reg_fields.get("date_of_birth") and reg_fields.get("gender") and phone_val:
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT patient_code FROM patients ORDER BY id DESC LIMIT 1;")
                row = cur.fetchone()
                next_code = "P011"
                if row:
                    last_code = row[0]
                    match = re.search(r"P(\d+)", last_code)
                    if match:
                        next_code = f"P{int(match.group(1)) + 1:03d}"

                cur.execute("""
                    INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
                    RETURNING id;
                """, (
                    next_code,
                    reg_fields["first_name"],
                    reg_fields["last_name"] or ".",
                    reg_fields["date_of_birth"],
                    reg_fields["gender"],
                    phone_val,
                    whatsapp_val
                ))
                new_pat_id = cur.fetchone()[0]
                cur.execute("UPDATE conversations SET patient_id = %s WHERE conversation_code = %s;", (new_pat_id, conversation_code))
                conn.commit()

                state["patient_id"] = new_pat_id
                state["entities"]["patient_id"] = new_pat_id
                state["intent"] = "GREETING"
                state["registration_fields"] = { "first_name": None, "last_name": None, "date_of_birth": None, "gender": None, "phone": None }
                response_text = f"Your registration is complete. Your patient code is {next_code}. How can I help you today?"
                state["interactive_buttons"] = [
                    {"id": "btn_book_appt", "title": "Book Appointment"},
                    {"id": "btn_doctor_avail", "title": "Doctor Availability"},
                    {"id": "btn_hosp_info", "title": "Hospital Information"}
                ]
            except Exception as e:
                conn.rollback()
                response_text = f"Registration failed: {str(e)}"
            finally:
                cur.close()
                conn.close()
        else:
            missing_req = []
            if not reg_fields.get("first_name"): missing_req.append("Full name")
            if not reg_fields.get("date_of_birth"): missing_req.append("Date of birth")
            if not reg_fields.get("gender"): missing_req.append("Gender")
            if not phone_val: missing_req.append("Mobile number")
            response_text = f"Great! I'll help you get registered. Please send the following details together:\n\n• " + "\n• ".join(missing_req) + "\n\nExample: Arokiya Gilbrit, 15 Aug 1995, Male"
            state["interactive_buttons"] = []

    elif intent == "EMERGENCY_GUIDANCE":
        response_text = language_service.translate_response("EMERGENCY_GUIDANCE", current_lang)
        
    elif intent == "HUMAN_ESCALATION":
        response_text = language_service.translate_response("HUMAN_ESCALATION", current_lang)
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            # Update conversation status and get conversation and patient DB IDs
            cur.execute("UPDATE conversations SET conversation_status = 'ESCALATED' WHERE conversation_code = %s RETURNING id, patient_id;", (conversation_code,))
            row = cur.fetchone()
            if row:
                conv_db_id, pat_db_id = row
                # Check for existing open escalation to avoid duplicates
                cur.execute("SELECT id FROM escalations WHERE conversation_id = %s AND status = 'OPEN';", (conv_db_id,))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO escalations (conversation_id, patient_id, escalation_reason, patient_question)
                        VALUES (%s, %s, 'Patient requested human staff escalation.', %s);
                    """, (conv_db_id, pat_db_id, message_text))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print("Failed to record escalation in database:", e)
        finally:
            cur.close()
            conn.close()

    elif intent == "SYMPTOM_GUIDANCE":
        symptoms_department_rules = [
            # ENT (Ear, Nose, Throat)
            (r"\b(nose|nasal|sinus|ear|earache|throat|tonsil|snoring|smell|voice|hearing|otitis|rhinitis)\b", "ENT"),
            # Cardiology
            (r"\b(chest\s*pain|heart|cardio|cardiac|palpitations|breathlessness|chest\s*tightness|blood\s*pressure|hypertension)\b", "Cardiology"),
            # Neurology
            (r"\b(migraine|severe\s*headache|dizziness|vertigo|seizure|numbness|paralysis|nerve|brain|head\s*injury)\b", "Neurology"),
            # Orthopedics
            (r"\b(joint|bone|back|backache|knee|spine|leg\s*pain|fracture|shoulder|neck\s*pain|arthritis|sprain|ligament)\b", "Orthopedics"),
            # Dermatology
            (r"\b(skin|rash|itching|itch|eczema|acne|psoriasis|allergy|skin\s*infection|hives|dermatitis)\b", "Dermatology"),
            # Pediatrics
            (r"\b(child|baby|infant|toddler|newborn|kid|pediatric)\b", "Pediatrics"),
            # Gynecology
            (r"\b(pregnancy|pregnant|period|menstrual|menstruation|pelvic|uterine|ovary|women\s*health)\b", "Gynecology"),
            # General Medicine (fallback for general symptoms)
            (r"\b(fever|cold|cough|stomach|flu|nausea|vomiting|diarrhea|headache|fatigue|weakness|body\s*pain|feverish|pain)\b", "General Medicine")
        ]
        
        resolved_dept = "General Medicine"
        msg_l = message_text.lower()
        for pattern, dept in symptoms_department_rules:
            if re.search(pattern, msg_l):
                resolved_dept = dept
                break
                
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM departments WHERE department_name = %s AND status = 'ACTIVE';", (resolved_dept,))
        row = cur.fetchone()
        dept_id = row[0] if row else 1
        cur.close()
        conn.close()
        
        response_text = language_service.translate_response("SYMPTOM_GUIDANCE", current_lang, dept=resolved_dept)
        state["previous_question"] = "would_you_like_to_check_available_doctors"
        
        state["entities"]["department_id"] = dept_id
        if state["entities"]["reason"] is None:
            state["entities"]["reason"] = message_text.strip()

    elif intent == "DOCTOR_AVAILABILITY":
        doc_id = state["entities"]["doctor_id"]
        appt_date = state["entities"]["appointment_date"]
        
        if not doc_id:
            response_text = language_service.translate_response("ASK_DEPT_OR_DOCTOR", current_lang)
            missing_info.append("doctor")
        elif not appt_date:
            response_text = language_service.translate_response("ASK_DATE", current_lang)
            missing_info.append("date")
        else:
            tool_called = "get_doctor_availability"
            res = tool_registry.tool_get_doctor_availability(conversation_code, doc_id, appt_date)
            doc_name = resolve_doctor_details(doc_id)["name"]
            if res["success"] and res["data"]["available"]:
                response_text = f"{doc_name} is available on {appt_date} between {res['data']['start_time']} and {res['data']['end_time']}."
            else:
                response_text = language_service.translate_response("DOCTOR_NOT_AVAILABLE", current_lang, date=appt_date)

    elif intent == "APPOINTMENT_STATUS":
        booking_id = state["entities"]["booking_id"]
        if not booking_id:
            response_text = language_service.translate_response("ASK_BOOKING_ID", current_lang)
            missing_info.append("booking_id")
        else:
            tool_called = "get_appointment_status"
            res = tool_registry.tool_get_appointment_status(conversation_code, booking_id, state["patient_id"])
            if res["success"]:
                appt_data = res["data"]
                appt_time_str = appt_data["appointment_time"]
                response_text = language_service.translate_response(
                    "STATUS_RESPONSE", current_lang,
                    booking_id=booking_id,
                    doctor=appt_data["doctor_name"],
                    date=str(appt_data["appointment_date"]),
                    time=appt_time_str,
                    status=appt_data["status"]
                )
            else:
                if res.get("error_code") == "ACCESS_DENIED":
                    response_text = language_service.translate_response("ACCESS_DENIED", current_lang)
                else:
                    response_text = f"Could not find appointment with booking ID {booking_id}."

    elif intent == "BOOK_APPOINTMENT":
        msg_clean = message_text.lower().strip()
        state["interactive_buttons"] = []

        # 1. Handle explicit confirmation pending state
        if state.get("confirmation_pending"):
            if is_affirmative or msg_clean in ["btn_confirm_appt", "confirm appointment", "confirm"]:
                pat_id = state["patient_id"]
                doc_id = state["entities"]["doctor_id"]
                dept_id = state["entities"]["department_id"]

                # Always sync dept_id from doc_id if doc_id is present
                if doc_id:
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT department_id FROM doctors WHERE id = %s;", (doc_id,))
                        row = cur.fetchone()
                        if row:
                            dept_id = row[0]
                            state["entities"]["department_id"] = dept_id
                    finally:
                        cur.close()
                        conn.close()

                appt_date = state["entities"]["appointment_date"]
                appt_time = state["entities"]["appointment_time"]
                reason = state["entities"]["reason"] or "General Checkup"

                if not pat_id:
                    response_text = "Please register or identify yourself before confirming an appointment."
                    state["intent"] = "IDENTIFY_PATIENT"
                    state["interactive_buttons"] = [
                        {"id": "btn_first_time", "title": "First-time Patient"},
                        {"id": "btn_existing", "title": "Existing Patient"}
                    ]
                else:
                    tool_called = "book_appointment"
                    res = tool_registry.tool_book_appointment(
                        conversation_code=conversation_code,
                        patient_id=pat_id,
                        doctor_id=doc_id,
                        department_id=dept_id,
                        date_str=appt_date,
                        time_str=appt_time,
                        reason=reason,
                        user_id=None
                    )
                    state["confirmation_pending"] = False
                    state["confirmation_details"] = {}

                    if res["success"]:
                        doc_details = resolve_doctor_details(doc_id)
                        response_text = (
                            f"Your appointment has been confirmed successfully!\n\n"
                            f"Booking ID: {res['data']['booking_id']}\n"
                            f"Doctor: {doc_details['name']}\n"
                            f"Date: {appt_date}\n"
                            f"Time: {appt_time}\n"
                            f"Reason: {reason}\n\n"
                            f"Thank you for using Meridian Hospital AI Patient Desk! Is there anything else I can help you with, such as hospital information?"
                        )
                        state["intent"] = "POST_BOOKING"
                        state["previous_question"] = "post_booking_help"
                        state["entities"] = {
                            "patient_id": state["patient_id"],
                            "doctor_id": None, "department_id": None,
                            "appointment_date": None, "appointment_time": None,
                            "booking_id": None, "reason": None
                        }
                        state["interactive_buttons"] = []
                    else:
                        state["confirmation_pending"] = False
                        state["entities"]["appointment_time"] = None
                        doc_id = state["entities"].get("doctor_id")
                        appt_date = state["entities"].get("appointment_date")
                        doc_info = resolve_doctor_details(doc_id)
                        res_alt = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date) if (doc_id and appt_date) else {}
                        avail_slots_str = ", ".join(res_alt.get("slots", [])) if res_alt.get("slots") else "No remaining slots for this date"
                        err_reason = res.get('error', 'The selected appointment slot is no longer available.')
                        response_text = (
                            f"Booking could not be completed: {err_reason}\n\n"
                            f"Available alternative slots for {doc_info['name']} on {appt_date}:\n"
                            f"• {avail_slots_str}\n\n"
                            f"Please reply with your preferred appointment time."
                        )
            elif is_negative or msg_clean in ["btn_cancel_appt", "cancel"]:
                state["confirmation_pending"] = False
                state["confirmation_details"] = {}
                state["intent"] = "GREETING"
                response_text = "Appointment booking cancelled. How else can I help you today?"
                state["interactive_buttons"] = [
                    {"id": "btn_book_appt", "title": "Book Appointment"},
                    {"id": "btn_hosp_info", "title": "Hospital Information"}
                ]
            elif msg_clean in ["btn_change_appt", "change details", "change"]:
                state["confirmation_pending"] = False
                state["change_pending"] = True
                response_text = "What details would you like to change? (Doctor, Date, Time, or Reason)"
            else:
                response_text = "Please confirm your appointment details using the options below:"
                state["interactive_buttons"] = [
                    {"id": "btn_confirm_appt", "title": "Confirm Appointment"},
                    {"id": "btn_change_appt", "title": "Change Details"},
                    {"id": "btn_cancel_appt", "title": "Cancel"}
                ]
        else:
            # 1. Handle change_pending prompt response
            if state.get("change_pending"):
                state["change_pending"] = False
                if "reason" in msg_clean:
                    state["entities"]["reason"] = None
                    response_text = "Please enter your updated reason for visit:"
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                elif "time" in msg_clean or "slot" in msg_clean:
                    state["entities"]["appointment_time"] = None
                    doc_id = state["entities"].get("doctor_id")
                    appt_date = state["entities"].get("appointment_date")
                    slots_str = ""
                    if doc_id and appt_date:
                        res_alt = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                        if res_alt.get("slots"):
                            slots_str = f"\nAvailable slots on {appt_date}: {', '.join(res_alt['slots'])}"
                    response_text = f"Please enter your updated preferred appointment time:{slots_str}"
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                elif "date" in msg_clean:
                    state["entities"]["appointment_date"] = None
                    state["entities"]["appointment_time"] = None
                    response_text = "Please enter your updated preferred appointment date (e.g. tomorrow, 2026-09-03):"
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                elif "doctor" in msg_clean or "dept" in msg_clean or "department" in msg_clean:
                    state["entities"]["doctor_id"] = None
                    state["entities"]["department_id"] = None
                    state["entities"]["appointment_date"] = None
                    state["entities"]["appointment_time"] = None
                    response_text = "Which doctor or department would you like to switch to?"
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

            # 2. Handle explicit available time/slots query
            if any(kw in msg_clean for kw in ["available time", "available slots", "what times", "show times"]):
                doc_id = state["entities"].get("doctor_id")
                appt_date = state["entities"].get("appointment_date")
                if doc_id and appt_date:
                    doc_info = resolve_doctor_details(doc_id)
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                    slots_list = res_slots.get("slots", []) if res_slots.get("success") else []
                    slots_text = ", ".join(slots_list) if slots_list else "No remaining slots for this date"
                    response_text = f"Here are the available time slots for {doc_info['name']} on {appt_date}:\n• {slots_text}\n\nWhich time would you prefer?"
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

            # 3. Extract multi-field entities via LLM / Rule Extractor
            llm_info = llm_service.extract_structured_info(message_text, state, current_lang)

            # Doctor & Department matching
            if llm_info.get("doctor"):
                rule_ext = entity_extractor.extract_entities(message_text)
                if rule_ext.get("doctor_id"):
                    state["entities"]["doctor_id"] = rule_ext["doctor_id"]
            if llm_info.get("department") and not state["entities"].get("department_id"):
                rule_ext = entity_extractor.extract_entities(message_text)
                if rule_ext.get("department_id"):
                    state["entities"]["department_id"] = rule_ext["department_id"]

            # Date Normalization & Ambiguity Check
            date_candidate = llm_info.get("appointment_date") or message_text
            norm_date, is_ambig, _ = date_normalizer.parse_and_normalize_date(date_candidate)
            if norm_date:
                state["entities"]["appointment_date"] = norm_date

            if llm_info.get("appointment_time"):
                state["entities"]["appointment_time"] = llm_info["appointment_time"]
            
            if not state["entities"].get("reason"):
                if llm_info.get("reason"):
                    state["entities"]["reason"] = llm_info["reason"]
                elif not entity_extractor.is_date_or_time_expression(message_text):
                    state["entities"]["reason"] = message_text.strip()

            pat_id = state["patient_id"]
            doc_id = state["entities"]["doctor_id"]
            dept_id = state["entities"]["department_id"]
            appt_date = state["entities"]["appointment_date"]
            appt_time = state["entities"]["appointment_time"]
            reason = state["entities"]["reason"]

            if doc_id and not dept_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT department_id FROM doctors WHERE id = %s;", (doc_id,))
                    row = cur.fetchone()
                    if row:
                        dept_id = row[0]
                        state["entities"]["department_id"] = dept_id
                finally:
                    cur.close()
                    conn.close()

            # Check missing fields
            missing_fields_list = []
            if not doc_id and not dept_id:
                missing_fields_list.append("Department or Doctor")
            if not appt_date:
                missing_fields_list.append("Preferred appointment date")
            if not appt_time:
                missing_fields_list.append("Preferred appointment time")
            if not reason:
                missing_fields_list.append("Reason for visit")

            if missing_fields_list:
                known_parts = []
                if doc_id:
                    known_parts.append(f"Doctor: {resolve_doctor_details(doc_id)['name']}")
                if appt_date:
                    known_parts.append(f"Date: {appt_date}")
                if appt_time:
                    known_parts.append(f"Time: {appt_time}")

                known_summary = "I have " + ", ".join(known_parts) + " noted.\n\n" if known_parts else ""
                response_text = f"Sure! I can help you book an appointment. {known_summary}Please provide the remaining details:\n\n• " + "\n• ".join(missing_fields_list) + "\n\nYou can send them together."
                missing_info = missing_fields_list
            else:
                # All required fields present -> check real DB slot availability
                tool_called = "get_available_slots"
                res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                doc_info = resolve_doctor_details(doc_id)

                available_slots = res_slots.get("slots", []) if res_slots.get("success") else []
                if appt_time in available_slots:
                    state["confirmation_pending"] = True
                    pat_name = "Patient"
                    if pat_id:
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute("SELECT first_name, last_name FROM patients WHERE id = %s;", (pat_id,))
                            p_row = cur.fetchone()
                            if p_row:
                                pat_name = f"{p_row[0]} {p_row[1] or ''}".strip()
                        finally:
                            cur.close()
                            conn.close()

                    response_text = f"Please confirm your appointment:\n\nPatient: {pat_name}\nDoctor: {doc_info['name']}\nDepartment: {doc_info['department']}\nDate: {appt_date}\nTime: {appt_time}\nReason: {reason}"
                    state["interactive_buttons"] = [
                        {"id": "btn_confirm_appt", "title": "Confirm Appointment"},
                        {"id": "btn_change_appt", "title": "Change Details"},
                        {"id": "btn_cancel_appt", "title": "Cancel"}
                    ]
                else:
                    state["entities"]["appointment_time"] = None
                    state["confirmation_pending"] = False
                    alt_slots_str = ", ".join(available_slots) if available_slots else "No remaining slots for this date"
                    response_text = (
                        f"{doc_info['name']} is not available at {appt_time} on {appt_date}.\n\n"
                        f"Available alternative slots on {appt_date}:\n"
                        f"• {alt_slots_str}\n\n"
                        f"Please reply with your preferred appointment time from the list above."
                    )

    elif intent == "SYMPTOM_GUIDANCE":
        symptoms_map = {
            "fever": "General Medicine",
            "cold": "General Medicine",
            "cough": "General Medicine",
            "headache": "General Medicine",
            "pain": "General Medicine",
            "stomach": "General Medicine",
            "chest pain": "Cardiology"
        }
        resolved_dept = "General Medicine"
        for keyword, dept in symptoms_map.items():
            if keyword in message_text.lower():
                resolved_dept = dept
                break
                
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM departments WHERE department_name = %s AND status = 'ACTIVE';", (resolved_dept,))
        row = cur.fetchone()
        dept_id = row[0] if row else 1
        cur.close()
        conn.close()
        
        response_text = language_service.translate_response("SYMPTOM_GUIDANCE", current_lang, dept=resolved_dept)
        state["previous_question"] = "would_you_like_to_check_available_doctors"
        
        state["entities"]["department_id"] = dept_id
        if state["entities"]["reason"] is None:
            state["entities"]["reason"] = f"Symptoms in message: {message_text}"

    elif intent == "DOCTOR_AVAILABILITY":
        doc_id = state["entities"]["doctor_id"]
        appt_date = state["entities"]["appointment_date"]
        
        if not doc_id:
            response_text = language_service.translate_response("ASK_DEPT_OR_DOCTOR", current_lang)
            missing_info.append("doctor")
        elif not appt_date:
            response_text = language_service.translate_response("ASK_DATE", current_lang)
            missing_info.append("date")
        else:
            tool_called = "get_doctor_availability"
            res = tool_registry.tool_get_doctor_availability(conversation_code, doc_id, appt_date)
            doc_name = resolve_doctor_details(doc_id)["name"]
            if res["success"] and res["data"]["available"]:
                # Available
                response_text = f"{doc_name} is available on {appt_date} between {res['data']['start_time']} and {res['data']['end_time']}."
            else:
                response_text = language_service.translate_response("DOCTOR_NOT_AVAILABLE", current_lang, date=appt_date)

    elif intent == "APPOINTMENT_STATUS":
        booking_id = state["entities"]["booking_id"]
        if not booking_id:
            response_text = language_service.translate_response("ASK_BOOKING_ID", current_lang)
            missing_info.append("booking_id")
        else:
            tool_called = "get_appointment_status"
            # Get status (verify patient lookup security restriction)
            res = tool_registry.tool_get_appointment_status(conversation_code, booking_id, state["patient_id"])
            if res["success"]:
                appt_data = res["data"]
                # Format time
                appt_time_str = appt_data["appointment_time"]
                response_text = language_service.translate_response(
                    "STATUS_RESPONSE", current_lang,
                    booking_id=booking_id,
                    doctor=appt_data["doctor_name"],
                    date=str(appt_data["appointment_date"]),
                    time=appt_time_str,
                    status=appt_data["status"]
                )
            else:
                if res.get("error_code") == "ACCESS_DENIED":
                    response_text = language_service.translate_response("ACCESS_DENIED", current_lang)
                else:
                    response_text = f"Could not find appointment with booking ID {booking_id}."

    elif intent == "BOOK_APPOINTMENT":
        pat_id = state["patient_id"]
        doc_id = state["entities"]["doctor_id"]
        dept_id = state["entities"]["department_id"]
        appt_date = state["entities"]["appointment_date"]
        appt_time = state["entities"]["appointment_time"]
        reason = state["entities"]["reason"] or "General Checkup"
        
        if not dept_id and not doc_id:
            response_text = language_service.translate_response("ASK_DEPT_OR_DOCTOR", current_lang)
            missing_info.append("department_or_doctor")
        elif not appt_date:
            response_text = language_service.translate_response("ASK_DATE", current_lang)
            missing_info.append("appointment_date")
        elif not appt_time:
            # Date is present but time is missing. Let's present available slots!
            # If doc_id is missing but dept_id is present, let's select the first doctor in that department
            if not doc_id and dept_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT id FROM doctors WHERE department_id = %s AND status = 'ACTIVE' LIMIT 1;", (dept_id,))
                row = cur.fetchone()
                if row:
                    doc_id = row[0]
                    state["entities"]["doctor_id"] = doc_id
                cur.close()
                conn.close()
                
            if doc_id:
                tool_called = "get_available_slots"
                res = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                doc_name = resolve_doctor_details(doc_id)["name"]
                if res["success"] and res["slots"]:
                    formatted_slots = ", ".join(res["slots"])
                    response_text = language_service.translate_response(
                        "SLOTS_AVAILABLE", current_lang,
                        date=appt_date,
                        doctor=doc_name,
                        slots=formatted_slots
                    )
                else:
                    response_text = language_service.translate_response(
                        "NO_SLOTS", current_lang,
                        date=appt_date,
                        doctor=doc_name
                    )
            else:
                response_text = language_service.translate_response("ASK_DEPT_OR_DOCTOR", current_lang)
                missing_info.append("doctor")
            missing_info.append("appointment_time")
        elif not pat_id:
            if re.search(r"\b(p\d+)\b", message_text.lower()):
                response_text = language_service.translate_response("PATIENT_NOT_FOUND", current_lang)
            else:
                response_text = language_service.translate_response("ASK_PATIENT_CODE", current_lang)
            missing_info.append("patient_id")
        else:
            # We have all slots. Execute Booking tool!
            # Resolve doc_id if missing from dept_id
            if not doc_id and dept_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                cur.execute("SELECT id FROM doctors WHERE department_id = %s AND status = 'ACTIVE' LIMIT 1;", (dept_id,))
                row = cur.fetchone()
                if row:
                    doc_id = row[0]
                    state["entities"]["doctor_id"] = doc_id
                cur.close()
                conn.close()
                
            tool_called = "book_appointment"
            res = tool_registry.tool_book_appointment(
                conversation_code=conversation_code,
                patient_id=pat_id,
                doctor_id=doc_id,
                department_id=dept_id,
                date_str=appt_date,
                time_str=appt_time,
                reason=reason,
                user_id=None # Patient booked themselves
            )
            if res["success"]:
                doc_details = resolve_doctor_details(doc_id)
                response_text = language_service.translate_response(
                    "BOOKING_SUCCESS", current_lang,
                    booking_id=res["data"]["booking_id"],
                    date=appt_date,
                    time=appt_time,
                    doctor=doc_details["name"]
                )
                # Success booking: clear appointment slots from state to allow a new booking later
                state["entities"] = {
                    "patient_id": None,
                    "doctor_id": None,
                    "department_id": None,
                    "appointment_date": None,
                    "appointment_time": None,
                    "booking_id": None,
                    "reason": None
                }
                state["intent"] = "GREETING" # Reset intent
            else:
                if res.get("error_code") == "APPOINTMENT_SLOT_UNAVAILABLE":
                    response_text = language_service.translate_response("SLOT_UNAVAILABLE", current_lang)
                else:
                    response_text = f"Booking failed: {res['error']}"

    elif intent == "CANCEL_APPOINTMENT":
        booking_id = state["entities"]["booking_id"]
        reason = state["entities"]["reason"]
        
        if not booking_id:
            response_text = language_service.translate_response("ASK_BOOKING_ID", current_lang)
            missing_info.append("booking_id")
        elif not reason:
            response_text = language_service.translate_response("ASK_CANCEL_REASON", current_lang)
            missing_info.append("reason")
        else:
            tool_called = "cancel_appointment"
            res = tool_registry.tool_cancel_appointment(
                conversation_code=conversation_code,
                booking_id=booking_id,
                reason=reason,
                user_id=None
            )
            if res["success"]:
                response_text = language_service.translate_response("CANCEL_SUCCESS", current_lang, booking_id=booking_id)
                # Clear slots
                state["entities"] = {
                    "patient_id": None,
                    "doctor_id": None,
                    "department_id": None,
                    "appointment_date": None,
                    "appointment_time": None,
                    "booking_id": None,
                    "reason": None
                }
                state["intent"] = "GREETING"
            else:
                response_text = f"Cancellation failed: {res['error']}"

    elif intent == "RESCHEDULE_APPOINTMENT":
        booking_id = state["entities"]["booking_id"]
        new_date = state["entities"]["appointment_date"]
        new_time = state["entities"]["appointment_time"]
        reason = state["entities"]["reason"]
        
        if not booking_id:
            response_text = language_service.translate_response("ASK_BOOKING_ID", current_lang)
            missing_info.append("booking_id")
        elif not new_date:
            response_text = language_service.translate_response("ASK_RESCHEDULE_DATE_TIME", current_lang)
            missing_info.append("appointment_date")
        elif not new_time:
            # We have new_date, let's query slots!
            # Resolve doctor_id from booking_id
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT doctor_id FROM appointments WHERE booking_id = %s;", (booking_id,))
            row = cur.fetchone()
            doc_id = row[0] if row else None
            cur.close()
            conn.close()
            
            if doc_id:
                tool_called = "get_available_slots"
                res = tool_registry.tool_get_available_slots(conversation_code, doc_id, new_date)
                doc_name = resolve_doctor_details(doc_id)["name"]
                if res["success"] and res["slots"]:
                    formatted_slots = ", ".join(res["slots"])
                    response_text = language_service.translate_response(
                        "SLOTS_AVAILABLE", current_lang,
                        date=new_date,
                        doctor=doc_name,
                        slots=formatted_slots
                    )
                else:
                    response_text = language_service.translate_response("ASK_TIME", current_lang)
            else:
                response_text = language_service.translate_response("ASK_TIME", current_lang)
            missing_info.append("appointment_time")
        elif not reason:
            response_text = language_service.translate_response("ASK_RESCHEDULE_REASON", current_lang)
            missing_info.append("reason")
        else:
            tool_called = "reschedule_appointment"
            res = tool_registry.tool_reschedule_appointment(
                conversation_code=conversation_code,
                booking_id=booking_id,
                new_date_str=new_date,
                new_time_str=new_time,
                reason=reason,
                user_id=None
            )
            if res["success"]:
                response_text = language_service.translate_response(
                    "RESCHEDULE_SUCCESS", current_lang,
                    booking_id=booking_id,
                    date=new_date,
                    time=new_time
                )
                # Clear state slots
                state["entities"] = {
                    "patient_id": None,
                    "doctor_id": None,
                    "department_id": None,
                    "appointment_date": None,
                    "appointment_time": None,
                    "booking_id": None,
                    "reason": None
                }
                state["intent"] = "GREETING"
            else:
                err_msg = res.get("error", "")
                err_code = res.get("error_code", "")
                
                if err_code == "APPOINTMENT_SLOT_UNAVAILABLE" or "no longer available" in err_msg.lower():
                    response_text = "Sorry, that slot is no longer available. Would you like me to check another time?"
                elif "past" in err_msg.lower() or err_code in ["PAST_DATE", "PAST_TIME", "APPOINTMENT_DATE_PAST"]:
                    response_text = "That time has already passed today. I can check the next available appointment for you."
                else:
                    response_text = f"I'm sorry, I couldn't complete the rescheduling: {err_msg}"
                
                # Clear time slot so they can choose another one
                state["entities"]["appointment_time"] = None
                if "past" in err_msg.lower() or err_code in ["PAST_DATE", "PAST_TIME", "APPOINTMENT_DATE_PAST"]:
                    state["entities"]["appointment_date"] = None
                
                state["intent"] = "RESCHEDULE_APPOINTMENT"
                    
    elif intent == "HOSPITAL_INFORMATION":
        # Use knowledge retrieval (RAG) to answer hospital information questions
        tool_called = "search_knowledge"
        try:
            kb_result = knowledge_service.answer_knowledge_question(
                query=message_text,
                language=current_lang,
                top_k=3
            )
            if kb_result["found"]:
                response_text = kb_result["response"]
                # Store source context in state for audit traceability
                state["knowledge_context"] = kb_result.get("source_context", [])
            else:
                response_text = knowledge_service.NO_KNOWLEDGE_RESPONSE
                state["knowledge_context"] = []
        except Exception as e:
            print(f"[Agent] HOSPITAL_INFORMATION knowledge retrieval error: {e}")
            response_text = knowledge_service.NO_KNOWLEDGE_RESPONSE
            state["knowledge_context"] = []

    elif intent == "PRE_ADMISSION":
        # Use knowledge retrieval for pre-admission and admission document questions
        tool_called = "search_knowledge"
        msg_l = message_text.lower()
        try:
            # Determine best category hint
            if any(w in msg_l for w in ["document", "bring", "required", "need", "carry"]):
                cat_hint = "ADMISSION_DOCUMENTS"
            else:
                cat_hint = "PRE_ADMISSION"
            kb_result = knowledge_service.answer_knowledge_question(
                query=message_text,
                language=current_lang,
                category_hint=cat_hint,
                top_k=3
            )
            if kb_result["found"]:
                response_text = kb_result["response"]
                state["knowledge_context"] = kb_result.get("source_context", [])
            else:
                response_text = knowledge_service.NO_KNOWLEDGE_RESPONSE
                state["knowledge_context"] = []
        except Exception as e:
            print(f"[Agent] PRE_ADMISSION knowledge retrieval error: {e}")
            response_text = knowledge_service.NO_KNOWLEDGE_RESPONSE
            state["knowledge_context"] = []

    elif intent == "POST_BOOKING":
        msg_clean = message_text.lower().strip()
        state["interactive_buttons"] = []
        if is_affirmative or any(w in msg_clean for w in ["yes", "sure", "options", "help", "info", "hospital"]):
            response_text = "Here are some options you can explore:"
            state["interactive_buttons"] = [
                {"id": "btn_hosp_info", "title": "Hospital Information"},
                {"id": "btn_depts", "title": "Departments"},
                {"id": "btn_doctors", "title": "Doctors"},
                {"id": "btn_opd", "title": "OPD Timings"},
                {"id": "btn_contact", "title": "Contact Info"}
            ]
        elif is_negative or any(w in msg_clean for w in ["no", "nothing", "bye", "thanks", "thank you"]):
            response_text = "Thank you for contacting Meridian Hospital. Have a wonderful day!"
            state["intent"] = "GREETING"
        else:
            tool_called = "search_knowledge"
            try:
                kb_result = knowledge_service.answer_knowledge_question(
                    query=message_text,
                    language=current_lang,
                    top_k=3
                )
                if kb_result["found"]:
                    response_text = kb_result["response"]
                    state["knowledge_context"] = kb_result.get("source_context", [])
                else:
                    response_text = "I'm here to help! You can ask me about hospital services, doctors, OPD timings, visiting hours, or pre-admission guidance."
            except Exception as e:
                response_text = "How else can I assist you with Meridian Hospital services today?"

    else:
        response_text = language_service.translate_response("UNKNOWN", current_lang)

    # 6. Save updated state and log response message
    intent = state["intent"]
    state["missing_information"] = missing_info
    state["last_action"] = tool_called
    
    # Save session state changes
    state_manager.save_conversation_state(conversation_code, state)
    
    # Insert AI message to DB, attaching state as metadata JSONB
    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)

    return {
        "success": True,
        "conversation_id": conversation_code,
        "language": current_lang,
        "intent": intent,
        "response": response_text,
        "missing_information": missing_info,
        "tool_called": tool_called,
        "interactive_buttons": state.get("interactive_buttons", [])
    }
