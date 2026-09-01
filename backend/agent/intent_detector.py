import re

# Simple pattern dictionaries for intent detection across 7 languages:
# English, Tamil, Hindi, Telugu, Malayalam, Kannada, Urdu

PATTERNS = {
    "EMERGENCY_GUIDANCE": [
        r"\b(chest\s*pain|breathing\s*difficulty|shortness\s*of\s*breath|heart\s*attack|severe\s*bleeding|unconscious|stroke|accident|trauma|emergency)\b",
        r"(நெஞ்சு\s*வலி|சுவாசிக்க\s*முடியவில்லை|அவசர|விபத்து)",
        r"(छाती\s*में\s*दर्द|सांस\s*लेने\s*में\s*तकलीफ|आपातकालीन|दुर्घटना)",
        r"(గుండె\s*నొప్పి|శ్వాస\s*తీసుకోవడం|అత్యవసర)",
        r"(നെഞ്ചുവേദന|ശ്വാസതടസ്സം|അപകടം|അടിയന്തിരം)",
        r"(ಎದೆ\s*ನೋವು|ಉಸಿರಾಟದ\s*ತೊಂದರೆ|ತುರ್ತು|ಅಪಘಾತ)",
        r"(چھاتی\s*میں\s*درد|سانس\s*کی\s*تکلیف|ایمرجنسی)"
    ],
    "HUMAN_ESCALATION": [
        r"\b(human|staff|agent|operator|representative|escalate|talk\s*to\s*person|not\s*ai|customer\s*care|helpdesk|support\s*team)\b",
        r"(மனிதர்|அதிகாரி|உதவி|ஆள்)",
        r"(इंसान|कर्मचारी|एजेंट|अधिकारी|बात\s*करनी)",
        r"(మనిషి|సిబ్బంది|సహాయం)",
        r"(മനുഷ്യൻ|ഉദ്യോഗസ്ഥൻ|ആളോട്\s*സംസാരിക്കണം)",
        r"(ಮನುಷ್ಯ|ಸಿಬ್ಬಂದಿ|ಸಹಾಯಕಿ)",
        r"(انسان|عملہ|نمائندہ|بات\s*کرو)"
    ],
    "LANGUAGE_CHANGE": [
        r"\b(english|tamil|hindi|telugu|malayalam|kannada|urdu)\b",
        r"(தமிழ்|தமிழில்|ஆங்கிலம்)",
        r"(हिंदी|अंग्रेजी|तमिल)",
        r"(తెలుగు|ఇంగ్లీష్)",
        r"(മലയാളം|ഇംഗ്ലീഷ്)",
        r"(ಕನ್ನಡ|ಇಂಗ್ಲಿಷ್)",
        r"(اردو|انگریزی)"
    ],
    "GREETING": [
        r"\b(hi|hello|hey|good\s*morning|good\s*afternoon|good\s*evening|yoo|greetings)\b",
        r"(வணக்கம்|ஹலோ|ஹாய்)",
        r"(नमस्ते|नमस्कार|हैलो)",
        r"(నమస్తే|హలో)",
        r"(നമസ്കാരം|ഹലോ)",
        r"(ನಮಸ್ಕಾರ|ಹಲೋ)",
        r"(سلام|آداب)"
    ],
    "CANCEL_APPOINTMENT": [
        r"\b(cancel|cancellation|rathu|discard|delete\s*appointment|cancel\s*booking)\b",
        r"(ரத்து|நீக்கு)",
        r"(रद्द|निरस्त|कैंसिल)",
        r"(రద్దు|తీసివేయి)",
        r"(റദ്ദാക്കുക|ഒഴിവാക്കുക)",
        r"(ರದ್ದು|ತೆಗೆದುಹಾಕಿ)",
        r"(منسوخ|کینسل)"
    ],
    "RESCHEDULE_APPOINTMENT": [
        r"\b(reschedule|postpone|change\s*date|change\s*time|shift|change\s*appointment|modify\s*appointment)\b",
        r"(மாற்ற|தேதி\s*மாற்ற|நேரம்\s*மாற்ற)",
        r"(तारीख\s*बदलें|समय\s*बदलें|बदलाव|रिशेड्यूल)",
        r"(మార్చడం|తేదీ\s*మార్చండి)",
        r"(മാറ്റുക|തീയതി\s*മാറ്റുക|പുനഃക്രമീകരിക്കുക)",
        r"(ಬದಲಾಯಿಸಿ|ಸಮಯ\s*ಬದಲಾವಣೆ)",
        r"(تبدیل|تاریخ\s*بدلیں|وقت\s*بدلیں)"
    ],
    "APPOINTMENT_STATUS": [
        r"\b(status|lookup|check\s*appointment|my\s*appointment|view\s*booking|status\s*query)\b",
        r"(நிலை|அப்பாயிண்ட்மெண்ட்\s*விவரம்)",
        r"(स्थिति|अपॉइंटमेंट\s*चेक|विवरण)",
        r"(స్థితి|అపాయింట్మెంట్\s*చూడు)",
        r"(നില|വിവരം\s*അറിയുക)",
        r"(ಸ್ಥಿತಿ|ಮಾಹಿತಿ)",
        r"(حیثیت|اسٹیٹس|چیک\s*کریں)"
    ],
    "DOCTOR_AVAILABILITY": [
        r"\b(availability|working|present|duty|schedule\s*of|is\s*dr|is\s*doctor)\b",
        r"(இருக்கிறாரா|அறிமுகம்|அட்டவணை|பணி)",
        r"(उपलब्ध|ड्यूटी|शेड्यूल|डॉक्टर\s*हैं)",
        r"(అందుబాటులో|షెడ్యూల్|వైద్యుడు)",
        r"(ലഭ്യമാണോ|ഡ്യൂട്ടി|ഷെഡ്യൂൾ|ഡോക്ടർ\s*ഉണ്ടോ)",
        r"(ಲಭ್ಯವಿದ್ದಾರಾ|ಸಮಯ|ಡಾಕ್ಟರ್)",
        r"(دستیاب|ڈیوٹی|موجود|شیڈول)"
    ],
    "PRE_ADMISSION": [
        r"\b(pre-admission|preadmission|admission|admit|inpatient|surgery\s*documents|admission\s*follow-up|stay\s*details)\b",
        r"(அட்மிஷன்|சேர்க்கை|அறுவை\s*சிகிச்சை)",
        r"(दाखिला|एडमिशन|भर्ती|ऑपरेशन)",
        r"(ప్రవేశం|అడ్మిషన్|శస్త్రచికిత్స)",
        r"(അഡ്മിഷൻ|ശസ്ത്രക്രിയ|മുറി\s*വിവരം)",
        r"(ಪ್ರವೇಶ|ಅಡ್ಮಿಷನ್|ಶಸ್ತ್ರಚಿಕಿತ್ಸೆ)",
        r"(داخلہ|ایڈمیشن|سرجری)"
    ],
    "HOSPITAL_INFORMATION": [
        r"\b(location|address|directions|phone\s*number|contact|map|website|hospital\s*info|timings|visiting\s*hours|where|hospital|department|departments|specialty|specialties|facility|facilities|services|faq)\b",
        r"(முகவரி|தொலைபேசி|இடம்|வழித்தடம்|துறைகள்|துறை|வசதிகள்|மருத்துவமனை|எங்கே)",
        r"(पता|लोकेशन|फोन\s*नंबर|संपर्क|अस्पताल\s*के\s*बारे\s*में|विभाग|सुविधाएं|अस्पताल|कहाँ)",
        r"(చిరునామా|ఫోన్|లోకేషన్|విభాగాలు|సదుపాయాలు|ఆసుపత్రి|ఎక్కడ)",
        r"(വിലാസം|ഫോൺ|സ്ഥലം|രോഗീവിവരം|വകുപ്പുകൾ|സൗകര്യങ്ങൾ|ആശുപത്രി|എവിടെ)",
        r"(ವಿಳಾಸ|ಫೋನ್|ಸ್ಥಳ|ವಿಭಾಗಗಳು|ಸೌಲಭ್ಯಗಳು|ಆಸ್ಪತ್ರೆ|ಎಲ್ಲಿದೆ)",
        r"(پتہ|لوکیشن|فون|معلومات|شعبہ|شعبہ جات|سہولیات|ہسپتال|کہاں)"
    ],
    "REGISTER_PATIENT": [
        r"\b(register\s*patient|register\s*account|new\s*patient\s*registration|patient\s*registration|register|registration|signup)\b",
        r"(பதிவு|புதிய\s*நோயாளி)",
        r"(पंजीकरण|नया\s*मरीज)",
        r"(నమోదు)",
        r"(രജിസ്ട്രേഷൻ)",
        r"(ನೋಂದಣಿ)",
        r"(رجسٹریشن)"
    ],
    "BOOK_APPOINTMENT": [
        r"\b(book|appointment|booking|need\s*appointment|schedule\s*appointment|consult|consultation|see\s*a\s*doctor|appointment\s*time|booking\s*time|reschedule\s*time|what\s*time|what\s*times|available\s*time|available\s*times|available\s*slot|slot|slots|free\s*slot|see\s*dr|meet\s*dr|consult\s*dr|see\s*doctor|meet\s*doctor|consult\s*doctor|meet|cardiologist|cardialogist|cardiology|heart\s*doctor|heart\s*specialist|cardiac\s*doctor|cardiology\s*doctor|pediatrician|neurologist|gynecologist|orthopedist|dermatologist|physician)\b",
        r"(பதிவு|அப்பாயிண்ட்மெண்ட்|சந்திப்பு)",
        r"(बुक|अपॉइंटमेंट|पंजीकरण|दिखाना|परामर्श)",
        r"(అపాయింట్మెంట్|బుక్|వైద్యుని\s*కలవాలి)",
        r"(ബുക്കിംഗ്|അപ്പോയിന്റ്മെന്റ്|ഡോക്ടറെ\s*കാണണം)",
        r"(ಬುಕ್|ಅಪಾಯಿಂಟ್ಮೆಂಟ್|ಸಮಾಲೋಚನೆ)",
        r"(بک|اپائنٹمنٹ|مشورہ|ڈاکٹر\s*کو\s*دکھانا)"
    ],
    "SYMPTOM_GUIDANCE": [
        r"\b(fever|cold|cough|headache|pain|vomiting|stomach|nausea|diarrhea|rash|dizzy|dizziness|flu|congestion|throat|ache)\b",
        r"(காய்ச்சல்|தலைவலி|வயிற்று\s*வலி|இருமல்|சளி)",
        r"(बुखार|सिरदर्द|पेट\s*दर्द|खांसी|जुकाम)",
        r"(జ్వరం|తలనొప్పి|కడుపు\s*నొప్పి|దగ్గు|జలుబు)",
        r"(പനി|തലവേദന|വയറുവേദന|ചുമ|ജലദോഷം)",
        r"(ಜ್ವರ|ತಲೆನೋವು|ಹೊಟ್ಟೆ\s*ನೋವು|ಕೆಮ್ಮು|ನೆಗಡಿ)",
        r"(بخار|سر\s*درد|پیٹ\s*درد|کھانسی|زکام)"
    ],
    "REGISTER_PATIENT": [
        r"\b(register|registration|new\s*patient|first\s*time|new\s*here|create\s*account|sign\s*up|first\s*visit)\b",
        r"(பதிவு|புதிய\s*நோயாளி|முதல்\s*முறை)",
        r"(पंजीकरण|नया\s*मरीज|पहली\s*बार|रजिस्टर)",
        r"(నమోదు|కొత్త\s*రోగి|మొదటి\s*సారి)",
        r"(രജിസ്റ്റർ|പുതിയ\s*രോഗി|ആദ്യമായി)",
        r"(ನೋಂದಣಿ|ಹೊಸ\s*ರೋಗಿ|ಮೊದಲ\s*ಬಾರಿ)",
        r"(رجسٹریشن|نیا\s*مریض|پہلی\s*بار)"
    ]
}

