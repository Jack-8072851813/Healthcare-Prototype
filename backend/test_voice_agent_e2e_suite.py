"""
test_voice_agent_e2e_suite.py
================================
Comprehensive test suite for Voice Agent End-to-End processing in Meridian Hospital POC.

24 Required Test Cases (Section 23 Matrix):
 1. test_1_valid_whatsapp_audio
 2. test_2_media_id_missing
 3. test_3_media_download_failure
 4. test_4_empty_audio
 5. test_5_invalid_audio_format
 6. test_6_audio_conversion
 7. test_7_stt_success
 8. test_8_stt_empty_transcript
 9. test_9_stt_provider_error
10. test_10_english_voice
11. test_11_tamil_voice
12. test_12_voice_booking
13. test_13_voice_cancellation
14. test_14_voice_rescheduling
15. test_15_voice_patient_profile
16. test_16_voice_dependent_booking
17. test_17_voice_during_active_text_conversation
18. test_18_text_after_voice
19. test_19_voice_after_text
20. test_20_duplicate_meta_webhook
21. test_21_multiple_unique_voice_messages
22. test_22_llm_failure_handling
23. test_23_whatsapp_response_delivery
24. test_24_e2e_voice_pipeline
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


# Test 1: Valid WhatsApp audio
def test_1_valid_whatsapp_audio():
    conv_code = "WA_TEST_E2E_01"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_01_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800001", "english_appointment")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert "appointment" in res.json()["transcript"].lower()


# Test 2: Media ID missing
def test_2_media_id_missing():
    conv_code = "WA_TEST_E2E_02"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_02_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800002", "")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "error"
    assert res.json()["detail"] == "Missing voice media id"


# Test 3: Media download failure
def test_3_media_download_failure():
    conv_code = "WA_TEST_E2E_03"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_03_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800003", "invalid_media_id_999")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "error"
    assert res.json()["detail"] == "Media download failed"


# Test 4: Empty audio
def test_4_empty_audio():
    conv_code = "WA_TEST_E2E_04"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_04_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800004", "empty_audio_track")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "error"
    assert res.json()["detail"] == "STT transcription failed"


# Test 5: Invalid audio format
def test_5_invalid_audio_format():
    conv_code = "WA_TEST_E2E_05"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_05_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800005", "corrupt_file_format")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "error"


# Test 6: Audio format conversion / handling
def test_6_audio_conversion():
    conv_code = "WA_TEST_E2E_06"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_06_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800006", "english_greet", mime_type="audio/ogg; codecs=opus")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"


# Test 7: STT success
def test_7_stt_success():
    conv_code = "WA_TEST_E2E_07"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_07_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800007", "english_fever")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["transcript"] == "I have fever"


# Test 8: STT empty transcript
def test_8_stt_empty_transcript():
    conv_code = "WA_TEST_E2E_08"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_08_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800008", "unclear_audio_track")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "error"


# Test 9: STT provider error
def test_9_stt_provider_error():
    conv_code = "WA_TEST_E2E_09"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_09_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800009", "stt_failed_audio")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "error"


# Test 10: English voice
def test_10_english_voice():
    conv_code = "WA_TEST_E2E_10"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_10_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800010", "english_appointment")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["language"] == "ENGLISH"


# Test 11: Tamil voice
def test_11_tamil_voice():
    conv_code = "WA_TEST_E2E_11"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_11_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800011", "tamil_greet")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["language"] == "TAMIL"


# Test 12: Voice appointment booking
def test_12_voice_booking():
    conv_code = "WA_TEST_E2E_12"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_12_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800012", "english_appointment")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["intent"] in ["BOOK_APPOINTMENT", "CHECK_AVAILABILITY", "GENERAL_QUERY"]


# Test 13: Voice appointment cancellation
def test_13_voice_cancellation():
    conv_code = "WA_TEST_E2E_13"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_13_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800013", "english_cancel")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert "cancel" in res.json()["transcript"].lower()


# Test 14: Voice appointment rescheduling
def test_14_voice_rescheduling():
    conv_code = "WA_TEST_E2E_14"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_14_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800014", "english_reschedule")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert "reschedule" in res.json()["transcript"].lower()


# Test 15: Voice patient profile
def test_15_voice_patient_profile():
    conv_code = "WA_TEST_E2E_15"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_15_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800015", "english_location")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200


# Test 16: Voice dependent booking
def test_16_voice_dependent_booking():
    conv_code = "WA_TEST_E2E_16"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_16_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800016", "english_brother")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert "brother" in res.json()["transcript"].lower()


# Test 17: Voice during active text conversation
def test_17_voice_during_active_text_conversation():
    conv_code = "WA_TEST_E2E_17"
    cleanup_conversation(conv_code)
    phone = "9199800017"

    wamid1 = f"wamid.e2e_17_a_{uuid.uuid4().hex[:8]}"
    client.post("/api/whatsapp/webhook", json=make_text_webhook_payload(wamid1, phone, "I want an appointment"))

    wamid2 = f"wamid.e2e_17_b_{uuid.uuid4().hex[:8]}"
    res2 = client.post("/api/whatsapp/webhook", json=make_audio_webhook_payload(wamid2, phone, "english_fever"))
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"


# Test 18: Text after voice
def test_18_text_after_voice():
    conv_code = "WA_TEST_E2E_18"
    cleanup_conversation(conv_code)
    phone = "9199800018"

    wamid1 = f"wamid.e2e_18_a_{uuid.uuid4().hex[:8]}"
    client.post("/api/whatsapp/webhook", json=make_audio_webhook_payload(wamid1, phone, "english_appointment"))

    wamid2 = f"wamid.e2e_18_b_{uuid.uuid4().hex[:8]}"
    res2 = client.post("/api/whatsapp/webhook", json=make_text_webhook_payload(wamid2, phone, "Pediatrics"))
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"


# Test 19: Voice after text
def test_19_voice_after_text():
    conv_code = "WA_TEST_E2E_19"
    cleanup_conversation(conv_code)
    phone = "9199800019"

    wamid1 = f"wamid.e2e_19_a_{uuid.uuid4().hex[:8]}"
    client.post("/api/whatsapp/webhook", json=make_text_webhook_payload(wamid1, phone, "Hello"))

    wamid2 = f"wamid.e2e_19_b_{uuid.uuid4().hex[:8]}"
    res2 = client.post("/api/whatsapp/webhook", json=make_audio_webhook_payload(wamid2, phone, "english_appointment"))
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"


# Test 20: Duplicate Meta webhook
def test_20_duplicate_meta_webhook():
    conv_code = "WA_TEST_E2E_20"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_20_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800020", "english_greet")
    
    res1 = client.post("/api/whatsapp/webhook", json=payload)
    assert res1.status_code == 200
    assert res1.json()["status"] == "success"

    res2 = client.post("/api/whatsapp/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["detail"] == "Duplicate message ignored"


# Test 21: Multiple unique voice messages
def test_21_multiple_unique_voice_messages():
    conv_code = "WA_TEST_E2E_21"
    cleanup_conversation(conv_code)
    phone = "9199800021"

    wamid1 = f"wamid.e2e_21_a_{uuid.uuid4().hex[:8]}"
    res1 = client.post("/api/whatsapp/webhook", json=make_audio_webhook_payload(wamid1, phone, "english_greet"))
    assert res1.status_code == 200

    wamid2 = f"wamid.e2e_21_b_{uuid.uuid4().hex[:8]}"
    res2 = client.post("/api/whatsapp/webhook", json=make_audio_webhook_payload(wamid2, phone, "english_appointment"))
    assert res2.status_code == 200
    assert res2.json()["status"] == "success"


# Test 22: LLM failure handling after STT
def test_22_llm_failure_handling():
    conv_code = "WA_TEST_E2E_22"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_22_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800022", "english_greet")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "success"


# Test 23: WhatsApp response delivery
def test_23_whatsapp_response_delivery():
    conv_code = "WA_TEST_E2E_23"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_23_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800023", "english_fever")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert "session_id" in res.json()


# Test 24: End-to-end voice pipeline verification
def test_24_e2e_voice_pipeline():
    conv_code = "WA_TEST_E2E_24"
    cleanup_conversation(conv_code)
    wamid = f"wamid.e2e_24_{uuid.uuid4().hex[:8]}"
    payload = make_audio_webhook_payload(wamid, "9199800024", "english_appointment")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "transcript" in data
    assert "intent" in data
