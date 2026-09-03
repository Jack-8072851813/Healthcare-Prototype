import re
import datetime
import sys
import os
from typing import Optional

# Dynamically add the backend path to sys.path if not present
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config

def get_current_kolkata_date() -> datetime.date:
    """Returns the current date in Asia/Kolkata timezone (UTC + 5:30)."""
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

    # 1. today / tomorrow / day after tomorrow (with typo tolerance)
    if re.search(r"day\s+after\s+tom[a-z]*ro[a-z]*w?", text_lower) or re.search(r"after\s+tom[a-z]*ro[a-z]*w?", text_lower):
        return (today + datetime.timedelta(days=2)).strftime("%Y-%m-%d")
    elif re.search(r"\btom[a-z]*ro[a-z]*w?\b", text_lower) or "tmrw" in text_lower:
        return (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    elif "today" in text_lower or "2day" in text_lower:
        return today.strftime("%Y-%m-%d")

    # 2. Weekdays (next Monday, this Friday, Saturday, etc.)
    weekdays_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    for weekday_name, weekday_val in weekdays_map.items():
        if weekday_name in text_lower:
            days_ahead = weekday_val - today.weekday()
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

COMMAND_PHRASES = [
    "book appointment", "confirm appointment", "doctor availability",
    "cancel appointment", "reschedule appointment", "change details",
    "book", "confirm", "cancel", "reschedule", "change", "yes", "no",
    "today", "tomorrow", "first-time patient", "existing patient",
    "same doctor", "that doctor", "same date", "same time", "same slot"
]

def is_command_phrase(text: str) -> bool:
    """Returns True if text is a system command or menu phrase."""
    if not text:
        return False
    t_clean = text.lower().strip()
    return t_clean in COMMAND_PHRASES

def parse_natural_time(text_lower: str) -> Optional[str]:
    """
    Parses natural language time formats and returns HH:MM or None.
    Handles: '10 AM', '10:30', '11:00 am', '5', '5 pm',
             'morning' (09:00), 'afternoon' (14:00), 'evening' (18:00),
             'night' (20:00), 'noon' (12:00).
    """
    if not text_lower:
        return None

    # Named time-of-day blocks (check before digit matching to avoid conflict)
    if re.search(r"\bnoon\b", text_lower):
        return "12:00"
    if re.search(r"\bmidnight\b", text_lower):
        return "00:00"
    if re.search(r"\bmorning\b", text_lower) and not re.search(r"\d", text_lower):
        return "09:00"
    if re.search(r"\bafternoon\b", text_lower) and not re.search(r"\d", text_lower):
        return "14:00"
    if re.search(r"\bevening\b", text_lower) and not re.search(r"\d", text_lower):
        return "18:00"
    if re.search(r"\bnight\b", text_lower) and not re.search(r"\d", text_lower):
        return "20:00"

    # Match standard HH:MM with optional AM/PM
    match_hh_mm = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", text_lower)
    if match_hh_mm:
        hh, mm, ampm = match_hh_mm.groups()
        hh, mm = int(hh), int(mm)
        if ampm == "pm" and hh < 12:
            hh += 12
        elif ampm == "am" and hh == 12:
            hh = 0
        elif not ampm and 1 <= hh <= 5:
            hh += 12
        return f"{hh:02d}:{mm:02d}"

    # Match HH AM/PM (e.g. '10 am', '9 AM', '5pm', '5 pm')
    match_hh_ampm = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text_lower)
    if match_hh_ampm:
        hh, ampm = match_hh_ampm.groups()
        hh = int(hh)
        if ampm == "pm" and hh < 12:
            hh += 12
        elif ampm == "am" and hh == 12:
            hh = 0
        return f"{hh:02d}:00"

    # Match standalone hour digit (e.g. '5', '9', '10', 'at 5')
    match_digit = re.search(r"\b(?:at\s*)?(\d{1,2})\b", text_lower)
    if match_digit:
        hh = int(match_digit.group(1))
        if 1 <= hh <= 5:
            hh += 12  # PM assumption for 1-5
        if 8 <= hh <= 23:
            return f"{hh:02d}:00"

    return None

