"""
patient_identification_service.py
===================================
Patient Identification Service for Meridian Hospital AI Patient Desk.

Responsibilities:
  - Phone number normalization & primary patient lookup via WhatsApp number
  - Classification of sender status (EXISTING_PATIENT, REGISTERED_CONTACT_NO_PROFILE, NEW_PATIENT)
  - Patient Profile summary retrieval for PATIENT_DETAILS / PATIENT_PROFILE intent
  - Dependent patient profile management (separate from parent profile)
  - Gender & relationship matching for dependent resolution
  - Strict authorization validation for Patient ID / Name access
"""

import sys
import os
import re
from typing import Optional, Dict, Any, List

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
from utils.phone_utils import get_phone_query_condition, get_phone_query_params, normalize_phone


def identify_patient_by_phone(phone_number: str) -> Dict[str, Any]:
    """
    Looks up primary patient in database using WhatsApp phone number.
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
        
        # Primary non-dependent patient first
        cur.execute(f"""
            SELECT id, patient_code, first_name, last_name, date_of_birth, gender,
                   phone, whatsapp_number, email, address, city, state, pincode, status, created_at
            FROM patients
            WHERE {cond} AND status = 'ACTIVE' AND (is_dependent = FALSE OR is_dependent IS NULL)
            ORDER BY id ASC
            LIMIT 1;
        """, params)
        row = cur.fetchone()

        # Fallback to any patient record if primary flag not set
        if not row:
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


def get_dependents_for_parent(parent_patient_id: Optional[int], whatsapp_number: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches all dependent patients associated with parent_patient_id (guardian_patient_id)
    or guardian_phone/whatsapp_number.
    """
    if not parent_patient_id and not whatsapp_number:
        return []

    w_phone = (whatsapp_number or "").strip()
    p_id = parent_patient_id if (parent_patient_id and parent_patient_id > 0) else -1
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, patient_code, first_name, last_name, date_of_birth, gender, status, relationship_to_contact
            FROM patients
            WHERE (
                (guardian_patient_id = %s)
                OR (%s <> '' AND guardian_phone = %s)
                OR (%s <> '' AND phone = %s AND is_dependent = TRUE)
            )
            AND is_dependent = TRUE AND status = 'ACTIVE'
            ORDER BY id ASC;
        """, (p_id, w_phone, w_phone, w_phone, w_phone))
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
                "status": r[6],
                "relationship": r[7]
            })
        return dependents
    except Exception as e:
        print(f"[PATIENT_ID_SERVICE] Error fetching dependents for parent_id={parent_patient_id}: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def get_matching_dependents(
    parent_patient_id: Optional[int],
    whatsapp_number: Optional[str] = None,
    relationship: Optional[str] = None,
    gender: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Filters dependents by relationship and/or gender.
    
    Relationships:
      - 'SON' / 'BOY' -> matches relationship_to_contact in ('SON','BOY') or gender ILIKE 'Male'
      - 'DAUGHTER' / 'GIRL' -> matches relationship_to_contact in ('DAUGHTER','GIRL') or gender ILIKE 'Female'
      - 'CHILD' / 'KID' / 'CHILDREN' -> matches any child dependent (SON or DAUGHTER or CHILD)
      - Other (SPOUSE, FATHER, MOTHER, etc.) -> matches exact relationship or all dependents if unmapped
    """
    all_deps = get_dependents_for_parent(parent_patient_id, whatsapp_number)
    if not all_deps:
        return []

    if not relationship and not gender:
        return all_deps

    rel_norm = (relationship or "").strip().upper()

    filtered = []
    for dep in all_deps:
        d_rel = (dep.get("relationship") or "").strip().upper()
        d_gen = (dep.get("gender") or "").strip().capitalize()

        match = False
        if rel_norm in ("SON", "BOY"):
            if d_rel in ("SON", "BOY") or d_gen in ("Male", "M"):
                match = True
        elif rel_norm in ("DAUGHTER", "GIRL"):
            if d_rel in ("DAUGHTER", "GIRL") or d_gen in ("Female", "F"):
                match = True
        elif rel_norm in ("CHILD", "KID", "CHILDREN"):
            if d_rel in ("SON", "BOY", "DAUGHTER", "GIRL", "CHILD", "KID") or d_gen in ("Male", "Female", "M", "F"):
                match = True
        elif rel_norm in ("SPOUSE", "WIFE", "HUSBAND", "FATHER", "MOTHER"):
            if d_rel == rel_norm or (rel_norm in ("WIFE", "SPOUSE") and d_gen == "Female") or (rel_norm in ("HUSBAND", "SPOUSE") and d_gen == "Male"):
                match = True
        elif rel_norm:
            if d_rel == rel_norm:
                match = True
        else:
            match = True

        if gender and match:
            g_norm = gender.strip().capitalize()
            if d_gen != g_norm:
                match = False

        if match:
            filtered.append(dep)

    return filtered


