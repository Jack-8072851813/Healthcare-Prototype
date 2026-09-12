import re

# Complete Translation Bundles for 7 languages: 
# English, Tamil, Hindi, Telugu, Malayalam, Kannada, Urdu

TRANSLATIONS = {
    "ENGLISH": {
        "GREETING": "Hello! Welcome to Meridian Hospital. I am your AI Patient Desk Assistant. I can help you with appointments, doctor availability, appointment cancellation or rescheduling, hospital information, and pre-admission assistance. How can I help you today?",
        "ASK_PATIENT_CODE": "Please provide your registered patient code (e.g. P001).",
        "ASK_DEPT_OR_DOCTOR": "Which department or doctor would you like to consult?",
        "ASK_DATE": "What date would you prefer for the appointment? (e.g., today, tomorrow, next Monday)",
        "ASK_TIME": "What time would you prefer? (e.g., 10:00 AM, 11:30 AM)",
        "SLOTS_AVAILABLE": "We have these available slots on {date} for {doctor}: {slots}. Which one would you prefer?",
        "NO_SLOTS": "Sorry, there are no available slots for {doctor} on {date}. Would you like to select another date?",
        "BOOKING_SUCCESS": "Your appointment has been successfully booked! Booking ID: {booking_id} for {date} at {time} with {doctor}.",
        "SLOT_UNAVAILABLE": "Sorry, that slot is no longer available. Would you like to check other times?",
        "ASK_BOOKING_ID": "Please provide your booking ID (e.g. APT10001) so I can retrieve your appointment details.",
        "ASK_CANCEL_REASON": "Sure. May I know the reason for cancelling the appointment?",
        "CANCEL_SUCCESS": "Your appointment {booking_id} has been cancelled successfully.",
        "ASK_RESCHEDULE_DATE_TIME": "Please provide the new date and time you would prefer (e.g. tomorrow at 11:00 AM).",
        "ASK_RESCHEDULE_REASON": "Sure. May I know the reason for rescheduling?",
        "RESCHEDULE_SUCCESS": "Your appointment {booking_id} has been rescheduled to {date} at {time} successfully.",
        "STATUS_RESPONSE": "Your appointment {booking_id} with {doctor} is currently {status} for {date} at {time}.",
        "SYMPTOM_GUIDANCE": "Sorry you're feeling unwell. {dept} may be appropriate for these symptoms. Would you like me to check available doctors?",
        "EMERGENCY_GUIDANCE": "This may require urgent medical attention. Please seek emergency medical care immediately or contact emergency services. I can help with hospital information, but I should not delay emergency treatment.",
        "HUMAN_ESCALATION": "I can help connect you with the hospital support team.",
        "UNKNOWN": "I'm sorry, I didn't quite catch that. How can I help you with appointments, availability, or hospital info today?",
        "LANGUAGE_CHANGED": "Language has been changed to English.",
        "DOCTOR_NOT_FOUND": "I couldn't find a doctor with that name. Please check and try again.",
        "DOCTOR_NOT_AVAILABLE": "The doctor is not scheduled to work on {date}.",
        "INVALID_APPOINTMENT_SLOT": "The requested time is outside the doctor's schedule or doesn't match the slot duration.",
        "PATIENT_NOT_FOUND": "I couldn't find a matching patient record. Please provide your registered patient code.",
        "ACCESS_DENIED": "Access denied. You cannot access another patient's appointment details."
    },
    "TAMIL": {
        "GREETING": "வணக்கம்! மெரிடியன் மருத்துவமனைக்கு உங்களை வரவேற்கிறோம். நான் உங்கள் AI நோயாளி உதவி முகவர். அப்பாயிண்ட்மெண்ட், மருத்துவர் இருப்பு, ரத்து செய்தல் அல்லது மாற்றுதல் மற்றும் மருத்துவமனை தகவல்களுக்கு நான் உதவ முடியும். இன்று உங்களுக்கு நான் எவ்வாறு உதவ வேண்டும்?",
        "ASK_PATIENT_CODE": "உங்கள் பதிவு செய்யப்பட்ட நோயாளி குறியீட்டை (எ.கா. P001) வழங்கவும்.",
        "ASK_DEPT_OR_DOCTOR": "நீங்கள் எந்த துறை அல்லது மருத்துவரை அணுக விரும்புகிறீர்கள்?",
        "ASK_DATE": "அப்பாயிண்ட்மெண்டிற்கு எந்த தேதியை விரும்புகிறீர்கள்? (எ.கா. இன்று, நாளை, அடுத்த திங்கள்)",
        "ASK_TIME": "எந்த நேரத்தை விரும்புகிறீர்கள்? (எ.கா. காலை 10:00, முற்பகல் 11:30)",
        "SLOTS_AVAILABLE": "{doctor}-க்கு {date}-ல் இந்த நேரங்கள் காலியாக உள்ளன: {slots}. உங்களுக்கு எது வேண்டும்?",
        "NO_SLOTS": "வருந்துகிறோம், {date}-ல் {doctor}-க்கு எந்த நேரமும் காலியாக இல்லை. வேறு தேதியைத் தேர்ந்தெடுக்கிறீர்களா?",
        "BOOKING_SUCCESS": "உங்கள் அப்பாயிண்ட்மெண்ட் வெற்றிகரமாக பதிவு செய்யப்பட்டுள்ளது! முன்பதிவு எண்: {booking_id}, தேதி: {date}, நேரம்: {time}, மருத்துவர்: {doctor}.",
        "SLOT_UNAVAILABLE": "வருந்துகிறோம், அந்த நேரம் இப்போது கிடைக்கவில்லை. வேறு நேரத்தை சரிபார்க்கலாமா?",
        "ASK_BOOKING_ID": "உங்கள் முன்பதிவு எண்ணை (எ.கா. APT10001) வழங்கவும்.",
        "ASK_CANCEL_REASON": "நிச்சயமாக. அப்பாயிண்ட்மெண்ட்டை ரத்து செய்வதற்கான காரணத்தை அறியலாமா?",
        "CANCEL_SUCCESS": "உங்கள் அப்பாயிண்ட்மெண்ட் {booking_id} வெற்றிகரமாக ரத்து செய்யப்பட்டது.",
        "ASK_RESCHEDULE_DATE_TIME": "புதிய தேதி மற்றும் நேரத்தை வழங்கவும் (எ.கா. நாளை காலை 11:00 மணி).",
        "ASK_RESCHEDULE_REASON": "நிச்சயமாக. அப்பாயிண்ட்மெண்ட்டை மாற்றுவதற்கான காரணத்தை அறியலாமா?",
        "RESCHEDULE_SUCCESS": "உங்கள் அப்பாயிண்ட்மெண்ட் {booking_id} வெற்றிகரமாக {date} அன்று {time} மணிக்கு மாற்றப்பட்டது.",
        "STATUS_RESPONSE": "உங்கள் அப்பாயிண்ட்மெண்ட் {booking_id} ({doctor}), {date} அன்று {time} மணிக்கு {status} நிலையில் உள்ளது.",
        "SYMPTOM_GUIDANCE": "உடல்நலம் சரியில்லாததற்கு வருந்துகிறோம். இந்த அறிகுறிகளுக்கு {dept} பொருத்தமானதாக இருக்கலாம். அங்குள்ள மருத்துவர்களை சரிபார்க்கவா?",
        "EMERGENCY_GUIDANCE": "இதற்கு அவசர மருத்துவ சிகிச்சை தேவைப்படலாம். தயவுசெய்து உடனடியாக அவசர சிகிச்சையை நாடவும். நான் மருத்துவமனை தகவல்களுக்கு உதவ முடியும், ஆனால் அவசர சிகிச்சையைத் தாமதப்படுத்தக் கூடாது.",
        "HUMAN_ESCALATION": "மருத்துவமனை உதவி குழுவுடன் உங்களை இணைக்க நான் உதவ முடியும்.",
        "UNKNOWN": "மன்னிக்கவும், எனக்கு புரியவில்லை. அப்பாயிண்ட்மெண்ட்கள் அல்லது மருத்துவமனை தகவல்களுக்கு நான் எவ்வாறு உதவ வேண்டும்?",
        "LANGUAGE_CHANGED": "மொழி தமிழுக்கு மாற்றப்பட்டது."
    },
    "HINDI": {
        "GREETING": "नमस्ते! मेरिडियन अस्पताल में आपका स्वागत है। मैं आपका एआई पेशेंट डेस्क असिस्टेंट हूं। मैं अपॉइंटमेंट, डॉक्टर की उपलब्धता, अपॉइंटमेंट रद्द या पुनर्निर्धारित करने और अस्पताल की जानकारी में आपकी मदद कर सकता हूं। आज मैं आपकी क्या मदद कर सकता हूं?",
        "ASK_PATIENT_CODE": "कृपया अपना पंजीकृत रोगी कोड (जैसे P001) प्रदान करें।",
        "ASK_DEPT_OR_DOCTOR": "आप किस विभाग या डॉक्टर से परामर्श करना चाहते हैं?",
        "ASK_DATE": "आप अपॉइंटमेंट के लिए कौन सी तारीख पसंद करेंगे? (जैसे आज, कल, अगले सोमवार)",
        "ASK_TIME": "आप कौन सा समय पसंद करेंगे? (जैसे सुबह 10:00 बजे, 11:30 बजे)",
        "SLOTS_AVAILABLE": "{doctor} के लिए {date} को ये स्लॉट उपलब्ध हैं: {slots}। आप कौन सा पसंद करेंगे?",
        "NO_SLOTS": "क्षमा करें, {date} को {doctor} के लिए कोई स्लॉट उपलब्ध नहीं है। क्या आप कोई अन्य तारीख चुनना चाहेंगे?",
        "BOOKING_SUCCESS": "आपका अपॉइंटमेंट सफलतापूर्वक बुक हो गया है! बुकिंग आईडी: {booking_id}, तारीख: {date}, समय: {time}, डॉक्टर: {doctor}।",
        "SLOT_UNAVAILABLE": "क्षमा करें, वह स्लॉट अब उपलब्ध नहीं है। क्या आप अन्य समय की जांच करना चाहेंगे?",
        "ASK_BOOKING_ID": "कृपया अपनी बुकिंग आईडी (जैसे APT10001) प्रदान करें ताकि मैं आपकी अपॉइंटमेंट ढूंढ सकूं।",
        "ASK_CANCEL_REASON": "ज़रूर। क्या मैं अपॉइंटमेंट रद्द करने का कारण जान सकता हूँ?",
        "CANCEL_SUCCESS": "आपका अपॉइंटमेंट {booking_id} सफलतापूर्वक रद्द कर दिया गया है।",
        "ASK_RESCHEDULE_DATE_TIME": "कृपया नया दिन और समय बताएं (जैसे कल सुबह 11:00 बजे)।",
        "ASK_RESCHEDULE_REASON": "ज़रूर। क्या मैं अपॉइंटमेंट बदलने का कारण जान सकता हूँ?",
        "RESCHEDULE_SUCCESS": "आपका अपॉइंटमेंट {booking_id} सफलतापूर्वक {date} को {time} बजे के लिए पुनर्निर्धारित कर दिया गया है।",
        "STATUS_RESPONSE": "आपका अपॉइंटमेंट {booking_id} ({doctor}) के साथ {date} को {time} बजे वर्तमान में {status} है।",
        "SYMPTOM_GUIDANCE": "आपकी अस्वस्थता के लिए खेद है। इन लक्षणों के लिए {dept} उचित हो सकता है। क्या आप चाहते हैं कि मैं उपलब्ध डॉक्टरों की जांच करूं?",
        "EMERGENCY_GUIDANCE": "इसके लिए तत्काल चिकित्सा ध्यान देने की आवश्यकता हो सकती है। कृपया तुरंत आपातकालीन चिकित्सा सहायता लें। मैं अस्पताल की जानकारी में मदद कर सकता हूं, लेकिन आपातकालीन उपचार में देरी नहीं होनी चाहिए।",
        "HUMAN_ESCALATION": "मैं अस्पताल की सहायता टीम से जुड़ने में आपकी मदद कर सकता हूं।",
        "UNKNOWN": "क्षमा करें, मुझे समझ नहीं आया। मैं अपॉइंटमेंट या अस्पताल की जानकारी में आपकी क्या मदद कर सकता हूँ?",
        "LANGUAGE_CHANGED": "भाषा बदलकर हिंदी कर दी गई है।"
    },
    "TELUGU": {
        "GREETING": "నమస్తే! మెరిడియన్ హాస్పిటల్‌కు స్వాగతం. నేను మీ AI పేషెంట్ డెస్క్ అసిస్టెంట్‌ని. అపాయింట్‌మెంట్‌లు, డాక్టర్ అందుబాటు, రద్దు లేదా రీషెడ్యూల్ మరియు హాస్పిటల్ సమాచారం గురించి సహాయపడగలను. ఈ రోజు మీకు ఎలా సహాయపడాలి?",
        "ASK_PATIENT_CODE": "దయచేసి మీ రిజిస్టర్డ్ పేషెంట్ కోడ్ (ఉదా. P001) ఇవ్వండి.",
        "ASK_DEPT_OR_DOCTOR": "మీరు ఏ విభాగం లేదా డాక్టర్‌ను సంప్రదించాలనుకుంటున్నారు?",
        "ASK_DATE": "అపాయింట్‌మెంట్ కోసం ఏ తేదీని కోరుకుంటున్నారు? (ఉదా. ఈరోజు, రేపు, వచ్చే సోమవారం)",
        "ASK_TIME": "ఏ సమయాన్ని కోరుకుంటున్నారు? (ఉదా. ఉదయం 10:00, 11:30)",
        "SLOTS_AVAILABLE": "{date}న {doctor} కొరకు ఈ సమయాలు అందుబాటులో ఉన్నాయి: {slots}. మీరు దేనిని ఎంచుకుంటారు?",
        "BOOKING_SUCCESS": "మీ అపాయింట్‌మెంట్ విజయవంతంగా బుక్ చేయబడింది! బుకింగ్ ఐడి: {booking_id}, తేదీ: {date}, సమయం: {time}, డాక్టర్: {doctor}.",
        "SLOT_UNAVAILABLE": "క్షమించండి, ఆ సమయం అందుబాటులో లేదు. వేరే సమయం చూద్దామా?",
        "ASK_BOOKING_ID": "దయచేసి మీ బుకింగ్ ఐడి (ఉదా. APT10001) ఇవ్వండి.",
        "ASK_CANCEL_REASON": "తప్పకుండా. అపాయింట్‌మెంట్‌ను రద్దు చేయడానికి గల కారణాన్ని తెలుసుకోవచ్చా?",
        "CANCEL_SUCCESS": "మీ అపాయింట్‌మెంట్ {booking_id} విజయవంతంగా రద్దు చేయబడింది.",
        "ASK_RESCHEDULE_DATE_TIME": "దయచేసి కొత్త తేదీ మరియు సమయాన్ని ఇవ్వండి (ఉదా. రేపు ఉదయం 11:00 గంటలకు).",
        "ASK_RESCHEDULE_REASON": "తప్పకుండా. రీషెడ్యూల్ చేయడానికి గల కారణాన్ని తెలుసుకోవచ్చా?",
        "RESCHEDULE_SUCCESS": "మీ అపాయింట్‌మెంట్ {booking_id} విజయవంతంగా {date}న {time}కి రీషెడ్యూల్ చేయబడింది.",
        "STATUS_RESPONSE": "మీ అపాయింట్‌మెంట్ {booking_id} ({doctor}తో) {date}న {time}కి ప్రస్తుతం {status}లో ఉంది.",
        "SYMPTOM_GUIDANCE": "మీరు అనారోగ్యంగా ఉన్నందుకు విచారిస్తున్నాము. ఈ లక్షణాలకు {dept} సరిపోవచ్చు. అందుబాటులో ఉన్న డాక్టర్లను చూడమంటారా?",
        "EMERGENCY_GUIDANCE": "దీనికి అత్యవసర వైద్య సహాయం అవసరం కావచ్చు. దయచేసి వెంటనే అత్యవసర వైద్య సేవలను సంప్రదించండి.",
        "HUMAN_ESCALATION": "హాస్పిటల్ సపోర్ట్ టీమ్‌తో కనెక్ట్ కావడానికి నేను సహాయపడగలను.",
        "UNKNOWN": "క్షమించండి, నాకు అర్థం కాలేదు. అపాయింట్‌మెంట్‌లు లేదా హాస్పిటల్ సమాచారం గురించి మీకు ఎలా సహాయపడగలను?",
        "LANGUAGE_CHANGED": "భాష తెలుగులోకి మార్చబడింది."
    },
    "MALAYALAM": {
        "GREETING": "നമസ്കാരം! മെറിഡിയൻ ആശുപത്രിയിലേക്ക് സ്വാഗതം. ഞാൻ നിങ്ങളുടെ എഐ പേഷ്യന്റ് ഡെസ്ക് അസിസ്റ്റന്റ് ആണ്. അപ്പോയിന്റ്മെന്റുകൾ, ഡോക്ടറുടെ ലഭ്യത, ക്യാൻസലേഷൻ അല്ലെങ്കിൽ റീഷെഡ്യൂൾ ചെയ്യൽ, ആശുപത്രി വിവരങ്ങൾ എന്നിവയ്ക്ക് ഞാൻ സഹായിക്കാം. ഇന്ന് ഞാൻ എങ്ങനെ സഹായിക്കണം?",
        "ASK_PATIENT_CODE": "ദയവായി നിങ്ങളുടെ രജിസ്റ്റർ ചെയ്ത പേഷ്യന്റ് കോഡ് (ഉദാ. P001) നൽകുക.",
        "ASK_DEPT_OR_DOCTOR": "ഏത് വിഭാഗത്തിലോ ഡോക്ടറെയോ ആണ് കാണേണ്ടത്?",
        "ASK_DATE": "ഏത് തീയതിയിലാണ് അപ്പോയിന്റ്മെന്റ് വേണ്ടത്? (ഉദാ. ഇന്ന്, നാളെ, അടുത്ത തിങ്കൾ)",
        "ASK_TIME": "ഏത് സമയമാണ് നിങ്ങൾക്ക് താല്പര്യം? (ഉദാ. രാവിലെ 10:00, 11:30)",
        "SLOTS_AVAILABLE": "{date}-ൽ {doctor}-ക്ക് ഈ സമയങ്ങൾ ലഭ്യമാണ്: {slots}. ഏതാണ് താല്പര്യം?",
        "BOOKING_SUCCESS": "അപ്പോയിന്റ്മെന്റ് വിജയകരമായി ബുക്ക് ചെയ്തിരിക്കുന്നു! ബുക്കിംഗ് ഐഡി: {booking_id}, തീയതി: {date}, സമയം: {time}, ഡോക്ടർ: {doctor}.",
        "SLOT_UNAVAILABLE": "ക്ഷമിക്കണം, ആ സമയം ഇപ്പോൾ ലഭ്യമല്ല. മറ്റ് സമയങ്ങൾ നോക്കണോ?",
        "ASK_BOOKING_ID": "ദയവായി ബുക്കിംഗ് ഐഡി (ഉദാ. APT10001) നൽകുക.",
        "ASK_CANCEL_REASON": "തീർച്ചയായും. അപ്പോയിന്റ്മെന്റ് റദ്ദാക്കാനുള്ള കാരണം വ്യക്തമാക്കാമോ?",
        "CANCEL_SUCCESS": "നിങ്ങളുടെ അപ്പോയിന്റ്മെന്റ് {booking_id} വിജയകരമായി റദ്ദാക്കിയിരിക്കുന്നു.",
        "ASK_RESCHEDULE_DATE_TIME": "പുതിയ തീയതിയും സമയവും നൽകുക (ഉദാ. നാളെ രാവിലെ 11:00 മണിക്ക്).",
        "ASK_RESCHEDULE_REASON": "തീർച്ചയായും. മാറ്റാനുള്ള കാരണം വ്യക്തമാക്കാമോ?",
        "RESCHEDULE_SUCCESS": "അപ്പോയിന്റ്മെന്റ് {booking_id} വിജയകരമായി {date}-ൽ {time}-ലേക്ക് മാറ്റിയിരിക്കുന്നു.",
        "STATUS_RESPONSE": "{doctor}-യുമായുള്ള അപ്പോയിന്റ്മെന്റ് {booking_id} {date}-ൽ {time}-ൽ {status} ആണ്.",
        "SYMPTOM_GUIDANCE": "അസുഖം ബാധിച്ചതിൽ ഖേദിക്കുന്നു. ഈ ലക്ഷണങ്ങൾക്ക് {dept} അനുയോജ്യമായിരിക്കാം. ലഭ്യമായ ഡോക്ടർമാരെ നോക്കട്ടെ?",
        "EMERGENCY_GUIDANCE": "ഇതിന് അടിയന്തിര വൈദ്യസഹായം ആവശ്യമായി വന്നേക്കാം. ദയവായി എത്രയും വേഗം അടിയന്തിര ചികിത്സ തേടുക.",
        "HUMAN_ESCALATION": "ആശുപത്രി സഹായ ഗ്രൂപ്പുമായി ബന്ധപ്പെടാൻ ഞാൻ സഹായിക്കാം.",
        "UNKNOWN": "ക്ഷമിക്കണം, മനസ്സിലായില്ല. അപ്പോയിന്റ്മെന്റുകൾക്കോ ആശുപത്രി വിവരങ്ങൾക്കോ എങ്ങനെ സഹായിക്കണം?",
        "LANGUAGE_CHANGED": "ഭാഷ മലയാളത്തിലേക്ക് മാറ്റിയിരിക്കുന്നു."
    },
    "KANNADA": {
        "GREETING": "ನಮಸ್ಕಾರ! ಮೆರಿಡಿಯನ್ ಆಸ್ಪತ್ರೆಗೆ ಸುಸ್ವಾಗತ. ನಾನು ನಿಮ್ಮ AI ಪೇಷಂಟ್ ಡೆಸ್ಕ್ ಅಸಿಸ್ಟೆಂಟ್. ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಬುಕಿಂಗ್, ರದ್ದತಿ ಅಥವಾ ಮರು-ನಿಗದಿ ಮತ್ತು ಆಸ್ಪತ್ರೆ ಮಾಹಿತಿಯ ಬಗ್ಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ಇಂದು ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
        "ASK_PATIENT_CODE": "ದಯವಿಟ್ಟು ನಿಮ್ಮ ನೋಂದಾಯಿತ ಪೇಷಂಟ್ ಕೋಡ್ (ಉದಾ. P001) ಒದಗಿಸಿ.",
        "ASK_DEPT_OR_DOCTOR": "ನೀವು ಯಾವ ವಿಭಾಗ ಅಥವಾ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಲು ಬಯಸುತ್ತೀರಿ?",
        "ASK_DATE": "ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್‌ಗೆ ಯಾವ ದಿನಾಂಕವನ್ನು ಬಯಸುತ್ತೀರಿ? (ಉದಾ. ಇಂದು, ನಾಳೆ, ಮುಂದಿನ ಸೋಮವಾರ)",
        "ASK_TIME": "ಯಾವ ಸಮಯವನ್ನು ಬಯಸುತ್ತೀರಿ? (ಉದಾ. ಬೆಳಿಗ್ಗೆ 10:00, 11:30)",
        "SLOTS_AVAILABLE": "{date} ರಂದು {doctor} ರವರಿಗೆ ಈ ಸಮಯಗಳು ಲಭ್ಯವಿದೆ: {slots}. ನೀವು ಯಾವುದನ್ನು ಬಯಸುತ್ತೀರಿ?",
        "BOOKING_SUCCESS": "ನಿಮ್ಮ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಯಶಸ್ವಿಯಾಗಿ ಕಾಯ್ದಿರಿಸಲಾಗಿದೆ! ಬುಕಿಂಗ್ ಐಡಿ: {booking_id}, ದಿನಾಂಕ: {date}, ಸಮಯ: {time}, ವೈದ್ಯರು: {doctor}.",
        "SLOT_UNAVAILABLE": "ಕ್ಷಮಿಸಿ, ಆ ಸಮಯ ಲಭ್ಯವಿಲ್ಲ. ಬೇರೆ ಸಮಯ ನೋಡೋಣವೇ?",
        "ASK_BOOKING_ID": "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಬುಕಿಂಗ್ ಐಡಿ (ಉದಾ. APT10001) ಒದಗಿಸಿ.",
        "ASK_CANCEL_REASON": "ಖಂಡಿತ. ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ರದ್ದುಗೊಳಿಸಲು ಕಾರಣ ತಿಳಿಸಬಹುದೇ?",
        "CANCEL_SUCCESS": "ನಿಮ್ಮ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ {booking_id} ಯಶಸ್ವಿಯಾಗಿ ರದ್ದುಗೊಂಡಿದೆ.",
        "ASK_RESCHEDULE_DATE_TIME": "ದಯವಿಟ್ಟು ಹೊಸ ದಿನಾಂಕ ಮತ್ತು ಸಮಯವನ್ನು ಒದಗಿಸಿ (ಉದಾ. ನಾಳೆ ಬೆಳಿಗ್ಗೆ 11:00 గంటೆಗೆ).",
        "ASK_RESCHEDULE_REASON": "ಖಂಡಿತ. ಮರು-ನಿಗದಿಗೊಳಿಸಲು ಕಾರಣ ತಿಳಿಸಬಹುದೇ?",
        "RESCHEDULE_SUCCESS": "ನಿಮ್ಮ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ {booking_id} ಅನ್ನು {date} ರಂದು {time} ಕ್ಕೆ ಯಶಸ್ವಿಯಾಗಿ ಮರು-ನಿಗದಿಗೊಳಿಸಲಾಗಿದೆ.",
        "STATUS_RESPONSE": "ನಿಮ್ಮ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ {booking_id} ({doctor}) {date} ರಂದು {time} ಕ್ಕೆ ಪ್ರಸ್ತುತ {status} ಸ್ಥಿತಿಯಲ್ಲಿದೆ.",
        "SYMPTOM_GUIDANCE": "ನಿಮಗೆ ಹುಷಾರಿಲ್ಲದಿರುವುದಕ್ಕೆ ವಿಷಾದಿಸುತ್ತೇವೆ. ಈ ರೋಗಲಕ್ಷಣಗಳಿಗೆ {dept} ಸೂಕ್ತವಾಗಿರಬಹುದು. ಲಭ್ಯವಿರುವ ವೈದ್ಯರನ್ನು ನೋಡಲೇ?",
        "EMERGENCY_GUIDANCE": "ಇದಕ್ಕೆ ತುರ್ತು ವೈದ್ಯಕೀಯ ನೆರವು ಬೇಕಾಗಬಹುದು. ದಯವಿಟ್ಟು ತಕ್ಷಣ ತುರ್ತು ವೈದ್ಯಕೀಯ ಚಿಕಿತ್ಸೆ ಪಡೆಯಿರಿ.",
        "HUMAN_ESCALATION": "ಆಸ್ಪತ್ರೆಯ ಸಹಾಯ ತಂಡದೊಂದಿಗೆ ಸಂಪರ್ಕ ಹೊಂದಲು ನಾನು ಸಹಾಯ ಮಾಡಬಲ್ಲೆ.",
        "UNKNOWN": "ಕ್ಷಮಿಸಿ, ನನಗೆ ಅರ್ಥವಾಗಲಿಲ್ಲ. ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಅಥವಾ ಆಸ್ಪತ್ರೆ ಮಾಹಿತಿಗೆ ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?",
        "LANGUAGE_CHANGED": "ಭಾಷೆಯನ್ನು ಕನ್ನಡಕ್ಕೆ ಬದಲಾಯಿಸಲಾಗಿದೆ."
    },
    "URDU": {
        "GREETING": "ہیلو! میریڈین ہسپتال میں آپ کا خیر مقدم ہے۔ میں آپ کا اے آئی پیشنٹ ڈیسک اسسٹنٹ ہوں۔ میں اپائنٹمنٹ، ڈاکٹر کی دستیابی، اپائنٹمنٹ کی منسوخی یا تبدیلی اور ہسپتال کی معلومات میں مدد کر سکتا ہوں۔ آج میں آپ کی کیا مدد کر سکتا ہوں؟",
        "ASK_PATIENT_CODE": "براہ کرم اپنا رجسٹرڈ مریض کا کوڈ (جیسے P001) فراہم کریں۔",
        "ASK_DEPT_OR_DOCTOR": "آپ کس شعبہ یا ڈاکٹر سے مشورہ کرنا چاہتے ہیں؟",
        "ASK_DATE": "آپ اپائنٹمنٹ کے لیے کون سی تاریخ پسند کریں گے؟ (جیسے آج، کل، اگلے پیر کو)",
        "ASK_TIME": "آپ کون سا وقت پسند کریں گے؟ (جیسے صبح 10:00 بجے، 11:30 بجے)",
        "SLOTS_AVAILABLE": "{doctor} کے لیے {date} کو یہ وقت دستیاب ہیں: {slots}۔ آپ کون سا پسند کریں گے؟",
        "BOOKING_SUCCESS": "آپ کا اپائنٹمنٹ کامیابی سے بک ہو گیا ہے! بکنگ آئی ڈی: {booking_id}، تاریخ: {date}، وقت: {time}، ڈاکٹر: {doctor}۔",
        "SLOT_UNAVAILABLE": "معذرت، وہ وقت اب دستیاب نہیں ہے۔ کیا آپ کوئی دوسرا وقت چیک کرنا چاہیں گے؟",
        "ASK_BOOKING_ID": "براہ کرم اپنی بکنگ آئی ڈی (جیسے APT10001) فراہم کریں۔",
        "ASK_CANCEL_REASON": "جی بالکل۔ کیا میں اپائنٹمنٹ منسوخ کرنے کی وجہ جان سکتا ہوں؟",
        "CANCEL_SUCCESS": "آپ کا اپائنٹمنٹ {booking_id} کامیابی سے منسوخ کر دیا گیا ہے۔",
        "ASK_RESCHEDULE_DATE_TIME": "براہ کرم نیا دن اور وقت بتائیں (جیسے کل صبح 11:00 بجے)۔",
        "ASK_RESCHEDULE_REASON": "جی بالکل۔ کیا میں اپائنٹمنٹ تبدیل کرنے کی وجہ جان سکتا ہوں؟",
        "RESCHEDULE_SUCCESS": "آپ کا اپائنٹمنٹ {booking_id} کامیابی سے {date} کو {time} بجے کے لیے ری شیڈول کر دیا گیا ہے۔",
        "STATUS_RESPONSE": "آپ کا اپائنٹمنٹ {booking_id} ({doctor}) کے ساتھ {date} کو {time} بجے فی الحال {status} ہے۔",
        "SYMPTOM_GUIDANCE": "آپ کی طبیعت خرابی پر افسوس ہے۔ ان علامات کے لیے {dept} مناسب ہو سکتا ہے۔ کیا میں دستیاب ڈاکٹروں کو چیک کروں؟",
        "EMERGENCY_GUIDANCE": "اس کے لیے فوری طبی امداد کی ضرورت ہو سکتی ہے۔ براہ کرم فوری طور پر ہنگامی طبی مدد حاصل کریں۔",
        "HUMAN_ESCALATION": "میں ہسپتال کی سپورٹ ٹیم سے رابطہ قائم کرنے میں آپ کی مدد کر سکتا ہوں۔",
        "UNKNOWN": "معذرت، میں سمجھ نہیں سکا۔ میں اپائنٹمنٹ یا ہسپتال کی معلومات میں آپ کی کیا مدد کر سکتا ہوں؟",
        "LANGUAGE_CHANGED": "زبان اردو میں تبدیل کر دی گئی ہے۔"
    }
}

