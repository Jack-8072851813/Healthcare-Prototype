"""
whatsapp_routes.py
==================
Meta WhatsApp Cloud API Webhook routing for Meridian Hospital.

GET /api/whatsapp/webhook: Webhook verification challenge
POST /api/whatsapp/webhook: Webhook message delivery (text & voice)

Step 5.3 — Real WhatsApp Channel Layer Integration
"""

from fastapi import APIRouter, Query, HTTPException, Request, Response, BackgroundTasks

from pydantic import BaseModel
from typing import Optional, List
import sys
import os
import uuid
import json
import hmac
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor

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
import agent.message_aggregator as message_aggregator
import voice.speech_to_text as speech_to_text
import voice.text_to_speech as text_to_speech
import voice.whatsapp_client as whatsapp_client

# Module-level aggregator singleton — 3 s debounce window
_aggregator = message_aggregator.get_aggregator(window_seconds=1.5)

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


def record_outbound_wamid(session_code: str, outbound_wamid: str):
    """Associates outbound WhatsApp message ID (wamid) and initial SENT status with the latest AI_AGENT message."""
    if not outbound_wamid or not session_code:
        return
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE messages
            SET metadata = jsonb_set(
                COALESCE(metadata, '{}'::jsonb),
                '{whatsapp_message_id}',
                to_jsonb(%s::text)
            ) || jsonb_build_object('whatsapp_status', 'SENT', 'status_updated_at', CURRENT_TIMESTAMP::text)
            WHERE id = (
                SELECT id FROM messages 
                WHERE conversation_id = (SELECT id FROM conversations WHERE conversation_code = %s)
                AND sender_type = 'AI_AGENT'
                ORDER BY id DESC LIMIT 1
            );
        """, (outbound_wamid, session_code))
        conn.commit()
        print(f"[WHATSAPP_MESSAGE_SENT] wamid={outbound_wamid}")
    except Exception as e:
        print("[ERROR] record_outbound_wamid failed:", e)
    finally:
        cur.close()
        conn.close()


import time
from datetime import datetime, timezone, timedelta

def get_or_create_whatsapp_session(whatsapp_number: str) -> str:
    """Finds active conversation code for the whatsapp number or creates a new unique one."""
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, conversation_code, last_message_at FROM conversations 
            WHERE whatsapp_number = %s AND conversation_status = 'ACTIVE'
            ORDER BY id DESC LIMIT 1;
        """, (whatsapp_number,))
        row = cur.fetchone()
        if row:
            conv_id, conv_code, last_msg_at = row[0], row[1], row[2]
            # Check 24-hour inactivity timeout
            if last_msg_at:
                now_utc = datetime.now(timezone.utc)
                if last_msg_at.tzinfo is None:
                    last_msg_at = last_msg_at.replace(tzinfo=timezone.utc)
                if (now_utc - last_msg_at) > timedelta(hours=24):
                    cur.execute("UPDATE conversations SET conversation_status = 'COMPLETED', ended_at = CURRENT_TIMESTAMP WHERE id = %s;", (conv_id,))
                    conn.commit()
                else:
                    return conv_code

        # Generate a unique session ID if none active
        base_code = f"WA_{whatsapp_number}"
        cur.execute("SELECT id FROM conversations WHERE conversation_code = %s;", (base_code,))
        if cur.fetchone() is None:
            return base_code
        else:
            return f"WA_{whatsapp_number}_{int(time.time())}"
    finally:
        cur.close()
        conn.close()


