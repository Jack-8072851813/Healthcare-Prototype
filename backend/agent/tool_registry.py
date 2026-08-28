import sys
import os
import json

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import appointment_service

def log_agent_action(conversation_code: str, action_name: str, intent: str, input_data: dict, output_data: dict, status: str, error_message: str = None):
    """Logs the agent action execution inside the agent_action_logs table."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Resolve conversation_id and patient_id
        cur.execute("SELECT id, patient_id FROM conversations WHERE conversation_code = %s;", (conversation_code,))
        row = cur.fetchone()
        if not row:
            return
        conv_id, patient_id = row
        
        # Valid actions check constraints
        valid_actions = [
            'GET_DOCTOR_AVAILABILITY', 'GET_AVAILABLE_SLOTS', 'BOOK_APPOINTMENT', 
            'GET_APPOINTMENT_STATUS', 'CANCEL_APPOINTMENT', 'RESCHEDULE_APPOINTMENT', 
            'GET_PATIENT', 'GET_HOSPITAL_INFORMATION'
        ]
        db_action = action_name if action_name in valid_actions else 'GET_APPOINTMENT_STATUS'
        
        cur.execute("""
            INSERT INTO agent_action_logs (
                conversation_id, patient_id, action_name, intent, 
                input_data, output_data, status, error_message
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            conv_id, patient_id, db_action, intent, 
            json.dumps(input_data), json.dumps(output_data), 
            status, error_message
        ))
        conn.commit()
    except Exception as e:
        print("Failed to log agent action:", str(e))
    finally:
        cur.close()
        conn.close()

# Controlled tools callable by the orchestrator:

def tool_get_doctor_availability(conversation_code: str, doctor_id: int, date_str: str) -> dict:
    input_data = {"doctor_id": doctor_id, "date_str": date_str}
    try:
        res = appointment_service.get_doctor_availability(doctor_id, date_str)
        log_agent_action(conversation_code, "GET_DOCTOR_AVAILABILITY", "DOCTOR_AVAILABILITY", input_data, res, "SUCCESS")
        return {"success": True, "data": res}
    except Exception as e:
        err_msg = str(e)
        log_agent_action(conversation_code, "GET_DOCTOR_AVAILABILITY", "DOCTOR_AVAILABILITY", input_data, {}, "FAILED", err_msg)
        return {"success": False, "error": err_msg}

def tool_get_available_slots(conversation_code: str, doctor_id: int, date_str: str) -> dict:
    input_data = {"doctor_id": doctor_id, "date_str": date_str}
    try:
        res = appointment_service.get_available_slots(doctor_id, date_str)
        
        # Filter out past slots for today's date in Asia/Kolkata
        import datetime
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.datetime.now(ist)
        today_str = now_ist.strftime("%Y-%m-%d")
        if date_str == today_str:
            curr_time = now_ist.strftime("%H:%M")
            res = [s for s in res if s > curr_time]

        log_agent_action(conversation_code, "GET_AVAILABLE_SLOTS", "DOCTOR_AVAILABILITY", input_data, {"slots": res}, "SUCCESS")
        return {"success": True, "slots": res}
    except Exception as e:
        err_msg = str(e)
        log_agent_action(conversation_code, "GET_AVAILABLE_SLOTS", "DOCTOR_AVAILABILITY", input_data, {}, "FAILED", err_msg)
        return {"success": False, "error": err_msg}

def tool_book_appointment(conversation_code: str, patient_id: int, doctor_id: int, department_id: int, date_str: str, time_str: str, reason: str, user_id: int = None) -> dict:
    input_data = {
        "patient_id": patient_id, "doctor_id": doctor_id, "department_id": department_id,
        "date_str": date_str, "time_str": time_str, "reason": reason, "created_by_user_id": user_id
    }
    try:
        res = appointment_service.book_appointment(
            patient_id=patient_id, doctor_id=doctor_id, department_id=department_id,
            date_str=date_str, time_str=time_str, patient_reason=reason,
            booking_source="WHATSAPP_TEXT", created_by_user_id=user_id
        )
        log_agent_action(conversation_code, "BOOK_APPOINTMENT", "BOOK_APPOINTMENT", input_data, res, "SUCCESS")
        return {"success": True, "data": res}
    except appointment_service.AppointmentError as e:
        # Business error
        log_agent_action(conversation_code, "BOOK_APPOINTMENT", "BOOK_APPOINTMENT", input_data, {}, "REJECTED", e.message)
        return {"success": False, "error_code": e.error_code, "error": e.message}
    except Exception as e:
        err_msg = str(e)
        log_agent_action(conversation_code, "BOOK_APPOINTMENT", "BOOK_APPOINTMENT", input_data, {}, "FAILED", err_msg)
        return {"success": False, "error_code": "UNKNOWN_ERROR", "error": err_msg}

