"""
preadmission_service.py
========================
Pre-Admission & Admission Management Service for Meridian Hospital.

Responsibilities:
  - Admission registration & validation (patient, doctor, department, appointment, date)
  - Duplicate active admission prevention
  - Transactional DB insertion & WhatsApp notification dispatch
  - Scoped pre-admission listing & follow-up status updates for Admin & Doctor portals
  - Patient WhatsApp conversation retrieval for pre-admission follow-ups
"""

import datetime
from typing import Optional, Dict, Any, List
import db_config
from utils.phone_utils import normalize_phone


class PreAdmissionValidationError(Exception):
    pass


def generate_pre_admission_code(cur) -> str:
    """Generates a unique pre_admission_code (e.g., PAD0001)."""
    cur.execute("SELECT COUNT(*) FROM pre_admissions;")
    count = cur.fetchone()[0]
    return f"PAD{(count + 1):04d}"


def create_pre_admission(
    patient_id: int,
    doctor_id: int,
    department_id: int,
    expected_admission_date: str,
    admission_type: str,
    appointment_id: Optional[int] = None,
    expected_checkin_time: Optional[str] = None,
    instructions: Optional[str] = None,
    remarks: Optional[str] = None,
    pending_documents: Optional[str] = None,
    created_by_user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Registers a new pre-admission for an existing patient.
    Validates patient, doctor, department, doctor-department match, appointment ownership, and active record duplicates.
    Commits DB transaction first before creating & sending WhatsApp notification.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()

    try:
        # 1. Validate Patient
        cur.execute("""
            SELECT id, patient_code, first_name, last_name, phone, whatsapp_number, gender, date_of_birth, status
            FROM patients WHERE id = %s AND status = 'ACTIVE';
        """, (patient_id,))
        pat_row = cur.fetchone()
        if not pat_row:
            raise PreAdmissionValidationError(f"Patient ID {patient_id} not found or inactive.")
        
        pat_name = f"{pat_row[2]} {pat_row[3] or ''}".strip()
        pat_phone = pat_row[5] or pat_row[4]

        # 2. Validate Doctor
        cur.execute("""
            SELECT id, display_name, department_id, status FROM doctors WHERE id = %s;
        """, (doctor_id,))
        doc_row = cur.fetchone()
        if not doc_row:
            raise PreAdmissionValidationError(f"Doctor ID {doctor_id} not found.")
        doc_name = doc_row[1]
        doc_dept_id = doc_row[2]

        # 3. Validate Department
        cur.execute("SELECT id, department_name FROM departments WHERE id = %s;", (department_id,))
        dept_row = cur.fetchone()
        if not dept_row:
            raise PreAdmissionValidationError(f"Department ID {department_id} not found.")
        dept_name = dept_row[1]

        # 4. Validate Doctor-Department Match
        if doc_dept_id != department_id:
            raise PreAdmissionValidationError(f"Doctor '{doc_name}' does not belong to selected department '{dept_name}'.")

        # 5. Validate Appointment Ownership if appointment_id provided
        if appointment_id:
            cur.execute("SELECT id, patient_id FROM appointments WHERE id = %s;", (appointment_id,))
            appt_row = cur.fetchone()
            if not appt_row:
                raise PreAdmissionValidationError(f"Appointment ID {appointment_id} not found.")
            if appt_row[1] != patient_id:
                raise PreAdmissionValidationError(f"Appointment ID {appointment_id} does not belong to Patient ID {patient_id}.")

        # 6. Validate Admission Date
        try:
            date_obj = datetime.datetime.strptime(expected_admission_date.strip(), "%Y-%m-%d").date()
        except ValueError:
            raise PreAdmissionValidationError("Invalid expected_admission_date format. Expected YYYY-MM-DD.")

        # 7. Validate Admission Type
        valid_types = {"INPATIENT", "SURGERY", "DAYCARE"}
        adm_type_clean = admission_type.strip().upper()
        if adm_type_clean not in valid_types:
            raise PreAdmissionValidationError(f"Invalid admission_type '{admission_type}'. Allowed: {list(valid_types)}")

        # 8. Prevent Duplicate Active Pre-Admission
        cur.execute("""
            SELECT id, pre_admission_code FROM pre_admissions
            WHERE patient_id = %s AND status NOT IN ('COMPLETED', 'CANCELLED')
            LIMIT 1;
        """, (patient_id,))
        dup_row = cur.fetchone()
        if dup_row:
            raise PreAdmissionValidationError(f"Patient '{pat_name}' already has an active pre-admission record ({dup_row[1]}).")

        # 9. Format check-in time
        time_obj = None
        if expected_checkin_time and expected_checkin_time.strip():
            try:
                t_str = expected_checkin_time.strip()
                if len(t_str) == 5:
                    t_str += ":00"
                time_obj = datetime.datetime.strptime(t_str, "%H:%M:%S").time()
            except ValueError:
                pass

        # 10. Generate Code & Insert Record
        pad_code = generate_pre_admission_code(cur)
        status_initial = "PENDING"
        docs_pending = pending_documents or "Government ID, Insurance Card, Referral Note"

        cur.execute("""
            INSERT INTO pre_admissions (
                pre_admission_code, patient_id, appointment_id, doctor_id, department_id,
                expected_admission_date, expected_checkin_time, admission_type, status,
                pending_documents, instructions, remarks, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id;
        """, (
            pad_code, patient_id, appointment_id, doctor_id, department_id,
            date_obj, time_obj, adm_type_clean, status_initial,
            docs_pending, instructions, remarks
        ))
        pre_adm_id = cur.fetchone()[0]

        # 11. COMMIT DB TRANSACTION BEFORE NOTIFICATION DISPATCH
        conn.commit()
        print(f"[PRE_ADMISSION] Successfully registered pre-admission ID {pre_adm_id} ({pad_code}) for patient ID {patient_id}")

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        if isinstance(e, PreAdmissionValidationError):
            raise e
        print(f"[PRE_ADMISSION] Error registering pre-admission: {e}")
        raise PreAdmissionValidationError(f"Database error during admission registration: {str(e)}")

    finally:
        if not conn.closed:
            cur.close()
            conn.close()

    # 12. DISPATCH WHATSAPP NOTIFICATION AFTER DB COMMIT
    notification_result = dispatch_pre_admission_notification(pre_adm_id)

    return {
        "success": True,
        "pre_admission_id": pre_adm_id,
        "pre_admission_code": pad_code,
        "patient_name": pat_name,
        "doctor_name": doc_name,
        "department_name": dept_name,
        "expected_admission_date": str(date_obj),
        "admission_type": adm_type_clean,
        "status": status_initial,
        "notification_status": notification_result.get("status")
    }


def dispatch_pre_admission_notification(pre_admission_id: int) -> Dict[str, Any]:
    """
    Creates notification record & sends outbound WhatsApp message for a pre-admission.
    Uses patient's preferred language from recent conversation if available.
    Sends fine-tuned message with interactive quick response buttons.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT pa.id, pa.pre_admission_code, pa.expected_admission_date, pa.admission_type, pa.instructions,
                   pa.expected_checkin_time, pa.pending_documents,
                   p.id as patient_id, p.first_name, p.last_name, p.phone, p.whatsapp_number,
                   d.display_name as doctor_name, dept.department_name
            FROM pre_admissions pa
            JOIN patients p ON pa.patient_id = p.id
            JOIN doctors d ON pa.doctor_id = d.id
            JOIN departments dept ON pa.department_id = dept.id
            WHERE pa.id = %s;
        """, (pre_admission_id,))
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": "Pre-admission record not found"}

        (pa_id, pa_code, adm_date, adm_type, instructions,
         checkin_time, pending_docs,
         pat_id, f_name, l_name, phone, wa_phone,
         doc_name, dept_name) = row

        target_wa = wa_phone or phone
        pat_full_name = f"{f_name} {l_name or ''}".strip()

        # Check patient's conversation preferred language
        cur.execute("SELECT language FROM conversations WHERE patient_id = %s ORDER BY id DESC LIMIT 1;", (pat_id,))
        lang_row = cur.fetchone()
        lang = lang_row[0] if lang_row else "ENGLISH"

        # Format Fine-tuned Professional WhatsApp Message
        formatted_date = adm_date.strftime("%d %B %Y (%A)") if hasattr(adm_date, "strftime") else str(adm_date)
        adm_type_disp = adm_type.replace("_", " ").title()
        checkin_disp = str(checkin_time)[:5] if checkin_time else "09:00 AM"

        msg = (
            f"🏥 *MERIDIAN HOSPITAL — PRE-ADMISSION CLEARANCE* 🏥\n\n"
            f"Dear *{f_name}*,\n\n"
            f"Your pre-admission registration has been processed successfully. Please review your admission details:\n\n"
            f"📋 *Admission Summary:*\n"
            f"• *Pre-Admission Code:* `{pa_code}`\n"
            f"• *Expected Admission Date:* {formatted_date}\n"
            f"• *Reporting Time:* {checkin_disp}\n"
            f"• *Department:* {dept_name}\n"
            f"• *Attending Doctor:* Dr. {doc_name}\n"
            f"• *Admission Type:* {adm_type_disp}\n\n"
            f"📄 *Required Documents to Bring:*\n"
            f"• {pending_docs or 'Government Photo ID, Health Insurance Card, Referral Notes'}\n\n"
            f"📝 *Instructions:*\n"
            f"• {instructions or 'Please report to the Ground Floor Admission Desk at your scheduled check-in time.'}\n\n"
            f"Please tap a button below or reply *YES* to confirm your admission or *NO* to cancel."
        )

        # 1. Create Notification Record in DB
        cur.execute("""
            INSERT INTO notifications (
                patient_id, notification_type, channel, message, status, created_at
            ) VALUES (%s, 'ADMISSION_REMINDER', 'WHATSAPP', %s, 'PENDING', CURRENT_TIMESTAMP)
            RETURNING id;
        """, (pat_id, msg))
        notif_id = cur.fetchone()[0]
        conn.commit()

        # 2. Dispatch via voice.whatsapp_client service
        send_success = False
        ext_msg_id = None
        try:
            import voice.whatsapp_client as whatsapp_client
            buttons = [
                {"id": "btn_confirm_admission", "title": "Confirm Admission"},
                {"id": "btn_cancel_admission", "title": "Cancel Admission"},
                {"id": "btn_admission_help", "title": "Need Assistance"}
            ]
            res = whatsapp_client.send_button_message(target_wa, msg, buttons)
            if isinstance(res, dict) and res.get("success"):
                send_success = True
                ext_msg_id = res.get("message_id")
            elif res is True:
                send_success = True
            else:
                # Fallback to plain text message if button message fails
                res_text = whatsapp_client.send_text_message(target_wa, msg)
                if isinstance(res_text, dict) and res_text.get("success"):
                    send_success = True
                    ext_msg_id = res_text.get("message_id")
                elif res_text is True:
                    send_success = True
        except Exception as ws_err:
            print(f"[PRE_ADMISSION_NOTIF] Outbound WhatsApp dispatch failed: {ws_err}")
            send_success = False

        # 3. Update Notification Status
        if send_success:
            cur.execute("""
                UPDATE notifications
                SET status = 'SENT', external_message_id = %s, sent_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (ext_msg_id, notif_id))
            cur.execute("UPDATE pre_admissions SET status = 'CONTACTED' WHERE id = %s AND status = 'PENDING';", (pre_admission_id,))
            print(f"[PRE_ADMISSION_NOTIF] Notification ID {notif_id} dispatched successfully to {target_wa}")
        else:
            cur.execute("""
                UPDATE notifications
                SET status = 'FAILED', reason = 'WhatsApp dispatch failed', failed_at = CURRENT_TIMESTAMP
                WHERE id = %s;
            """, (notif_id,))
            print(f"[PRE_ADMISSION_NOTIF] Notification ID {notif_id} failed to dispatch to {target_wa}")

        conn.commit()
        return {
            "success": send_success,
            "notification_id": notif_id,
            "status": "SENT" if send_success else "FAILED",
            "whatsapp_number": target_wa
        }

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Failed to dispatch pre-admission notification: {e}")
        return {"success": False, "error": str(e)}
    finally:
        cur.close()
        conn.close()


def get_pre_admissions(
    doctor_id_filter: Optional[int] = None,
    patient_id: Optional[int] = None,
    status: Optional[str] = None,
    admission_type: Optional[str] = None,
    admission_date: Optional[str] = None,
    search: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Returns list of pre-admission records with filters.
    If doctor_id_filter is provided (for Doctor role), restricts to ONLY that doctor's patients.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        query = """
            SELECT pa.id, pa.pre_admission_code, pa.patient_id,
                   p.patient_code, p.first_name as pat_first, p.last_name as pat_last, p.phone as pat_phone, p.whatsapp_number,
                   pa.doctor_id, d.display_name as doctor_name,
                   pa.department_id, dept.department_name,
                   pa.appointment_id, appt.booking_id,
                   pa.expected_admission_date, TO_CHAR(pa.expected_checkin_time, 'HH24:MI') as expected_checkin_time,
                   pa.admission_type, pa.status, pa.pending_documents, pa.submitted_documents,
                   pa.instructions, pa.remarks, pa.created_at, pa.updated_at,
                   (SELECT n.status FROM notifications n WHERE n.patient_id = pa.patient_id AND n.notification_type = 'ADMISSION_REMINDER' ORDER BY n.id DESC LIMIT 1) as last_notif_status
            FROM pre_admissions pa
            JOIN patients p ON pa.patient_id = p.id
            JOIN doctors d ON pa.doctor_id = d.id
            JOIN departments dept ON pa.department_id = dept.id
            LEFT JOIN appointments appt ON pa.appointment_id = appt.id
        """
        conditions = []
        params = []

        if doctor_id_filter:
            conditions.append("(pa.doctor_id = %s OR pa.patient_id IN (SELECT patient_id FROM appointments WHERE doctor_id = %s))")
            params.extend([doctor_id_filter, doctor_id_filter])

        if patient_id:
            conditions.append("pa.patient_id = %s")
            params.append(patient_id)

        if status:
            conditions.append("pa.status = %s")
            params.append(status.upper())

        if admission_type:
            conditions.append("pa.admission_type = %s")
            params.append(admission_type.upper())

        if admission_date:
            conditions.append("pa.expected_admission_date = %s")
            params.append(admission_date)

        if search and search.strip():
            s = f"%{search.strip().lower()}%"
            conditions.append("""(
                LOWER(pa.pre_admission_code) LIKE %s OR
                LOWER(p.patient_code) LIKE %s OR
                LOWER(p.first_name) LIKE %s OR
                LOWER(p.last_name) LIKE %s OR
                LOWER(p.phone) LIKE %s OR
                LOWER(p.whatsapp_number) LIKE %s
            )""")
            params.extend([s, s, s, s, s, s])

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY pa.expected_admission_date DESC, pa.id DESC;"

        cur.execute(query, params)
        rows = cur.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "pre_admission_code": r[1],
                "patient_id": r[2],
                "patient_code": r[3],
                "patient_name": f"{r[4]} {r[5] or ''}".strip(),
                "patient_phone": r[7] or r[6],
                "doctor_id": r[8],
                "doctor_name": r[9],
                "department_id": r[10],
                "department_name": r[11],
                "appointment_id": r[12],
                "booking_id": r[13],
                "expected_admission_date": str(r[14]),
                "expected_checkin_time": r[15],
                "admission_type": r[16],
                "status": r[17],
                "pending_documents": r[18],
                "submitted_documents": r[19],
                "instructions": r[20],
                "remarks": r[21],
                "created_at": str(r[22]) if r[22] else None,
                "updated_at": str(r[23]) if r[23] else None,
                "notification_status": r[24] or "NOT_SENT"
            })
        return result
    except Exception as e:
        print(f"[ERROR] Failed to query pre-admissions: {e}")
        return []
    finally:
        cur.close()
        conn.close()


def update_pre_admission_status(
    pre_admission_id: int,
    status: Optional[str] = None,
    submitted_documents: Optional[str] = None,
    pending_documents: Optional[str] = None,
    remarks: Optional[str] = None
) -> Dict[str, Any]:
    """Updates pre-admission status and document tracking."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, status FROM pre_admissions WHERE id = %s;", (pre_admission_id,))
        row = cur.fetchone()
        if not row:
            return {"success": False, "error": f"Pre-admission ID {pre_admission_id} not found."}

        updates = []
        params = []
        if status:
            valid_statuses = {"PENDING", "CONTACTED", "CONFIRMED", "DOCUMENTS_PENDING", "READY", "READY_FOR_ADMISSION", "ESCALATED", "COMPLETED", "CANCELLED"}
            st_clean = status.strip().upper()
            if st_clean not in valid_statuses:
                return {"success": False, "error": f"Invalid status '{status}'. Allowed: {list(valid_statuses)}"}
            updates.append("status = %s")
            params.append(st_clean)

        if submitted_documents is not None:
            updates.append("submitted_documents = %s")
            params.append(submitted_documents)

        if pending_documents is not None:
            updates.append("pending_documents = %s")
            params.append(pending_documents)

        if remarks is not None:
            updates.append("remarks = %s")
            params.append(remarks)

        if not updates:
            return {"success": True, "message": "No changes specified."}

        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.append(pre_admission_id)

        sql = f"UPDATE pre_admissions SET {', '.join(updates)} WHERE id = %s;"
        cur.execute(sql, params)
        conn.commit()

        return {"success": True, "message": "Pre-admission updated successfully."}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        cur.close()
        conn.close()


