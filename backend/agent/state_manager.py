import json
import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config

import copy

from utils.phone_utils import get_phone_query_condition, get_phone_query_params, normalize_phone

def get_default_state():
    return {
        "conversation_id": None,
        "patient_id": None,
        "patient_type": None,
        "language": "ENGLISH",
        "intent": "GREETING",
        "conversation_state": "GREETING",
        # Booking / department context
        "entities": {
            "patient_id": None,
            "doctor_id": None,
            "department_id": None,
            "appointment_date": None,
            "appointment_time": None,
            "booking_id": None,
            "reason": None,
            "symptoms": []
        },
        # Convenience resolved labels (populated during booking flow)
        "department_name": None,
        "specialty": None,
        "doctor_name": None,
        "full_name": None,
        # Booking flow state
        "missing_information": [],
        "booking_stage": None,
        "last_action": None,
        "confirmation_pending": False,
        "confirmation_details": {},
        "change_pending": False,
        "change_pending_field": None,
        "previous_question": None,
        "interactive_buttons": [],
        # Registration fields
        "registration_fields": {
            "first_name": None,
            "last_name": None,
            "date_of_birth": None,
            "gender": None,
            "phone": None,
            "reason_for_visit": None
        },
        # Time-of-day split parsing (e.g. patient says '5' then 'PM' in separate messages)
        "pending_time_digit": None,
        # Dependent / family patient flow
        "appointment_for": None,           # SELF | CHILD | FAMILY_MEMBER
        "patient_relationship": None,       # SON | DAUGHTER | SPOUSE | MOTHER | FATHER | CHILD | SIBLING | DEPENDENT
        "actual_patient_id": None,          # patient_id of the dependent (not the contact)
        "actual_patient_name": None,        # name of dependent
        "contact_patient_id": None,         # patient_id of the WhatsApp sender
        "dependent_collection_stage": None, # which field we are collecting for dependent
        # Last sent/received for context
        "last_user_message": None,
        "last_bot_message": None,
    }

def resolve_valid_patient_id(cur, candidate_patient_id: int = None, whatsapp_number: str = None) -> int:
    """
    Validates candidate_patient_id against the patients table.
    If valid, returns candidate_patient_id.
    If invalid/stale or None, attempts to resolve an ACTIVE patient by phone or whatsapp_number using 10-digit normalization.
    Returns valid patient_id (int) or None if no matching patient exists.
    """
    if candidate_patient_id is not None:
        try:
            cur.execute("SELECT id FROM patients WHERE id = %s;", (candidate_patient_id,))
            if cur.fetchone():
                return candidate_patient_id
        except Exception:
            pass

    if whatsapp_number:
        try:
            cond = get_phone_query_condition()
            params = get_phone_query_params(whatsapp_number)
            query = f"SELECT id, whatsapp_number FROM patients WHERE {cond} AND status = 'ACTIVE' LIMIT 1;"
            cur.execute(query, params)
            row = cur.fetchone()
            if row:
                pat_id, curr_wnum = row[0], row[1]
                # Sync whatsapp_number if empty or not updated
                if not curr_wnum and whatsapp_number:
                    try:
                        cur.execute("UPDATE patients SET whatsapp_number = %s WHERE id = %s;", (whatsapp_number, pat_id))
                    except Exception:
                        pass
                return pat_id
        except Exception as e:
            print("Error in resolve_valid_patient_id:", e)

    return None

