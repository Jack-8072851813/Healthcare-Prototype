"""
voice_service.py
================
Coordinate voice processing pipeline for the Meridian Hospital AI Voice Desk.

Orchestrates:
  1. Speech-to-Text: transcribe audio file
  2. Orchestration: feed transcript to existing Agent Core
  3. Text-to-Speech: synthesize agent's response text to audio
  4. Returns playable audio & full metadata

Step 5.2 — Meridian Hospital POC
"""

import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from voice import speech_to_text
from voice import text_to_speech
import agent.agent_service as agent_service


def process_voice_input(
    audio_file_path: str,
    session_id: str,
    patient_code: str = None,
    language_override: str = None
) -> dict:
    """
    Main entry point for voice processing.
    """
    # 1. Speech-to-Text Transcription
    stt_provider = speech_to_text.get_stt_provider()
    stt_res = stt_provider.transcribe(audio_file_path, language=language_override)
    
    if not stt_res["success"] or stt_res["error"]:
        return {
            "success": False,
            "error": stt_res.get("error") or "Speech recognition failed",
            "transcript": "",
            "language": language_override or "ENGLISH",
            "response_text": "I couldn't understand the voice message clearly. Please try again.",
            "audio": ""
        }
        
    transcript = stt_res["text"]
    detected_lang = stt_res["language"]

    # 2. Process via existing Agent Core
    # Ensures we preserve intent tracking, context, tools (booking/rescheduling/RAG/safety)
    agent_res = agent_service.process_agent_message(
        conversation_code=session_id,
        patient_code=patient_code,
        message_text=transcript,
        language_override=detected_lang
    )

    if not agent_res.get("success"):
        return {
            "success": False,
            "error": "Agent core processing failed",
            "transcript": transcript,
            "language": detected_lang,
            "response_text": "I'm sorry, I encountered an issue processing your request. Please try again.",
            "audio": ""
        }

    response_text = agent_res["response"]
    final_lang = agent_res["language"]

    # 3. Text-to-Speech Synthesis
    tts_provider = text_to_speech.get_tts_provider()
    tts_res = tts_provider.synthesize(response_text, language=final_lang)

    if not tts_res["success"] or tts_res["error"]:
        # Fallback to text response but without audio
        return {
            "success": True,
            "transcript": transcript,
            "language": final_lang,
            "response_text": response_text,
            "audio": "",
            "intent": agent_res["intent"],
            "missing_information": agent_res["missing_information"],
            "tool_called": agent_res["tool_called"]
        }

    # 4. Return combined voice/text result
    return {
        "success": True,
        "transcript": transcript,
        "language": final_lang,
        "response_text": response_text,
        "audio": tts_res["audio_data"],
        "intent": agent_res["intent"],
        "missing_information": agent_res["missing_information"],
        "tool_called": agent_res["tool_called"]
    }