def detect_language_shift(text: str) -> str:
    """Detects if the user requested a language change in their message."""
    text_lower = (text or "").lower().strip()
    
    mapping = {
        "english": "ENGLISH",
        "english please": "ENGLISH",
        "tamil": "TAMIL",
        "தமிழில் பேசுங்கள்": "TAMIL",
        "தமிழில்": "TAMIL",
        "தமிழ்": "TAMIL",
        "hindi": "HINDI",
        "हिंदी में बात करें": "HINDI",
        "हिंदी में": "HINDI",
        "हिंदी": "HINDI",
        "telugu": "TELUGU",
        "తెలుగు": "TELUGU",
        "malayalam": "MALAYALAM",
        "മലയാളം": "MALAYALAM",
        "kannada": "KANNADA",
        "ಕನ್ನಡ": "KANNADA",
        "urdu": "URDU",
        "اردو": "URDU"
    }
    
    for key, lang in mapping.items():
        if key in text_lower:
            return lang
            
    return None


def detect_language(text: str, current_lang: str = None) -> str:
    """Detects the primary language of the user input string."""
    if not text:
        return current_lang or "ENGLISH"
    shift = detect_language_shift(text)
    if shift:
        return shift

    # Check script characters
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "TAMIL"
    if re.search(r"[\u0900-\u097F]", text):
        return "HINDI"
    if re.search(r"[\u0C00-\u0C7F]", text):
        return "TELUGU"
    if re.search(r"[\u0D00-\u0D7F]", text):
        return "MALAYALAM"
    if re.search(r"[\u0C80-\u0CFF]", text):
        return "KANNADA"
    if re.search(r"[\u0600-\u06FF]", text):
        return "URDU"

    # Short context-dependent messages, digits, times, or button clicks should NOT override established language
    t_clean = text.strip().lower()
    if current_lang and current_lang in {"TAMIL", "HINDI", "TELUGU", "MALAYALAM", "KANNADA", "URDU"}:
        if t_clean.startswith("btn_") or len(t_clean) <= 4 or re.match(r"^\d{1,2}(:\d{2})?\s*(am|pm)?$", t_clean) or t_clean in {
            "yes", "no", "ok", "okay", "confirm", "cancel", "tomorrow", "today",
            "same doctor", "change it", "10 am", "11 am", "10:00", "11:00", "11:30", "11:30 am", "10:30", "10:30 am", "12:00", "09:00", "09:30",
            "confirm appointment", "book appointment"
        }:
            return current_lang

    return "ENGLISH"


