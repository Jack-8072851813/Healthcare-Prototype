import sys
import os
import datetime
import random
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
import agent.intent_router as intent_router
import agent.llm_intent_router as llm_intent_router
import agent.patient_identification_service as patient_id_service
import agent.response_validator as response_validator
import agent.grounding_validator as grounding_validator
import agent.conversation_stages as conversation_stages
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

def format_safe_dob(pat_dob_raw) -> str:
    """Formats a DOB string safely. Returns 'Not provided' if raw value is not a valid date."""
    if not pat_dob_raw or str(pat_dob_raw).strip() in ["-", "None", "null", "Not provided"]:
        return "Not provided"
    try:
        is_v, norm_d, _ = date_normalizer.validate_dob(str(pat_dob_raw).strip(), allow_ambiguous=True)
        if is_v and norm_d:
            d_obj = datetime.datetime.strptime(norm_d, "%Y-%m-%d").date()
            return d_obj.strftime("%d-%b-%Y")
    except Exception:
        pass
    return "Not provided"

def format_safe_gender(gender_raw) -> str:
    """Formats gender safely. Returns '-' if missing or invalid."""
    if not gender_raw or str(gender_raw).strip() in ["-", "None", "null"]:
        return "-"
    g = str(gender_raw).strip().capitalize()
    if g in ["Male", "Female", "Other"]:
        return g
    return "-"

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
    return mapping.get(d_name, (f"{d_name} Specialist" if d_name else "Specialist", f"{d_name} Specialists" if d_name else "Specialists"))

def sync_selected_doctor_state(state: dict, doctor_id: int):
    """
    Ensures selected_doctor_id, selected_doctor_name, selected_department_id, and
    selected_department_name are synchronized with DB ground truth in conversation state.
    """
    if not doctor_id:
        return
    try:
        doc_info = resolve_doctor_details(int(doctor_id))
        if doc_info and doc_info.get("name"):
            state["selected_doctor_id"] = int(doctor_id)
            state["selected_doctor_name"] = doc_info["name"]
            dept_id = doc_info.get("department_id")
            if dept_id:
                state["selected_department_id"] = dept_id
                state.setdefault("entities", {})["department_id"] = dept_id
            state["selected_department_name"] = doc_info.get("department")
            state.setdefault("entities", {})["doctor_id"] = int(doctor_id)
    except Exception as e:
        print(f"[SYNC_DOCTOR_STATE_ERR] Failed to sync doctor state for id={doctor_id}: {e}")

def restore_selected_doctor_state(state: dict):
    """
    Restores doctor_id and department_id into state["entities"] if selected_doctor_id exists.
    """
    sel_doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id")
    if sel_doc_id:
        sync_selected_doctor_state(state, sel_doc_id)

def validate_and_enforce_selected_doctor(conversation_code: str, state: dict, response_payload: dict) -> dict:
    """
    Stale context / mismatch protection guard:
    Ensures that if selected_doctor_id is active in state, response_payload does NOT reference
    a different doctor (context leakage). If a mismatch is detected, rebuilds the response
    specifically for the active selected doctor.
    """
    if not isinstance(response_payload, dict) or not response_payload.get("response"):
        return response_payload

    sel_doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id")
    if not sel_doc_id:
        return response_payload

    try:
        doc_info = resolve_doctor_details(int(sel_doc_id))
        if not doc_info or not doc_info.get("name"):
            return response_payload
            
        resp_text = response_payload.get("response", "")
        
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        other_docs = []
        try:
            cur.execute("SELECT display_name FROM doctors WHERE id != %s AND status = 'ACTIVE';", (int(sel_doc_id),))
            other_docs = [r[0] for r in cur.fetchall()]
        finally:
            cur.close()
            conn.close()

        mismatch = False
        for other_name in other_docs:
            if other_name in resp_text and doc_info["name"] not in resp_text:
                mismatch = True
                print(f"[CONTEXT_GUARD_ALERT] Intercepted doctor mismatch! Response mentioned '{other_name}' instead of selected doctor '{doc_info['name']}'. Rebuilding response for selected doctor!")
                break

        if mismatch:
            current_lang = state.get("language", "ENGLISH")
            intent = state.get("intent", "DOCTOR_AVAILABILITY")
            appt_date = state.get("entities", {}).get("appointment_date")
            if appt_date:
                res_slots = tool_registry.tool_get_available_slots(conversation_code, int(sel_doc_id), appt_date)
                slots_list = res_slots.get("slots", []) if res_slots.get("success") else []
                if slots_list:
                    return build_verified_slot_selection_response(conversation_code, state, int(sel_doc_id), doc_info, appt_date, slots_list, current_lang=current_lang, intent=intent)
                else:
                    return build_verified_date_selection_response(conversation_code, state, int(sel_doc_id), doc_info, failed_date=appt_date, current_lang=current_lang, intent=intent)
            else:
                return build_verified_date_selection_response(conversation_code, state, int(sel_doc_id), doc_info, current_lang=current_lang, intent=intent)
    except Exception as e:
        print(f"[VALIDATE_DOCTOR_ERR] Error in validate_and_enforce_selected_doctor: {e}")

    return response_payload


def get_verified_doctor_available_dates(conversation_code: str, doctor_id: int, start_offset: int = 0, max_days: int = 21, limit: int = 4) -> list:
    """
    Queries actual availability for a doctor over future dates.
    Returns ONLY dates that have at least 1 real available slot in DB.
    Each item: {"date": "YYYY-MM-DD", "title": "Fri, Sep 11", "slots": [...], "count": int}
    """
    import datetime
    import pytz
    ist = pytz.timezone("Asia/Kolkata")
    today = datetime.datetime.now(ist).date()
    valid_dates = []
    
    for offset in range(start_offset, max_days + 1):
        d_obj = today + datetime.timedelta(days=offset)
        d_str = d_obj.strftime("%Y-%m-%d")
        res = tool_registry.tool_get_available_slots(conversation_code, doctor_id, d_str)
        slots = res.get("slots", []) if res.get("success") else []
        if slots:
            valid_dates.append({
                "date": d_str,
                "title": d_obj.strftime("%a, %b %d"),
                "slots": slots,
                "count": len(slots)
            })
            if len(valid_dates) >= limit:
                break
    return valid_dates


def build_verified_slot_selection_response(conversation_code: str, state: dict, doc_id: int, doc_info: dict, target_date: str, slots_list: list, details_header: str = "", current_lang: str = "ENGLISH", intent: str = "BOOK_APPOINTMENT") -> dict:
    """
    Renders slot selection response for a validated target_date with non-empty slots_list.
    Presents an interactive time slot list so the patient explicitly selects their preferred time.
    """
    state["entities"]["appointment_date"] = target_date
    state["entities"]["appointment_time"] = None
    state["conversation_state"] = "TIME_SELECTION"
    state["confirmation_pending"] = False

    formatted_date_str = target_date
    if target_date:
        try:
            dt = datetime.datetime.strptime(target_date, "%Y-%m-%d")
            formatted_date_str = dt.strftime("%A, %B %d").replace(" 0", " ")
        except Exception:
            formatted_date_str = target_date

    doc_name = doc_info.get("name", "Doctor")
    dept_name = doc_info.get("department", "Cardiology")

    header_title = "📅 *Available time slots*"
    choose_prompt = "Please select an available time slot below:"
    list_title = "Choose a time ▼"

    lang = (current_lang or "ENGLISH").upper()
    if lang == "TAMIL":
        header_title = "📅 *கிடைக்கும் நேரங்கள்*"
        choose_prompt = "கீழே உள்ள நேரத்தில் ஒன்றை தேர்வு செய்யவும்:"
        list_title = "நேரத்தை தேர்வு செய்க ▼"
    elif lang == "HINDI":
        header_title = "📅 *उपलब्ध समय स्लॉट*"
        choose_prompt = "कृपया नीचे दिए गए समय में से चुनें:"
        list_title = "समय चुनें ▼"
    elif lang == "TELUGU":
        header_title = "📅 *అందుబాటులో ఉన్న సమయాలు*"
        choose_prompt = "దయచేసి క్రింది సమయాన్ని ఎంచుకోండి:"
        list_title = "సమయాన్ని ఎంచుకోండి ▼"
    elif lang == "MALAYALAM":
        header_title = "📅 *ലഭ്യമായ സമയങ്ങൾ*"
        choose_prompt = "ദയവായി താഴെയുള്ള സമയം തിരഞ്ഞെടുക്കുക:"
        list_title = "സമയം തിരഞ്ഞെടുക്കുക ▼"
    elif lang == "KANNADA":
        header_title = "📅 *ಲಭ್ಯವಿರುವ ಸಮಯಗಳು*"
        choose_prompt = "ದಯವಿಟ್ಟು ಕೆಳಗಿನ ಸಮಯವನ್ನು ಆಯ್ಕೆಮಾಡಿ:"
        list_title = "ಸಮಯವನ್ನು ಆಯ್ಕೆಮಾಡಿ ▼"
    elif lang == "URDU":
        header_title = "📅 *دستیاب وقت*"
        choose_prompt = "براہ کرم نیچے دیے گئے وقت کا انتخاب کریں:"
        list_title = "وقت منتخب کریں ▼"

    header_prefix = f"{details_header}\n\n" if details_header else ""
    response_text = (
        f"{header_prefix}"
        f"{header_title}\n"
        f"*{doc_name}*\n"
        f"*{dept_name}*\n"
        f"*{formatted_date_str}*\n\n"
        f"{choose_prompt}"
    )
    slot_buttons = [{"id": f"btn_slot_{s}", "title": format_time_12h(s)} for s in slots_list]
    state["interactive_buttons"] = slot_buttons
    state["interactive_type"] = "list"
    state["list_button_title"] = list_title

    state_manager.save_conversation_state(conversation_code, state)
    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
    return {
        "response": response_text,
        "intent": intent,
        "language": current_lang,
        "interactive_buttons": slot_buttons,
        "interactive_type": "list",
        "list_button_title": list_title
    }


def build_verified_date_selection_response(conversation_code: str, state: dict, doc_id: int, doc_info: dict, failed_date: str = None, current_lang: str = "ENGLISH", intent: str = "BOOK_APPOINTMENT") -> dict:
    """
    Queries verified future dates for doc_id that have at least 1 available slot.
    Handles 0 dates, 1 date (auto-advances to slot selection), and >1 dates.
    """
    valid_dates = get_verified_doctor_available_dates(conversation_code, doc_id)

    details_parts = [f"👨‍⚕️ *{doc_info['name']}*", f"🏥 *Department*: {doc_info['department']}"]
    if doc_info.get("qualification"):
        details_parts.append(f"🎓 *Qualification*: {doc_info['qualification']}")
    if doc_info.get("experience_years"):
        details_parts.append(f"💼 *Experience*: {doc_info['experience_years']} years")
    if doc_info.get("consultation_fee"):
        fee_val = doc_info['consultation_fee']
        fee_str = f"₹{fee_val:.0f}" if (isinstance(fee_val, float) and fee_val.is_integer()) or isinstance(fee_val, int) else f"₹{fee_val}"
        details_parts.append(f"💵 *Consultation Fee*: {fee_str}")
    details_header = "\n".join(details_parts)

    fail_prefix = f"Sorry, *{doc_info['name']}* has no available slots on *{failed_date}*.\n\n" if failed_date else ""

    if not valid_dates:
        state["conversation_state"] = "DOCTOR_SELECTION_REQUIRED"
        state["entities"]["appointment_date"] = None
        state["entities"]["appointment_time"] = None
        resp = (
            f"{details_header}\n\n"
            f"{fail_prefix}"
            f"Sorry, *{doc_info['name']}* has no available slots in the upcoming schedule.\n\n"
            f"📅 Please choose another doctor or contact our hospital desk for assistance."
        )
        buttons = []
        state["interactive_buttons"] = buttons
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, intent, state)
        return {"response": resp, "intent": intent, "language": current_lang, "interactive_buttons": buttons}

    if len(valid_dates) == 1:
        # Single available date -> Auto-advance directly!
        target_date = valid_dates[0]["date"]
        slots_list = valid_dates[0]["slots"]
        return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, target_date, slots_list, details_header, current_lang, intent)

    # Multiple available dates -> Show verified date buttons with Choose Another Date
    state["conversation_state"] = "DATE_REQUIRED"
    state["entities"]["appointment_date"] = None
    state["entities"]["appointment_time"] = None
    date_buttons = [{"id": f"btn_date_{d['date']}", "title": d["title"][:20]} for d in valid_dates[:2]]
    date_buttons.append({"id": "btn_date_custom", "title": "Choose Another Date"})

    date_list_text = "\n• ".join([f"*{d['title']}* ({d['count']} slots available)" for d in valid_dates[:4]])
    resp = (
        f"{details_header}\n\n"
        f"{fail_prefix}"
        f"Which date would you like to book your appointment?\n\n"
        f"📅 *Available dates for {doc_info['name']}*:\n• {date_list_text}"
    )
    state["interactive_buttons"] = date_buttons
    state_manager.save_conversation_state(conversation_code, state)
    log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, intent, state)
    return {"response": resp, "intent": intent, "language": current_lang, "interactive_buttons": date_buttons}

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


def format_doctor_working_schedule_response(doc_id: int) -> str:
    """
    Returns a human-friendly response showing the doctor's configured weekly working schedule
    from doctor_schedules. Used when user asks for availability without a specific date,
    or after a failed slot lookup on a particular date (so we don't repeat the failed date).
    """
    doc_info = resolve_doctor_details(doc_id)
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT day_of_week, start_time, end_time
            FROM doctor_schedules
            WHERE doctor_id = %s AND status = 'ACTIVE'
            ORDER BY
                CASE day_of_week
                    WHEN 'Monday'    THEN 1
                    WHEN 'Tuesday'   THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday'  THEN 4
                    WHEN 'Friday'    THEN 5
                    WHEN 'Saturday'  THEN 6
                    WHEN 'Sunday'    THEN 7
                    ELSE 8
                END;
        """, (doc_id,))
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    if not rows:
        return (
            f"*{doc_info['name']}* ({doc_info['department']}) does not have any scheduled working days "
            f"configured at this time. Please contact the hospital directly for availability.\n\n"
            f"📞 Helpline: +91 98765 43210"
        )

    # Build schedule lines
    schedule_lines = []
    for day, start, end in rows:
        start_fmt = format_time_12h(str(start)[:5]) if start else ""
        end_fmt   = format_time_12h(str(end)[:5])   if end   else ""
        if start_fmt and end_fmt:
            schedule_lines.append(f"• *{day.capitalize()}*: {start_fmt} – {end_fmt}")
        else:
            schedule_lines.append(f"• *{day.capitalize()}*")

    schedule_text = "\n".join(schedule_lines)
    working_day_names = [r[0].capitalize() for r in rows]
    days_summary = ", ".join(working_day_names)

    return (
        f"👨‍⚕️ *{doc_info['name']}* — {doc_info['department']}\n\n"
        f"📅 *Weekly Availability:*\n{schedule_text}\n\n"
        f"*{doc_info['name']}* is available on {days_summary}.\n\n"
        f"Which date would you like to check for available time slots? "
        f"You can say a day like *Monday*, *tomorrow*, or a specific date."
    )

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

def log_message_to_db(conversation_code: str, sender_type: str, message_text: str, language: str, intent: str, metadata: dict = None, message_type: str = "TEXT"):
    """Inserts a conversation message into the messages table in a single query."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
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

        db_msg_type = (metadata or {}).get("message_type") or message_type or 'TEXT'
        if db_msg_type not in ['TEXT', 'VOICE', 'SYSTEM']:
            db_msg_type = 'TEXT'

        import json
        cur.execute("""
            INSERT INTO messages (conversation_id, sender_type, message_type, message_text, language, intent, metadata)
            SELECT id, %s, %s, %s, %s, %s, %s::jsonb
            FROM conversations
            WHERE conversation_code = %s;
        """, (db_sender, db_msg_type, message_text, db_lang, intent, json.dumps(metadata, default=str) if metadata else None, conversation_code))
        conn.commit()
    except Exception as e:
        print("Failed to log message to DB:", str(e))
    finally:
        cur.close()
        conn.close()

def log_agent_action(conversation_code: str, action_type: str, details: dict = None):
    """Inserts an audit entry into agent_action_logs table in a single query."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        import json
        valid_actions = ('SEARCH_HOSPITAL_KNOWLEDGE', 'GET_DOCTOR_AVAILABILITY', 'GET_AVAILABLE_SLOTS', 'BOOK_APPOINTMENT', 'GET_APPOINTMENT_STATUS', 'CANCEL_APPOINTMENT', 'RESCHEDULE_APPOINTMENT', 'GET_PATIENT', 'GET_PRE_ADMISSION_STATUS', 'CREATE_ESCALATION')
        action_name = action_type if action_type in valid_actions else 'BOOK_APPOINTMENT'
        cur.execute("""
            INSERT INTO agent_action_logs (conversation_id, patient_id, action_name, intent, status, output_data)
            SELECT id, patient_id, %s, 'BOOK_APPOINTMENT', 'SUCCESS', %s
            FROM conversations
            WHERE conversation_code = %s;
        """, (action_name, json.dumps(details, default=str) if details else None, conversation_code))
        conn.commit()
    except Exception as e:
        pass
    finally:
        cur.close()
        conn.close()

def format_single_appointment_card(appt_data: dict) -> str:
    """Formats a rich WhatsApp card for an appointment."""
    b_id = appt_data.get("booking_id") or "N/A"
    p_name = appt_data.get("patient_name") or "Patient"
    doc_name = appt_data.get("doctor_name") or "Doctor"
    dept_name = appt_data.get("department_name") or appt_data.get("department") or "General"
    
    appt_date_raw = str(appt_data.get("appointment_date"))
    try:
        dt_obj = datetime.datetime.strptime(appt_date_raw, "%Y-%m-%d").date()
        formatted_date = dt_obj.strftime("%A, %d-%b-%Y")
    except Exception:
        formatted_date = appt_date_raw

    raw_time = str(appt_data.get("appointment_time") or "")
    formatted_time = format_time_12h(raw_time) if raw_time else "Scheduled"

    reason = appt_data.get("patient_reason") or appt_data.get("reason") or "General Consultation"
    status = str(appt_data.get("status") or "CONFIRMED").upper()
    status_icon = "✅" if status in ["CONFIRMED", "ACTIVE", "COMPLETED"] else ("❌" if status == "CANCELLED" else "🟡")

    fee_str = ""
    fee = appt_data.get("consultation_fee")
    if fee is not None:
        try:
            fee_float = float(fee)
            fee_str = f"\n💵 *Consultation Fee*: ₹{fee_float:.0f}" if fee_float.is_integer() else f"\n💵 *Consultation Fee*: ₹{fee_float:.2f}"
        except Exception:
            pass

    return (
        f"📋 *Appointment Details*\n\n"
        f"🆔 *Booking ID*: {b_id}\n"
        f"👤 *Patient Name*: {p_name}\n"
        f"👨‍⚕️ *Doctor*: {doc_name}\n"
        f"🏥 *Department*: {dept_name}\n"
        f"📅 *Date*: {formatted_date}\n"
        f"⏰ *Time*: {formatted_time}\n"
        f"📝 *Reason for Visit*: {reason}\n"
        f"📌 *Status*: {status_icon} {status}"
        f"{fee_str}"
    )


def fetch_appointment_details_by_booking_id(booking_id: str) -> dict:
    """Queries DB for appointment details by booking ID (case-insensitive)."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                a.booking_id, a.appointment_date, a.appointment_time, a.status, a.patient_reason,
                p.first_name || ' ' || p.last_name AS patient_name,
                d.display_name AS doctor_name,
                dept.department_name,
                d.consultation_fee
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN departments dept ON a.department_id = dept.id
            WHERE LOWER(a.booking_id) = LOWER(%s);
        """, (booking_id.strip(),))
        row = cur.fetchone()
        if row:
            return {
                "booking_id": row[0],
                "appointment_date": row[1],
                "appointment_time": row[2],
                "status": row[3],
                "patient_reason": row[4],
                "patient_name": row[5].strip(),
                "doctor_name": row[6].replace("Dr. Dr.", "Dr.").strip(),
                "department_name": row[7],
                "consultation_fee": row[8]
            }
        return None
    finally:
        cur.close()
        conn.close()


def fetch_patient_appointments(patient_id: int = None, whatsapp_number: str = None, time_filter: str = "ALL") -> list:
    """Queries DB for appointments for a specific patient_id or whatsapp_number."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        base_query = """
            SELECT 
                a.booking_id, a.appointment_date, a.appointment_time, a.status, a.patient_reason,
                p.first_name || ' ' || p.last_name AS patient_name,
                d.display_name AS doctor_name,
                dept.department_name,
                d.consultation_fee,
                p.patient_code
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN departments dept ON a.department_id = dept.id
        """
        params = []
        if patient_id and int(patient_id) > 0:
            base_query += " WHERE a.patient_id = %s"
            params.append(patient_id)
        elif whatsapp_number:
            base_query += " WHERE (p.whatsapp_number = %s OR p.phone = %s OR p.guardian_phone = %s)"
            params.extend([whatsapp_number, whatsapp_number, whatsapp_number])
        else:
            return []

        tf_norm = (time_filter or "ALL").upper()
        if tf_norm == "UPCOMING":
            base_query += " AND a.appointment_date >= CURRENT_DATE ORDER BY a.appointment_date ASC, a.appointment_time ASC;"
        elif tf_norm == "PAST":
            base_query += " AND a.appointment_date < CURRENT_DATE ORDER BY a.appointment_date DESC, a.appointment_time DESC;"
        elif tf_norm == "NEXT":
            base_query += " AND a.appointment_date >= CURRENT_DATE ORDER BY a.appointment_date ASC, a.appointment_time ASC LIMIT 1;"
        else:
            base_query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC LIMIT 10;"

        cur.execute(base_query, tuple(params))
        rows = cur.fetchall()
        appts = []
        for r in rows:
            raw_time = r[2]
            formatted_time = raw_time.strftime("%H:%M") if hasattr(raw_time, "strftime") else str(raw_time)
            appts.append({
                "booking_id": r[0],
                "appointment_date": str(r[1]),
                "appointment_time": formatted_time,
                "status": r[3],
                "patient_reason": r[4] or "General Consultation",
                "patient_name": (r[5] or "").strip(),
                "doctor_name": (r[6] or "").replace("Dr. Dr.", "Dr.").strip(),
                "department_name": r[7],
                "consultation_fee": r[8],
                "patient_code": r[9]
            })
        return appts
    finally:
        cur.close()
        conn.close()


_DOCTOR_CACHE = {}

def resolve_doctor_details(doctor_id: int) -> dict:
    """Helper to query doctor name, department, and profile details from the database (cached in memory)."""
    if doctor_id in _DOCTOR_CACHE:
        return _DOCTOR_CACHE[doctor_id]

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT d.display_name, dept.department_name, d.specialization, d.qualification, d.experience_years, d.consultation_fee, d.department_id
            FROM doctors d
            JOIN departments dept ON d.department_id = dept.id
            WHERE d.id = %s;
        """, (doctor_id,))
        row = cur.fetchone()
        if row:
            doc_name = row[0].replace("Dr. Dr.", "Dr.").strip() if row[0] else "Doctor"
            res = {
                "name": doc_name,
                "department": row[1],
                "specialization": row[2] or row[1],
                "qualification": row[3] or "",
                "experience_years": row[4] if row[4] is not None else 0,
                "consultation_fee": float(row[5]) if row[5] is not None else 0.0,
                "department_id": row[6]
            }
            _DOCTOR_CACHE[doctor_id] = res
            return res
        res = {"name": "Doctor", "department": "General Medicine", "specialization": "General Medicine", "qualification": "", "experience_years": 0, "consultation_fee": 0.0, "department_id": None}
        return res
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


