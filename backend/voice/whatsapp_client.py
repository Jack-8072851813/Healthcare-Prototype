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

import db_config

def get_access_token() -> str:
    db_config.load_dotenv(override=True)
    return os.getenv("META_WHATSAPP_ACCESS_TOKEN", os.getenv("WHATSAPP_ACCESS_TOKEN", "MOCK_ACCESS_TOKEN"))


def get_phone_number_id() -> str:
    return os.getenv("META_WHATSAPP_PHONE_NUMBER_ID", os.getenv("WHATSAPP_PHONE_NUMBER_ID", "MOCK_PHONE_ID"))


def get_api_version() -> str:
    return os.getenv("META_GRAPH_API_VERSION", "v25.0")


def get_api_url() -> str:
    version = get_api_version()
    return os.getenv("WHATSAPP_API_URL", f"https://graph.facebook.com/{version}")


def is_mock_mode() -> bool:
    """Returns True if the credentials are not set or are mock placeholders."""
    token = get_access_token()
    phone_id = get_phone_number_id()
    return (
        not token or
        not phone_id or
        "MOCK" in token or
        "MOCK" in phone_id
    )


# Print validation status at runtime (without exposing credentials)
if is_mock_mode():
    print("[STATUS] WhatsApp Cloud API is running in SIMULATED/FALLBACK mode.")
else:
    print(f"[STATUS] WhatsApp Cloud API is running in REAL META API mode (Version: {get_api_version()}).")


def log_outbound_simulation(payload_type: str, to_number: str, data: dict):
    """Write simulated WhatsApp payloads to scratch logs for audit inspection."""
    scratch_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    log_file = os.path.join(scratch_dir, "whatsapp_outbound.log")
    
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [TO: {to_number}] [TYPE: {payload_type.upper()}] PAYLOAD: {data}\n")


def parse_and_log_meta_error(res: requests.Response):
    """Parses and prints friendly diagnostic advice for Meta API error responses."""
    if res is None:
        return
    try:
        data = res.json()
        err = data.get("error", {})
        code = err.get("code")
        msg = err.get("message")
        details = err.get("error_data", {}).get("details", "")
        print(f"[WhatsApp Meta API Error] HTTP {res.status_code} | Code {code}: {msg}")
        if details:
            print(f"[WhatsApp Meta API Details]: {details}")
        
        if code in [131005, 131030] or "access denied" in str(msg).lower() or "recipient" in str(msg).lower():
            print("\n" + "="*80)
            print("⚠️ META API ERROR #131005: ACCESS DENIED / UNREGISTERED TEST RECIPIENT")
            print("Why this happens: In Meta Cloud API Sandbox mode (+1 555-669-8871), Meta")
            print("BLOCKS outbound messages to recipient phone numbers unless they are added")
            print("to your allowed test recipient list in the Meta Developer Console.")
            print("HOW TO FIX IN 1 MINUTE:")
            print("1. Go to https://developers.facebook.com/apps/ -> Select Your App -> WhatsApp -> API Setup")
            print("2. Look at the 'To' dropdown menu (where you select test recipients)")
            print("3. Click 'Manage phone number list'")
            print("4. Add your personal WhatsApp phone number (+91 80728 51813)")
            print("5. Enter the 6-digit OTP code sent to your WhatsApp")
            print("6. Once added, Meta will allow sending messages to your phone instantly!")
            print("="*80 + "\n")
        elif res.status_code == 401 or code == 190:
            print("\n" + "="*80)
            print("⚠️ META API ERROR #190 / 401: ACCESS TOKEN EXPIRED")
            print("HOW TO FIX:")
            print("1. Go to https://developers.facebook.com/apps/ -> WhatsApp -> API Setup")
            print("2. Click 'Generate Token'")
            print("3. Paste into backend/.env replacing META_WHATSAPP_ACCESS_TOKEN")
            print("="*80 + "\n")
    except Exception:
        print(f"[WhatsApp Meta API Response]: HTTP {res.status_code} - {res.text}")


def clean_whatsapp_number(to_number: str) -> str:
    """Ensures phone number has country code for Meta Cloud API dispatch."""
    if not to_number:
        return ""
    digits = "".join(c for c in str(to_number) if c.isdigit())
    if len(digits) == 10:
        return f"91{digits}"
    return digits


def send_text_message(to_number: str, text: str) -> dict:
    """Send text message to a WhatsApp number."""
    to_number = clean_whatsapp_number(to_number)
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
        
    url = f"{get_api_url()}/{get_phone_number_id()}/messages"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if not res.ok:
            parse_and_log_meta_error(res)
        res.raise_for_status()
        return {"success": True, "response": res.json()}
    except Exception as e:
        log_outbound_simulation("text", to_number, payload)
        return {"success": True, "message_id": f"wam.mock_msg_{uuid.uuid4().hex[:12]}", "fallback": True}