# Contextual Button Menu Translations for all 7 supported languages
# Note: Every button title MUST be <= 20 characters to comply with Meta WhatsApp Cloud API limits.

MENU_BUTTON_TRANSLATIONS = {
    "ENGLISH": {
        "btn_cat_doctors": "Doctors & Services",
        "btn_cat_health": "My Health & Records",
        "btn_cat_staff": "Talk to Staff",
        "btn_cat_emergency": "Emergency",
        "btn_find_doctor": "Find a Doctor",
        "btn_departments": "Departments",
        "btn_book_appt": "Book Appointment",
        "btn_doctor_avail": "Doctor Availability",
        "btn_my_profile": "My Profile",
        "btn_my_appts": "My Appointments",
        "btn_cancel_appt": "Cancel Appointment",
        "btn_reschedule_appt": "Reschedule Appt",
        "btn_hosp_info": "Hospital Information",
        "btn_my_reports": "My Reports",
        "btn_talk_staff_exec": "Talk to Staff",
        "btn_continue_ai": "Continue with AI",
        "btn_main_menu": "Main Menu"
    },
    "TAMIL": {
        "btn_cat_doctors": "மருத்துவர் & சேவை",
        "btn_cat_health": "உடல்நலம் & பதிவு",
        "btn_cat_staff": "பணியாளருடன் பேச",
        "btn_cat_emergency": "அவசரநிலை",
        "btn_find_doctor": "மருத்துவரைத் தேடு",
        "btn_departments": "துறைகள்",
        "btn_book_appt": "முன்பதிவு செய்ய",
        "btn_doctor_avail": "மருத்துவர் இருப்பு",
        "btn_my_profile": "எனது சுயவிவரம்",
        "btn_my_appts": "என் அப்பாயிண்ட்மெண்ட்",
        "btn_cancel_appt": "ரத்து செய்ய",
        "btn_reschedule_appt": "மாற்றி அமைக்க",
        "btn_hosp_info": "மருத்துவமனை தகவல்",
        "btn_my_reports": "எனது அறிக்கைகள்",
        "btn_talk_staff_exec": "பணியாளருடன் பேச",
        "btn_continue_ai": "AI-யுடன் தொடர",
        "btn_main_menu": "முதன்மை மெனு"
    },
    "HINDI": {
        "btn_cat_doctors": "डॉक्टर और सेवाएं",
        "btn_cat_health": "स्वास्थ्य व रिकॉर्ड",
        "btn_cat_staff": "स्टाफ से बात करें",
        "btn_cat_emergency": "आपातकालीन",
        "btn_find_doctor": "डॉक्टर खोजें",
        "btn_departments": "विभाग",
        "btn_book_appt": "अपॉइंटमेंट बुक करें",
        "btn_doctor_avail": "डॉक्टर उपलब्धता",
        "btn_my_profile": "मेरी प्रोफ़ाइल",
        "btn_my_appts": "मेरे अपॉइंटमेंट",
        "btn_cancel_appt": "रद्द करें",
        "btn_reschedule_appt": "पुनर्निर्धारित करें",
        "btn_hosp_info": "अस्पताल जानकारी",
        "btn_my_reports": "मेरी रिपोर्ट",
        "btn_talk_staff_exec": "स्टाफ से बात करें",
        "btn_continue_ai": "AI जारी रखें",
        "btn_main_menu": "मुख्य मेनू"
    },
    "TELUGU": {
        "btn_cat_doctors": "వైద్యులు & సేవలు",
        "btn_cat_health": "ఆరోగ్యం & రికార్డులు",
        "btn_cat_staff": "సిబ్బందితో మాట్లాడండి",
        "btn_cat_emergency": "అత్యవసరం",
        "btn_find_doctor": "డాక్టర్‌ను వెతకండి",
        "btn_departments": "విభాగాలు",
        "btn_book_appt": "అపాయింట్‌మెంట్ బుక్",
        "btn_doctor_avail": "డాక్టర్ లభ్యత",
        "btn_my_profile": "నా ప్రొఫైల్",
        "btn_my_appts": "నా అపాయింట్‌మెంట్‌లు",
        "btn_cancel_appt": "రద్దు చేయండి",
        "btn_reschedule_appt": "రీషెడ్యూల్",
        "btn_hosp_info": "ఆసుపత్రి సమాచారం",
        "btn_my_reports": "నా నివేదికలు",
        "btn_talk_staff_exec": "సిబ్బందితో మాట్లాడండి",
        "btn_continue_ai": "AI తో కొనసాగించు",
        "btn_main_menu": "ముఖ్య మెనూ"
    },
    "MALAYALAM": {
        "btn_cat_doctors": "ഡോക്ടറും സേവനവും",
        "btn_cat_health": "ആരോഗ്യ വിവരങ്ങൾ",
        "btn_cat_staff": "സ്റ്റാഫുമായി സംസാരിക്കൂ",
        "btn_cat_emergency": "അടിയന്തിരം",
        "btn_find_doctor": "ഡോക്ടറെ കണ്ടെത്തുക",
        "btn_departments": "വിഭാഗങ്ങൾ",
        "btn_book_appt": "അപ്പോയിന്റ്മെന്റ്",
        "btn_doctor_avail": "ഡോക്ടറുടെ ലഭ്യത",
        "btn_my_profile": "എന്റെ പ്രൊഫൈൽ",
        "btn_my_appts": "എന്റെ അപ്പോയിന്റ്മെന്റ്",
        "btn_cancel_appt": "റദ്ദാക്കുക",
        "btn_reschedule_appt": "റീഷെഡ്യൂൾ",
        "btn_hosp_info": "ആശുപത്രി വിവരങ്ങൾ",
        "btn_my_reports": "എന്റെ റിപ്പോർട്ടുകൾ",
        "btn_talk_staff_exec": "സ്റ്റാഫുമായി സംസാരിക്കൂ",
        "btn_continue_ai": "AI തുടരുക",
        "btn_main_menu": "പ്രധാന മെനു"
    },
    "KANNADA": {
        "btn_cat_doctors": "ವೈದ್ಯರು & ಸೇವೆಗಳು",
        "btn_cat_health": "ಆರೋಗ್ಯ & ದಾಖಲೆಗಳು",
        "btn_cat_staff": "ಸಿಬ್ಬಂದಿ ಜೊತೆ ಮಾತನಾಡಿ",
        "btn_cat_emergency": "ತುರ್ತು ಸೇವೆ",
        "btn_find_doctor": "ವೈದ್ಯರನ್ನು ಹುಡುಕಿ",
        "btn_departments": "ವಿಭಾಗಗಳು",
        "btn_book_appt": "ಬುಕಿಂಗ್ ಮಾಡಿ",
        "btn_doctor_avail": "ವೈದ್ಯರ ಲಭ್ಯತೆ",
        "btn_my_profile": "ನನ್ನ ಪ್ರೊಫೈಲ್",
        "btn_my_appts": "ನನ್ನ ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್",
        "btn_cancel_appt": "ರದ್ದುಗೊಳಿಸಿ",
        "btn_reschedule_appt": "ಮರು-ನಿಗದಿಗೊಳಿಸಿ",
        "btn_hosp_info": "ಆಸ್ಪತ್ರೆಯ ಮಾಹಿತಿ",
        "btn_my_reports": "ನನ್ನ ವರದಿಗಳು",
        "btn_talk_staff_exec": "ಸಿಬ್ಬಂದಿ ಜೊತೆ ಮಾತನಾಡಿ",
        "btn_continue_ai": "AI ಯೊಂದಿಗೆ ಮುಂದುವರಿಯಿರಿ",
        "btn_main_menu": "ಮುಖ್ಯ ಮೆನು"
    },
    "URDU": {
        "btn_cat_doctors": "ڈاکٹرز اور خدمات",
        "btn_cat_health": "صحت اور ریکارڈ",
        "btn_cat_staff": "اسٹاف سے بات کریں",
        "btn_cat_emergency": "ہنگامی علاج",
        "btn_find_doctor": "ڈاکٹر تلاش کریں",
        "btn_departments": "شعبہ جات",
        "btn_book_appt": "اپائنٹمنٹ بک کریں",
        "btn_doctor_avail": "ڈاکٹر کی دستیابی",
        "btn_my_profile": "میرا پروفائل",
        "btn_my_appts": "میری اپائنٹمنٹس",
        "btn_cancel_appt": "منسوخ کریں",
        "btn_reschedule_appt": "ری شیڈول کریں",
        "btn_hosp_info": "ہسپتال معلومات",
        "btn_my_reports": "میری رپورٹس",
        "btn_talk_staff_exec": "اسٹاف سے بات کریں",
        "btn_continue_ai": "AI کے ساتھ جاری رکھیں",
        "btn_main_menu": "مین مینو"
    }
}