def process_agent_message(conversation_code: str, patient_code: str, message_text: str, language_override: str = None, interactive_id: str = None) -> dict:
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

    # Structured interactive button tap handler (Fix 3)
    btn_id = interactive_id or (message_text.strip() if message_text and message_text.strip().startswith("btn_") else None)
    if not btn_id and message_text:
        m_strip = message_text.strip().lower()
        if m_strip in ["hospital information", "hospital info"]:
            btn_id = "btn_hosp_info"
        elif m_strip in ["doctor availability", "doctor information", "doctor info"]:
            btn_id = "btn_doctor_avail"
        elif m_strip in ["other services", "other hospital services"]:
            btn_id = "btn_other_services"
        elif m_strip in ["my appointments", "my appts", "my appointment", "appointment details", "check appointment", "view appointment", "show my appointment", "my appointment details", "upcoming appointments"]:
            btn_id = "btn_my_appts"
        elif m_strip in ["my reports", "my report", "show my reports", "show reports", "reports", "medical reports", "get reports", "view reports"]:
            btn_id = "btn_my_reports"
        elif m_strip in ["gpay", "google pay"]:
            btn_id = "btn_pay_gpay"
        elif m_strip in ["phonepe"]:
            btn_id = "btn_pay_phonepe"
        elif m_strip in ["paytm"]:
            btn_id = "btn_pay_paytm"
        elif m_strip in ["upi"]:
            btn_id = "btn_pay_upi"
        elif m_strip in ["netbanking", "net banking"]:
            btn_id = "btn_pay_netbanking"
        elif m_strip in ["change payment method", "change payment"]:
            btn_id = "btn_pay_change"
        elif m_strip in ["cancel payment"]:
            btn_id = "btn_pay_cancel"
        elif m_strip.startswith("pay ₹") or m_strip == "pay":
            btn_id = "btn_pay_exec"
        elif m_strip in ["book appointment"]:
            btn_id = "btn_book_appt"
        elif m_strip in ["confirm appointment", "confirm"]:
            btn_id = "btn_confirm_appt"
        elif m_strip in ["cancel appointment"]:
            btn_id = "btn_cancel_appt"
        elif m_strip in ["confirm admission", "confirm pre-admission", "confirm preadmission"]:
            btn_id = "btn_confirm_admission"
        elif m_strip in ["cancel admission", "cancel pre-admission", "cancel preadmission"]:
            btn_id = "btn_cancel_admission"
        elif m_strip in ["need assistance", "admission assistance", "admission help"]:
            btn_id = "btn_admission_help"
        # Dynamic doctor / dependent / slot / date / payment / report / appt buttons
        elif m_strip in ["male", "btn_g_male"]:
            btn_id = "btn_g_male"
        elif m_strip in ["female", "btn_g_female"]:
            btn_id = "btn_g_female"
        elif m_strip in ["other", "btn_g_other"]:
            btn_id = "btn_g_other"
        elif m_strip in ["today", "btn_date_today"]:
            btn_id = "btn_date_today"
        elif m_strip in ["tomorrow", "btn_date_tomorrow"]:
            btn_id = "btn_date_tomorrow"
        elif m_strip.startswith("btn_date_") or m_strip.startswith("btn_doc_") \
                or m_strip.startswith("btn_dep_") or m_strip.startswith("btn_slot_") \
                or m_strip.startswith("btn_pay_") or m_strip.startswith("btn_report_") \
                or m_strip.startswith("btn_appt_") or m_strip.startswith("btn_cancel_existing_") \
                or m_strip.startswith("btn_reschedule_existing_") or m_strip.startswith("btn_exec_cancel_") \
                or m_strip.startswith("btn_confirm_") or m_strip.startswith("btn_change_") or m_strip.startswith("btn_cancel_"):
            # Pass structured IDs through unchanged
            btn_id = m_strip
        # Change-details field picker buttons
        elif m_strip in ["change patient name", "btn_chg_name"]:
            btn_id = "btn_chg_name"
        elif m_strip in ["change date", "btn_chg_date"]:
            btn_id = "btn_chg_date"
        elif m_strip in ["change time", "btn_chg_time"]:
            btn_id = "btn_chg_time"
        elif m_strip in ["change doctor", "btn_chg_doctor"]:
            btn_id = "btn_chg_doctor"
        elif m_strip in ["change reason", "btn_chg_reason"]:
            btn_id = "btn_chg_reason"

        # Check against translated menu button titles for all 7 languages
        if not btn_id:
            for lang_code, btn_dict in language_service.MENU_BUTTON_TRANSLATIONS.items():
                for k, v in btn_dict.items():
                    if m_strip == v.lower() or m_strip == k.lower():
                        btn_id = k
                        break
                if btn_id:
                    break

    if language_override:
        current_lang = language_override.upper()
    elif message_text and not message_text.startswith("btn_"):
        detected_lang = language_service.detect_language(message_text, current_lang=state.get("language", "ENGLISH"))
        current_lang = detected_lang or state.get("language", "ENGLISH")
    else:
        current_lang = state.get("language", "ENGLISH")
    state["language"] = current_lang

    if btn_id:
        print(f"[BUTTON_ROUTING] Handling structured button tap: {btn_id}")
        if btn_id in ("btn_cat_appts", "btn_cat_appointments"):
            resp = "📅 *Appointments*\n\nHow can I help you with your appointments?"
            if current_lang == "TAMIL":
                resp = "📅 *அப்பாயிண்ட்மெண்ட்கள்*\n\nஉங்கள் அப்பாயிண்ட்மெண்ட்கள் குறித்து நான் எவ்வாறு உதவ வேண்டும்?"
            elif current_lang == "HINDI":
                resp = "📅 *अपॉइंटमेंट*\n\nमैं आपकी अपॉइंटमेंट में कैसे मदद कर सकता हूं?"
            elif current_lang == "TELUGU":
                resp = "📅 *అపాయింట్‌మెంట్‌లు*\n\nమీ అపాయింట్‌మెంట్‌ల విషయంలో ఎలా సహాయపడాలి?"
            elif current_lang == "MALAYALAM":
                resp = "📅 *അപ്പോയിന്റ്മെന്റുകൾ*\n\nഅപ്പോയിന്റ്മെന്റുകളിൽ എങ്ങനെ സഹായിക്കണം?"
            elif current_lang == "KANNADA":
                resp = "📅 *ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್*\n\nನಿಮ್ಮ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್‌ನಲ್ಲಿ ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?"
            elif current_lang == "URDU":
                resp = "📅 *اپائنٹمنٹس*\n\nمیں آپ کی اپائنٹمنٹ میں کیسے مدد کر سکتا ہوں؟"

            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_book_appt", current_lang),
                language_service.get_translated_button("btn_my_appts", current_lang),
                language_service.get_translated_button("btn_reschedule_appt", current_lang),
                language_service.get_translated_button("btn_cancel_appt", current_lang),
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "APPOINTMENT_MENU"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "APPOINTMENT_MENU", state)
            return {
                "response": resp,
                "intent": "APPOINTMENT_MENU",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_cat_doctors":
            resp = "👨‍⚕️ *Doctors & Services*\n\nWhat would you like to explore?"
            if current_lang == "TAMIL":
                resp = "👨‍⚕️ *மருத்துவர்கள் & சேவைகள்*\n\nஎதைத் தேட விரும்புகிறீர்கள்?"
            elif current_lang == "HINDI":
                resp = "👨‍⚕️ *डॉक्टर और सेवाएं*\n\nआप क्या खोजना चाहते हैं?"
            elif current_lang == "TELUGU":
                resp = "👨‍⚕️ *వైద్యులు & సేవలు*\n\nమీరు దేనిని వెతకాలనుకుంటున్నారు?"
            elif current_lang == "MALAYALAM":
                resp = "👨‍⚕️ *ഡോക്ടറും സേവനവും*\n\nഎന്താണ് അറിയേണ്ടത്?"
            elif current_lang == "KANNADA":
                resp = "👨‍⚕️ *ವೈದ್ಯರು & ಸೇವೆಗಳು*\n\nನೀವು ಏನನ್ನು ಹುಡುಕಲು ಬಯಸುತ್ತೀರಿ?"
            elif current_lang == "URDU":
                resp = "👨‍⚕️ *ڈاکٹرز اور خدمات*\n\nآپ کیا تلاش کرنا چاہتے ہیں؟"

            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_find_doctor", current_lang),
                language_service.get_translated_button("btn_departments", current_lang),
                {"id": "btn_other_services", "title": "Hospital Services"},
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "DOCTORS_AND_SERVICES"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "DOCTORS_AND_SERVICES", state)
            return {
                "response": resp,
                "intent": "DOCTORS_AND_SERVICES",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id in ("btn_cat_inquiries", "btn_patient_help"):
            resp = "💬 *Patient Help & Inquiries*\n\nWelcome to Meridian Hospital Administrative Help & Inquiries. How can we assist you today?"
            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_hosp_info", current_lang),
                {"id": "btn_visiting_hours", "title": "Visiting Hours"},
                {"id": "btn_preadmission_info", "title": "Pre-Admission Info"},
                language_service.get_translated_button("btn_cat_staff", current_lang),
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "HOSPITAL_INFORMATION"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "HOSPITAL_INFORMATION", state)
            return {
                "response": resp,
                "intent": "HOSPITAL_INFORMATION",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_cat_health":
            resp = "📋 *My Health & Records*\n\nWhat would you like to access?"
            if current_lang == "TAMIL":
                resp = "📋 *என் சுகாதாரம் & பதிவுகள்*\n\nஎதைப் பார்க்க விரும்புகிறீர்கள்?"
            elif current_lang == "HINDI":
                resp = "📋 *स्वास्थ्य व रिकॉर्ड*\n\nआप क्या देखना चाहते हैं?"

            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_my_reports", current_lang),
                language_service.get_translated_button("btn_my_appts", current_lang),
                {"id": "btn_my_documents", "title": "Documents"},
                {"id": "btn_preadmission", "title": "Pre-Admission"},
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "MY_HEALTH_AND_RECORDS"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "MY_HEALTH_AND_RECORDS", state)
            return {
                "response": resp,
                "intent": "MY_HEALTH_AND_RECORDS",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_cat_billing":
            resp = (
                "💳 *Billing & Payments*\n\n"
                "Outstanding Balance: ₹4,850\n"
                "Account Status: Active\n\n"
                "Select an option below to view or manage billing:"
            )
            state["interactive_buttons"] = [
                {"id": "btn_view_bill", "title": "View Bill"},
                {"id": "btn_payment_history", "title": "Payment History"},
                {"id": "btn_insurance", "title": "Insurance"},
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "BILLING_AND_PAYMENTS"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BILLING_AND_PAYMENTS", state)
            return {
                "response": resp,
                "intent": "BILLING_AND_PAYMENTS",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_cat_voice_lang":
            resp = "🎤 *Voice & Language*\n\nSelect an option below to talk to AI or change your preferred language:"
            state["interactive_buttons"] = [
                {"id": "btn_talk_ai", "title": "🎤 Talk to AI"},
                {"id": "btn_change_language", "title": "🌐 Change Language"},
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "VOICE_AND_LANGUAGE"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "VOICE_AND_LANGUAGE", state)
            return {
                "response": resp,
                "intent": "VOICE_AND_LANGUAGE",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_cat_staff":
            resp = "🧑‍💼 *Hospital Staff Support*\n\nHow can our hospital support team help you today?"
            state["interactive_buttons"] = [
                {"id": "btn_staff_appt", "title": "Appointment Support"},
                {"id": "btn_staff_billing", "title": "Billing Support"},
                {"id": "btn_staff_reg", "title": "Registration Support"},
                {"id": "btn_staff_general", "title": "General Support"},
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "TALK_TO_STAFF_PROMPT"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "TALK_TO_STAFF_PROMPT", state)
            return {
                "response": resp,
                "intent": "TALK_TO_STAFF_PROMPT",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id in ("btn_cat_emergency", "btn_emergency"):
            resp = (
                "🚨 *Emergency Assistance*\n\n"
                "If this is an emergency, please seek immediate medical care.\n\n"
                "🚨 *Emergency Helpline:* 044 6666 9999\n"
                "📞 *General Enquiries:* 044 6666 9910\n"
                "📍 *Address:* #46D, Jawaharlal Nehru Road, 200 Feet Ring Road, Chennai – 600 099\n\n"
                "⚠️ *Important Safety Notice:*\n"
                "If this is a medical emergency, contact local emergency services (108 / 112) or go to the nearest Emergency Department."
            )
            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_talk_staff_exec", current_lang),
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "EMERGENCY"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "EMERGENCY", state)
            return {
                "response": resp,
                "intent": "EMERGENCY",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id in ("btn_staff_appt", "btn_staff_billing", "btn_staff_reg", "btn_staff_general"):
            resp = language_service.get_talk_to_staff_contact_response(current_lang)
            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "HUMAN_ESCALATION"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "HUMAN_ESCALATION", state)
            return {
                "response": resp,
                "intent": "HUMAN_ESCALATION",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_view_bill":
            resp = (
                "💳 *Itemized Hospital Bill*\n\n"
                "Patient: Gil Christ (P9989)\n"
                "Bill Reference: INV-2026-8841\n"
                "Bill Date: 10-Sep-2026\n\n"
                "• OPD Consultation Fee: ₹800\n"
                "• Diagnostic Lab Tests: ₹2,450\n"
                "• Pharmacy Charges: ₹1,600\n"
                "----------------------------------------\n"
                "Total Amount Due: ₹4,850\n\n"
                "Select a payment method below to clear outstanding balance:"
            )
            state["interactive_buttons"] = [
                {"id": "btn_pay_gpay", "title": "Google Pay"},
                {"id": "btn_pay_upi", "title": "UPI / PhonePe"},
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "BILLING_AND_PAYMENTS"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BILLING_AND_PAYMENTS", state)
            return {"response": resp, "intent": "BILLING_AND_PAYMENTS", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id == "btn_payment_history":
            resp = (
                "📜 *Payment & Billing History*\n\n"
                "1. TXN9981 — ₹800 (OPD Consultation - Dermatology) — Paid on 02-Sep-2026\n"
                "2. TXN9102 — ₹1,200 (Lab Test - CBC & Lipid) — Paid on 15-Aug-2026\n\n"
                "All receipts have been issued to your registered account."
            )
            state["interactive_buttons"] = [language_service.get_translated_button("btn_main_menu", current_lang)]
            state["intent"] = "BILLING_AND_PAYMENTS"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BILLING_AND_PAYMENTS", state)
            return {"response": resp, "intent": "BILLING_AND_PAYMENTS", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id == "btn_insurance":
            resp = (
                "🛡️ *Insurance & Cashless Desk*\n\n"
                "Meridian Hospital partners with major TPA and Health Insurance Providers (Star Health, ICICI Lombard, HDFC ERGO, Max Bupa, Care Health).\n\n"
                "📞 *Insurance Desk Helpline:* 044 6666 9910\n"
                "📍 *Location:* Ground Floor, Main Block Counter 4\n"
                "📧 *TPA Email:* insurance@meridian-hospital.com"
            )
            state["interactive_buttons"] = [language_service.get_translated_button("btn_cat_staff", current_lang), language_service.get_translated_button("btn_main_menu", current_lang)]
            state["intent"] = "HOSPITAL_INFORMATION"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "HOSPITAL_INFORMATION", state)
            return {"response": resp, "intent": "HOSPITAL_INFORMATION", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id == "btn_my_documents":
            resp = (
                "📑 *My Documents*\n\n"
                "1. Discharge Summary (2026-06-10)\n"
                "2. Doctor Prescription (2026-09-02)\n"
                "3. Vaccination Certificate\n\n"
                "All documents are securely archived in your digital health folder."
            )
            state["interactive_buttons"] = [language_service.get_translated_button("btn_my_reports", current_lang), language_service.get_translated_button("btn_main_menu", current_lang)]
            state["intent"] = "MY_HEALTH_AND_RECORDS"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "MY_HEALTH_AND_RECORDS", state)
            return {"response": resp, "intent": "MY_HEALTH_AND_RECORDS", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id == "btn_preadmission":
            resp = (
                "📋 *Pre-Admission Status*\n\n"
                "Status: No active pre-admission form required.\n\n"
                "If you are scheduled for elective surgery or inpatient admission, please bring your ID proof, doctor referral note, and insurance card."
            )
            state["interactive_buttons"] = [language_service.get_translated_button("btn_main_menu", current_lang)]
            state["intent"] = "MY_HEALTH_AND_RECORDS"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "MY_HEALTH_AND_RECORDS", state)
            return {"response": resp, "intent": "MY_HEALTH_AND_RECORDS", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id == "btn_visiting_hours":
            resp = (
                "🕒 *Visiting Hours & Guidelines*\n\n"
                "• OPD Consultations: 08:00 AM - 08:00 PM (Mon - Sat)\n"
                "• In-Patient Ward: 04:00 PM - 07:00 PM Daily\n"
                "• ICU Visiting Hours: 05:00 PM - 06:00 PM (1 Visitor at a time)\n"
                "• 24/7 Emergency & Casualty Service"
            )
            state["interactive_buttons"] = [language_service.get_translated_button("btn_cat_staff", current_lang), language_service.get_translated_button("btn_main_menu", current_lang)]
            state["intent"] = "HOSPITAL_INFORMATION"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "HOSPITAL_INFORMATION", state)
            return {"response": resp, "intent": "HOSPITAL_INFORMATION", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id == "btn_other_services":
            resp = (
                "🩺 *Meridian Hospital Services*\n\n"
                "• 24/7 Multi-Specialty OPD & Inpatient Care\n"
                "• Advanced Diagnostic Lab & 3T MRI Radiology\n"
                "• Emergency, Ambulance & Level-1 Trauma Care\n"
                "• 24/7 Pharmacy & Blood Bank Facilities"
            )
            state["interactive_buttons"] = [language_service.get_translated_button("btn_book_appt", current_lang), language_service.get_translated_button("btn_main_menu", current_lang)]
            state["intent"] = "DOCTORS_AND_SERVICES"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "DOCTORS_AND_SERVICES", state)
            return {"response": resp, "intent": "DOCTORS_AND_SERVICES", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id == "btn_talk_ai":
            resp = (
                "🎤 *Talk to AI Assistant*\n\n"
                "You can tap the microphone button on your input bar at any time to record a voice message in English, Tamil, Hindi, Telugu, Malayalam, Kannada, or Urdu.\n\n"
                "Our AI Assistant will listen, translate, and respond naturally."
            )
            state["interactive_buttons"] = [language_service.get_translated_button("btn_main_menu", current_lang)]
            state["intent"] = "VOICE_AND_LANGUAGE"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "VOICE_AND_LANGUAGE", state)
            return {"response": resp, "intent": "VOICE_AND_LANGUAGE", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id == "btn_change_language":
            resp = "🌐 *Select Your Language / மொழியைத் தேர்ந்தெடுக்கவும்*\n\nPlease select your preferred language:"
            state["interactive_buttons"] = [
                {"id": "btn_lang_en", "title": "English"},
                {"id": "btn_lang_ta", "title": "தமிழ் (Tamil)"},
                {"id": "btn_lang_hi", "title": "हिंदी (Hindi)"},
                {"id": "btn_lang_te", "title": "తెలుగు (Telugu)"},
                {"id": "btn_lang_ml", "title": "മലയാളം (Malayalam)"},
                {"id": "btn_lang_kn", "title": "ಕನ್ನಡ (Kannada)"},
                {"id": "btn_lang_ur", "title": "اردو (Urdu)"},
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "VOICE_AND_LANGUAGE"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "VOICE_AND_LANGUAGE", state)
            return {"response": resp, "intent": "VOICE_AND_LANGUAGE", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id and btn_id.startswith("btn_lang_"):
            lang_code_map = {
                "btn_lang_en": "ENGLISH",
                "btn_lang_ta": "TAMIL",
                "btn_lang_hi": "HINDI",
                "btn_lang_te": "TELUGU",
                "btn_lang_ml": "MALAYALAM",
                "btn_lang_kn": "KANNADA",
                "btn_lang_ur": "URDU"
            }
            new_lang = lang_code_map.get(btn_id, "ENGLISH")
            state["language"] = new_lang
            resp = language_service.translate_response("LANGUAGE_CHANGED", language=new_lang)
            state["interactive_buttons"] = language_service.get_main_menu_buttons(new_lang)
            state["intent"] = "GREETING"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, new_lang, "GREETING", state)
            return {"response": resp, "intent": "GREETING", "language": new_lang, "interactive_buttons": state["interactive_buttons"]}

        elif btn_id in ("btn_find_doctor", "btn_doctor_avail"):
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT id, department_name FROM departments WHERE status = 'ACTIVE' AND department_name NOT LIKE 'DummyDept%' ORDER BY id ASC LIMIT 5;")
                depts = cur.fetchall()
            finally:
                cur.close()
                conn.close()

            dept_btns = []
            for d_id, d_name in depts:
                dept_btns.append({"id": f"btn_dep_{d_id}", "title": str(d_name)[:20]})
            resp = "Please select a department to find doctors:"
            state["interactive_buttons"] = dept_btns
            state["intent"] = "DOCTOR_AVAILABILITY"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "DOCTOR_AVAILABILITY", state)
            return {
                "response": resp,
                "intent": "DOCTOR_AVAILABILITY",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_departments":
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT department_name FROM departments WHERE status = 'ACTIVE' AND department_name NOT LIKE 'DummyDept%' ORDER BY department_name ASC;")
                rows = cur.fetchall()
                dept_list = [r[0] for r in rows]
            finally:
                cur.close()
                conn.close()

            dept_str = "\n".join([f"• {d}" for d in dept_list])
            resp = f"🏥 *Meridian Hospital Departments*\n\n{dept_str}\n\nWould you like to book an appointment with a specialist?"
            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_book_appt", current_lang),
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "HOSPITAL_INFORMATION"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "HOSPITAL_INFORMATION", state)
            return {
                "response": resp,
                "intent": "HOSPITAL_INFORMATION",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_my_profile":
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            p_data = None
            try:
                if pat_id:
                    cur.execute("SELECT patient_code, first_name, last_name, phone, date_of_birth, gender FROM patients WHERE id = %s;", (pat_id,))
                    p_data = cur.fetchone()
                if not p_data:
                    cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                    w_row = cur.fetchone()
                    if w_row and w_row[0]:
                        cond = get_phone_query_condition()
                        params = get_phone_query_params(w_row[0])
                        cur.execute(f"SELECT patient_code, first_name, last_name, phone, date_of_birth, gender FROM patients WHERE {cond} LIMIT 1;", params)
                        p_data = cur.fetchone()
            finally:
                cur.close()
                conn.close()

            if p_data:
                p_code, fn, ln, ph, dob, g = p_data
                full_n = f"{fn} {ln or ''}".strip()
                dob_str = str(dob) if dob else "N/A"
                resp = (
                    f"👤 *Patient Profile Details*\n\n"
                    f"• *Name:* {full_n}\n"
                    f"• *Patient ID:* {p_code}\n"
                    f"• *Phone:* {ph or 'N/A'}\n"
                    f"• *DOB:* {dob_str}\n"
                    f"• *Gender:* {g or 'N/A'}"
                )
            else:
                resp = "No patient profile was found linked to your session."

            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_my_appts", current_lang),
                language_service.get_translated_button("btn_my_reports", current_lang),
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state["intent"] = "PATIENT_PROFILE"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "PATIENT_PROFILE", state)
            return {
                "response": resp,
                "intent": "PATIENT_PROFILE",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_talk_staff_exec":
            state["escalated"] = True
            state["intent"] = "HUMAN_ESCALATION"
            resp = language_service.get_talk_to_staff_contact_response(current_lang)
            state["interactive_buttons"] = []
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "HUMAN_ESCALATION", state)
            return {
                "response": resp,
                "intent": "HUMAN_ESCALATION",
                "language": current_lang,
                "interactive_buttons": []
            }

        elif btn_id in ("btn_continue_ai", "btn_main_menu"):
            resp = "Welcome back! How can I help you today?"
            state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)
            state["intent"] = "GREETING"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "GREETING", state)
            return {
                "response": resp,
                "intent": "GREETING",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        elif btn_id == "btn_book_appt":

            # Clear any stale booking state so we always start fresh
            state["booking_stage"] = "AWAITING_SYMPTOM"
            state["previous_question"] = "ask_booking_symptom"
            state["confirmation_pending"] = False
            state["change_pending"] = False
            state["change_pending_field"] = None
            state["conversation_state"] = "BOOKING_REASON_REQUIRED"
            state["department_name"] = None
            state["doctor_name"] = None
            state["active_workflow"] = "BOOKING"
            state["intent"] = "BOOK_APPOINTMENT"
            # Explicitly reset dependent/relationship context (Bug 1 fix)
            state["booking_for"] = "SELF"
            state["appointment_for"] = "SELF"
            state["appointment_subject"] = "SELF"
            state["patient_relationship"] = None
            state["dependent_patient_id"] = None
            state["dependent_name"] = None
            state["dependent_collected"] = False
            if state.get("primary_patient_id"):
                state["patient_id"] = state["primary_patient_id"]
                state.setdefault("entities", {})["patient_id"] = state["primary_patient_id"]
            # Clear stale entities
            ents = state.setdefault("entities", {})
            ents["doctor_id"] = None
            ents["department_id"] = None
            ents["reason"] = None
            ents["symptoms"] = []
            ents["appointment_date"] = None
            ents["appointment_time"] = None

            resp = "Sure! I can help you book an appointment. 😊\n\nWhat health problem, symptom, or reason would you like to consult the doctor for?"
            state["interactive_buttons"] = []
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
            return {
                "response": resp,
                "intent": "BOOK_APPOINTMENT",
                "language": current_lang,
                "interactive_buttons": []
            }
        elif btn_id == "btn_hosp_info":
            resp = (
                "🏥 *Meridian Hospital Information*\n\n"
                "Meridian Hospital is a 300-bed multi-super-specialty hospital in Chennai providing 24/7 emergency care and OPD consultations.\n\n"
                "📍 *Address:* #46D, Jawaharlal Nehru Road, 200 Feet Ring Road, Chennai – 600 099\n"
                "📞 *General Enquiries:* 044 6666 9910\n"
                "🚨 *24/7 Emergency Helpline:* 044 6666 9999\n"
                "📧 *Email:* info@meridian-hospital.com\n"
                "🌐 *Website:* https://meridianhospitals.in/\n\n"
                "Key Specialties include Cardiology, Oncology, Critical Care, Pediatrics, Orthopedics, Radiology, Nephrology, Neurology, Gynecology, Emergency & Trauma Care, Urology, Dermatology, Pulmonology, Diabetology, Neurosurgery, Plastic Surgery, etc."
            )
            state["interactive_buttons"] = [
                language_service.get_translated_button("btn_book_appt", current_lang),
                language_service.get_translated_button("btn_cat_doctors", current_lang),
                language_service.get_translated_button("btn_main_menu", current_lang)
            ]
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "HOSPITAL_INFORMATION", state)
            return {
                "response": resp,
                "intent": "HOSPITAL_INFORMATION",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }
        elif btn_id == "btn_my_appts":
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            appts = []
            try:
                cur.execute("""
                    SELECT a.id, a.booking_id, a.appointment_date, a.appointment_time, a.status,
                           d.display_name AS doctor_name, dept.department_name, p.first_name, p.last_name
                    FROM appointments a
                    JOIN doctors d ON a.doctor_id = d.id
                    JOIN departments dept ON d.department_id = dept.id
                    JOIN patients p ON a.patient_id = p.id
                    WHERE a.patient_id = %s AND a.status IN ('CONFIRMED', 'SCHEDULED', 'PENDING')
                    ORDER BY a.appointment_date ASC, a.appointment_time ASC LIMIT 5;
                """, (pat_id,))
                appts = cur.fetchall()
            finally:
                cur.close()
                conn.close()

            if appts:
                appt_buttons = []
                for a in appts:
                    a_id, b_id, a_date, a_time, a_stat, doc_n, dept_n, p_fn, p_ln = a
                    d_str = a_date.strftime("%d %b") if hasattr(a_date, "strftime") else str(a_date)[:10]
                    t_str = format_time_12h(a_time)
                    btn_title = f"{d_str} — {doc_n} — {t_str}"[:20]
                    appt_buttons.append({"id": f"btn_appt_{a_id}", "title": btn_title})
                appt_buttons.append(language_service.get_translated_button("btn_main_menu", current_lang))
                resp = "📅 *Your Upcoming Appointments*\n\nPlease select an appointment to view details, cancel, or reschedule:"
                state["interactive_buttons"] = appt_buttons
            else:
                resp = "You have no upcoming active appointments.\n\nWould you like to book an appointment?"
                state["interactive_buttons"] = [
                    language_service.get_translated_button("btn_book_appt", current_lang),
                    language_service.get_translated_button("btn_main_menu", current_lang)
                ]
            state["intent"] = "APPOINTMENT_STATUS"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "APPOINTMENT_STATUS", state)
            return {
                "response": resp,
                "intent": "APPOINTMENT_STATUS",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }
        elif btn_id == "btn_cancel_appt":
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            appts = []
            try:
                cur.execute("""
                    SELECT a.id, a.booking_id, a.appointment_date, a.appointment_time, a.status,
                           d.display_name AS doctor_name, dept.department_name
                    FROM appointments a
                    JOIN doctors d ON a.doctor_id = d.id
                    JOIN departments dept ON d.department_id = dept.id
                    WHERE a.patient_id = %s AND a.status IN ('CONFIRMED', 'SCHEDULED', 'PENDING')
                    ORDER BY a.appointment_date ASC, a.appointment_time ASC LIMIT 5;
                """, (pat_id,))
                appts = cur.fetchall()
            finally:
                cur.close()
                conn.close()

            if appts:
                appt_buttons = []
                for a in appts:
                    a_id, b_id, a_date, a_time, a_stat, doc_n, dept_n = a
                    d_str = a_date.strftime("%d %b") if hasattr(a_date, "strftime") else str(a_date)[:10]
                    btn_title = f"Cancel {b_id}"[:20]
                    appt_buttons.append({"id": f"btn_cancel_existing_{a_id}", "title": btn_title})
                appt_buttons.append(language_service.get_translated_button("btn_main_menu", current_lang))
                resp = "📅 *Cancel Appointment*\n\nPlease select an appointment you would like to cancel:"
                state["interactive_buttons"] = appt_buttons
            else:
                resp = "You have no active appointments to cancel.\n\nWould you like to book an appointment?"
                state["interactive_buttons"] = [
                    language_service.get_translated_button("btn_book_appt", current_lang),
                    language_service.get_translated_button("btn_main_menu", current_lang)
                ]
            state["intent"] = "CANCEL_APPOINTMENT"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "CANCEL_APPOINTMENT", state)
            return {
                "response": resp,
                "intent": "CANCEL_APPOINTMENT",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }
        elif btn_id == "btn_reschedule_appt":
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            appts = []
            try:
                cur.execute("""
                    SELECT a.id, a.booking_id, a.appointment_date, a.appointment_time, a.status,
                           d.display_name AS doctor_name, dept.department_name
                    FROM appointments a
                    JOIN doctors d ON a.doctor_id = d.id
                    JOIN departments dept ON d.department_id = dept.id
                    WHERE a.patient_id = %s AND a.status IN ('CONFIRMED', 'SCHEDULED', 'PENDING')
                    ORDER BY a.appointment_date ASC, a.appointment_time ASC LIMIT 5;
                """, (pat_id,))
                appts = cur.fetchall()
            finally:
                cur.close()
                conn.close()

            if appts:
                appt_buttons = []
                for a in appts:
                    a_id, b_id, a_date, a_time, a_stat, doc_n, dept_n = a
                    d_str = a_date.strftime("%d %b") if hasattr(a_date, "strftime") else str(a_date)[:10]
                    btn_title = f"Reschedule {b_id}"[:20]
                    appt_buttons.append({"id": f"btn_reschedule_existing_{a_id}", "title": btn_title})
                appt_buttons.append(language_service.get_translated_button("btn_main_menu", current_lang))
                resp = "📅 *Reschedule Appointment*\n\nPlease select an appointment you would like to reschedule:"
                state["interactive_buttons"] = appt_buttons
            else:
                resp = "You have no active appointments to reschedule.\n\nWould you like to book an appointment?"
                state["interactive_buttons"] = [
                    language_service.get_translated_button("btn_book_appt", current_lang),
                    language_service.get_translated_button("btn_main_menu", current_lang)
                ]
            state["intent"] = "RESCHEDULE_APPOINTMENT"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "RESCHEDULE_APPOINTMENT", state)
            return {
                "response": resp,
                "intent": "RESCHEDULE_APPOINTMENT",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }
        elif btn_id == "btn_my_reports":
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            reports = []
            try:
                cur.execute("""
                    SELECT id, report_reference, report_type, report_title, report_date, status, summary
                    FROM patient_reports
                    WHERE patient_id = %s AND UPPER(status) IN ('AVAILABLE', 'COMPLETED', 'READY', 'ACTIVE')
                    ORDER BY report_date DESC LIMIT 5;
                """, (pat_id,))
                reports = cur.fetchall()
            finally:
                cur.close()
                conn.close()

            if reports:
                report_buttons = []
                for r in reports:
                    r_id, r_ref, r_type, r_title, r_date, r_status, r_sum = r
                    d_str = r_date.strftime("%d %b") if hasattr(r_date, "strftime") else str(r_date)[:10]
                    title_btn = f"{r_title} — {d_str}"[:20]
                    report_buttons.append({"id": f"btn_report_{r_id}", "title": title_btn})
                report_buttons.append(language_service.get_translated_button("btn_main_menu", current_lang))
                resp = "📄 *Your Reports*\n\nPlease select a report to view details:"
                state["interactive_buttons"] = report_buttons
            else:
                resp = "No medical reports were found for your account.\n\nIf you recently had lab tests done, please allow 24–48 hours for reports to be uploaded to your patient record."
                state["interactive_buttons"] = [
                    language_service.get_translated_button("btn_main_menu", current_lang)
                ]
            state["intent"] = "PATIENT_REPORTS"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "PATIENT_REPORTS", state)
            return {
                "response": resp,
                "intent": "PATIENT_REPORTS",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }
        elif btn_id and btn_id.startswith("btn_report_"):
            try:
                rep_id = int(btn_id.split("btn_report_")[1])
            except (ValueError, IndexError):
                rep_id = None
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            if rep_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                r_row = None
                try:
                    cur.execute("""
                        SELECT r.report_reference, r.report_type, r.report_title, r.report_date, r.status, r.summary,
                               d.display_name AS doctor_name, dept.department_name
                        FROM patient_reports r
                        LEFT JOIN doctors d ON r.doctor_id = d.id
                        LEFT JOIN departments dept ON r.department_id = dept.id
                        WHERE r.id = %s AND r.patient_id = %s;
                    """, (rep_id, pat_id))
                    r_row = cur.fetchone()
                finally:
                    cur.close()
                    conn.close()
                if r_row:
                    r_ref, r_type, r_title, r_date, r_status, r_sum, doc_name, dept_name = r_row
                    d_str = r_date.strftime("%d %b %Y") if hasattr(r_date, "strftime") else str(r_date)[:10]
                    resp = (
                        f"📄 *{r_title}*\n\n"
                        f"Report ID: {r_ref}\n"
                        f"Date: {d_str}\n"
                        f"Department: {dept_name or 'General'}\n"
                        f"Doctor: {doc_name or 'Meridian Desk'}\n"
                        f"Status: {r_status}\n\n"
                        f"*Summary:*\n{r_sum or 'Report available in patient record.'}\n\n"
                        f"What would you like to do?"
                    )
                    buttons = [
                        language_service.get_translated_button("btn_my_reports", current_lang),
                        language_service.get_translated_button("btn_main_menu", current_lang)
                    ]
                    state["interactive_buttons"] = buttons
                    state["intent"] = "PATIENT_REPORTS"
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "PATIENT_REPORTS", state)
                    return {"response": resp, "intent": "PATIENT_REPORTS", "language": current_lang, "interactive_buttons": buttons}

        elif btn_id in ["btn_pay_gpay", "btn_pay_phonepe", "btn_pay_paytm", "btn_pay_upi", "btn_pay_netbanking"]:
            method_map = {
                "btn_pay_gpay": ("GPAY", "GPay"),
                "btn_pay_phonepe": ("PHONEPE", "PhonePe"),
                "btn_pay_paytm": ("PAYTM", "Paytm"),
                "btn_pay_upi": ("UPI", "UPI"),
                "btn_pay_netbanking": ("NETBANKING", "NetBanking")
            }
            method_code, display_name = method_map.get(btn_id, ("GPAY", "GPay"))
            doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id")
            if doc_id:
                state["selected_doctor_id"] = int(doc_id)
                state.setdefault("entities", {})["doctor_id"] = int(doc_id)
            appt_date = state["entities"].get("appointment_date")
            appt_time = state["entities"].get("appointment_time")
            doc_info = resolve_doctor_details(doc_id) if doc_id else {"name": "Doctor", "department": "General Medicine", "consultation_fee": 800}
            fee_val = doc_info.get("consultation_fee") or 800
            fee_str = f"₹{fee_val:.0f}" if (isinstance(fee_val, float) and fee_val.is_integer()) or isinstance(fee_val, int) else f"₹{fee_val}"

            pat_id = state.get("dependent_patient_id") or state.get("patient_id")
            pay_ref = f"PAY{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
            pay_db_id = None
            if pat_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        INSERT INTO payments (payment_reference, patient_id, amount, currency, payment_method, payment_status, created_at, updated_at)
                        VALUES (%s, %s, %s, 'INR', %s, 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        RETURNING id;
                    """, (pay_ref, pat_id, fee_val, method_code))
                    pay_db_id = cur.fetchone()[0]
                    conn.commit()
                except Exception as e:
                    print(f"[PAYMENT_DB_ERR] Error creating pending payment: {e}")
                    conn.rollback()
                finally:
                    cur.close()
                    conn.close()

            state["payment_id"] = pay_db_id
            state["payment_reference"] = pay_ref
            state["payment_method"] = method_code
            state["payment_status"] = "PENDING"
            state["payment_amount"] = fee_val
            state["conversation_state"] = "MOCK_PAYMENT_PROMPT"

            resp = (
                f"💳 *Mock Payment*\n\n"
                f"Doctor: {doc_info['name']}\n"
                f"Department: {doc_info['department']}\n"
                f"Date: {appt_date}\n"
                f"Time: {format_time_12h(appt_time)}\n\n"
                f"Amount: {fee_str}\n"
                f"Payment Method: {display_name}\n\n"
                f"This is a demo payment for the Meridian Hospital Patient Desk POC.\n"
                f"No real payment will be processed."
            )
            pay_prompt_buttons = [
                {"id": "btn_pay_exec", "title": f"Pay {fee_str}"},
                {"id": "btn_pay_change", "title": "Change Payment Method"},
                {"id": "btn_pay_cancel", "title": "Cancel"}
            ]
            state["interactive_buttons"] = pay_prompt_buttons
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
            return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": pay_prompt_buttons}

        elif btn_id == "btn_pay_exec":
            pay_id = state.get("payment_id")
            pay_ref = state.get("payment_reference") or f"PAY{datetime.datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
            method_code = state.get("payment_method", "GPAY")
            method_names = {"GPAY": "GPay", "PHONEPE": "PhonePe", "PAYTM": "Paytm", "UPI": "UPI", "NETBANKING": "NetBanking"}
            display_name = method_names.get(method_code, method_code)

            doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id")
            if doc_id:
                state["selected_doctor_id"] = int(doc_id)
                state.setdefault("entities", {})["doctor_id"] = int(doc_id)
            doc_info = resolve_doctor_details(doc_id) if doc_id else {"name": "Doctor", "department": "General Medicine", "consultation_fee": 800}
            fee_val = state.get("payment_amount") or doc_info.get("consultation_fee") or 800
            fee_str = f"₹{fee_val:.0f}" if (isinstance(fee_val, float) and fee_val.is_integer()) or isinstance(fee_val, int) else f"₹{fee_val}"

            # Idempotency check: if payment already SUCCESS and booking done
            if state.get("payment_status") == "SUCCESS" or state.get("booking_id") or state.get("entities", {}).get("booking_id"):
                booking_id = state.get("booking_id") or state.get("entities", {}).get("booking_id")
                txn_ref = state.get("transaction_reference") or "MOCKTXN"
                resp = (
                    f"✅ *Payment successful!*\n\n"
                    f"Payment Reference: {pay_ref}\n"
                    f"Transaction Reference: {txn_ref}\n"
                    f"Amount Paid: {fee_str}\n"
                    f"Method: {display_name}\n\n"
                    f"Your appointment is already confirmed (ID: {booking_id})."
                )
                clean_buttons = [b for b in state.get("interactive_buttons", []) if not b.get("id", "").startswith("btn_pay_")]
                state["interactive_buttons"] = clean_buttons
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
                return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": clean_buttons}

            # Update payment record to SUCCESS
            txn_ref = f"MOCKTXN{random.randint(100000, 999999)}"
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                if pay_id:
                    cur.execute("UPDATE payments SET payment_status = 'SUCCESS', transaction_reference = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (txn_ref, pay_id))
                    conn.commit()
            except Exception as e:
                print(f"[PAYMENT_UPDATE_ERR] Error marking payment success: {e}")
                conn.rollback()
            finally:
                cur.close()
                conn.close()

            state["payment_status"] = "SUCCESS"
            state["transaction_reference"] = txn_ref
            log_agent_action(conversation_code, "PAYMENT_SUCCESS", {"payment_reference": pay_ref, "amount": fee_val, "transaction_reference": txn_ref})

            # Execute appointment booking transaction
            pat_id = state.get("patient_id")
            dept_id = state["entities"].get("department_id")
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

            appt_date = state["entities"]["appointment_date"]
            appt_time = state["entities"]["appointment_time"]
            reason = state["entities"].get("reason") or "General Consultation"

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

            if res.get("success"):
                booking_id = (res.get("data") or {}).get("booking_id") or res.get("booking_id")
                state["booking_id"] = booking_id
                state.setdefault("entities", {})["booking_id"] = booking_id
                state["confirmation_pending"] = False
                state["conversation_state"] = "BOOKING_COMPLETED"

                # Link appointment_id in payments table
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    if pay_id and booking_id:
                        cur.execute("UPDATE payments SET appointment_id = (SELECT id FROM appointments WHERE booking_id = %s LIMIT 1) WHERE id = %s;", (booking_id, pay_id))
                        conn.commit()
                except Exception as e:
                    print(f"[PAYMENT_LINK_ERR] Error linking appointment_id to payment: {e}")
                    conn.rollback()
                finally:
                    cur.close()
                    conn.close()

                # Get patient display details
                pat_name = state["entities"].get("patient_name_override") or state.get("dependent_name")
                db_dob, db_gender, db_pat_code = None, None, state.get("dependent_patient_code") or state.get("patient_code")
                if booking_pat_id:
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT first_name, last_name, date_of_birth, gender, patient_code FROM patients WHERE id = %s;", (booking_pat_id,))
                        p_row = cur.fetchone()
                        if p_row:
                            if not pat_name:
                                pat_name = f"{p_row[0]} {p_row[1] or ''}".strip()
                            db_dob = p_row[2]
                            db_gender = p_row[3]
                            if len(p_row) > 4 and p_row[4]:
                                db_pat_code = p_row[4]
                    finally:
                        cur.close()
                        conn.close()
                pat_code_val = db_pat_code or state.get("patient_code") or ""
                pat_code_line = f"Patient ID: {pat_code_val}\n" if pat_code_val else ""
                pat_dob_raw = state.get("dependent_dob") or db_dob or "-"
                pat_gender_raw = state.get("dependent_gender") or db_gender or "-"
                try:
                    dob_str_clean = str(pat_dob_raw).split("T")[0]
                    if "-" in dob_str_clean and len(dob_str_clean.split("-")[0]) == 4:
                        d_obj = datetime.datetime.strptime(dob_str_clean, "%Y-%m-%d").date()
                        pat_dob_val = d_obj.strftime("%d-%b-%Y")
                    else:
                        pat_dob_val = str(pat_dob_raw)
                except Exception:
                    pat_dob_val = str(pat_dob_raw)
                pat_gender_val = str(pat_gender_raw).capitalize() if pat_gender_raw and str(pat_gender_raw) != "-" else "-"

                resp = (
                    f"✅ *Payment successful!*\n\n"
                    f"Payment Reference: {pay_ref}\n"
                    f"Transaction Reference: {txn_ref}\n"
                    f"Amount Paid: {fee_str}\n"
                    f"Method: {display_name}\n\n"
                    f"Your appointment has been confirmed!\n\n"
                    f"Patient: {pat_name or 'Patient'}\n"
                    f"{pat_code_line}"
                    f"DOB: {pat_dob_val}\n"
                    f"Gender: {pat_gender_val}\n"
                    f"Reason: {reason}\n"
                    f"Department: {doc_info['department']}\n"
                    f"Doctor: {doc_info['name']}\n"
                    f"Date: {appt_date}\n"
                    f"Time: {format_time_12h(appt_time)}\n"
                    f"Appointment ID: {booking_id}"
                )
                state["interactive_buttons"] = [
                    {"id": "btn_my_appts", "title": "My Appointments"},
                    {"id": "btn_my_reports", "title": "My Reports"},
                    {"id": "btn_hosp_info", "title": "Hospital Information"}
                ]
                log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
                state_manager.save_conversation_state(conversation_code, state)
                return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}
            else:
                # Booking failed -> mark payment failed
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    if pay_id:
                        cur.execute("UPDATE payments SET payment_status = 'FAILED', updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (pay_id,))
                        conn.commit()
                finally:
                    cur.close()
                    conn.close()
                state["payment_status"] = "FAILED"
                resp = "❌ *Payment was not completed or slot is no longer available.*\n\nPlease try again or choose another payment method."
                buttons = [
                    {"id": "btn_pay_change", "title": "Try Again"},
                    {"id": "btn_pay_cancel", "title": "Cancel"}
                ]
                state["interactive_buttons"] = buttons
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
                return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": buttons}

        elif btn_id == "btn_pay_change":
            pay_id = state.get("payment_id")
            if pay_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE payments SET payment_status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (pay_id,))
                    conn.commit()
                finally:
                    cur.close()
                    conn.close()
            state["payment_status"] = "CANCELLED"
            state["conversation_state"] = "PAYMENT_METHOD_REQUIRED"
            doc_id = state["entities"].get("doctor_id")
            doc_info = resolve_doctor_details(doc_id) if doc_id else {"name": "Doctor", "consultation_fee": 800}
            fee_val = doc_info.get("consultation_fee") or 800
            fee_str = f"₹{fee_val:.0f}" if (isinstance(fee_val, float) and fee_val.is_integer()) or isinstance(fee_val, int) else f"₹{fee_val}"

            pay_method_buttons = [
                {"id": "btn_pay_gpay", "title": "GPay"},
                {"id": "btn_pay_phonepe", "title": "PhonePe"},
                {"id": "btn_pay_paytm", "title": "Paytm"},
                {"id": "btn_pay_upi", "title": "UPI"},
                {"id": "btn_pay_netbanking", "title": "NetBanking"}
            ]
            resp = (
                f"Your appointment slot is available.\n\n"
                f"Consultation Fee: {fee_str}\n\n"
                f"Please choose a payment method to continue."
            )
            state["interactive_buttons"] = pay_method_buttons
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
            return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": pay_method_buttons}

        elif btn_id in ["btn_confirm_appt", "btn_confirm"]:
            state["payment_status"] = None
            if True:
                doc_id = state["entities"].get("doctor_id")
                doc_info = resolve_doctor_details(doc_id) if doc_id else {"name": "Doctor", "department": "General Medicine", "consultation_fee": 800}
                fee_val = doc_info.get("consultation_fee") or 800
                fee_str = f"₹{fee_val:.0f}" if (isinstance(fee_val, float) and fee_val.is_integer()) or isinstance(fee_val, int) else f"₹{fee_val}"
                appt_date = state["entities"].get("appointment_date")
                appt_time = state["entities"].get("appointment_time")

                # Revalidate slot before asking for payment
                if doc_id and appt_date and appt_time:
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                    avail = res_slots.get("slots", []) if res_slots.get("success") else []
                    if appt_time not in avail:
                        state["entities"]["appointment_time"] = None
                        state["confirmation_pending"] = False
                        formatted_slots = [format_time_12h(s) for s in avail] if avail else []
                        alt_slots_text = "\n• ".join(formatted_slots) if formatted_slots else "No available slots"
                        response_text = (
                            f"Sorry, *{format_time_12h(appt_time)}* is no longer available on *{appt_date}*.\n\n"
                            f"📅 Available slots for *{doc_info['name']}* on *{appt_date}*:\n• {alt_slots_text}\n\n"
                            f"Please select a new time slot."
                        )
                        alt_buttons = [{"id": f"btn_slot_{s}", "title": format_time_12h(s)} for s in avail]
                        state["interactive_buttons"] = alt_buttons
                        state_manager.save_conversation_state(conversation_code, state)
                        log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, "BOOK_APPOINTMENT", state)
                        return {
                            "response": response_text,
                            "intent": "BOOK_APPOINTMENT",
                            "language": current_lang,
                            "interactive_buttons": alt_buttons
                        }

                # Create PENDING payment entry in PostgreSQL payments table
                pat_id = state.get("dependent_patient_id") or state.get("patient_id")
                pay_ref = f"PAY{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
                pay_db_id = None
                if pat_id:
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("""
                            INSERT INTO payments (payment_reference, patient_id, amount, currency, payment_method, payment_status, created_at, updated_at)
                            VALUES (%s, %s, %s, 'INR', 'GPAY', 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            RETURNING id;
                        """, (pay_ref, pat_id, fee_val))
                        pay_db_id = cur.fetchone()[0]
                        conn.commit()
                    except Exception as e:
                        print(f"[PAYMENT_DB_ERR] Error creating pending payment: {e}")
                        conn.rollback()
                    finally:
                        cur.close()
                        conn.close()

                state["payment_id"] = pay_db_id
                state["payment_reference"] = pay_ref
                state["payment_amount"] = fee_val
                state["conversation_state"] = "PAYMENT_METHOD_REQUIRED"
                state["confirmation_pending"] = False

                pay_method_buttons = [
                    {"id": "btn_pay_gpay", "title": "Google Pay"},
                    {"id": "btn_pay_phonepe", "title": "PhonePe"},
                    {"id": "btn_pay_paytm", "title": "Paytm"},
                    {"id": "btn_pay_upi", "title": "UPI"},
                    {"id": "btn_pay_netbanking", "title": "Net Banking"}
                ]
                response_text = (
                    f"💳 *Payment Required*\n\n"
                    f"Please complete the consultation payment to confirm your appointment.\n\n"
                    f"Doctor: {doc_info['name']}\n"
                    f"Department: {doc_info['department']}\n"
                    f"Date: {appt_date}\n"
                    f"Time: {format_time_12h(appt_time)}\n"
                    f"Consultation Fee: {fee_str}\n\n"
                    f"Please select your payment method:"
                )
                state["interactive_buttons"] = pay_method_buttons
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, "BOOK_APPOINTMENT", state)
                return {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": pay_method_buttons
                }

        elif btn_id == "btn_pay_cancel":
            pay_id = state.get("payment_id")
            if pay_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("UPDATE payments SET payment_status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP WHERE id = %s;", (pay_id,))
                    conn.commit()
                finally:
                    cur.close()
                    conn.close()
            state["payment_status"] = "CANCELLED"
            state["confirmation_pending"] = False
            state["conversation_state"] = "AWAITING_INTENT"
            resp = "Appointment booking has been cancelled as payment was not completed.\n\nWould you like to start over or view hospital information?"
            buttons = [
                {"id": "btn_book_appt", "title": "Book Appointment"},
                {"id": "btn_hosp_info", "title": "Hospital Information"}
            ]
            state["interactive_buttons"] = buttons
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
            return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": buttons}

        elif btn_id and btn_id.startswith("btn_appt_"):
            try:
                appt_db_id = int(btn_id.split("btn_appt_")[1])
            except (ValueError, IndexError):
                appt_db_id = None
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            if appt_db_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                a_row = None
                try:
                    cur.execute("""
                        SELECT a.id, a.booking_id, a.appointment_date, a.appointment_time, a.status,
                               d.display_name AS doctor_name, dept.department_name, p.first_name, p.last_name, p.patient_code
                        FROM appointments a
                        JOIN doctors d ON a.doctor_id = d.id
                        JOIN departments dept ON d.department_id = dept.id
                        JOIN patients p ON a.patient_id = p.id
                        WHERE a.id = %s AND a.patient_id = %s;
                    """, (appt_db_id, pat_id))
                    a_row = cur.fetchone()
                finally:
                    cur.close()
                    conn.close()
                if a_row:
                    _, b_id, a_date, a_time, a_status, doc_n, dept_n, p_fn, p_ln, p_code = a_row
                    d_str = a_date.strftime("%d %B %Y") if hasattr(a_date, "strftime") else str(a_date)
                    p_name = f"{p_fn} {p_ln or ''}".strip()
                    resp = (
                        f"📅 *Appointment Details*\n\n"
                        f"Patient: {p_name}\n"
                        f"Patient ID: {p_code}\n\n"
                        f"Doctor: {doc_n}\n"
                        f"Department: {dept_n}\n"
                        f"Date: {d_str}\n"
                        f"Time: {format_time_12h(a_time)}\n"
                        f"Appointment ID: {b_id}\n"
                        f"Status: {a_status}\n\n"
                        f"What would you like to do?"
                    )
                    buttons = [
                        {"id": f"btn_cancel_existing_{appt_db_id}", "title": "Cancel Appointment"},
                        {"id": f"btn_reschedule_existing_{appt_db_id}", "title": "Reschedule Appointment"},
                        {"id": "btn_my_appts", "title": "Back to Appointments"}
                    ]
                    state["interactive_buttons"] = buttons
                    state["intent"] = "APPOINTMENT_STATUS"
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "APPOINTMENT_STATUS", state)
                    return {"response": resp, "intent": "APPOINTMENT_STATUS", "language": current_lang, "interactive_buttons": buttons}

        elif btn_id and btn_id.startswith("btn_cancel_existing_"):
            try:
                appt_db_id = int(btn_id.split("btn_cancel_existing_")[1])
            except (ValueError, IndexError):
                appt_db_id = None
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            if appt_db_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                b_id, doc_n = None, None
                try:
                    cur.execute("""
                        SELECT a.booking_id, d.display_name
                        FROM appointments a JOIN doctors d ON a.doctor_id = d.id
                        WHERE a.id = %s AND a.patient_id = %s;
                    """, (appt_db_id, pat_id))
                    r = cur.fetchone()
                    if r:
                        b_id, doc_n = r[0], r[1]
                finally:
                    cur.close()
                    conn.close()
                if b_id:
                    state["entities"]["booking_id"] = b_id
                    state["intent"] = "CANCEL_APPOINTMENT"
                    resp = f"Are you sure you want to cancel appointment *{b_id}* ({doc_n})?"
                    buttons = [
                        {"id": f"btn_exec_cancel_{b_id}", "title": "Yes, Cancel"},
                        {"id": "btn_my_appts", "title": "Keep Appointment"}
                    ]
                    state["interactive_buttons"] = buttons
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "CANCEL_APPOINTMENT", state)
                    return {"response": resp, "intent": "CANCEL_APPOINTMENT", "language": current_lang, "interactive_buttons": buttons}

        elif btn_id and btn_id.startswith("btn_exec_cancel_"):
            b_id = btn_id.split("btn_exec_cancel_")[1]
            res = tool_registry.tool_cancel_appointment(conversation_code=conversation_code, booking_id=b_id, reason="Patient requested cancellation via WhatsApp", user_id=None)
            if res.get("success"):
                log_agent_action(conversation_code, "APPOINTMENT_CANCELLED", {"booking_id": b_id})
                resp = f"✅ Your appointment *{b_id}* has been cancelled successfully.\n\nWould you like to book another appointment?"
                buttons = [
                    {"id": "btn_book_appt", "title": "Book Appointment"},
                    {"id": "btn_hosp_info", "title": "Hospital Information"}
                ]
                state["interactive_buttons"] = buttons
                state["intent"] = "CANCEL_APPOINTMENT"
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "CANCEL_APPOINTMENT", state)
                return {"response": resp, "intent": "CANCEL_APPOINTMENT", "language": current_lang, "interactive_buttons": buttons}

        elif btn_id and btn_id.startswith("btn_reschedule_existing_"):
            try:
                appt_db_id = int(btn_id.split("btn_reschedule_existing_")[1])
            except (ValueError, IndexError):
                appt_db_id = None
            pat_id = state.get("dependent_patient_id") or state.get("patient_id") or state.get("primary_patient_id")
            if appt_db_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                b_id, doc_id = None, None
                try:
                    cur.execute("SELECT booking_id, doctor_id FROM appointments WHERE id = %s AND patient_id = %s;", (appt_db_id, pat_id))
                    r = cur.fetchone()
                    if r:
                        b_id, doc_id = r[0], r[1]
                finally:
                    cur.close()
                    conn.close()
                if b_id and doc_id:
                    state["entities"]["booking_id"] = b_id
                    state["entities"]["doctor_id"] = doc_id
                    state["selected_doctor_id"] = doc_id
                    sync_selected_doctor_state(state, doc_id)
                    doc_info = resolve_doctor_details(doc_id)
                    state["intent"] = "RESCHEDULE_APPOINTMENT"
                    return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, current_lang=current_lang, intent="RESCHEDULE_APPOINTMENT")

    # ── NEW: Dynamic button fast-path handlers ──────────────────────────────────
    # These handle btn_doc_{id}, btn_dep_{id}, btn_slot_{HH:MM}, btn_date_*, btn_chg_*
    # They are resolved here BEFORE the LLM router to avoid expensive LLM calls for
    # simple structured button selections.
    if btn_id and btn_id.startswith("btn_doc_"):
        try:
            pressed_doc_id = int(btn_id.split("btn_doc_")[1])
        except (ValueError, IndexError):
            pressed_doc_id = None
        if pressed_doc_id:
            print(f"[BUTTON_ROUTING] Doctor button tap: doc_id={pressed_doc_id}")
            sync_selected_doctor_state(state, pressed_doc_id)
            doc_info = resolve_doctor_details(pressed_doc_id)
            state["conversation_state"] = "DOCTOR_SELECTED"
            state["intent"] = "BOOK_APPOINTMENT"
            state["booking_stage"] = None
            state["confirmation_pending"] = False
            preserved_date = state["entities"].get("appointment_date")
            if preserved_date:
                target_date = preserved_date
                state["entities"]["appointment_date"] = target_date
                state["entities"]["appointment_time"] = None

                details_parts = [f"👨‍⚕️ *{doc_info['name']}*", f"🏥 *Department*: {doc_info['department']}"]
                if doc_info.get("qualification"):
                    details_parts.append(f"🎓 *Qualification*: {doc_info['qualification']}")
                if doc_info.get("experience_years"):
                    details_parts.append(f"💼 *Experience*: {doc_info['experience_years']} years")
                if doc_info.get("consultation_fee"):
                    fee_val = doc_info["consultation_fee"]
                    fee_str = f"₹{fee_val:.0f}" if (isinstance(fee_val, float) and fee_val.is_integer()) or isinstance(fee_val, int) else f"₹{fee_val}"
                    details_parts.append(f"💵 *Consultation Fee*: {fee_str}")
                details_header = "\n".join(details_parts)

                res_slots = tool_registry.tool_get_available_slots(conversation_code, pressed_doc_id, target_date)
                slots_list = res_slots.get("slots", []) if res_slots.get("success") else []

                if slots_list:
                    return build_verified_slot_selection_response(conversation_code, state, pressed_doc_id, doc_info, target_date, slots_list, details_header, current_lang, "BOOK_APPOINTMENT")
                else:
                    return build_verified_date_selection_response(conversation_code, state, pressed_doc_id, doc_info, failed_date=target_date, current_lang=current_lang, intent="BOOK_APPOINTMENT")
            else:
                # Patient has NOT specified a date yet -> Ask for appointment date!
                return build_verified_date_selection_response(conversation_code, state, pressed_doc_id, doc_info, current_lang=current_lang, intent="BOOK_APPOINTMENT")

    elif btn_id and btn_id.startswith("btn_dep_"):
        try:
            pressed_dep_id = int(btn_id.split("btn_dep_")[1])
        except (ValueError, IndexError):
            pressed_dep_id = None
        if pressed_dep_id:
            print(f"[BUTTON_ROUTING] Dependent button tap: dep_id={pressed_dep_id}")
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            dep_name = None
            try:
                cur.execute("SELECT first_name, last_name FROM patients WHERE id = %s AND status = 'ACTIVE';", (pressed_dep_id,))
                p_row = cur.fetchone()
                if p_row:
                    dep_name = f"{p_row[0]} {p_row[1] or ''}".strip()
            finally:
                cur.close()
                conn.close()
            if dep_name:
                state["patient_id"] = pressed_dep_id
                state["dependent_patient_id"] = pressed_dep_id
                state["dependent_name"] = dep_name
                state["entities"]["patient_id"] = pressed_dep_id
                state["entities"]["patient_name_override"] = dep_name
                state["dependent_collected"] = True
                state["pending_stage"] = None
                state["previous_question"] = None
                resp = (
                    f"Booking for *{dep_name}* ✅\n\n"
                    f"Which health problem or symptom would you like to book for?"
                )
                state["intent"] = "BOOK_APPOINTMENT"
                state["booking_stage"] = "AWAITING_SYMPTOM"
                state["previous_question"] = "ask_booking_symptom"
                state["interactive_buttons"] = []
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
                return {
                    "response": resp,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": []
                }

    elif btn_id and btn_id.startswith("btn_slot_"):
        try:
            pressed_time = btn_id.split("btn_slot_")[1]  # e.g. "09:00"
        except IndexError:
            pressed_time = None
        if pressed_time:
            doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id")
            if doc_id:
                state["selected_doctor_id"] = int(doc_id)
                state.setdefault("entities", {})["doctor_id"] = int(doc_id)
            appt_date = state["entities"].get("appointment_date")
            print(f"[BUTTON_ROUTING] Slot button tap: time={pressed_time}")
            print(f"[DATE_STATE_DEBUG] btn_slot handler: doctor_id={doc_id}, appointment_date={appt_date}, appointment_time={pressed_time}, stage={state.get('conversation_state')}")
            state["entities"]["appointment_time"] = pressed_time
            state["intent"] = "BOOK_APPOINTMENT"
            # Validate that the slot is still available
            slot_valid = False
            if doc_id and appt_date:
                res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                avail = res_slots.get("slots", []) if res_slots.get("success") else []
                slot_valid = pressed_time in avail
            if slot_valid:
                # Slot is validated -> Move to Appointment Preview state
                doc_info = resolve_doctor_details(doc_id) if doc_id else {"name": "Doctor", "department": "General Medicine", "consultation_fee": 800}
                state["confirmation_pending"] = True
                state["conversation_state"] = "CONFIRMATION_PENDING"
                state["payment_status"] = None
                state["payment_id"] = None
                state["payment_reference"] = None

                # Get patient details for preview card
                pat_id = state.get("dependent_patient_id") or state.get("patient_id")
                pat_name = state["entities"].get("patient_name_override") or state.get("dependent_name")
                db_dob, db_gender, db_pat_code = None, None, state.get("dependent_patient_code") or state.get("patient_code")
                if pat_id:
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("SELECT first_name, last_name, date_of_birth, gender, patient_code FROM patients WHERE id = %s;", (pat_id,))
                        p_row = cur.fetchone()
                        if p_row:
                            if not pat_name:
                                pat_name = f"{p_row[0]} {p_row[1] or ''}".strip()
                            db_dob = p_row[2]
                            db_gender = p_row[3]
                            if len(p_row) > 4 and p_row[4]:
                                db_pat_code = p_row[4]
                    finally:
                        cur.close()
                        conn.close()

                pat_code_val = db_pat_code or state.get("patient_code") or ""
                pat_code_line = f"Patient ID: {pat_code_val}\n" if pat_code_val else ""
                pat_dob_raw = state.get("dependent_dob") or db_dob or "-"
                pat_gender_raw = state.get("dependent_gender") or db_gender or "-"
                try:
                    dob_str_clean = str(pat_dob_raw).split("T")[0]
                    if "-" in dob_str_clean and len(dob_str_clean.split("-")[0]) == 4:
                        d_obj = datetime.datetime.strptime(dob_str_clean, "%Y-%m-%d").date()
                        pat_dob_val = d_obj.strftime("%d-%b-%Y")
                    else:
                        pat_dob_val = str(pat_dob_raw)
                except Exception:
                    pat_dob_val = str(pat_dob_raw)
                pat_gender_val = str(pat_gender_raw).capitalize() if pat_gender_raw and str(pat_gender_raw) != "-" else "-"
                reason = state["entities"].get("reason") or "General Consultation"

                resp = (
                    f"Please confirm your appointment details:\n\n"
                    f"Patient: {pat_name or 'Patient'}\n"
                    f"{pat_code_line}"
                    f"DOB: {pat_dob_val}\n"
                    f"Gender: {pat_gender_val}\n"
                    f"Reason: {reason}\n"
                    f"Department: {doc_info['department']}\n"
                    f"Doctor: {doc_info['name']}\n"
                    f"Date: {appt_date}\n"
                    f"Time: {format_time_12h(pressed_time)}"
                )
                confirm_buttons = [
                    {"id": "btn_confirm_appt", "title": "Confirm Appointment"},
                    {"id": "btn_change_appt", "title": "Change Details"},
                    {"id": "btn_cancel_appt", "title": "Cancel"}
                ]
                state["interactive_buttons"] = confirm_buttons
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
                return {
                    "response": resp,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": confirm_buttons
                }
            else:
                # Slot is gone — show fresh available slots
                doc_info = resolve_doctor_details(doc_id) if doc_id else {"name": "Doctor", "department": "General"}
                state["entities"]["appointment_time"] = None
                if doc_id and appt_date:
                    res_slots2 = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                    avail2 = res_slots2.get("slots", []) if res_slots2.get("success") else []
                    if avail2:
                        res_p = build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, avail2, current_lang=current_lang, intent="BOOK_APPOINTMENT")
                        res_p["response"] = f"Sorry, *{format_time_12h(pressed_time)}* is no longer available.\n\n" + res_p["response"]
                        return res_p
                    else:
                        return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, failed_date=appt_date, current_lang=current_lang, intent="BOOK_APPOINTMENT")
                else:
                    resp = "I couldn't verify the slot. Please try selecting again or type your preferred time."
                    new_slot_buttons = []
                state["interactive_buttons"] = new_slot_buttons
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
                return {
                    "response": resp,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": new_slot_buttons
                }

    elif btn_id == "btn_date_custom":
        print("[BUTTON_ROUTING] Choose Another Date button tap: btn_date_custom")
        doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id")
        doc_name = "the doctor"
        if doc_id:
            doc_info = resolve_doctor_details(doc_id)
            if doc_info and doc_info.get("name"):
                doc_name = doc_info["name"]
        state["conversation_state"] = "DATE_REQUIRED"
        state["entities"]["appointment_date"] = None
        state["entities"]["appointment_time"] = None
        resp = f"Please enter or select the date you prefer to consult *{doc_name}* (e.g., 18th September or 2026-09-18):"
        state["interactive_buttons"] = []
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
        return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": []}

    elif btn_id in ["btn_date_today", "btn_date_tomorrow"] or (btn_id and btn_id.startswith("btn_date_")):
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        today = datetime.datetime.now(ist).date()
        if btn_id == "btn_date_today":
            target_date = today.strftime("%Y-%m-%d")
        elif btn_id == "btn_date_tomorrow":
            target_date = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            try:
                target_date = btn_id.split("btn_date_")[1]  # e.g. "2026-09-15"
            except IndexError:
                target_date = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        print(f"[BUTTON_ROUTING] Date button tap: date={target_date}")
        print(f"[DATE_STATE_DEBUG] btn_date handler: setting appointment_date={target_date}, clearing appointment_time")
        state["entities"]["appointment_date"] = target_date
        state["entities"]["appointment_time"] = None
        state["intent"] = "BOOK_APPOINTMENT"
        doc_id = state["entities"].get("doctor_id")
        if doc_id:
            doc_info = resolve_doctor_details(doc_id)
            res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, target_date)
            slots_list = res_slots.get("slots", []) if res_slots.get("success") else []
            if slots_list:
                return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, target_date, slots_list, current_lang=current_lang, intent="BOOK_APPOINTMENT")
            else:
                return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, failed_date=target_date, current_lang=current_lang, intent="BOOK_APPOINTMENT")
        else:
            # No doctor yet — just store the date and continue to normal flow
            pass

    elif btn_id in ["btn_change_time", "btn_chg_time"] or (message_text and message_text.strip().lower() in ["change time", "btn_change_time"]):
        print("[BUTTON_ROUTING] Change time button tap")
        state["entities"]["appointment_time"] = None
        state["confirmation_pending"] = False
        doc_id = state["entities"].get("doctor_id")
        appt_date = state["entities"].get("appointment_date")
        if doc_id and appt_date:
            doc_info = resolve_doctor_details(doc_id)
            res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
            slots_list = res_slots.get("slots", []) if res_slots.get("success") else []
            if slots_list:
                return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, slots_list, current_lang=current_lang, intent="BOOK_APPOINTMENT")

    elif btn_id == "btn_change_appt":
        print("[BUTTON_ROUTING] Change appointment button tap: btn_change_appt")
        state["confirmation_pending"] = False
        state["change_pending"] = True
        resp = "What detail would you like to change?"
        chg_buttons = [
            {"id": "btn_chg_doctor", "title": "Doctor"},
            {"id": "btn_chg_date",   "title": "Date"},
            {"id": "btn_chg_time",   "title": "Time"},
            {"id": "btn_chg_reason", "title": "Reason"},
            {"id": "btn_chg_name",   "title": "Patient Name"},
        ]
        state["interactive_buttons"] = chg_buttons
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
        return {
            "response": resp,
            "intent": "BOOK_APPOINTMENT",
            "language": current_lang,
            "interactive_buttons": chg_buttons
        }

    elif btn_id in ["btn_chg_name", "btn_chg_date", "btn_chg_time", "btn_chg_doctor", "btn_chg_reason"]:
        print(f"[BUTTON_ROUTING] Change-details button tap: {btn_id}")
        field_map = {
            "btn_chg_name":   "patient_name",
            "btn_chg_date":   "date",
            "btn_chg_time":   "time",
            "btn_chg_doctor": "doctor",
            "btn_chg_reason": "reason",
        }
        chosen_field = field_map[btn_id]
        state["change_pending"] = False
        state["change_pending_field"] = chosen_field
        state["confirmation_pending"] = False
        state["intent"] = "BOOK_APPOINTMENT"
        if chosen_field == "patient_name":
            resp = "Please enter the updated *patient full name*:"
            state["interactive_buttons"] = []
        elif chosen_field == "date":
            state["entities"]["appointment_date"] = None
            state["entities"]["appointment_time"] = None
            doc_id = state["entities"].get("doctor_id")
            if doc_id:
                doc_info = resolve_doctor_details(doc_id)
                return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, current_lang=current_lang, intent="BOOK_APPOINTMENT")
            resp = "Please enter your updated preferred appointment date (e.g. *tomorrow*, *Monday*, *15 Sep*):"
            state["interactive_buttons"] = []
        elif chosen_field == "time":
            state["entities"]["appointment_time"] = None
            doc_id = state["entities"].get("doctor_id")
            appt_date = state["entities"].get("appointment_date")
            slot_buttons = []
            if doc_id and appt_date:
                res_alt = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                if res_alt.get("slots"):
                    slot_buttons = [{"id": f"btn_slot_{s}", "title": format_time_12h(s)} for s in res_alt["slots"]]
            resp = "Please choose your updated preferred appointment time:"
            state["interactive_buttons"] = slot_buttons
        elif chosen_field == "doctor":
            state["entities"]["doctor_id"] = None
            state["entities"]["department_id"] = None
            state["entities"]["appointment_date"] = None
            state["entities"]["appointment_time"] = None
            resp = "Which doctor or department would you like to switch to?"
            state["interactive_buttons"] = []
        else:  # reason
            resp = "Please enter your updated reason for visit:"
            state["interactive_buttons"] = []
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "BOOK_APPOINTMENT", state)
        return {
            "response": resp,
            "intent": "BOOK_APPOINTMENT",
            "language": current_lang,
            "interactive_buttons": state["interactive_buttons"]
        }

    # ── END: Dynamic button fast-path handlers ───────────────────────────────────

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

    # Pre-resolve patient ID & info from active phone using Patient Identification Service (if not already resolved in state)
    if not state.get("patient_info") or not state.get("patient_id"):
        try:
            w_num = None
            if conversation_code and conversation_code.startswith("WA_"):
                parts = conversation_code.split("_")
                if len(parts) >= 2 and parts[1].isdigit():
                    w_num = parts[1]
            if not w_num:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
                    row = cur.fetchone()
                    if row and row[0]:
                        w_num = row[0]
                finally:
                    cur.close()
                    conn.close()

            if w_num:
                id_res = patient_id_service.identify_patient_by_phone(w_num)
                if id_res.get("found") and id_res.get("patient"):
                    p_data = id_res["patient"]
                    state["patient_id"] = p_data["id"]
                    state["entities"]["patient_id"] = p_data["id"]
                    state["patient_info"] = p_data
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("UPDATE conversations SET patient_id = %s WHERE conversation_code = %s;", (p_data["id"], conversation_code))
                        conn.commit()
                    except Exception:
                        conn.rollback()
                    finally:
                        cur.close()
                        conn.close()
        except Exception as e:
            print("Failed to auto-resolve patient by phone:", e)

    # Apply override if specified
    if language_override:
        state["language"] = language_override.upper()
        
    current_lang = state.get("language", "ENGLISH")

    # Log incoming patient message
    # Use quick rule-based detector for audit DB log only (lightweight)
    turn_intent = intent_detector.detect_intent(message_text, state.get("intent", "GREETING"))
    log_message_to_db(conversation_code, "PATIENT", message_text, current_lang, turn_intent)

    # 2. Medical Safety Check — always deterministic, always first
    safety_response = safety_service.check_medical_safety(message_text, current_lang)
    if safety_response:
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

    # 4. LLM-Powered Intent & Entity Routing (PRIMARY)
    #    Falls back to rule-based engine when LLM is unavailable.
    # ---------------------------------------------------------------------------
    msg_cleaned = (message_text or "").lower().strip()
    is_affirmative = msg_cleaned in [
        "yes", "sure", "ok", "okay", "please do", "yes please", "yeah", "yup",
        "சரி", "ஆம்", "हाँ", "हाँ जी", "అవును", "ശരി", "അതെ", "ಹೌದು", "جی", "جی ہاں"
    ]
    is_negative = msg_cleaned in [
        "no", "no thanks", "not now", "nope", "nay",
        "இல்லை", "வேண்டாம்", "नहीं", "नहीं धन्यवाद", "వద్దు", "లేదు",
        "വേണ്ട", "ഇല്ല", "ಬೇಡ", "ಇಲ್ಲ", "نہیں"
    ]

    # OK clean text fallback if no question active
    if msg_cleaned in ["ok", "okay", "thanks", "thank you"] and not state.get("previous_question") and not state.get("pending_stage") and not state.get("confirmation_pending"):
        state["intent"] = "GREETING"
        resp_ack = "You're welcome! 😊 How can I help you today?"
        log_message_to_db(conversation_code, "AI_AGENT", resp_ack, current_lang, "GREETING", state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": current_lang,
            "intent": "GREETING",
            "response": resp_ack,
            "missing_information": [],
            "tool_called": None
        }

    # Intercept Booking ID (e.g. APT24321) or AWAITING_BOOKING_ID stage early
    safe_msg = message_text or ""
    is_awaiting_bid = state.get("pending_stage") == "AWAITING_BOOKING_ID" or state.get("previous_question") == "AWAITING_BOOKING_ID"
    if is_awaiting_bid:
        m_id = re.search(r"\b(APT-?\d+|\d{4,8})\b", safe_msg, re.IGNORECASE)
    else:
        m_id = re.search(r"\b(APT-?\d{3,8})\b", safe_msg, re.IGNORECASE)

    if m_id or is_awaiting_bid:
        msg_lwr = safe_msg.lower().strip()
        cancel_words = ["cancel", "exit", "stop", "back", "never mind", "nevermind"]
        if not any(w in msg_lwr for w in cancel_words):
            if m_id:
                b_id = m_id.group(1).upper()
                state["entities"]["booking_id"] = b_id
                state["pending_stage"] = None
                state["previous_question"] = None
                state["intent"] = "APPOINTMENT_STATUS"

                appt_info = fetch_appointment_details_by_booking_id(b_id)
                if appt_info:
                    resp_id = format_single_appointment_card(appt_info)
                else:
                    resp_id = f"Could not find an appointment with Booking ID *{b_id}*. Please check the ID and try again."

                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp_id, current_lang, "APPOINTMENT_STATUS", state)
                return {
                    "response": resp_id,
                    "intent": "APPOINTMENT_STATUS",
                    "language": current_lang,
                    "interactive_buttons": [
                        {"id": "btn_book_appt", "title": "Book Appointment"},
                        {"id": "btn_hosp_info", "title": "Hospital Information"}
                    ]
                }
            else:
                resp_id = (
                    "That doesn't look like a valid Booking ID (e.g. APT10001).\n\n"
                    "Please provide a valid Booking ID, or reply 'cancel' to exit."
                )
                state["previous_question"] = "AWAITING_BOOKING_ID"
                state["pending_stage"] = "AWAITING_BOOKING_ID"
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp_id, current_lang, "APPOINTMENT_STATUS", state)
                return {
                    "response": resp_id,
                    "intent": "APPOINTMENT_STATUS",
                    "language": current_lang,
                    "interactive_buttons": []
                }

    # Retrieve recent conversation history for LLM context
    recent_history = llm_intent_router.get_recent_conversation_history(conversation_code, max_turns=6)

    # Run LLM Intent Router
    llm_route = llm_intent_router.route_patient_message_llm(
        message_text=message_text,
        current_state=state,
        conversation_history=recent_history,
    )

    # ── Language update from LLM router ──────────────────────────────────────
    if llm_route.get("language") and llm_route["language"] != "ENGLISH":
        state["language"] = llm_route["language"]
        current_lang = state["language"]

    # ── Detect intent from LLM result ────────────────────────────────────────
    # Map canonical 12-intent names back to the names used by downstream handlers
    LLM_TO_HANDLER_INTENT = {
        "PATIENT_REGISTRATION":  "REGISTER_PATIENT",
        "DEPENDENT_BOOKING":     "BOOK_APPOINTMENT",   # handled via sub-flow
        "APPOINTMENT_CONFIRMATION": "BOOK_APPOINTMENT",
        "PATIENT_DETAILS_UPDATE": "REGISTER_PATIENT",
        "DOCTOR_AVAILABILITY":   "DOCTOR_AVAILABILITY",
    }
    llm_intent_name = llm_route.get("intent", "UNKNOWN")
    detected_intent = LLM_TO_HANDLER_INTENT.get(llm_intent_name, llm_intent_name)

    GREETING_WORDS = {
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "namaste", "vanakkam", "namaskara", "helo", "hii", "hiii", "greetings"
    }
    ACK_WORDS = {
        "ok", "okay", "thanks", "thank you", "thanks!", "great", "fine", "alright", "k", "sure", "noted"
    }
    msg_clean_greeting = safe_msg.lower().strip().rstrip("!.,")
    is_ack = (msg_clean_greeting in ACK_WORDS) and not state.get("confirmation_pending") and not state.get("pending_stage")
    if state.get("confirmation_pending"):
        detected_intent = "BOOK_APPOINTMENT"
        llm_intent_name = "BOOK_APPOINTMENT"
        state["intent"] = "BOOK_APPOINTMENT"
        state["booking_stage"] = conversation_stages.Stage.AWAITING_CONFIRMATION.value
    elif msg_clean_greeting in GREETING_WORDS or is_ack or llm_intent_name in ["GREETING", "THANK_YOU"]:
        detected_intent = "GREETING"
        state["intent"] = "GREETING"
        state["booking_stage"] = None
        state["pending_stage"] = None
        state["previous_question"] = None
        state["dependent_collection_stage"] = None
        state["dependent_collected"] = False
        state["confirmation_pending"] = False
        state["department_name"] = None
        state["doctor_name"] = None
        if is_ack:
            state["is_acknowledgement"] = True
        state["entities"] = {
            "patient_id":      state.get("patient_id"),
            "doctor_id":       None,
            "department_id":   None,
            "appointment_date": None,
            "appointment_time": None,
            "booking_id":      None,
            "reason":          None,
            "symptoms":        []
        }
    elif state.get("intent") == "REGISTER_PATIENT" or (state.get("booking_stage") or "").startswith("REGISTERING_"):
        if not any(w in safe_msg.lower().strip() for w in ["cancel", "exit", "stop", "never mind", "nevermind"]):
            detected_intent = "REGISTER_PATIENT"

    # Persist booking_for & relationship for dependent flow (Fix 4 / Bug 1 fix)
    _subj = llm_route.get("appointment_subject")
    _b_for = llm_route.get("booking_for")
    _rel = llm_route.get("relationship")

    # Use word-boundary regex for dependent keywords so "Wilson" doesn't match "son"
    _dep_kw_pattern = re.compile(r"\b(son|daughter|child|kid|wife|husband|mother|father|mom|dad|baby|infant|sibling|brother|sister)\b", re.IGNORECASE)
    _msg_has_explicit_dep = bool(_dep_kw_pattern.search(safe_msg))

    # Only reset dependent state to SELF when:
    #   a) The router explicitly returned booking_for=SELF or appointment_subject=SELF, AND
    #   b) The current message does NOT contain explicit dependent keywords.
    # This prevents "Wilson M" (contains "son" as substring) from triggering SELF reset
    # while preserving correct reset for true SELF requests like "I have hair loss".
    if (_b_for == "SELF" or _subj == "SELF") and not _msg_has_explicit_dep:
        state["booking_for"] = "SELF"
        state["appointment_for"] = "SELF"
        state["appointment_subject"] = "SELF"
        state["patient_relationship"] = None
        state["dependent_patient_id"] = None
        state["dependent_name"] = None
        state["dependent_collected"] = False
        if state.get("primary_patient_id"):
            state["patient_id"] = state["primary_patient_id"]
            state.setdefault("entities", {})["patient_id"] = state["primary_patient_id"]
    else:
        if _b_for and _b_for != "SELF":
            state["booking_for"] = _b_for
        if _rel:
            state["patient_relationship"] = _rel

    # Fix 6: Pending-stage guard for AWAITING_CANCEL_REASON
    if state.get("pending_stage") == "AWAITING_CANCEL_REASON":
        msg_lwr = message_text.lower().strip()
        cancel_words = ["cancel", "exit", "stop", "back", "never mind", "nevermind"]
        # Short acknowledgment words should NOT be treated as a cancellation reason
        ack_words = {"ok", "okay", "yes", "no", "sure", "fine", "alright", "yep", "nope", "yeah", "k", "👍", "👎"}
        is_ack_only = msg_lwr in ack_words or len(msg_lwr) < 4
        if not any(w in msg_lwr for w in cancel_words) and msg_lwr and not is_ack_only:
            # Capture the user's message as the cancellation reason
            state["entities"]["reason"] = message_text.strip()
            state["pending_stage"] = None
            state["previous_question"] = None

    # Fix 5: Pending-stage guard for AWAITING_BOOKING_ID
    if state.get("pending_stage") == "AWAITING_BOOKING_ID" or state.get("previous_question") == "AWAITING_BOOKING_ID":
        msg_lwr = message_text.lower().strip()
        cancel_words = ["cancel", "exit", "stop", "back", "never mind", "nevermind"]
        if not any(w in msg_lwr for w in cancel_words):
            m_id = re.search(r"\b(APT\d+|\d{4,8})\b", message_text, re.IGNORECASE)
            if m_id:
                state["entities"]["booking_id"] = m_id.group(1).upper()
                state["pending_stage"] = None
                state["previous_question"] = None
            else:
                resp_id = (
                    "That doesn't look like a valid Booking ID (e.g. APT10001).\n\n"
                    "Please provide a valid Booking ID, or reply 'cancel' to exit."
                )
                state["previous_question"] = "AWAITING_BOOKING_ID"
                state["pending_stage"] = "AWAITING_BOOKING_ID"
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp_id, current_lang, "APPOINTMENT_STATUS", state)
                return {
                    "response": resp_id,
                    "intent": "APPOINTMENT_STATUS",
                    "language": current_lang,
                    "interactive_buttons": []
                }

    # Fix 4: Dedicated Dependent/Guardian Booking Sub-Flow
    # IMPORTANT: Only use the current-message LLM/router result for b_for and rel_val.
    # Do NOT fall back to stale state["booking_for"] / state["appointment_for"] /
    # state["patient_relationship"] from previous dependent sessions, as they would
    # incorrectly trigger dependent flow for a fresh SELF booking (Bug 1 fix).
    _llm_b_for = llm_route.get("booking_for") or llm_route.get("appointment_for")
    _llm_rel = llm_route.get("relationship")
    b_for = _llm_b_for  # Only trust what THIS message's router returned
    rel_val = _llm_rel  # Only trust what THIS message's router returned

    dep_keywords = ["brother", "sister", "sibling", "son", "daughter", "child", "kid", "spouse", "wife", "husband", "father", "mother", "family", "relative"]
    has_dep_keyword = any(re.search(rf"\bfor my {kw}\b|\b{kw}\b", safe_msg.lower()) for kw in dep_keywords)
    is_booking_context = detected_intent in ["BOOK_APPOINTMENT", "DEPENDENT_BOOKING"] or llm_intent_name in ["BOOK_APPOINTMENT", "DEPENDENT_BOOKING"]
    is_dep_intent = (is_booking_context or state.get("pending_stage") in ["AWAITING_DEPENDENT_SELECTION", "REGISTERING_NEW_DEPENDENT"]) and (
        b_for in ["CHILD", "DEPENDENT", "FAMILY_MEMBER"] or
        llm_intent_name == "DEPENDENT_BOOKING" or
        has_dep_keyword or
        (rel_val and rel_val.upper() in ["SON", "DAUGHTER", "CHILD", "KID", "SPOUSE", "WIFE", "HUSBAND", "FATHER", "MOTHER", "BROTHER", "SISTER", "SIBLING", "FAMILY_MEMBER", "RELATIVE"])
    )

    # Track primary patient ID (account holder / contact)
    if state.get("patient_id") and not state.get("primary_patient_id"):
        state["primary_patient_id"] = state["patient_id"]
    primary_pat_id = state.get("primary_patient_id") or state.get("patient_id")
    sender_phone = state.get("whatsapp_number") or ""

    # Topic switching guard: if user switched topic to PATIENT_DETAILS, CANCEL, or RESCHEDULE, exit pending dependent stage
    if llm_intent_name in ["PATIENT_DETAILS", "CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT"]:
        state["pending_stage"] = None

    # 1. User responding to Case C clarification prompt
    elif state.get("pending_stage") == "AWAITING_DEPENDENT_SELECTION":
        rel_hint = rel_val or state.get("patient_relationship") or "child"
        res = patient_id_service.resolve_dependent_by_input(primary_pat_id, sender_phone, message_text, relationship_hint=rel_hint)
        if res.get("found") and not res.get("authorized"):
            resp_err = res.get("reason") or "I couldn't find that patient ID under your registered WhatsApp number. Please check the ID and try again."
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp_err, current_lang, "DEPENDENT_BOOKING", state)
            return {
                "response": resp_err,
                "intent": "BOOK_APPOINTMENT",
                "language": current_lang,
                "interactive_buttons": []
            }
        elif res.get("found") and res.get("authorized") and res.get("patient"):
            dep = res["patient"]
            state["dependent_patient_id"] = dep["id"]
            state["patient_id"] = dep["id"]
            state["dependent_name"] = dep["full_name"]
            state["dependent_dob"] = dep.get("date_of_birth")
            state["dependent_gender"] = dep.get("gender")
            state["entities"]["patient_id"] = dep["id"]
            state["entities"]["patient_name_override"] = dep["full_name"]
            state["dependent_collected"] = True
            state["pending_stage"] = None
            state["previous_question"] = None
        else:
            rel_word = (rel_hint or "child").lower()
            resp_clarify = (
                f"I couldn't find a registered {rel_word} matching '{message_text.strip()}'.\n\n"
                f"Please provide the *Patient ID* (e.g. P00125) or exact *Full Name* of your {rel_word}."
            )
            state["pending_stage"] = "AWAITING_DEPENDENT_SELECTION"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp_clarify, current_lang, "DEPENDENT_BOOKING", state)
            return {
                "response": resp_clarify,
                "intent": "BOOK_APPOINTMENT",
                "language": current_lang,
                "interactive_buttons": []
            }

    # 2. User registering details for Case A
    elif state.get("pending_stage") == "REGISTERING_NEW_DEPENDENT":
        msg_l = message_text.lower().strip()
        if msg_l == "btn_self" or "myself" in msg_l or "for me" in msg_l or b_for == "SELF":
            state["pending_stage"] = None
            state["dependent_collection_substage"] = None
            state["booking_for"] = "SELF"
            state["appointment_for"] = "SELF"
            if state.get("primary_patient_id"):
                state["patient_id"] = state["primary_patient_id"]
                state["entities"]["patient_id"] = state["primary_patient_id"]
            state.pop("dependent_patient_id", None)
            state.pop("dependent_name", None)
            state.pop("dependent_dob", None)
            state.pop("dependent_gender", None)
            state["entities"].pop("patient_name_override", None)
            state["entities"].pop("patient_dob", None)

        rel_hint = rel_val or state.get("patient_relationship") or state.get("entities", {}).get("relationship") or "family member"
        dep_name = state.get("dependent_name") or llm_route.get("patient_name")
        dep_dob_raw = state.get("dependent_dob") or llm_route.get("date_of_birth")
        dep_dob = None
        if dep_dob_raw:
            norm_d, _, _ = date_normalizer.parse_and_normalize_date(str(dep_dob_raw))
            if norm_d and date_normalizer.validate_dob(norm_d):
                dep_dob = norm_d
        dep_gender = state.get("dependent_gender") or llm_route.get("gender")

        raw_msg = message_text.strip()
        if not dep_name or not dep_dob or not dep_gender:
            parts = [p.strip() for p in re.split(r'[\n,]+', raw_msg) if p.strip()]
            if len(parts) >= 3:
                if not dep_name:
                    dep_name = parts[0]
                if not dep_dob:
                    norm_d, _, _ = date_normalizer.parse_and_normalize_date(parts[1])
                    if norm_d and date_normalizer.validate_dob(norm_d):
                        dep_dob = norm_d
                if not dep_gender:
                    m_l = parts[2].lower()
                    dep_gender = "Female" if "female" in m_l or "girl" in m_l else ("Male" if "male" in m_l or "boy" in m_l else "Other")

        sub_stage = state.get("dependent_collection_substage")
        if sub_stage == "NAME" and not dep_name:
            dep_name = raw_msg
            state["dependent_name"] = dep_name
        elif sub_stage == "DOB" and not dep_dob:
            is_v, norm_d, _ = date_normalizer.parse_and_normalize_date(raw_msg)
            if is_v and norm_d and date_normalizer.validate_dob(norm_d):
                dep_dob = norm_d
                state["dependent_dob"] = dep_dob
            else:
                dep_dob = None
        elif sub_stage == "GENDER" and not dep_gender:
            m_l = raw_msg.lower()
            dep_gender = "Female" if "female" in m_l or "girl" in m_l else ("Male" if "male" in m_l or "boy" in m_l else "Other")
            state["dependent_gender"] = dep_gender

        if not dep_name:
            state["dependent_collection_substage"] = "NAME"
            resp = f"Please provide your {rel_hint.lower()}'s *full name*."
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "DEPENDENT_BOOKING", state)
            return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": []}
        if not dep_dob:
            state["dependent_collection_substage"] = "DOB"
            resp = f"What is *{dep_name}*'s date of birth? (e.g. 12 May 2015)"
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "DEPENDENT_BOOKING", state)
            return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": []}
        if not dep_gender:
            state["dependent_collection_substage"] = "GENDER"
            resp = f"What is *{dep_name}*'s gender? (Male / Female / Other)"
            state["interactive_buttons"] = [
                {"id": "btn_g_male", "title": "Male"},
                {"id": "btn_g_female", "title": "Female"},
                {"id": "btn_g_other", "title": "Other"}
            ]
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", resp, current_lang, "DEPENDENT_BOOKING", state)
            return {"response": resp, "intent": "BOOK_APPOINTMENT", "language": current_lang, "interactive_buttons": state["interactive_buttons"]}

        dep_id = resolve_or_create_child_patient(
            parent_patient_id=primary_pat_id,
            child_name=dep_name,
            dob_str=dep_dob,
            gender=dep_gender,
            parent_phone=sender_phone,
            parent_whatsapp=sender_phone,
            relationship=rel_hint
        )

        state["dependent_patient_id"] = dep_id
        state["patient_id"] = dep_id
        state["dependent_name"] = dep_name
        state["dependent_dob"] = dep_dob
        state["dependent_gender"] = dep_gender
        state["entities"]["patient_id"] = dep_id
        state["entities"]["patient_name_override"] = dep_name
        state["entities"]["patient_dob"] = dep_dob
        state["entities"]["gender"] = dep_gender
        state["dependent_collected"] = True
        state["pending_stage"] = None
        state["dependent_collection_substage"] = None

        rel_label = rel_hint.lower()
        resp_done = (
            f"✅ *{dep_name}* has been registered successfully as your {rel_label}.\n\n"
            f"What health problem, symptom, or cause would {dep_name} like to consult the doctor for?"
        )
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", resp_done, current_lang, "BOOK_APPOINTMENT", state)
        return {
            "response": resp_done,
            "intent": "BOOK_APPOINTMENT",
            "language": current_lang,
            "interactive_buttons": []
        }

    if is_dep_intent and not state.get("dependent_collected"):
        state["patient_relationship"] = rel_val
        if not state.get("appointment_for") or state.get("appointment_for") == "SELF":
            state["appointment_for"] = b_for if b_for in ["CHILD", "FAMILY_MEMBER"] else ("CHILD" if rel_val.upper() in ["SON", "DAUGHTER", "CHILD", "KID"] else "FAMILY_MEMBER")

        # 3. Initial Dependent Resolution (Cases A, B, C)
        if not state.get("dependent_collected"):
            # Check if name or patient ID was explicitly specified in this initial message
            input_name = llm_route.get("patient_name")
            if input_name or re.search(r"\b(P\d{3,6}|PAT\d{4,6})\b", message_text, re.IGNORECASE):
                target_str = input_name or message_text
                res = patient_id_service.resolve_dependent_by_input(primary_pat_id, sender_phone, target_str, relationship_hint=rel_val)
                if res.get("found") and res.get("authorized") and res.get("patient"):
                    dep = res["patient"]
                    state["dependent_patient_id"] = dep["id"]
                    state["patient_id"] = dep["id"]
                    state["dependent_name"] = dep["full_name"]
                    state["entities"]["patient_id"] = dep["id"]
                    state["entities"]["patient_name_override"] = dep["full_name"]
                    state["dependent_collected"] = True

            if not state.get("dependent_collected"):
                matching_deps = patient_id_service.get_matching_dependents(primary_pat_id, sender_phone, relationship=rel_val)

                # CASE A: 0 MATCHING DEPENDENTS
                if len(matching_deps) == 0:
                    extracted_name = llm_route.get("patient_name")
                    extracted_dob_raw = llm_route.get("date_of_birth")
                    extracted_dob = None
                    if extracted_dob_raw:
                        is_v, norm_d, _ = date_normalizer.parse_and_normalize_date(str(extracted_dob_raw))
                        if is_v and norm_d and date_normalizer.validate_dob(norm_d):
                            extracted_dob = norm_d
                    extracted_gender = llm_route.get("gender")

                    if extracted_name and extracted_dob and extracted_gender:
                        dep_id = resolve_or_create_child_patient(
                            parent_patient_id=primary_pat_id,
                            child_name=extracted_name,
                            dob_str=extracted_dob,
                            gender=extracted_gender,
                            parent_phone=sender_phone,
                            parent_whatsapp=sender_phone,
                            relationship=rel_val
                        )
                        state["dependent_patient_id"] = dep_id
                        state["patient_id"] = dep_id
                        state["dependent_name"] = extracted_name
                        state["dependent_dob"] = extracted_dob
                        state["dependent_gender"] = extracted_gender
                        state["entities"]["patient_id"] = dep_id
                        state["entities"]["patient_name_override"] = extracted_name
                        state["dependent_collected"] = True
                    else:
                        rel_word = rel_val.lower()
                        resp_case_a = (
                            f"I can help you book an appointment for your {rel_word}. "
                            f"I don't have your {rel_word}'s patient details registered yet.\n\n"
                            f"Please provide:\n"
                            f"• Full name\n"
                            f"• Date of birth\n"
                            f"• Gender\n\n"
                            f"Once the details are registered, I can continue with the appointment booking."
                        )
                        state["pending_stage"] = "REGISTERING_NEW_DEPENDENT"
                        if extracted_name: state["dependent_name"] = extracted_name
                        if extracted_dob: state["dependent_dob"] = extracted_dob
                        if extracted_gender: state["dependent_gender"] = extracted_gender

                        state_manager.save_conversation_state(conversation_code, state)
                        log_message_to_db(conversation_code, "AI_AGENT", resp_case_a, current_lang, "DEPENDENT_BOOKING", state)
                        return {
                            "response": resp_case_a,
                            "intent": "BOOK_APPOINTMENT",
                            "language": current_lang,
                            "interactive_buttons": []
                        }

                # CASE B: EXACTLY 1 MATCHING DEPENDENT
                elif len(matching_deps) == 1:
                    dep = matching_deps[0]
                    state["dependent_patient_id"] = dep["id"]
                    state["patient_id"] = dep["id"]
                    state["dependent_name"] = dep["full_name"]
                    state["dependent_dob"] = dep.get("date_of_birth")
                    state["dependent_gender"] = dep.get("gender")
                    state["entities"]["patient_id"] = dep["id"]
                    state["entities"]["patient_name_override"] = dep["full_name"]
                    state["dependent_collected"] = True
                    print(f"[DEPENDENT_RESOLVE] Case B: Auto-resolved single matching dependent {dep['full_name']} ({dep.get('patient_code')})")

                # CASE C: 2 OR MORE MATCHING DEPENDENTS
                else:
                    rel_up = rel_val.upper()
                    if rel_up in ("SON", "BOY"):
                        prompt_msg = (
                            "I found more than one son registered under your WhatsApp number.\n\n"
                            "Please tell me which patient you mean by:\n"
                            "• Patient ID, or\n"
                            "• Full name.\n\n"
                            "For example: P00125 or Ravi Kumar."
                        )
                    elif rel_up in ("DAUGHTER", "GIRL"):
                        prompt_msg = (
                            "I found more than one daughter registered under your WhatsApp number.\n\n"
                            "Please tell me which patient you mean by:\n"
                            "• Patient ID, or\n"
                            "• Full name."
                        )
                    else:
                        prompt_msg = (
                            "I have more than one child registered under your WhatsApp number. "
                            "Which child would you like help with?\n\n"
                            "Please provide the child's name or Patient ID."
                        )
                    state["pending_stage"] = "AWAITING_DEPENDENT_SELECTION"
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", prompt_msg, current_lang, "DEPENDENT_BOOKING", state)
                    return {
                        "response": prompt_msg,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": [
                            {"id": f"btn_dep_{d['id']}", "title": (d.get("full_name") or "Patient")[:20]}
                            for d in matching_deps[:3]
                        ]
                    }

    # ── Handle DOB ambiguity early: ask for clarification before proceeding ──
    if llm_route.get("dob_is_ambiguous") and llm_route.get("date_of_birth"):
        dob_raw = llm_route["date_of_birth"]
        clarify_dob = (
            f"I noticed you provided a date of birth as *{dob_raw}*. "
            f"This could be interpreted as either DD/MM/YYYY or MM/DD/YYYY.\n\n"
            f"Could you please confirm your date of birth in this format: *DD Month YYYY* "
            f"(e.g. *08 September 2004*)?"
        )
        state["previous_question"] = "dob_clarification"
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", clarify_dob, current_lang, "REGISTER_PATIENT", state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": current_lang,
            "intent": "REGISTER_PATIENT",
            "response": clarify_dob,
            "missing_information": ["date_of_birth"],
            "tool_called": None
        }

    # ── Handle LLM-flagged clarification ─────────────────────────────────────
    if llm_route.get("needs_clarification") and llm_route.get("clarification_question"):
        clarify_msg = llm_route["clarification_question"]
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", clarify_msg, current_lang, "UNKNOWN", state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": current_lang,
            "intent": "UNKNOWN",
            "response": clarify_msg,
            "missing_information": llm_route.get("missing_fields", []),
            "tool_called": None
        }

    # ── Confidence gate: below threshold → clarification menu ────────────────
    llm_confidence = llm_route.get("confidence", 1.0)
    if llm_confidence < 0.5 and llm_intent_name not in ("GREETING", "EMERGENCY", "APPOINTMENT_CONFIRMATION"):
        print(f"[INTENT_ROUTE] Low confidence {llm_confidence:.2f} for intent '{llm_intent_name}' — presenting clarification menu")
        clarify_low_conf = (
            "I wasn't quite sure what you need. Here's what I can help with — please tap one:"
        )
        state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", clarify_low_conf, current_lang, "UNKNOWN", state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": current_lang,
            "intent": "UNKNOWN",
            "response": clarify_low_conf,
            "missing_information": [],
            "tool_called": None,
            "interactive_buttons": state["interactive_buttons"],
        }

    # ── Grounding validation — gate all LLM output before touching state ─────
    is_change_doc_req = any(kw in (message_text or "").lower() for kw in ["change doctor", "choose another doctor", "different doctor", "select another doctor", "another doctor", "different dr", "change dr"])
    pending_stage = state.get("booking_stage") or ""
    grounding_result = grounding_validator.validate_extraction(
        user_message=message_text,
        conversation_state=state,
        extracted_fields=llm_route,
        pending_stage=pending_stage,
    )
    cleaned_fields = grounding_result["cleaned"]
    rejected = grounding_result["rejected_fields"]
    if rejected:
        print(f"[GROUNDING] Rejected {len(rejected)} field(s): {rejected}")
    for log_entry in grounding_result["grounding_log"]:
        pass  # Already printed inside grounding_validator

    # ── Check for new symptom / department to clear stale doctor & date ───────
    has_new_symptom_or_dept = bool(cleaned_fields.get("medical_reason") or cleaned_fields.get("department") or cleaned_fields.get("symptoms"))
    if has_new_symptom_or_dept:
        new_dept = cleaned_fields.get("department")
        curr_dept = state.get("department_name") or state.get("selected_department_name")
        dept_changed = bool(new_dept and curr_dept and new_dept.lower() != curr_dept.lower())

        if dept_changed:
            print(f"[DEPT_CHANGE] Department changed from {curr_dept} to {new_dept}. Clearing stale doctor, date, time, slot.")
            state["selected_department_name"] = new_dept
            state["department_name"] = new_dept
            state["selected_doctor_id"] = None
            state["selected_doctor_name"] = None
            state["doctor_name"] = None
            state["selected_slot_id"] = None
            if isinstance(state.get("entities"), dict):
                state["entities"]["doctor_id"] = None
                state["entities"]["appointment_date"] = None
                state["entities"]["appointment_time"] = None
                state["entities"]["selected_slot_id"] = None

        target_dept = cleaned_fields.get("department") or state.get("department_name")
        curr_doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id")
        if curr_doc_id and target_dept:
            doc_info = resolve_doctor_details(int(curr_doc_id))
            if doc_info and doc_info.get("department") and doc_info["department"].lower() != target_dept.lower():
                print(f"[DOCTOR_REVALIDATION] Clearing stale doctor {doc_info['name']} ({doc_info['department']}) for new department {target_dept}")
                state["selected_doctor_id"] = None
                state["selected_doctor_name"] = None
                state["doctor_name"] = None
                state["selected_slot_id"] = None
                if isinstance(state.get("entities"), dict):
                    state["entities"]["doctor_id"] = None

        is_in_active_booking_flow = (
            state.get("conversation_state") in ["TIME_SELECTION", "CONFIRMATION_PENDING", "PREVIEW", "PAYMENT_METHOD_REQUIRED", "MOCK_PAYMENT_PROMPT", "AWAITING_PAYMENT"] or \
            state.get("booking_stage") in ["AWAITING_TIME", "CONFIRMATION_PENDING", "PAYMENT_PENDING"] or \
            state.get("confirmation_pending") is True
        )
        if not cleaned_fields.get("appointment_date") and not is_change_doc_req and not dept_changed:
            if isinstance(state.get("entities"), dict) and not is_in_active_booking_flow:
                state["entities"]["appointment_date"] = None
                state["entities"]["appointment_time"] = None
                state["selected_slot_id"] = None
            elif is_in_active_booking_flow:
                print(f"[DATE_GUARD] Preserving appointment_date={state['entities'].get('appointment_date')} during active booking stage ({state.get('conversation_state')})")

    # ── Merge validated fields into state via conversation_stages ────────────
    previous_intent_for_merge = state.get("intent", "GREETING")
    conversation_stages.merge_state(
        state=state,
        validated_fields=cleaned_fields,
        intent=detected_intent,
        previous_intent=previous_intent_for_merge,
    )

    # ── Restore / Sync Selected Doctor State if active and NOT explicit change doctor ──
    if is_change_doc_req:
        state["selected_doctor_id"] = None
        state["selected_doctor_name"] = None
        if "doctor_id" in state.get("entities", {}):
            state["entities"]["doctor_id"] = None
    elif state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id"):
        curr_doc_id = state.get("selected_doctor_id") or state.get("entities", {}).get("doctor_id")
        if curr_doc_id and state.get("department_name"):
            doc_info = resolve_doctor_details(int(curr_doc_id))
            if doc_info and doc_info.get("department") and doc_info["department"].lower() != state["department_name"].lower():
                print(f"[DOCTOR_REVALIDATION] Clearing stale doctor {doc_info['name']} ({doc_info['department']}) inconsistent with {state['department_name']}")
                state["selected_doctor_id"] = None
                state["selected_doctor_name"] = None
                state["doctor_name"] = None
                if "doctor_id" in state.get("entities", {}):
                    state["entities"]["doctor_id"] = None
            else:
                restore_selected_doctor_state(state)
        else:
            restore_selected_doctor_state(state)

    # ── Apply period-to-time mapping for appointment_time ────────────────────
    PERIOD_TO_TIME = {
        "MORNING":   "09:00",
        "AFTERNOON": "14:00",
        "EVENING":   "18:00",
        "NIGHT":     "20:00",
    }
    raw_time = state["entities"].get("appointment_time")
    if raw_time and str(raw_time).upper() in PERIOD_TO_TIME:
        state["entities"]["appointment_time"] = PERIOD_TO_TIME[str(raw_time).upper()]

    # ── Doctor lookup (if LLM extracted doctor_name that passed grounding) ────
    llm_doc_name = cleaned_fields.get("doctor_name")
    if llm_doc_name and not state.get("confirmation_pending"):
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            clean_q = f"%{llm_doc_name.replace('Dr.', '').replace('Dr', '').strip()}%"
            cur.execute("SELECT id, department_id, display_name FROM doctors WHERE display_name ILIKE %s AND status = 'ACTIVE' LIMIT 1;", (clean_q,))
            d_row = cur.fetchone()
            if d_row:
                state["entities"]["doctor_id"] = d_row[0]
                state["entities"]["department_id"] = d_row[1]
                state["doctor_name"] = d_row[2]
                print(f"[DOCTOR_SELECTION] Doctor explicitly requested by patient: {d_row[2]} (ID: {d_row[0]})")
        finally:
            cur.close()
            conn.close()

    # ── Appointment date validation (past-date guard) ─────────────────────────
    llm_date = state["entities"].get("appointment_date") or llm_route.get("appointment_date")
    if llm_date and not state.get("confirmation_pending"):
        is_valid_d, date_err = response_validator.validate_appointment_date(llm_date)
        if not is_valid_d:
            state["entities"]["appointment_date"] = None
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", date_err, current_lang, detected_intent, state)
            return {
                "success": True,
                "conversation_id": conversation_code,
                "language": current_lang,
                "intent": detected_intent,
                "response": date_err,
                "missing_information": ["appointment_date"],
                "tool_called": None,
                "interactive_buttons": []
            }

    # ── Department: resolve department_id from DB & sync department_name ─────
    if state["entities"].get("department_id"):
        try:
            _conn = db_config.get_db_connection()
            _cur = _conn.cursor()
            try:
                _cur.execute(
                    "SELECT department_name FROM departments WHERE id = %s AND status = 'ACTIVE';",
                    (state["entities"]["department_id"],)
                )
                _row = _cur.fetchone()
                if _row and _row[0]:
                    state["department_name"] = _row[0]
            finally:
                _cur.close()
                _conn.close()
        except Exception as _e:
            print(f"[AGENT] Dept name sync lookup error: {_e}")
    else:
        llm_dept = state.get("department_name")
        if llm_dept:
            try:
                _conn = db_config.get_db_connection()
                _cur = _conn.cursor()
                try:
                    _cur.execute(
                        "SELECT id, department_name FROM departments WHERE LOWER(department_name) = LOWER(%s) AND status = 'ACTIVE';",
                        (llm_dept,)
                    )
                    _row = _cur.fetchone()
                    if _row:
                        state["entities"]["department_id"] = _row[0]
                        state["department_name"] = _row[1]
                finally:
                    _cur.close()
                    _conn.close()
            except Exception as _e:
                print(f"[AGENT] Dept ID lookup error: {_e}")

    # ── Contextual Confirmation Handling (YES/NO) from prior_question ────────
    if (is_affirmative or is_negative) and state.get("previous_question") and not state.get("confirmation_pending") and state["intent"] not in ["REGISTER_PATIENT", "IDENTIFY_PATIENT"]:
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
                "patient_id":      state.get("patient_id"),
                "doctor_id":       None,
                "department_id":   None,
                "appointment_date": None,
                "appointment_time": None,
                "booking_id":      None,
                "reason":          None,
                "symptoms":        []
            }

    # ── Apply intent transition logic ─────────────────────────────────────────
    if detected_intent != "UNKNOWN" and detected_intent != state.get("intent", "GREETING"):
        previous_intent = state.get("intent", "GREETING")
        state["intent"] = detected_intent

        # conversation_stages.merge_state already applies clear rules;
        # keep the existing clear_pairs as a belt-and-suspenders backstop
        clear_pairs = [
            ("BOOK_APPOINTMENT",      "CANCEL_APPOINTMENT"),
            ("BOOK_APPOINTMENT",      "RESCHEDULE_APPOINTMENT"),
            ("CANCEL_APPOINTMENT",    "BOOK_APPOINTMENT"),
            ("CANCEL_APPOINTMENT",    "RESCHEDULE_APPOINTMENT"),
            ("CANCEL_APPOINTMENT",    "DOCTOR_AVAILABILITY"),
            ("RESCHEDULE_APPOINTMENT", "BOOK_APPOINTMENT"),
            ("RESCHEDULE_APPOINTMENT", "CANCEL_APPOINTMENT"),
            ("RESCHEDULE_APPOINTMENT", "DOCTOR_AVAILABILITY"),
            ("REGISTER_PATIENT",      "BOOK_APPOINTMENT"),
            ("IDENTIFY_PATIENT",      "BOOK_APPOINTMENT"),
            ("GREETING",              "BOOK_APPOINTMENT"),   # clears stale cancel reason when starting fresh booking
            ("GREETING",              "DOCTOR_AVAILABILITY"),
        ]
        if (previous_intent, detected_intent) in clear_pairs:
            state["entities"] = {
                "patient_id":      state.get("patient_id"),
                "doctor_id":       None,
                "department_id":   None,
                "appointment_date": None,
                "appointment_time": None,
                "booking_id":      None,
                "reason":          None,
                "symptoms":        []
            }
            state["previous_question"] = None

        # Special case: BOOK_APPOINTMENT → DOCTOR_AVAILABILITY
        # Preserve doctor_id and department_id for context (pronoun resolution, schedule lookup)
        # but clear stale date/time so we don't repeat a failed slot lookup
        elif previous_intent == "BOOK_APPOINTMENT" and detected_intent == "DOCTOR_AVAILABILITY":
            state["entities"]["appointment_date"] = None
            state["entities"]["appointment_time"] = None
            state["entities"]["booking_id"] = None
            state["entities"]["reason"] = None
            state["confirmation_pending"] = False
            state["booking_stage"] = None
            state["conversation_state"] = None
            state["previous_question"] = None

    # ── Supplemental entity extraction (rule-based, non-LLM fields only) ─────
    # The rule-based extractor handles booking_id, patient_code, doctor button-taps.
    # It does NOT override LLM+grounded fields.
    extracted = entity_extractor.extract_entities(message_text)

    new_doc_id  = extracted.get("doctor_id")
    new_dept_id = extracted.get("department_id")
    curr_doc_id  = state["entities"].get("doctor_id")
    curr_dept_id = state["entities"].get("department_id")

    if not state.get("confirmation_pending") and not state.get("change_pending"):
        if (new_doc_id and new_doc_id != curr_doc_id) or (new_dept_id and new_dept_id != curr_dept_id and not new_doc_id):
            state["entities"]["appointment_date"] = None
            state["entities"]["appointment_time"] = None
            state["previous_question"] = None

    # Only merge rule-based fields that the LLM didn't provide (avoid overwrite)
    for k, v in extracted.items():
        if v is not None and not state["entities"].get(k):
            state["entities"][k] = v

    # Associate patient_id dynamically
    if state["entities"].get("patient_id"):
        state["patient_id"] = state["entities"]["patient_id"]

    # Explicit doctor query guard: if a doctor is matched in the message, retain doctor_id and route to DOCTOR_AVAILABILITY
    if (extracted.get("doctor_id") or cleaned_fields.get("doctor_name")) and state["intent"] in ["GREETING", "UNKNOWN", "DOCTOR_AVAILABILITY"]:
        if previous_intent_for_merge != "REGISTER_PATIENT" and not state.get("registration_fields"):
            state["intent"] = "DOCTOR_AVAILABILITY"
            if extracted.get("doctor_id"):
                state["entities"]["doctor_id"] = extracted["doctor_id"]

    # 5. Core Intent Workflows
    intent = state["intent"]
    response_text = ""
    tool_called = None
    missing_info = []

    if state.get("confirmation_pending") and any(w in message_text.lower() for w in ["yes", "yeah", "yep", "sure", "confirm", "btn_confirm_appt", "change", "btn_change_appt", "cancel", "btn_cancel_appt"]):
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

        msg_l = message_text.lower().strip().rstrip("!.,")
        is_ack = state.get("is_acknowledgement") or msg_l in {"ok", "okay", "thanks", "thank you", "thanks!", "great", "fine", "alright", "k", "sure", "noted"}

        if is_ack:
            state["is_acknowledgement"] = False
            response_text = "You're welcome! 😊 How can I help you today?"
            state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
            return {
                "response": response_text,
                "intent": "GREETING",
                "language": current_lang,
                "interactive_buttons": state["interactive_buttons"]
            }

        is_first_time = any(w in msg_l for w in ["first time", "first-time", "btn_first_time", "new patient", "register"]) or msg_l == "1"
        is_existing = any(w in msg_l for w in ["existing patient", "existing", "btn_existing", "registered patient"]) or msg_l == "2"

        if is_first_time:
            state["intent"] = "REGISTER_PATIENT"
            state["patient_type"] = "FIRST_TIME"
            # Incremental registration — start with name only
            if not isinstance(state.get("registration_fields"), dict):
                state["registration_fields"] = {}
            state["booking_stage"] = conversation_stages.Stage.REGISTERING_NAME.value
            response_text = (
                "Welcome! 😊\n\n"
                "Let's create your patient profile step by step.\n\n"
                "What is your *full name*?"
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
                if current_lang == "TAMIL":
                    response_text = f"வணக்கம் {p_name}! 👋\n\nஇன்று உங்களுக்கு நான் எவ்வாறு உதவ வேண்டும்?"
                elif current_lang == "HINDI":
                    response_text = f"नमस्ते {p_name}! 👋\n\nआज मैं आपकी क्या मदद कर सकता हूँ?"
                elif current_lang == "TELUGU":
                    response_text = f"నమస్తే {p_name}! 👋\n\nఈ రోజు మీకు ఎలా సహాయపడాలి?"
                elif current_lang == "MALAYALAM":
                    response_text = f"നമസ്കാരം {p_name}! 👋\n\nഇന്ന് ഞാൻ എങ്ങനെ സഹായിക്കണം?"
                elif current_lang == "KANNADA":
                    response_text = f"ನಮಸ್ಕಾರ {p_name}! 👋\n\nಇಂದು ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?"
                elif current_lang == "URDU":
                    response_text = f"خوش آمدید {p_name}! 👋\n\nآج میں آپ کی کیا مدد کر سکتا ہوں؟"
                else:
                    response_text = f"Welcome back, {p_name}! 👋\n\nHow can I help you today?"
                state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)
            else:
                response_text = "I couldn't find a patient profile associated with this WhatsApp number.\n\nWould you like to register as a new patient?"
                state["interactive_buttons"] = [
                    {"id": "btn_first_time", "title": "Register"},
                    language_service.get_translated_button("btn_cat_doctors", current_lang),
                    language_service.get_translated_button("btn_cat_emergency", current_lang)
                ]
        else:
            p_name_gen = None
            if state.get("patient_id"):
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT first_name FROM patients WHERE id = %s;", (state["patient_id"],))
                    r = cur.fetchone()
                    if r:
                        p_name_gen = r[0]
                finally:
                    cur.close()
                    conn.close()

            if p_name_gen:
                if current_lang == "TAMIL":
                    response_text = f"வணக்கம் {p_name_gen}! 👋\n\nஇன்று உங்களுக்கு நான் எவ்வாறு உதவ வேண்டும்?"
                elif current_lang == "HINDI":
                    response_text = f"नमस्ते {p_name_gen}! 👋\n\nआज मैं आपकी क्या मदद कर सकता हूँ?"
                elif current_lang == "TELUGU":
                    response_text = f"నమస్తే {p_name_gen}! 👋\n\nఈ రోజు మీకు ఎలా సహాయపడాలి?"
                elif current_lang == "MALAYALAM":
                    response_text = f"നമസ്കാരം {p_name_gen}! 👋\n\nഇന്ന് ഞാൻ എങ്ങനെ സഹായിക്കണം?"
                elif current_lang == "KANNADA":
                    response_text = f"ನಮಸ್ಕಾರ {p_name_gen}! 👋\n\nಇಂದು ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?"
                elif current_lang == "URDU":
                    response_text = f"خوش آمدید {p_name_gen}! 👋\n\nآج میں آپ کی کیا مدد کر سکتا ہوں؟"
                else:
                    response_text = f"Welcome back, {p_name_gen}! 👋\n\nHow can I help you today?"
            else:
                if current_lang == "TAMIL":
                    response_text = "👋 மெரிடியன் மருத்துவமனைக்கு உங்களை வரவேற்கிறோம்!\n\nஇன்று உங்களுக்கு நான் எவ்வாறு உதவ வேண்டும்?"
                elif current_lang == "HINDI":
                    response_text = "👋 मेरिडियन अस्पताल में आपका स्वागत है!\n\nआज मैं आपकी क्या मदद कर सकता हूँ?"
                elif current_lang == "TELUGU":
                    response_text = "👋 మెరిడియన్ హాస్పిటల్‌కు స్వాగతం!\n\nఈ రోజు మీకు ఎలా సహాయపడాలి?"
                elif current_lang == "MALAYALAM":
                    response_text = "👋 മെറിഡിയൻ ആശുപത്രിയിലേക്ക് സ്വാഗതം!\n\nഇന്ന് ഞാൻ എങ്ങനെ സഹായിക്കണം?"
                elif current_lang == "KANNADA":
                    response_text = "👋 ಮೆರಿಡಿಯನ್ ಆಸ್ಪತ್ರೆಗೆ ಸುಸ್ವಾಗತ!\n\nಇಂದು ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?"
                elif current_lang == "URDU":
                    response_text = "👋 میریڈین ہسپتال میں آپ کا خیر مقدم ہے!\n\nآج میں آپ کی کیا مدد کر سکتا ہوں؟"
                else:
                    response_text = (
                        "👋 Welcome to Meridian Hospital!\n\n"
                        "How can I help you today?"
                    )
            state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)


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
            state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)
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

        # 0. Check if user typed an edit/change request or tapped Edit button
        is_edit_request = any(re.search(rf"\b{w}\b", msg_raw.lower()) for w in ["edit", "change", "modify", "reset", "start over", "btn_edit_reg"]) or (msg_raw.lower() in ["no", "n"] and state.get("reg_confirmation_pending"))
        if is_edit_request:
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

        # Check confirmation tap or response (Yes/Confirm)
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

        # Extract structured info via LLM and fallback rule parser
        llm_info = llm_service.extract_structured_info(message_text, state, current_lang)
        if llm_info.get("gender"):
            reg_fields["gender"] = llm_info["gender"]
        if llm_info.get("phone"):
            reg_fields["phone"] = llm_info["phone"]
        if llm_info.get("reason"):
            _llm_reason_val = llm_info["reason"]
            # Bug 2 fix: only accept llm reason if it contains a real medical keyword
            # (prevents patient name or DOB from being inferred as the visit reason)
            _med_kw_check = [
                "fever", "cough", "cold", "pain", "ache", "loss", "rash", "itch",
                "vomit", "nausea", "breath", "chest", "head", "consult", "checkup",
                "check-up", "fatigue", "weak", "diarrhea", "bleed", "swelling",
                "throat", "ear", "back", "knee", "joint", "migraine", "seizure",
            ]
            if any(kw in _llm_reason_val.lower() for kw in _med_kw_check):
                reg_fields["reason_for_visit"] = _llm_reason_val

        parts = [p.strip() for p in re.split(r"[,;\n]+", msg_raw) if p.strip()]

        # 1. Flexible Full Name Extraction (preserves existing valid name, validates new name)
        existing_fn = reg_fields.get("first_name")
        p_name_is = re.search(r"^(?:my\s+name\s+is|i\s+am|iam|name[:\s]+)\s+([a-zA-Z\s\.]+)", msg_raw, re.IGNORECASE)
        p_is_name = re.search(r"^([a-zA-Z\s\.]+)\s+(?:is\s+my\s+(?:full\s+)?name)\b", msg_raw, re.IGNORECASE)

        if p_name_is and entity_extractor.is_valid_person_name(p_name_is.group(1).strip()):
            raw_n = p_name_is.group(1).strip()
            n_parts = raw_n.split(None, 1)
            reg_fields["first_name"] = n_parts[0].capitalize()
            reg_fields["last_name"] = n_parts[1].capitalize() if len(n_parts) > 1 else "."
        elif p_is_name and entity_extractor.is_valid_person_name(p_is_name.group(1).strip()):
            raw_n = p_is_name.group(1).strip()
            n_parts = raw_n.split(None, 1)
            reg_fields["first_name"] = n_parts[0].capitalize()
            reg_fields["last_name"] = n_parts[1].capitalize() if len(n_parts) > 1 else "."
        elif not existing_fn or not entity_extractor.is_valid_person_name(existing_fn):
            extracted_fn = llm_info.get("first_name")
            if extracted_fn and entity_extractor.is_valid_person_name(extracted_fn):
                reg_fields["first_name"] = extracted_fn
                reg_fields["last_name"] = llm_info.get("last_name") or reg_fields.get("last_name") or "."
            elif len(parts) >= 1:
                first_part = parts[0]
                if entity_extractor.is_valid_person_name(first_part):
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
        # IMPORTANT: Exclude first_name, last_name, AND the full combined name from
        # reason candidates so the patient's name never leaks into reason_for_visit (Bug 2 fix).
        if not reg_fields.get("reason_for_visit"):
            _fn_low = (reg_fields.get("first_name") or "").lower().strip()
            _ln_low = (reg_fields.get("last_name") or "").lower().strip(". ")
            _full_low = f"{_fn_low} {_ln_low}".strip()
            _name_variants = {v for v in [_fn_low, _ln_low, _full_low] if v}
            reason_candidates = [
                p for p in parts
                if not any(c.isdigit() for c in p)
                and p.lower() not in ["male", "female", "other"]
                and p.lower() not in _name_variants
            ]
            # Only treat a part as a reason if it looks like a symptom/medical reason
            # (i.e., has more than one word OR contains a known medical keyword).
            # Single-word non-medical parts during registration are likely just stray name parts.
            _medical_kw = [
                "fever", "cough", "cold", "pain", "ache", "loss", "rash", "itch",
                "vomit", "nausea", "breath", "chest", "head", "consult", "checkup",
                "check-up", "fatigue", "weak", "diarrhea", "bleed", "swelling"
            ]
            valid_reasons = [
                p for p in reason_candidates
                if len(p.split()) > 1 or any(kw in p.lower() for kw in _medical_kw)
            ]
            if valid_reasons:
                reg_fields["reason_for_visit"] = valid_reasons[-1].capitalize()
            # If no valid reason found, leave it None (do not default to "General Consultation"
            # here — we only set a default at DB-insert time if still missing).

        fn = reg_fields.get("first_name")
        ln = reg_fields.get("last_name") or ""
        dob = reg_fields.get("date_of_birth")
        gen = reg_fields.get("gender")
        ph = reg_fields.get("phone")

        if fn and dob and gen and ph:
            state["registration_fields"] = reg_fields
            state["reg_confirmation_pending"] = True

            try:
                dob_obj = datetime.datetime.strptime(dob, "%Y-%m-%d").date()
                formatted_dob = dob_obj.strftime("%d-%b-%Y")
            except Exception:
                formatted_dob = dob

            full_n = f"{fn} {ln}".strip()
            # Build confirmation message. Only show Reason line if an explicit
            # medical reason was provided (Bug 2 fix: never show patient name as reason).
            _reason_display = reg_fields.get("reason_for_visit")
            reason_line = f"📝 Reason: {_reason_display}\n" if _reason_display else ""
            response_text = (
                f"Thank you! 😊\n\n"
                f"I understood your details as:\n\n"
                f"👤 Name: {full_n}\n"
                f"🎂 Date of Birth: {formatted_dob}\n"
                f"👨 Gender: {gen}\n"
                f"📱 Phone: {ph}\n"
                f"{reason_line}\n"
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
                greeting_name = f", *{fn}*" if fn else ""
                response_text = (
                    f"Got it{greeting_name}! 👍\n\n"
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

    elif intent in ["EMERGENCY", "EMERGENCY_GUIDANCE"]:
        log_agent_action(conversation_code, "EMERGENCY_DETECTED", {"trigger_message": message_text})
        response_text = (
            "🚨 *MERIDIAN HOSPITAL EMERGENCY*\n\n"
            "Meridian Hospital provides 24/7 Emergency & Trauma Care.\n\n"
            "📞 *Emergency Helpline:* 044 6666 9999\n"
            "🏥 *Hospital:* Meridian Hospital\n"
            "📍 *Address:* #46D, Jawaharlal Nehru Road, 200 Feet Ring Road, Chennai – 600 099\n"
            "☎️ *General Enquiries:* 044 6666 9910\n\n"
            "🚑 Ambulance services are available 24/7.\n\n"
            "*Note:* If this is a life-threatening emergency (such as severe chest pain, extreme shortness of breath, heavy bleeding, stroke, or loss of consciousness), seek immediate emergency medical care and call 044 6666 9999 or 112/108 right away. Do not wait for an appointment for an emergency."
        )
        state["interactive_buttons"] = [
            {"id": "btn_hosp_info", "title": "Hospital Information"},
            {"id": "btn_book_appt", "title": "Book Appointment"}
        ]
        
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

        contact_card = language_service.get_talk_to_staff_contact_response(current_lang)
        response_text = contact_card + "\n\nStatus: 🟡 OPEN\nA hospital staff member will review your request."
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
        med_reason = llm_route.get("medical_reason") or state.get("appointment_reason") or (extracted.get("symptoms")[0] if extracted.get("symptoms") else None)
        if med_reason:
            state["entities"]["reason"] = med_reason
            state["appointment_reason"] = med_reason
        elif state["entities"].get("reason") is None and not any(w in message_text.lower() for w in ["dr.", "dr ", "pediatrics", "cardiology", "dermatology", "general medicine", "orthopedics"]):
            state["entities"]["reason"] = message_text.strip()
            state["appointment_reason"] = message_text.strip()


    elif intent == "DOCTOR_AVAILABILITY":
        state["interactive_buttons"] = []
        msg_lower = (message_text or "").lower()
        is_change_doc_req = any(kw in msg_lower for kw in ["change doctor", "another doctor", "different doctor", "switch doctor", "show another doctor"])

        if is_change_doc_req:
            state["selected_doctor_id"] = None
            state["selected_doctor_name"] = None
            state["entities"]["doctor_id"] = None
            sel_doc_id = None
        else:
            sel_doc_id = extracted.get("doctor_id") or state.get("selected_doctor_id") or state["entities"].get("doctor_id")
            if sel_doc_id:
                sync_selected_doctor_state(state, sel_doc_id)
        
        # Clear stale/historical date (e.g. birth dates) from appointment_date
        appt_date = state["entities"].get("appointment_date")
        if appt_date:
            try:
                today_yr = llm_intent_router._get_ist_now().year
                p_yr = int(appt_date.split("-")[0])
                if p_yr < today_yr:
                    state["entities"]["appointment_date"] = None
            except Exception:
                pass

        dept_id = state["entities"].get("department_id")
        doc_id = state["entities"].get("doctor_id")
        appt_date = state["entities"].get("appointment_date")

        # If doctor_id is present:
        #   - No date supplied → show the doctor's weekly working schedule (explicit availability request)
        #   - Date supplied    → show available slots for that specific date
        if doc_id:
            sync_selected_doctor_state(state, doc_id)
            doc_info = resolve_doctor_details(doc_id)
            dept_id = doc_info["department_id"]
            state["entities"]["department_id"] = dept_id

            if not appt_date:
                # User asked "show doctor availability" / "when is he available?" without a date.
                # Show the doctor's configured weekly schedule from doctor_schedules table.
                response_text = format_doctor_working_schedule_response(doc_id)
                state["previous_question"] = "avail_ask_date"
                state["intent"] = "DOCTOR_AVAILABILITY"
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, "DOCTOR_AVAILABILITY", state)
                return validate_and_enforce_selected_doctor(conversation_code, state, {
                    "response": response_text,
                    "intent": "DOCTOR_AVAILABILITY",
                    "language": current_lang,
                    "interactive_buttons": []
                })

            res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
            slots_list = res_slots.get("slots", []) if res_slots.get("success") else []

            # Try to extract a time from the message — if valid, go straight to confirmation
            time_in_msg = entity_extractor.parse_natural_time(message_text.lower())
            if time_in_msg and time_in_msg in slots_list:
                # Time is valid and available — store it and show confirmation prompt
                state["entities"]["appointment_time"] = time_in_msg
                state["intent"] = "BOOK_APPOINTMENT"
                state["confirmation_pending"] = True
                pat_id = state.get("dependent_patient_id") or state.get("patient_id")
                pat_name = state["entities"].get("patient_name_override") or state.get("dependent_name")
                db_dob = None
                db_gender = None
                db_pat_code = state.get("dependent_patient_code") or state.get("patient_code")
                if pat_id:
                    _conn = db_config.get_db_connection()
                    _cur = _conn.cursor()
                    try:
                        _cur.execute("SELECT first_name, last_name, date_of_birth, gender, patient_code FROM patients WHERE id = %s;", (pat_id,))
                        p_row = _cur.fetchone()
                        if p_row:
                            if not pat_name:
                                pat_name = f"{p_row[0]} {p_row[1] or ''}".strip()
                            db_dob = p_row[2]
                            db_gender = p_row[3]
                            if len(p_row) > 4 and p_row[4]:
                                db_pat_code = p_row[4]
                    finally:
                        _cur.close()
                        _conn.close()
                pat_code_val = db_pat_code or state.get("patient_code") or ""
                pat_code_line = f"Patient ID: {pat_code_val}\n" if pat_code_val else ""
                reason = state["entities"].get("reason") or "General Consultation"
                pat_dob_raw = state["entities"].get("patient_dob") or state.get("dependent_dob") or db_dob
                pat_dob_val = format_safe_dob(pat_dob_raw)
                pat_gender_raw = state["entities"].get("gender") or state.get("dependent_gender") or db_gender
                pat_gender_val = format_safe_gender(pat_gender_raw)

                rel_val_card = state.get("patient_relationship") or state.get("entities", {}).get("relationship")
                rel_line = f"Relationship: {str(rel_val_card).capitalize()}\n" if (rel_val_card and state.get("appointment_for") != "SELF") else ""

                response_text = (
                    f"Please confirm your appointment:\n\n"
                    f"Patient: {pat_name or 'Patient'}\n"
                    f"{pat_code_line}"
                    f"DOB: {pat_dob_val}\n"
                    f"{rel_line}"
                    f"Gender: {pat_gender_val}\n"
                    f"Reason: {reason}\n"
                    f"Department: {doc_info['department']}\n"
                    f"Doctor: {doc_info['name']}\n"
                    f"Date: {appt_date}\n"
                    f"Time: {format_time_12h(time_in_msg)}"
                )
                state["interactive_buttons"] = [
                    {"id": "btn_confirm_appt", "title": "Confirm Appointment"},
                    {"id": "btn_change_appt", "title": "Change Details"},
                    {"id": "btn_cancel_appt", "title": "Cancel"}
                ]
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, "BOOK_APPOINTMENT", state)
                return validate_and_enforce_selected_doctor(conversation_code, state, {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": state["interactive_buttons"]
                })
            else:
                # Show doctor profile + available slots
                details_parts = [
                    f"👨‍⚕️ *{doc_info['name']}*",
                    f"🏥 *Department*: {doc_info['department']}"
                ]
                if doc_info.get("qualification"):
                    details_parts.append(f"🎓 *Qualification*: {doc_info['qualification']}")
                if doc_info.get("experience_years"):
                    details_parts.append(f"💼 *Experience*: {doc_info['experience_years']} years")
                if doc_info.get("consultation_fee"):
                    fee_val = doc_info['consultation_fee']
                    details_parts.append(f"💵 *Consultation Fee*: ₹{fee_val:.0f}" if fee_val.is_integer() else f"💵 *Consultation Fee*: ₹{fee_val:.2f}")

                details_header = "\n".join(details_parts)

                if slots_list:
                    res_p = build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, slots_list, details_header, current_lang, intent)
                    if time_in_msg:
                        res_p["response"] = f"*{doc_info['name']}* is not available at *{format_time_12h(time_in_msg)}* on *{appt_date}*.\n\n" + res_p["response"]
                    return validate_and_enforce_selected_doctor(conversation_code, state, res_p)
                else:
                    res_p = build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, failed_date=appt_date, current_lang=current_lang, intent=intent)
                    return validate_and_enforce_selected_doctor(conversation_code, state, res_p)

        # Step 1: No department/doctor known yet — ask about symptom or department
        elif not dept_id and not doc_id:
            state["previous_question"] = "avail_ask_dept_or_symptom"
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT department_name FROM departments WHERE status='ACTIVE' AND department_name NOT LIKE 'DummyDept%%' ORDER BY id;")
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
            state["missing_information"] = missing_info
            state_manager.save_conversation_state(conversation_code, state)
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

        # Step 2: Department known, but no date yet — ask for the date
        elif not appt_date:
            dept_label = ""
            if dept_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT department_name FROM departments WHERE id = %s AND status = 'ACTIVE';", (dept_id,))
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
            state["missing_information"] = missing_info
            state_manager.save_conversation_state(conversation_code, state)
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

        # Step 3: Both department and date known — show available slots per doctor
        else:
            tool_called = "get_doctor_availability"
            response_text = format_doctor_availability_response(dept_id, appt_date, conversation_code)
            state["previous_question"] = None
            state["missing_information"] = missing_info
            state_manager.save_conversation_state(conversation_code, state)
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

    elif intent in ["PATIENT_DETAILS", "PATIENT_PROFILE", "PATIENT_ID"]:
        # Reset stale appointment state when entering PATIENT_DETAILS
        state["entities"]["doctor_id"] = None
        state["entities"]["department_id"] = None
        state["entities"]["appointment_date"] = None
        state["entities"]["appointment_time"] = None
        state["entities"]["reason"] = None
        state["confirmation_pending"] = False
        state["previous_question"] = None

        # Get the actual WhatsApp number from conversation
        w_num = conversation_code.replace("WA_", "").split("_")[0]
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
            r = cur.fetchone()
            if r and r[0]:
                w_num = r[0]
        finally:
            cur.close()
            conn.close()

        # Primary parent patient
        id_res = patient_id_service.identify_patient_by_phone(w_num)
        p_dict = id_res.get("patient")
        parent_id = p_dict.get("id") if p_dict else state.get("primary_patient_id") or state.get("patient_id")

        rel_val = llm_route.get("relationship") or state.get("patient_relationship") or ""
        msg_lwr = message_text.lower()
        is_dep_query = (
            llm_route.get("query_for_dependent") or
            extracted.get("query_for_dependent") or
            any(w in msg_lwr for w in ["son", "daughter", "child", "kid", "wife", "husband", "mother", "father", "dependent"])
        )

        # Check if user is responding to a profile dependent clarification prompt or providing Patient ID
        if state.get("pending_stage") == "AWAITING_PROFILE_DEPENDENT_CLARIFICATION" or re.search(r"\b(P\d{3,6}|PAT\d{4,6})\b", message_text, re.IGNORECASE):
            res = patient_id_service.resolve_dependent_by_input(parent_id, w_num, message_text, relationship_hint=rel_val)
            if res.get("found") and not res.get("authorized"):
                resp_err = res.get("reason") or "I couldn't find that patient ID under your registered WhatsApp number. Please check the ID and try again."
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp_err, current_lang, intent, state)
                return {"success": True, "conversation_id": conversation_code, "language": current_lang, "intent": intent, "response": resp_err, "missing_information": [], "tool_called": None}
            elif res.get("found") and res.get("authorized") and res.get("patient"):
                dep = res["patient"]
                dep_name = dep.get("full_name") or f"{dep.get('first_name', '')} {dep.get('last_name', '')}".strip()
                dep_code = dep.get("patient_code") or f"P{dep.get('id')}"
                dep_dob = dep.get("date_of_birth") or "Not recorded"
                dep_gender = dep.get("gender") or "Not recorded"
                state["pending_stage"] = None
                resp_dep = (
                    f"Your dependent's registered details are:\n\n"
                    f"📋 *Registered Patient Details*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *Name:* {dep_name}\n"
                    f"🆔 *Patient ID:* `{dep_code}`\n"
                    f"📅 *Date of Birth:* {dep_dob}\n"
                    f"🚻 *Gender:* {dep_gender}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"How else can I assist you today?"
                )
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", resp_dep, current_lang, intent, state)
                return {"success": True, "conversation_id": conversation_code, "language": current_lang, "intent": intent, "response": resp_dep, "missing_information": [], "tool_called": "get_dependent_details"}

        # Dependent Profile Details Query
        if is_dep_query and parent_id:
            matching_deps = patient_id_service.get_matching_dependents(parent_id, w_num, relationship=rel_val)
            rel_word = (rel_val or "child").lower()

            if len(matching_deps) == 0:
                response_text = (
                    f"I couldn't find any registered {rel_word} linked to your account.\n\n"
                    f"If you'd like to book an appointment for a family member, I can register them during the booking process."
                )
            elif len(matching_deps) == 1:
                # Directly show details for that single matching dependent
                dep = matching_deps[0]
                dep_name = dep.get("full_name") or f"{dep.get('first_name', '')} {dep.get('last_name', '')}".strip()
                dep_code = dep.get("patient_code") or f"P{dep.get('id')}"
                dep_dob = dep.get("date_of_birth") or "Not recorded"
                dep_gender = dep.get("gender") or "Not recorded"
                response_text = (
                    f"Your {rel_word}'s registered details are:\n\n"
                    f"📋 *Registered Patient Details*\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👤 *Name:* {dep_name}\n"
                    f"🆔 *Patient ID:* `{dep_code}`\n"
                    f"📅 *Date of Birth:* {dep_dob}\n"
                    f"🚻 *Gender:* {dep_gender}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"How else can I assist you today?"
                )
            else:
                # 2 or more matching dependents
                extracted_hint = llm_route.get("dependent_name_hint") or llm_route.get("patient_name")
                if extracted_hint:
                    res = patient_id_service.resolve_dependent_by_input(parent_id, w_num, extracted_hint, relationship_hint=rel_val)
                    if res.get("found") and res.get("authorized") and res.get("patient"):
                        dep = res["patient"]
                        dep_name = dep.get("full_name") or f"{dep.get('first_name', '')} {dep.get('last_name', '')}".strip()
                        dep_code = dep.get("patient_code") or f"P{dep.get('id')}"
                        dep_dob = dep.get("date_of_birth") or "Not recorded"
                        dep_gender = dep.get("gender") or "Not recorded"
                        response_text = (
                            f"Your {rel_word}'s registered details are:\n\n"
                            f"📋 *Registered Patient Details*\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"👤 *Name:* {dep_name}\n"
                            f"🆔 *Patient ID:* `{dep_code}`\n"
                            f"📅 *Date of Birth:* {dep_dob}\n"
                            f"🚻 *Gender:* {dep_gender}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"How else can I assist you today?"
                        )
                        state_manager.save_conversation_state(conversation_code, state)
                        log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                        return {"success": True, "conversation_id": conversation_code, "language": current_lang, "intent": intent, "response": response_text, "missing_information": [], "tool_called": "get_dependent_details"}

                rel_up = rel_val.upper()
                if rel_up in ("SON", "BOY"):
                    response_text = (
                        "I have more than one son registered under your WhatsApp number.\n\n"
                        "Please provide the Patient ID or name of the son whose details you want to see."
                    )
                elif rel_up in ("DAUGHTER", "GIRL"):
                    response_text = (
                        "I have more than one daughter registered under your WhatsApp number.\n\n"
                        "Please provide the Patient ID or name of the daughter whose details you want to see."
                    )
                else:
                    response_text = (
                        "I have more than one child registered under your WhatsApp number. "
                        "Please provide the child's name or Patient ID."
                    )
                state["pending_stage"] = "AWAITING_PROFILE_DEPENDENT_CLARIFICATION"

            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
            return {
                "success": True,
                "conversation_id": conversation_code,
                "language": current_lang,
                "intent": intent,
                "response": response_text,
                "missing_information": [],
                "tool_called": "get_dependent_details"
            }

        # Self profile details
        else:
            response_text = patient_id_service.format_patient_details_response(p_dict or state.get("patient_info"), w_num, current_lang)
            state["interactive_buttons"] = [
                {"id": "btn_book_appt", "title": "Book Appointment"},
                {"id": "btn_doctor_avail", "title": "Doctor Availability"}
            ]
            state_manager.save_conversation_state(conversation_code, state)
            log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
            res_payload = {
                "success": True,
                "conversation_id": conversation_code,
                "language": current_lang,
                "intent": intent,
                "response": response_text,
                "missing_information": [],
                "tool_called": "get_patient_details",
                "interactive_buttons": state.get("interactive_buttons", [])
            }
            return response_validator.validate_pre_dispatch(state, res_payload)


    elif intent == "CLARIFICATION_REQUIRED":
        response_text = (
            "I'm happy to help! Could you please clarify what you would like to do?\n\n"
            "1. 📅 *Book an appointment*\n"
            "2. 👨‍⚕️ *Check doctor availability*\n"
            "3. 👤 *View registered patient profile*\n"
            "4. 🔄 *Reschedule or cancel an appointment*\n"
            "5. 🏥 *Get hospital information*"
        )
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": current_lang,
            "intent": intent,
            "response": response_text,
            "missing_information": [],
            "tool_called": "ask_clarification",
            "interactive_buttons": [
                {"id": "btn_book_appt", "title": "Book Appointment"},
                {"id": "btn_doc_avail", "title": "Doctor Availability"},
                {"id": "btn_view_profile", "title": "My Profile"}
            ]
        }

    elif intent == "PATIENT_ID":
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        p_code = None
        p_name = None
        try:
            phone_digits = "".join(c for c in str(conversation_code) if c.isdigit())
            if len(phone_digits) >= 10:
                short_phone = phone_digits[-10:]
                cur.execute(
                    "SELECT patient_code, first_name, last_name FROM patients WHERE phone_number LIKE %s ORDER BY id DESC LIMIT 1;",
                    (f"%{short_phone}%",)
                )
                row = cur.fetchone()
                if row:
                    p_code = row[0]
                    p_name = f"{row[1]} {row[2] or ''}".strip()
        finally:
            cur.close()
            conn.close()

        if p_code:
            response_text = (
                f"🏥 *Meridian Hospital Patient Desk*\n\n"
                f"Your Patient ID is: *{p_code}* ({p_name}).\n\n"
                f"How can I help you today?"
            )
        else:
            response_text = (
                "I couldn't find a registered patient profile associated with your phone number.\n\n"
                "Would you like to register as a new patient?"
            )
        state_manager.save_conversation_state(conversation_code, state)
        log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
        return {
            "success": True,
            "conversation_id": conversation_code,
            "language": current_lang,
            "intent": intent,
            "response": response_text,
            "missing_information": [],
            "tool_called": "get_patient_id",
            "interactive_buttons": []
        }

    elif intent in ["APPOINTMENT_STATUS", "MY_APPOINTMENTS"]:
        # 1. Reset any stale booking stage & active booking flags
        state["booking_stage"] = None
        state["previous_question"] = None
        state["confirmation_pending"] = False
        state["department_name"] = None
        state["doctor_name"] = None
        state["active_workflow"] = "APPOINTMENT_LOOKUP"

        # 2. Get contact patient ID & WhatsApp number
        # The phone-based re-identification (earlier in this function) always sets
        # state["patient_id"] to the non-dependent primary patient. Anchor it here
        # as primary_patient_id so it won't be confused with any dependent's ID.
        if state.get("patient_id") and not state.get("primary_patient_id"):
            state["primary_patient_id"] = state["patient_id"]
        contact_pat_id = state.get("primary_patient_id") or state.get("patient_id")
        w_num = None
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
            r = cur.fetchone()
            if r and r[0]:
                w_num = r[0]
        finally:
            cur.close()
            conn.close()


        # 3. Check for specific Booking ID query (e.g. APT12345)
        booking_id = state.get("entities", {}).get("booking_id")
        if not booking_id:
            m_id = re.search(r"\b(APT-?\d{3,8})\b", message_text, re.IGNORECASE)
            if m_id:
                booking_id = m_id.group(1).upper()
                state["entities"]["booking_id"] = booking_id

        if booking_id:
            tool_called = "get_appointment_status"
            appt_info = fetch_appointment_details_by_booking_id(booking_id)
            if appt_info:
                response_text = format_single_appointment_card(appt_info)
            else:
                response_text = f"Could not find an appointment with Booking ID *{booking_id}*. Please check the ID and try again."
            state["pending_stage"] = None
            state["previous_question"] = None
            state["active_workflow"] = None

        else:
            tool_called = "get_patient_appointments"
            # Extract subject, relationship, patient_reference, time_filter
            # IMPORTANT: Always prefer the CURRENT message (llm_route) over potentially
            # stale state values. State may still hold "patient_relationship = SON" from a
            # previous dependent booking, which would incorrectly return the son's appointments
            # when the parent asks "show my appointments".
            appt_subj = llm_route.get("appointment_subject") or state.get("appointment_subject")

            # rel_val: only inherit stale state relationship if appt_subj is explicitly DEPENDENT
            # (i.e., the current LLM routing says this is a dependent query). Never let old
            # booking state leak into a SELF appointment query.
            llm_rel = llm_route.get("relationship")
            if appt_subj == "SELF":
                # Explicit SELF query — ignore any stale patient_relationship from state
                rel_val = llm_rel
            else:
                rel_val = llm_rel or (state.get("patient_relationship") if appt_subj == "DEPENDENT" else None)

            pat_ref = llm_route.get("patient_reference") or state.get("patient_reference")
            time_filter = llm_route.get("time_filter") or state.get("time_filter") or "ALL"

            # Check if user is replying to pending dependent selection question
            is_replying_dep_selection = (state.get("pending_stage") == "AWAITING_DEPENDENT_SELECTION_APPT")

            target_patient_id = None
            target_name = "your"
            is_dependent_query = False

            # Check if explicit Patient ID or Dependent Name is mentioned in message or reply
            explicit_id_match = re.search(r"\b(P\d{3,6}|PAT\d{4,6}|TST\d{3,6})\b", message_text, re.IGNORECASE)
            if pat_ref or is_replying_dep_selection or explicit_id_match:
                input_to_resolve = pat_ref or (explicit_id_match.group(1) if explicit_id_match else message_text)
                res = patient_id_service.resolve_dependent_by_input(contact_pat_id, w_num, input_to_resolve)
                if not res.get("found") or not res.get("authorized"):
                    response_text = "I couldn't find that patient ID under your registered WhatsApp number. Please check the ID and try again."
                    state["pending_stage"] = None
                    state["previous_question"] = None
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "success": True,
                        "conversation_id": conversation_code,
                        "language": current_lang,
                        "intent": intent,
                        "response": response_text,
                        "interactive_buttons": []
                    }
                else:
                    target_patient_id = res["patient"]["id"]
                    target_name = res["patient"].get("first_name") or res["patient"].get("full_name") or "dependent"
                    is_dependent_query = True
                    state["pending_stage"] = None

            # If not resolved by patient_ref, check relationship (SON, DAUGHTER, CHILD etc.)
            # Only enter this branch when the query is explicitly about a dependent:
            #   - LLM said appt_subj == "DEPENDENT", OR
            #   - relationship keyword is in the CURRENT message text (not stale state)
            # NEVER enter this branch when appt_subj == "SELF".
            msg_has_dependent_keyword = bool(re.search(r"\b(son|daughter|child|kid|boy|girl)\b", message_text, re.IGNORECASE))
            is_explicit_self = (appt_subj == "SELF") or (not msg_has_dependent_keyword and not rel_val and appt_subj != "DEPENDENT")
            if not target_patient_id and not is_explicit_self and (appt_subj == "DEPENDENT" or rel_val or msg_has_dependent_keyword):
                if not rel_val:
                    if re.search(r"\b(son|boy)\b", message_text, re.IGNORECASE):
                        rel_val = "SON"
                    elif re.search(r"\b(daughter|girl)\b", message_text, re.IGNORECASE):
                        rel_val = "DAUGHTER"
                    elif re.search(r"\b(child|kid)\b", message_text, re.IGNORECASE):
                        rel_val = "CHILD"
                    else:
                        rel_val = "DEPENDENT"

                rel_display_map = {
                    "SON": "son",
                    "DAUGHTER": "daughter",
                    "CHILD": "child",
                    "KID": "child",
                    "DEPENDENT": "dependent"
                }
                rel_disp = rel_display_map.get(rel_val.upper(), "child")

                matching_deps = patient_id_service.get_matching_dependents(contact_pat_id, w_num, rel_val)

                if len(matching_deps) == 1:
                    # CASE A: Exactly 1 matching dependent -> auto resolve!
                    target_patient_id = matching_deps[0]["id"]
                    target_name = matching_deps[0].get("first_name") or matching_deps[0].get("full_name") or rel_disp
                    is_dependent_query = True
                elif len(matching_deps) > 1:
                    # CASE B: Multiple matching dependents -> ask clarification!
                    dep_names_str = ", ".join([f"*{d['first_name']}* ({d['patient_code']})" for d in matching_deps])
                    response_text = (
                        f"I have more than one {rel_disp} registered under your WhatsApp number ({dep_names_str}).\n\n"
                        f"Which {rel_disp}'s appointments would you like to see?\n\n"
                        f"Please provide the child's name or Patient ID."
                    )
                    state["pending_stage"] = "AWAITING_DEPENDENT_SELECTION_APPT"
                    state["previous_question"] = "AWAITING_DEPENDENT_SELECTION_APPT"
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "success": True,
                        "conversation_id": conversation_code,
                        "language": current_lang,
                        "intent": intent,
                        "response": response_text,
                        "interactive_buttons": []
                    }
                else:
                    # CASE C: 0 matching dependents
                    response_text = (
                        f"I don't have a {rel_disp} registered under your WhatsApp number.\n\n"
                        f"If you want to check another patient's appointments, please provide the patient's name or Patient ID."
                    )
                    state["pending_stage"] = None
                    state["previous_question"] = None
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "success": True,
                        "conversation_id": conversation_code,
                        "language": current_lang,
                        "intent": intent,
                        "response": response_text,
                        "interactive_buttons": []
                    }

            # Default: Self Query (parent's patient ID)
            if not target_patient_id:
                target_patient_id = contact_pat_id
                target_name = "your"
                is_dependent_query = False

            # Retrieve appointments from database for target_patient_id
            pat_appts = fetch_patient_appointments(patient_id=target_patient_id, whatsapp_number=None, time_filter=time_filter)

            if pat_appts:
                cards = [format_single_appointment_card(a) for a in pat_appts]
                if is_dependent_query:
                    header = f"Here is {target_name}'s upcoming appointment:\n\n" if len(cards) == 1 else f"Here are {target_name}'s appointments:\n\n"
                else:
                    header = "Here is your upcoming appointment:\n\n" if len(cards) == 1 else "Here are your appointments:\n\n"
                response_text = header + "\n\n---\n\n".join(cards)
                state["interactive_buttons"] = [
                    {"id": "btn_book_appt", "title": "Book Appointment"},
                    {"id": "btn_hosp_info", "title": "Hospital Information"}
                ]
            else:
                if is_dependent_query:
                    response_text = f"{target_name} doesn't have any appointments currently."
                else:
                    response_text = "You don't have any appointments currently."
                state["interactive_buttons"] = [
                    {"id": "btn_book_appt", "title": "Book Appointment"}
                ]

            state["pending_stage"] = None
            state["previous_question"] = None
            state["active_workflow"] = None

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
                state["payment_status"] = None
                if True:
                    doc_id = state["entities"].get("doctor_id")
                    doc_info = resolve_doctor_details(doc_id) if doc_id else {"name": "Doctor", "department": "General Medicine", "consultation_fee": 800}
                    fee_val = doc_info.get("consultation_fee") or 800
                    fee_str = f"₹{fee_val:.0f}" if (isinstance(fee_val, float) and fee_val.is_integer()) or isinstance(fee_val, int) else f"₹{fee_val}"
                    appt_date = state["entities"].get("appointment_date")
                    appt_time = state["entities"].get("appointment_time")

                    # Revalidate slot before asking for payment
                    if doc_id and appt_date and appt_time:
                        res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                        avail = res_slots.get("slots", []) if res_slots.get("success") else []
                        if appt_time not in avail:
                            state["entities"]["appointment_time"] = None
                            state["confirmation_pending"] = False
                            if avail:
                                res_p = build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, avail, current_lang=current_lang, intent=intent)
                                res_p["response"] = f"Sorry, *{format_time_12h(appt_time)}* is no longer available on *{appt_date}*.\n\n" + res_p["response"]
                                return res_p

                    # Create PENDING payment entry in PostgreSQL payments table
                    pat_id = state.get("dependent_patient_id") or state.get("patient_id")
                    pay_ref = f"PAY{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
                    pay_db_id = None
                    if pat_id:
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute("""
                                INSERT INTO payments (payment_reference, patient_id, amount, currency, payment_method, payment_status, created_at, updated_at)
                                VALUES (%s, %s, %s, 'INR', 'GPAY', 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                RETURNING id;
                            """, (pay_ref, pat_id, fee_val))
                            pay_db_id = cur.fetchone()[0]
                            conn.commit()
                        except Exception as e:
                            print(f"[PAYMENT_DB_ERR] Error creating pending payment: {e}")
                            conn.rollback()
                        finally:
                            cur.close()
                            conn.close()

                    state["payment_id"] = pay_db_id
                    state["payment_reference"] = pay_ref
                    state["payment_amount"] = fee_val
                    state["conversation_state"] = "PAYMENT_METHOD_REQUIRED"
                    state["confirmation_pending"] = False

                    pay_method_buttons = [
                        {"id": "btn_pay_gpay", "title": "Google Pay"},
                        {"id": "btn_pay_phonepe", "title": "PhonePe"},
                        {"id": "btn_pay_paytm", "title": "Paytm"},
                        {"id": "btn_pay_upi", "title": "UPI"},
                        {"id": "btn_pay_netbanking", "title": "Net Banking"}
                    ]
                    response_text = (
                        f"💳 *Payment Required*\n\n"
                        f"Please complete the consultation payment to confirm your appointment.\n\n"
                        f"Doctor: {doc_info['name']}\n"
                        f"Department: {doc_info['department']}\n"
                        f"Date: {appt_date}\n"
                        f"Time: {format_time_12h(appt_time)}\n"
                        f"Consultation Fee: {fee_str}\n\n"
                        f"Please select your payment method:"
                    )
                    state["interactive_buttons"] = pay_method_buttons
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": pay_method_buttons
                    }

                pat_id = state["patient_id"]
                doc_id = state["entities"]["doctor_id"]
                dept_id = state["entities"]["department_id"]

                # Guard: if doctor_id is missing at confirmation, we cannot proceed
                if not doc_id:
                    state["confirmation_pending"] = False
                    state["entities"]["appointment_time"] = None
                    state["entities"]["appointment_date"] = None
                    response_text = (
                        "I'm sorry, I lost track of your doctor selection. "
                        "Let's start over.\n\nWhich doctor or department would you like to book with?"
                    )
                    state["conversation_state"] = "DOCTOR_SELECTION_REQUIRED"
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

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

                    if not appt_date:
                        print(f"[BOOKING_GUARD] STOP: appointment_date is missing from state before calling booking service!")
                        state["confirmation_pending"] = False
                        response_text = language_service.translate_response("ASK_DATE", current_lang) if current_lang != "ENGLISH" else "Appointment date is required. Which date would you like to book?"
                        state["conversation_state"] = "AWAITING_DATE"
                        state_manager.save_conversation_state(conversation_code, state)
                        log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                        return {
                            "response": response_text,
                            "intent": "BOOK_APPOINTMENT",
                            "language": current_lang,
                            "interactive_buttons": []
                        }

                    print(f"[CONFIRMATION_PAYLOAD_VALIDATED] patient_id={booking_pat_id}, doctor_id={doc_id}, department_id={dept_id}, appointment_date={appt_date}, appointment_time={appt_time}, selected_slot_id={state.get('selected_slot_id') or state['entities'].get('selected_slot_id')}, reason={reason}")

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
                        display_pat_code = state.get("dependent_patient_code") or state.get("patient_code")
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute("SELECT first_name, last_name, patient_code FROM patients WHERE id = %s;", (booking_pat_id,))
                            p_row = cur.fetchone()
                            if p_row:
                                if not display_pat:
                                    display_pat = f"{p_row[0]} {p_row[1] or ''}".strip()
                                if len(p_row) > 2 and p_row[2]:
                                    display_pat_code = p_row[2]
                        finally:
                            cur.close()
                            conn.close()

                        pat_code_line = f"Patient ID: {display_pat_code}\n" if display_pat_code else ""
                        email_note = f"\n\nA confirmation email has also been sent to {state['entities'].get('email')}." if state["entities"].get("email") else "\n\nA confirmation email has also been sent."

                        response_text = (
                            f"✅ *Appointment confirmed!*\n\n"
                            f"Patient: {display_pat or 'Patient'}\n"
                            f"{pat_code_line}"
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
                response_text = "What detail would you like to change?"
                state["interactive_buttons"] = [
                    {"id": "btn_chg_name",   "title": "Patient Name"},
                    {"id": "btn_chg_doctor", "title": "Change Doctor"},
                    {"id": "btn_chg_date",   "title": "Change Date"},
                    {"id": "btn_chg_time",   "title": "Change Time"},
                    {"id": "btn_chg_reason", "title": "Change Reason"},
                ]
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
                    # Do not auto-select a doctor. Doctor must be selected by patient.
                    doc_id_ctx = None

                if doc_id_ctx:
                    doc_info = resolve_doctor_details(doc_id_ctx)
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id_ctx, appt_date_ctx)
                    slots_list = res_slots.get("slots", []) if res_slots.get("success") else []
                    if slots_list:
                        return build_verified_slot_selection_response(conversation_code, state, doc_id_ctx, doc_info, appt_date_ctx, slots_list, current_lang=current_lang, intent=intent)
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
            has_symptom_or_dept_or_doc = bool(
                state.get("entities", {}).get("doctor_id") or
                state.get("entities", {}).get("department_id") or
                # Only count 'reason' as a valid symptom if we're already in a booking stage
                # (not a leftover reason from a cancel flow)
                (state.get("entities", {}).get("reason") and state.get("booking_stage") not in [None, "AWAITING_SYMPTOM"]) or
                state.get("entities", {}).get("symptoms")
            )

            # Generic booking intent phrases — always treated as a fresh start (never as a symptom)
            GENERIC_BOOKING_PHRASES = {
                "book appointment", "btn_book_appt", "book an appointment",
                "i want to book an appointment", "appointment booking", "book appt", "book",
                "new appointment", "new appoinment", "book new appointment", "book new appoinment",
                "new appt", "book a new appointment", "book another appointment",
                "i want an appointment", "i need an appointment", "make appointment",
                "schedule appointment", "set appointment"
            }
            is_explicit_booking_request = msg_clean in GENERIC_BOOKING_PHRASES or any(
                phrase in msg_clean for phrase in ["new appointment", "book new", "book another", "new appt"]
            )

            is_mid_booking_flow = state.get("booking_stage") in ["AWAITING_DATE", "AWAITING_DOCTOR", "AWAITING_TIME", "AWAITING_CONFIRMATION", "AWAITING_DEPARTMENT_CONFIRM"] or state.get("conversation_state") in ["DOCTOR_SELECTION_REQUIRED", "TIME_SELECTION", "DATE_REQUIRED", "CONFIRMATION"]
            is_generic_booking_start = (
                (is_explicit_booking_request or not has_symptom_or_dept_or_doc) and
                not state.get("confirmation_pending") and not is_mid_booking_flow
            ) or is_explicit_booking_request  # always override mid-flow if explicitly requesting new booking

            if is_generic_booking_start:
                # Clear stale entities for fresh booking (including any leftover cancel reason)
                state["entities"]["doctor_id"] = None
                state["entities"]["department_id"] = None
                state["entities"]["reason"] = None
                state["entities"]["symptoms"] = []
                state["entities"]["appointment_date"] = None
                state["entities"]["appointment_time"] = None
                state["entities"]["booking_id"] = None
                state["conversation_state"] = "BOOKING_REASON_REQUIRED"
                state["booking_stage"] = "AWAITING_SYMPTOM"
                state["previous_question"] = "ask_booking_symptom"
                
                response_text = "Sure! I can help you book an appointment. What health problem, symptom, or reason would you like to consult the doctor for?"
                state["interactive_buttons"] = []
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                print("[CONVERSATION_STATE] Fresh appointment flow initiated. State: BOOKING_REASON_REQUIRED")
                return {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": []
                }

            # 1b. Check for ambiguous symptom (Requirement 10 & Scenarios 12/13)
            msg_lower_check = message_text.lower().strip()
            specific_body_part_or_dept = any(b in msg_lower_check for b in [
                "chest", "heart", "knee", "joint", "back", "bone", "skin", "hair", "ear", "throat",
                "nose", "eye", "stomach", "fever", "cough", "cold", "acne", "rash", "pregnant", "pregnancy"
            ])
            is_ambiguous_symptom = (
                msg_lower_check in ["i have pain", "pain", "my pain", "i don't feel well", "not feeling well", "don't feel well", "unwell", "ill", "having pain", "feel sick"] or
                (any(phrase in msg_lower_check for phrase in ["i have pain", "don't feel well", "not feeling well", "feel unwell"]) and not specific_body_part_or_dept)
            ) and not state["entities"].get("doctor_id")

            if is_ambiguous_symptom:
                if "pain" in msg_lower_check:
                    response_text = "Could you tell me where you are experiencing the pain, such as chest, stomach, back, knee, or somewhere else?"
                else:
                    response_text = "Could you please describe what symptom or health issue you are experiencing (e.g., fever, cold, skin rash, joint pain)?"
                state["conversation_state"] = "BOOKING_REASON_REQUIRED"
                state["previous_question"] = "ask_booking_symptom"
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                print("[CONVERSATION_STATE] Ambiguous symptom prompt sent. State: BOOKING_REASON_REQUIRED")
                return {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": []
                }

            # 2. Handle patient response to symptom/cause prompt
            if (state.get("booking_stage") == "AWAITING_SYMPTOM" or state.get("previous_question") == "ask_booking_symptom") and detected_intent != "GREETING":
                # Guard: if user is re-stating a booking intent (not a real symptom), re-ask for symptom
                _generic_booking_kws = [
                    "new appointment", "new appoinment", "book appointment", "book new",
                    "book another", "new appt", "appointment", "book appt", "make appointment"
                ]
                if any(kw in msg_clean for kw in _generic_booking_kws):
                    response_text = "Sure! What health problem, symptom, or reason would you like to consult the doctor for?"
                    state["booking_stage"] = "AWAITING_SYMPTOM"
                    state["previous_question"] = "ask_booking_symptom"
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

                state["booking_stage"] = None
                state["previous_question"] = None
                symptom_input = message_text.strip()

                # Map symptom to department
                dept_name = entity_extractor.map_symptom_to_department_name(symptom_input)
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("SELECT id, department_name FROM departments WHERE department_name ILIKE %s AND status = 'ACTIVE';", (dept_name,))
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
                    
                    print(f"[DATABASE_LOOKUP] Querying active doctors for department_id={dept_id}")
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
                state["department_name"] = resolved_dept_name
                state["entities"]["reason"] = symptom_input.capitalize()
                # DO NOT auto-assign doctor_id! doctor_id remains None until selected by patient.
                state["entities"]["doctor_id"] = None
                
                target_date = state["entities"].get("appointment_date")

                # Build doctor listing & slots
                spec_singular, spec_plural = get_specialist_titles(resolved_dept_name)
                doctor_listings = []
                buttons = []
                for doc_id, doc_name, doc_spec in docs:
                    doc_name_clean = doc_name.replace("Dr. Dr.", "Dr.").strip() if doc_name else "Doctor"
                    if target_date:
                        res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, target_date)
                        slots = res_slots.get("slots", []) if res_slots.get("success") else []
                        slots_str = ", ".join([format_time_12h(s) for s in slots[:6]]) if slots else "No remaining slots on this date"
                        doctor_listings.append(f"• *{doc_name_clean}* — {resolved_dept_name} (Available slots on {target_date}:\n  {slots_str})")
                    else:
                        info = get_doctor_working_info_and_next_slots(doc_id, llm_intent_router._get_ist_date_str())
                        doctor_listings.append(f"• *{doc_name_clean}* — {resolved_dept_name} ({info['working_days_str']})")
                    buttons.append({"id": f"btn_doc_{doc_id}", "title": doc_name_clean[:20]})

                doc_text_block = "\n".join(doctor_listings)
                
                response_text = (
                    f"For *{symptom_input.capitalize()}*, you should consult our *\"{resolved_dept_name}\"* department.\n\n"
                    f"Here are the available {spec_plural}:\n"
                    f"{doc_text_block}\n\n"
                    f"Which doctor would you like to consult?"
                )
                
                state["conversation_state"] = "DOCTOR_SELECTION_REQUIRED"
                state["interactive_buttons"] = buttons[:3]
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                print(f"[DOCTOR_SELECTION] Displayed {len(docs)} doctor options for {resolved_dept_name}. State: DOCTOR_SELECTION_REQUIRED")
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
                    if doc_id and appt_date:
                        res_alt = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                        slots_list = res_alt.get("slots", []) if res_alt.get("success") else []
                        if slots_list:
                            doc_info = resolve_doctor_details(doc_id)
                            return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, slots_list, current_lang=current_lang, intent=intent)
                    response_text = "Please enter your updated preferred appointment time:"
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
                        return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, slots_list, current_lang=current_lang, intent="BOOK_APPOINTMENT")
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

            # Do NOT auto-resolve doctor from department. Doctor selection must be explicitly requested or selected by patient.


            # Date Normalization & Ambiguity Check (STRICT: Reject past dates and birth dates)
            # FIX: Guard against secondary LLM extraction overwriting a confirmed appointment_date
            existing_confirmed_date = state["entities"].get("appointment_date")
            date_candidate = llm_info.get("appointment_date") or rule_ext.get("appointment_date")
            if existing_confirmed_date and date_candidate:
                # Only allow overwrite if the user explicitly mentioned a date in THIS message
                user_explicitly_mentioned_date = bool(
                    entity_extractor.parse_natural_date(message_text.lower())
                    or re.search(r"\b\d{4}-\d{2}-\d{2}\b", message_text)
                    or re.search(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b", message_text)
                )
                if not user_explicitly_mentioned_date:
                    print(f"[DATE_GUARD] Preserving confirmed date={existing_confirmed_date}, "
                          f"ignoring secondary extraction date={date_candidate}")
                    date_candidate = None

            if not date_candidate and (state.get("previous_question") in ["avail_ask_date", "DATE_REQUIRED"] or state.get("conversation_state") == "DATE_REQUIRED"):
                if not any(g in message_text.lower() for g in ["male", "female"]) and not re.search(r"\b(fever|cough|pain|fall|rash|loss)\b", message_text.lower()):
                    date_candidate = message_text.strip()

            if date_candidate:
                is_valid, norm_date, date_err = date_normalizer.validate_appointment_date(date_candidate)
                if not is_valid and date_err and "already passed" in date_err:
                    print(f"[DATE_VALIDATION]\nToday: {date_normalizer.get_current_kolkata_date()}\nRequested: {norm_date or date_candidate}\nStatus: REJECTED_PAST_DATE")
                    state["entities"]["appointment_date"] = None
                    response_text = date_err
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }
                elif is_valid and norm_date:
                    print(f"[DATE_VALIDATION]\nToday: {date_normalizer.get_current_kolkata_date()}\nRequested: {norm_date}\nStatus: PASSED_FUTURE_DATE")
                    state["entities"]["appointment_date"] = norm_date

            # Time parsing (Rule extractor + LLM)
            user_explicitly_mentioned_time = bool(
                re.search(r"\b(1[0-2]|0?[1-9])(?::[0-5]\d)?\s*(?:am|pm)\b", message_text.lower())
                or re.search(r"\b([01]?\d|2[0-3]):[0-5]\d\b", message_text)
                or re.search(r"\b(morning|afternoon|evening|night|noon|midnight)\b", message_text.lower())
                or re.search(r"\bat\s+(1[0-2]|0?[1-9])\b", message_text.lower())
            )
            parsed_time = entity_extractor.parse_natural_time(message_text.lower()) if user_explicitly_mentioned_time else None
            if parsed_time:
                state["entities"]["appointment_time"] = parsed_time
            elif user_explicitly_mentioned_time and llm_info.get("appointment_time"):
                state["entities"]["appointment_time"] = llm_info["appointment_time"]
            elif not user_explicitly_mentioned_time and not (btn_id and btn_id.startswith("btn_slot_")):
                if not state.get("confirmation_pending") and state.get("conversation_state") != "CONFIRMATION_REQUIRED":
                    state["entities"]["appointment_time"] = None
            print(f"[DATE_STATE_DEBUG] After time parsing: doctor_id={state['entities'].get('doctor_id')}, "
                  f"appointment_date={state['entities'].get('appointment_date')}, "
                  f"appointment_time={state['entities'].get('appointment_time')}, "
                  f"stage={state.get('conversation_state')}")

            # Immediate validation of appointment_time against doctor's available slots (Fix 2)
            c_doc_id = state["entities"].get("doctor_id")
            c_appt_date = state["entities"].get("appointment_date")
            c_appt_time = state["entities"].get("appointment_time")
            if c_doc_id and c_appt_date and c_appt_time:
                res_slots = tool_registry.tool_get_available_slots(conversation_code, c_doc_id, c_appt_date)
                avail_slots = res_slots.get("slots", []) if res_slots.get("success") else []
                if c_appt_time not in avail_slots:
                    doc_info = resolve_doctor_details(c_doc_id)
                    state["entities"]["appointment_time"] = None
                    if avail_slots:
                        res_p = build_verified_slot_selection_response(conversation_code, state, c_doc_id, doc_info, c_appt_date, avail_slots, current_lang=current_lang, intent=intent)
                        res_p["response"] = f"*{doc_info['name']}* is not available at *{format_time_12h(c_appt_time)}* on *{c_appt_date}*.\n\n" + res_p["response"]
                        return res_p
                    else:
                        return build_verified_date_selection_response(conversation_code, state, c_doc_id, doc_info, failed_date=c_appt_date, current_lang=current_lang, intent=intent)
            
            # Sanitize and preserve reason entity
            curr_reason = state["entities"].get("reason")
            is_doc_or_dept = any(kw in (message_text or "").lower() for kw in ["dr.", "dr ", "doctor", "pediatrics", "cardiology", "dermatology", "orthopedics", "general medicine", "neurology"])
            is_demographic = any(kw in (message_text or "").lower() for kw in ["male", "female", "years", "old", "dob", "born"])
            if not curr_reason and not is_demographic and not is_doc_or_dept:
                med_reason_val = llm_route.get("medical_reason") or (extracted.get("symptoms")[0] if extracted.get("symptoms") else None)
                if med_reason_val:
                    state["entities"]["reason"] = med_reason_val
                elif not entity_extractor.is_date_or_time_expression(message_text) and not entity_extractor.is_command_phrase(message_text):
                    state["entities"]["reason"] = message_text.strip()

            pat_id = state["patient_id"]
            doc_id = state["entities"]["doctor_id"]
            dept_id = state["entities"]["department_id"]
            appt_date = state["entities"]["appointment_date"]
            appt_time = state["entities"]["appointment_time"]
            reason = state.setdefault("entities", {}).get("reason") or "General Consultation"
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

            # --- Stage 1: Doctor Selection Required ---
            if dept_id and not doc_id:
                conn = db_config.get_db_connection()
                cur = conn.cursor()
                docs = []
                dept_name = None
                try:
                    cur.execute("SELECT department_name FROM departments WHERE id = %s AND status = 'ACTIVE';", (dept_id,))
                    d_row = cur.fetchone()
                    if d_row and d_row[0]:
                        dept_name = d_row[0]
                        state["department_name"] = dept_name

                    if not dept_name:
                        dept_name = state.get("department_name") or "General Medicine"

                    print(f"[DATABASE_LOOKUP] Querying active doctors for department_id={dept_id}")
                    cur.execute("SELECT id, display_name, specialization FROM doctors WHERE department_id = %s AND status = 'ACTIVE' ORDER BY id;", (dept_id,))
                    docs = cur.fetchall()
                finally:
                    cur.close()
                    conn.close()

                if not docs:
                    response_text = f"I can help you with {dept_name}. There are currently no active doctors available in {dept_name}."
                    state_manager.save_conversation_state(conversation_code, state)
                    log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                    return {
                        "response": response_text,
                        "intent": "BOOK_APPOINTMENT",
                        "language": current_lang,
                        "interactive_buttons": []
                    }

                spec_singular, spec_plural = get_specialist_titles(dept_name)
                target_date = state["entities"].get("appointment_date")
                doctor_listings = []
                buttons = []
                for d_id, d_name, d_spec in docs:
                    d_name_clean = d_name.replace("Dr. Dr.", "Dr.").strip() if d_name else "Doctor"
                    if target_date:
                        res_slots = tool_registry.tool_get_available_slots(conversation_code, d_id, target_date)
                        slots = res_slots.get("slots", []) if res_slots.get("success") else []
                        slots_str = ", ".join([format_time_12h(s) for s in slots[:4]]) if slots else "No remaining slots"
                        doctor_listings.append(f"• *{d_name_clean}* (Available slots on {target_date}:\n  {slots_str})")
                    else:
                        info = get_doctor_working_info_and_next_slots(d_id, llm_intent_router._get_ist_date_str())
                        doctor_listings.append(f"• *{d_name_clean}* ({info['working_days_str']})")
                    buttons.append({"id": f"btn_doc_{d_id}", "title": d_name_clean[:20]})

                doc_text_block = "\n".join(doctor_listings)
                reason_val = state["entities"].get("reason") or message_text.strip()

                response_text = (
                    f"For *{reason_val.capitalize()}*, you should consult our *\"{dept_name}\"* department.\n\n"
                    f"Here are the available {spec_plural}:\n"
                    f"{doc_text_block}\n\n"
                    f"Which doctor would you like to consult?"
                )
                state["conversation_state"] = "DOCTOR_SELECTION_REQUIRED"
                state["interactive_buttons"] = buttons[:3]
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                print(f"[DOCTOR_SELECTION] Doctor selection prompt sent for department {dept_name}. State: DOCTOR_SELECTION_REQUIRED")
                return {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": state["interactive_buttons"]
                }

            # --- Stage 2: Doctor Selected (Show Doctor Details & Available Slots) ---
            if doc_id and not appt_date:
                doc_info = resolve_doctor_details(doc_id)
                # FIX: Instead of silently defaulting to "tomorrow", show verified available dates
                # This prevents arbitrary date assignment when the upstream bug cleared a confirmed date
                print(f"[DATE_STATE_DEBUG] Stage 2: doc_id={doc_id}, no appt_date — showing verified available dates")
                return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, current_lang=current_lang, intent=intent)

            # --- Stage 3: Preferred Time Required ---
            if doc_id and appt_date and not appt_time:
                doc_info = resolve_doctor_details(doc_id)
                res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                available_slots = res_slots.get("slots", []) if res_slots.get("success") else []

                if available_slots:
                    return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, available_slots, current_lang=current_lang, intent=intent)
                else:
                    return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, failed_date=appt_date, current_lang=current_lang, intent=intent)

            else:
                # Hard business validation: Never allow confirmation unless appt_time is explicitly set!
                if not appt_time:
                    doc_info = resolve_doctor_details(doc_id)
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                    available_slots = res_slots.get("slots", []) if res_slots.get("success") else []
                    if available_slots:
                        return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, available_slots, current_lang=current_lang, intent=intent)
                    else:
                        return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, failed_date=appt_date, current_lang=current_lang, intent=intent)
                # All required fields present -> check real DB slot availability
                tool_called = "get_available_slots"
                res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                doc_info = resolve_doctor_details(doc_id)

                available_slots = res_slots.get("slots", []) if res_slots.get("success") else []
                if appt_time in available_slots:
                    state["confirmation_pending"] = True
                    pat_id = state.get("dependent_patient_id") or state.get("patient_id")
                    pat_name = state["entities"].get("patient_name_override") or state.get("dependent_name")
                    db_dob = None
                    db_gender = None
                    db_pat_code = state.get("dependent_patient_code") or state.get("patient_code")
                    if pat_id:
                        conn = db_config.get_db_connection()
                        cur = conn.cursor()
                        try:
                            cur.execute("SELECT first_name, last_name, date_of_birth, gender, patient_code FROM patients WHERE id = %s;", (pat_id,))
                            p_row = cur.fetchone()
                            if p_row:
                                if not pat_name:
                                    pat_name = f"{p_row[0]} {p_row[1] or ''}".strip()
                                db_dob = p_row[2]
                                db_gender = p_row[3]
                                if len(p_row) > 4 and p_row[4]:
                                    db_pat_code = p_row[4]
                        finally:
                            cur.close()
                            conn.close()

                    pat_code_val = db_pat_code or state.get("patient_code") or ""
                    pat_code_line = f"Patient ID: {pat_code_val}\n" if pat_code_val else ""
                    pat_dob_raw = state["entities"].get("patient_dob") or state.get("dependent_dob") or state.get("registration_fields", {}).get("date_of_birth") or db_dob
                    pat_dob_val = format_safe_dob(pat_dob_raw)
                    pat_gender_raw = state["entities"].get("gender") or state.get("dependent_gender") or state.get("registration_fields", {}).get("gender") or db_gender
                    pat_gender_val = format_safe_gender(pat_gender_raw)

                    rel_val_card = state.get("patient_relationship") or state.get("entities", {}).get("relationship")
                    rel_line = f"Relationship: {str(rel_val_card).capitalize()}\n" if (rel_val_card and state.get("appointment_for") != "SELF") else ""

                    response_text = (
                        f"Please confirm your appointment:\n\n"
                        f"Patient: {pat_name}\n"
                        f"{pat_code_line}"
                        f"DOB: {pat_dob_val}\n"
                        f"{rel_line}"
                        f"Gender: {pat_gender_val}\n"
                        f"Reason: {reason}\n"
                        f"Department: {doc_info['department']}\n"
                        f"Doctor: {doc_info['name']}\n"
                        f"Date: {appt_date}\n"
                        f"Time: {format_time_12h(appt_time)}"
                    )
                    state["interactive_buttons"] = [
                        {"id": "btn_confirm_appt", "title": "Confirm Appointment"},
                        {"id": "btn_change_appt", "title": "Change Details"},
                        {"id": "btn_cancel_appt", "title": "Cancel"}
                    ]
                else:
                    state["entities"]["appointment_time"] = None
                    state["confirmation_pending"] = False
                    if available_slots:
                        res_p = build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, available_slots, current_lang=current_lang, intent=intent)
                        res_p["response"] = f"*{doc_info['name']}* is not available at *{format_time_12h(appt_time)}* on *{appt_date}*. That slot is already booked.\n\n" + res_p["response"]
                        return res_p
                    else:
                        info = get_doctor_working_info_and_next_slots(doc_id, appt_date)
                        state["entities"]["appointment_date"] = None
                        if info.get("next_date"):
                            state["entities"]["appointment_date"] = info["next_date"]
                            return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, info["next_date"], info["next_slots"], details_header=f"*{doc_info['name']}* is not scheduled to work on *{appt_date}* ({info['day_name']}).\n🏥 Working days: *{info['working_days_str']}*.", current_lang=current_lang, intent=intent)
                        else:
                            return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, failed_date=appt_date, current_lang=current_lang, intent=intent)

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
                            cur.execute("SELECT department_name FROM departments WHERE id=%s AND status='ACTIVE';", (dept_id_now,))
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
        state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)
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
        if state["entities"].get("reason") is None and not any(kw in message_text.lower() for kw in ["dr.", "dr ", "doctor", "pediatrics", "cardiology", "dermatology"]):
            state["entities"]["reason"] = message_text.strip()


    elif intent == "DOCTOR_AVAILABILITY":
        state["interactive_buttons"] = []
        dept_id = state["entities"].get("department_id")
        doc_id = state["entities"].get("doctor_id")
        appt_date = state["entities"].get("appointment_date")

        # Fast path: doctor known, no date → show weekly working schedule
        if doc_id and not appt_date:
            response_text = format_doctor_working_schedule_response(doc_id)
            state["previous_question"] = "avail_ask_date"
            state["intent"] = "DOCTOR_AVAILABILITY"
            missing_info = []

        # Step 1: No department/doctor known yet — ask about symptom or department
        elif not dept_id and not doc_id:
            state["previous_question"] = "avail_ask_dept_or_symptom"
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("SELECT department_name FROM departments WHERE status='ACTIVE' AND department_name NOT LIKE 'DummyDept%%' ORDER BY id;")
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

        # Step 2: Department/doctor known, but no date yet — ask for the date
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
                    cur.execute("SELECT department_name FROM departments WHERE id = %s AND status = 'ACTIVE';", (dept_id,))
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
            if doc_id:
                tool_called = "get_available_slots"
                res = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                doc_info = resolve_doctor_details(doc_id)
                if res["success"] and res["slots"]:
                    return build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, res["slots"], current_lang=current_lang, intent="BOOK_APPOINTMENT")
                else:
                    response_text = language_service.translate_response(
                        "NO_SLOTS", current_lang,
                        date=appt_date,
                        doctor=doc_info["name"]
                    )
            else:
                response_text = "Please select a doctor to see available time slots."
                missing_info.append("doctor")
            missing_info.append("appointment_time")
        elif not pat_id:
            if re.search(r"\b(p\d+)\b", message_text.lower()):
                response_text = language_service.translate_response("PATIENT_NOT_FOUND", current_lang)
            else:
                response_text = language_service.translate_response("ASK_PATIENT_CODE", current_lang)
            missing_info.append("patient_id")
        else:
            # We have all slots. Verify payment status before booking!
            state["payment_status"] = None
            if True:
                doc_info = resolve_doctor_details(doc_id) if doc_id else {"name": "Doctor", "department": "General Medicine", "consultation_fee": 800}
                fee_val = doc_info.get("consultation_fee") or 800
                fee_str = f"₹{fee_val:.0f}" if (isinstance(fee_val, float) and fee_val.is_integer()) or isinstance(fee_val, int) else f"₹{fee_val}"

                # Revalidate slot before asking for payment
                if doc_id and appt_date and appt_time:
                    res_slots = tool_registry.tool_get_available_slots(conversation_code, doc_id, appt_date)
                    avail = res_slots.get("slots", []) if res_slots.get("success") else []
                    if appt_time not in avail:
                        state["entities"]["appointment_time"] = None
                        state["confirmation_pending"] = False
                        if avail:
                            res_p = build_verified_slot_selection_response(conversation_code, state, doc_id, doc_info, appt_date, avail, current_lang=current_lang, intent=intent)
                            res_p["response"] = f"Sorry, *{format_time_12h(appt_time)}* is no longer available on *{appt_date}*.\n\n" + res_p["response"]
                            return res_p
                        else:
                            return build_verified_date_selection_response(conversation_code, state, doc_id, doc_info, failed_date=appt_date, current_lang=current_lang, intent=intent)

                # Create PENDING payment entry in PostgreSQL payments table
                pay_ref = f"PAY{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
                pay_db_id = None
                if pat_id:
                    conn = db_config.get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("""
                            INSERT INTO payments (payment_reference, patient_id, amount, currency, payment_method, payment_status, created_at, updated_at)
                            VALUES (%s, %s, %s, 'INR', 'GPAY', 'PENDING', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            RETURNING id;
                        """, (pay_ref, pat_id, fee_val))
                        pay_db_id = cur.fetchone()[0]
                        conn.commit()
                    except Exception as e:
                        print(f"[PAYMENT_DB_ERR] Error creating pending payment: {e}")
                        conn.rollback()
                    finally:
                        cur.close()
                        conn.close()

                state["payment_id"] = pay_db_id
                state["payment_reference"] = pay_ref
                state["payment_amount"] = fee_val
                state["conversation_state"] = "PAYMENT_METHOD_REQUIRED"
                state["confirmation_pending"] = False

                pay_method_buttons = [
                    {"id": "btn_pay_gpay", "title": "Google Pay"},
                    {"id": "btn_pay_phonepe", "title": "PhonePe"},
                    {"id": "btn_pay_paytm", "title": "Paytm"},
                    {"id": "btn_pay_upi", "title": "UPI"},
                    {"id": "btn_pay_netbanking", "title": "Net Banking"}
                ]
                response_text = (
                    f"💳 *Payment Required*\n\n"
                    f"Please complete the consultation payment to confirm your appointment.\n\n"
                    f"Doctor: {doc_info['name']}\n"
                    f"Department: {doc_info['department']}\n"
                    f"Date: {appt_date}\n"
                    f"Time: {format_time_12h(appt_time)}\n"
                    f"Consultation Fee: {fee_str}\n\n"
                    f"Please select your payment method:"
                )
                state["interactive_buttons"] = pay_method_buttons
                state_manager.save_conversation_state(conversation_code, state)
                log_message_to_db(conversation_code, "AI_AGENT", response_text, current_lang, intent, state)
                return {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": pay_method_buttons
                }

            if not doc_id:
                response_text = "Doctor selection is required before completing the booking."
                return {
                    "response": response_text,
                    "intent": "BOOK_APPOINTMENT",
                    "language": current_lang,
                    "interactive_buttons": []
                }
                
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
            state["pending_stage"] = "AWAITING_BOOKING_ID"
            state["previous_question"] = "AWAITING_BOOKING_ID"
        elif not reason and not any(w in message_text.lower() for w in ["confirm", "cancel appointment", "btn_confirm_cancel"]):
            response_text = f"Please provide the reason for cancelling appointment {booking_id}:"
            missing_info.append("reason")
            state["pending_stage"] = "AWAITING_CANCEL_REASON"
            state["previous_question"] = "AWAITING_CANCEL_REASON"
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
                state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)
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
                # Reset cancel state so subsequent messages don't retry the same failed cancellation
                state["entities"]["booking_id"] = None
                state["entities"]["reason"] = None
                state["pending_stage"] = None
                state["previous_question"] = None
                state["booking_stage"] = None
                state["conversation_state"] = None
                state["intent"] = "GREETING"
                state["interactive_buttons"] = language_service.get_main_menu_buttons(current_lang)

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

    elif intent == "PATIENT_REPORTS":
        return process_agent_message(conversation_code, patient_code, "btn_my_reports", current_lang, "btn_my_reports")

    elif intent == "PRE_ADMISSION":
        log_agent_action(conversation_code, "PRE_ADMISSION_REQUESTED")
        msg_lower = message_text.lower().strip()

        conn = db_config.get_db_connection()
        cur = conn.cursor()
        pa_record = None
        target_patient_id = state.get("patient_id")
        wa_number = None

        try:
            cur.execute("SELECT patient_id, whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
            c_row = cur.fetchone()
            if c_row:
                if not target_patient_id and c_row[0]:
                    target_patient_id = c_row[0]
                wa_number = c_row[1]

            if not target_patient_id and wa_number:
                cur.execute("SELECT id FROM patients WHERE whatsapp_number = %s OR phone = %s ORDER BY id DESC LIMIT 1;", (wa_number, wa_number))
                p_row = cur.fetchone()
                if p_row:
                    target_patient_id = p_row[0]
                    state["patient_id"] = target_patient_id

            cur.execute("""
                SELECT pa.id, pa.pre_admission_code, pa.expected_admission_date, pa.expected_checkin_time,
                       pa.admission_type, pa.status, pa.pending_documents, pa.submitted_documents,
                       pa.instructions, pa.remarks, d.display_name as doctor_name, dept.department_name,
                       (p.first_name || ' ' || COALESCE(p.last_name, '')) as patient_name
                FROM pre_admissions pa
                JOIN patients p ON pa.patient_id = p.id
                JOIN doctors d ON pa.doctor_id = d.id
                JOIN departments dept ON pa.department_id = dept.id
                WHERE (pa.patient_id = %s OR (%s IS NOT NULL AND (p.phone = %s OR p.whatsapp_number = %s)))
                  AND pa.status NOT IN ('COMPLETED', 'CANCELLED')
                ORDER BY pa.id DESC LIMIT 1;
            """, (target_patient_id, wa_number, wa_number, wa_number))
            row = cur.fetchone()
            if row:
                pa_record = {
                    "id": row[0],
                    "code": row[1],
                    "date": str(row[2]),
                    "checkin": str(row[3]) if row[3] else None,
                    "type": row[4],
                    "status": row[5],
                    "pending_docs": row[6],
                    "submitted_docs": row[7],
                    "instructions": row[8],
                    "remarks": row[9],
                    "doctor": row[10],
                    "department": row[11],
                    "patient_name": row[12]
                }
        except Exception as query_err:
            print(f"[PRE_ADMISSION] Error retrieving pre-admission record: {query_err}")
        finally:
            cur.close()
            conn.close()

        # Check intent triggers (buttons or text phrases)
        is_yes = btn_id == "btn_confirm_admission" or any(w in msg_lower for w in ["yes", "confirm", "confirm admission", "i will come", "sure", "coming", "agreed", "btn_confirm"])
        is_no = btn_id == "btn_cancel_admission" or any(w in msg_lower for w in ["no", "cancel", "cancel admission", "cannot come", "not coming", "won't come", "btn_cancel"])
        is_insurance_escalation = btn_id == "btn_admission_help" or any(w in msg_lower for w in ["insurance", "claim", "coverage", "policy", "cashless", "tpa", "human", "agent", "receptionist", "speak to staff", "call me", "assistance", "need help", "need assistance"])
        is_doc_query = any(w in msg_lower for w in ["document", "bring", "require", "need", "id", "card", "proof", "what to bring"])

        if is_yes:
            import preadmission_service
            if pa_record:
                preadmission_service.update_pre_admission_status(pa_record["id"], status="CONFIRMED")
                p_name_str = f" {pa_record['patient_name']}" if pa_record.get('patient_name') else ""
                response_text = (
                    f"✅ Thank you{p_name_str}! Your pre-admission registration (*{pa_record['code']}*) for *{pa_record['date']}* "
                    f"under Dr. {pa_record['doctor']} ({pa_record['department']}) has been *CONFIRMED*.\n\n"
                    f"📋 *Required Documents to Bring:*\n{pa_record['pending_docs'] or 'Government ID, Health Insurance Card, Doctor Referral Note'}\n\n"
                    f"📍 Please report to the Ground Floor Admission Desk by *{pa_record['checkin'] or '09:00 AM'}*."
                )
            else:
                response_text = (
                    "✅ Thank you! Your pre-admission confirmation has been recorded successfully.\n\n"
                    "Our Admission Desk team will verify your details and assist you upon arrival."
                )

        elif is_no:
            import preadmission_service
            if pa_record:
                preadmission_service.update_pre_admission_status(pa_record["id"], status="CANCELLED")
                response_text = (
                    f"❌ Your pre-admission record (*{pa_record['code']}*) has been *CANCELLED* as requested.\n\n"
                    f"If you need to reschedule your admission or consult with Dr. {pa_record['doctor']}, please let us know."
                )
            else:
                response_text = (
                    "❌ Your pre-admission cancellation request has been recorded.\n\n"
                    "If you need further assistance or wish to reschedule, please feel free to reach out to us."
                )

        elif is_insurance_escalation:
            # Create Escalation entry & set status to ESCALATED
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            esc_id = None
            try:
                cur.execute("""
                    INSERT INTO escalations (
                        patient_id, conversation_id, escalation_type, reason, status, created_at
                    ) VALUES (
                        %s, (SELECT id FROM conversations WHERE conversation_code = %s LIMIT 1),
                        'PRE_ADMISSION_ASSISTANCE', %s, 'OPEN', CURRENT_TIMESTAMP
                    ) RETURNING id;
                """, (state.get("patient_id"), conversation_code, f"Pre-Admission help request: {message_text[:100]}"))
                esc_id = cur.fetchone()[0]
                conn.commit()
            except Exception as esc_err:
                conn.rollback()
                print(f"[PRE_ADMISSION] Escalation logging error: {esc_err}")
            finally:
                cur.close()
                conn.close()

            if pa_record:
                import preadmission_service
                preadmission_service.update_pre_admission_status(pa_record["id"], status="ESCALATED", remarks=f"Escalated query: {message_text[:100]}")

            response_text = (
                "👩‍⚕️ I have escalated your request regarding insurance/admission assistance to our Admission Desk Coordinator.\n\n"
                "A hospital representative will call you directly to verify your details and assist you with the paperwork. 🙏"
            )

        elif pa_record and not is_doc_query:
            # Display current pre-admission record details
            pend_docs_fmt = pa_record['pending_docs'] or "Government ID, Insurance Card"
            response_text = (
                f"📋 *Your Pre-Admission Details:*\n\n"
                f"🆔 *Code:* {pa_record['code']}\n"
                f"📅 *Admission Date:* {pa_record['date']}\n"
                f"⏰ *Check-in Time:* {pa_record['checkin'] or '09:00 AM'}\n"
                f"🏥 *Department:* {pa_record['department']}\n"
                f"👨‍⚕️ *Doctor:* Dr. {pa_record['doctor']}\n"
                f"🛋️ *Type:* {pa_record['type']}\n"
                f"📊 *Status:* {pa_record['status']}\n\n"
                f"📝 *Instructions:* {pa_record['instructions'] or 'Fast 8 hours prior if instructed.'}\n"
                f"📄 *Pending Documents:* {pend_docs_fmt}\n\n"
                f"Reply *YES* to confirm your admission or *NO* to cancel."
            )

        else:
            # Fallback to RAG knowledge retrieval for admission document questions
            tool_called = "search_knowledge"
            try:
                cat_hint = "ADMISSION_DOCUMENTS" if is_doc_query else "PRE_ADMISSION"
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
                    response_text = (
                        "📋 *General Admission Preparation Guidelines:*\n\n"
                        "1. *Required Documents:* Government Photo ID (Aadhaar/Passport/DL), Health Insurance Card & pre-authorization form, Referral letter/Doctor notes.\n"
                        "2. *Personal Items:* Essential toiletries, comfortable clothing, regular prescription medications.\n"
                        "3. *Check-in:* Please report to the Ground Floor Admission Desk at your scheduled check-in time.\n\n"
                        "How else can I assist you with your admission?"
                    )
                    state["knowledge_context"] = []
            except Exception as e:
                print(f"[Agent] PRE_ADMISSION knowledge retrieval error: {e}")
                response_text = "Please bring your Photo ID and Insurance card to the Admission Desk upon arrival."
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

    res_payload = {
        "success": True,
        "conversation_id": conversation_code,
        "language": current_lang,
        "intent": intent,
        "response": response_text,
        "missing_information": missing_info,
        "tool_called": tool_called,
        "interactive_buttons": state.get("interactive_buttons", [])
    }
    return response_validator.validate_pre_dispatch(state, res_payload)
