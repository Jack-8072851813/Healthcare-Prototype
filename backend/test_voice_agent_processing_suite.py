"""
test_voice_agent_processing_suite.py
======================================
Comprehensive test suite for Voice Agent Processing in Meridian Hospital POC.

13 Required Test Cases:
 1. test_voice_greeting
 2. test_voice_appointment
 3. test_voice_symptom_routing
 4. test_voice_cancellation
 5. test_voice_dependent_booking
 6. test_voice_tamil_language
 7. test_voice_empty_unclear_audio
 8. test_voice_invalid_media_id
 9. test_voice_stt_failure
10. test_voice_duplicate_webhook_deduplication
11. test_voice_multiple_sequential_voice_messages
12. test_voice_after_text
13. test_text_after_voice
"""

import sys
import os
import pytest
import uuid
import json

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.testclient import TestClient
from main import app
import db_config
from agent import state_manager
import voice.whatsapp_client as whatsapp_client

client = TestClient(app)


def cleanup_conversation(conv_code):
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE conversation_code = %s);", (conv_code,))
        cur.execute("DELETE FROM conversations WHERE conversation_code = %s;", (conv_code,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def make_audio_webhook_payload(wamid: str, from_number: str, media_id: str, mime_type: str = "audio/ogg"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BIZ_123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550123456",
                                "phone_number_id": "PHONE_ID_123"
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test Voice User"},
                                    "wa_id": from_number
                                }
                            ],
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": wamid,
                                    "timestamp": "1700000000",
                                    "type": "audio",
                                    "audio": {
                                        "id": media_id,
                                        "mime_type": mime_type
                                    }
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }


def make_text_webhook_payload(wamid: str, from_number: str, text: str):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "BIZ_123",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15550123456",
                                "phone_number_id": "PHONE_ID_123"
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test Voice User"},
                                    "wa_id": from_number
                                }
                            ],
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": wamid,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text}
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }


# Test 1: Simple Greeting Voice Message
def test_voice_greeting():
    conv_code = "WA_TEST_VOICE_01"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v01_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900001", "english_greet")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["transcript"] == "Hi"
    assert data["intent"] == "GREETING"


# Test 2: Appointment Voice Message
def test_voice_appointment():
    conv_code = "WA_TEST_VOICE_02"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v02_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900002", "english_appointment")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "appointment" in data["transcript"].lower()


# Test 3: Symptom Routing Voice Message
def test_voice_symptom_routing():
    conv_code = "WA_TEST_VOICE_03"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v03_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900003", "english_fever")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["transcript"] == "I have fever"


# Test 4: Cancellation Voice Message
def test_voice_cancellation():
    conv_code = "WA_TEST_VOICE_04"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v04_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900004", "english_cancel")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "cancel" in data["transcript"].lower()


# Test 5: Dependent Booking Voice Message
def test_voice_dependent_booking():
    conv_code = "WA_TEST_VOICE_05"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v05_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900005", "english_brother")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "brother" in data["transcript"].lower()


# Test 6: Tamil Language Voice Message
def test_voice_tamil_language():
    conv_code = "WA_TEST_VOICE_06"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v06_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900006", "tamil_greet")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["language"] == "TAMIL"


# Test 7: Empty/Unclear Audio (Returns interactive error buttons, no LLM call)
def test_voice_empty_unclear_audio():
    conv_code = "WA_TEST_VOICE_07"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v07_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900007", "empty_audio_sample")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert data["detail"] == "STT transcription failed"


# Test 8: Invalid Media ID (Download failure, returns interactive error buttons)
def test_voice_invalid_media_id():
    conv_code = "WA_TEST_VOICE_08"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v08_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900008", "invalid_media_id_999")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert data["detail"] == "Media download failed"


# Test 9: STT Failure
def test_voice_stt_failure():
    conv_code = "WA_TEST_VOICE_09"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v09_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900009", "stt_failed_audio")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "error"
    assert data["detail"] == "STT transcription failed"


# Test 10: Duplicate Webhook Deduplication (Same wamid sent twice)
def test_voice_duplicate_webhook_deduplication():
    conv_code = "WA_TEST_VOICE_10"
    cleanup_conversation(conv_code)
    wamid = f"wamid.test_v10_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199900010", "english_greet")
    
    # First attempt -> Processed
    res1 = client.post("/api/whatsapp/webhook", json=payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "success"

    # Second attempt with same wamid -> Duplicate skipped
    res2 = client.post("/api/whatsapp/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["detail"] == "Duplicate message ignored"


# Test 11: Multiple Sequential Voice Messages
def test_voice_multiple_sequential_voice_messages():
    conv_code = "WA_TEST_VOICE_11"
    cleanup_conversation(conv_code)
    phone = "9199900011"

    # Voice 1: Greeting
    wamid1 = f"wamid.test_v11_a_{uuid.uuid4().hex[:8]}"
    payload1 = make_audio_webhook_payload(wamid1, phone, "english_greet")
    res1 = client.post("/api/whatsapp/webhook", json=payload1)
    assert res1.status_code == 200

    # Voice 2: Appointment
    wamid2 = f"wamid.test_v11_b_{uuid.uuid4().hex[:8]}"
    payload2 = make_audio_webhook_payload(wamid2, phone, "english_appointment")
    res2 = client.post("/api/whatsapp/webhook", json=payload2)
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"


# Test 12: Voice After Text Context Preservation
def test_voice_after_text():
    conv_code = "WA_TEST_VOICE_12"
    cleanup_conversation(conv_code)
    phone = "9199900012"

    # Step 1: Text message
    wamid_text = f"wamid.test_v12_txt_{uuid.uuid4().hex[:8]}"
    payload_text = make_text_webhook_payload(wamid_text, phone, "Hello")
    res_txt = client.post("/api/whatsapp/webhook", json=payload_text)
    assert res_txt.status_code == 200

    # Step 2: Voice message
    wamid_voice = f"wamid.test_v12_vce_{uuid.uuid4().hex[:8]}"
    payload_voice = make_audio_webhook_payload(wamid_voice, phone, "english_appointment")
    res_vce = client.post("/api/whatsapp/webhook", json=payload_voice)
    assert res_vce.status_code == 200
    assert res_vce.json()["status"] == "success"


# Test 13: Text After Voice Context Preservation
def test_text_after_voice():
    conv_code = "WA_TEST_VOICE_13"
    cleanup_conversation(conv_code)
    phone = "9199900013"

    # Step 1: Voice message asking for appointment
    wamid_voice = f"wamid.test_v13_vce_{uuid.uuid4().hex[:8]}"
    payload_voice = make_audio_webhook_payload(wamid_voice, phone, "english_appointment")
    res_vce = client.post("/api/whatsapp/webhook", json=payload_voice)
    assert res_vce.status_code == 200

    # Step 2: Text message following up
    wamid_text = f"wamid.test_v13_txt_{uuid.uuid4().hex[:8]}"
    payload_text = make_text_webhook_payload(wamid_text, phone, "Pediatrics")
    res_txt = client.post("/api/whatsapp/webhook", json=payload_text)
    assert res_txt.status_code == 200
    assert res_txt.json()["status"] == "success"