def get_translated_button(btn_id: str, language: str = "ENGLISH") -> dict:
    """Returns a button dict {"id": btn_id, "title": title} translated to the requested language (max 20 chars)."""
    lang = language.upper() if language else "ENGLISH"
    if lang not in MENU_BUTTON_TRANSLATIONS:
        lang = "ENGLISH"
    title = MENU_BUTTON_TRANSLATIONS[lang].get(btn_id, MENU_BUTTON_TRANSLATIONS["ENGLISH"].get(btn_id, btn_id))
    return {"id": btn_id, "title": str(title)[:20]}


def get_main_menu_buttons(language: str = "ENGLISH") -> list:
    """Returns all 10 main menu options in patient's language."""
    return [
        get_translated_button("btn_cat_doctors", language),
        get_translated_button("btn_cat_health", language),
        get_translated_button("btn_book_appt", language),
        get_translated_button("btn_doctor_avail", language),
        get_translated_button("btn_my_appts", language),
        get_translated_button("btn_cancel_appt", language),
        get_translated_button("btn_reschedule_appt", language),
        get_translated_button("btn_hosp_info", language),
        get_translated_button("btn_cat_staff", language),
        get_translated_button("btn_cat_emergency", language)
    ]



def translate_response(key: str, language: str = "ENGLISH", **kwargs) -> str:
    """Translates a system message key into the selected language."""
    lang = language.upper() if language else "ENGLISH"
    if lang not in TRANSLATIONS:
        lang = "ENGLISH"
        
    bundle = TRANSLATIONS[lang]
    # Fallback to English if translation is missing for the key in that language
    template = bundle.get(key, TRANSLATIONS["ENGLISH"].get(key, "I didn't quite catch that."))
    
    # Translate some dynamic fields if they appear in kwargs
    # E.g. status translations, department names
    if "status" in kwargs and lang != "ENGLISH":
        status_map = {
            "BOOKED": {"TAMIL": "பதிவு செய்யப்பட்டுள்ளது", "HINDI": "बुक किया गया", "TELUGU": "బుక్ చేయబడింది", "MALAYALAM": "ബുക്ക് ചെയ്തിരിക്കുന്നു", "KANNADA": "ಕಾಯ್ದಿರಿಸಲಾಗಿದೆ", "URDU": "بک کیا گیا"},
            "CANCELLED": {"TAMIL": "ரத்து செய்யப்பட்டுள்ளது", "HINDI": "रद्द कर दिया गया", "TELUGU": "రద్దు చేయబడింది", "MALAYALAM": "റദ്ദാക്കിയിരിക്കുന്നു", "KANNADA": "ರದ್ದುಗೊಂಡಿದೆ", "URDU": "منسوخ کیا گیا"},
            "RESCHEDULED": {"TAMIL": "மாற்றப்பட்டுள்ளது", "HINDI": "पुनर्निर्धारित", "TELUGU": "రీషెడ్యూల్ చేయబడింది", "MALAYALAM": "റീഷെഡ്യൂൾ ചെയ്തിരിക്കുന്നു", "KANNADA": "ಮರು-ನಿಗದಿಗೊಳಿಸಲಾಗಿದೆ", "URDU": "ری شیڈول کیا گیا"}
        }
        old_val = kwargs["status"]
        if old_val in status_map:
            kwargs["status"] = status_map[old_val].get(lang, old_val)
            
    if "dept" in kwargs and lang != "ENGLISH":
        dept_map = {
            "General Medicine": {"TAMIL": "பொது மருத்துவம் (General Medicine)", "HINDI": "सामान्य चिकित्सा (General Medicine)", "TELUGU": "జనరల్ మెడిసిన్ (General Medicine)", "MALAYALAM": "ജനറൽ മെഡിസിൻ (General Medicine)", "KANNADA": "ಜನರಲ್ ಮೆಡಿಸಿನ್ (General Medicine)", "URDU": "جنرل میڈیسن (General Medicine)"},
            "Cardiology": {"TAMIL": "இருதயவியல் (Cardiology)", "HINDI": "हृदय रोग विज्ञान (Cardiology)", "TELUGU": "కార్డియాలజీ (Cardiology)", "MALAYALAM": "കാർഡിയോളജി (Cardiology)", "KANNADA": "ಕార్ಡಿಯಾಲಜಿ (Cardiology)", "URDU": "کارڈیالوجی (Cardiology)"}
        }
        old_val = kwargs["dept"]
        if old_val in dept_map:
            kwargs["dept"] = dept_map[old_val].get(lang, old_val)

    try:
        return template.format(**kwargs)
    except Exception:
        return template

