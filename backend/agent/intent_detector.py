import re

# ============================================================
# CONTROLLED INTENT TAXONOMY
# ============================================================
# Valid intents (must match DB CHECK constraint in migrations):
VALID_DB_INTENTS = [
    'GREETING', 'BOOK_APPOINTMENT', 'CANCEL_APPOINTMENT', 'RESCHEDULE_APPOINTMENT',
    'APPOINTMENT_STATUS', 'DOCTOR_AVAILABILITY', 'HOSPITAL_INFORMATION',
    'DEPARTMENT_INFORMATION', 'SYMPTOM_GUIDANCE', 'PRE_ADMISSION', 'HUMAN_ESCALATION',
    'REGISTER_PATIENT', 'IDENTIFY_PATIENT', 'DEPENDENT_PATIENT', 'EMERGENCY_GUIDANCE',
    'THANK_YOU', 'GOODBYE', 'APPOINTMENT_CONFIRMATION', 'APPOINTMENT_TIME',
    'APPOINTMENT_DATE', 'LANGUAGE_CHANGE', 'UNKNOWN'
]

# Map agent-side intents to valid DB intents
INTENT_TO_DB_MAP = {
    'DEPENDENT_PATIENT': 'BOOK_APPOINTMENT',
    'THANK_YOU': 'GREETING',
    'GOODBYE': 'GREETING',
    'APPOINTMENT_CONFIRMATION': 'BOOK_APPOINTMENT',
    'APPOINTMENT_TIME': 'BOOK_APPOINTMENT',
    'APPOINTMENT_DATE': 'BOOK_APPOINTMENT',
    'EMERGENCY_GUIDANCE': 'HOSPITAL_INFORMATION',
    'IDENTIFY_PATIENT': 'GREETING',
    'REGISTER_PATIENT': 'REGISTER_PATIENT',
}

def get_db_intent(intent: str) -> str:
    """Maps agent intent to a valid DB-safe intent string."""
    return INTENT_TO_DB_MAP.get(intent, intent if intent in VALID_DB_INTENTS else 'GREETING')

