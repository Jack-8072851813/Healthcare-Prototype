import datetime
import random
import json
import psycopg2
import db_config

# Custom Exception Classes for Business Logic Errors
class AppointmentError(Exception):
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "APPOINTMENT_ERROR"

class EntityNotFoundError(AppointmentError):
    pass

class DoctorInactiveError(AppointmentError):
    pass

class InvalidScheduleError(AppointmentError):
    pass

class PastDateError(AppointmentError):
    pass

class SlotUnavailableError(AppointmentError):
    pass

class InvalidStatusTransitionError(AppointmentError):
    pass

# --- Validation Helpers ---

def validate_patient(cur, patient_id):
    """Checks if the patient exists and is active."""
    cur.execute("SELECT first_name, last_name, phone, whatsapp_number, status FROM patients WHERE id = %s;", (patient_id,))
    row = cur.fetchone()
    if not row:
        raise EntityNotFoundError(f"Patient with ID {patient_id} does not exist.", "PATIENT_NOT_FOUND")
    first_name, last_name, phone, whatsapp, status = row
    if status != 'ACTIVE':
        raise AppointmentError(f"Patient with ID {patient_id} is inactive.", "PATIENT_INACTIVE")
    return {"name": f"{first_name} {last_name}", "phone": phone, "whatsapp_number": whatsapp}

def validate_doctor(cur, doctor_id):
    """Checks if the doctor exists and is active."""
    cur.execute("SELECT first_name, last_name, display_name, department_id, status, email, phone FROM doctors WHERE id = %s;", (doctor_id,))
    row = cur.fetchone()
    if not row:
        raise EntityNotFoundError(f"Doctor with ID {doctor_id} does not exist.", "DOCTOR_NOT_FOUND")
    first_name, last_name, display_name, department_id, status, email, phone = row
    if status != 'ACTIVE':
        raise DoctorInactiveError(f"Doctor with ID {doctor_id} is currently not active.", "DOCTOR_INACTIVE")
    return {"name": display_name, "department_id": department_id, "email": email, "phone": phone}

def validate_department(cur, department_id):
    """Checks if the department exists and is active."""
    cur.execute("SELECT department_name, status FROM departments WHERE id = %s;", (department_id,))
    row = cur.fetchone()
    if not row:
        raise EntityNotFoundError(f"Department with ID {department_id} does not exist.", "DEPARTMENT_NOT_FOUND")
    name, status = row
    if status != 'ACTIVE':
        raise AppointmentError(f"Department with ID {department_id} is inactive.", "DEPARTMENT_INACTIVE")
    return name

def validate_past_datetime(date_obj, time_obj):
    """Ensures that the date and time of the appointment are not in the past."""
    appt_dt = datetime.datetime.combine(date_obj, time_obj)
    if appt_dt < datetime.datetime.now():
        raise PastDateError("The requested appointment slot is in the past.", "APPOINTMENT_DATE_PAST")

# --- Slot Generation ---

def generate_slots(start_time, end_time, duration_minutes):
    """Generates a list of time objects between start_time and end_time incremented by duration_minutes."""
    slots = []
    dummy_date = datetime.date(2000, 1, 1)
    current_dt = datetime.datetime.combine(dummy_date, start_time)
    end_dt = datetime.datetime.combine(dummy_date, end_time)
    delta = datetime.timedelta(minutes=duration_minutes)
    
    while current_dt < end_dt:
        slots.append(current_dt.time())
        current_dt += delta
    return slots

def get_doctor_schedule_for_date(cur, doctor_id, date_obj):
    """Queries and returns the active schedule of the doctor for the weekday of date_obj."""
    day_name = date_obj.strftime("%A").upper()
    cur.execute("""
        SELECT start_time, end_time, slot_duration_minutes
        FROM doctor_schedules
        WHERE doctor_id = %s
          AND day_of_week = %s
          AND status = 'ACTIVE'
          AND effective_from <= %s
          AND (effective_to IS NULL OR effective_to >= %s);
    """, (doctor_id, day_name, date_obj, date_obj))
    row = cur.fetchone()
    if not row:
        return None
    return {"start_time": row[0], "end_time": row[1], "slot_duration": row[2]}

# --- Service Operations ---

