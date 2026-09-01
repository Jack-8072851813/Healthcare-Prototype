"""
whatsapp_routes.py
==================
Meta WhatsApp Cloud API Webhook routing for Meridian Hospital.

GET /api/whatsapp/webhook: Webhook verification challenge
POST /api/whatsapp/webhook: Webhook message delivery (text & voice)

Step 5.3 — Real WhatsApp Channel Layer Integration
"""

from fastapi import APIRouter, Query, HTTPException, Request, Response
from pydantic import BaseModel
from typing import Optional, List
import sys
import os
import uuid
import json
import hmac
import hashlib

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import agent.agent_service as agent_service
import voice.speech_to_text as speech_to_text
import voice.text_to_speech as text_to_speech
import voice.whatsapp_client as whatsapp_client

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp Webhook"])

VERIFY_TOKEN = os.getenv("META_WHATSAPP_VERIFY_TOKEN", os.getenv("WHATSAPP_VERIFY_TOKEN", "meridian_hospital_token"))
META_APP_SECRET = os.getenv("META_APP_SECRET")


def is_duplicate_message(msg_id: str) -> bool:
    """Returns True if this msg_id was already processed (exists in messages metadata)."""
    if not msg_id:
        return False
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id FROM messages 
            WHERE metadata ->> 'whatsapp_message_id' = %s;
        """, (msg_id,))
        return cur.fetchone() is not None
    except Exception as e:
        print("Error checking message duplicate:", e)
        return False
    finally:
        cur.close()
        conn.close()


def record_whatsapp_message_id(session_id: str, msg_id: str):
    """Records the processed message ID in the database messages table."""
    if not msg_id:
        return
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM conversations WHERE conversation_code = %s;", (session_id,))
        row = cur.fetchone()
        if row:
            conv_id = row[0]
            cur.execute("""
                INSERT INTO messages (conversation_id, sender_type, message_type, message_text, metadata)
                VALUES (%s, 'PATIENT', 'SYSTEM', 'WhatsApp message receipt tracker', %s);
            """, (conv_id, json.dumps({"whatsapp_message_id": msg_id})))
            conn.commit()
    except Exception as e:
        print("Failed to record WhatsApp message ID:", e)
    finally:
        cur.close()
        conn.close()


def get_or_create_whatsapp_session(whatsapp_number: str) -> str:
    """Finds active conversation code for the whatsapp number or creates a new one."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT conversation_code FROM conversations 
            WHERE whatsapp_number = %s AND conversation_status = 'ACTIVE'
            ORDER BY id DESC LIMIT 1;
        """, (whatsapp_number,))
        row = cur.fetchone()
        if row:
            return row[0]
            
        # Create a new session ID if none active
        new_session_id = f"WA_{whatsapp_number}"
        return new_session_id
    finally:
        cur.close()
        conn.close()


@router.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Handle Meta webhook verification challenge.
    GET /api/whatsapp/webhook?hub.mode=subscribe&hub.challenge=1158201444&hub.verify_token=meridian_hospital_token
    """
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
        
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/webhook")
async def receive_webhook(request: Request):
    print("========== WEBHOOK ROUTE HIT ==========")
    """
    Receive incoming WhatsApp messages (text, voice, delivery logs).
    POST /api/whatsapp/webhook
    """
    print("[DEBUG] Entered receive_webhook endpoint")

    # Security Verification: Validate X-Hub-Signature-256 header using the Meta App Secret
    is_mock = whatsapp_client.is_mock_mode()
    
    # In real Meta mode, App Secret is required
    if not is_mock and not META_APP_SECRET:
        print("[SECURITY] WhatsApp webhook signature validation failed: META_APP_SECRET is missing in real Meta API configuration")
        raise HTTPException(status_code=403, detail="App secret not configured")

    # Only validate signature if META_APP_SECRET is configured
    if META_APP_SECRET:
        signature_header = request.headers.get("X-Hub-Signature-256")
        if not signature_header:
            print("[SECURITY] WhatsApp webhook signature validation failed: Missing X-Hub-Signature-256 header")
            raise HTTPException(status_code=403, detail="Missing signature header")

        if not signature_header.startswith("sha256="):
            print("[SECURITY] WhatsApp webhook signature validation failed: Invalid header format")
            raise HTTPException(status_code=403, detail="Invalid signature format")

        try:
            expected_signature = signature_header.split("sha256=")[1]
        except IndexError:
            print("[SECURITY] WhatsApp webhook signature validation failed: Malformed signature header")
            raise HTTPException(status_code=403, detail="Malformed signature header")

        raw_body = await request.body()
        calculated_signature = hmac.new(
            META_APP_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_signature, expected_signature):
            print("[SECURITY] WhatsApp webhook signature validation failed: Signature mismatch")
            raise HTTPException(status_code=403, detail="Signature mismatch")

        print("[SECURITY] WhatsApp webhook signature validation passed")

    try:
        payload = await request.json()
        print(f"[DEBUG] Incoming payload received: {json.dumps(payload)}")
    except Exception as e:
        print(f"[DEBUG] Failed to parse JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Log payload for auditing
    scratch_dir = os.path.join(backend_dir, "scratch")
    os.makedirs(scratch_dir, exist_ok=True)
    with open(os.path.join(scratch_dir, "whatsapp_webhook_received.log"), "a", encoding="utf-8") as log_f:
        log_f.write(json.dumps(payload) + "\n")

    # Check if this is a standard message event
    entry = payload.get("entry", [])
    if not entry:
        return {"status": "ok", "detail": "Empty entries payload"}
        
    changes = entry[0].get("changes", [])
    if not changes:
        return {"status": "ok", "detail": "Empty changes payload"}
        
    value = changes[0].get("value", {})
    messages = value.get("messages", [])
    if not messages:
        # Could be status update webhook (sent, delivered, read) -> ignore or log
        return {"status": "ok", "detail": "Message status update event"}

    message_data = messages[0]
    from_number = message_data.get("from")
    msg_type = message_data.get("type")
    msg_id = message_data.get("id")

    if not from_number:
        return {"status": "ok", "detail": "Missing sender WaID"}

    print(f"[DEBUG] WhatsApp message successfully extracted. ID: {msg_id}, Type: {msg_type}")
    print(f"[DEBUG] Extracted from_number: {from_number}")

    try:
        # Resolve session ID mapping to load context
        session_id = get_or_create_whatsapp_session(from_number)

        # Message deduplication check (Meta webhook retry guard)
        if msg_id and is_duplicate_message(msg_id):
            print(f"[STATUS] Duplicate message ID detected: {msg_id}. Skipping processing.")
            return {
                "status": "success",
                "message_id": msg_id,
                "session_id": session_id,
                "detail": "Duplicate message ignored"
            }

        # 1. Text or Interactive Message flow
        if msg_type in ["text", "interactive"]:
            if msg_type == "interactive":
                interactive_obj = message_data.get("interactive", {})
                i_type = interactive_obj.get("type")
                if i_type == "button_reply":
                    text_body = interactive_obj.get("button_reply", {}).get("title") or interactive_obj.get("button_reply", {}).get("id", "")
                elif i_type == "list_reply":
                    text_body = interactive_obj.get("list_reply", {}).get("title") or interactive_obj.get("list_reply", {}).get("id", "")
                else:
                    text_body = ""
            else:
                text_body = message_data.get("text", {}).get("body", "").strip()

            if not text_body:
                return {"status": "ok", "detail": "Empty message body"}

            # Mark message read & start typing indicator state
            whatsapp_client.mark_message_read(msg_id)
            whatsapp_client.send_typing_indicator(from_number)

            print(f"[DEBUG] Before calling AI/RAG agent. Input message: '{text_body}'")
            # Run through Agent Core
            agent_res = agent_service.process_agent_message(
                conversation_code=session_id,
                patient_code=None,
                message_text=text_body
            )
            print(f"[DEBUG] After agent response is generated. Intent: {agent_res.get('intent')}, Language: {agent_res.get('language')}")
            print(f"[DEBUG] Generated response: '{agent_res.get('response')}'")
            
            # Send reply (Interactive buttons if present, else standard text)
            if agent_res.get("interactive_buttons"):
                print(f"[DEBUG] Before calling send_button_message() to {from_number}")
                send_res = whatsapp_client.send_button_message(from_number, agent_res["response"], agent_res["interactive_buttons"])
            else:
                print(f"[DEBUG] Before calling send_text_message() to {from_number}")
                send_res = whatsapp_client.send_text_message(from_number, agent_res["response"])

            print(f"[DEBUG] Complete message dispatch result: {send_res}")
            if not send_res.get("success"):
                print(f"[ERROR] WhatsApp outbound message failed: {send_res.get('error')}")

            # Record message ID to prevent duplicate retries
            record_whatsapp_message_id(session_id, msg_id)
            return {
                "status": "success",
                "message_id": msg_id,
                "session_id": session_id,
                "intent": agent_res["intent"],
                "language": agent_res["language"]
            }

        # 2. Voice/Audio Message flow
        elif msg_type == "audio":
            audio_data = message_data.get("audio", {})
            media_id = audio_data.get("id")
            
            if not media_id:
                return {"status": "ok", "detail": "Missing voice media id"}

            # Download audio from Meta
            print(f"[DEBUG] Downloading voice media ID: {media_id}")
            temp_audio_path = whatsapp_client.download_media(media_id)
            if not temp_audio_path or not os.path.exists(temp_audio_path):
                print(f"[DEBUG] Before calling send_text_message() for download fallback to {from_number}")
                send_res = whatsapp_client.send_text_message(from_number, "I couldn't retrieve your voice message. Please try again.")
                print(f"[DEBUG] Complete send_text_message() result: {send_res}")
                if not send_res.get("success"):
                    print(f"[ERROR] WhatsApp outbound fallback message failed: {send_res.get('error')}")
                return {"status": "error", "detail": "Media download failed"}

            try:
                # Transcribe audio file using our STT service
                stt_provider = speech_to_text.get_stt_provider()
                stt_res = stt_provider.transcribe(temp_audio_path)
                
                if not stt_res["success"] or stt_res["error"]:
                    print(f"[DEBUG] Before calling send_text_message() for STT fallback to {from_number}")
                    send_res = whatsapp_client.send_text_message(from_number, "I couldn't understand the voice message clearly. Please try again.")
                    print(f"[DEBUG] Complete send_text_message() result: {send_res}")
                    if not send_res.get("success"):
                        print(f"[ERROR] WhatsApp outbound STT fallback message failed: {send_res.get('error')}")
                    return {"status": "error", "detail": "STT transcription error"}
                    
                transcript = stt_res["text"]
                detected_lang = stt_res["language"]

                print(f"[DEBUG] Before calling AI/RAG agent (Voice Transcript). Input message: '{transcript}'")
                # Process transcript through Agent Core
                agent_res = agent_service.process_agent_message(
                    conversation_code=session_id,
                    patient_code=None,
                    message_text=transcript,
                    language_override=detected_lang
                )
                print(f"[DEBUG] After agent response is generated. Intent: {agent_res.get('intent')}, Language: {agent_res.get('language')}")
                print(f"[DEBUG] Generated response: '{agent_res.get('response')}'")
                
                response_text = agent_res["response"]
                final_lang = agent_res["language"]

                # Synthesize voice response
                tts_provider = text_to_speech.get_tts_provider()
                tts_res = tts_provider.synthesize(response_text, language=final_lang)

                print(f"[DEBUG] Before calling send_text_message() (Voice Flow text reply) to {from_number}")
                # Send text reply
                send_res = whatsapp_client.send_text_message(from_number, response_text)
                print(f"[DEBUG] Complete send_text_message() result: {send_res}")
                if not send_res.get("success"):
                    print(f"[ERROR] WhatsApp outbound text reply failed: {send_res.get('error')}")

                # Send audio reply if synthesized successfully
                if tts_res["success"] and tts_res["audio_data"]:
                    print(f"[DEBUG] Before calling send_audio_message() (Voice Flow audio reply) to {from_number}")
                    send_audio_res = whatsapp_client.send_audio_message(from_number, tts_res["audio_data"])
                    print(f"[DEBUG] Complete send_audio_message() result: {send_audio_res}")
                    if not send_audio_res.get("success"):
                        print(f"[ERROR] WhatsApp outbound audio reply failed: {send_audio_res.get('error')}")

                # Record message ID to prevent duplicate retries
                record_whatsapp_message_id(session_id, msg_id)
                return {
                    "status": "success",
                    "message_id": msg_id,
                    "session_id": session_id,
                    "transcript": transcript,
                    "intent": agent_res["intent"],
                    "language": agent_res["language"]
                }
                
            finally:
                # Cleanup temp downloaded file
                if os.path.exists(temp_audio_path):
                    try:
                        os.remove(temp_audio_path)
                    except Exception:
                        pass

        return {"status": "ok", "detail": f"Unsupported message type: {msg_type}"}

    except Exception as e:
        print("[ERROR] Exception occurred while processing incoming webhook message:")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal processing error: {str(e)}")
