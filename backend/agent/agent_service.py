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
from utils.phone_utils import get_phone_query_condition, get_phone_query_params, normalize_phone

def format_time_12h(time_str: str) -> str:
    """Converts '09:00' to '09:00 AM' and '14:30' to '02:30 PM'."""
    try:
        if not time_str:
            return ""
        if "AM" in time_str.upper() or "PM" in time_str.upper():
            return time_str
        parts = time_str.split(":")
        hh = int(parts[0])
        mm = parts[1]
        period = "AM" if hh < 12 else "PM"
        display_h = hh if hh <= 12 else hh - 12
        if display_h == 0:
            display_h = 12
        return f"{display_h:02d}:{mm} {period}"
    except Exception:
        return str(time_str)

def get_specialist_titles(d_name: str) -> tuple:
    mapping = {
        "Dermatology": ("Dermatologist", "Dermatologists"),
        "General Medicine": ("General Medicine Doctor", "General Medicine Doctors"),
        "Cardiology": ("Cardiologist", "Cardiologists"),
        "Pediatrics": ("Pediatrician", "Pediatricians"),
        "Orthopedics": ("Orthopedist", "Orthopedists"),
        "ENT": ("ENT Specialist", "ENT Specialists"),
        "Gynecology": ("Gynecologist", "Gynecologists"),
        "Neurology": ("Neurologist", "Neurologists")
    }
    return mapping.get(d_name, ("Specialist", "Specialists"))

def resolve_or_create_child_patient(
    parent_patient_id: int,
    child_name: str,
    dob_str: str = None,
    gender: str = None,
    parent_phone: str = None,
    parent_whatsapp: str = None,
    email: str = None,
    relationship: str = "CHILD"
) -> int:
    """
    Creates or retrieves a separate patient record for a child/dependent,
    linking guardian_patient_id to parent_patient_id without overwriting parent data.
    """
    if not parent_patient_id or not child_name:
        return parent_patient_id

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        parts = child_name.strip().split()
        first_name = parts[0].capitalize()
        last_name = " ".join(parts[1:]).capitalize() if len(parts) > 1 else "User"

        # Fetch parent phone/whatsapp if missing
        if not parent_phone or not parent_whatsapp:
            cur.execute("SELECT phone, whatsapp_number FROM patients WHERE id = %s;", (parent_patient_id,))
            p_row = cur.fetchone()
            if p_row:
                parent_phone = parent_phone or p_row[0]
                parent_whatsapp = parent_whatsapp or p_row[1] or p_row[0]

        # 1. Search if child patient already exists under this guardian
        cur.execute("""
            SELECT id FROM patients
            WHERE guardian_patient_id = %s AND LOWER(first_name) = LOWER(%s) AND status = 'ACTIVE'
            LIMIT 1;
        """, (parent_patient_id, first_name))
        row = cur.fetchone()
        if row:
            if email:
                cur.execute("UPDATE patients SET email = %s WHERE id = %s;", (email, row[0]))
                conn.commit()
            return row[0]

        # 2. Generate unique patient_code
        cur.execute("SELECT COUNT(*) FROM patients;")
        count = cur.fetchone()[0]
        patient_code = f"P{(count + 1):04d}"

        # 3. Insert child patient record
        norm_dob = dob_str if (dob_str and len(dob_str) == 10 and "-" in dob_str) else "2015-01-01"
        rel_str = relationship.upper() if relationship else "CHILD"
        cur.execute("""
            INSERT INTO patients (
                patient_code, first_name, last_name, date_of_birth, gender,
                phone, whatsapp_number, email, guardian_patient_id, guardian_phone,
                relationship_to_contact, is_dependent, status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, 'ACTIVE', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id;
        """, (
            patient_code, first_name, last_name, norm_dob, gender or "Unknown",
            parent_phone, parent_whatsapp, email, parent_patient_id, parent_whatsapp,
            rel_str
        ))
        child_id = cur.fetchone()[0]
        conn.commit()
        print(f"[FAMILY_PATIENT] Created separate patient record ID {child_id} ({patient_code}) for dependent {first_name} {last_name} under guardian ID {parent_patient_id}")
        return child_id
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to create child patient record: {e}")
        return parent_patient_id
    finally:
        cur.close()
        conn.close()

def get_doctor_working_info_and_next_slots(doc_id: int, from_date_str: str) -> dict:
    """
    Returns doctor's working schedule details and the next available working date + slots.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        doc_info = resolve_doctor_details(doc_id)
        cur.execute("""
            SELECT DISTINCT day_of_week
            FROM doctor_schedules
            WHERE doctor_id = %s AND status = 'ACTIVE'
            ORDER BY day_of_week;
        """, (doc_id,))
        s_rows = cur.fetchall()
        working_days = [r[0].capitalize() for r in s_rows]
        working_days_str = ", ".join(working_days) if working_days else "Regular Working Days"
        
        try:
            from_date = datetime.datetime.strptime(from_date_str, "%Y-%m-%d").date()
        except Exception:
            from_date = datetime.date.today()
            
        day_name = from_date.strftime("%A")
        
        next_date = None
        next_slots = []
        for d_offset in range(1, 14):
            candidate_d = from_date + datetime.timedelta(days=d_offset)
            cand_str = candidate_d.strftime("%Y-%m-%d")
            res = tool_registry.tool_get_available_slots("SYSTEM", doc_id, cand_str)
            if res.get("success") and res.get("slots"):
                next_date = cand_str
                next_slots = res["slots"]
                break
                
        return {
            "doctor_name": doc_info["name"],
            "department_name": doc_info["department"],
            "day_name": day_name,
            "working_days_str": working_days_str,
            "next_date": next_date,
            "next_slots": next_slots
        }
    finally:
        cur.close()
        conn.close()

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
        
        LANG_MAP = {
            'EN': 'ENGLISH', 'ENGLISH': 'ENGLISH',
            'TA': 'TAMIL', 'TAMIL': 'TAMIL',
            'HI': 'HINDI', 'HINDI': 'HINDI',
            'TE': 'TELUGU', 'TELUGU': 'TELUGU',
            'ML': 'MALAYALAM', 'MALAYALAM': 'MALAYALAM',
            'KN': 'KANNADA', 'KANNADA': 'KANNADA',
            'UR': 'URDU', 'URDU': 'URDU'
        }
        db_lang = LANG_MAP.get(str(language).upper(), 'ENGLISH') if language else 'ENGLISH'

        # Write to messages table
        import json
        cur.execute("""
            INSERT INTO messages (conversation_id, sender_type, message_type, message_text, language, intent, metadata)
            VALUES (%s, %s, 'TEXT', %s, %s, %s, %s);
        """, (conv_id, db_sender, message_text, db_lang, intent, json.dumps(metadata) if metadata else None))
        conn.commit()
    except Exception as e:
        print("Failed to log message to DB:", str(e))
    finally:
        cur.close()
        conn.close()

def log_agent_action(conversation_code: str, action_type: str, details: dict = None):
    """Inserts an audit entry into agent_action_logs table."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, patient_id FROM conversations WHERE conversation_code = %s;", (conversation_code,))
        row = cur.fetchone()
        conv_id = row[0] if row else None
        pat_id = row[1] if row else None
        import json
        cur.execute("""
            INSERT INTO agent_action_logs (conversation_id, patient_id, action_type, action_details)
            VALUES (%s, %s, %s, %s);
        """, (conv_id, pat_id, action_type, json.dumps(details) if details else None))
        conn.commit()
    except Exception as e:
        print(f"Failed to write agent_action_log ({action_type}):", e)
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
            doc_name = row[0].replace("Dr. Dr.", "Dr.").strip() if row[0] else "Doctor"
            return {"name": doc_name, "department": row[1]}
        return {"name": "Doctor", "department": "General Medicine"}
    finally:
        cur.close()
        conn.close()