def get_doctor_availability(doctor_id, date_str):
    """
    Checks if a doctor is scheduled and available on a date.
    Returns details if available, else raises InvalidScheduleError.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Verify doctor exists and is active
        doc_info = validate_doctor(cur, doctor_id)
        
        # Parse date
        if not date_str or not isinstance(date_str, str):
            raise AppointmentError("Appointment date is required (YYYY-MM-DD).", "INVALID_DATE_FORMAT")
        try:
            date_obj = datetime.datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise AppointmentError("Invalid date format. Use YYYY-MM-DD.", "INVALID_DATE_FORMAT")
            
        schedule = get_doctor_schedule_for_date(cur, doctor_id, date_obj)
        if not schedule:
            raise InvalidScheduleError("Doctor is not scheduled on this day.", "DOCTOR_NOT_AVAILABLE")
            
        return {
            "available": True,
            "doctor": doc_info["name"],
            "start_time": schedule["start_time"].strftime("%H:%M"),
            "end_time": schedule["end_time"].strftime("%H:%M"),
            "slot_duration": schedule["slot_duration"]
        }
    finally:
        cur.close()
        conn.close()

def get_available_slots(doctor_id, date_str):
    """
    Generates all available appointment slots for a doctor on a date.
    Filters out slots that have already been booked.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Check doctor
        validate_doctor(cur, doctor_id)
        
        # Parse date
        if not date_str or not isinstance(date_str, str):
            return []
        try:
            date_obj = datetime.datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return []
            
        schedule = get_doctor_schedule_for_date(cur, doctor_id, date_obj)
        if not schedule:
            return []
            
        # Generate all slot times
        all_slots = generate_slots(schedule["start_time"], schedule["end_time"], schedule["slot_duration"])
        all_slots_str = [s.strftime("%H:%M") for s in all_slots]
        
        # Fetch booked slots
        cur.execute("""
            SELECT appointment_time
            FROM appointments
            WHERE doctor_id = %s
              AND appointment_date = %s
              AND status NOT IN ('CANCELLED', 'RESCHEDULED');
        """, (doctor_id, date_obj))
        booked_times = {row[0].strftime("%H:%M") for row in cur.fetchall()}
        
        # Filter available slots
        available = [s for s in all_slots_str if s not in booked_times]
        return available
    finally:
        cur.close()
        conn.close()

def generate_booking_id(cur):
    """Helper to generate a unique booking ID."""
    for _ in range(10):
        b_id = f"APT{random.randint(10000, 99999)}"
        cur.execute("SELECT 1 FROM appointments WHERE booking_id = %s;", (b_id,))
        if not cur.fetchone():
            return b_id
    raise AppointmentError("Failed to generate a unique booking ID.", "BOOKING_ID_GENERATION_FAILED")