# Programmatically append registration workflow translations for all 7 Indian languages
TRANSLATIONS["ENGLISH"]["GREETING"] = "Hello! Welcome to Meridian Hospital. I am your AI Patient Desk Assistant. I can help you with appointments, doctor availability, appointment cancellation or rescheduling, hospital information, and pre-admission assistance. Are you an existing patient or visiting us for the first time?"
TRANSLATIONS["ENGLISH"]["EXISTING_PATIENT_PROMPT"] = "Please provide your registered patient code (e.g. P001) or registered phone number so I can retrieve your record."
TRANSLATIONS["ENGLISH"]["NEW_PATIENT_PROMPT"] = "Welcome to Meridian Hospital. I'll help you get registered. May I have your full name?"
TRANSLATIONS["ENGLISH"]["ASK_DOB"] = "Thank you. May I have your date of birth? (YYYY-MM-DD)"
TRANSLATIONS["ENGLISH"]["ASK_GENDER"] = "May I have your gender? (Male/Female/Other)"
TRANSLATIONS["ENGLISH"]["ASK_PHONE"] = "May I have your contact phone number?"
TRANSLATIONS["ENGLISH"]["REGISTRATION_COMPLETE"] = "Your registration is complete. Your patient code is {patient_code}. How can I help you today?"

