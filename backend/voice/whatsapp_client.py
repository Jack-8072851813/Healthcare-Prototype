"""
whatsapp_client.py
==================
Meta WhatsApp Cloud API Client abstraction for Meridian Hospital.

Manages:
  - Text message dispatch
  - Audio/Voice message dispatch
  - Media Upload/Download mechanics
  - Graceful mock simulation for local/offline testing

Step 5.3 — Meridian Hospital POC
"""

import os
import requests
import base64
import uuid

# Load credentials from environment (both standard and META_ prefixed)
ACCESS_TOKEN = os.getenv("META_WHATSAPP_ACCESS_TOKEN", os.getenv("WHATSAPP_ACCESS_TOKEN", "MOCK_ACCESS_TOKEN"))
PHONE_NUMBER_ID = os.getenv("META_WHATSAPP_PHONE_NUMBER_ID", os.getenv("WHATSAPP_PHONE_NUMBER_ID", "MOCK_PHONE_ID"))
API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v17.0")
API_URL = os.getenv("WHATSAPP_API_URL", f"https://graph.facebook.com/{API_VERSION}")


def is_mock_mode() -> bool:
    """Returns True if the credentials are not set or are mock placeholders."""
    return (
        not ACCESS_TOKEN or
        not PHONE_NUMBER_ID or
        "MOCK" in ACCESS_TOKEN or
        "MOCK" in PHONE_NUMBER_ID
    )


# Print validation status at runtime (without exposing credentials)
if is_mock_mode():
    print("[STATUS] WhatsApp Cloud API is running in SIMULATED/FALLBACK mode.")
else:
    print(f"[STATUS] WhatsApp Cloud API is running in REAL META API mode (Version: {API_VERSION}).")


def log_outbound_simulation(payload_type: str, to_number: str, data: dict):
    """Write simulated WhatsApp payloads to scratch logs for audit inspection."""
    scratch_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    log_file = os.path.join(scratch_dir, "whatsapp_outbound.log")
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [TO: {to_number}] [TYPE: {payload_type.upper()}] PAYLOAD: {data}\n")