def detect_intent(text: str, current_intent: str = None) -> str:
    """
    Detects the intent of a user message.
    Preserves context if we are in the middle of a slot-filling workflow, 
    unless the patient explicitly shifts intent (e.g. asking to cancel).
    """
    text_lower = text.lower().strip()
    
    # Priority 1: Emergency check
    for pattern in PATTERNS["EMERGENCY_GUIDANCE"]:
        if re.search(pattern, text_lower):
            return "EMERGENCY_GUIDANCE"
            
    # Priority 2: Human escalation check
    for pattern in PATTERNS["HUMAN_ESCALATION"]:
        if re.search(pattern, text_lower):
            return "HUMAN_ESCALATION"

    # Priority 3: Language change check
    for pattern in PATTERNS["LANGUAGE_CHANGE"]:
        if re.search(pattern, text_lower):
            return "LANGUAGE_CHANGE"

    # Match other intents
    matched_intents = []
    for intent, patterns in PATTERNS.items():
        if intent in ["EMERGENCY_GUIDANCE", "HUMAN_ESCALATION", "LANGUAGE_CHANGE"]:
            continue
        for pattern in patterns:
            if re.search(pattern, text_lower):
                matched_intents.append(intent)
                break

    # If we are in an active transaction workflow (e.g. BOOK_APPOINTMENT slot filling),
    # preserve the current intent unless the user explicitly triggers an intent override (CANCEL, EMERGENCY, ESCALATION, LANGUAGE).
    if current_intent in ["BOOK_APPOINTMENT", "REGISTER_PATIENT", "IDENTIFY_PATIENT", "RESCHEDULE_APPOINTMENT", "CANCEL_APPOINTMENT"]:
        if "CANCEL_APPOINTMENT" in matched_intents and current_intent != "CANCEL_APPOINTMENT":
            return "CANCEL_APPOINTMENT"
        if "RESCHEDULE_APPOINTMENT" in matched_intents and current_intent != "RESCHEDULE_APPOINTMENT":
            return "RESCHEDULE_APPOINTMENT"
        return current_intent
                
    if matched_intents:
        # If multiple match, prioritize transactional intents
        for prio in ["REGISTER_PATIENT", "CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT", "APPOINTMENT_STATUS", "BOOK_APPOINTMENT", "DOCTOR_AVAILABILITY", "SYMPTOM_GUIDANCE", "PRE_ADMISSION", "HOSPITAL_INFORMATION", "GREETING"]:
            if prio in matched_intents:
                return prio
        return matched_intents[0]
        
    # If no intent matches but we have an ongoing workflow, keep it!
    if current_intent in ["REGISTER_PATIENT", "IDENTIFY_PATIENT", "BOOK_APPOINTMENT", "CANCEL_APPOINTMENT", "RESCHEDULE_APPOINTMENT", "POST_BOOKING"]:
        return current_intent

    return "UNKNOWN"