# ============================================================
# PATTERN DICTIONARY
# ============================================================
PATTERNS = {
    # ---- Priority 0: EMERGENCY (checked first, always) ----
    "EMERGENCY_GUIDANCE": [
        r"\b(chest\s*pain|severe\s*chest|breathing\s*difficulty|shortness\s*of\s*breath|cant\s*breathe|can't\s*breathe|"
        r"cannot\s*breathe|not\s*breathing|breathe\s*difficulty|trouble\s*breathing|"
        r"heart\s*attack|severe\s*bleeding|heavy\s*bleed|unconscious|stroke|seizure|convulsion|"
        r"accident|trauma|emergency|paralysis|sudden\s*numbness|anaphylaxis|allergic\s*reaction|"
        r"severe\s*head\s*injury|overdose|poisoning)\b",
        r"(நெஞ்சு\s*வலி|சுவாசிக்க\s*முடியவில்லை|அவசர|விபத்து)",
        r"(छाती\s*में\s*दर्द|सांस\s*लेने\s*में\s*तकलीफ|आपातकालीन|दुर्घटना)",
        r"(గుండె\s*నొప్పి|శ్వాస\s*తీసుకోవడం|అత్యవసర)",
        r"(നെഞ്ചുവേദന|ശ്വാസതടസ്സം|അപകടം|അടിയന്തിരം)",
        r"(ಎದೆ\s*ನೋವು|ಉಸಿರಾಟದ\s*ತೊಂದರೆ|ತುರ್ತು|ಅಪಘಾತ)",
        r"(چھاتی\s*میں\s*درد|سانس\s*کی\s*تکلیف|ایمرجنسی)"
    ],

    # ---- Priority 1: HUMAN_ESCALATION ----
    "HUMAN_ESCALATION": [
        r"\b(human|staff|agent|operator|representative|escalate|talk\s*to\s*person|speak\s*to\s*(a\s*)?human|"
        r"not\s*ai|real\s*person|customer\s*care|helpdesk|support\s*team|connect\s*me\s*to)\b",
        r"(மனிதர்|அதிகாரி|உதவி|ஆள்)",
        r"(इंसान|कर्मचारी|एजेंट|अधिकारी|बात\s*करनी)",
        r"(మనిషి|సిబ్బంది|సహాయం)",
        r"(മനുഷ്യൻ|ഉദ്യോഗസ്ഥൻ|ആളോട്\s*സംസാരിക്കണം)",
        r"(ಮನುಷ್ಯ|ಸಿಬ್ಬಂದಿ|ಸಹಾಯಕಿ)",
        r"(انسان|عملہ|نمائندہ|بات\s*کرو)"
    ],

    # ---- Priority 2: LANGUAGE_CHANGE ----
    "LANGUAGE_CHANGE": [
        r"\b(english|tamil|hindi|telugu|malayalam|kannada|urdu)\b",
        r"(தமிழ்|தமிழில்|ஆங்கிலம்)",
        r"(हिंदी|अंग्रेजी|तमिल)",
        r"(తెలుగు|ఇంగ్లీష్)",
        r"(മലയാളം|ഇംഗ്ലീഷ്)",
        r"(ಕನ್ನಡ|ಇಂಗ್ಲಿಷ್)",
        r"(اردو|انگریزی)"
    ],

    # ---- GREETING ----
    "GREETING": [
        r"^(hi|hello|hey|good\s*morning|good\s*afternoon|good\s*evening|yoo|greetings|hola|howdy)[\s!.]*$",
        r"(வணக்கம்|ஹலோ|ஹாய்)",
        r"(नमस्ते|नमस्कार|हैलो)",
        r"(నమస్తే|హలో)",
        r"(നമസ്കാരം|ഹലോ)",
        r"(ನಮಸ್ಕಾರ|ಹಲೋ)",
        r"(سلام|آداب)"
    ],

    # ---- THANK_YOU ----
    "THANK_YOU": [
        r"\b(no\s*thank\s*you|thank\s*you|thanks|thank\s*u|thx|thnks|ty|cheers|appreciate\s*it|great\s*thank|many\s*thanks)\b",
        r"(நன்றி|மிக்க\s*நன்றி)",
        r"(धन्यवाद|शुक्रिया|बहुत\s*धन्यवाद)",
        r"(ధన్యవాదాలు)",
        r"(നന്ദി|വളരെ\s*നന്ദി)",
        r"(ಧನ್ಯವಾದ)",
        r"(شکریہ|بہت\s*شکریہ)"
    ],

    # ---- GOODBYE ----
    "GOODBYE": [
        r"^(bye|goodbye|see\s*you|take\s*care|done|all\s*done|that\s*is\s*all|that'?s\s*all|no\s*more|"
        r"nothing\s*else|i'?m\s*done|i\s*am\s*done|exit|quit|close)[\s!.]*$",
        r"(போகிறேன்|வணக்கம்\s*பின்னர்)",
        r"(अलविदा|बाय|फिर\s*मिलेंगे)",
        r"(వెళ్తున్నాను|బై)",
        r"(ഞാൻ\s*പോകുന്നു|ബൈ)",
        r"(ಹೋಗ್ತೀನಿ|ಬಾಯ್)",
        r"(الوداع|بائے)"
    ],

    # ---- DEPENDENT_PATIENT ----
    "DEPENDENT_PATIENT": [
        r"\b(for\s*my\s*(son|daughter|child|kid|baby|wife|husband|mother|father|mom|dad|spouse|"
        r"parent|sister|brother|relative|family\s*member|dependent)|"
        r"my\s*(son|daughter|child|kid|wife|husband|mother|father|mom|dad)\s*(has|have|is|needs|want|would)|"
        r"book\s*(for|an\s*appointment\s*for)\s*my\s*(son|daughter|child|wife|husband|mother|father|mom|dad)|"
        r"appointment\s*for\s*my\s*(son|daughter|child|wife|husband|mother|father)|"
        r"(son|daughter|child)\s*(has|have)\s*(fever|cough|cold|pain|illness|problem|issue|sick))\b",
        r"(என்\s*மகன்|என்\s*மகள்|என்\s*குழந்தை|என்\s*மனைவி|என்\s*கணவன்)",
        r"(मेरे\s*बेटे|मेरी\s*बेटी|मेरे\s*बच्चे|मेरी\s*पत्नी|मेरे\s*पति)",
        r"(నా\s*కొడుకు|నా\s*కూతురు|నా\s*పిల్ల|నా\s*భార్య|నా\s*భర్త)",
        r"(എന്റെ\s*മകൻ|എന്റെ\s*മകൾ|എന്റെ\s*കുട്ടി|എന്റെ\s*ഭാര്യ|എന്റെ\s*ഭർത്താവ്)",
        r"(ನನ್ನ\s*ಮಗ|ನನ್ನ\s*ಮಗಳು|ನನ್ನ\s*ಮಕ್ಕಳು|ನನ್ನ\s*ಹೆಂಡತಿ|ನನ್ನ\s*ಗಂಡ)",
        r"(میرے\s*بیٹے|میری\s*بیٹی|میرے\s*بچے|میری\s*بیوی|میرے\s*شوہر)"
    ],

    # ---- CANCEL_APPOINTMENT ----
    "CANCEL_APPOINTMENT": [
        r"\b(cancel|cancellation|discard|delete\s*appointment|cancel\s*booking|cancel\s*my\s*appointment|"
        r"i\s*want\s*to\s*cancel|please\s*cancel)\b",
        r"(ரத்து|நீக்கு)",
        r"(रद्द|निरस्त|कैंसिल)",
        r"(రద్దు|తీసివేయి)",
        r"(റദ്ദാക്കുക|ഒഴിവാക്കുക)",
        r"(ರದ್ದು|ತೆಗೆದುಹಾಕಿ)",
        r"(منسوخ|کینسل)"
    ],

    # ---- RESCHEDULE_APPOINTMENT ----
    "RESCHEDULE_APPOINTMENT": [
        r"\b(reschedule|postpone|change\s*date|change\s*time|shift\s*appointment|modify\s*appointment|"
        r"change\s*my\s*appointment|move\s*appointment|change\s*to\s*tomorrow|change\s*to\s*monday|"
        r"i\s*want\s*to\s*reschedule|can\s*i\s*reschedule)\b",
        r"(மாற்ற|தேதி\s*மாற்ற|நேரம்\s*மாற்ற)",
        r"(तारीख\s*बदलें|समय\s*बदलें|बदलाव|रिशेड्यूल)",
        r"(మార్చడం|తేదీ\s*మార్చండి)",
        r"(മാറ്റുക|തീയതി\s*മാറ്റുക|പുനഃക്രമീകരിക്കുക)",
        r"(ಬದಲಾಯಿಸಿ|ಸಮಯ\s*ಬದಲಾವಣೆ)",
        r"(تبدیل|تاریخ\s*بدلیں|وقت\s*بدلیں)"
    ],

    # ---- APPOINTMENT_STATUS ----
    "APPOINTMENT_STATUS": [
        r"\b(status|check\s*appointment|my\s*appointment|view\s*booking|appointment\s*status|"
        r"what\s*is\s*my\s*appointment|show\s*my\s*booking|track\s*appointment)\b",
        r"(நிலை|அப்பாயிண்ட்மெண்ட்\s*விவரம்)",
        r"(स्थिति|अपॉइंटमेंट\s*चेक|विवरण)",
        r"(స్థితి|అపాయింట్మెంట్\s*చూడు)",
        r"(നില|വിവരം\s*അറിയുക)",
        r"(ಸ್ಥಿತಿ|ಮಾಹಿತಿ)",
        r"(حیثیت|اسٹیٹس|چیک\s*کریں)"
    ],

    # ---- APPOINTMENT_CONFIRMATION ----
    "APPOINTMENT_CONFIRMATION": [
        r"\b(yes\s*(confirm|please\s*confirm|book\s*it|go\s*ahead|proceed)|"
        r"confirm\s*(it|appointment|booking|please)|"
        r"btn_confirm_appt|please\s*confirm|go\s*ahead\s*(and\s*book|with\s*it)|"
        r"i\s*confirm|that'?s\s*(fine|correct|right)|looks\s*good)\b"
    ],

    "DOCTOR_AVAILABILITY": [
        r"\b(availability|available\s*(doctors?|times?|slots?)|working|present|duty|schedule\s*of|"
        r"is\s*dr|is\s*doctor|when\s*will|when\s*is|when\s*does|when\s*can|"
        r"can\s*i\s*(meet|see|consult)\s*(dr|doctor)?|"
        r"free\s*slot|free\s*time|show\s*times?|show\s*slots?|show\s*available|"
        r"available\s*times?|available\s*slots?|doctor\s*availability|check\s*availability|"
        r"which\s*doctors?\s*are\s*available|what\s*times?\s*are\s*available|"
        r"what\s*slots?\s*are\s*available)\b",

        r"(இருக்கிறாரா|அறிமுகம்|அட்டவணை|பணி|கிடைக்கும்|நேரம்)",
        r"(उपलब्ध|ड्यूटी|शेड्यूल|डॉक्टर\s*हैं|कब\s*मिलेंगे|खाली\s*समय)",
        r"(అందుబాటులో|షెడ్యూల్|వైద్యుడు|ఎప్పుడు\s*అందుబాటులో)",
        r"(ലഭ്യമാണോ|ഡ്യൂട്ടി|ഷെഡ്യൂൾ|ഡോക്ടർ\s*ഉണ്ടോ|എപ്പോൾ\s*ലഭ്യം)",
        r"(ಲಭ್ಯವಿದ್ದಾರಾ|ಸಮಯ|ಡಾಕ್ಟರ್|ಯಾವಾಗ\s*ಲಭ್ಯ)",
        r"(دستیاب|ڈیوٹی|موجود|شیڈول|کب\s*دستیاب)"
    ],

    # ---- PRE_ADMISSION ----
    "PRE_ADMISSION": [
        r"\b(pre-?admission|preadmission|admission|admit|inpatient|surgery\s*documents|"
        r"admission\s*follow-?up|stay\s*details|hospital\s*stay|ward|bed\s*availability)\b",
        r"(அட்மிஷன்|சேர்க்கை|அறுவை\s*சிகிச்சை)",
        r"(दाखिला|एडमिशन|भर्ती|ऑपरेशन)",
        r"(ప్రవేశం|అడ్మిషన్|శస్త్రచికిత్స)",
        r"(അഡ്മിഷൻ|ശസ്ത്രക്രിയ|മുറി\s*വിവരം)",
        r"(ಪ್ರವೇಶ|ಅಡ್ಮಿಷನ್|ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ)",
        r"(داخلہ|ایڈمیشن|سرجری)"
    ],

    # ---- HOSPITAL_INFORMATION ----
    "HOSPITAL_INFORMATION": [
        r"\b(location|address|directions?|phone\s*number|contact|map|website|hospital\s*info|"
        r"timings?|visiting\s*hours?|where\s*(is\s*the\s*hospital|are\s*you)|"
        r"hospital|departments?|specialty|specialties|facility|facilities|services?|faq|"
        r"how\s*to\s*(reach|get\s*to)|working\s*hours?|open\s*hours?)\b",
        r"(முகவரி|தொலைபேசி|இடம்|வழித்தடம்|துறைகள்|துறை|வசதிகள்|மருத்துவமனை|எங்கே)",
        r"(पता|लोकेशन|फोन\s*नंबर|संपर्क|अस्पताल\s*के\s*बारे\s*में|विभाग|सुविधाएं|अस्पताल|कहाँ)",
        r"(చిరునామా|ఫోన్|లోకేషన్|విభాగాలు|సదుపాయాలు|ఆసుపత్రి|ఎక్కడ)",
        r"(വിലാസം|ഫോൺ|സ്ഥലം|രോഗീവിവരം|വകുപ്പുകൾ|സൗകര്യങ്ങൾ|ആശുപത്രി|എവിടെ)",
        r"(ವಿಳಾಸ|ಫೋನ್|ಸ್ಥಳ|ವಿಭಾಗಗಳು|ಸೌಲಭ್ಯಗಳು|ಆಸ್ಪತ್ರೆ|ಎಲ್ಲಿದೆ)",
        r"(پتہ|لوکیشن|فون|معلومات|شعبہ|شعبہ\s*جات|سہولیات|ہسپتال|کہاں)"
    ],

    # ---- REGISTER_PATIENT ----
    "REGISTER_PATIENT": [
        r"\b(register\s*(patient|account|me|myself|new)?|new\s*patient\s*registration|"
        r"patient\s*registration|sign\s*up|first\s*time\s*(patient|visitor|here)|"
        r"new\s*here|create\s*(account|profile)|btn_first_time)\b",
        r"(பதிவு|புதிய\s*நோயாளி|முதல்\s*முறை)",
        r"(पंजीकरण|नया\s*मरीज|पहली\s*बार|रजिस्टर)",
        r"(నమోదు|కొత్త\s*రోగి|మొదటి\s*సారి)",
        r"(രജിസ്റ്റർ|പുതിയ\s*രോഗി|ആദ്യമായി)",
        r"(ನೋಂದಣಿ|ಹೊಸ\s*ರೋಗಿ|ಮೊದಲ\s*ಬಾರಿ)",
        r"(رجسٹریشن|نیا\s*مریض|پہلی\s*بار)"
    ],

    # ---- BOOK_APPOINTMENT ----
    "BOOK_APPOINTMENT": [
        r"\b(book|appointment|booking|need\s*(an?\s*)?appointment|schedule\s*appointment|"
        r"consult(ation)?|see\s*a\s*doctor|want\s*to\s*(see|meet)\s*(a\s*)?doctor|"
        r"i\s*(need|want|would\s*like)\s*(to\s*)?(see|visit|consult|meet)\s*(a\s*)?doctor|"
        r"i\s*have\s*(hair|skin|fever|cough|cold|pain|problem|issue|rash|acne|"
        r"hair\s*fall|hair\s*loss|losing\s*hair|bald|headache|migraine|"
        r"chest|joint|ear|eye|stomach|back)\b|"
        r"slot|slots|free\s*slot|cardiologist|cardiology|heart\s*doctor|heart\s*specialist|"
        r"pediatrician|neurologist|gynecologist|orthopedist|dermatologist|physician|"
        r"i\s*need\s*a\s*(dermatologist|cardiologist|pediatrician|neurologist|"
        r"gynecologist|orthopedist|ent|specialist|doctor))\b",
        r"(பதிவு|அப்பாயிண்ட்மெண்ட்|சந்திப்பு)",
        r"(बुक|अपॉइंटमेंट|पंजीकरण|दिखाना|परामर्श)",
        r"(అపాయింట్మెంట్|బుక్|వైద్యుని\s*కలవాలి)",
        r"(ബുക്കിംഗ്|അപ്പോയിന്റ്മെന്റ്|ഡോക്ടറെ\s*കാണണം)",
        r"(ಬುಕ್|ಅಪಾಯಿಂಟ್ಮೆಂಟ್|ಸಮಾಲೋಚನೆ)",
        r"(بک|اپائنٹمنٹ|مشورہ|ڈاکٹر\s*کو\s*دکھانا)"
    ],

    # ---- SYMPTOM_GUIDANCE (fallback — only if no other workflow active) ----
    "SYMPTOM_GUIDANCE": [
        r"\b(fever|cold|cough|headache|vomiting|stomach\s*pain|nausea|diarrhea|"
        r"dizzy|dizziness|flu|congestion|sore\s*throat|ache|rash|itching|"
        r"hair\s*fall|hair\s*loss|losing\s*hair|bald|acne|pimples?|skin\s*problem|"
        r"chest\s*pain|joint\s*pain|back\s*pain|bone\s*pain|ear\s*pain|migraine)\b",
        r"(காய்ச்சல்|தலைவலி|வயிற்று\s*வலி|இருமல்|சளி)",
        r"(बुखार|सिरदर्द|पेट\s*दर्द|खांसी|जुकाम)",
        r"(జ్వరం|తలనొప్పి|కడుపు\s*నొప్పి|దగ్గు|జలుబు)",
        r"(പനി|തലവേദന|വയറുവേദന|ചുമ|ജലദോഷം)",
        r"(ಜ್ವರ|ತಲೆನೋವು|ಹೊಟ್ಟೆ\s*ನೋವು|ಕೆಮ್ಮು|ನೆಗಡಿ)",
        r"(بخار|سر\s*درد|پیٹ\s*درد|کھانسی|زکام)"
    ],
}