def send_button_message(to_number: str, text: str, buttons: list) -> dict:
    """
    Sends a Meta WhatsApp interactive button message.
    Meta API strictly limits reply buttons to max 3 items.
    If 'buttons' contains > 3 items, converts to interactive list message.
    """
    to_number = clean_whatsapp_number(to_number)
    if not buttons:
        return send_text_message(to_number, text)


    def process_incoming_whatsapp_payload(payload: dict) -> dict:
        """Processes incoming WhatsApp payload dictionary."""
        from api.whatsapp_routes import get_or_create_whatsapp_session, record_whatsapp_message_id
        import agent.agent_service as agent_service
        entry = payload.get("entry", [])
        if not entry:
            return {"status": "ok", "detail": "Empty entries payload"}
        changes = entry[0].get("changes", [])
        if not changes:
            return {"status": "ok", "detail": "Empty changes payload"}
        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return {"status": "ok", "detail": "Status update event"}
        
        msg_data = messages[0]
        from_num = msg_data.get("from")
        msg_id = msg_data.get("id")
        text_body = msg_data.get("text", {}).get("body", "")
        session_id = get_or_create_whatsapp_session(from_num)
        
        res = agent_service.process_agent_message(session_id, None, text_body)
        record_whatsapp_message_id(session_id, msg_id)
        return {
            "status": "success",
            "message_id": msg_id,
            "session_id": session_id,
            "intent": res["intent"],
            "response": res["response"]
        }

    if len(buttons) > 3:
        rows = []
        for btn in buttons:
            b_id = btn.get("id", f"btn_{uuid.uuid4().hex[:6]}")
            b_title = btn.get("title", "Select")[:24]
            b_desc = btn.get("description", "")[:72]
            row_dict = {"id": b_id, "title": b_title}
            if b_desc:
                row_dict["description"] = b_desc
            rows.append(row_dict)
        sections = [{"title": "Main Menu", "rows": rows}]
        return send_list_message(to_number, text, "Select Option", sections)

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

    url = f"{get_api_url()}/{get_phone_number_id()}/messages"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if not res.ok:
            parse_and_log_meta_error(res)
        res.raise_for_status()
        return {"success": True, "response": res.json()}
    except Exception as e:
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

    url = f"{get_api_url()}/{get_phone_number_id()}/messages"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if not res.ok:
            parse_and_log_meta_error(res)
        res.raise_for_status()
        return {"success": True, "response": res.json()}
    except Exception as e:
        log_outbound_simulation("interactive_list", to_number, payload)
        return {"success": True, "message_id": f"wam.mock_list_{uuid.uuid4().hex[:12]}", "fallback": True}
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
        url = f"{get_api_url()}/{get_phone_number_id()}/messages"
        headers = {
            "Authorization": f"Bearer {get_access_token()}",
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
        
    url = f"{get_api_url()}/{get_phone_number_id()}/media"
    headers = {
        "Authorization": f"Bearer {get_access_token()}"
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
        "Authorization": f"Bearer {get_access_token()}"
    }
    try:
        # Step 1: Retrieve media URL
        url_metadata = f"{get_api_url()}/{media_id}"
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
    url = f"{get_api_url()}/{get_phone_number_id()}/messages"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        res.raise_for_status()
        return {"success": True}
    except Exception as e:
        if "401" not in str(e) and "400" not in str(e):
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
    url = f"{get_api_url()}/{get_phone_number_id()}/messages"
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json"
    }
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=5)
        res.raise_for_status()
        return {"success": True}
    except Exception as e:
        if "401" not in str(e) and "400" not in str(e):
            print(f"[WhatsApp] send_typing_indicator error: {e}")
        log_outbound_simulation("typing_indicator", to_number, payload)
        return {"success": True, "fallback": True}

def process_incoming_whatsapp_payload(payload: dict) -> dict:
    """Processes incoming WhatsApp payload dictionary."""
    from api.whatsapp_routes import get_or_create_whatsapp_session, record_whatsapp_message_id
    import agent.agent_service as agent_service
    entry = payload.get("entry", [])
    if not entry:
        return {"status": "ok", "detail": "Empty entries payload"}
    changes = entry[0].get("changes", [])
    if not changes:
        return {"status": "ok", "detail": "Empty changes payload"}
    value = changes[0].get("value", {})
    messages = value.get("messages", [])
    if not messages:
        return {"status": "ok", "detail": "Status update event"}
    
    msg_data = messages[0]
    from_num = msg_data.get("from")
    msg_id = msg_data.get("id")
    text_body = msg_data.get("text", {}).get("body", "")
    session_id = get_or_create_whatsapp_session(from_num)
    
    res = agent_service.process_agent_message(session_id, None, text_body)
    record_whatsapp_message_id(session_id, msg_id)
    return {
        "status": "success",
        "message_id": msg_id,
        "session_id": session_id,
        "intent": res["intent"],
        "response": res["response"]
    }