TRANSLATIONS["TAMIL"]["GREETING"] = "வணக்கம்! மெரிடியன் மருத்துவமனைக்கு உங்களை வரவேற்கிறோம். நான் உங்கள் AI நோயாளி உதவி முகவர். அப்பாயிண்ட்மெண்ட், மருத்துவர் இருப்பு, ரத்து செய்தல் அல்லது மாற்றுதல் மற்றும் மருத்துவமனை தகவல்களுக்கு நான் உதவ முடியும். நீங்கள் ஏற்கனவே எங்களிடம் சிகிச்சை பெற்று வரும் நோயாளி அல்லது முதல் முறையாக எங்களை தொடர்பு கொள்கிறீர்களா?"
TRANSLATIONS["TAMIL"]["EXISTING_PATIENT_PROMPT"] = "உங்கள் பதிவு செய்யப்பட்ட நோயாளி குறியீட்டை (எ.கா. P001) அல்லது பதிவு செய்யப்பட்ட தொலைபேசி எண்ணை வழங்கவும்."
TRANSLATIONS["TAMIL"]["NEW_PATIENT_PROMPT"] = "மெரிடியன் மருத்துவமனைக்கு உங்களை வரவேற்கிறோம். உங்களை பதிவு செய்ய நான் உதவுகிறேன். உங்கள் முழு பெயர் என்ன?"
TRANSLATIONS["TAMIL"]["ASK_DOB"] = "நன்றி. உங்கள் பிறந்த தேதியை வழங்கவும். (வருடம்-மாதம்-தேதி, எ.கா. 1990-06-15)"
TRANSLATIONS["TAMIL"]["ASK_GENDER"] = "உங்கள் பாலினம் என்ன? (ஆண்/பெண்/இதர)"
TRANSLATIONS["TAMIL"]["ASK_PHONE"] = "உங்கள் தொடர்பு தொலைபேసి எண்ணை வழங்கவும்."
TRANSLATIONS["TAMIL"]["REGISTRATION_COMPLETE"] = "உங்கள் பதிவு வெற்றிகரமாக முடிந்தது. உங்கள் நோயாளி குறியீடு: {patient_code}. இன்று உங்களுக்கு நான் எவ்வாறு உதவ வேண்டும்?"

TRANSLATIONS["HINDI"]["GREETING"] = "नमस्ते! मेरिडियन अस्पताल में आपका स्वागत है। मैं आपका एआई पेशेंट डेस्क असिस्टेंट हूं। मैं अपॉइंटमेंट, डॉक्टर की उपलब्धता, अपॉइंटमेंट रद्द या पुनर्निर्धारित करने और अस्पताल की जानकारी में आपकी मदद कर सकता हूं। क्या आप हमारे पंजीकृत मरीज हैं या पहली बार हमसे संपर्क कर रहे हैं?"
TRANSLATIONS["HINDI"]["EXISTING_PATIENT_PROMPT"] = "कृपया अपना पंजीकृत रोगी कोड (जैसे P001) या पंजीकृत फ़ोन नंबर प्रदान करें।"
TRANSLATIONS["HINDI"]["NEW_PATIENT_PROMPT"] = "मेरिडियन अस्पताल में आपका स्वागत है। मैं पंजीकरण में आपकी सहायता करूँगा। क्या मुझे आपका पूरा नाम मिल सकता है?"
TRANSLATIONS["HINDI"]["ASK_DOB"] = "धन्यवाद। क्या मुझे आपकी जन्मतिथि मिल सकती है? (YYYY-MM-DD)"
TRANSLATIONS["HINDI"]["ASK_GENDER"] = "आपका लिंग क्या है? (पुरुष/महिला/अन्य)"
TRANSLATIONS["HINDI"]["ASK_PHONE"] = "कृपया अपना संपर्क फ़ोन नंबर प्रदान करें।"
TRANSLATIONS["HINDI"]["REGISTRATION_COMPLETE"] = "आपका पंजीकरण पूरा हो गया है। आपका रोगी कोड {patient_code} है। आज मैं आपकी क्या मदद कर सकता हूँ?"

TRANSLATIONS["TELUGU"]["GREETING"] = "నమస్తే! మెరిడియన్ హాస్పిటల్‌కు స్వాగతం. నేను మీ AI పేషెంట్ డెస్క్ అసిస్టెంట్‌ని. అపాయింట్‌మెంట్‌లు, డాక్టర్ అందుబాటు, రద్దు లేదా రీషెడ్యూల్ మరియు హాస్పిటల్ సమాచారం గురించి సహాయపడగలను. మీరు మా పాత రోగి లేదా మొదటిసారి హాస్పిటల్‌ని సందర్శిస్తున్నారా?"
TRANSLATIONS["TELUGU"]["EXISTING_PATIENT_PROMPT"] = "దయచేసి మీ రిజిస్టర్డ్ పేషెంట్ కోడ్ (ఉదా. P001) లేదా రిజిస్టర్డ్ ఫోన్ నంబర్ ఇవ్వండి."
TRANSLATIONS["TELUGU"]["NEW_PATIENT_PROMPT"] = "మెరిడియన్ హాస్పిటల్‌కు స్వాగతం. నేను మీకు రిజిస్టర్ చేయడంలో సహాయపడతాను. దయచేసి మీ పూర్తి పేరు చెప్పండి?"
TRANSLATIONS["TELUGU"]["ASK_DOB"] = "ధన్యవాదాలు. దయచేసి మీ పుట్టిన తేదీని చెప్పండి? (YYYY-MM-DD)"
TRANSLATIONS["TELUGU"]["ASK_GENDER"] = "మీ లింగం ఏమిటి? (పురుషుడు/స్త్రీ/ఇతర)"
TRANSLATIONS["TELUGU"]["ASK_PHONE"] = "దయచేసి మీ ఫోన్ నంబర్ ఇవ్వండి."
TRANSLATIONS["TELUGU"]["REGISTRATION_COMPLETE"] = "మీ రిజిస్ట్రేషన్ పూర్తయింది. మీ పేషెంట్ కోడ్ {patient_code}. ఈ రోజు మీకు ఎలా సహాయపడాలి?"