def resolve_dependent_by_input(
    parent_patient_id: Optional[int],
    whatsapp_number: Optional[str],
    input_str: str,
    relationship_hint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Attempts to resolve a dependent patient from user input (Name or Patient Code/ID).
    Validates ownership/authorization against parent_patient_id or whatsapp_number.
    
    Returns:
      {
        "found": True/False,
        "authorized": True/False,
        "patient": dict or None,
        "reason": str message
      }
    """
    clean_input = input_str.strip()
    if not clean_input:
        return {"found": False, "authorized": False, "patient": None, "reason": "Empty input"}

    all_deps = get_dependents_for_parent(parent_patient_id, whatsapp_number)

    # 1. Check if input matches patient_code or ID (e.g. P00125 or P125 or PAT12345 or 125)
    code_match = re.search(r"\b(P\d{3,6}|PAT\d{4,6}|\d{3,6})\b", clean_input, re.IGNORECASE)
    search_code = code_match.group(1).upper() if code_match else clean_input.upper()

    # Search among authorized dependents first
    for dep in all_deps:
        p_code = (dep.get("patient_code") or "").upper()
        p_id = str(dep.get("id"))
        if search_code in (p_code, f"P{p_id}", p_id):
            return {"found": True, "authorized": True, "patient": dep, "reason": "Matched patient code/ID"}

    # Search by full name or first name among authorized dependents
    for dep in all_deps:
        full_name = (dep.get("full_name") or "").lower()
        first_name = (dep.get("first_name") or "").lower()
        inp_lower = clean_input.lower()
        if inp_lower == full_name or inp_lower == first_name or inp_lower in full_name:
            return {"found": True, "authorized": True, "patient": dep, "reason": "Matched dependent name"}

    # 2. Check if patient ID exists in DB globally to detect UNAUTHORIZED access attempt
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, patient_code, first_name, last_name, date_of_birth, gender, status, guardian_patient_id, guardian_phone, phone, whatsapp_number
            FROM patients
            WHERE UPPER(patient_code) = %s OR id::text = %s OR UPPER(patient_code) = %s
            LIMIT 1;
        """, (search_code, search_code.lstrip("P"), f"P{search_code}"))
        row = cur.fetchone()
        if row:
            global_id, global_code, fn, ln, dob, gen, st, g_id, g_ph, ph, wa = row
            # Validate ownership
            is_authorized = (
                (parent_patient_id and g_id == parent_patient_id) or
                (whatsapp_number and (g_ph == whatsapp_number or ph == whatsapp_number or wa == whatsapp_number))
            )
            if not is_authorized:
                return {
                    "found": True,
                    "authorized": False,
                    "patient": None,
                    "reason": "I couldn't find that patient ID under your registered WhatsApp number. Please check the ID and try again."
                }
            else:
                patient_info = {
                    "id": global_id,
                    "patient_code": global_code,
                    "first_name": fn,
                    "last_name": ln,
                    "full_name": f"{fn or ''} {ln or ''}".strip(),
                    "date_of_birth": str(dob) if dob else None,
                    "gender": gen,
                    "status": st
                }
                return {"found": True, "authorized": True, "patient": patient_info, "reason": "Matched authorized patient record"}
    except Exception as e:
        print(f"[PATIENT_ID_SERVICE] Error checking global patient authorization: {e}")
    finally:
        cur.close()
        conn.close()

    return {"found": False, "authorized": True, "patient": None, "reason": "Patient not found"}
