"""
date_normalizer.py
==================
Date and Date of Birth (DOB) normalization, parsing, ambiguity detection,
and validation for Meridian Hospital AI Patient Desk.
"""

import re
import datetime
from typing import Tuple, Optional


def get_current_kolkata_date() -> datetime.date:
    """Returns current date in Asia/Kolkata timezone (UTC+5:30)."""
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    kolkata_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    return utc_now.astimezone(kolkata_tz).date()


MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12
}


def parse_and_normalize_date(text: str, reference_date: Optional[datetime.date] = None) -> Tuple[Optional[str], bool, Optional[str]]:
    """
    Parses natural language date strings and normalizes to YYYY-MM-DD.

    Returns:
        (normalized_date_str, is_ambiguous, error_message)
    """
    if not text:
        return None, False, None

    if reference_date is None:
        reference_date = get_current_kolkata_date()

    text_clean = text.lower().strip()

    # 1. Relative dates (with typo tolerance for tomrmorrow, tommorow, etc.)
    if re.search(r"day\s+after\s+tom[a-z]*row", text_clean) or re.search(r"after\s+tom[a-z]*row", text_clean):
        target = reference_date + datetime.timedelta(days=2)
        return target.strftime("%Y-%m-%d"), False, None

    if re.search(r"\btom[a-z]*row\b", text_clean) or "tomorrow" in text_clean or "tmrw" in text_clean:
        target = reference_date + datetime.timedelta(days=1)
        return target.strftime("%Y-%m-%d"), False, None

    if "today" in text_clean or "2day" in text_clean:
        return reference_date.strftime("%Y-%m-%d"), False, None

    # 2. Weekdays ("next monday", "this friday", "saturday")
    weekdays_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    for w_name, w_val in weekdays_map.items():
        if w_name in text_clean:
            days_ahead = w_val - reference_date.weekday()
            if "next" in text_clean:
                if days_ahead <= 0:
                    days_ahead += 7
                days_ahead += 7
            else:
                if days_ahead <= 0:
                    days_ahead += 7
            target = reference_date + datetime.timedelta(days=days_ahead)
            return target.strftime("%Y-%m-%d"), False, None

    # 3. Standard YYYY-MM-DD
    match_iso = re.search(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", text_clean)
    if match_iso:
        y, m, d = map(int, match_iso.groups())
        try:
            target = datetime.date(y, m, d)
            return target.strftime("%Y-%m-%d"), False, None
        except ValueError:
            return None, False, "Invalid calendar date"

    # 4. Textual months: "15 August 1995", "August 15 1995", "15th Aug 95", "Aug 15, 1995"
    pattern_text_month = r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\s*,?\s*(\d{2,4})\b|\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*,?\s*(\d{2,4})\b"
    match_text_month = re.search(pattern_text_month, text_clean)
    if match_text_month:
        g = match_text_month.groups()
        if g[0] is not None:
            day_num, month_name, year_num = int(g[0]), g[1], int(g[2])
        else:
            month_name, day_num, year_num = g[3], int(g[4]), int(g[5])

        if month_name in MONTH_MAP:
            m = MONTH_MAP[month_name]
            if year_num < 100:
                # Two digit year heuristic
                current_year_short = reference_date.year % 100
                year_num += 1900 if year_num > current_year_short else 2000
            try:
                target = datetime.date(year_num, m, day_num)
                return target.strftime("%Y-%m-%d"), False, None
            except ValueError:
                return None, False, "Invalid calendar date"

    # 5. Short numeric formats: DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY
    match_short = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b", text_clean)
    if match_short:
        n1, n2, y_val = map(int, match_short.groups())
        if y_val < 100:
            current_year_short = reference_date.year % 100
            y_val += 1900 if y_val > current_year_short else 2000

        # Check ambiguity if both <= 12 and n1 != n2
        is_ambiguous = (n1 <= 12 and n2 <= 12 and n1 != n2)

        # Prefer DD/MM/YYYY for Indian hospital standard unless n1 > 12 (MM/DD/YYYY)
        if n1 > 12 and n2 <= 12:
            # Must be DD/MM/YYYY
            day_val, month_val = n1, n2
        elif n2 > 12 and n1 <= 12:
            # Must be MM/DD/YYYY
            month_val, day_val = n1, n2
        else:
            # Default DD/MM/YYYY
            day_val, month_val = n1, n2

        try:
            target = datetime.date(y_val, month_val, day_val)
            return target.strftime("%Y-%m-%d"), is_ambiguous, None
        except ValueError:
            return None, False, "Invalid calendar date"

    return None, False, None


def validate_dob(dob_str: str, reference_date: Optional[datetime.date] = None, allow_ambiguous: bool = True) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates a normalized or natural DOB string.

    Returns:
        (is_valid, normalized_yyyy_mm_dd, error_reason)
    """
    if reference_date is None:
        reference_date = get_current_kolkata_date()

    normalized, is_ambiguous, err = parse_and_normalize_date(dob_str, reference_date)
    if err or not normalized:
        return False, None, "Invalid date format. Please use DD/MM/YYYY or specify month in words (e.g., 15 Aug 1995)."

    if is_ambiguous and not allow_ambiguous:
        return False, normalized, "Ambiguous date (e.g. 05/06/1995). Please clarify if you mean 5th June or 6th May (e.g. 05 June 1995)."

    dob_date = datetime.datetime.strptime(normalized, "%Y-%m-%d").date()


    if dob_date > reference_date:
        return False, None, "Date of birth cannot be in the future."

    age = reference_date.year - dob_date.year - ((reference_date.month, reference_date.day) < (dob_date.month, dob_date.day))
    if age > 120:
        return False, None, "Please provide a valid date of birth."

    return True, normalized, None