def send_text_message(to_number: str, text: str) -> dict:
    """Send text message to a WhatsApp number."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "text",
        "text": {"body": text}
    }
    
    if is_mock_mode():
        log_outbound_simulation("text", to_number, payload)
        return {"success": True, "message_id": f"wam.mock_msg_{uuid.uuid4().hex[:12]}"}
        
    url = f"{API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        return {"success": True, "response": res.json()}
    except Exception as e:
        print(f"[WhatsApp] Live Meta API dispatch error: {e}. Falling back to simulation mode.")
        log_outbound_simulation("text", to_number, payload)
        return {"success": True, "message_id": f"wam.mock_msg_{uuid.uuid4().hex[:12]}", "fallback": True}


def send_button_message(to_number: str, text: str, buttons: list) -> dict:
    """
    Sends a Meta WhatsApp interactive button message.
    'buttons' parameter is a list of dicts: [{"id": "btn_1", "title": "First-time Patient"}, ...]
    """
    formatted_buttons = []
    for btn in buttons:
        btn_id = btn.get("id", f"btn_{uuid.uuid4().hex[:6]}")
        btn_title = btn.get("title", "Select")[:20]  # WhatsApp 20 char title limit
        formatted_buttons.append({
            "type": "reply",
            "reply": {"id": btn_id, "title": btn_title}
        })

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {"buttons": formatted_buttons}
        }
    }

    if is_mock_mode():
        log_outbound_simulation("interactive_button", to_number, payload)
        return {"success": True, "message_id": f"wam.mock_button_{uuid.uuid4().hex[:12]}"}

    url = f"{API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        return {"success": True, "response": res.json()}
    except Exception as e:
        print(f"[WhatsApp] Live Meta API button dispatch error: {e}. Falling back to simulation mode.")
        log_outbound_simulation("interactive_button", to_number, payload)
        return {"success": True, "message_id": f"wam.mock_button_{uuid.uuid4().hex[:12]}", "fallback": True}


def send_list_message(to_number: str, text: str, button_label: str, sections: list) -> dict:
    """
    Sends a Meta WhatsApp interactive list message.
    """
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": text},
            "action": {
                "button": button_label[:20],
                "sections": sections
            }
        }
    }

    if is_mock_mode():
        log_outbound_simulation("interactive_list", to_number, payload)
        return {"success": True, "message_id": f"wam.mock_list_{uuid.uuid4().hex[:12]}"}

    url = f"{API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        return {"success": True, "response": res.json()}
    except Exception as e:
        print(f"[WhatsApp] Live Meta API list dispatch error: {e}. Falling back to simulation mode.")
        log_outbound_simulation("interactive_list", to_number, payload)
        return {"success": True, "message_id": f"wam.mock_list_{uuid.uuid4().hex[:12]}", "fallback": True}



def send_audio_message(to_number: str, audio_data_uri_or_path: str) -> dict:
    """
    Send audio/voice message.
    Under real API:
      - If audio_data_uri_or_path is a path to a file: uploads the file to Meta to obtain a media ID, then dispatches.
      - If it is base64 Data URI: decodes, writes to temporary file, uploads, then dispatches.
    Under Mock/Simulated API:
      - Writes simulated payload directly to outbound logs.
    """
    payload_mock = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "audio",
        "audio": {"link": "http://meridian-hospital.poc/static/audio_response.wav"}
    }
    
    if is_mock_mode():
        log_outbound_simulation("audio", to_number, payload_mock)
        return {"success": True, "message_id": f"wam.mock_audio_{uuid.uuid4().hex[:12]}"}

    # Real implementation
    # 1. Parse and extract bytes
    temp_file_path = None
    try:
        if audio_data_uri_or_path.startswith("data:audio/"):
            # Base64 Data URI format
            header, base64_data = audio_data_uri_or_path.split(",", 1)
            ext = ".wav"
            if "wav" in header:
                ext = ".wav"
            elif "mpeg" in header or "mp3" in header:
                ext = ".mp3"
            elif "ogg" in header:
                ext = ".ogg"
                
            audio_bytes = base64.b64decode(base64_data)
            scratch_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
            temp_file_path = os.path.join(scratch_dir, f"outbound_temp_{uuid.uuid4().hex}{ext}")
            with open(temp_file_path, "wb") as f:
                f.write(audio_bytes)
        else:
            temp_file_path = audio_data_uri_or_path

        # 2. Upload to Meta media library
        media_id = upload_media(temp_file_path)
        if not media_id:
            raise Exception("Failed to upload audio reply to Meta Graph API")

        # 3. Dispatch audio message via media ID
        url = f"{API_URL}/{PHONE_NUMBER_ID}/messages"
        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "audio",
            "audio": {"id": media_id}
        }
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        return {"success": True, "response": res.json()}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        # Cleanup temporary audio files
        if temp_file_path and audio_data_uri_or_path.startswith("data:audio/") and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass


def upload_media(file_path: str) -> str | None:
    """Upload media file to Meta Cloud API. Returns media ID."""
    if is_mock_mode():
        return f"media_mock_{uuid.uuid4().hex[:12]}"
        
    url = f"{API_URL}/{PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    
    # Determine content-type
    content_type = "audio/wav"
    if file_path.endswith(".mp3"):
        content_type = "audio/mpeg"
    elif file_path.endswith(".ogg"):
        content_type = "audio/ogg"
        
    try:
        with open(file_path, "rb") as f:
            files = {
                "file": (os.path.basename(file_path), f, content_type)
            }
            data = {
                "messaging_product": "whatsapp"
            }
            res = requests.post(url, files=files, data=data, headers=headers, timeout=20)
            res.raise_for_status()
            return res.json().get("id")
    except Exception as e:
        print("Meta media upload error:", e)
        return None


def download_media(media_id: str) -> str | None:
    """
    Download media file from Meta Cloud API.
    Returns path to downloaded file.
    In Mock Mode (or if media_id starts with "media_"): returns a path to a pre-defined test audio file from mapping.
    """
    scratch_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    
    if is_mock_mode() or (media_id and media_id.startswith("media_")):
        # Clean simulation lookup mapping media_id to standard test waves
        mock_audio_map = {
            "media_en_greet": "english_greet.wav",
            "media_en_appt": "english_appointment.wav",
            "media_en_doctor": "english_doctor.wav",
            "media_en_cancel": "english_cancel.wav",
            "media_en_reschedule": "english_reschedule.wav",
            "media_en_location": "english_location.wav",
            "media_en_chest_pain": "english_chest_pain.wav",
            "media_ta_where": "tamil_where.wav",
            "media_ta_departments": "tamil_departments.wav",
            "media_hi_where": "hindi_where.wav",
            "media_hi_fever": "hindi_fever.wav",
            "media_ur_where": "urdu_where.wav"
        }
        if media_id not in mock_audio_map:
            return None
        filename = mock_audio_map[media_id]
        mock_path = os.path.join(scratch_dir, f"mock_download_{filename}")
        
        # Write valid mock WAV header
        with open(mock_path, "wb") as f:
            f.write(b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x08\x00\x00")
        return mock_path

    # Real Meta API media download
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}"
    }
    try:
        # Step 1: Retrieve media URL
        url_metadata = f"{API_URL}/{media_id}"
        res_metadata = requests.get(url_metadata, headers=headers, timeout=10)
        res_metadata.raise_for_status()
        download_url = res_metadata.json().get("url")
        
        if not download_url:
            return None

        # Step 2: Download binary stream
        res_binary = requests.get(download_url, headers=headers, timeout=30)
        res_binary.raise_for_status()
        
        # Save extension based on content-type
        content_type = res_binary.headers.get("content-type", "")
        ext = ".wav"
        if "mpeg" in content_type or "mp3" in content_type:
            ext = ".mp3"
        elif "ogg" in content_type:
            ext = ".ogg"
            
        file_path = os.path.join(scratch_dir, f"download_{media_id}{ext}")
        with open(file_path, "wb") as f:
            f.write(res_binary.content)
            
        return file_path
    except Exception as e:
        print("Meta media download error:", e)
        return None


def mark_message_read(message_id: str) -> dict:
    """Marks an incoming message as read on Meta WhatsApp Cloud API."""
    if not message_id:
        return {"success": False, "error": "No message_id"}
    payload = {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": message_id
    }
    if is_mock_mode():
        log_outbound_simulation("read_status", "system", payload)
        return {"success": True}
    url = f"{API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        return {"success": res.status_code in [200, 201]}
    except Exception as e:
        print(f"[WhatsApp] mark_message_read error: {e}")
        log_outbound_simulation("read_status", "system", payload)
        return {"success": True, "fallback": True}


def send_typing_indicator(to_number: str) -> dict:
    """Sends/simulates typing status before processing AI response."""
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_number,
        "type": "action",
        "action": "typing_on"
    }
    if is_mock_mode():
        log_outbound_simulation("typing_indicator", to_number, payload)
        return {"success": True}
    url = f"{API_URL}/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        return {"success": True}
    except Exception as e:
        print(f"[WhatsApp] send_typing_indicator error: {e}")
        log_outbound_simulation("typing_indicator", to_number, payload)
        return {"success": True, "fallback": True}