def get_doctors_by_department(department_id: int) -> list:
    """Returns list of active doctors in a department: [{id, name, department}]"""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT d.id, d.display_name, dept.department_name
            FROM doctors d
            JOIN departments dept ON d.department_id = dept.id
            WHERE d.department_id = %s AND d.status = 'ACTIVE'
            ORDER BY d.display_name;
        """, (department_id,))
        rows = cur.fetchall()
        return [{"id": r[0], "name": r[1], "department": r[2]} for r in rows]
    finally:
        cur.close()
        conn.close()

def format_doctor_availability_response(department_id: int, date_str: str, conversation_code: str) -> str:
    """
    Fetches all doctors in the department and shows their available slots for
    the given date, excluding already-booked appointments.
    Returns a human-friendly multi-line response string.
    """
    import datetime
    import pytz

    doctors = get_doctors_by_department(department_id)
    if not doctors:
        return "No active doctors found for this department on the selected date."

    # Parse and validate date
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return f"Invalid date: {date_str}. Please provide a date in YYYY-MM-DD format."

    day_name = date_obj.strftime("%A, %d %b %Y")
    dept_name = doctors[0]["department"]

    # Filter past slots for today
    ist = pytz.timezone('Asia/Kolkata')
    now_ist = datetime.datetime.now(ist)
    today_str = now_ist.strftime("%Y-%m-%d")
    curr_time_str = now_ist.strftime("%H:%M")

    lines = [f"🏥 *{dept_name} Department* — Doctor Availability"]
    lines.append(f"📅 *{day_name}*\n")

    any_available = False
    for doc in doctors:
        slots_res = tool_registry.tool_get_available_slots(conversation_code, doc["id"], date_str)
        slots = slots_res.get("slots", []) if slots_res.get("success") else []

        # Filter past slots if today
        if date_str == today_str:
            slots = [s for s in slots if s > curr_time_str]

        lines.append(f"👨‍⚕️ *{doc['name']}*")
        if slots:
            any_available = True
            # Group slots into readable chunks (show max 8 to avoid overflow)
            shown = slots[:8]
            slot_str = "  ·  ".join(shown)
            if len(slots) > 8:
                slot_str += f"  ·  (+{len(slots)-8} more)"
            lines.append(f"   ✅ Available: {slot_str}")
        else:
            lines.append("   ❌ No slots available this day")
        lines.append("")

    if not any_available:
        lines.append("_No available slots found for this department on the selected date._")

    lines.append("Would you like to *book an appointment* with any of these doctors?")
    return "\n".join(lines)


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
            if row and row[0]:
                w_num = row[0]
                cond = get_phone_query_condition()
                params = get_phone_query_params(w_num)
                cur.execute(f"SELECT id, patient_code FROM patients WHERE {cond} AND status = 'ACTIVE' LIMIT 1;", params)
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
            ("CANCEL_APPOINTMENT", "DOCTOR_AVAILABILITY"),
            ("RESCHEDULE_APPOINTMENT", "BOOK_APPOINTMENT"),
            ("RESCHEDULE_APPOINTMENT", "CANCEL_APPOINTMENT"),
            ("RESCHEDULE_APPOINTMENT", "DOCTOR_AVAILABILITY"),
            ("REGISTER_PATIENT", "BOOK_APPOINTMENT"),
            ("IDENTIFY_PATIENT", "BOOK_APPOINTMENT"),
            ("GREETING", "DOCTOR_AVAILABILITY"),
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
            state["previous_question"] = None

    # Extract new entities and merge them
    extracted = entity_extractor.extract_entities(message_text)
    
    # If the user explicitly mentions a NEW doctor or NEW department different from current, clear slot selections
    new_doc_id = extracted.get("doctor_id")
    new_dept_id = extracted.get("department_id")
    curr_doc_id = state["entities"].get("doctor_id")
    curr_dept_id = state["entities"].get("department_id")

    if not state.get("confirmation_pending") and not state.get("change_pending") and not state.get("change_pending_field"):
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

    if state.get("confirmation_pending") and any(w in message_text.lower() for w in ["confirm", "btn_confirm_appt", "change", "btn_change_appt", "cancel", "btn_cancel_appt"]):
        state["intent"] = "BOOK_APPOINTMENT"
        intent = "BOOK_APPOINTMENT"

    if state.get("reg_confirmation_pending") and any(w in message_text.lower() for w in ["confirm", "btn_confirm_reg", "edit", "btn_edit_reg", "change"]):
        state["intent"] = "REGISTER_PATIENT"
        intent = "REGISTER_PATIENT"

    if intent == "GREETING":
        msg_l_btn = message_text.lower().strip()
        if any(w in msg_l_btn for w in ["book appointment", "btn_book_appt"]):
            state["intent"] = "BOOK_APPOINTMENT"
            intent = "BOOK_APPOINTMENT"
        elif any(w in msg_l_btn for w in ["doctor availability", "btn_doctor_avail"]):
            state["intent"] = "DOCTOR_AVAILABILITY"
            intent = "DOCTOR_AVAILABILITY"
        elif any(w in msg_l_btn for w in ["hospital information", "btn_hosp_info"]):
            state["intent"] = "HOSPITAL_INFORMATION"
            intent = "HOSPITAL_INFORMATION"

    if intent == "GREETING":
        state["interactive_buttons"] = []
        state["booking_stage"] = None
        state["previous_question"] = None
        state["confirmation_pending"] = False
        state["change_pending"] = False
        state["change_pending_field"] = None

        msg_l = message_text.lower().strip()
        is_first_time = any(w in msg_l for w in ["first time", "first-time", "btn_first_time", "new patient", "register"]) or msg_l == "1"
        is_existing = any(w in msg_l for w in ["existing patient", "existing", "btn_existing", "registered patient"]) or msg_l == "2"

        if is_first_time:
            state["intent"] = "REGISTER_PATIENT"
            state["patient_type"] = "FIRST_TIME"
            response_text = (
                "Welcome! 😊\n\n"
                "To create your patient profile, please send the following details in one message:\n\n"
                "• Full Name\n"
                "• Date of Birth\n"
                "• Gender\n"
                "• Phone Number\n"
                "• Reason for Visit\n\n"
                "Example:\n"
                "Arokiya Gilbrit, 08/09/2004, Male, 8072851813, fever and cough"
            )
            state["interactive_buttons"] = []
        elif is_existing or state.get("patient_id"):
            # Check existing patient in database via session patient_id or conversation lookup
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            p_name = None
            try:
                if state.get("patient_id"):
                    cur.execute("SELECT first_name, last_name FROM patients WHERE id = %s AND status = 'ACTIVE';", (state["patient_id"],))
                    r = cur.fetchone()
                    if r:
                        p_name = f"{r[0]} {r[1] or ''}".strip()
                if not p_name:
                    cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                    w_row = cur.fetchone()
                    if w_row and w_row[0]:
                        cond = get_phone_query_condition()
                        params = get_phone_query_params(w_row[0])
                        cur.execute(f"SELECT id, first_name, last_name FROM patients WHERE {cond} AND status = 'ACTIVE' LIMIT 1;", params)
                        r = cur.fetchone()
                        if r:
                            state["patient_id"] = r[0]
                            state["entities"]["patient_id"] = r[0]
                            p_name = f"{r[1]} {r[2] or ''}".strip()
            finally:
                cur.close()
                conn.close()

            if p_name:
                response_text = f"Welcome back, {p_name}! 👋\n\nHow can I help you today?"
                state["interactive_buttons"] = [
                    {"id": "btn_book_appt", "title": "Book Appointment"},
                    {"id": "btn_doctor_avail", "title": "Doctor Availability"},
                    {"id": "btn_my_appts", "title": "My Appointment"},
                    {"id": "btn_cancel_appt", "title": "Cancel Appointment"},
                    {"id": "btn_reschedule_appt", "title": "Reschedule Appointment"},
                    {"id": "btn_hosp_info", "title": "Hospital Information"}
                ]
            else:
                response_text = "I couldn't find a patient profile associated with this WhatsApp number.\n\nWould you like to register as a new patient?"
                state["interactive_buttons"] = [
                    {"id": "btn_first_time", "title": "Register"}
                ]
        else:
            response_text = (
                "👋 Hello! Welcome to Meridian Hospital.\n\n"
                "I’m your AI Patient Desk Assistant.\n\n"
                "I can help you with:\n"
                "📅 Appointments\n"
                "👨‍⚕️ Doctor availability\n"
                "❌ Cancellation / Rescheduling\n"
                "🏥 Hospital information\n"
                "📝 Pre-admission assistance\n\n"
                "Are you an existing patient or visiting us for the first time?"
            )
            state["interactive_buttons"] = [
                {"id": "btn_first_time", "title": "First-time Visitor"},
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
                cur.execute("SELECT id, first_name, last_name FROM patients WHERE patient_code = %s AND status = 'ACTIVE';", (p_code,))
                resolved_patient = cur.fetchone()
            elif match_phone:
                phone_num = match_phone.group(1)
                cond = get_phone_query_condition()
                params = get_phone_query_params(phone_num)
                cur.execute(f"SELECT id, first_name, last_name FROM patients WHERE {cond} AND status = 'ACTIVE' LIMIT 1;", params)
                resolved_patient = cur.fetchone()
            else:
                # Lookup by WhatsApp conversation number
                cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                w_row = cur.fetchone()
                if w_row and w_row[0]:
                    cond = get_phone_query_condition()
                    params = get_phone_query_params(w_row[0])
                    cur.execute(f"SELECT id, first_name, last_name FROM patients WHERE {cond} AND status = 'ACTIVE' LIMIT 1;", params)
                    resolved_patient = cur.fetchone()
        finally:
            cur.close()
            conn.close()
            
        if resolved_patient:
            pat_id, first_name, last_name = resolved_patient
            full_name = f"{first_name} {last_name or ''}".strip()
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
            
            response_text = f"Welcome back, {full_name}! 👋\n\nHow can I help you today?"
            state["interactive_buttons"] = [
                {"id": "btn_book_appt", "title": "Book Appointment"},
                {"id": "btn_doctor_avail", "title": "Doctor Availability"},
                {"id": "btn_my_appts", "title": "My Appointment"},
                {"id": "btn_cancel_appt", "title": "Cancel Appointment"},
                {"id": "btn_reschedule_appt", "title": "Reschedule Appointment"},
                {"id": "btn_hosp_info", "title": "Hospital Information"}
            ]
        else:
            response_text = "I couldn't find a patient profile associated with this WhatsApp number.\n\nWould you like to register as a new patient?"
            state["interactive_buttons"] = [
                {"id": "btn_first_time", "title": "Register"}
            ]

    elif intent == "REGISTER_PATIENT":
        state["interactive_buttons"] = []
        msg_raw = message_text.strip()
        reg_fields = state.get("registration_fields") or {
            "first_name": None, "last_name": None, "date_of_birth": None, "gender": None, "phone": None, "reason_for_visit": None
        }

        # Check confirmation tap or response
        if state.get("reg_confirmation_pending"):
            if any(w in msg_raw.lower() for w in ["confirm", "yes", "btn_confirm_reg", "correct", "ok"]):
                state["reg_confirmation_pending"] = False
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT MAX(CAST(SUBSTRING(patient_code FROM 2) AS INTEGER)) FROM patients WHERE patient_code ~ '^P[0-9]+';")
                    row = cur.fetchone()
                    next_num = (row[0] + 1) if (row and row[0]) else 11
                    next_code = f"P{next_num:03d}"

                    whatsapp_val = "919999999999"
                    cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                    w_row = cur.fetchone()
                    if w_row and w_row[0]:
                        whatsapp_val = w_row[0]

                    phone_val = reg_fields.get("phone") or (whatsapp_val if whatsapp_val != "919999999999" else "8072851813")
                    cur.execute("""
                        INSERT INTO patients (patient_code, first_name, last_name, date_of_birth, gender, phone, whatsapp_number, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
                        RETURNING id;
                    """, (
                        next_code,
                        reg_fields["first_name"] or "Patient",
                        reg_fields["last_name"] or ".",
                        reg_fields["date_of_birth"] or "2000-01-01",
                        reg_fields["gender"] or "Male",
                        phone_val,
                        whatsapp_val
                    ))
                    new_pat_id = cur.fetchone()[0]
                    cur.execute("UPDATE conversations SET patient_id = %s WHERE conversation_code = %s;", (new_pat_id, conversation_code))
                    conn.commit()

                    state["patient_id"] = new_pat_id
                    state["entities"]["patient_id"] = new_pat_id
                    state["intent"] = "GREETING"
                    state["registration_fields"] = { "first_name": None, "last_name": None, "date_of_birth": None, "gender": None, "phone": None, "reason_for_visit": None }

                    log_agent_action(conversation_code, "PATIENT_REGISTERED", {"patient_id": new_pat_id, "patient_code": next_code})
                    response_text = f"Your patient profile has been created successfully. ✅ (Patient Code: {next_code})\n\nHow can I help you today?"
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

                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                return {
                    "success": True,
                    "conversation_id": conversation_code,
                    "language": current_lang,
                    "intent": intent,
                    "response": response_text,
                    "missing_information": [],
                    "tool_called": "register_patient",
                    "interactive_buttons": state.get("interactive_buttons", [])
                }
            elif any(w in msg_raw.lower() for w in ["edit", "change", "btn_edit_reg", "no"]):
                state["reg_confirmation_pending"] = False
                state["registration_fields"] = { "first_name": None, "last_name": None, "date_of_birth": None, "gender": None, "phone": None, "reason_for_visit": None }
                response_text = "Please send your updated registration details in one message:\n\nFull Name, Date of Birth, Gender, Phone Number, Reason for Visit"
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                return {
                    "success": True,
                    "conversation_id": conversation_code,
                    "language": current_lang,
                    "intent": intent,
                    "response": response_text,
                    "missing_information": [],
                    "tool_called": None,
                    "interactive_buttons": []
                }

        # Extract structured info via LLM and fallback rule parser
        llm_info = llm_service.extract_structured_info(message_text, state, current_lang)
        if llm_info.get("first_name"):
            reg_fields["first_name"] = llm_info["first_name"]
            reg_fields["last_name"] = llm_info.get("last_name") or reg_fields.get("last_name") or "."
        if llm_info.get("gender"):
            reg_fields["gender"] = llm_info["gender"]
        if llm_info.get("phone"):
            reg_fields["phone"] = llm_info["phone"]
        if llm_info.get("reason"):
            reg_fields["reason_for_visit"] = llm_info["reason"]

        parts = [p.strip() for p in re.split(r"[,;\n]+", msg_raw) if p.strip()]

        # 1. Flexible Full Name Extraction
        if not reg_fields.get("first_name"):
            p_is_name = re.search(r"^([a-zA-Z\s\.]+)\s+(?:is\s+my\s+(?:full\s+)?name)\b", msg_raw, re.IGNORECASE)
            p_name_is = re.search(r"^(?:my\s+name\s+is|i\s+am|iam|name[:\s]+)\s+([a-zA-Z\s\.]+)", msg_raw, re.IGNORECASE)
            if p_is_name:
                raw_n = p_is_name.group(1).strip()
                n_parts = raw_n.split(None, 1)
                reg_fields["first_name"] = n_parts[0].capitalize()
                reg_fields["last_name"] = n_parts[1].capitalize() if len(n_parts) > 1 else "."
            elif p_name_is:
                raw_n = p_name_is.group(1).strip()
                n_parts = raw_n.split(None, 1)
                reg_fields["first_name"] = n_parts[0].capitalize()
                reg_fields["last_name"] = n_parts[1].capitalize() if len(n_parts) > 1 else "."
            elif len(parts) >= 1:
                first_part = parts[0]
                if not re.search(r"\d", first_part) and not any(kw in first_part.lower() for kw in ["register", "first", "existing", "male", "female", "appointment", "fever", "cough"]):
                    n_parts = first_part.split(None, 1)
                    reg_fields["first_name"] = n_parts[0].capitalize()
                    reg_fields["last_name"] = n_parts[1].capitalize() if len(n_parts) > 1 else "."

        # 2. Phone Extraction & Sender Number Fallback
        if not reg_fields.get("phone"):
            match_phone = re.search(r"\b(\d{10,12})\b", msg_raw)
            if match_phone:
                reg_fields["phone"] = match_phone.group(1)
            else:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                    r_w = cur.fetchone()
                    if r_w and r_w[0] and r_w[0] != "919999999999" and len(r_w[0]) >= 10:
                        reg_fields["phone"] = r_w[0]
                finally:
                    cur.close()
                    conn.close()

        # 3. Gender matching
        if re.search(r"\b(male|man)\b", msg_raw.lower()):
            reg_fields["gender"] = "Male"
        elif re.search(r"\b(female|woman)\b", msg_raw.lower()):
            reg_fields["gender"] = "Female"

        # 4. DOB parsing & validation
        is_command_msg = any(kw in msg_raw.lower() for kw in ["first-time", "first time", "visitor", "register", "hi", "hello", "existing"])
        dob_candidate = llm_info.get("date_of_birth")
        if not dob_candidate and not is_command_msg:
            for part in parts:
                if any(c.isdigit() for c in part) and not part.isdigit() and len(part) >= 6:
                    dob_candidate = part
                    break
        if dob_candidate:
            is_valid_dob, norm_dob, dob_err = date_normalizer.validate_dob(dob_candidate)
            if is_valid_dob and norm_dob:
                reg_fields["date_of_birth"] = norm_dob

        # 5. Reason for visit matching
        if not reg_fields.get("reason_for_visit"):
            reason_candidates = [p for p in parts if not any(c.isdigit() for c in p) and p.lower() not in ["male", "female", "other"] and p.lower() != (reg_fields.get("first_name") or "").lower()]
            if reason_candidates:
                reg_fields["reason_for_visit"] = reason_candidates[-1].capitalize()
            else:
                reg_fields["reason_for_visit"] = "General Consultation"

        fn = reg_fields.get("first_name")
        ln = reg_fields.get("last_name") or ""
        dob = reg_fields.get("date_of_birth")
        gen = reg_fields.get("gender")
        ph = reg_fields.get("phone")

        if fn and dob and gen and ph:
            state["registration_fields"] = reg_fields
            state["reg_confirmation_pending"] = True

            import datetime
            try:
                dob_obj = datetime.datetime.strptime(dob, "%Y-%m-%d").date()
                formatted_dob = dob_obj.strftime("%d-%b-%Y")
            except Exception:
                formatted_dob = dob

            full_n = f"{fn} {ln}".strip()
            response_text = (
                f"Thank you! 😊\n\n"
                f"I understood your details as:\n\n"
                f"👤 Name: {full_n}\n"
                f"🎂 Date of Birth: {formatted_dob}\n"
                f"👨 Gender: {gen}\n"
                f"📱 Phone: {ph}\n"
                f"📝 Reason: {reg_fields.get('reason_for_visit') or 'General Consultation'}\n\n"
                f"Please confirm your details."
            )
            state["interactive_buttons"] = [
                {"id": "btn_confirm_reg", "title": "Confirm"},
                {"id": "btn_edit_reg", "title": "Edit"}
            ]
        else:
            state["registration_fields"] = reg_fields
            known_list = []
            if fn: known_list.append(f"👤 Name: {fn} {ln}".strip())
            if dob: known_list.append(f"🎂 DOB: {dob}")
            if gen: known_list.append(f"👨 Gender: {gen}")
            if ph: known_list.append(f"📱 Phone: {ph}")

            known_text = "\n".join(known_list) if known_list else ""

            missing_req = []
            if not fn: missing_req.append("Full Name")
            if not dob: missing_req.append("Date of Birth (e.g., 08/09/2004)")
            if not gen: missing_req.append("Gender (Male / Female)")
            if not ph: missing_req.append("Phone Number")

            if known_text:
                detail_heading = "detail" if len(missing_req) == 1 else "details"
                together_suffix = "\n\nYou can send them together (e.g., 08/09/2004, Male, 8072851813)." if len(missing_req) > 1 else "."
                response_text = (
                    f"Got it, *{fn}*! 👍\n\n"
                    f"{known_text}\n\n"
                    f"Please provide the remaining {detail_heading}:\n• " + "\n• ".join(missing_req) + together_suffix
                )

            else:
                response_text = (
                    f"Welcome! 😊\n\n"
                    f"To create your patient profile, please send the following details in one message:\n\n"
                    f"• " + "\n• ".join(missing_req) + "\n\n"
                    f"Example:\n"
                    f"Arokiya Gilbrit, 08/09/2004, Male, 8072851813, fever and cough"
                )
            state["interactive_buttons"] = []

    elif intent == "EMERGENCY_GUIDANCE":
        log_agent_action(conversation_code, "EMERGENCY_DETECTED", {"trigger_message": message_text})
        response_text = (
            "🚨 This may be a medical emergency.\n\n"
            "Please seek immediate medical attention.\n\n"
            "Call 112 or 108 or go to the nearest Emergency Department immediately.\n\n"
            "Meridian Hospital Emergency Services are available 24/7.\n\n"
            "Do not wait for an appointment or rely on this chatbot for emergency treatment."
        )
        state["interactive_buttons"] = []
        
    elif intent == "HUMAN_ESCALATION":
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("UPDATE conversations SET conversation_status = 'ESCALATED' WHERE conversation_code = %s RETURNING id, patient_id;", (conversation_code,))
            row = cur.fetchone()
            if row:
                conv_db_id, pat_db_id = row
                cur.execute("SELECT id FROM escalations WHERE conversation_id = %s AND status = 'OPEN';", (conv_db_id,))
                if not cur.fetchone():
                    cur.execute("""
                        INSERT INTO escalations (conversation_id, patient_id, escalation_reason, patient_question)
                        VALUES (%s, %s, 'Patient requested human staff escalation.', %s);
                    """, (conv_db_id, pat_db_id, message_text))
            conn.commit()
            log_agent_action(conversation_code, "HUMAN_ESCALATION", {"reason": message_text})
        except Exception as e:
            conn.rollback()
            print("Failed to record escalation in database:", e)
        finally:
            cur.close()
            conn.close()

        response_text = (
            "Of course. I’ll forward your request to the hospital support team.\n\n"
            "Escalation created successfully.\n\n"
            "Status: 🟡 OPEN\n\n"
            "A hospital staff member will review your request."
        )
        state["interactive_buttons"] = []

    elif intent == "SYMPTOM_GUIDANCE":
        # Use the canonical map_symptom_to_department_name for consistent routing
        resolved_dept = entity_extractor.map_symptom_to_department_name(message_text)

        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM departments WHERE department_name ILIKE %s AND status = 'ACTIVE';", (resolved_dept,))
        row = cur.fetchone()
        dept_id = row[0] if row else None
        cur.close()
        conn.close()

        response_text = language_service.translate_response("SYMPTOM_GUIDANCE", current_lang, dept=resolved_dept)
        state["previous_question"] = "would_you_like_to_check_available_doctors"

        if dept_id:
            state["entities"]["department_id"] = dept_id
        if state["entities"]["reason"] is None:
            state["entities"]["reason"] = message_text.strip()


    elif intent == "DOCTOR_AVAILABILITY":
        state["interactive_buttons"] = []
        dept_id = state["entities"].get("department_id")
        doc_id = state["entities"].get("doctor_id")
        appt_date = state["entities"].get("appointment_date")

        # If doctor_id is present, return available slots for that doctor
        if doc_id:
            if not appt_date:
                appt_date = entity_extractor.parse_natural_date("tomorrow")
                state["entities"]["appointment_date"] = appt_date
            doc_info = resolve_doctor_details(doc_id)
            res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
            slots_list = res_slots.get("slots", []) if res_slots.get("success") else []
            if slots_list:
                formatted_slots = [format_time_12h(s) for s in slots_list]
                slots_text = "\n• ".join(formatted_slots)
                response_text = f"Available times for {doc_info['name']} on {appt_date} are:\n• {slots_text}\n\nWhich time would you prefer?"
            else:
                response_text = (
                    f"Sorry, *{doc_info['name']}* has no available slots on *{appt_date}*. "
                    f"All slots are fully booked for that day.\n\n"
                    f"📅 Please try a different date. Which date would you prefer?"
                )
            state["intent"] = "BOOK_APPOINTMENT"
            state["previous_question"] = None
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
            return {
                "response": response_text,
                "intent": "BOOK_APPOINTMENT",
                "language": current_lang,
                "interactive_buttons": []
            }

        # Step 1: No department/doctor known yet — ask about symptom or department
        elif not dept_id and not doc_id:
            state["previous_question"] = "avail_ask_dept_or_symptom"
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT department_name FROM departments WHERE status='ACTIVE' ORDER BY id;")
                dept_names = [r[0] for r in cur.fetchall()]
            finally:
                cur.close()
                conn.close()
            dept_list = "  ·  ".join(dept_names)
            response_text = (
                "Sure! To find the right doctor, please tell me:\n\n"
                "*Which department* are you looking for, or *what symptoms/condition* do you have?\n\n"
                f"🏥 Departments: {dept_list}"
            )
            missing_info.append("department_or_symptom")

        # Step 2: Department known, but no date yet — ask for the date
        elif not appt_date:
            dept_label = ""
            if dept_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT department_name FROM departments WHERE id = %s;", (dept_id,))
                    row = cur.fetchone()
                    dept_label = f" ({row[0]})"
                finally:
                    cur.close()
                    conn.close()

            state["previous_question"] = "avail_ask_date"
            response_text = (
                f"Got it{dept_label}! 📅 Which date would you like to check availability for?\n\n"
                "You can say *today*, *tomorrow*, a *weekday* (e.g. Monday), or a specific date (e.g. 05 Sep)."
            )
            missing_info.append("appointment_date")

        # Step 3: Both department and date known — show available slots per doctor
        else:
            tool_called = "get_doctor_availability"
            response_text = format_doctor_availability_response(dept_id, appt_date, conversation_code)
            state["previous_question"] = None

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

        # ─── Handle split time input: '5' then 'PM' in separate messages ───
        # If previous message was a bare digit (stored in pending_time_digit) and
        # this message is 'pm'/'am', combine them.
        msg_lwr = message_text.lower().strip()
        if msg_lwr in ["pm", "am", "p.m.", "a.m."]:
            pending_digit = state.get("pending_time_digit")
            curr_t = state["entities"].get("appointment_time")
            if pending_digit:
                # Combine: pending_digit was stored as HH:00 (possibly wrong period)
                parts_t = str(pending_digit).split(":")
                hh = int(parts_t[0])
                mm = parts_t[1] if len(parts_t) > 1 else "00"
                if "pm" in msg_lwr and hh < 12:
                    hh += 12
                elif "am" in msg_lwr and hh == 12:
                    hh = 0
                state["entities"]["appointment_time"] = f"{hh:02d}:{mm}"
                state["pending_time_digit"] = None
            elif curr_t:
                # Correct already-stored time's AM/PM
                parts_t = curr_t.split(":")
                hh = int(parts_t[0])
                mm = parts_t[1] if len(parts_t) > 1 else "00"
                if "pm" in msg_lwr and hh < 12:
                    hh += 12
                elif "am" in msg_lwr and hh == 12:
                    hh = 0
                state["entities"]["appointment_time"] = f"{hh:02d}:{mm}"
        else:
            state["pending_time_digit"] = None

        # Detect standalone digit (save as pending_time_digit for next AM/PM message)
        _is_standalone_digit = re.match(r"^\d{1,2}$", msg_lwr.strip())
        if _is_standalone_digit:
            _d = int(msg_lwr.strip())
            if 1 <= _d <= 12:
                state["pending_time_digit"] = f"{_d:02d}:00"
            else:
                state["pending_time_digit"] = None
        elif msg_lwr not in ["pm", "am", "p.m.", "a.m."]:
            state["pending_time_digit"] = None

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
                    # Resolve patient_id for booking (Self vs Child/Family Member)
                    app_for = state["entities"].get("appointment_for")
                    c_name = state["entities"].get("patient_name") or state["entities"].get("patient_name_override")
                    
                    if (app_for in ["CHILD", "FAMILY_MEMBER"] or c_name) and pat_id:
                        booking_pat_id = resolve_or_create_child_patient(
                            parent_patient_id=pat_id,
                            child_name=c_name or "Family Member",
                            dob_str=state["entities"].get("date_of_birth"),
                            gender=state["entities"].get("gender"),
                            email=state["entities"].get("email"),
                            relationship=state["entities"].get("relationship") or "CHILD"
                        )
                    else:
                        booking_pat_id = pat_id

                    tool_called = "book_appointment"
                    res = tool_registry.tool_book_appointment(
                        conversation_code=conversation_code,
                        patient_id=booking_pat_id,
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
                        display_pat = c_name if (c_name and app_for in ["CHILD", "FAMILY_MEMBER"]) else None
                        if not display_pat:
                            conn = db_config.get_db_connection()
                            cur = conn.cursor()
                            try:
                                cur.execute("SELECT first_name, last_name FROM patients WHERE id = %s;", (booking_pat_id,))
                                p_row = cur.fetchone()
                                if p_row:
                                    display_pat = f"{p_row[0]} {p_row[1] or ''}".strip()
                            finally:
                                cur.close()
                                conn.close()

                        email_note = f"\n\nA confirmation email has also been sent to {state['entities'].get('email')}." if state["entities"].get("email") else "\n\nA confirmation email has also been sent."

                        response_text = (
                            f"✅ *Appointment confirmed!*\n\n"
                            f"Patient: {display_pat or 'Patient'}\n"
                            f"Doctor: {doc_details['name']}\n"
                            f"Department: {doc_details['department']}\n"
                            f"Date: {appt_date}\n"
                            f"Time: {format_time_12h(appt_time)}\n"
                            f"Appointment ID: {res['data']['booking_id']}"
                            f"{email_note}\n\n"
                            f"Thank you for using Meridian Hospital Patient Desk.\n\n"
                            f"Would you like information about:"
                        )
                        state["intent"] = "POST_BOOKING"
                        state["previous_question"] = "post_booking_help"
                        state["entities"] = {
                            "patient_id": state["patient_id"],
                            "doctor_id": None, "department_id": None,
                            "appointment_date": None, "appointment_time": None,
                            "booking_id": None, "reason": None
                        }
                        state["interactive_buttons"] = [
                            {"id": "btn_hosp_info", "title": "Hospital Information"},
                            {"id": "btn_doctor_avail", "title": "Doctor Information"},
                            {"id": "btn_other_services", "title": "Other Services"}
                        ]
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
                response_text = "What detail would you like to change? (Patient Name, Doctor, Date, Time, or Reason)"
            else:
                response_text = "Please confirm your appointment details using the options below:"
                state["interactive_buttons"] = [
                    {"id": "btn_confirm_appt", "title": "Confirm Appointment"},
                    {"id": "btn_change_appt", "title": "Change Details"},
                    {"id": "btn_cancel_appt", "title": "Cancel"}
                ]
        else:
            rule_ext = entity_extractor.extract_entities(message_text)

            # 0. Check explicit request for available times / slots when doctor/date/dept context exists
            avail_query_kws = [
                "available time", "available times", "available slot", "available slots",
                "what times", "what time", "show time", "show times", "show slot", "show slots",
                "tell available", "can you tell", "list times", "list slots", "time slots",
                "when can i book", "when available"
            ]
            is_asking_slots = any(kw in msg_clean for kw in avail_query_kws)
            doc_id_ctx = state["entities"].get("doctor_id") or rule_ext.get("doctor_id")
            dept_id_ctx = state["entities"].get("department_id") or rule_ext.get("department_id")
            appt_date_ctx = state["entities"].get("appointment_date") or entity_extractor.parse_natural_date(message_text.lower())

            if is_asking_slots and (doc_id_ctx or dept_id_ctx or appt_date_ctx):
                if not appt_date_ctx:
                    appt_date_ctx = entity_extractor.parse_natural_date("tomorrow")
                    state["entities"]["appointment_date"] = appt_date_ctx
                
                if not doc_id_ctx and dept_id_ctx:
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT id FROM doctors WHERE department_id = %s AND status = 'ACTIVE' ORDER BY id LIMIT 1;", (dept_id_ctx,))
                        r_doc = cur.fetchone()
                        if r_doc:
                            doc_id_ctx = r_doc[0]
                            state["entities"]["doctor_id"] = doc_id_ctx
                    finally:
                        cur.close()
                        conn.close()

                if doc_id_ctx:
                    doc_info = resolve_doctor_details(doc_id_ctx)
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id_ctx, appt_date_ctx)
                    slots_list = res_slots.get("slots", []) if res_slots.get("success") else []
                    if slots_list:
                        formatted_slots = [format_time_12h(s) for s in slots_list]
                        slots_text = "\n• ".join(formatted_slots)
                        response_text = f"Available times for {doc_info['name']} on {appt_date_ctx} are:\n• {slots_text}\n\nWhich time would you prefer?"
                    else:
                        response_text = (
                            f"Sorry, *{doc_info['name']}* has no available slots on *{appt_date_ctx}*. "
                            f"All slots are fully booked for that day.\n\n"
                            f"📅 Please try a different date. Which date would you prefer?"
                        )
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

            # 1. Check if this is a fresh generic appointment initiation command
            has_active_booking_context = bool(
                state.get("entities", {}).get("doctor_id") or
                state.get("entities", {}).get("department_id") or
                state.get("entities", {}).get("appointment_date") or
                state.get("booking_stage") == "AWAITING_SYMPTOM" or
                state.get("previous_question") == "ask_booking_symptom"
            )

            is_generic_booking_start = (
                msg_clean in ["book appointment", "btn_book_appt", "book an appointment", "i want to book an appointment", "appointment booking", "book appt", "book"] and
                not has_active_booking_context and
                not state.get("confirmation_pending")
            )

            if is_generic_booking_start:
                # Clear stale entities for fresh booking
                state["entities"]["doctor_id"] = None
                state["entities"]["department_id"] = None
                state["entities"]["reason"] = None
                state["entities"]["appointment_date"] = None
                state["entities"]["appointment_time"] = None
                state["booking_stage"] = "AWAITING_SYMPTOM"
                state["previous_question"] = "ask_booking_symptom"
                
                response_text = (
                    "Sure! I can help you book an appointment.\n\n"
                    "Which disease, symptom, or cause do you have? (e.g., Fever, Cold, Chest pain, Earache, Joint pain, Skin rash)"
                )
                state["interactive_buttons"] = []
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                return {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": []
                }

            # 2. Handle patient response to symptom/cause prompt
            if state.get("booking_stage") == "AWAITING_SYMPTOM" or state.get("previous_question") == "ask_booking_symptom":
                state["booking_stage"] = None
                state["previous_question"] = None
                symptom_input = message_text.strip()
                
                # Map symptom to department
                dept_name = entity_extractor.map_symptom_to_department_name(symptom_input)
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT id, department_name FROM departments WHERE department_name ILIKE %s;", (dept_name,))
                    row = cur.fetchone()
                    if not row:
                        response_text = f"I can help you with {dept_name}. There are currently no {dept_name} appointments available. Would you like to check another date?"
                        state_manager.save_conversation_state(conversation_code, state)
                        log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                        return {
                            "response": response_text,
                            "intent": "BOOK_APPOINTMENT",
                            "language": current_lang,
                            "interactive_buttons": []
                        }
                    dept_id, resolved_dept_name = row[0], row[1]
                    
                    cur.execute("SELECT id, display_name, specialization FROM doctors WHERE department_id = %s AND status = 'ACTIVE' ORDER BY id;", (dept_id,))
                    docs = cur.fetchall()
                finally:
                    cur.close()
                    conn.close()

                if not docs:
                    response_text = f"I can help you with {resolved_dept_name}. There are currently no {resolved_dept_name} appointments available. Would you like to check another date?"
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

                state["entities"]["department_id"] = dept_id
                state["entities"]["reason"] = symptom_input.capitalize()
                
                target_date = entity_extractor.parse_natural_date(message_text.lower())
                if not target_date:
                    target_date = entity_extractor.parse_natural_date("tomorrow")
                state["entities"]["appointment_date"] = target_date

                # Build doctor listing & slots
                spec_singular, spec_plural = get_specialist_titles(resolved_dept_name)
                doctor_listings = []
                buttons = []
                for doc_id, doc_name, doc_spec in docs:
                    doc_name_clean = doc_name.replace("Dr. Dr.", "Dr.").strip() if doc_name else "Doctor"
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, target_date)
                    slots = res_slots.get("slots", []) if res_slots.get("success") else []
                    slots_str = ", ".join([format_time_12h(s) for s in slots[:6]]) if slots else "No remaining slots on this date"
                    doctor_listings.append(f"• *{doc_name_clean}* — {resolved_dept_name} (Available slots on {target_date}:\n  {slots_str})")
                    buttons.append({"id": f"btn_doc_{doc_id}", "title": doc_name_clean[:20]})

                if docs:
                    state["entities"]["doctor_id"] = docs[0][0]

                doc_text_block = "\n".join(doctor_listings)
                
                response_text = (
                    f"For *{symptom_input.capitalize()}*, you should consult our *\"{resolved_dept_name}\"* department.\n\n"
                    f"Here are the available {spec_plural}:\n"
                    f"{doc_text_block}\n\n"
                    f"Which doctor and preferred time (e.g., 09:00 AM, 10:00 AM) would you like to book?"
                )
                
                state["interactive_buttons"] = buttons[:3]
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                return {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": state["interactive_buttons"]
                }

            # 3. Handle value entry if we are waiting for a specific updated field from Change Details
            if state.get("change_pending_field"):
                field_type = state["change_pending_field"]
                state["change_pending_field"] = None
                state["change_pending"] = False
                val = message_text.strip()
                if val and not entity_extractor.is_command_phrase(val):
                    if field_type == "patient_name":
                        state["entities"]["patient_name_override"] = val
                    elif field_type == "reason":
                        state["entities"]["reason"] = val
                    elif field_type == "time":
                        parsed_t = entity_extractor.parse_natural_time(val.lower())
                        if parsed_t:
                            state["entities"]["appointment_time"] = parsed_t
                    elif field_type == "date":
                        norm_d, _, _ = date_normalizer.parse_and_normalize_date(val)
                        if norm_d:
                            state["entities"]["appointment_date"] = norm_d

            # 2. Handle change_pending field selection prompt response
            elif state.get("change_pending"):
                state["change_pending"] = False
                if any(w in msg_clean for w in ["name", "patient", "person"]):
                    state["change_pending_field"] = "patient_name"
                    response_text = "Please enter the updated patient full name:"
                    state["interactive_buttons"] = []
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                elif any(w in msg_clean for w in ["reason", "problem", "symptom", "issue", "why"]):
                    state["change_pending_field"] = "reason"
                    response_text = "Please enter your updated reason for visit:"
                    state["interactive_buttons"] = []
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                elif any(w in msg_clean for w in ["time", "slot", "timing", "hour", "clock"]):
                    state["change_pending_field"] = "time"
                    state["entities"]["appointment_time"] = None
                    doc_id = state["entities"].get("doctor_id")
                    appt_date = state["entities"].get("appointment_date")
                    slots_str = ""
                    if doc_id and appt_date:
                        res_alt = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                        if res_alt.get("slots"):
                            slots_str = f"\nAvailable slots on {appt_date}: {', '.join(res_alt['slots'])}"
                    response_text = f"Please enter your updated preferred appointment time:{slots_str}"
                    state["interactive_buttons"] = []
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                elif any(w in msg_clean for w in ["date", "day", "tomorrow", "today", "when"]):
                    state["change_pending_field"] = "date"
                    state["entities"]["appointment_date"] = None
                    state["entities"]["appointment_time"] = None
                    response_text = "Please enter your updated preferred appointment date (e.g. tomorrow, 2026-09-03):"
                    state["interactive_buttons"] = []
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                elif any(w in msg_clean for w in ["doctor", "dept", "department", "specialist", "dr"]):
                    state["entities"]["doctor_id"] = None
                    state["entities"]["department_id"] = None
                    state["entities"]["appointment_date"] = None
                    state["entities"]["appointment_time"] = None
                    response_text = "Which doctor or department would you like to switch to?"
                    state["interactive_buttons"] = []
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                else:
                    state["change_pending"] = True
                    response_text = "Please specify which detail you would like to change: Patient Name, Doctor, Date, Time, or Reason."
                    state["interactive_buttons"] = []
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

            # 2. Handle explicit available time/slots query
            avail_query_kws = [
                "available time", "available times", "available slot", "available slots",
                "what times", "what time", "show time", "show times", "show slot", "show slots",
                "show the available", "can you show", "when will", "when is", "when does",
                "when can", "when.*available", "available.*time"
            ]
            if any(kw in msg_clean for kw in avail_query_kws):
                doc_id = state["entities"].get("doctor_id")
                appt_date = state["entities"].get("appointment_date")
                if doc_id and appt_date:
                    doc_info = resolve_doctor_details(doc_id)
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                    slots_list = res_slots.get("slots", []) if res_slots.get("success") else []
                    if slots_list:
                        slots_text = ", ".join(slots_list)
                        response_text = f"Here are the available time slots for {doc_info['name']} on {appt_date}:\n• {slots_text}\n\nWhich time would you prefer?"
                    else:
                        # No slots — clear the date and ask for another
                        state["entities"]["appointment_date"] = None
                        response_text = (
                            f"Sorry, *{doc_info['name']}* has no available slots on *{appt_date}*. "
                            f"All slots are fully booked for that day.\n\n"
                            f"📅 Please try a different date. Which date would you prefer?"
                        )
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

            # 3. Extract multi-field entities via LLM / Rule Extractor
            llm_info = llm_service.extract_structured_info(message_text, state, current_lang)
            rule_ext = entity_extractor.extract_entities(message_text)

            # ── Symptom → Department fallback ──
            # If entity_extractor did not resolve a department from explicit keywords,
            # try map_symptom_to_department_name to catch natural language symptoms.
            if not rule_ext.get("department_id") and not state["entities"].get("department_id"):
                symptom_dept_name = entity_extractor.map_symptom_to_department_name(message_text)
                if symptom_dept_name and symptom_dept_name != "General Medicine":
                    # Only override with General Medicine as last resort
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT id FROM departments WHERE department_name ILIKE %s AND status='ACTIVE';", (symptom_dept_name,))
                        dept_row = cur.fetchone()
                        if dept_row:
                            rule_ext["department_id"] = dept_row[0]
                    finally:
                        cur.close()
                        conn.close()
                elif symptom_dept_name == "General Medicine":
                    # Also handle the General Medicine fallback
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT id FROM departments WHERE department_name ILIKE %s AND status='ACTIVE';", (symptom_dept_name,))
                        dept_row = cur.fetchone()
                        if dept_row:
                            rule_ext["department_id"] = dept_row[0]
                    finally:
                        cur.close()
                        conn.close()

            # Handle change_pending_field for patient_name
            if state.get("change_pending_field") == "patient_name":
                state["change_pending_field"] = None
                new_name = message_text.strip()
                if new_name and not entity_extractor.is_command_phrase(new_name):
                    state["entities"]["patient_name_override"] = new_name

            # Handle standalone "am" / "pm" when time digit was sent previously
            msg_clean_time = message_text.lower().strip()
            if msg_clean_time in ["am", "pm", "a.m.", "p.m."]:
                curr_t = state["entities"].get("appointment_time")
                if curr_t:
                    parts = curr_t.split(":")
                    hh = int(parts[0])
                    mm = parts[1]
                    if "pm" in msg_clean_time and hh < 12:
                        hh += 12
                    elif "am" in msg_clean_time and hh == 12:
                        hh = 0
                    state["entities"]["appointment_time"] = f"{hh:02d}:{mm}"

            # Doctor & Department matching
            if rule_ext.get("doctor_id"):
                state["entities"]["doctor_id"] = rule_ext["doctor_id"]
            elif llm_info.get("doctor") and rule_ext.get("doctor_id"):
                state["entities"]["doctor_id"] = rule_ext["doctor_id"]

            if rule_ext.get("department_id") and not state["entities"].get("doctor_id"):
                state["entities"]["department_id"] = rule_ext["department_id"]
            elif llm_info.get("department") and not state["entities"].get("department_id") and not state["entities"].get("doctor_id"):
                if rule_ext.get("department_id"):
                    state["entities"]["department_id"] = rule_ext["department_id"]

            # Always sync department_id from doctor_id if doctor_id is present
            if state["entities"].get("doctor_id"):
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT department_id FROM doctors WHERE id = %s;", (state["entities"]["doctor_id"],))
                    row = cur.fetchone()
                    if row:
                        state["entities"]["department_id"] = row[0]
                finally:
                    cur.close()
                    conn.close()

            # Auto-resolve doctor from department if department is set but doctor is missing
            if state["entities"].get("department_id") and not state["entities"].get("doctor_id"):
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT id FROM doctors WHERE department_id = %s ORDER BY id LIMIT 1;", (state["entities"]["department_id"],))
                    row = cur.fetchone()
                    if row:
                        state["entities"]["doctor_id"] = row[0]
                finally:
                    cur.close()
                    conn.close()


            # Date Normalization & Ambiguity Check
            date_candidate = llm_info.get("appointment_date") or message_text
            norm_date, is_ambig, _ = date_normalizer.parse_and_normalize_date(date_candidate)
            if norm_date:
                state["entities"]["appointment_date"] = norm_date

            # Time parsing (Rule extractor + LLM)
            parsed_time = entity_extractor.parse_natural_time(message_text.lower())
            if parsed_time:
                state["entities"]["appointment_time"] = parsed_time
            elif llm_info.get("appointment_time"):
                state["entities"]["appointment_time"] = llm_info["appointment_time"]
            
            # Sanitize reason: Clear command phrases or time expressions incorrectly stored as reason
            curr_reason = state["entities"].get("reason")
            if curr_reason:
                if entity_extractor.is_command_phrase(curr_reason) or entity_extractor.is_date_or_time_expression(curr_reason):
                    state["entities"]["reason"] = None

            # Assign new reason if valid and not a date/time/command expression
            if not state["entities"].get("reason"):
                if rule_ext.get("department_id") and not entity_extractor.is_command_phrase(message_text) and not entity_extractor.is_date_or_time_expression(message_text):
                    state["entities"]["reason"] = message_text.strip()
                elif llm_info.get("reason") and not entity_extractor.is_command_phrase(llm_info["reason"]) and not entity_extractor.is_date_or_time_expression(llm_info["reason"]):
                    state["entities"]["reason"] = llm_info["reason"]
                elif not entity_extractor.is_date_or_time_expression(message_text) and not entity_extractor.is_command_phrase(message_text):
                    state["entities"]["reason"] = message_text.strip()

            pat_id = state["patient_id"]
            doc_id = state["entities"]["doctor_id"]
            dept_id = state["entities"]["department_id"]
            appt_date = state["entities"]["appointment_date"]
            appt_time = state["entities"]["appointment_time"]
            reason = state["entities"]["reason"] or "General Consultation"
            state["entities"]["reason"] = reason

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
                # If doctor and date are known, but time is missing, list available slots for that date!
                if doc_id and appt_date and not appt_time:
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                    doc_info = resolve_doctor_details(doc_id)
                    available_slots = res_slots.get("slots", []) if res_slots.get("success") else []

                    if available_slots:
                        formatted_slots = [format_time_12h(s) for s in available_slots]
                        slots_str = ", ".join(formatted_slots)
                        response_text = (
                            f"For *{appt_date}*, *{doc_info['name']}* has the following available time slots:\n\n"
                            f"• {slots_str}\n\n"
                            f"Which time would you prefer to book?"
                        )
                    else:
                        info = get_doctor_working_info_and_next_slots(doc_id, appt_date)
                        state["entities"]["appointment_date"] = None
                        if info.get("next_date"):
                            formatted_next = [format_time_12h(s) for s in info["next_slots"]]
                            next_str = ", ".join(formatted_next)
                            response_text = (
                                f"*{doc_info['name']}* is not scheduled to work on *{appt_date}* ({info['day_name']}).\n"
                                f"🏥 Working days: *{info['working_days_str']}*.\n\n"
                                f"📅 Available slots on the next working day (*{info['next_date']}*):\n"
                                f"• {next_str}\n\n"
                                f"Which date or time would you prefer to book?"
                            )
                        else:
                            response_text = (
                                f"Sorry, *{doc_info['name']}* has no available slots on *{appt_date}*.\n\n"
                                f"📅 Please try a different date. Which date would you prefer?"
                            )
                    missing_info = ["appointment_time"]
                else:
                    known_parts = []
                    if doc_id:
                        known_parts.append(f"Doctor: {resolve_doctor_details(doc_id)['name']}")
                    if appt_date:
                        known_parts.append(f"Date: {appt_date}")
                    if appt_time:
                        known_parts.append(f"Time: {appt_time}")

                    known_summary = "I have " + ", ".join(known_parts) + " noted.\n\n" if known_parts else ""
                    detail_heading = "detail" if len(missing_fields_list) == 1 else "details"
                    together_suffix = "\n\nYou can send them together." if len(missing_fields_list) > 1 else "."
                    response_text = f"Sure! I can help you book an appointment. {known_summary}Please provide the remaining {detail_heading}:\n\n• " + "\n• ".join(missing_fields_list) + together_suffix
                    missing_info = missing_fields_list

            else:
                # All required fields present -> check real DB slot availability
                tool_called = "get_available_slots"
                res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                doc_info = resolve_doctor_details(doc_id)

                available_slots = res_slots.get("slots", []) if res_slots.get("success") else []
                if appt_time in available_slots:
                    state["confirmation_pending"] = True
                    pat_name = state["entities"].get("patient_name_override")
                    if not pat_name and pat_id:
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
                    if not pat_name:
                        pat_name = "Patient"

                    response_text = f"Please confirm your appointment:\n\nPatient: {pat_name}\nDoctor: {doc_info['name']}\nDepartment: {doc_info['department']}\nDate: {appt_date}\nTime: {format_time_12h(appt_time)}\nReason: {reason}"
                    state["interactive_buttons"] = [
                        {"id": "btn_confirm_appt", "title": "Confirm Appointment"},
                        {"id": "btn_change_appt", "title": "Change Details"},
                        {"id": "btn_cancel_appt", "title": "Cancel"}
                    ]
                else:
                    state["entities"]["appointment_time"] = None
                    state["confirmation_pending"] = False
                    if available_slots:
                        formatted_slots = [format_time_12h(s) for s in available_slots]
                        alt_slots_str = ", ".join(formatted_slots)
                        response_text = (
                            f"*{doc_info['name']}* is not available at *{format_time_12h(appt_time)}* on *{appt_date}*. "
                            f"That slot is already booked.\n\n"
                            f"⏰ Available slots for *{doc_info['name']}* on *{appt_date}*:\n"
                            f"• {alt_slots_str}\n\n"
                            f"Please reply with your preferred time from the list above."
                        )
                    else:
                        info = get_doctor_working_info_and_next_slots(doc_id, appt_date)
                        state["entities"]["appointment_date"] = None
                        if info.get("next_date"):
                            formatted_next = [format_time_12h(s) for s in info["next_slots"]]
                            next_str = ", ".join(formatted_next)
                            response_text = (
                                f"*{doc_info['name']}* is not scheduled to work on *{appt_date}* ({info['day_name']}).\n"
                                f"🏥 Working days: *{info['working_days_str']}*.\n\n"
                                f"📅 Available slots on the next working day (*{info['next_date']}*):\n"
                                f"• {next_str}\n\n"
                                f"Which date or time would you prefer to book?"
                            )
                        else:
                            response_text = (
                                f"Sorry, *{doc_info['name']}* has no available slots on *{appt_date}*.\n\n"
                                f"📅 Please try a different date. Which date would you prefer?"
                            )

    elif intent == "DEPENDENT_PATIENT":
        """
        DEPENDENT_PATIENT flow:
        Turn 1: Patient says 'book for my son'
        Turn 2 (if needed): Collect dependent's name, DOB, gender, symptoms
        Turn 3: Create child patient record → proceed to BOOK_APPOINTMENT
        """
        state["interactive_buttons"] = []
        msg_raw = message_text.strip()

        # Extract relationship from message
        rel_info = entity_extractor.extract_relationship(message_text)
        if rel_info.get("relationship"):
            state["patient_relationship"] = rel_info["relationship"]
            state["appointment_for"] = rel_info["appointment_for"]

        dep_stage = state.get("dependent_collection_stage")
        rel = state.get("patient_relationship") or "family member"

        # Also extract any symptom from the current message
        symptom_dept_name = entity_extractor.map_symptom_to_department_name(message_text)
        if symptom_dept_name:
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT id FROM departments WHERE department_name ILIKE %s AND status='ACTIVE';", (symptom_dept_name,))
                d_row = cur.fetchone()
                if d_row:
                    state["entities"]["department_id"] = d_row[0]
                    state["entities"]["reason"] = msg_raw
            finally:
                cur.close()
                conn.close()

        if dep_stage is None:
            # Turn 1: We just detected DEPENDENT_PATIENT. Ask for their name.
            rel_label = rel.lower() if rel else "family member"
            state["dependent_collection_stage"] = "AWAITING_NAME"
            response_text = (
                f"Sure! I'll help you book an appointment for your {rel_label}. 😊\n\n"
                f"Please share your {rel_label}'s details in one message:\n"
                f"• Full Name\n"
                f"• Date of Birth (e.g., 12/05/2010)\n"
                f"• Gender (Male / Female)\n"
                f"• Main symptoms or reason for visit\n\n"
                f"Example: Ravi Kumar, 12/05/2010, Male, fever and cough"
            )

        elif dep_stage == "AWAITING_NAME":
            # Turn 2: Parse provided fields
            llm_dep = llm_service.extract_structured_info(message_text, state, current_lang)

            actual_name = llm_dep.get("first_name") or llm_dep.get("patient_name")
            dob = llm_dep.get("date_of_birth")
            gender = llm_dep.get("gender")
            symptom_text = msg_raw

            # Try comma-separated fallback extraction
            if not actual_name:
                parts = [p.strip() for p in re.split(r"[,;]+", msg_raw) if p.strip()]
                if parts:
                    actual_name = parts[0]
                if len(parts) > 1:
                    dob = dob or parts[1]
                if len(parts) > 2:
                    gender_raw = parts[2].lower()
                    if "male" in gender_raw or "boy" in gender_raw or "man" in gender_raw:
                        gender = "Male"
                    elif "female" in gender_raw or "girl" in gender_raw or "woman" in gender_raw:
                        gender = "Female"
                if len(parts) > 3:
                    symptom_text = parts[3]

            # Normalize DOB
            if dob:
                norm_dob, _, _ = date_normalizer.parse_and_normalize_date(dob)
                dob = norm_dob or dob

            state["actual_patient_name"] = actual_name
            state["entities"]["date_of_birth"] = dob
            state["entities"]["gender"] = gender

            # Map symptom → department
            dep_symptom_dept = entity_extractor.map_symptom_to_department_name(symptom_text)
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT id FROM departments WHERE department_name ILIKE %s AND status='ACTIVE';", (dep_symptom_dept,))
                d_row = cur.fetchone()
                if d_row:
                    state["entities"]["department_id"] = d_row[0]
                    state["entities"]["reason"] = symptom_text
            finally:
                cur.close()
                conn.close()

            if not actual_name:
                # Still missing name — ask again
                response_text = (
                    f"I couldn't catch the name. Could you please share your {rel.lower()}'s full name?\n\n"
                    f"(Example: Ravi Kumar, 12/05/2010, Male, fever)"
                )
            else:
                # Sufficient info — create or look up dependent patient
                parent_id = state.get("patient_id")
                if parent_id:
                    dep_patient_id = resolve_or_create_child_patient(
                        parent_patient_id=parent_id,
                        child_name=actual_name,
                        dob_str=dob,
                        gender=gender,
                        relationship=state.get("patient_relationship") or "CHILD"
                    )
                    state["actual_patient_id"] = dep_patient_id
                    state["entities"]["appointment_for"] = state.get("appointment_for", "CHILD")
                    state["entities"]["patient_name_override"] = actual_name

                    # Now switch to BOOK_APPOINTMENT flow
                    state["dependent_collection_stage"] = None
                    state["intent"] = "BOOK_APPOINTMENT"
                    dept_id_now = state["entities"].get("department_id")
                    spec_label = "doctor"
                    if dept_id_now:
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute("SELECT department_name FROM departments WHERE id=%s;", (dept_id_now,))
                            dn = cur.fetchone()
                            if dn:
                                spec_label = entity_extractor.map_symptom_to_department_name(symptom_text)
                                sing, _ = get_specialist_titles(dn[0])
                                spec_label = sing
                        finally:
                            cur.close()
                            conn.close()

                    response_text = (
                        f"Got it! I'll book an appointment for *{actual_name}* (your {rel.lower()}).\n\n"
                        f"Condition/Reason: {symptom_text.capitalize()}\n\n"
                        f"What date and time would you prefer? \n"
                        f"(Example: tomorrow 10 AM, or Monday 3 PM)"
                    )
                    state["booking_stage"] = None
                else:
                    # Parent not registered — ask to register first
                    response_text = (
                        "To book an appointment for your family member, I need your own patient profile first.\n\n"
                        "Are you registered with us?"
                    )
                    state["interactive_buttons"] = [
                        {"id": "btn_first_time", "title": "Register Now"},
                        {"id": "btn_existing", "title": "Existing Patient"}
                    ]

    elif intent == "THANK_YOU":
        state["interactive_buttons"] = [
            {"id": "btn_book_appt", "title": "Book Appointment"},
            {"id": "btn_hosp_info", "title": "Hospital Information"}
        ]
        response_text = (
            "You're very welcome! 😊\n\n"
            "Is there anything else I can help you with today?"
        )
        state["intent"] = "GREETING"

    elif intent == "GOODBYE":
        state["interactive_buttons"] = []
        response_text = (
            "Thank you for visiting Meridian Hospital! 🙏\n\n"
            "Have a healthy and wonderful day! 😊\n\n"
            "Feel free to message us anytime."
        )
        state["intent"] = "GREETING"

    elif intent == "APPOINTMENT_CONFIRMATION":
        # Treat as BOOK_APPOINTMENT confirmation
        state["intent"] = "BOOK_APPOINTMENT"
        # Re-route as confirmation
        if state.get("confirmation_pending"):
            return process_agent_message(conversation_code, patient_code, "confirm", language_override)
        else:
            response_text = "I don't have a pending appointment to confirm. Would you like to book one?"
            state["interactive_buttons"] = [{"id": "btn_book_appt", "title": "Book Appointment"}]

    elif intent == "SYMPTOM_GUIDANCE":
        # Use the canonical map_symptom_to_department_name for consistent routing
        resolved_dept = entity_extractor.map_symptom_to_department_name(message_text)

        conn = db_config.get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM departments WHERE department_name ILIKE %s AND status = 'ACTIVE';", (resolved_dept,))
        row = cur.fetchone()
        dept_id = row[0] if row else None
        cur.close()
        conn.close()

        response_text = language_service.translate_response("SYMPTOM_GUIDANCE", current_lang, dept=resolved_dept)
        state["previous_question"] = "would_you_like_to_check_available_doctors"

        if dept_id:
            state["entities"]["department_id"] = dept_id
        if state["entities"]["reason"] is None:
            state["entities"]["reason"] = f"Symptoms: {message_text.strip()}"


    elif intent == "DOCTOR_AVAILABILITY":
        state["interactive_buttons"] = []
        dept_id = state["entities"].get("department_id")
        doc_id = state["entities"].get("doctor_id")
        appt_date = state["entities"].get("appointment_date")

        # Step 1: No department/doctor known yet — ask about symptom or department
        if not dept_id and not doc_id:
            state["previous_question"] = "avail_ask_dept_or_symptom"
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT department_name FROM departments WHERE status='ACTIVE' ORDER BY id;")
                dept_names = [r[0] for r in cur.fetchall()]
            finally:
                cur.close()
                conn.close()
            dept_list = "  ·  ".join(dept_names)
            response_text = (
                "Sure! To find the right doctor, please tell me:\n\n"
                "*Which department* are you looking for, or *what symptoms/condition* do you have?\n\n"
                f"🏥 Departments: {dept_list}"
            )
            missing_info.append("department_or_symptom")

        # Step 2: Department known, but no date yet — ask for the date
        elif not appt_date:
            # Resolve dept from doc if only doc is known
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

            dept_label = ""
            if dept_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT department_name FROM departments WHERE id = %s;", (dept_id,))
                    row = cur.fetchone()
                    dept_label = f" ({row[0]})"
                finally:
                    cur.close()
                    conn.close()

            state["previous_question"] = "avail_ask_date"
            response_text = (
                f"Got it{dept_label}! 📅 Which date would you like to check availability for?\n\n"
                "You can say *today*, *tomorrow*, a *weekday* (e.g. Monday), or a specific date (e.g. 05 Sep)."
            )
            missing_info.append("appointment_date")

        # Step 3: Both department and date known — show available slots per doctor
        else:
            tool_called = "get_doctor_availability"
            response_text = format_doctor_availability_response(dept_id, appt_date, conversation_code)
            state["previous_question"] = None

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
                booking_id_code = res["data"].get("booking_id", "APT000")
                log_agent_action(conversation_code, "APPOINTMENT_CONFIRMED", {"booking_id": booking_id_code, "doctor_id": doc_id, "date": appt_date, "time": appt_time})
                response_text = (
                    f"🎉 Appointment Confirmed!\n\n"
                    f"Booking ID: {booking_id_code}\n"
                    f"Doctor: {doc_details['name']}\n"
                    f"Department: {doc_details['department']}\n"
                    f"Date: {appt_date}\n"
                    f"Time: {appt_time}\n\n"
                    f"Please arrive 10–15 minutes before your appointment.\n\n"
                    f"Thank you for choosing Meridian Hospital. 🙏"
                )
                state["interactive_buttons"] = []
                # Clear state slots to allow clean future workflows
                state["entities"] = {
                    "patient_id": None,
                    "doctor_id": None,
                    "department_id": None,
                    "appointment_date": None,
                    "appointment_time": None,
                    "booking_id": None,
                    "reason": None
                }
                state["confirmation_pending"] = False
                state["intent"] = "POST_BOOKING"
            else:
                if res.get("error_code") == "APPOINTMENT_SLOT_UNAVAILABLE":
                    response_text = f"I'm sorry, {appt_time} is not available for {resolve_doctor_details(doc_id)['name']} on {appt_date}. Please select another time slot."
                else:
                    response_text = f"Booking failed: {res.get('error', 'Unknown error')}"

    elif intent == "CANCEL_APPOINTMENT":
        booking_id = state["entities"]["booking_id"]
        reason = state["entities"]["reason"]
        
        if not booking_id:
            # Look up active booking for this patient automatically
            if state.get("patient_id"):
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        SELECT booking_id, doctor_id, appointment_date, appointment_time
                        FROM appointments
                        WHERE patient_id = %s AND status IN ('CONFIRMED', 'PENDING', 'SCHEDULED')
                        ORDER BY appointment_date ASC LIMIT 1;
                    """, (state["patient_id"],))
                    b_row = cur.fetchone()
                    if b_row:
                        booking_id = b_row[0]
                        state["entities"]["booking_id"] = booking_id
                        doc_n = resolve_doctor_details(b_row[1])["name"]
                        response_text = (
                            f"I found your upcoming appointment:\n\n"
                            f"{booking_id}\n"
                            f"{doc_n}\n"
                            f"{b_row[2]} at {b_row[3]}\n\n"
                            f"Would you like to cancel this appointment?"
                        )
                        state["interactive_buttons"] = [
                            {"id": "btn_confirm_cancel", "title": "Cancel Appointment"},
                            {"id": "btn_keep_appt", "title": "Keep Appointment"}
                        ]
                        state_manager.save_conversation_state(conversation_code, state)
                        log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                        return {
                            "success": True,
                            "conversation_id": conversation_code,
                            "language": current_lang,
                            "intent": intent,
                            "response": response_text,
                            "missing_information": [],
                            "tool_called": None,
                            "interactive_buttons": state["interactive_buttons"]
                        }
                finally:
                    cur.close()
                    conn.close()

            response_text = "Please enter your Booking ID (e.g. APT86554) to cancel your appointment:"
            missing_info.append("booking_id")
        elif not reason and not any(w in message_text.lower() for w in ["confirm", "cancel appointment", "btn_confirm_cancel"]):
            response_text = f"Please provide the reason for cancelling appointment {booking_id}:"
            missing_info.append("reason")
        else:
            cancel_reason = reason or "Patient requested cancellation via WhatsApp"
            tool_called = "cancel_appointment"
            res = tool_registry.tool_cancel_appointment(
                conversation_code=conversation_code,
                booking_id=booking_id,
                reason=cancel_reason,
                user_id=None
            )
            if res["success"]:
                log_agent_action(conversation_code, "APPOINTMENT_CANCELLED", {"booking_id": booking_id, "reason": cancel_reason})
                response_text = f"Your appointment {booking_id} has been cancelled successfully.\n\nWould you like to book another appointment?"
                state["interactive_buttons"] = [
                    {"id": "btn_book_appt", "title": "Book Appointment"},
                    {"id": "btn_hosp_info", "title": "Hospital Information"}
                ]
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
                response_text = f"Cancellation failed: {res.get('error', 'Appointment not found')}"

    elif intent == "RESCHEDULE_APPOINTMENT":
        booking_id = state["entities"]["booking_id"]
        new_date = state["entities"]["appointment_date"]
        new_time = state["entities"]["appointment_time"]
        reason = state["entities"]["reason"] or "Rescheduled via WhatsApp"
        
        if not booking_id:
            # Auto-lookup active appointment
            if state.get("patient_id"):
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        SELECT booking_id FROM appointments
                        WHERE patient_id = %s AND status IN ('CONFIRMED', 'PENDING', 'SCHEDULED')
                        ORDER BY appointment_date ASC LIMIT 1;
                    """, (state["patient_id"],))
                    r = cur.fetchone()
                    if r:
                        booking_id = r[0]
                        state["entities"]["booking_id"] = booking_id
                finally:
                    cur.close()
                    conn.close()

        if not booking_id:
            response_text = "Please provide your Booking ID (e.g. APT86554) to reschedule:"
            missing_info.append("booking_id")
        elif not new_date:
            response_text = f"Please provide your preferred new date to reschedule appointment {booking_id} (e.g. next Monday, 2026-09-10):"
            missing_info.append("appointment_date")
        elif not new_time:
            # Query doctor slots for new date
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            doc_id = None
            try:
                cur.execute("SELECT doctor_id FROM appointments WHERE booking_id = %s;", (booking_id,))
                r = cur.fetchone()
                if r:
                    doc_id = r[0]
            finally:
                cur.close()
                conn.close()

            if doc_id:
                tool_called = "get_available_slots"
                res = tool_registry.tool_get_available_slots(conversation_code, doc_id, new_date)
                doc_name = resolve_doctor_details(doc_id)["name"]
                if res["success"] and res["slots"]:
                    formatted_slots = "\n• " + "\n• ".join(res["slots"])
                    response_text = f"Available slots for {doc_name} on {new_date}:\n{formatted_slots}\n\nPlease select your preferred time."
                else:
                    response_text = f"No available slots for {doc_name} on {new_date}. Please select another date."
            else:
                response_text = f"Please select your preferred time for {new_date} (e.g. 10:30 AM):"
            missing_info.append("appointment_time")
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
                log_agent_action(conversation_code, "APPOINTMENT_RESCHEDULED", {"booking_id": booking_id, "new_date": new_date, "new_time": new_time})
                response_text = f"Your appointment {booking_id} has been rescheduled successfully to {new_date} at {new_time}. 🎉"
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
                response_text = f"Rescheduling failed: {err_msg}. Please select another date or time."
                state["entities"]["appointment_time"] = None
                    
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
        log_agent_action(conversation_code, "PRE_ADMISSION_REQUESTED")
        found_db_rec = False
        if state.get("patient_id"):
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT admission_date, admission_type, status, pending_documents, submitted_documents, instructions, remarks
                    FROM pre_admissions WHERE patient_id = %s ORDER BY id DESC LIMIT 1;
                """, (state["patient_id"],))
                p_row = cur.fetchone()
                if p_row:
                    found_db_rec = True
                    adm_date, adm_type, status, pend_docs, sub_docs, inst, rmks = p_row
                    import datetime
                    if isinstance(adm_date, (datetime.date, datetime.datetime)):
                        adm_date_str = adm_date.strftime("%d-%b-%Y")
                    else:
                        adm_date_str = str(adm_date)

                    if isinstance(pend_docs, list):
                        pend_str = "• " + "\n• ".join(pend_docs)
                    elif pend_docs:
                        pend_str = f"• {pend_docs}"
                    else:
                        pend_str = "None"

                    response_text = (
                        f"📋 Your pre-admission details:\n\n"
                        f"📅 Admission Date: {adm_date_str}\n"
                        f"🏥 Admission Type: {adm_type or 'General'}\n"
                        f"📋 Status: {status or 'Pending'}\n\n"
                        f"Pending documents:\n{pend_str}\n\n"
                        f"Instructions:\n{inst or 'No special preparation required.'}\n\n"
                        f"Remarks:\n{rmks or 'Your pre-admission record is currently awaiting physician clearance.'}"
                    )
            finally:
                cur.close()
                conn.close()

        if not found_db_rec:
            # Fallback to RAG knowledge retrieval for admission document questions
            tool_called = "search_knowledge"
            msg_l = message_text.lower()
            try:
                cat_hint = "ADMISSION_DOCUMENTS" if any(w in msg_l for w in ["document", "bring", "required", "need", "carry"]) else "PRE_ADMISSION"
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
        if any(w in msg_clean for w in ["no", "thanks", "thank you", "bye", "btn_no_thanks"]):
            response_text = "You're very welcome! 😊\n\nThank you for choosing Meridian Hospital.\n\nHave a great day! 🙏"
            state["intent"] = "GREETING"
        elif any(w in msg_clean for w in ["hospital", "btn_hosp_info"]):
            state["intent"] = "HOSPITAL_INFORMATION"
            return process_agent_message(conversation_code, patient_code, "Tell me about Meridian Hospital")
        elif any(w in msg_clean for w in ["book", "appointment", "btn_book_another"]):
            state["intent"] = "BOOK_APPOINTMENT"
            return process_agent_message(conversation_code, patient_code, "Book Appointment")
        elif any(w in msg_clean for w in ["yes", "sure", "options", "help", "info"]):
            response_text = (
                "✅ Your appointment has been completed successfully.\n\n"
                "Thank you for using Meridian Hospital AI Patient Desk. 🙏\n\n"
                "Is there anything else you'd like to know about Meridian Hospital?"
            )
            state["interactive_buttons"] = [
                {"id": "btn_hosp_info", "title": "Hospital Information"},
                {"id": "btn_doctors", "title": "Doctors & Departments"},
                {"id": "btn_book_another", "title": "Book Another Appointment"},
                {"id": "btn_no_thanks", "title": "No, Thank You"}
            ]
        else:
            response_text = (
                "✅ Your appointment has been completed successfully.\n\n"
                "Thank you for using Meridian Hospital AI Patient Desk. 🙏\n\n"
                "Is there anything else you'd like to know about Meridian Hospital?"
            )
            state["interactive_buttons"] = [
                {"id": "btn_hosp_info", "title": "Hospital Information"},
                {"id": "btn_doctors", "title": "Doctors & Departments"},
                {"id": "btn_book_another", "title": "Book Another Appointment"},
                {"id": "btn_no_thanks", "title": "No, Thank You"}
            ]

    else:
        # ── LLM-powered fallback for UNKNOWN / unmatched intents ────────────
        msg_l_feat = message_text.lower().strip()
        is_features_query = any(w in msg_l_feat for w in [
            "feature", "features", "available features", "what can you do",
            "what do you do", "capabilities", "help me", "how can you help",
            "what can i do", "options", "menu"
        ])

        if is_features_query:
            state["interactive_buttons"] = []
            response_text = (
                "Here's what I can help you with at Meridian Hospital:\n\n"
                "📅 *Book Appointment* — Schedule a consultation with any doctor\n"
                "👨‍⚕️ *Doctor Availability* — Check which doctors are on duty\n"
                "🏥 *Hospital Information* — Location, departments, facilities, timings\n"
                "❌ *Cancel Appointment* — Cancel an existing booking\n"
                "🔄 *Reschedule Appointment* — Change your appointment date/time\n"
                "📋 *Appointment Status* — Check your booking status\n"
                "🩺 *Pre-Admission Guidance* — Documents and steps for hospital admission\n"
                "🆕 *Register as New Patient* — Create your patient profile\n\n"
                "Just tell me what you need and I'll take care of it!"
            )
        elif llm_service.is_llm_active():
            # Load recent conversation history for context
            conv_history = []
            try:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT id FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                    conv_row = cur.fetchone()
                    if conv_row:
                        cur.execute("""
                            SELECT sender_type, message_text FROM messages
                            WHERE conversation_id = %s
                              AND message_type = 'TEXT'
                              AND sender_type IN ('PATIENT', 'AI_AGENT')
                            ORDER BY id DESC LIMIT 10;
                        """, (conv_row[0],))
                        rows = cur.fetchall()
                        conv_history = [{"sender": r[0], "text": r[1]} for r in reversed(rows)]
                finally:
                    cur.close()
                    conn.close()
            except Exception as hist_err:
                print(f"[LLM Fallback] Could not load history: {hist_err}")

            # Call LLM for intent classification + response
            print(f"[LLM Fallback] Calling LLM for: '{message_text[:80]}'")
            llm_result = llm_service.llm_classify_intent_and_respond(
                message_text=message_text,
                current_state=state,
                language=current_lang,
                conversation_history=conv_history
            )

            llm_intent = llm_result.get("intent", "UNKNOWN")
            llm_response = llm_result.get("response")
            llm_route = llm_result.get("route_to_handler", False)
            llm_dept = llm_result.get("detected_department")
            llm_doctor = llm_result.get("detected_doctor")
            llm_date = llm_result.get("detected_date")
            llm_time = llm_result.get("detected_time")

            ROUTABLE_INTENTS = {
                "BOOK_APPOINTMENT", "CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT",
                "DOCTOR_AVAILABILITY", "APPOINTMENT_STATUS", "REGISTER_PATIENT",
                "HOSPITAL_INFORMATION", "PRE_ADMISSION", "SYMPTOM_GUIDANCE",
                "GREETING", "HUMAN_ESCALATION"
            }

            if llm_intent in ROUTABLE_INTENTS:
                # Update state intent so next turn routes correctly
                state["intent"] = llm_intent
                intent = llm_intent

                # Inject any entities the LLM detected
                if llm_dept and not state["entities"].get("department_id"):
                    try:
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute(
                                "SELECT id FROM departments WHERE LOWER(department_name) = LOWER(%s) AND status='ACTIVE' LIMIT 1;",
                                (llm_dept,)
                            )
                            dept_row = cur.fetchone()
                            if dept_row:
                                state["entities"]["department_id"] = dept_row[0]
                        finally:
                            cur.close()
                            conn.close()
                    except Exception:
                        pass

                if llm_doctor and not state["entities"].get("doctor_id"):
                    try:
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            doc_search = llm_doctor.replace("Dr.", "").replace("Dr ", "").strip()
                            cur.execute(
                                "SELECT id FROM doctors WHERE LOWER(display_name) LIKE LOWER(%s) AND status='ACTIVE' LIMIT 1;",
                                (f"%{doc_search}%",)
                            )
                            doc_row = cur.fetchone()
                            if doc_row:
                                state["entities"]["doctor_id"] = doc_row[0]
                        finally:
                            cur.close()
                            conn.close()
                    except Exception:
                        pass

                if llm_date and not state["entities"].get("appointment_date"):
                    from agent import entity_extractor as _ee
                    parsed_date = _ee.parse_natural_date(llm_date.lower())
                    if parsed_date:
                        state["entities"]["appointment_date"] = parsed_date

                if llm_time and not state["entities"].get("appointment_time"):
                    from agent import entity_extractor as _ee
                    parsed_time = _ee.parse_natural_time(llm_time.lower())
                    if parsed_time:
                        state["entities"]["appointment_time"] = parsed_time

                # Use LLM response directly (it handles both routed and informational cases)
                response_text = llm_response or language_service.translate_response("UNKNOWN", current_lang)
            else:
                response_text = llm_response or language_service.translate_response("UNKNOWN", current_lang)
        else:
            # LLM not configured — static fallback
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