def is_date_or_time_expression(text: str) -> bool:
    """Returns True if the text represents a date or time expression."""
    if not text:
        return False
    text_lower = text.lower().strip()
    if parse_natural_date(text_lower) is not None or parse_natural_time(text_lower) is not None:
        return True
    time_indicators = [
        "today", "tomorrow", "morning", "afternoon", "evening", "night",
        "am", "pm", "noon", "midnight", "clock",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
    ]
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

        # Match button taps for doctor selection
        match_btn_doc = re.search(r"btn_doc_(\d+)", text_lower)
        if match_btn_doc:
            entities["doctor_id"] = int(match_btn_doc.group(1))

        # Match doctor names
        cur.execute("SELECT id, display_name FROM doctors WHERE status = 'ACTIVE';")
        doctors = cur.fetchall()
        for doc_id, display_name in doctors:
            name_parts = re.findall(r"\b\w+\b", display_name.lower())
            for part in name_parts:
                if len(part) <= 2 or part in ["dr", "dr.", "kumar", "ramesh", "mr", "mrs", "ms"]:
                    continue
                if re.search(r"\b" + re.escape(part) + r"\b", text_lower):
                    entities["doctor_id"] = doc_id
                    break

        # Match department names — ordered from MOST SPECIFIC to LEAST SPECIFIC
        cur.execute("SELECT id, department_name FROM departments WHERE status = 'ACTIVE';")
        departments = cur.fetchall()

        # Build a lookup by name
        dept_by_name = {d[1].lower(): d[0] for d in departments}

        # Try exact department name match first
        for dept_id, department_name in departments:
            dept_name_lower = department_name.lower()
            if re.search(r"\b" + re.escape(dept_name_lower) + r"\b", text_lower):
                entities["department_id"] = dept_id
                break

        # Then keyword-based matching (specific → general order)
        if not entities["department_id"]:
            # Dermatology — MUST check before General Medicine (hair/skin keywords)
            if re.search(
                r"\b(dermatology|dermatologist|skin|hair|scalp|rash|acne|pimple|pimples|"
                r"eczema|psoriasis|hives|dermatitis|hair\s*fall|hair\s*loss|hairfall|"
                r"bald|baldness|thinning\s*hair|itching|itch|allergy|skin\s*infection)\b",
                text_lower
            ):
                did = dept_by_name.get("dermatology")
                if did:
                    entities["department_id"] = did

            # ENT — check before General Medicine
            elif re.search(
                r"\b(ent|ear|earache|ear\s*pain|hearing|sinus|sinus\s*infection|"
                r"nose|nasal|throat|tonsil|snoring|smell|voice|otitis|rhinitis)\b",
                text_lower
            ):
                did = dept_by_name.get("ent")
                if did:
                    entities["department_id"] = did

            # Cardiology — check before General Medicine (chest pain is emergency but also cardiology)
            elif re.search(
                r"\b(cardio|cardiology|cardiologist|heart|cardiac|palpitations|"
                r"breathlessness|chest\s*tightness|blood\s*pressure|hypertension)\b",
                text_lower
            ):
                did = dept_by_name.get("cardiology")
                if did:
                    entities["department_id"] = did

            # Pediatrics — before General Medicine
            elif re.search(
                r"\b(pediatric|pediatrics|pediatrician|child\s*(doctor|specialist)|"
                r"infant|baby|toddler|newborn|kid\s*(doctor|specialist))\b",
                text_lower
            ):
                did = dept_by_name.get("pediatrics")
                if did:
                    entities["department_id"] = did

            # Orthopedics
            elif re.search(
                r"\b(ortho|orthopedics|orthopedist|orthopedic|bone|joint\s*pain|knee|"
                r"spine|back\s*pain|backache|fracture|shoulder|neck\s*pain|arthritis|"
                r"sprain|ligament)\b",
                text_lower
            ):
                did = dept_by_name.get("orthopedics")
                if did:
                    entities["department_id"] = did

            # Neurology
            elif re.search(
                r"\b(neurology|neurologist|migraine|neurological|vertigo|seizure|"
                r"numbness|paralysis|nerve|brain|head\s*injury)\b",
                text_lower
            ):
                did = dept_by_name.get("neurology")
                if did:
                    entities["department_id"] = did

            # Gynecology
            elif re.search(
                r"\b(gynecology|gynecologist|gynaecology|pregnancy|pregnant|period|"
                r"menstrual|menstruation|pelvic|uterine|ovary|women\s*health|reproductive)\b",
                text_lower
            ):
                did = dept_by_name.get("gynecology")
                if did:
                    entities["department_id"] = did

            # General Medicine — LAST (most general)
            elif re.search(
                r"\b(general\s*medicine|general\s*physician|general\s*doctor|"
                r"fever|cold|cough|flu|nausea|vomiting|diarrhea|fatigue|weakness|"
                r"body\s*pain|feverish|infection|ailment|sick|illness|general\s*checkup)\b",
                text_lower
            ):
                did = dept_by_name.get("general medicine")
                if did:
                    entities["department_id"] = did

        # If doctor was found but department wasn't, resolve department from doctor
        if entities["doctor_id"] and not entities["department_id"]:
            cur.execute("SELECT department_id FROM doctors WHERE id = %s;", (entities["doctor_id"],))
            row = cur.fetchone()
            if row:
                entities["department_id"] = row[0]

    finally:
        cur.close()
        conn.close()

    # 4. Extract symptoms/reason
    symptom_keywords = [
        "fever", "cold", "cough", "headache", "pain", "vomiting", "stomach",
        "rash", "dizzy", "dizziness", "hair fall", "hair loss", "acne", "pimples",
        "skin rash", "itching", "eczema", "joint pain", "bone pain", "ear pain",
        "migraine", "chest pain", "pregnancy", "weakness", "fatigue"
    ]
    found_symptoms = [w for w in symptom_keywords if w in text_lower]
    if found_symptoms:
        entities["reason"] = f"Symptoms: {', '.join(found_symptoms)}"
    elif "checkup" in text_lower or "regular checkup" in text_lower:
        entities["reason"] = "Regular Checkup"

    return entities


