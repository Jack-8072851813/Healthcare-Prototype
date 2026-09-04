"""
patient_identification_service.py
===================================
Patient Identification Service for Meridian Hospital AI Patient Desk.

Responsibilities:
  - Phone number normalization & primary patient lookup via WhatsApp number
  - Classification of sender status (EXISTING_PATIENT, REGISTERED_CONTACT_NO_PROFILE, NEW_PATIENT)
  - Patient Profile summary retrieval for PATIENT_DETAILS / PATIENT_PROFILE intent
  - Dependent patient profile management (separate from parent profile)
"""

import sys
import os
from typing import Optional, Dict, Any, List

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from utils.phone_utils import get_phone_query_condition, get_phone_query_params, normalize_phone


def identify_patient_by_phone(phone_number: str) -> Dict[str, Any]:
    """
    Looks up patient in database using WhatsApp phone number.
    Returns dictionary with patient status and data.
    """
    if not phone_number:
        return {
            "found": False,
            "status": "NEW_PATIENT",
            "patient": None
        }

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cond = get_phone_query_condition()
        params = get_phone_query_params(phone_number)
        
        cur.execute(f"""
            SELECT id, patient_code, first_name, last_name, date_of_birth, gender,
                   phone, whatsapp_number, email, address, city, state, pincode, status, created_at
            FROM patients
            WHERE {cond} AND status = 'ACTIVE'
            ORDER BY id ASC
            LIMIT 1;
        """, params)
        row = cur.fetchone()
        if row:
            patient_info = {
                "id": row[0],
                "patient_code": row[1],
                "first_name": row[2],
                "last_name": row[3],
                "full_name": f"{row[2] or ''} {row[3] or ''}".strip() or "Patient",
                "date_of_birth": str(row[4]) if row[4] else None,
                "gender": row[5],
                "phone": row[6],
                "whatsapp_number": row[7],
                "email": row[8],
                "address": row[9],
                "city": row[10],
                "state": row[11],
                "pincode": row[12],
                "status": row[13],
                "created_at": str(row[14]) if row[14] else None
            }
            return {
                "found": True,
                "status": "EXISTING_PATIENT",
                "patient": patient_info
            }
        
        # Check if conversation exists for contact without formal patient row
        cur.execute("""
            SELECT id, patient_id FROM conversations
            WHERE whatsapp_number = %s
            ORDER BY id DESC LIMIT 1;
        """, (phone_number,))
        conv_row = cur.fetchone()
        if conv_row and conv_row[1]:
            cur.execute("SELECT id, patient_code, first_name, last_name, date_of_birth, gender FROM patients WHERE id = %s;", (conv_row[1],))
            p_row = cur.fetchone()
            if p_row:
                patient_info = {
                    "id": p_row[0],
                    "patient_code": p_row[1],
                    "first_name": p_row[2],
                    "last_name": p_row[3],
                    "full_name": f"{p_row[2] or ''} {p_row[3] or ''}".strip() or "Patient",
                    "date_of_birth": str(p_row[4]) if p_row[4] else None,
                    "gender": p_row[5],
                }
                return {
                    "found": True,
                    "status": "EXISTING_PATIENT",
                    "patient": patient_info
                }

        return {
            "found": False,
            "status": "NEW_PATIENT",
            "patient": None
        }

    except Exception as e:
        print(f"[PATIENT_ID_SERVICE] Error identifying patient by phone ({phone_number}): {e}")
        return {
            "found": False,
            "status": "NEW_PATIENT",
            "patient": None,
            "error": str(e)
        }
    finally:
        cur.close()
        conn.close()


def format_patient_details_response(patient_dict: Optional[Dict[str, Any]], whatsapp_number: str, lang: str = "ENGLISH") -> str:
    """
    Formats structured patient profile details for WhatsApp response.
    Never asks for Patient ID if record exists.
    """
    if not patient_dict:
        return (
            "We don't have a registered patient profile associated with your phone number "
            f"(*{whatsapp_number}*) yet.\n\n"
            "Would you like to register as a new patient with Meridian Hospital?"
        )

    p_code = patient_dict.get("patient_code") or f"P{patient_dict.get('id')}"
    full_name = patient_dict.get("full_name") or f"{patient_dict.get('first_name', '')} {patient_dict.get('last_name', '')}".strip()
    dob = patient_dict.get("date_of_birth") or "Not recorded"
    gender = patient_dict.get("gender") or "Not recorded"
    phone = patient_dict.get("phone") or patient_dict.get("whatsapp_number") or whatsapp_number
    email = patient_dict.get("email") or "Not recorded"
    city = patient_dict.get("city") or "Not recorded"

    return (
        f"📋 *Registered Patient Details*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Name:* {full_name}\n"
        f"🆔 *Patient ID:* `{p_code}`\n"
        f"📅 *Date of Birth:* {dob}\n"
        f"🚻 *Gender:* {gender}\n"
        f"📞 *Phone:* {phone}\n"
        f"✉️ *Email:* {email}\n"
        f"📍 *City:* {city}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"How else can I assist you today?"
    )


def get_dependents_for_parent(parent_patient_id: int) -> List[Dict[str, Any]]:
    """
    Fetches dependent patients associated with parent_patient_id.
    """
    if not parent_patient_id:
        return []

    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, patient_code, first_name, last_name, date_of_birth, gender, status
            FROM patients
            WHERE parent_patient_id = %s AND status = 'ACTIVE'
            ORDER BY id ASC;
        """, (parent_patient_id,))
        rows = cur.fetchall()
        dependents = []
        for r in rows:
            dependents.append({
                "id": r[0],
                "patient_code": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "full_name": f"{r[2] or ''} {r[3] or ''}".strip(),
                "date_of_birth": str(r[4]) if r[4] else None,
                "gender": r[5],
                "status": r[6]
            })
        return dependents
    except Exception as e:
        print(f"[PATIENT_ID_SERVICE] Error fetching dependents for parent_id={parent_patient_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()
