"""
knowledge_service.py
====================
Higher-level knowledge service for the Meridian Hospital Agent.

Responsibilities:
  - Orchestrates retrieval via knowledge_retriever
  - Formats natural-language answers from retrieved chunks
  - Provides hallucination guard: returns structured signal when no knowledge found
  - Tracks source context (document_id, chunk_id, category) for audit

Step 5.1 — Meridian Hospital POC
"""

import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from knowledge import knowledge_retriever

# Minimum score threshold to accept FTS results (lower = more permissive)
MIN_SCORE_THRESHOLD = 0.0

# Hallucination-guard response when no knowledge is found
NO_KNOWLEDGE_RESPONSE = (
    "I don't have verified information about that yet. "
    "I can help you with appointments, doctor availability, "
    "hospital departments, OPD timings, location, pre-admission guidance, "
    "or general hospital information. How can I help you?"
)


def get_knowledge_context(
    query: str,
    language: str = "ENGLISH",
    category_hint: str = None,
    top_k: int = 3
) -> dict:
    """
    Retrieve relevant knowledge context for a patient query.

    Returns:
        {
            "found": bool,
            "chunks": [ { document_id, chunk_id, category, title, content, score } ],
            "source_context": [ { document_id, chunk_id, category } ]  # for audit
        }
    """
    results = knowledge_retriever.search(
        query=query,
        language=language,
        category_hint=category_hint,
        top_k=top_k
    )

    # Filter by minimum score threshold
    filtered = [r for r in results if r["score"] >= MIN_SCORE_THRESHOLD]

    source_context = [
        {
            "document_id": r["document_id"],
            "chunk_id": r["chunk_id"],
            "category": r["category"]
        }
        for r in filtered
    ]

    return {
        "found": len(filtered) > 0,
        "chunks": filtered,
        "source_context": source_context
    }


def answer_knowledge_question(
    query: str,
    language: str = "ENGLISH",
    category_hint: str = None,
    top_k: int = 3
) -> dict:
    """
    Generate a natural answer to a knowledge question.

    Returns:
        {
            "found": bool,
            "response": str,            # Natural language answer or no-knowledge message
            "source_context": list,     # Audit trail of chunks used
            "category": str | None      # Primary category of the answer
        }
    """
    ctx = get_knowledge_context(query, language, category_hint, top_k)

    if not ctx["found"]:
        return {
            "found": False,
            "response": NO_KNOWLEDGE_RESPONSE,
            "source_context": [],
            "category": None
        }

    # Build answer from top chunks
    chunks = ctx["chunks"]
    primary_category = chunks[0]["category"] if chunks else None

    # Combine content from top chunks (deduplicated)
    seen = set()
    content_parts = []
    for chunk in chunks:
        content = chunk["content"].strip()
        if content not in seen:
            seen.add(content)
            content_parts.append(content)

    # Join into a single answer
    answer = "\n\n".join(content_parts)

    # Translate English response to requested language for POC compliance
    lang_upper = (language or "ENGLISH").upper()
    translated_answer = translate_knowledge_answer(answer, primary_category, lang_upper)

    return {
        "found": True,
        "response": translated_answer,
        "source_context": ctx["source_context"],
        "category": primary_category
    }


def answer_by_category(category: str, language: str = "ENGLISH") -> dict:
    """
    Retrieve all knowledge for a specific document_type category.
    Used when the intent directly maps to a category (e.g. PRE_ADMISSION).
    """
    results = knowledge_retriever.search_by_category(category, top_k=5)

    if not results:
        return {
            "found": False,
            "response": NO_KNOWLEDGE_RESPONSE,
            "source_context": [],
            "category": category
        }

    seen = set()
    content_parts = []
    for r in results:
        content = r["content"].strip()
        if content not in seen:
            seen.add(content)
            content_parts.append(content)

    source_context = [
        {"document_id": r["document_id"], "chunk_id": r["chunk_id"], "category": r["category"]}
        for r in results
    ]

    answer = "\n\n".join(content_parts)
    lang_upper = (language or "ENGLISH").upper()
    translated_answer = translate_knowledge_answer(answer, category, lang_upper)

    return {
        "found": True,
        "response": translated_answer,
        "source_context": source_context,
        "category": category
    }


