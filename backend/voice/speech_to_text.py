"""
speech_to_text.py
=================
Speech-to-Text abstraction layer for the Meridian Hospital AI Voice Desk.

Supports: English, Tamil, Hindi, Telugu, Malayalam, Kannada, Urdu.
Enables pluggable/replaceable STT providers.
Provides a mock implementation for development and testing.

Step 5.2 — Meridian Hospital POC
"""

import abc
import os

class SpeechToTextProvider(abc.ABC):
    @abc.abstractmethod
    def transcribe(self, audio_file_path: str, language: str = None) -> dict:
        """
        Transcribe the audio file.
        Returns a dict:
            {
                "success": bool,
                "text": str,
                "language": str,
                "confidence": float,
                "error": str | None
            }
        """
        pass

# Idempotent mock lookup table for test scenarios and simulations
MOCK_TRANSCRIPTION_MAP = {
    "english_greet": ("Hi", "ENGLISH"),
    "english_appointment": ("I want to book an appointment", "ENGLISH"),
    "english_cardiologist": ("I want to book an appointment with a cardiologist tomorrow", "ENGLISH"),
    "english_tomorrow": ("I want an appointment tomorrow", "ENGLISH"),
    "english_timing": ("What are the hospital timings?", "ENGLISH"),
    "english_location": ("Where is Meridian Hospital?", "ENGLISH"),
    "english_cancel": ("I want to cancel my appointment", "ENGLISH"),
    "english_reschedule": ("I want to reschedule my appointment", "ENGLISH"),
    "english_doctor": ("Is Dr. Arun available tomorrow?", "ENGLISH"),
    "english_fever": ("I have fever", "ENGLISH"),
    "english_chest_pain": ("I have severe chest pain", "ENGLISH"),
    "english_pre_admission": ("What is the pre-admission process?", "ENGLISH"),
    "english_admission_docs": ("What documents do I need for admission?", "ENGLISH"),
    "english_mars_alien": ("What is the hospital's policy on alien patients from Mars?", "ENGLISH"),
    "english_switch": ("What are the OPD timings?", "ENGLISH"),
    "english_fee": ("What is the consultation fee?", "ENGLISH"),
    
    # Multilingual inputs
    "tamil_hospital": ("மருத்துவமனை எங்கே உள்ளது?", "TAMIL"),
    "tamil_where": ("மருத்துவமனை எங்கே உள்ளது?", "TAMIL"),
    "tamil_greet": ("வணக்கம்", "TAMIL"),
    "tamil_new": ("நான் புதிய நோயாளி", "TAMIL"),
    "tamil_departments": ("மருத்துவமனையில் என்னென்ன துறைகள் உள்ளன?", "TAMIL"),
    "tamil_switch": ("தமிழில் சொல்லுங்கள்", "TAMIL"),
    
    "hindi_greet": ("नमस्ते", "HINDI"),
    "hindi_where": ("अस्पताल कहाँ है?", "HINDI"),
    "hindi_fever": ("मुझे बुखार है", "HINDI"),
    "hindi_switch": ("हिंदी में बताइए", "HINDI"),
    
    "telugu_where": ("ఆసుపత్రి ఎక్కడ ఉంది?", "TELUGU"),
    "telugu_greet": ("నమస్తే", "TELUGU"),
    
    "malayalam_where": ("ആശുപത്രി എവിടെ ആണ്?", "MALAYALAM"),
    "malayalam_greet": ("ഹലോ", "MALAYALAM"),
    
    "kannada_where": ("ಆಸ್ಪತ್ರೆ ಎಲ್ಲಿದೆ?", "KANNADA"),
    "kannada_greet": ("ಹಲೋ", "KANNADA"),
    
    "urdu_where": ("ہسپتال کہاں ہے؟", "URDU"),
    "urdu_greet": ("ہیلو", "URDU")
}


class MockSpeechToTextProvider(SpeechToTextProvider):
    def transcribe(self, audio_file_path: str, language: str = None) -> dict:
        """
        Mock transcription using filename lookup or default language placeholders.
        Guarantees 100% deterministic behaviour for the validation tests.
        """
        filename = os.path.basename(audio_file_path).lower()
        
        # Look for matching pattern in transcription map
        matched_text = None
        detected_lang = language or "ENGLISH"
        
        for key, val in MOCK_TRANSCRIPTION_MAP.items():
            if key in filename:
                matched_text, detected_lang = val
                break
                
        if matched_text is None:
            # Fallback if no match: return a generic statement in the requested language
            lang_upper = (language or "ENGLISH").upper()
            if lang_upper == "TAMIL":
                matched_text = "வணக்கம் மெரிடியன் மருத்துவமனை"
                detected_lang = "TAMIL"
            elif lang_upper == "HINDI":
                matched_text = "नमस्ते मेरिडियन अस्पताल"
                detected_lang = "HINDI"
            elif lang_upper == "TELUGU":
                matched_text = "నమస్తే మెరిడియన్ హాస్పిటల్"
                detected_lang = "TELUGU"
            elif lang_upper == "MALAYALAM":
                matched_text = "ഹലോ മെറിഡിയൻ ആശുപത്രി"
                detected_lang = "MALAYALAM"
            elif lang_upper == "KANNADA":
                matched_text = "ಹಲೋ ಮೆರಿಡಿಯನ್ ಆಸ್ಪತ್ರೆ"
                detected_lang = "KANNADA"
            elif lang_upper == "URDU":
                matched_text = "ہیلو میریڈین ہسپتال"
                detected_lang = "URDU"
            else:
                matched_text = "Hello Meridian Hospital"
                detected_lang = "ENGLISH"

        return {
            "success": True,
            "text": matched_text,
            "language": detected_lang,
            "confidence": 0.98,
            "error": None
        }

# Default global provider
_current_stt_provider = MockSpeechToTextProvider()

def get_stt_provider() -> SpeechToTextProvider:
    return _current_stt_provider

def set_stt_provider(provider: SpeechToTextProvider):
    global _current_stt_provider
    _current_stt_provider = provider