def book_appointment(patient_id, doctor_id, department_id, date_str, time_str, patient_reason=None, booking_source="ADMIN", created_by_user_id=None):
    """
    Creates an appointment. Runs all validation checks transactionally
    and utilizes row-level locking + unique index validation.
    """
    # Standard source validation
    valid_sources = {"WHATSAPP_TEXT", "WHATSAPP_VOICE", "ADMIN", "DOCTOR"}
    if booking_source not in valid_sources:
        raise AppointmentError(f"Invalid booking source. Must be one of {valid_sources}", "INVALID_BOOKING_SOURCE")

    conn = db_config.get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        # 1. Base Validations
        pat_info = validate_patient(cur, patient_id)
        doc_info = validate_doctor(cur, doctor_id)
        dept_name = validate_department(cur, department_id)
        
        # Doctor department mismatch
        if doc_info["department_id"] != department_id:
            raise AppointmentError("Doctor does not belong to the selected department.", "DOCTOR_DEPARTMENT_MISMATCH")
            
        # Validate created_by_user_id exists
        if created_by_user_id:
            cur.execute("SELECT 1 FROM users WHERE id = %s AND is_active = true;", (created_by_user_id,))
            if not cur.fetchone():
                raise EntityNotFoundError(f"User with ID {created_by_user_id} does not exist or is inactive.", "USER_NOT_FOUND")
            
        # Parse inputs
        if not date_str or not isinstance(date_str, str):
            raise AppointmentError("Appointment date is required (YYYY-MM-DD).", "INVALID_DATE_FORMAT")
        if not time_str or not isinstance(time_str, str):
            raise AppointmentError("Appointment time is required (HH:MM).", "INVALID_TIME_FORMAT")

        try:
            date_obj = datetime.datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise AppointmentError("Invalid date format. Use YYYY-MM-DD.", "INVALID_DATE_FORMAT")
        try:
            clean_t = time_str.strip()
            if len(clean_t) == 5:
                time_obj = datetime.datetime.strptime(clean_t, "%H:%M").time()
            else:
                time_obj = datetime.datetime.strptime(clean_t, "%H:%M:%S").time()
        except (ValueError, TypeError):
            raise AppointmentError("Invalid time format. Use HH:MM.", "INVALID_TIME_FORMAT")
            
        # Past check
        validate_past_datetime(date_obj, time_obj)
        
        # 2. Working hours and slots check
        schedule = get_doctor_schedule_for_date(cur, doctor_id, date_obj)
        if not schedule:
            raise InvalidScheduleError("Doctor is not scheduled to work on this day.", "DOCTOR_NOT_AVAILABLE")
            
        valid_slots = generate_slots(schedule["start_time"], schedule["end_time"], schedule["slot_duration"])
        if time_obj not in valid_slots:
            raise InvalidScheduleError("The requested time does not match a valid appointment slot duration.", "INVALID_APPOINTMENT_SLOT")
            
        # 3. Race condition prevention via row-level locks
        cur.execute("""
            SELECT id FROM appointments 
            WHERE doctor_id = %s 
              AND appointment_date = %s 
              AND appointment_time = %s 
              AND status NOT IN ('CANCELLED', 'RESCHEDULED')
            FOR UPDATE;
        """, (doctor_id, date_obj, time_obj))
        if cur.fetchone():
            raise SlotUnavailableError("The selected appointment slot is no longer available.", "APPOINTMENT_SLOT_UNAVAILABLE")
            
        # 4. Generate unique ID and insert
        booking_id = generate_booking_id(cur)
        status_val = "CONFIRMED"
        print(f"[BOOKING_TRANSACTION] Inserting appointment into PostgreSQL: booking_id={booking_id}, patient_id={patient_id}, doctor_id={doctor_id}, department_id={department_id}, date={date_obj}, time={time_obj}, status={status_val}, source={booking_source}")
        cur.execute("""
            INSERT INTO appointments (
                booking_id, patient_id, doctor_id, department_id, 
                appointment_date, appointment_time, status, booking_source, 
                patient_reason, created_by_user_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (booking_id, patient_id, doctor_id, department_id, date_obj, time_obj, status_val, booking_source, patient_reason, created_by_user_id))
        appt_id = cur.fetchone()[0]
        
        # 5. Audit Logging (if booked by Admin/Doctor)
        if created_by_user_id:
            new_vals = {
                "booking_id": booking_id,
                "patient_id": patient_id,
                "doctor_id": doctor_id,
                "appointment_date": str(date_obj),
                "appointment_time": time_obj.strftime("%H:%M"),
                "status": status_val
            }
            cur.execute("""
                INSERT INTO audit_logs (user_id, action, entity_type, entity_id, new_values, reason)
                VALUES (%s, 'CREATE_APPOINTMENT', 'appointments', %s, %s, %s);
            """, (created_by_user_id, appt_id, json.dumps(new_vals), f"Appointment booked via {booking_source}"))
            
        # 6. Notification placeholder
        notification_message = f"Dear {pat_info['name']}, your appointment with {doc_info['name']} in the {dept_name} department is confirmed for {date_str} at {time_obj.strftime('%I:%M %p')}."
        cur.execute("""
            INSERT INTO notifications (patient_id, appointment_id, notification_type, channel, message, status)
            VALUES (%s, %s, 'APPOINTMENT_CONFIRMED', 'WHATSAPP', %s, 'PENDING');
        """, (patient_id, appt_id, notification_message))
        
        # Commit transaction
        conn.commit()
        print(f"[BOOKING_TRANSACTION] Successfully committed appointment ID {appt_id} (Booking ID: {booking_id}) to PostgreSQL database.")

        # Dispatch email alert to doctor asynchronously in background thread
        def _send_async_doctor_email():
            try:
                from utils.email_service import send_appointment_notification_email
                doc_email = doc_info.get("email")
                if doc_email:
                    send_appointment_notification_email(
                        doctor_email=doc_email,
                        doctor_name=doc_info["name"],
                        patient_name=pat_info["name"],
                        patient_phone=pat_info.get("phone", ""),
                        appointment_date=str(date_obj),
                        appointment_time=time_obj.strftime("%I:%M %p"),
                        department_name=dept_name,
                        booking_id=booking_id
                    )
            except Exception as email_err:
                print(f"[WARNING] Could not dispatch doctor notification email: {email_err}")

        import threading
        threading.Thread(target=_send_async_doctor_email, daemon=True).start()
        
        return {
            "success": True,
            "booking_id": booking_id,
            "appointment_id": appt_id,
            "status": status_val,
            "doctor": doc_info["name"],
            "department": dept_name,
            "appointment_date": str(date_obj),
            "appointment_time": time_obj.strftime("%H:%M")
        }
        
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise SlotUnavailableError("The selected appointment slot is no longer available.", "APPOINTMENT_SLOT_UNAVAILABLE")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def get_appointment(booking_id, patient_id=None):
    """
    Retrieves appointment details by booking ID.
    If patient_id is provided, checks patient ownership.
    """
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                a.id, a.booking_id, a.patient_id, a.doctor_id, a.department_id,
                a.appointment_date, a.appointment_time, a.status, a.patient_reason, a.created_at,
                p.first_name || ' ' || p.last_name AS patient_name,
                d.display_name AS doctor_name,
                dept.department_name
            FROM appointments a
            JOIN patients p ON a.patient_id = p.id
            JOIN doctors d ON a.doctor_id = d.id
            JOIN departments dept ON a.department_id = dept.id
            WHERE a.booking_id = %s;
        """, (booking_id,))
        row = cur.fetchone()
        if not row:
            raise EntityNotFoundError(f"Appointment with booking ID {booking_id} not found.", "APPOINTMENT_NOT_FOUND")
            
        a_id, b_id, pat_id, doc_id, dept_id, app_date, app_time, status, reason, created_at, pat_name, doc_name, dept_name = row
        
        # Ownership check
        if patient_id and int(pat_id) != int(patient_id):
            raise AppointmentError("Access denied: You cannot access another patient's appointment details.", "ACCESS_DENIED")
            
        return {
            "appointment_id": a_id,
            "booking_id": b_id,
            "patient_id": pat_id,
            "patient_name": pat_name,
            "doctor_id": doc_id,
            "doctor_name": doc_name,
            "department_id": dept_id,
            "department_name": dept_name,
            "appointment_date": str(app_date),
            "appointment_time": app_time.strftime("%H:%M"),
            "status": status,
            "reason": reason,
            "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
    finally:
        cur.close()
        conn.close()

def get_patient_appointments(patient_id):
    """Lists all appointments for a given patient."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT 
                a.booking_id, a.status, a.appointment_date, a.appointment_time,
                d.display_name AS doctor_name,
                dept.department_name
            FROM appointments a
            JOIN doctors d ON a.doctor_id = d.id
            JOIN departments dept ON a.department_id = dept.id
            WHERE a.patient_id = %s
            ORDER BY a.appointment_date DESC, a.appointment_time DESC;
        """, (patient_id,))
        rows = cur.fetchall()
        
        appointments = []
        for r in rows:
            appointments.append({
                "booking_id": r[0],
                "status": r[1],
                "appointment_date": str(r[2]),
                "appointment_time": r[3].strftime("%H:%M"),
                "doctor_name": r[4],
                "department_name": r[5]
            })
        return appointments
    finally:
        cur.close()
        conn.close()