def map_symptom_to_department_name(text: str) -> str:
    """
    Maps a symptom/disease description to the most appropriate hospital department name.
    Rules are ordered from MOST SPECIFIC to LEAST SPECIFIC to avoid false positives.
    CRITICAL: Dermatology keywords (hair, skin) must be checked BEFORE General Medicine.
    """
    if not text:
        return "General Medicine"
    text_lower = text.lower()

    rules = [
        # 1. DERMATOLOGY — checked FIRST (highest specificity for skin/hair)
        (
            r"\b(hair|hairfall|hair\s*fall|hair\s*loss|hair\s*shedding|hair\s*falling|"
            r"hair\s*problem|hair\s*issue|hair\s*thinning|losing\s*hair|"
            r"bald|baldness|thinning|scalp|dandruff|"
            r"acne|pimple|pimples|blackhead|whitehead|"
            r"skin|rash|itching|itch|eczema|psoriasis|"
            r"allergy|skin\s*infection|hives|dermatitis|"
            r"lesion|wound\s*healing|pigmentation|dark\s*spot|"
            r"dermatology|dermatologist)\b",
            "Dermatology"
        ),
        # 2. PEDIATRICS — checked early (child/baby keywords are specific)
        (
            r"\b(child|baby|infant|toddler|newborn|kid|pediatric|pediatrics|pediatrician|"
            r"my\s*son|my\s*daughter|son\s*(has|have)|daughter\s*(has|have)|"
            r"son\s*fever|daughter\s*fever|child\s*fever|kid\s*fever|baby\s*fever|"
            r"children|my\s*kid|young\s*child)\b",
            "Pediatrics"
        ),
        # 3. CARDIOLOGY — before General Medicine (chest-related)
        (
            r"\b(chest\s*pain|heart|cardio|cardiac|palpitations|breathlessness|"
            r"chest\s*tightness|blood\s*pressure|hypertension|cardiologist|cardiology)\b",
            "Cardiology"
        ),
        # 4. ENT — before General Medicine (ear/nose/throat)
        (
            r"\b(ear|earache|ear\s*pain|hearing|sinus|sinus\s*infection|nasal|"
            r"throat|tonsil|snoring|otitis|rhinitis|ent\s*specialist)\b",
            "ENT"
        ),
        # 5. ORTHOPEDICS — before General Medicine (bone/joint)
        (
            r"\b(joint\s*pain|bone\s*pain|back\s*pain|backache|knee\s*pain|"
            r"spine|fracture|shoulder\s*pain|neck\s*pain|arthritis|sprain|"
            r"ligament|orthopedic|orthopedics|orthopedist)\b",
            "Orthopedics"
        ),
        # 6. NEUROLOGY — before General Medicine (brain/nerve)
        (
            r"\b(migraine|neurological|vertigo|seizure|numbness|paralysis|"
            r"nerve\s*pain|brain|head\s*injury|neurologist|neurology)\b",
            "Neurology"
        ),
        # 7. GYNECOLOGY — women-specific
        (
            r"\b(pregnancy|pregnant|period|menstrual|menstruation|pelvic\s*pain|"
            r"uterine|ovary|women\s*health|reproductive|gynecologist|gynecology)\b",
            "Gynecology"
        ),
        # 8. GENERAL MEDICINE — LAST (most generic)
        (
            r"\b(fever|cold|cough|stomach|flu|nausea|vomiting|diarrhea|fatigue|"
            r"weakness|body\s*pain|feverish|pain|infection|ailment|sick|illness|"
            r"general\s*checkup|headache|runny\s*nose|sneezing|sore\s*throat)\b",
            "General Medicine"
        ),
    ]

    for pattern, dept_name in rules:
        if re.search(pattern, text_lower):
            return dept_name

    return "General Medicine"


