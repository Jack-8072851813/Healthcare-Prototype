"""
test_whatsapp.py
================
Step 5.3 automated test suite for Meta WhatsApp Cloud API Integration.

Checks 20 scenarios:
  1:  Webhook challenge verification (GET)
  2:  Incoming text greeting (POST)
  3:  Incoming text appointment booking
  4:  Incoming text doctor availability
  5:  Incoming text RAG query
  6:  Incoming text emergency override
  7:  Incoming text cancellation
  8:  Incoming text rescheduling
  9:  Incoming voice greeting (audio media payload)
  10: Incoming voice RAG query
  11: Incoming voice emergency symptom
  12: Incoming voice appointment booking
  13: Multilingual voice message (Tamil text/audio)
  14: Multilingual voice message (Hindi text/audio)
  15: Multilingual voice message (Urdu text/audio)
  16: Language switching via WhatsApp (EN -> TA -> HI)
  17: Invalid verify token handling
  18: Missing parameters/malformed webhook payloads
  19: Notification trigger on transactional confirmation
  20: Media download failure fallback

Run:
    python test_whatsapp.py

Step 5.3 — Meridian Hospital POC
"""

import sys
import os
import uuid
import datetime
import pytz

# Set mock App Secret in environment before loading app routes
os.environ["META_APP_SECRET"] = "test_app_secret"

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import hmac
import hashlib
import db_config
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

passed_tests = []
failed_tests = []


def post_webhook(payload: dict, headers: dict = None):
    import json
    raw_body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(
        b"test_app_secret",
        raw_body,
        hashlib.sha256
    ).hexdigest()
    
    actual_headers = {"X-Hub-Signature-256": f"sha256={signature}"}
    if headers:
        actual_headers.update(headers)
        
    return client.post("/api/whatsapp/webhook", content=raw_body, headers=actual_headers)



def log_result(name, passed, detail=""):
    if passed:
        passed_tests.append(name)
        print(f"[PASS] {name}")
    else:
        failed_tests.append(name)
        print(f"[FAIL] {name}" + (f" - {detail}" if detail else ""))