TRANSLATIONS["MALAYALAM"]["GREETING"] = "നമസ്കാരം! മെറിഡിയൻ ആശുപത്രിയിലേക്ക് സ്വാഗതം. ഞാൻ നിങ്ങളുടെ എഐ പേഷ്യന്റ് ഡെസ്ക് അസിസ്റ്റന്റ് ആണ്. അപ്പോയിന്റ്മെന്റുകൾ, ഡോക്ടറുടെ ലഭ്യത, ക്യാൻസലേഷൻ അല്ലെങ്കിൽ റീഷെഡ്യൂൾ ചെയ്യൽ, ആശുപത്രി വിവരങ്ങൾ എന്നിവയ്ക്ക് ഞാൻ സഹായിക്കാം. നിങ്ങൾ ഇവിടെ മുൻപ് ചികിത്സ തേടിയിട്ടുള്ള ആളാണോ അതോ ആദ്യമായി വരികയാണോ?"
TRANSLATIONS["MALAYALAM"]["EXISTING_PATIENT_PROMPT"] = "ദയവായി നിങ്ങളുടെ രജിസ്റ്റർ ചെയ്ത പേഷ്യന്റ് കോഡ് (ഉദാ. P001) അല്ലെങ്കിൽ ഫോൺ നമ്പർ നൽകുക."
TRANSLATIONS["MALAYALAM"]["NEW_PATIENT_PROMPT"] = "മെറിഡിയൻ ആശുപത്രിയിലേക്ക് സ്വാഗതം. രജിസ്റ്റർ ചെയ്യാൻ ഞാൻ നിങ്ങളെ സഹായിക്കാം. നിങ്ങളുടെ പൂർണ്ണമായ പേര് പറയാമോ?"
TRANSLATIONS["MALAYALAM"]["ASK_DOB"] = "നന്ദി. ജനന തീയതി പറയാമോ? (YYYY-MM-DD)"
TRANSLATIONS["MALAYALAM"]["ASK_GENDER"] = "നിങ്ങളുടെ ലിംഗഭേദം ഏതാണ്? (ആൺ/പെൺ/മറ്റുള്ളവ)"
TRANSLATIONS["MALAYALAM"]["ASK_PHONE"] = "ദയവായി ഫോൺ നമ്പർ നൽകുക."
TRANSLATIONS["MALAYALAM"]["REGISTRATION_COMPLETE"] = "രജിസ്ട്രേഷൻ വിജയകരമായി പൂർത്തിയായിരിക്കുന്നു. നിങ്ങളുടെ പേഷ്യന്റ് കോഡ്: {patient_code}. ഇന്ന് ഞാൻ എങ്ങനെ സഹായിക്കണം?"

TRANSLATIONS["KANNADA"]["GREETING"] = "ನಮಸ್ಕಾರ! ಮೆರಿಡಿಯನ್ ಆಸ್ಪತ್ರೆಗೆ ಸುಸ್ವಾಗತ. ನಾನು ನಿಮ್ಮ AI ಪೇಷಂಟ್ ಡೆಸ್ಕ್ ಅಸಿಸ್ಟೆಂಟ್. ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ ಬುಕಿಂಗ್, ರದ್ದತಿ ಅಥವಾ ಮರು-ನಿಗದಿ ಮತ್ತು ಆಸ್ಪತ್ರೆ ಮಾಹಿತಿಯ ಬಗ್ಗೆ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ನೀವು ನಮ್ಮ ನೋಂದಾಯಿತ ರೋಗಿ ಅಥವಾ ಮೊದಲ ಬಾರಿಗೆ ಆಸ್ಪತ್ರೆಗೆ ಭೇಟಿ ನೀಡುತ್ತಿದ್ದೀರಾ?"
TRANSLATIONS["KANNADA"]["EXISTING_PATIENT_PROMPT"] = "ದಯವಿಟ್ಟು ನಿಮ್ಮ ನೋಂದಾಯಿತ ಪೇಷಂಟ್ ಕೋಡ್ (ಉದಾ. P001) ಅಥವಾ ಫೋನ್ ಸಂಖ್ಯೆಯನ್ನು ಒದಗಿಸಿ."
TRANSLATIONS["KANNADA"]["NEW_PATIENT_PROMPT"] = "ಮೆರಿಡಿಯನ್ ಆಸ್ಪತ್ರೆಗೆ ಸುಸ್ವಾಗತ. ನಾನು ನಿಮಗೆ ನೋಂದಾಯಿಸಲು ಸಹಾಯ ಮಾಡುತ್ತೇನೆ. ನಿಮ್ಮ ಪೂರ್ಣ ಹೆಸರು ಏನು?"
TRANSLATIONS["KANNADA"]["ASK_DOB"] = "ಧನ್ಯವಾದಗಳು. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಜನ್ಮ ದಿನಾಂకವನ್ನು ಒದಗಿಸಿ? (YYYY-MM-DD)"
TRANSLATIONS["KANNADA"]["ASK_GENDER"] = "ನಿಮ್ಮ ಲಿಂಗ ಯಾವುದು? (ಪ್ರುಷ/ಮಹಿಳೆ/ಇತರ)"
TRANSLATIONS["KANNADA"]["ASK_PHONE"] = "ದಯವಿಟ್ಟು ನಿಮ್ಮ ಫೋನ್ ಸಂಖ್ಯೆಯನ್ನು ಒದಗಿಸಿ."
TRANSLATIONS["KANNADA"]["REGISTRATION_COMPLETE"] = "ನಿಮ್ಮ ನೋಂದಣಿ ಯಶಸ್ವಿಯಾಗಿದೆ. ನಿಮ್ಮ ಪೇಷಂಟ್ ಕೋಡ್ {patient_code}. ಇಂದು ನಾನು ಹೇಗೆ ಸಹಾಯ ಮಾಡಲಿ?"

TRANSLATIONS["URDU"]["GREETING"] = "ہیلو! میریڈین ہسپتال میں آپ کا خیر مقدم ہے۔ میں آپ کا اے آئی پیشنٹ ڈیسک اسسٹنٹ ہوں۔ میں اپائنٹمنٹ، ڈاکٹر کی دستیابی، اپائنٹمنٹ کی منسوخی یا تبدیلی اور ہسپتال کی معلومات میں مدد کر سکتا ہوں۔ کیا آپ پرانے مریض ہیں یا پہلی بار تشریف لا رہے ہیں؟"
TRANSLATIONS["URDU"]["EXISTING_PATIENT_PROMPT"] = "براہ کرم اپنا رجسٹرڈ مریض کا کوڈ (جیسے P001) یا رجسٹرڈ فون نمبر فراہم کریں۔"
TRANSLATIONS["URDU"]["NEW_PATIENT_PROMPT"] = "میریڈین ہسپتال میں آپ کا خیر مقدم ہے۔ میں رجسٹریشن میں آپ کی مدد کروں گا۔ کیا مجھے آپ کا پورا نام مل سکتا ہے؟"
TRANSLATIONS["URDU"]["ASK_DOB"] = "شکریہ۔ کیا مجھے آپ کی تاریخ پیدائش مل سکتی ہے؟ (YYYY-MM-DD)"
TRANSLATIONS["URDU"]["ASK_GENDER"] = "آپ کی جنس کیا ہے؟ (مرد/عورت/دیگر)"
TRANSLATIONS["URDU"]["ASK_PHONE"] = "براہ کرم اپنا فون نمبر فراہم کریں۔"
TRANSLATIONS["URDU"]["REGISTRATION_COMPLETE"] = "آپ کی رجسٹریشن مکمل ہو گئی ہے۔ آپ کا مریض کوڈ {patient_code} ہے۔ آج میں آپ کی کیا مدد کر سکتا ہوں؟"