def cancel_appointment(booking_id, reason, cancelled_by_user_id=None):
    """
    Cancels an active appointment, updates status to CANCELLED,
    records auditing data, and registers WhatsApp notification placeholder.
    """
    if not reason or not reason.strip():
        raise AppointmentError("A cancellation reason is mandatory.", "CANCELLATION_REASON_REQUIRED")
        
    conn = db_config.get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        # Lock the row
        cur.execute("""
            SELECT id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status 
            FROM appointments 
            WHERE booking_id = %s 
            FOR UPDATE;
        """, (booking_id,))
        row = cur.fetchone()
        if not row:
            raise EntityNotFoundError(f"Appointment with booking ID {booking_id} not found.", "APPOINTMENT_NOT_FOUND")
            
        appt_id, patient_id, doctor_id, department_id, appt_date, appt_time, status = row
        
        # Validate cancelled_by_user_id exists
        if cancelled_by_user_id:
            cur.execute("SELECT 1 FROM users WHERE id = %s AND is_active = true;", (cancelled_by_user_id,))
            if not cur.fetchone():
                raise EntityNotFoundError(f"User with ID {cancelled_by_user_id} does not exist or is inactive.", "USER_NOT_FOUND")
        
        # Check eligibility
        if status == 'CANCELLED':
            raise InvalidStatusTransitionError("Appointment is already cancelled.", "APPOINTMENT_ALREADY_CANCELLED")
        if status == 'COMPLETED':
            raise InvalidStatusTransitionError("Completed appointments cannot be cancelled.", "APPOINTMENT_ALREADY_COMPLETED")
            
        # Fetch names for message formatting
        cur.execute("SELECT first_name, last_name FROM patients WHERE id = %s;", (patient_id,))
        pat_row = cur.fetchone()
        pat_name = f"{pat_row[0]} {pat_row[1]}" if pat_row else "Patient"
        
        cur.execute("SELECT display_name FROM doctors WHERE id = %s;", (doctor_id,))
        doc_row = cur.fetchone()
        doc_name = doc_row[0] if doc_row else "Doctor"
        
        # Update row status
        cur.execute("""
            UPDATE appointments
            SET status = 'CANCELLED',
                cancellation_reason = %s,
                cancelled_by_user_id = %s,
                cancelled_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (reason, cancelled_by_user_id, appt_id))
        
        # Write Audit Log
        old_vals = {"status": status}
        new_vals = {"status": "CANCELLED", "cancellation_reason": reason}
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, old_values, new_values, reason)
            VALUES (%s, 'CANCEL_APPOINTMENT', 'appointments', %s, %s, %s, %s);
        """, (cancelled_by_user_id, appt_id, json.dumps(old_vals), json.dumps(new_vals), "Appointment cancellation"))
        
        # Create Patient Notification record
        formatted_date = appt_date.strftime("%d %B")
        notification_message = f"Your appointment with {doc_name} on {formatted_date} at {appt_time.strftime('%I:%M %p')} has been cancelled because {reason.strip()}."
        cur.execute("""
            INSERT INTO notifications (patient_id, appointment_id, notification_type, channel, message, reason, status)
            VALUES (%s, %s, 'APPOINTMENT_CANCELLED', 'WHATSAPP', %s, %s, 'PENDING');
        """, (patient_id, appt_id, notification_message, reason))
        
        # Commit transaction
        conn.commit()
        
        return {
            "success": True,
            "booking_id": booking_id,
            "status": "CANCELLED",
            "reason": reason
        }
        
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()