def process_and_send_reply(session_code: str, sender_num: str, message_id: str, body_text: str, button_id: str = None):
    t_total_start = time.monotonic()
    masked_num = f"***{sender_num[-4:]}" if sender_num and len(sender_num) >= 4 else "****"
    try:
        t_agent_start = time.monotonic()
        agent_res = agent_service.process_agent_message(
            conversation_code=session_code,
            patient_code=None,
            message_text=body_text,
            interactive_id=button_id
        )
        t_agent_ms = int((time.monotonic() - t_agent_start) * 1000)

        t_send_start = time.monotonic()
        if agent_res.get("interactive_buttons"):
            send_res = whatsapp_client.send_button_message(sender_num, agent_res["response"], agent_res["interactive_buttons"])
        else:
            send_res = whatsapp_client.send_text_message(sender_num, agent_res["response"])
        t_send_ms = int((time.monotonic() - t_send_start) * 1000)

        t_total_ms = int((time.monotonic() - t_total_start) * 1000)
        print(
            f"[PERF] num={masked_num} intent={agent_res.get('intent','?')} | "
            f"agent={t_agent_ms}ms  wa_send={t_send_ms}ms  total={t_total_ms}ms"
        )

        outbound_wamid = send_res.get("message_id") if isinstance(send_res, dict) else None
        if outbound_wamid:
            record_outbound_wamid(session_code, outbound_wamid)

        record_whatsapp_message_id(session_code, message_id)
        print(f"[DEBUG] Outbound message dispatch complete for {message_id}")
        return agent_res
    except Exception as e:
        t_total_ms = int((time.monotonic() - t_total_start) * 1000)
        print(f"[ERROR] Background WhatsApp message dispatch failed after {t_total_ms}ms: {e}")
        import traceback
        traceback.print_exc()
        return None


def _global_whatsapp_flush_callback(phone_num: str, merged_text: str, metadata: dict = None):
    """
    Module-level callback triggered when the message aggregator timer expires for a phone number.
    Resolves session ID dynamically to ensure thread-safety and correct session state.
    """
    try:
        msg_id = (metadata or {}).get("msg_id") if metadata else None
        session_id = get_or_create_whatsapp_session(phone_num)
        process_and_send_reply(session_id, phone_num, msg_id, merged_text)
    except Exception as exc:
        print(f"[ERROR] Global WhatsApp flush callback error for {phone_num}: {exc}")
        import traceback
        traceback.print_exc()


