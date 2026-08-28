import sys
import os
import datetime

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
    
    # If the user explicitly mentions a new doctor or department, clear old slot selections
    if extracted.get("doctor_id") or extracted.get("department_id"):
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
        if state["patient_id"] is None:
            prev_q = state.get("previous_question")
            if prev_q == "new_or_existing_patient":
                msg_l = message_text.lower().strip()
                import re
                match_name = re.search(r"\b(?:i\s*am|my\s*name\s*is|i'm|call\s*me)\s+([a-zA-Z]+)(?:\s+([a-zA-Z]+))?\b", msg_l)
                
                is_new = any(k in msg_l for k in ["new", "first", "no", "never", "haven't", "புதிய", "नहीं", "వద్దు", "വേണ്ട", "ಬೇಡ", "نہیں"])
                is_existing = any(k in msg_l for k in ["exist", "yes", "already", "old", "பழைய", "हाँ", "అవును", "അതെ", "ಹೌದು", "جی"])
                
                if is_existing:
                    state["intent"] = "IDENTIFY_PATIENT"
                    state["previous_question"] = "ask_patient_code"
                    response_text = language_service.translate_response("EXISTING_PATIENT_PROMPT", current_lang)
                elif is_new:
                    state["intent"] = "REGISTER_PATIENT"
                    state["previous_question"] = "register_first_name"
                    if not state.get("registration_fields"):
                        state["registration_fields"] = {
                            "first_name": None, "last_name": None, "date_of_birth": None, "gender": None, "phone": None
                        }
                    response_text = language_service.translate_response("NEW_PATIENT_PROMPT", current_lang)
                elif match_name:
                    first_name = match_name.group(1).capitalize()
                    last_name = match_name.group(2).capitalize() if match_name.group(2) else "."
                    state["registration_fields"] = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "date_of_birth": None,
                        "gender": None,
                        "phone": None
                    }
                    response_text = f"Hi {first_name}. Are you an existing patient or visiting us for the first time?"
                else:
                    response_text = "Are you an existing patient or visiting us for the first time?"
            else:
                state["previous_question"] = "new_or_existing_patient"
                import re
                msg_l = message_text.lower().strip()
                match_name = re.search(r"\b(?:i\s*am|my\s*name\s*is|i'm|call\s*me)\s+([a-zA-Z]+)(?:\s+([a-zA-Z]+))?\b", msg_l)
                if match_name:
                    first_name = match_name.group(1).capitalize()
                    last_name = match_name.group(2).capitalize() if match_name.group(2) else "."
                    state["registration_fields"] = {
                        "first_name": first_name,
                        "last_name": last_name,
                        "date_of_birth": None,
                        "gender": None,
                        "phone": None
                    }
                    response_text = f"Hello {first_name}! Welcome to Meridian Hospital. I am your AI Patient Desk Assistant. I can help you with appointments, doctor availability, appointment cancellation or rescheduling, hospital information, and pre-admission assistance. Are you an existing patient or visiting us for the first time?"
                else:
                    response_text = language_service.translate_response("GREETING", current_lang)
        else:
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT first_name FROM patients WHERE id = %s;", (state["patient_id"],))
                row = cur.fetchone()
                p_name = row[0] if row else "Patient"
                if current_lang == "TAMIL":
                    response_text = f"மெரிடியன் மருத்துவமனைக்கு மீண்டும் வரவேற்கிறோம், {p_name}. இன்று நான் உங்களுக்கு எவ்வாறு உதவ வேண்டும்?"
                elif current_lang == "HINDI":
                    response_text = f"मेरिडियन अस्पताल में आपका पुनः स्वागत है, {p_name}। आज मैं आपकी क्या मदद कर सकता हूँ?"
                elif current_lang == "TELUGU":
                    response_text = f"మెరిడియన్ హాస్పిటల్‌కు తిరిగి స్వాగతం, {p_name}. ఈ రోజు మీకు ఎలా సహాయపడాలి?"
                elif current_lang == "MALAYALAM":
                    response_text = f"物理മെറിഡിയൻ ആശുപത്രിയിലേക്ക് വീണ്ടും സ്വാഗതം, {p_name}. ഇന്ന് ഞാൻ എങ്ങനെ സഹായിക്കണം?"
                elif current_lang == "KANNADA":
                    response_text = f"ಮೆರಿಡಿಯನ್ ಆಸ್ಪತ್ರೆಗೆ ಮರಳಿ ಸುಸ್ವಾಗತ, {p_name}. ಇಂದು ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?"
                elif current_lang == "URDU":
                    response_text = f"میریڈین ہسپتال میں آپ کا دوبارہ خیر مقدم ہے، {p_name}۔ آج میں آپ کی کیا مدد کر سکتا ہوں؟"
                else:
                    response_text = f"Welcome back to Meridian Hospital, {p_name}. How can I help you today?"
            finally:
                cur.close()
                conn.close()
                
    elif intent == "IDENTIFY_PATIENT":
        import re
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
            cur.execute("UPDATE conversations SET patient_id = %s WHERE conversation_code = %s;", (pat_id, conversation_code))
            conn.commit()
            cur.close()
            conn.close()
            
            response_text = f"Welcome back to Meridian Hospital, {first_name}. How can I help you today?"
        else:
            response_text = "I couldn't find a matching patient record. Please check your patient code (e.g. P001), or are you visiting us for the first time?"

    elif intent == "REGISTER_PATIENT":
        import re
        prev_q = state.get("previous_question")
        if not state.get("registration_fields"):
            state["registration_fields"] = {
                "first_name": None, "last_name": None, "date_of_birth": None, "gender": None, "phone": None
            }
            
        # Skip name registration if first name was already captured contextually
        if prev_q == "register_first_name" and state["registration_fields"]["first_name"]:
            state["previous_question"] = "register_dob"
            response_text = language_service.translate_response("ASK_DOB", current_lang)
        elif prev_q == "register_first_name":
            parts = message_text.strip().split(None, 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else "."
            state["registration_fields"]["first_name"] = first_name
            state["registration_fields"]["last_name"] = last_name
            state["previous_question"] = "register_dob"
            response_text = language_service.translate_response("ASK_DOB", current_lang)
            
        elif prev_q == "register_dob":
            parsed_date = entity_extractor.parse_natural_date(message_text)
            if parsed_date:
                state["registration_fields"]["date_of_birth"] = parsed_date
                state["previous_question"] = "register_gender"
                response_text = language_service.translate_response("ASK_GENDER", current_lang)
            else:
                response_text = "Please provide a valid date of birth (e.g., 15 June 1990 or 1990-06-15)."
                
        elif prev_q == "register_gender":
            g_lower = message_text.lower().strip()
            gender = "Male"
            if "female" in g_lower:
                gender = "Female"
            elif "other" in g_lower or "trans" in g_lower:
                gender = "Other"
            state["registration_fields"]["gender"] = gender
            state["previous_question"] = "register_phone"
            response_text = language_service.translate_response("ASK_PHONE", current_lang)
            
        elif prev_q == "register_phone":
            match_phone = re.search(r"\b(\d{10,12})\b", message_text)
            if match_phone:
                phone_num = match_phone.group(1)
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
                            
                    cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                    w_row = cur.fetchone()
                    whatsapp_val = w_row[0] if w_row else "919999999999"
                    
                    cur.execute("""
                        INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
                        RETURNING id;
                    """, (
                        next_code,
                        state["registration_fields"]["first_name"],
                        state["registration_fields"]["last_name"],
                        state["registration_fields"]["date_of_birth"],
                        state["registration_fields"]["gender"],
                        phone_num,
                        whatsapp_val
                    ))
                    new_pat_id = cur.fetchone()[0]
                    cur.execute("UPDATE conversations SET patient_id = %s WHERE conversation_code = %s;", (new_pat_id, conversation_code))
                    conn.commit()
                    
                    state["patient_id"] = new_pat_id
                    state["entities"]["patient_id"] = new_pat_id
                    state["intent"] = "GREETING"
                    state["previous_question"] = None
                    state["registration_fields"] = {
                        "first_name": None,
                        "last_name": None,
                        "date_of_birth": None,
                        "gender": None,
                        "phone": None
                    }
                    response_text = f"Your registration is complete. Your patient code is {next_code}. How can I help you today?"
                except Exception as e:
                    conn.rollback()
                    response_text = f"Registration failed: {str(e)}"
                finally:
                    cur.close()
                    conn.close()
            else:
                response_text = "Please provide a valid 10 to 12 digit phone number."
        else:
            state["previous_question"] = "register_first_name"
            response_text = language_service.translate_response("NEW_PATIENT_PROMPT", current_lang)

    elif intent == "EMERGENCY_GUIDANCE":
        response_text = language_service.translate_response("EMERGENCY_GUIDANCE", current_lang)
        
    elif intent == "HUMAN_ESCALATION":
        response_text = language_service.translate_response("HUMAN_ESCALATION", current_lang)
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE conversations SET conversation_status = 'ESCALATED' WHERE conversation_code = %s;", (conversation_code,))
        conn.commit()
        cur.close()
        conn.close()

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
                    import datetime
                    import pytz
                    ist = pytz.timezone('Asia/Kolkata')
                    today_str = datetime.datetime.now(ist).strftime("%Y-%m-%d")
                    if appt_date == today_str:
                        response_text = "There are no more available slots today. Would you like me to check tomorrow?"
                        state["previous_question"] = "would_you_like_to_check_tomorrow_slots"
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
            import re
            if re.search(r"\b(p\d+)\b", message_text.lower()):
                response_text = language_service.translate_response("PATIENT_NOT_FOUND", current_lang)
            else:
                response_text = language_service.translate_response("ASK_PATIENT_CODE", current_lang)
            missing_info.append("patient_id")
        else:
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
                user_id=None
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
                state["entities"] = {
                    "patient_id": state["patient_id"],
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
                elif err_code == "DOCTOR_NOT_AVAILABLE":
                    response_text = "The doctor is not scheduled or not available at that time. Would you like to select another time?"
                else:
                    response_text = f"I'm sorry, I couldn't complete the booking: {err_msg}"
                
                # Clear time slot so they can choose another one
                state["entities"]["appointment_time"] = None
                if "past" in err_msg.lower() or err_code in ["PAST_DATE", "PAST_TIME", "APPOINTMENT_DATE_PAST"]:
                    state["entities"]["appointment_date"] = None
                state["intent"] = "BOOK_APPOINTMENT"

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
            import re
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
        msg_l = message_text.lower()
        if "department" in msg_l:
            response_text = "Meridian Hospital has specialized departments in General Medicine, Cardiology, Pediatrics, Orthopedics, Dermatology, ENT, Gynecology, and Neurology."
        elif "opd" in msg_l or "timing" in msg_l or "time" in msg_l:
            response_text = "Our Outpatient Department (OPD) is open Monday through Saturday from 9:00 AM to 5:00 PM. Emergency services are open 24/7."
        elif "where" in msg_l or "location" in msg_l or "address" in msg_l:
            response_text = "Meridian Hospital is located at 123 Healthcare Lane, Sector 4, Walfs India. You can contact us at +91 99999 99999 or find directions on Google Maps."
        else:
            response_text = "Meridian Hospital is a state-of-the-art multi-specialty healthcare provider located in Walfs India. We operate 24/7 emergency services, specialized departments in General Medicine, Cardiology, Pediatrics, Neurology, and more, and provide easy WhatsApp-based booking."
        
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
        "tool_called": tool_called
    }
