import re
import datetime
import sys
import os

# Dynamically add the backend path to sys.path if not present
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config

def get_current_kolkata_date() -> datetime.date:
    """Returns the current date in Asia/Kolkata timezone (UTC + 5:30)."""
    # Since the server OS local time is running in UTC or user's local timezone, 
    # we calculate Kolkata time explicitly.
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    kolkata_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    kolkata_now = utc_now.astimezone(kolkata_tz)
    return kolkata_now.date()

def parse_natural_date(text_lower: str) -> str:
    """
    Parses natural language date phrases relative to Asia/Kolkata timezone.
    Returns YYYY-MM-DD or None.
    """
    today = get_current_kolkata_date()
    
    # 1. today / tomorrow / day after tomorrow
    if "day after tomorrow" in text_lower:
        return (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    elif "tomorrow" in text_lower:
        return (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    elif "today" in text_lower:
        return today.strftime("%Y-%m-%d")
        
    # 2. Weekdays
    weekdays_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    
    for weekday_name, weekday_val in weekdays_map.items():
        if weekday_name in text_lower:
            days_ahead = weekday_val - today.weekday()
            # If the weekday has already occurred this week (or is today), pick next week's
            if "next" in text_lower:
                if days_ahead <= 0:
                    days_ahead += 7
                days_ahead += 7
            else:
                if days_ahead <= 0:
                    days_ahead += 7
            return (today + datetime.timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            
    # 3. YYYY-MM-DD match
    match_date = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text_lower)
    if match_date:
        return match_date.group(0)
        
    # 4. DD-MM-YYYY or DD/MM/YYYY match
    match_date_short = re.search(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", text_lower)
    if match_date_short:
        d, m, y = match_date_short.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    return None

def parse_natural_time(text_lower: str) -> str:
    """
    Parses natural language time formats (e.g. '10 AM', '10:30', '11:00 am') 
    and returns HH:MM or None.
    """
    # Match standard HH:MM
    match_hh_mm = re.search(r"\b(\d{1,2}):(\d{2})\b", text_lower)
    if match_hh_mm:
        hh, mm = match_hh_mm.groups()
        hh = int(hh)
        # Handle AM/PM suffix if present later in the string
        if "pm" in text_lower and hh < 12:
            hh += 12
        elif "am" in text_lower and hh == 12:
            hh = 0
        return f"{hh:02d}:{mm}"
        
    # Match HH AM/PM (e.g. '10 am', '9 AM')
    match_hh_ampm = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text_lower)
    if match_hh_ampm:
        hh, ampm = match_hh_ampm.groups()
        hh = int(hh)
        if ampm == "pm" and hh < 12:
            hh += 12
        elif ampm == "am" and hh == 12:
            hh = 0
        return f"{hh:02d}:00"
        
    # Match numbers like "9" or "10" if preceded by "at" (e.g. "at 10")
    match_at_number = re.search(r"\bat\s*(\d{1,2})\b", text_lower)
    if match_at_number:
        hh = int(match_at_number.group(1))
        # If it is standard business hours 9 to 12, assume AM. 1 to 5 assume PM
        if 1 <= hh <= 5:
            hh += 12
        if 9 <= hh <= 23:
            return f"{hh:02d}:00"
            
    return None


def is_date_or_time_expression(text: str) -> bool:
    """Returns True if the text represents a date or time expression."""
    if not text:
        return False
    text_lower = text.lower().strip()
    if parse_natural_date(text_lower) is not None or parse_natural_time(text_lower) is not None:
        return True
    time_indicators = ["today", "tomorrow", "morning", "afternoon", "evening", "am", "pm", "clock", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    return any(w in text_lower for w in time_indicators)

def extract_entities(text: str) -> dict:
    """
    Scans user text and resolves entities dynamically against the database:
    - doctor_id
    - department_id
    - appointment_date
    - appointment_time
    - booking_id
    - patient_id
    - reason
    """
    text_lower = text.lower().strip()
    entities = {
        "doctor_id": None,
        "department_id": None,
        "appointment_date": None,
        "appointment_time": None,
        "booking_id": None,
        "patient_id": None,
        "reason": None
    }
    
    # 1. Regex matches for Booking ID
    match_bk = re.search(r"\b(apt\d+|test_bk_\w+|bk\d+)\b", text_lower)
    if match_bk:
        entities["booking_id"] = match_bk.group(1).upper()
        
    # 2. Parse Date and Time
    entities["appointment_date"] = parse_natural_date(text_lower)
    entities["appointment_time"] = parse_natural_time(text_lower)
    
    # 3. Connect to DB to check for patient, doctor, and department names
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        # Match patient code (e.g. 'P001', 'P1001')
        match_pat = re.search(r"\b(p\d+)\b", text_lower)
        if match_pat:
            pat_code = match_pat.group(1).upper()
            cur.execute("SELECT id FROM patients WHERE patient_code = %s AND status = 'ACTIVE';", (pat_code,))
            row = cur.fetchone()
            if row:
                entities["patient_id"] = row[0]
                
        # Match doctor names
        cur.execute("SELECT id, display_name FROM doctors WHERE status = 'ACTIVE';")
        doctors = cur.fetchall()
        for doc_id, display_name in doctors:
            # Check for name parts (e.g. 'Arun', 'Priya', 'Ramesh')
            name_parts = re.findall(r"\b\w+\b", display_name.lower())
            for part in name_parts:
                if part in ["dr", "dr.", "kumar", "ramesh"]:
                    continue # Skip common titles and generic names if they stand alone
                if part in text_lower:
                    entities["doctor_id"] = doc_id
                    break
                    
        # Match department names
        cur.execute("SELECT id, department_name FROM departments WHERE status = 'ACTIVE';")
        departments = cur.fetchall()
        for dept_id, department_name in departments:
            dept_name_lower = department_name.lower()
            # If name is "General Medicine", also check for "general medicine" or "medicine"
            if re.search(r"\b" + re.escape(dept_name_lower) + r"\b", text_lower):
                entities["department_id"] = dept_id
                break
            elif "general" in dept_name_lower and re.search(r"\bgeneral\b", text_lower):
                entities["department_id"] = dept_id
                break
            elif "cardiology" in dept_name_lower and re.search(r"\b(cardio|cardiology|cardiologist|cardialogist|heart\s*doctor|heart\s*specialist|cardiac\s*doctor)\b", text_lower):
                entities["department_id"] = dept_id
                break
            elif "pediatrics" in dept_name_lower and re.search(r"\b(pediatric|pediatrics)\b", text_lower):
                entities["department_id"] = dept_id
                break
                
        # If doctor was found, but department wasn't, resolve department from doctor
        if entities["doctor_id"] and not entities["department_id"]:
            cur.execute("SELECT department_id FROM doctors WHERE id = %s;", (entities["doctor_id"],))
            row = cur.fetchone()
            if row:
                entities["department_id"] = row[0]
                
    finally:
        cur.close()
        conn.close()
        
    # 4. Extract symptoms/reason if booking or symptom guidance is detected
    symptom_keywords = ["fever", "cold", "cough", "headache", "pain", "vomiting", "stomach", "rash", "dizzy", "dizziness"]
    found_symptoms = [w for w in symptom_keywords if w in text_lower]
    if found_symptoms:
        entities["reason"] = f"Symptoms: {', '.join(found_symptoms)}"
    elif "checkup" in text_lower or "regular checkup" in text_lower:
        entities["reason"] = "Regular Checkup"
        
    return entities
