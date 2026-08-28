import json
import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config

import copy

def get_default_state():
    return {
        "conversation_id": None,
        "patient_id": None,
        "language": "ENGLISH",
        "intent": "GREETING",
        "entities": {
            "patient_id": None,
            "doctor_id": None,
            "department_id": None,
            "appointment_date": None,
            "appointment_time": None,
            "booking_id": None,
            "reason": None
        },
        "missing_information": [],
        "last_action": None,
        "registration_fields": {
            "first_name": None,
            "last_name": None,
            "date_of_birth": None,
            "gender": None,
            "phone": None
        },
        "previous_question": None
    }

def get_conversation_state(conversation_code: str, whatsapp_number: str = "919999999999", default_language: str = "ENGLISH") -> dict:
    """
    Retrieves the conversation state.
    If the conversation doesn't exist, creates it.
    If it exists, retrieves the state from the metadata of the latest logged message.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Check if conversation exists
        cur.execute("SELECT id, patient_id, language, current_intent FROM conversations WHERE conversation_code = %s;", (conversation_code,))
        row = cur.fetchone()
        
        if not row:
            # Create a new conversation row
            cur.execute("""
                INSERT INTO conversations (conversation_code, whatsapp_number, language, current_intent, conversation_status)
                VALUES (%s, %s, %s, 'GREETING', 'ACTIVE')
                RETURNING id;
            """, (conversation_code, whatsapp_number, default_language))
            conv_id = cur.fetchone()[0]
            conn.commit()
            
            # Return new state
            state = get_default_state()
            state["conversation_id"] = conversation_code
            state["language"] = default_language
            return state
            
        conv_db_id, pat_id, db_lang, db_intent = row
        
        # Query latest message containing state metadata
        cur.execute("""
            SELECT metadata FROM messages
            WHERE conversation_id = %s AND metadata IS NOT NULL
            ORDER BY id DESC LIMIT 1;
        """, (conv_db_id,))
        msg_row = cur.fetchone()
        
        if msg_row and msg_row[0]:
            # Load state from metadata column
            state = msg_row[0]
            if not isinstance(state, dict):
                state = json.loads(state)
            state["conversation_id"] = conversation_code
            return state
            
        # If no message has metadata, construct from conversation fields
        state = get_default_state()
        state["conversation_id"] = conversation_code
        state["patient_id"] = pat_id
        state["language"] = db_lang or default_language
        state["intent"] = db_intent or "GREETING"
        return state
        
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
        # Resolve patient_id to update conversations table
        patient_id = state_dict.get("patient_id")
        intent = state_dict.get("intent", "GREETING")
        language = state_dict.get("language", "ENGLISH")
        
        # Valid intents matching Check constraints in migrations
        valid_intents = [
            'GREETING', 'BOOK_APPOINTMENT', 'CANCEL_APPOINTMENT', 'RESCHEDULE_APPOINTMENT', 
            'APPOINTMENT_STATUS', 'DOCTOR_AVAILABILITY', 'HOSPITAL_INFORMATION', 
            'DEPARTMENT_INFORMATION', 'SYMPTOM_GUIDANCE', 'PRE_ADMISSION', 'HUMAN_ESCALATION'
        ]
        db_intent = intent if intent in valid_intents else 'GREETING'
        
        cur.execute("""
            UPDATE conversations
            SET patient_id = %s,
                language = %s,
                current_intent = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE conversation_code = %s;
        """, (patient_id, language, db_intent, conversation_code))
        conn.commit()
    finally:
        cur.close()
        conn.close()