def extract_relationship(text: str) -> dict:
    """
    Extracts dependent patient relationship information from patient message.
    Returns dict with 'appointment_for' and 'relationship' keys.
    """
    text_lower = text.lower()
    result = {"appointment_for": None, "relationship": None}

    if re.search(r"\b(for\s*my\s*son|my\s*son\s*(has|have|is|needs|want))\b", text_lower):
        result["appointment_for"] = "CHILD"
        result["relationship"] = "SON"
    elif re.search(r"\b(for\s*my\s*daughter|my\s*daughter\s*(has|have|is|needs|want))\b", text_lower):
        result["appointment_for"] = "CHILD"
        result["relationship"] = "DAUGHTER"
    elif re.search(r"\b(for\s*my\s*(child|kid|baby)|my\s*(child|kid|baby)\s*(has|have|is))\b", text_lower):
        result["appointment_for"] = "CHILD"
        result["relationship"] = "CHILD"
    elif re.search(r"\b(for\s*my\s*(wife|spouse)|my\s*(wife|spouse)\s*(has|have|is))\b", text_lower):
        result["appointment_for"] = "FAMILY_MEMBER"
        result["relationship"] = "SPOUSE"
    elif re.search(r"\b(for\s*my\s*husband|my\s*husband\s*(has|have|is))\b", text_lower):
        result["appointment_for"] = "FAMILY_MEMBER"
        result["relationship"] = "SPOUSE"
    elif re.search(r"\b(for\s*my\s*(mother|mom)|my\s*(mother|mom)\s*(has|have|is))\b", text_lower):
        result["appointment_for"] = "FAMILY_MEMBER"
        result["relationship"] = "MOTHER"
    elif re.search(r"\b(for\s*my\s*(father|dad)|my\s*(father|dad)\s*(has|have|is))\b", text_lower):
        result["appointment_for"] = "FAMILY_MEMBER"
        result["relationship"] = "FATHER"
    elif re.search(r"\b(for\s*my\s*(sister|brother)|my\s*(sister|brother)\s*(has|have|is))\b", text_lower):
        result["appointment_for"] = "FAMILY_MEMBER"
        result["relationship"] = "SIBLING"
    elif re.search(r"\b(for\s*my\s*(family|relative|dependent|family\s*member))\b", text_lower):
        result["appointment_for"] = "FAMILY_MEMBER"
        result["relationship"] = "DEPENDENT"
    elif re.search(r"\b(myself|for\s*me|my\s*appointment)\b", text_lower):
        result["appointment_for"] = "SELF"

    return result