def get_pre_admission_conversation(pre_admission_id: int) -> Dict[str, Any]:
    """Retrieves full WhatsApp conversation history for the patient linked to pre-admission."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT pa.id, pa.pre_admission_code, pa.patient_id, p.first_name, p.last_name, p.whatsapp_number, p.phone
            FROM pre_admissions pa
            JOIN patients p ON pa.patient_id = p.id
            WHERE pa.id = %s;
        """, (pre_admission_id,))
        pa_row = cur.fetchone()
        if not pa_row:
            return {"success": False, "error": "Pre-admission not found"}

        patient_id = pa_row[2]
        pat_name = f"{pa_row[3]} {pa_row[4] or ''}".strip()
        phone = pa_row[5] or pa_row[6]

        # Find conversation record
        cur.execute("""
            SELECT id, conversation_code, language, current_intent, conversation_status, created_at
            FROM conversations
            WHERE patient_id = %s OR whatsapp_number = %s
            ORDER BY id DESC LIMIT 1;
        """, (patient_id, phone))
        conv_row = cur.fetchone()
        if not conv_row:
            return {
                "success": True,
                "pre_admission_id": pre_admission_id,
                "patient_name": pat_name,
                "conversation": None,
                "messages": []
            }

        conv_id = conv_row[0]
        conv_code = conv_row[1]

        cur.execute("""
            SELECT id, sender_type, message_text, intent, language, created_at
            FROM messages
            WHERE conversation_id = %s
            ORDER BY id ASC;
        """, (conv_id,))
        msg_rows = cur.fetchall()

        messages = []
        for m in msg_rows:
            messages.append({
                "id": m[0],
                "sender_type": m[1],
                "message_text": m[2],
                "intent": m[3],
                "language": m[4],
                "timestamp": str(m[5]) if m[5] else None
            })

        return {
            "success": True,
            "pre_admission_id": pre_admission_id,
            "patient_name": pat_name,
            "conversation": {
                "id": conv_id,
                "conversation_code": conv_code,
                "language": conv_row[2],
                "current_intent": conv_row[3],
                "status": conv_row[4],
            },
            "messages": messages
        }
    except Exception as e:
        print(f"[ERROR] Failed to fetch pre-admission conversation: {e}")
        return {"success": False, "error": str(e)}
    finally:
        cur.close()
        conn.close()
