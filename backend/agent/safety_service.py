import re

SAFETY_WARNINGS = {
    "ENGLISH": "I am an AI assistant and cannot diagnose diseases or prescribe medications. Please consult a qualified doctor for clinical diagnosis and treatment options.",
    "TAMIL": "நான் ஒரு AI உதவியாளர், என்னால் நோய்களைக் கண்டறியவோ அல்லது மருந்துகளைப் பரிந்துரைக்கவோ முடியாது. முறையான சிகிச்சைக்காக மருத்துவரை அணுகவும்.",
    "HINDI": "मैं एक एआई सहायक हूं और बीमारियों का निदान या दवाएं नहीं लिख सकता। कृपया नैदानिक निदान और उपचार के लिए डॉक्टर से परामर्श करें।",
    "TELUGU": "నేను ఒక AI సహాయకుడిని మాత్రమే, వ్యాధులను నిర్ధారించలేను లేదా మందులను సూచించలేను. దయచేసి వైద్యుడిని సంప్రదించండి.",
    "MALAYALAM": "ഞാൻ ഒരു എഐ അസിസ്റ്റന്റ് ആണ്, രോഗനിർണ്ണയം നടത്താനോ മരുന്നുകൾ നിർദ്ദേശിക്കാനോ എനിക്ക് കഴിയില്ല. ദയവായി ഡോക്ടറെ സമീപിക്കുക.",
    "KANNADA": "ನಾನು ಎಐ ಸಹಾಯಕ, ರೋಗನಿರ್ಣಯ ಮಾಡಲು ಅಥವಾ ಔಷಧ ಬರೆಯಲು ಸಾಧ್ಯವಿಲ್ಲ. ದಯವಿಟ್ಟು ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ.",
    "URDU": "میں ایک اے آئی اسسٹنٹ ہوں اور بیماریوں کی تشخیص یا دوائیں تجویز نہیں کر سکتا۔ براہ کرم ڈاکٹر سے رجوع کریں۔"
}

DIAGNOSIS_KEYWORDS = [
    r"\b(prescribe|medicine|medication|pill|tablet|cure\s*for|treatment\s*for|diagnose|prescription|what\s*should\s*i\s*take|remedy)\b",
    r"(மருந்து|மாத்திரை|சிகிச்சை|பரிந்துரை)",
    r"(दवा|दवाई|इलाज|नुस्खा|परचे)",
    r"(మందులు|చికిత్స|ప్రిస్క్రిప్షన్)",
    r"(മരുന്ന്|ചികിത്സ|കുറിപ്പടി)",
    r"(ಔಷಧಿ|ಚಿಕಿತ್ಸೆ|ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್)",
    r"(دوا|علاج|نسخہ|گولی)"
]

def check_medical_safety(text: str, language: str = "ENGLISH") -> str:
    """
    Checks if the user is asking for medical diagnosis or prescription.
    If yes, returns the safety warning in their language, otherwise returns None.
    """
    if not text:
        return None

    text_lower = text.lower().strip()

    # Department variations / typos and intent phrases to exclude
    # so "medicine" in department names doesn't trigger medical diagnosis warnings
    DEPT_PHRASES = [
        "general medicine", "genearl medicine", "generel medicine", "genral medicine",
        "internal medicine", "medicine department", "dept of medicine", "doctor in medicine",
        "doctor for medicine", "medicine doctor", "cardiology", "pediatrics", "orthopedics",
        "dermatology", "ent", "gynecology", "neurology", "doctor availability", "check availability",
        "book appointment"
    ]

    text_clean = text_lower
    for phrase in DEPT_PHRASES:
        text_clean = text_clean.replace(phrase, "")

    lang = language.upper() if language else "ENGLISH"
    if lang not in SAFETY_WARNINGS:
        lang = "ENGLISH"

    for pattern in DIAGNOSIS_KEYWORDS:
        if re.search(pattern, text_clean):
            return SAFETY_WARNINGS[lang]

    return None