def tool_cancel_appointment(conversation_code: str, booking_id: str, reason: str, user_id: int = None) -> dict:
    input_data = {"booking_id": booking_id, "reason": reason, "cancelled_by_user_id": user_id}
    try:
        res = appointment_service.cancel_appointment(
            booking_id=booking_id, reason=reason, cancelled_by_user_id=user_id
        )
        log_agent_action(conversation_code, "CANCEL_APPOINTMENT", "CANCEL_APPOINTMENT", input_data, res, "SUCCESS")
        return {"success": True, "data": res}
    except appointment_service.AppointmentError as e:
        log_agent_action(conversation_code, "CANCEL_APPOINTMENT", "CANCEL_APPOINTMENT", input_data, {}, "REJECTED", e.message)
        return {"success": False, "error_code": e.error_code, "error": e.message}
    except Exception as e:
        err_msg = str(e)
        log_agent_action(conversation_code, "CANCEL_APPOINTMENT", "CANCEL_APPOINTMENT", input_data, {}, "FAILED", err_msg)
        return {"success": False, "error_code": "UNKNOWN_ERROR", "error": err_msg}

def tool_reschedule_appointment(conversation_code: str, booking_id: str, new_date_str: str, new_time_str: str, reason: str, user_id: int = None) -> dict:
    input_data = {
        "booking_id": booking_id, "new_date_str": new_date_str, 
        "new_time_str": new_time_str, "reason": reason, "rescheduled_by_user_id": user_id
    }
    try:
        res = appointment_service.reschedule_appointment(
            booking_id=booking_id, new_date_str=new_date_str, new_time_str=new_time_str,
            reason=reason, rescheduled_by_user_id=user_id
        )
        log_agent_action(conversation_code, "RESCHEDULE_APPOINTMENT", "RESCHEDULE_APPOINTMENT", input_data, res, "SUCCESS")
        return {"success": True, "data": res}
    except appointment_service.AppointmentError as e:
        log_agent_action(conversation_code, "RESCHEDULE_APPOINTMENT", "RESCHEDULE_APPOINTMENT", input_data, {}, "REJECTED", e.message)
        return {"success": False, "error_code": e.error_code, "error": e.message}
    except Exception as e:
        err_msg = str(e)
        log_agent_action(conversation_code, "RESCHEDULE_APPOINTMENT", "RESCHEDULE_APPOINTMENT", input_data, {}, "FAILED", err_msg)
        return {"success": False, "error_code": "UNKNOWN_ERROR", "error": err_msg}

def tool_get_appointment_status(conversation_code: str, booking_id: str, patient_id: int = None) -> dict:
    input_data = {"booking_id": booking_id, "patient_id": patient_id}
    try:
        res = appointment_service.get_appointment(booking_id, patient_id)
        log_agent_action(conversation_code, "GET_APPOINTMENT_STATUS", "APPOINTMENT_STATUS", input_data, res, "SUCCESS")
        return {"success": True, "data": res}
    except appointment_service.AppointmentError as e:
        log_agent_action(conversation_code, "GET_APPOINTMENT_STATUS", "APPOINTMENT_STATUS", input_data, {}, "REJECTED", e.message)
        return {"success": False, "error_code": e.error_code, "error": e.message}
    except Exception as e:
        err_msg = str(e)
        log_agent_action(conversation_code, "GET_APPOINTMENT_STATUS", "APPOINTMENT_STATUS", input_data, {}, "FAILED", err_msg)
        return {"success": False, "error_code": "UNKNOWN_ERROR", "error": err_msg}

def tool_get_hospital_information(conversation_code: str, query: str = "") -> dict:
    # Simulates RAG query against database knowledge chunks
    input_data = {"query": query}
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT content FROM knowledge_chunks LIMIT 3;")
        rows = cur.fetchall()
        contents = [r[0] for r in rows]
        res = {"success": True, "chunks": contents}
        log_agent_action(conversation_code, "GET_HOSPITAL_INFORMATION", "HOSPITAL_INFORMATION", input_data, res, "SUCCESS")
        return res
    except Exception as e:
        err_msg = str(e)
        log_agent_action(conversation_code, "GET_HOSPITAL_INFORMATION", "HOSPITAL_INFORMATION", input_data, {}, "FAILED", err_msg)
        return {"success": False, "error": err_msg}
    finally:
        cur.close()
        conn.close()