def make_whatsapp_webhook_payload(from_num: str, msg_type: str, body_or_media_id: str) -> dict:
    """Helper to construct a mock Meta webhook JSON payload."""
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WHATSAPP_ACC_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "123456789",
                                "phone_number_id": "123456789"
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Test Patient"},
                                    "wa_id": from_num
                                }
                            ],
                            "messages": [
                                {
                                    "from": from_num,
                                    "id": f"wamid.mock_{uuid.uuid4().hex[:10]}",
                                    "timestamp": str(int(datetime.datetime.now().timestamp())),
                                    "type": msg_type
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    if msg_type == "text":
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"] = {
            "body": body_or_media_id
        }
    elif msg_type == "audio":
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["audio"] = {
            "id": body_or_media_id,
            "mime_type": "audio/ogg; codecs=opus"
        }
        
    return payload


def run_tests():
    # Setup: Clean dynamic patient data to avoid greeting auto-bypass
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE whatsapp_number = '919999999999' OR phone = '919999999999');")
        cur.execute("DELETE FROM patients WHERE whatsapp_number = '919999999999' OR phone = '919999999999';")
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    # 1. Webhook challenge verification (GET)
    try:
        res = client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.challenge=12345&hub.verify_token=meridian_hospital_token")
        ok = res.status_code == 200 and res.text == "12345"
        log_result("Scenario 1: Webhook challenge verification", ok)
    except Exception as e:
        log_result("Scenario 1: Webhook challenge verification", False, str(e))

    # 2. Incoming text greeting (POST)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"  # Fresh unique phone number
        payload = make_whatsapp_webhook_payload(phone, "text", "Hi")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["status"] == "success" and res.json()["intent"] == "GREETING"
        log_result("Scenario 2: Incoming text greeting", ok)
    except Exception as e:
        log_result("Scenario 2: Incoming text greeting", False, str(e))

    # 3. Incoming text appointment booking
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        # Ensure patient registered first or bypass via mock ID
        # Let's say "I want an appointment"
        payload = make_whatsapp_webhook_payload(phone, "text", "I want to book an appointment")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] == "BOOK_APPOINTMENT"
        log_result("Scenario 3: Incoming text appointment booking", ok)
    except Exception as e:
        log_result("Scenario 3: Incoming text appointment booking", False, str(e))

    # 4. Incoming text doctor availability
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "Is Dr. Arun available tomorrow?")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] == "DOCTOR_AVAILABILITY"
        log_result("Scenario 4: Incoming text doctor availability", ok)
    except Exception as e:
        log_result("Scenario 4: Incoming text doctor availability", False, str(e))

    # 5. Incoming text RAG query
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "What departments do you have?")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] == "HOSPITAL_INFORMATION"
        log_result("Scenario 5: Incoming text RAG query", ok)
    except Exception as e:
        log_result("Scenario 5: Incoming text RAG query", False, str(e))

    # 6. Incoming text emergency override
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "I have severe chest pain")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] in ["EMERGENCY_GUIDANCE", "SYMPTOM_GUIDANCE"]
        log_result("Scenario 6: Incoming text emergency override", ok)
    except Exception as e:
        log_result("Scenario 6: Incoming text emergency override", False, str(e))

    # 7. Incoming text cancellation
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "I want to cancel my appointment")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] == "CANCEL_APPOINTMENT"
        log_result("Scenario 7: Incoming text cancellation", ok)
    except Exception as e:
        log_result("Scenario 7: Incoming text cancellation", False, str(e))

    # 8. Incoming text rescheduling
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "I want to reschedule my appointment")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] == "RESCHEDULE_APPOINTMENT"
        log_result("Scenario 8: Incoming text rescheduling", ok)
    except Exception as e:
        log_result("Scenario 8: Incoming text rescheduling", False, str(e))

    # 9. Incoming voice greeting (audio media payload)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "audio", "media_en_greet")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] == "GREETING" and res.json()["transcript"] == "Hi"
        log_result("Scenario 9: Incoming voice greeting", ok)
    except Exception as e:
        log_result("Scenario 9: Incoming voice greeting", False, str(e))

    # 10. Incoming voice RAG query
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "audio", "media_ta_departments")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] == "HOSPITAL_INFORMATION" and "துறை" in res.json()["transcript"]
        log_result("Scenario 10: Incoming voice RAG query", ok)
    except Exception as e:
        log_result("Scenario 10: Incoming voice RAG query", False, str(e))

    # 11. Incoming voice emergency symptom
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "audio", "media_en_chest_pain")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] in ["EMERGENCY_GUIDANCE", "SYMPTOM_GUIDANCE"]
        log_result("Scenario 11: Incoming voice emergency symptom", ok)
    except Exception as e:
        log_result("Scenario 11: Incoming voice emergency symptom", False, str(e))

    # 12. Incoming voice appointment booking
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "audio", "media_en_appt")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["intent"] == "BOOK_APPOINTMENT"
        log_result("Scenario 12: Incoming voice appointment booking", ok)
    except Exception as e:
        log_result("Scenario 12: Incoming voice appointment booking", False, str(e))

    # 13. Multilingual voice message (Tamil text/audio)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "audio", "media_ta_where")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["language"] == "TAMIL" and res.json()["intent"] == "HOSPITAL_INFORMATION"
        log_result("Scenario 13: Multilingual voice message (Tamil)", ok)
    except Exception as e:
        log_result("Scenario 13: Multilingual voice message (Tamil)", False, str(e))

    # 14. Multilingual voice message (Hindi text/audio)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "audio", "media_hi_where")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["language"] == "HINDI" and res.json()["intent"] == "HOSPITAL_INFORMATION"
        log_result("Scenario 14: Multilingual voice message (Hindi)", ok)
    except Exception as e:
        log_result("Scenario 14: Multilingual voice message (Hindi)", False, str(e))

    # 15. Multilingual voice message (Urdu text/audio)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "audio", "media_ur_where")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["language"] == "URDU" and res.json()["intent"] == "HOSPITAL_INFORMATION"
        log_result("Scenario 15: Multilingual voice message (Urdu)", ok)
    except Exception as e:
        log_result("Scenario 15: Multilingual voice message (Urdu)", False, str(e))

    # 16. Language switching via WhatsApp (EN -> TA -> HI)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        # Turn 1: English loc query
        payload1 = make_whatsapp_webhook_payload(phone, "text", "Where is the hospital?")
        res1 = post_webhook(payload1)
        ok1 = res1.json()["language"] == "ENGLISH"
        
        # Turn 2: Switch to Tamil
        payload2 = make_whatsapp_webhook_payload(phone, "text", "தமிழில் சொல்லுங்கள்")
        res2 = post_webhook(payload2)
        ok2 = res2.json()["language"] == "TAMIL"
        
        # Turn 3: Switch to Hindi
        payload3 = make_whatsapp_webhook_payload(phone, "text", "हिंदी में बताइए")
        res3 = post_webhook(payload3)
        ok3 = res3.json()["language"] == "HINDI"
        
        log_result("Scenario 16: Language switching via WhatsApp", ok1 and ok2 and ok3)
    except Exception as e:
        log_result("Scenario 16: Language switching via WhatsApp", False, str(e))

    # 17. Invalid verify token handling
    try:
        res = client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.challenge=12345&hub.verify_token=wrong_token")
        ok = res.status_code == 403
        log_result("Scenario 17: Invalid verify token handling", ok)
    except Exception as e:
        log_result("Scenario 17: Invalid verify token handling", False, str(e))

    # 18. Malformed payloads & Message deduplication
    try:
        # Check malformed
        res_malformed = post_webhook({"garbage": "data"})
        ok_malformed = res_malformed.status_code == 200 and res_malformed.json()["status"] == "ok" and "Empty entries" in res_malformed.json()["detail"]
        
        # Check deduplication
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "Hi")
        # First send
        res1 = post_webhook(payload)
        ok1 = res1.status_code == 200 and res1.json()["status"] == "success"
        
        # Second send (same payload, same message ID)
        res2 = post_webhook(payload)
        ok2 = res2.status_code == 200 and res2.json()["status"] == "success" and res2.json().get("detail") == "Duplicate message ignored"
        
        log_result("Scenario 18: Malformed payloads & Message deduplication", ok_malformed and ok1 and ok2)
    except Exception as e:
        log_result("Scenario 18: Malformed payloads & Message deduplication", False, str(e))

    # 19. Notification trigger on transactional confirmation
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        # Compute next Monday three weeks ahead (guaranteed scheduled slot for Dr. Arun)
        today = datetime.date.today()
        days_ahead = 7 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        test_date = (today + datetime.timedelta(days=days_ahead + 21)).strftime("%Y-%m-%d")

        # In this mock we will query database notifications for the whatsapp flow
        conn = db_config.get_db_connection()
        cur = conn.cursor()
        try:
            # Clean up any existing appointments for Dr. Arun on test_date to make slots free
            cur.execute("DELETE FROM appointments WHERE doctor_id = (SELECT id FROM doctors WHERE doctor_code = 'DR001') AND appointment_date = %s;", (test_date,))
            conn.commit()

            # Let's count existing notifications
            cur.execute("SELECT COUNT(*) FROM notifications;")
            initial_count = cur.fetchone()[0]
            
            # Perform a test booking using the core agent endpoint directly to trigger confirmations
            conv_id = f"WA_CONV_{uuid.uuid4().hex[:6]}"
            # Greets
            client.post("/api/agent/chat", json={"conversation_id": conv_id, "message": "Hi", "patient_id": "P001"})
            # Request cardiologist booking on test_date
            client.post("/api/agent/chat", json={"conversation_id": conv_id, "message": f"I want an appointment with Dr. Arun on {test_date} at 11:00 AM"})
            # Provide reason
            client.post("/api/agent/chat", json={"conversation_id": conv_id, "message": "Regular cardiology follow-up check"})
            
            # Check notifications table: must have increased by 1!
            cur.execute("SELECT COUNT(*) FROM notifications;")
            final_count = cur.fetchone()[0]
            ok = final_count > initial_count
            log_result("Scenario 19: Notification trigger on transactional confirmation", ok)
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        log_result("Scenario 19: Notification trigger on transactional confirmation", False, str(e))

    # 20. Media download failure fallback
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        # media_id = "nonexistent_garbage_id" should trigger download failure fallback
        payload = make_whatsapp_webhook_payload(phone, "audio", "nonexistent_garbage_id")
        res = post_webhook(payload)
        ok = res.status_code == 200 and res.json()["status"] == "error" and res.json()["detail"] == "Media download failed"
        log_result("Scenario 20: Media download failure fallback", ok)
    except Exception as e:
        log_result("Scenario 20: Media download failure fallback", False, str(e))

    # 21. Missing signature header validation (Security)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "Hi")
        # Direct TestClient call without signature header
        res = client.post("/api/whatsapp/webhook", json=payload)
        ok = res.status_code == 403 and "Missing signature header" in res.text
        log_result("Scenario 21: Missing X-Hub-Signature-256 header", ok)
    except Exception as e:
        log_result("Scenario 21: Missing X-Hub-Signature-256 header", False, str(e))

    # 22. Malformed signature header validation (Security)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "Hi")
        headers = {"X-Hub-Signature-256": "sha256=invalid_hex"}
        res = client.post("/api/whatsapp/webhook", json=payload, headers=headers)
        ok = res.status_code == 403 and "Signature mismatch" in res.text
        log_result("Scenario 22: Malformed X-Hub-Signature-256 header", ok)
    except Exception as e:
        log_result("Scenario 22: Malformed X-Hub-Signature-256 header", False, str(e))

    # 23. Mismatched/Invalid signature validation (Security)
    try:
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "Hi")
        # Correct prefix but wrong HMAC hex digest
        headers = {"X-Hub-Signature-256": "sha256=" + "a" * 64}
        res = client.post("/api/whatsapp/webhook", json=payload, headers=headers)
        ok = res.status_code == 403 and "Signature mismatch" in res.text
        log_result("Scenario 23: Mismatched/Invalid signature header", ok)
    except Exception as e:
        log_result("Scenario 23: Mismatched/Invalid signature header", False, str(e))

    # 24. Valid signature with raw payload (Security)
    try:
        import json
        phone = f"91{uuid.uuid4().hex[:10]}"
        payload = make_whatsapp_webhook_payload(phone, "text", "Hi")
        raw_body = json.dumps(payload).encode("utf-8")
        signature = hmac.new(
            b"test_app_secret",
            raw_body,
            hashlib.sha256
        ).hexdigest()
        headers = {"X-Hub-Signature-256": f"sha256={signature}"}
        res = client.post("/api/whatsapp/webhook", content=raw_body, headers=headers)
        ok = res.status_code == 200 and res.json()["intent"] == "GREETING"
        log_result("Scenario 24: Valid signature with raw payload", ok)
    except Exception as e:
        log_result("Scenario 24: Valid signature with raw payload", False, str(e))

    print("\n=== WHATSAPP SUITE SUMMARY ===")
    print(f"Passed: {len(passed_tests)}/24")
    print(f"Failed: {len(failed_tests)}/24")
    return len(failed_tests) == 0


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
    print("\nAll 24 WhatsApp webhook verifications passed successfully!")
    sys.exit(0)
