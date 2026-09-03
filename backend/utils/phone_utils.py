"""
phone_utils.py
==============
Utilities for phone number normalization and PostgreSQL queries.
Handles 10-digit national numbers (e.g. 9876543210), international format (e.g. 919876543210),
and formatted phone strings (e.g. +91 98765 43210).
"""

import re
from typing import Optional, Tuple


def normalize_phone(phone_str: Optional[str]) -> str:
    """
    Extracts the last 10 digits of a phone string for consistent lookup.
    Example:
        '919876543210' -> '9876543210'
        '+91 98765 43210' -> '9876543210'
        '09876543210' -> '9876543210'
        '9876543210' -> '9876543210'
    """
    if not phone_str:
        return ""
    digits = re.sub(r"\D", "", str(phone_str))
    if len(digits) >= 10:
        return digits[-10:]
    return digits


def get_phone_query_condition() -> str:
    """
    Returns SQL WHERE fragment for matching phone or whatsapp_number
    by exact string match OR 10-digit normalized suffix match.
    Expects 4 parameters: (raw_phone, raw_phone, last_10_digits, last_10_digits)
    """
    return """(
        phone = %s OR whatsapp_number = %s OR
        RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10) = %s OR
        RIGHT(REGEXP_REPLACE(whatsapp_number, '[^0-9]', '', 'g'), 10) = %s
    )"""


def get_phone_query_params(phone_str: Optional[str]) -> Tuple[str, str, str, str]:
    """
    Builds the 4-tuple parameter for get_phone_query_condition().
    """
    raw = str(phone_str or "").strip()
    norm = normalize_phone(raw)
    return (raw, raw, norm, norm)