_aggregator.set_flush_callback(_global_whatsapp_flush_callback)


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
    verify_token = os.getenv("META_WHATSAPP_VERIFY_TOKEN", os.getenv("WHATSAPP_VERIFY_TOKEN", "meridian_hospital_token"))
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return Response(content=hub_challenge, media_type="text/plain")
        
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    print("========== WEBHOOK ROUTE HIT ==========")

    """
    Receive incoming WhatsApp messages (text, voice, delivery logs).
    POST /api/whatsapp/webhook
    """
    print("[DEBUG] Entered receive_webhook endpoint")

    # Security Verification: Validate X-Hub-Signature-256 header using the Meta App Secret
    is_mock = whatsapp_client.is_mock_mode()
    
    meta_app_secret = os.getenv("META_APP_SECRET")
    if not is_mock and not meta_app_secret:
        print("[SECURITY] WhatsApp webhook signature validation failed: META_APP_SECRET is missing in real Meta API configuration")
        raise HTTPException(status_code=403, detail="App secret not configured")

    if meta_app_secret:
        signature_header = request.headers.get("X-Hub-Signature-256")
        if not signature_header:
            print("[SECURITY WARNING] WhatsApp webhook missing X-Hub-Signature-256 header (continuing processing)")
        elif not signature_header.startswith("sha256="):
            print("[SECURITY WARNING] WhatsApp webhook invalid signature format (continuing processing)")
        else:
            try:
                expected_signature = signature_header.split("sha256=")[1]
                raw_body = await request.body()
                calculated_signature = hmac.new(
                    meta_app_secret.encode("utf-8"),
                    raw_body,
                    hashlib.sha256
                ).hexdigest()
                if not hmac.compare_digest(calculated_signature, expected_signature):
                    print(f"[SECURITY WARNING] WhatsApp webhook signature mismatch. Expected: {expected_signature}, Calculated: {calculated_signature}")
                else:
                    print("[SECURITY] WhatsApp webhook signature validation passed")
            except Exception as e:
                print(f"[SECURITY WARNING] Signature verification exception: {e}")

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

    entry = payload.get("entry", [])
    if not entry:
        return {"status": "ok", "detail": "Empty entries payload"}
        
    changes = entry[0].get("changes", [])
    if not changes:
        return {"status": "ok", "detail": "Empty changes payload"}
        
    value = changes[0].get("value", {})
    statuses = value.get("statuses", [])
    messages = value.get("messages", [])

    # Handle WhatsApp Message Status Updates (sent, delivered, read, failed)
    if statuses:
        status_obj = statuses[0]
        wamid = status_obj.get("id")
        raw_status = status_obj.get("status")
        recipient_id = status_obj.get("recipient_id")
        status_upper = str(raw_status).upper() if raw_status else "UNKNOWN"
        
        print(f"[WHATSAPP_STATUS_RECEIVED] wamid={wamid}, status={status_upper}, recipient={recipient_id}")
        
        if wamid and status_upper in ["SENT", "DELIVERED", "READ", "FAILED"]:
            conn = db_config.get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    UPDATE messages
                    SET metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb),
                        '{whatsapp_status}',
                        to_jsonb(%s::text)
                    )
                    WHERE metadata ->> 'whatsapp_message_id' = %s;
                """, (status_upper, wamid))
                conn.commit()
                if status_upper == "SENT":
                    print(f"[WHATSAPP_MESSAGE_SENT] wamid={wamid}")
                elif status_upper == "DELIVERED":
                    print(f"[WHATSAPP_MESSAGE_DELIVERED] wamid={wamid}")
                elif status_upper == "READ":
                    print(f"[WHATSAPP_MESSAGE_READ] wamid={wamid}")
                elif status_upper == "FAILED":
                    print(f"[WHATSAPP_MESSAGE_FAILED] wamid={wamid}")
            except Exception as e:
                print(f"[ERROR] Failed to update message status for {wamid}: {e}")
            finally:
                cur.close()
                conn.close()

        return {"status": "ok", "detail": f"Status update processed ({status_upper})"}

    if not messages:
        return {"status": "ok", "detail": "No messages or statuses in change value"}

    message_data = messages[0]
    from_number = message_data.get("from")
    msg_type = message_data.get("type")
    msg_id = message_data.get("id")

    if not from_number:
        return {"status": "ok", "detail": "Missing sender WaID"}

    print(f"[WHATSAPP_MESSAGE_RECEIVED] wamid={msg_id}, type={msg_type}, from={from_number}")

    try:
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
            interactive_id = None
            if msg_type == "interactive":
                interactive_obj = message_data.get("interactive", {})
                i_type = interactive_obj.get("type")
                if i_type == "button_reply":
                    interactive_id = interactive_obj.get("button_reply", {}).get("id", "")
                    text_body = interactive_obj.get("button_reply", {}).get("title") or interactive_id
                elif i_type == "list_reply":
                    interactive_id = interactive_obj.get("list_reply", {}).get("id", "")
                    text_body = interactive_obj.get("list_reply", {}).get("title") or interactive_id
                else:
                    text_body = ""
            else:
                text_body = message_data.get("text", {}).get("body", "").strip()

            if not text_body:
                return {"status": "ok", "detail": "Empty message body"}

            # Fire-and-forget: don't block agent processing (~200ms saved)
            background_tasks.add_task(whatsapp_client.mark_message_read, msg_id)
            background_tasks.add_task(whatsapp_client.send_typing_indicator, from_number)

            if msg_type == "interactive":
                background_tasks.add_task(process_and_send_reply, session_id, from_number, msg_id, text_body, interactive_id)
                return {
                    "status": "success",
                    "message_id": msg_id,
                    "session_id": session_id
                }

            result = _aggregator.add(from_number, text_body, metadata={"msg_id": msg_id, "session_id": session_id})
            if result is not None:
                agent_res = process_and_send_reply(session_id, from_number, msg_id, result)
                return {
                    "status": "success",
                    "message_id": msg_id,
                    "session_id": session_id,
                    "intent": agent_res.get("intent") if agent_res else None,
                    "language": agent_res.get("language") if agent_res else None,
                    "response": agent_res.get("response") if agent_res else None
                }

            return {
                "status": "success",
                "message_id": msg_id,
                "session_id": session_id
            }

        # 2. Voice/Audio Message flow
        elif msg_type == "audio":
            audio_data = message_data.get("audio", {})
            media_id = audio_data.get("id")
            
            print(f"[VOICE_MESSAGE_RECEIVED] wamid={msg_id}, media_id={media_id}, from={from_number}")
            whatsapp_client.mark_message_read(msg_id)
            whatsapp_client.send_typing_indicator(from_number)

            if not media_id:
                err_msg = "Sorry, I couldn't access your voice message. Please try again."
                action_buttons = [
                    {"id": "btn_try_again_voice", "title": "Try Again"},
                    {"id": "btn_type_message", "title": "Type Message"}
                ]
                whatsapp_client.send_button_message(from_number, err_msg, action_buttons)
                record_whatsapp_message_id(session_id, msg_id)
                return {"status": "error", "detail": "Missing voice media id"}

            # Download audio from Meta
            temp_audio_path = whatsapp_client.download_media(media_id)
            if not temp_audio_path or not os.path.exists(temp_audio_path) or os.path.getsize(temp_audio_path) == 0:
                print(f"[VOICE_MEDIA_DOWNLOAD_FAILED] media_id={media_id}")
                err_msg = "Sorry, I couldn't access your voice message. Please try again."
                action_buttons = [
                    {"id": "btn_try_again_voice", "title": "Try Again"},
                    {"id": "btn_type_message", "title": "Type Message"}
                ]
                send_res = whatsapp_client.send_button_message(from_number, err_msg, action_buttons)
                record_whatsapp_message_id(session_id, msg_id)
                return {"status": "error", "detail": "Media download failed"}

            try:
                print(f"[VOICE_TRANSCRIPTION_STARTED] media_id={media_id}")
                stt_provider = speech_to_text.get_stt_provider()
                stt_res = stt_provider.transcribe(temp_audio_path)
                
                transcript = (stt_res.get("text") or "").strip() if stt_res.get("success") else ""
                detected_lang = stt_res.get("language") or "ENGLISH"

                invalid_transcripts = ["", "voice", "audio", "message", "none", "null"]
                if not stt_res.get("success") or not transcript or transcript.lower() in invalid_transcripts:
                    print(f"[VOICE_TRANSCRIPTION_FAILED] media_id={media_id}, error={stt_res.get('error')}")
                    err_msg = "Sorry, I couldn't understand your voice message. Please try again."
                    action_buttons = [
                        {"id": "btn_try_again_voice", "title": "Try Again"},
                        {"id": "btn_type_message", "title": "Type Message"}
                    ]
                    send_res = whatsapp_client.send_button_message(from_number, err_msg, action_buttons)
                    record_whatsapp_message_id(session_id, msg_id)
                    return {"status": "error", "detail": "STT transcription failed"}

                print(f"[VOICE_TRANSCRIPTION_COMPLETED] transcript='{transcript}', lang={detected_lang}")

                # Log incoming VOICE message in DB
                agent_service.log_message_to_db(
                    conversation_code=session_id,
                    sender_type="PATIENT",
                    message_text=transcript,
                    language=detected_lang,
                    intent="VOICE_MESSAGE",
                    metadata={
                        "whatsapp_message_id": msg_id,
                        "media_id": media_id,
                        "mime_type": audio_data.get("mime_type", "audio/ogg"),
                        "message_type": "VOICE"
                    },
                    message_type="VOICE"
                )

                # Process transcript through Agent Core
                agent_res = agent_service.process_agent_message(
                    conversation_code=session_id,
                    patient_code=None,
                    message_text=transcript,
                    language_override=detected_lang
                )
                print(f"[AI_RESPONSE_GENERATED] intent={agent_res.get('intent')}, lang={agent_res.get('language')}")
                
                response_text = agent_res["response"]
                final_lang = agent_res.get("language", detected_lang)
                interactive_buttons = agent_res.get("interactive_buttons", [])

                # Synthesize voice response
                tts_provider = text_to_speech.get_tts_provider()
                tts_res = tts_provider.synthesize(response_text, language=final_lang)

                if interactive_buttons:
                    send_res = whatsapp_client.send_button_message(from_number, response_text, interactive_buttons)
                else:
                    send_res = whatsapp_client.send_text_message(from_number, response_text)

                outbound_wamid = send_res.get("message_id") if isinstance(send_res, dict) else None
                if outbound_wamid:
                    record_outbound_wamid(session_id, outbound_wamid)

                if tts_res.get("success") and tts_res.get("audio_data"):
                    whatsapp_client.send_audio_message(from_number, tts_res["audio_data"])

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
