"""
text_to_speech.py
=================
Text-to-Speech abstraction layer for the Meridian Hospital AI Voice Desk.

Supports: English, Tamil, Hindi, Telugu, Malayalam, Kannada, Urdu.
Enables pluggable/replaceable TTS providers.
Provides a mock implementation that generates valid base64 audio data URI silence/beeps.

Step 5.2 — Meridian Hospital POC
"""

import abc
import io
import wave
import base64
import os

class TextToSpeechProvider(abc.ABC):
    @abc.abstractmethod
    def synthesize(self, text: str, language: str) -> dict:
        """
        Synthesize text into speech audio.
        Returns a dict:
            {
                "success": bool,
                "audio_data": str,          # base64 data URI: "data:audio/wav;base64,..."
                "file_path": str,           # optional temporary physical file path
                "language": str,
                "error": str | None,
                "simulated": bool           # True if mock/simulated
            }
        """
        pass


class MockTextToSpeechProvider(TextToSpeechProvider):
    def synthesize(self, text: str, language: str) -> dict:
        """
        Generates a valid, tiny silent WAV audio file dynamically.
        Encodes it to a browser-playable base64 Data URI.
        """
        try:
            # Generate 0.1 seconds of silent WAV audio (8kHz, mono, 16-bit PCM)
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                # 800 frames = 0.1s at 8kHz sample rate
                wav.writeframes(b'\x00' * 1600)
            
            wav_bytes = wav_buffer.getvalue()
            base64_audio = base64.b64encode(wav_bytes).decode('utf-8')
            audio_data_uri = f"data:audio/wav;base64,{base64_audio}"
            
            # Write to a temporary file for API compliance if needed
            temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
            os.makedirs(temp_dir, exist_ok=True)
            temp_file_path = os.path.join(temp_dir, f"simulated_tts_{language.lower()}.wav")
            with open(temp_file_path, "wb") as f:
                f.write(wav_bytes)
                
            return {
                "success": True,
                "audio_data": audio_data_uri,
                "file_path": temp_file_path,
                "language": language,
                "error": None,
                "simulated": True
            }
        except Exception as e:
            return {
                "success": False,
                "audio_data": "",
                "file_path": "",
                "language": language,
                "error": str(e),
                "simulated": True
            }

# Default global provider
_current_tts_provider = MockTextToSpeechProvider()

def get_tts_provider() -> TextToSpeechProvider:
    return _current_tts_provider

def set_tts_provider(provider: TextToSpeechProvider):
    global _current_tts_provider
    _current_tts_provider = provider