def get_conversation_state(conversation_code: str, whatsapp_number: str = "919999999999", default_language: str = "ENGLISH") -> dict:
    """
    Retrieves the conversation state.
    If the conversation doesn't exist, creates it.
    If it exists, retrieves the state from the metadata of the latest logged message.
    Validates and reconciles patient_id against the patients table.
    """
    if (not whatsapp_number or whatsapp_number == "919999999999") and conversation_code and conversation_code.startswith("WA_"):
        parts = conversation_code.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            whatsapp_number = parts[1]

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Check if conversation exists
        cur.execute("SELECT id, patient_id, whatsapp_number, language, current_intent FROM conversations WHERE conversation_code = %s;", (conversation_code,))
        row = cur.fetchone()
        
        if not row:
            # Check if whatsapp_number matches an existing active patient
            initial_patient_id = resolve_valid_patient_id(cur, None, whatsapp_number)
            
            # Create a new conversation row
            cur.execute("""
                INSERT INTO conversations (conversation_code, patient_id, whatsapp_number, language, current_intent, conversation_status)
                VALUES (%s, %s, %s, %s, 'GREETING', 'ACTIVE')
                RETURNING id;
            """, (conversation_code, initial_patient_id, whatsapp_number, default_language))
            conv_id = cur.fetchone()[0]
            conn.commit()
            
            # Return new state
            state = get_default_state()
            state["conversation_id"] = conversation_code
            state["patient_id"] = initial_patient_id
            if initial_patient_id:
                state["entities"]["patient_id"] = initial_patient_id
            state["language"] = default_language
            return state
            
        conv_db_id, db_pat_id, db_wnum, db_lang, db_intent = row
        effective_wnum = db_wnum or whatsapp_number
        
        # Query latest message containing state metadata
        cur.execute("""
            SELECT metadata FROM messages
            WHERE conversation_id = %s AND metadata IS NOT NULL AND metadata ->> 'language' IS NOT NULL
            ORDER BY id DESC LIMIT 1;
        """, (conv_db_id,))
        msg_row = cur.fetchone()
        
        if msg_row and msg_row[0]:
            state = msg_row[0]
            if not isinstance(state, dict):
                state = json.loads(state)
            state["conversation_id"] = conversation_code
        else:
            state = get_default_state()
            state["conversation_id"] = conversation_code
            state["patient_id"] = db_pat_id
            state["language"] = db_lang or default_language
            state["intent"] = db_intent or "GREETING"
            
        # Reconcile & validate candidate patient_id against patients table
        candidate_patient_id = state.get("patient_id")
        valid_patient_id = resolve_valid_patient_id(cur, candidate_patient_id, effective_wnum)
        
        state["patient_id"] = valid_patient_id
        if isinstance(state.get("entities"), dict):
            state["entities"]["patient_id"] = valid_patient_id

        if db_pat_id != valid_patient_id:
            cur.execute("UPDATE conversations SET patient_id = %s WHERE id = %s;", (valid_patient_id, conv_db_id))
            conn.commit()
            
        return state
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def save_conversation_state(conversation_code: str, state_dict: dict):
    """
    Updates the general conversation attributes (intent, patient_id, language) in the conversations table.
    Note: The actual state JSON is written to the metadata of the AI's response message in messages.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Query whatsapp_number to allow fallback patient resolution if patient_id is missing or stale
        cur.execute("SELECT whatsapp_number FROM conversations WHERE conversation_code = %s;", (conversation_code,))
        conv_row = cur.fetchone()
        wnum = conv_row[0] if conv_row else None
        
        # Resolve patient_id to update conversations table safely
        candidate_patient_id = state_dict.get("patient_id")
        valid_patient_id = resolve_valid_patient_id(cur, candidate_patient_id, wnum)
        
        state_dict["patient_id"] = valid_patient_id
        if isinstance(state_dict.get("entities"), dict):
            state_dict["entities"]["patient_id"] = valid_patient_id
            
            LANG_MAP = {
                'EN': 'ENGLISH', 'ENGLISH': 'ENGLISH',
                'TA': 'TAMIL', 'TAMIL': 'TAMIL',
                'HI': 'HINDI', 'HINDI': 'HINDI',
                'TE': 'TELUGU', 'TELUGU': 'TELUGU',
                'ML': 'MALAYALAM', 'MALAYALAM': 'MALAYALAM',
                'KN': 'KANNADA', 'KANNADA': 'KANNADA',
                'UR': 'URDU', 'URDU': 'URDU'
            }
            raw_lang = state_dict.get("language", "ENGLISH")
            db_language = LANG_MAP.get(str(raw_lang).upper(), 'ENGLISH')
    
            # Valid intents matching CHECK constraints in migrations
            # Map agent-side intents to valid DB intents
            INTENT_TO_DB = {
                'DEPENDENT_PATIENT': 'BOOK_APPOINTMENT',
                'THANK_YOU': 'GREETING',
                'GOODBYE': 'GREETING',
                'APPOINTMENT_CONFIRMATION': 'BOOK_APPOINTMENT',
                'APPOINTMENT_TIME': 'BOOK_APPOINTMENT',
                'APPOINTMENT_DATE': 'BOOK_APPOINTMENT',
                'EMERGENCY_GUIDANCE': 'HOSPITAL_INFORMATION',
                'IDENTIFY_PATIENT': 'GREETING',
                'POST_BOOKING': 'BOOK_APPOINTMENT',
                'LANGUAGE_CHANGE': 'GREETING',
                # REGISTER_PATIENT is not in DB CHECK constraint → map to GREETING
                'REGISTER_PATIENT': 'GREETING',
                'UNKNOWN': 'GREETING',
            }
            valid_intents = [
                'GREETING', 'BOOK_APPOINTMENT', 'CANCEL_APPOINTMENT', 'RESCHEDULE_APPOINTMENT', 
                'APPOINTMENT_STATUS', 'DOCTOR_AVAILABILITY', 'HOSPITAL_INFORMATION', 
                'DEPARTMENT_INFORMATION', 'SYMPTOM_GUIDANCE', 'PRE_ADMISSION', 'HUMAN_ESCALATION',
                'REGISTER_PATIENT'
            ]
            intent = state_dict.get("intent", "GREETING")
            db_intent = INTENT_TO_DB.get(intent, intent if intent in valid_intents else 'GREETING')
    
            cur.execute("""
                UPDATE conversations
                SET patient_id = %s,
                    language = %s,
                    current_intent = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE conversation_code = %s;
            """, (valid_patient_id, db_language, db_intent, conversation_code))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