# Short/ambiguous messages that must NEVER trigger intent reset
SHORT_CONTEXT_MESSAGES = {
    # Digits — likely time or option selection
    "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
    # AM/PM qualifiers
    "am", "pm", "a.m.", "p.m.", "morning", "afternoon", "evening", "night",
    # Vague references
    "same", "same doctor", "that doctor", "that one", "this doctor",
    "same date", "same time", "same slot",
    # Short affirmations / negations handled upstream
    "yes", "no", "ok", "okay", "sure", "yeah", "yep", "nope",
    # Follow-up words
    "tomorrow", "today", "monday", "tuesday", "wednesday", "thursday",
    "friday", "saturday", "sunday", "next week", "next monday",
    "what times", "what time", "available", "available times", "available slots",
    "show slots", "show times", "which times",
}


def detect_intent(text: str, current_intent: str = None) -> str:
    """
    Detects the intent of a user message.

    Priority order:
      0. EMERGENCY_GUIDANCE (always first)
      1. HUMAN_ESCALATION
      2. LANGUAGE_CHANGE
      3. Short / context-continuation messages — preserve current intent
      4. Match GREETING, THANK_YOU, GOODBYE, APPOINTMENT_CONFIRMATION (high confidence exact patterns)
      5. DEPENDENT_PATIENT
      6. Other intents in priority order
      7. If in an active workflow and no clear intent shift — preserve current intent
    """
    text_lower = text.lower().strip()

    # --- Priority 0: Emergency --- Always checked regardless of context
    for pattern in PATTERNS["EMERGENCY_GUIDANCE"]:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "EMERGENCY_GUIDANCE"

    # --- Priority 1: Human escalation ---
    for pattern in PATTERNS["HUMAN_ESCALATION"]:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "HUMAN_ESCALATION"

    # --- Priority 2: Language change ---
    for pattern in PATTERNS["LANGUAGE_CHANGE"]:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "LANGUAGE_CHANGE"

    # --- Priority 3: Short / ambiguous messages — preserve context ---
    if text_lower in SHORT_CONTEXT_MESSAGES:
        if current_intent and current_intent not in ["GREETING", "UNKNOWN", None]:
            return current_intent

    # --- Priority 4: Exact high-confidence single-turn intents ---
    for intent_name in ["GREETING", "THANK_YOU", "GOODBYE", "APPOINTMENT_CONFIRMATION"]:
        for pattern in PATTERNS[intent_name]:
            if re.search(pattern, text_lower, re.IGNORECASE):
                # These override workflow context only if they are strong signals
                if intent_name in ["THANK_YOU", "GOODBYE"]:
                    return intent_name
                if intent_name == "GREETING":
                    # Don't switch to GREETING if already in active workflow and message is not standalone
                    if current_intent in [
                        "BOOK_APPOINTMENT", "REGISTER_PATIENT", "IDENTIFY_PATIENT",
                        "RESCHEDULE_APPOINTMENT", "CANCEL_APPOINTMENT", "DOCTOR_AVAILABILITY",
                        "DEPENDENT_PATIENT"
                    ] and len(text_lower) > 5:
                        break
                    return "GREETING"
                if intent_name == "APPOINTMENT_CONFIRMATION":
                    if current_intent in ["BOOK_APPOINTMENT", "DEPENDENT_PATIENT"]:
                        return "APPOINTMENT_CONFIRMATION"

    # --- Priority 5: DEPENDENT_PATIENT (before BOOK_APPOINTMENT) ---
    for pattern in PATTERNS["DEPENDENT_PATIENT"]:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return "DEPENDENT_PATIENT"

    # --- Priority 6: Context preservation for active workflows ---
    ACTIVE_WORKFLOW_INTENTS = [
        "BOOK_APPOINTMENT", "REGISTER_PATIENT", "IDENTIFY_PATIENT",
        "RESCHEDULE_APPOINTMENT", "CANCEL_APPOINTMENT", "DOCTOR_AVAILABILITY",
        "DEPENDENT_PATIENT"
    ]

    if current_intent in ACTIVE_WORKFLOW_INTENTS:
        matched_intents = []
        for intent_name, patterns in PATTERNS.items():
            if intent_name in ["EMERGENCY_GUIDANCE", "HUMAN_ESCALATION", "LANGUAGE_CHANGE",
                               "GREETING", "THANK_YOU", "GOODBYE", "APPOINTMENT_CONFIRMATION",
                               "DEPENDENT_PATIENT"]:
                continue
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matched_intents.append(intent_name)
                    break

        # Only allow explicit intent switches that make sense
        if "CANCEL_APPOINTMENT" in matched_intents:
            return "CANCEL_APPOINTMENT"
        if "RESCHEDULE_APPOINTMENT" in matched_intents:
            return "RESCHEDULE_APPOINTMENT"

        # Allow BOOK_APPOINTMENT → DOCTOR_AVAILABILITY for explicit slot queries
        if current_intent == "BOOK_APPOINTMENT" and "DOCTOR_AVAILABILITY" in matched_intents:
            avail_phrases = [
                "when will", "when is", "when does", "when can",
                "available", "availability", "show available", "available time",
                "available slot", "available times", "available slots",
                "show time", "show slot", "what time", "what slot",
                "which times", "which slots"
            ]
            if any(p in text_lower for p in avail_phrases):
                return "DOCTOR_AVAILABILITY"

        # Allow DOCTOR_AVAILABILITY → BOOK_APPOINTMENT
        if current_intent == "DOCTOR_AVAILABILITY" and "BOOK_APPOINTMENT" in matched_intents:
            return "BOOK_APPOINTMENT"

        # Preserve workflow intent for any other message
        return current_intent

    # --- Priority 7: Fresh intent matching ---
    matched_intents = []
    for intent_name, patterns in PATTERNS.items():
        if intent_name in ["EMERGENCY_GUIDANCE", "HUMAN_ESCALATION", "LANGUAGE_CHANGE",
                           "GREETING", "THANK_YOU", "GOODBYE", "APPOINTMENT_CONFIRMATION",
                           "DEPENDENT_PATIENT", "SYMPTOM_GUIDANCE"]:
            continue
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                matched_intents.append(intent_name)
                break

    if matched_intents:
        # Priority order for fresh matches
        for prio in [
            "REGISTER_PATIENT", "CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT",
            "APPOINTMENT_STATUS", "BOOK_APPOINTMENT", "DOCTOR_AVAILABILITY",
            "PRE_ADMISSION", "HOSPITAL_INFORMATION"
        ]:
            if prio in matched_intents:
                return prio
        return matched_intents[0]

    # Check SYMPTOM_GUIDANCE last (only if no appointment context)
    for pattern in PATTERNS["SYMPTOM_GUIDANCE"]:
        if re.search(pattern, text_lower, re.IGNORECASE):
            # If no active workflow, route to BOOK_APPOINTMENT (symptom = booking intent)
            return "BOOK_APPOINTMENT"

    # --- Fallback: preserve active context ---
    if current_intent and current_intent not in ["UNKNOWN", None]:
        if current_intent in [
            "REGISTER_PATIENT", "IDENTIFY_PATIENT", "BOOK_APPOINTMENT",
            "CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT", "POST_BOOKING",
            "DOCTOR_AVAILABILITY", "DEPENDENT_PATIENT"
        ]:
            return current_intent

    return "UNKNOWN"