# Translation Bundle for 13 knowledge base categories across 7 languages
KNOWLEDGE_TRANSLATIONS = {
    "DEPARTMENT": {
        "TAMIL": "மெரிடியன் மருத்துவமனை பின்வரும் துறைகளில் சிறப்பு மருத்துவ வசதிகளை வழங்குகிறது:\n\nபொது மருத்துவம் (General Medicine), இருதயவியல் (Cardiology), குழந்தை மருத்துவம் (Pediatrics), எலும்பியல் (Orthopedics), தோல் மருத்துவம் (Dermatology), காது மூக்கு தொண்டை (ENT), மகப்பேறியல் (Gynecology), நரம்பியல் (Neurology).",
        "HINDI": "मेरिडियन अस्पताल सामान्य चिकित्सा (General Medicine), कार्डियोलॉजी (Cardiology), बाल रोग (Pediatrics), ऑर्थोपेडिक्स (Orthopedics), त्वचाविज्ञान (Dermatology), ईएनटी (ENT), स्त्री रोग (Gynecology) और न्यूरोलॉजी (Neurology) जैसे विभागों में विशेष चिकित्सा देखभाल प्रदान करता है।",
        "TELUGU": "మెరిడియన్ హాస్పిటల్ జనరల్ మెడిసిన్ (General Medicine), కార్డియాలజీ (Cardiology), పీడియాట్రిక్స్ (Pediatrics), ఆర్థోపెడిక్స్ (Orthopedics), డెర్మటాలジー (Dermatology), ఈఎన్‌టీ (ENT), గైనకాలజీ (Gynecology) మరియు న్యూరాలజీ (Neurology) విభాగాలలో వైద్య సేవలను అందిస్తుంది.",
        "MALAYALAM": "ജനറൽ മെഡിസിൻ, കാർഡിയോളജി, പീഡിയാട്രിക്സ്, ഓർത്തോപീഡിക്സ്, ഡെർമറ്റോളജി, ഇഎൻടി, ഗൈനക്കോളജി, ന്യൂറോളജി എന്നീ വിഭാഗങ്ങളിൽ മെറിഡിയൻ ആശുപത്രി പ്രത്യേക പരിചരണം നൽകുന്നു.",
        "KANNADA": "ಮೆರಿಡಿಯನ್ ಆಸ್ಪತ್ರೆಯು ಜನರಲ್ ಮೆಡಿಸಿನ್, ಕಾರ್ಡಿಯಾಲಜಿ, ಪೀಡಿಯಾಟ್ರಿಕ್ಸ್, ಆರ್ಥೋಪೆಡಿಕ್ಸ್, ಡರ್ಮಟಾಲಜಿ, ಇಎನ್‌ಟಿ, ಗೈನೆಕಾಲಜಿ ಮತ್ತು ನ್ಯೂರಾಲಜಿ ವಿಭಾಗಗಳಲ್ಲಿ ವೈದ್ಯಕೀಯ ಸೇವೆಗಳನ್ನು ನೀಡುತ್ತದೆ.",
        "URDU": "میریڈین ہسپتال جنرل میڈیسن، کارڈیالوجی، پیڈیاٹرکس، آرتھوپیڈکس، ڈرمیٹولوجی، ای این ٹی، گائناکالوجی اور نیورولوجی جیسے شعبوں میں خصوصی طبی خدمات فراہم کرتا ہے۔"
    },
    "HOSPITAL_PROFILE": {
        "TAMIL": "மெரிடியன் மருத்துவமனை 123 ஹெல்த்கேர் லேன், செக்டர் 4, வால்ஃப்ஸ் இந்தியா - 500001 என்ற முகவரியில் அமைந்துள்ளது. நீங்கள் எங்களை +91 99999 99999 என்ற எண்ணில் தொடர்பு கொள்ளலாம்.",
        "HINDI": "मेरिडियन अस्पताल 123 हेल्थकेयर लेन, सेक्टर 4, वाल्फ्स इंडिया - 500001 में स्थित है। आप हमसे +91 99999 99999 पर संपर्क कर सकते हैं।",
        "TELUGU": "మెరిడియన్ హాస్పిటల్ 123 హెల్త్‌కేర్ లేన్, సెక్టార్ 4, వాల్ఫ్స్ ఇండియా - 500001 లో ఉంది. మమ్మల్ని +91 99999 99999 లో సంప్రదించవచ్చు.",
        "MALAYALAM": "മെറിഡിയൻ ആശുപത്രി 123 ഹെൽത്ത് കെയർ ലെയ്ൻ, സെക്ടർ 4, വാൽഫ്സ് ഇന്ത്യ - 500001 എന്ന വിലാസത്തിലാണ് സ്ഥിതി ചെയ്യുന്നത്. ഞങ്ങളെ +91 99999 99999 എന്ന നമ്പറിൽ ബന്ധപ്പെടാം.",
        "KANNADA": "ಮೆರಿಡಿಯನ್ ಆಸ್ಪತ್ರೆಯು 123 ಹೆಲ್ತ್‌ಕೇರ್ ಲೇನ್, ಸೆಕ್ಟರ್ 4, ವಾಲ್ಫ್ಸ್ ಇಂಡಿಯಾ - 500001 ರಲ್ಲಿದೆ. ನಮ್ಮನ್ನು +91 99999 99999 ರಲ್ಲಿ ಸಂಪರ್ಕಿಸಬಹುದು.",
        "URDU": "میریڈین ہسپتال 123 ہیلتھ کیئر لین، سیکٹر 4، واالفس انڈیا - 500001 پر واقع ہے۔ آپ ہم سے +91 99999 99999 پر رابطہ کر سکتے ہیں۔"
    },
    "OPD_TIMING": {
        "TAMIL": "எங்கள் வெளிநோயாளிகள் பிரிவு (OPD) திங்கள் முதல் சனி வரை காலை 9:00 மணி முதல் மாலை 5:00 மணி வரை திறந்திருக்கும். அவசர சிகிச்சை 24 மணி நேரமும் செயல்படும்.",
        "HINDI": "हमारा आउट पेशेंट विभाग (ओपीडी) सोमवार से शनिवार सुबह 9:00 बजे से शाम 5:00 बजे तक खुला रहता है। आपातकालीन सेवाएं 24/7 खुली हैं।",
        "TELUGU": "మా అవుట్ పేషెంట్ విభాగం (OPD) సోమవారం నుండి శనివారం వరకు ఉదయం 9:00 నుండి సాయంత్రం 5:00 వరకు తెరిచి ఉంటుంది. అత్యవసర సేవలు 24/7 అందుబాటులో ఉంటాయి.",
        "MALAYALAM": "ഞങ്ങളുടെ ഔട്ട്പേഷ്യന്റ് വിഭാഗം (OPD) തിങ്കൾ മുതൽ ശനി വരെ രാവിലെ 9:00 മുതൽ വൈകുന്നേരം 5:00 വരെ പ്രവർത്തിക്കുന്നു. എമർജൻസി വിഭാഗം 24 മണിക്കൂറും പ്രവർത്തിക്കുന്നുണ്ട്.",
        "KANNADA": "ನಮ್ಮ ಹೊರರೋಗಿ ವಿಭಾಗವು (OPD) ಸೋಮವಾರದವರೆಗೆ ಶನಿವಾರದವರೆಗೆ ಬೆಳಿಗ್ಗೆ 9:00 ರಿಂದ ಸಂಜೆ 5:00 ರವರೆಗೆ ತೆರೆದಿರುತ್ತದೆ. ತುರ್ತು ಸೇವೆಗಳು 24/7 ಲಭ್ಯವಿದೆ.",
        "URDU": "ہمارا آؤٹ پیشنٹ ڈیپارٹمنٹ (OPD) پیر سے ہفتہ صبح 9:00 بجے سے شام 5:00 بجے تک کھلا رہتا ہے۔ ایمرجنسی سروسز 24/7 دستیاب ہیں۔"
    },
    "PRE_ADMISSION": {
        "TAMIL": "முன் சேர்க்கை மற்றும் அட்மிஷன் நடைமுறைகளுக்கு தேவையான அரசு அடையாள அட்டை, முந்தைய மருத்துவ அறிக்கைகள், மற்றும் காப்பீட்டு அட்டை ஆகியவற்றை எடுத்து வர வேண்டும்.",
        "HINDI": "प्री-एडमिशन और भर्ती प्रक्रियाओं के लिए आवश्यक सरकारी पहचान पत्र, पिछली चिकित्सा रिपोर्ट और बीमा कार्ड लाना अनिवार्य है।",
        "TELUGU": "అడ్మిషన్ ప్రక్రియ కోసం అవసరమైన ప్రభుత్వ గుర్তিంపు కార్డు, మునుపటి వైద్య నివేదికలు మరియు ఇన్సూరెన్స్ కార్డు తీసుకురావాలి.",
        "MALAYALAM": "അഡ്മിഷൻ നടപടികൾക്കായി ആവശ്യമായ സർക്കാർ തിരിച്ചറിയൽ കാർഡ്, മുൻകാല മെഡിക്കൽ റിപ്പോർട്ടുകൾ, ഇൻഷുറൻസ് കാർഡ് എന്നിവ കൊണ്ടുവരേണ്ടതുണ്ട്.",
        "KANNADA": "ದಾಖಲಾತಿ ಪ್ರಕ್ರಿಯೆಗಾಗಿ ಅಗತ್ಯವಿರುವ ಸರ್ಕಾರಿ ಗುರುತಿನ chheeti, ಹಿಂದಿನ ವೈದ್ಯಕೀಯ ವರದಿಗಳು ಮತ್ತು ವಿಮೆ ಕಾರ್ಡ್ ತರಬೇಕು.",
        "URDU": "داخلہ کے عمل کے لیے ضروری سرکاری شناختی کارڈ، پرانی طبی رپورٹس اور انشورنس کارڈ لانا ضروری ہے۔"
    },
    "ADMISSION": {
        "TAMIL": "அட்மிஷன் மற்றும் முன் சேர்க்கைக்கு தேவையான ஆவணங்கள்: அரசு அடையாள அட்டை, மருத்துவ பரிந்துரை கடிதம், மற்றும் காப்பீட்டு ஆவணங்கள்.",
        "HINDI": "प्रवेश के लिए आवश्यक दस्तावेज: सरकारी पहचान पत्र, डॉक्टर का रेफरल पत्र और बीमा दस्तावेज।",
        "TELUGU": "అడ్మిషన్ కోసం అవసరమైన పత్రాలు: ప్రభుత్వ గుర్తింపు కార్డు, డాక్టర్ రెఫరల్ లెటర్ మరియు ఇన్సూరెన్స్ పత్రాలు.",
        "MALAYALAM": "അഡ്മിഷനായി ആവശ്യമായ രേഖകൾ: സർക്കാർ തിരിച്ചറിയൽ കാർഡ്, ഡോക്ടറുടെ റഫറൽ കത്ത്, ഇൻഷുറൻസ് രേഖകൾ.",
        "KANNADA": "ದಾಖಲಾತಿಗಾಗಿ ಬೇಕಾಗುವ ದಾಖಲೆಗಳು: ಸರ್ಕಾರಿ ಗುರುತಿನ ಚೀಟಿ, ವೈದ್ಯರ ರೆಫರಲ್ ಪತ್ರ ಮತ್ತು ವಿಮಾ ದಾಖಲೆಗಳು.",
        "URDU": "داخلہ کے لیے ضروری دستاویزات: سرکاری شناختی کارڈ، ڈاکٹر کا ریفرل لیٹر اور انشورنس دستاویزات۔"
    }
}

# Alias mapping in case category is plural or slightly different
CATEGORY_ALIASES = {
    "DEPARTMENTS": "DEPARTMENT",
    "LOCATION": "HOSPITAL_PROFILE",
    "FAQ": "DEPARTMENT",
    "HOSPITAL_SERVICE": "DEPARTMENT",
    "ADMISSION_DOCUMENTS": "ADMISSION"
}

def translate_knowledge_answer(english_text: str, category: str, language: str) -> str:
    if not language or language.upper() == "ENGLISH":
        return english_text
        
    lang = language.upper()
    cat = (category or "").upper()
    mapped_cat = CATEGORY_ALIASES.get(cat, cat)
    
    if mapped_cat in KNOWLEDGE_TRANSLATIONS and lang in KNOWLEDGE_TRANSLATIONS[mapped_cat]:
        return KNOWLEDGE_TRANSLATIONS[mapped_cat][lang]
        
    return english_text