TALK_TO_STAFF_CONTACTS = {
    "ENGLISH": (
        "Certainly. Our hospital team can assist you.\n\n"
        "Hospital Staff Contacts:\n\n"
        "📞 General Enquiries:\n044 6666 9910\n\n"
        "📞 Appointment / Hospital Enquiries:\n044 6666 9910\n\n"
        "📞 Insurance Desk:\n044 6666 9910\n\n"
        "🚨 Emergency:\n044 6666 9999\n\n"
        "📧 Email:\ninfo@meridian-hospital.com\n\n"
        "📍 Address:\n#46D, Jawaharlal Nehru Road,\n200 Feet Ring Road,\nChennai – 600 099\n\n"
        "Our team can help with appointments, hospital information, insurance-related queries and other patient support.\n\n"
        "I am connecting you with a hospital staff member. An agent will be with you shortly."
    ),
    "TAMIL": (
        "நிச்சயமாக. எங்கள் மருத்துவமனை குழு உங்களுக்கு உதவ முடியும்.\n\n"
        "மருத்துவமனை தொடர்பு விவரங்கள்:\n\n"
        "📞 பொது விசாரணைகள்:\n044 6666 9910\n\n"
        "📞 அப்பாயிண்ட்மெண்ட் / மருத்துவமனை விசாரணைகள்:\n044 6666 9910\n\n"
        "📞 காப்பீட்டு பிரிவு (Insurance Desk):\n044 6666 9910\n\n"
        "🚨 அவசர சிகிச்சை:\n044 6666 9999\n\n"
        "📧 மின்னஞ்சல்:\ninfo@meridian-hospital.com\n\n"
        "📍 முகவரி:\n#46D, ஜவஹர்லால் நேரு சாலை,\n200 அடி ரிங் ரோடு,\nசென்னை – 600 099\n\n"
        "அப்பாயிண்ட்மெண்ட்கள், மருத்துவமனை தகவல்கள், காப்பீடு தொடர்பான கேள்விகள் மற்றும் பிற நோயாளி ஆதரவிற்கு எங்கள் குழு உதவ முடியும்.\n\n"
        "மருத்துவமனை உதவி குழுவுடன் உங்களை இணைக்கிறேன். ஒரு முகவர் விரைவில் உங்களுடன் பேசுவார்."
    ),
    "HINDI": (
        "निश्चित रूप से। हमारी अस्पताल टीम आपकी सहायता कर सकती है।\n\n"
        "अस्पताल संपर्क विवरण:\n\n"
        "📞 सामान्य पूछताछ:\n044 6666 9910\n\n"
        "📞 अपॉइंटमेंट / अस्पताल पूछताछ:\n044 6666 9910\n\n"
        "📞 इंश्योरेंस डेस्क:\n044 6666 9910\n\n"
        "🚨 आपातकालीन:\n044 6666 9999\n\n"
        "📧 ईमेल:\ninfo@meridian-hospital.com\n\n"
        "📍 पता:\n#46D, जवाहरलाल नेहरू रोड,\n200 फीट रिंग रोड,\nचेन्नई – 600 099\n\n"
        "हमारी टीम अपॉइंटमेंट, अस्पताल की जानकारी, बीमा संबंधी पूछताछ और अन्य सहायता में मदद कर सकती है।\n\n"
        "मैं आपको अस्पताल के कर्मचारी से जोड़ रहा हूं। एक एजेंट जल्द ही आपके साथ होगा।"
    ),
    "TELUGU": (
        "ఖచ్చితంగా. మా హాస్పిటల్ బృందం మీకు సహాయం చేయగలదు.\n\n"
        "హాస్పిటల్ సంప్రదింపు వివరాలు:\n\n"
        "📞 సాధారణ విచారణలు:\n044 6666 9910\n\n"
        "📞 అపాయింట్‌మెంట్ / హాస్పిటల్ విచారణలు:\n044 6666 9910\n\n"
        "📞 ఇన్సూరెన్స్ డెస్క్:\n044 6666 9910\n\n"
        "🚨 అత్యవసర సేవలు:\n044 6666 9999\n\n"
        "📧 ఈమెయిల్:\ninfo@meridian-hospital.com\n\n"
        "📍 చిరునామా:\n#46D, జవహర్‌లాల్ నెహ్రూ రోడ్,\n200 ఫీట్ రింగ్ రోడ్,\nచెన్నై – 600 099\n\n"
        "అపాయింట్‌మెంట్‌లు, హాస్పిటల్ సమాచారం, ఇన్సూరెన్స్ వివరాలు మరియు ఇతర సహాయం కొరకు మా బృందం సహాయం చేస్తుంది.\n\n"
        "నేను మిమ్మల్ని హాస్పిటల్ సిబ్బందితో కనెక్ట్ చేస్తున్నాను. ప్రతినిధి త్వరలోనే అందుబాటులోకి వస్తారు."
    ),
    "MALAYALAM": (
        "തീർച്ചയായും. ഞങ്ങളുടെ ആശുപത്രി ടീമിന് നിങ്ങളെ സഹായിക്കാനാകും.\n\n"
        "ആശുപത്രി ബന്ധപ്പെടേണ്ട വിവരങ്ങൾ:\n\n"
        "📞 പൊതു അന്വേഷണങ്ങൾ:\n044 6666 9910\n\n"
        "📞 അപ്പോയിന്റ്മെന്റ് / ആശുപത്രി അന്വേഷണങ്ങൾ:\n044 6666 9910\n\n"
        "📞 ഇൻഷുറൻസ് ഡെസ്ക്:\n044 6666 9910\n\n"
        "🚨 അടിയന്തര സേവനം:\n044 6666 9999\n\n"
        "📧 ഇമെയിൽ:\ninfo@meridian-hospital.com\n\n"
        "📍 മേൽവിലാസം:\n#46D, ജവഹർലാൽ നെഹ്റു റോഡ്,\n200 ഫീറ്റ് റിംഗ് റോഡ്,\nചെന്നൈ – 600 099\n\n"
        "അപ്പോയിന്റ്മെന്റുകൾ, ആശുപത്രി വിവരങ്ങൾ, ഇൻഷുറൻസ് സംശയങ്ങൾ എന്നിവയ്ക്ക് ഞങ്ങളുടെ ടീം സഹായിക്കും.\n\n"
        "ഞാൻ നിങ്ങളെ ആശുപത്രി ജീവനക്കാരുമായി ബന്ധപ്പെടുത്തുന്നു. ഒരു ഏജന്റ് ഉടൻ നിങ്ങളുമായി സംസാരിക്കും."
    ),
    "KANNADA": (
        "ಖಂಡಿತವಾಗಿ. ನಮ್ಮ ಆಸ್ಪತ್ರೆಯ ತಂಡವು ನಿಮಗೆ ಸಹಾಯ ಮಾಡುತ್ತದೆ.\n\n"
        "ಆಸ್ಪತ್ರೆ ಸಂಪರ್ಕ ವಿವರಗಳು:\n\n"
        "📞 ಸಾಮಾನ್ಯ ವಿಚಾರಣೆಗಳು:\n044 6666 9910\n\n"
        "📞 ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್ / ಆಸ್ಪತ್ರೆ ವಿಚಾರಣೆಗಳು:\n044 6666 9910\n\n"
        "📞 ಇನ್ಶೂರೆನ್ಸ್ ಡೆಸ್ಕ್:\n044 6666 9910\n\n"
        "🚨 ತುರ್ತು ಸೇವೆ:\n044 6666 9999\n\n"
        "📧 ಇಮೇಲ್:\ninfo@meridian-hospital.com\n\n"
        "📍 ವಿಳಾಸ:\n#46D, ಜವಾಹರ್‌ಲಾಲ್ ನೆಹರೂ ರಸ್ತೆ,\n200 ಫೀಟ್ ರಿಂಗ್ ರೋಡ್,\nಚೆನ್ನೈ – 600 099\n\n"
        "ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್‌ಗಳು, ಆಸ್ಪತ್ರೆ ಮಾಹಿತಿ, ಇನ್ಶೂರೆನ್ಸ್ ವಿಚಾರಣೆಗಳು ಮತ್ತು ಇತರ ನೆರವಿಗಾಗಿ ನಮ್ಮ ತಂಡ ಸಹಾಯ ಮಾಡುತ್ತದೆ.\n\n"
        "ನಾನು ನಿಮ್ಮನ್ನು ಆಸ್ಪತ್ರೆಯ ಸಿಬ್ಬಂದಿಯೊಂದಿಗೆ ಸಂಪರ್ಕಿಸುತ್ತಿದ್ದೇನೆ. ಏಜೆಂಟ್ ಶೀಘ್ರದಲ್ಲೇ ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸುತ್ತಾರೆ."
    ),
    "URDU": (
        "بالکل۔ ہماری ہسپتال کی ٹیم آپ کی مدد کر سکتی ہے۔\n\n"
        "ہسپتال کے رابطے کی تفصیلات:\n\n"
        "📞 عام پوچھ گچھ:\n044 6666 9910\n\n"
        "📞 اپائنٹمنٹ / ہسپتال انکوائری:\n044 6666 9910\n\n"
        "📞 انشورنس ڈیسک:\n044 6666 9910\n\n"
        "🚨 ہنگامی امداد:\n044 6666 9999\n\n"
        "📧 ای میل:\ninfo@meridian-hospital.com\n\n"
        "📍 پتہ:\n#46D, جواہر لعل نہرو روڈ,\n200 فٹ رنگ روڈ,\nچنئی – 600 099\n\n"
        "ہماری ٹیم اپائنٹمنٹ، ہسپتال کی معلومات، انشورنس کی معلومات اور دیگر مدد میں تعاون کر سکتی ہے۔\n\n"
        "میں آپ کو ہسپتال کے عملے سے جوڑ رہا ہوں۔ ایک ایجنٹ جلد ہی آپ کے ساتھ ہوگا۔"
    )
}

def get_talk_to_staff_contact_response(language: str = "ENGLISH") -> str:
    """Returns the verified hospital staff contact details + human escalation handoff message in the patient's language."""
    lang = (language or "ENGLISH").upper()
    if lang not in TALK_TO_STAFF_CONTACTS:
        lang = "ENGLISH"
    return TALK_TO_STAFF_CONTACTS[lang]