def reschedule_appointment(booking_id, new_date_str, new_time_str, reason, rescheduled_by_user_id=None):
    """
    Reschedules an active appointment to a new date/time slot.
    Checks availability and locks the new slot transactionally.
    """
    if not reason or not reason.strip():
        raise AppointmentError("A rescheduling reason is mandatory.", "RESCHEDULE_REASON_REQUIRED")
        
    conn = db_config.get_db_connection()
    conn.autocommit = False
    cur = conn.cursor()
    
    try:
        # 1. Fetch and Lock existing row
        cur.execute("""
            SELECT id, patient_id, doctor_id, department_id, appointment_date, appointment_time, status 
            FROM appointments 
            WHERE booking_id = %s 
            FOR UPDATE;
        """, (booking_id,))
        row = cur.fetchone()
        if not row:
            raise EntityNotFoundError(f"Appointment with booking ID {booking_id} not found.", "APPOINTMENT_NOT_FOUND")
            
        appt_id, patient_id, doctor_id, department_id, old_date, old_time, status = row
        
        # Validate rescheduled_by_user_id exists
        if rescheduled_by_user_id:
            cur.execute("SELECT 1 FROM users WHERE id = %s AND is_active = true;", (rescheduled_by_user_id,))
            if not cur.fetchone():
                raise EntityNotFoundError(f"User with ID {rescheduled_by_user_id} does not exist or is inactive.", "USER_NOT_FOUND")
        
        # Check eligibility
        if status == 'CANCELLED':
            raise InvalidStatusTransitionError("Cancelled appointments cannot be rescheduled.", "APPOINTMENT_CANCELLED_CANNOT_RESCHEDULE")
        if status == 'COMPLETED':
            raise InvalidStatusTransitionError("Completed appointments cannot be rescheduled.", "APPOINTMENT_COMPLETED_CANNOT_RESCHEDULE")
            
        # Parse inputs
        if not new_date_str or not isinstance(new_date_str, str):
            raise AppointmentError("New appointment date is required (YYYY-MM-DD).", "INVALID_DATE_FORMAT")
        if not new_time_str or not isinstance(new_time_str, str):
            raise AppointmentError("New appointment time is required (HH:MM).", "INVALID_TIME_FORMAT")

        try:
            new_date_obj = datetime.datetime.strptime(new_date_str.strip(), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            raise AppointmentError("Invalid date format. Use YYYY-MM-DD.", "INVALID_DATE_FORMAT")
        try:
            clean_t = new_time_str.strip()
            if len(clean_t) == 5:
                new_time_obj = datetime.datetime.strptime(clean_t, "%H:%M").time()
            else:
                new_time_obj = datetime.datetime.strptime(clean_t, "%H:%M:%S").time()
        except (ValueError, TypeError):
            raise AppointmentError("Invalid time format. Use HH:MM.", "INVALID_TIME_FORMAT")
            
        # Past check
        validate_past_datetime(new_date_obj, new_time_obj)
        
        # Verify doctor is active
        doc_info = validate_doctor(cur, doctor_id)
        pat_info = validate_patient(cur, patient_id)
        
        # 2. Check schedule working hours for new date
        schedule = get_doctor_schedule_for_date(cur, doctor_id, new_date_obj)
        if not schedule:
            raise InvalidScheduleError("Doctor is not scheduled to work on the selected reschedule date.", "DOCTOR_NOT_AVAILABLE")
            
        valid_slots = generate_slots(schedule["start_time"], schedule["end_time"], schedule["slot_duration"])
        if new_time_obj not in valid_slots:
            raise InvalidScheduleError("The requested time does not match a valid appointment slot duration.", "INVALID_APPOINTMENT_SLOT")
            
        # 3. Concurrency check on new slot (ignoring our current row ID)
        cur.execute("""
            SELECT id FROM appointments 
            WHERE doctor_id = %s 
              AND appointment_date = %s 
              AND appointment_time = %s 
              AND status NOT IN ('CANCELLED', 'RESCHEDULED')
              AND id <> %s
            FOR UPDATE;
        """, (doctor_id, new_date_obj, new_time_obj, appt_id))
        if cur.fetchone():
            raise SlotUnavailableError("The selected appointment slot is no longer available.", "APPOINTMENT_SLOT_UNAVAILABLE")
            
        # 4. Update the row details directly (releases old slot, blocks new slot under same ID)
        cur.execute("""
            UPDATE appointments
            SET appointment_date = %s,
                appointment_time = %s,
                reschedule_reason = %s,
                rescheduled_by_user_id = %s,
                rescheduled_at = CURRENT_TIMESTAMP
            WHERE id = %s;
        """, (new_date_obj, new_time_obj, reason, rescheduled_by_user_id, appt_id))
        
        # 5. Write Audit Log
        old_vals = {
            "appointment_date": str(old_date),
            "appointment_time": old_time.strftime("%H:%M")
        }
        new_vals = {
            "appointment_date": str(new_date_obj),
            "appointment_time": new_time_obj.strftime("%H:%M"),
            "reschedule_reason": reason
        }
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, entity_type, entity_id, old_values, new_values, reason)
            VALUES (%s, 'RESCHEDULE_APPOINTMENT', 'appointments', %s, %s, %s, %s);
        """, (rescheduled_by_user_id, appt_id, json.dumps(old_vals), json.dumps(new_vals), "Appointment rescheduled"))
        
        # 6. Create Patient Notification record
        formatted_date = new_date_obj.strftime("%d %B")
        notification_message = f"Your appointment with {doc_info['name']} has been rescheduled to {formatted_date} at {new_time_obj.strftime('%I:%M %p')}. Reason: {reason.strip()}."
        cur.execute("""
            INSERT INTO notifications (patient_id, appointment_id, notification_type, channel, message, reason, status)
            VALUES (%s, %s, 'APPOINTMENT_RESCHEDULED', 'WHATSAPP', %s, %s, 'PENDING');
        """, (patient_id, appt_id, notification_message, reason))
        
        # Commit transaction
        conn.commit()
        
        return {
            "success": True,
            "booking_id": booking_id,
            "status": "RESCHEDULED",
            "new_date": str(new_date_obj),
            "new_time": new_time_obj.strftime("%H:%M"),
            "reason": reason
        }
        
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise SlotUnavailableError("The selected appointment slot is no longer available.", "APPOINTMENT_SLOT_UNAVAILABLE")
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()
