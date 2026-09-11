"""
test_whatsapp_status_blue_tick_suite.py
=========================================
Comprehensive test suite for WhatsApp Blue-Tick / Delivery Status Tracking in Meridian Hospital POC.

8 Required Test Cases:
 1. test_status_sent (SENT -> ✓)
 2. test_status_delivered (DELIVERED -> ✓✓)
 3. test_status_read (READ -> ✓✓ blue)
 4. test_status_failed (FAILED)
 5. test_duplicate_status_event_idempotency
 6. test_outbound_status_progression (SENT -> DELIVERED -> READ)
 7. test_unknown_wamid_status_update
 8. test_multiple_outbound_messages_status_tracking
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
from agent import agent_service

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


def create_outbound_message(conv_code, text, wamid, initial_status="SENT"):
    state = agent_service.state_manager.get_conversation_state(conv_code, whatsapp_number="9198888001")
    agent_service.log_message_to_db(
        conversation_code=conv_code,
        sender_type="AI_AGENT",
        message_text=text,
        language="ENGLISH",
        intent="TEST_OUTBOUND",
        metadata={
            "whatsapp_message_id": wamid,
            "whatsapp_status": initial_status,
            "channel": "WHATSAPP"
        }
    )
    return wamid


def make_status_webhook_payload(wamid: str, status: str, recipient_id: str = "9198888001"):
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
                            "statuses": [
                                {
                                    "id": wamid,
                                    "status": status,
                                    "timestamp": "1700000000",
                                    "recipient_id": recipient_id
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }


def get_message_status(wamid: str):
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT metadata FROM messages WHERE metadata->>'whatsapp_message_id' = %s LIMIT 1;", (wamid,))
        row = cur.fetchone()
        if not row or not row[0]:
            return None
        meta = row[0]
        if isinstance(meta, str):
            meta = json.loads(meta)
        return meta.get("whatsapp_status")
    finally:
        cur.close()
        conn.close()


# Test 1: SENT status handling (✓)
def test_status_sent():
    conv_code = "WA_TEST_STATUS_01"
    cleanup_conversation(conv_code)
    wamid = f"wamid.outbound_st01_{uuid.uuid4().hex[:8]}"
    create_outbound_message(conv_code, "Hello from Meridian Hospital", wamid, initial_status="PENDING")

    payload = make_status_webhook_payload(wamid, "sent")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert get_message_status(wamid) == "SENT"


# Test 2: DELIVERED status handling (✓✓)
def test_status_delivered():
    conv_code = "WA_TEST_STATUS_02"
    cleanup_conversation(conv_code)
    wamid = f"wamid.outbound_st02_{uuid.uuid4().hex[:8]}"
    create_outbound_message(conv_code, "Your appointment is confirmed", wamid, initial_status="SENT")

    payload = make_status_webhook_payload(wamid, "delivered")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert get_message_status(wamid) == "DELIVERED"


# Test 3: READ status handling (✓✓ blue)
def test_status_read():
    conv_code = "WA_TEST_STATUS_03"
    cleanup_conversation(conv_code)
    wamid = f"wamid.outbound_st03_{uuid.uuid4().hex[:8]}"
    create_outbound_message(conv_code, "Please select a date", wamid, initial_status="DELIVERED")

    payload = make_status_webhook_payload(wamid, "read")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert get_message_status(wamid) == "READ"


# Test 4: FAILED status handling
def test_status_failed():
    conv_code = "WA_TEST_STATUS_04"
    cleanup_conversation(conv_code)
    wamid = f"wamid.outbound_st04_{uuid.uuid4().hex[:8]}"
    create_outbound_message(conv_code, "System notification", wamid, initial_status="SENT")

    payload = make_status_webhook_payload(wamid, "failed")
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert get_message_status(wamid) == "FAILED"


# Test 5: Duplicate status event idempotency
def test_duplicate_status_event_idempotency():
    conv_code = "WA_TEST_STATUS_05"
    cleanup_conversation(conv_code)
    wamid = f"wamid.outbound_st05_{uuid.uuid4().hex[:8]}"
    create_outbound_message(conv_code, "Duplicate test message", wamid, initial_status="SENT")

    payload = make_status_webhook_payload(wamid, "delivered")
    
    # First delivery event
    res1 = client.post("/api/whatsapp/webhook", json=payload)
    assert res1.status_code == 200
    assert get_message_status(wamid) == "DELIVERED"

    # Second identical delivery event -> should remain DELIVERED safely
    res2 = client.post("/api/whatsapp/webhook", json=payload)
    assert res2.status_code == 200
    assert get_message_status(wamid) == "DELIVERED"


# Test 6: Full outbound status progression (SENT -> DELIVERED -> READ)
def test_outbound_status_progression():
    conv_code = "WA_TEST_STATUS_06"
    cleanup_conversation(conv_code)
    wamid = f"wamid.outbound_st06_{uuid.uuid4().hex[:8]}"
    create_outbound_message(conv_code, "Progressive status message", wamid, initial_status="PENDING")

    # Step 1: sent
    client.post("/api/whatsapp/webhook", json=make_status_webhook_payload(wamid, "sent"))
    assert get_message_status(wamid) == "SENT"

    # Step 2: delivered
    client.post("/api/whatsapp/webhook", json=make_status_webhook_payload(wamid, "delivered"))
    assert get_message_status(wamid) == "DELIVERED"

    # Step 3: read
    client.post("/api/whatsapp/webhook", json=make_status_webhook_payload(wamid, "read"))
    assert get_message_status(wamid) == "READ"


# Test 7: Status update for unknown/non-existent wamid (Graceful 200 OK handling)
def test_unknown_wamid_status_update():
    wamid = f"wamid.unknown_{uuid.uuid4().hex[:8]}"
    payload = make_status_webhook_payload(wamid, "read")
    
    res = client.post("/api/whatsapp/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert get_message_status(wamid) is None


# Test 8: Multiple outbound messages status tracking independently
def test_multiple_outbound_messages_status_tracking():
    conv_code = "WA_TEST_STATUS_08"
    cleanup_conversation(conv_code)
    
    wamid1 = f"wamid.outbound_st08_1_{uuid.uuid4().hex[:8]}"
    wamid2 = f"wamid.outbound_st08_2_{uuid.uuid4().hex[:8]}"
    
    create_outbound_message(conv_code, "First message", wamid1, initial_status="SENT")
    create_outbound_message(conv_code, "Second message", wamid2, initial_status="SENT")

    # Mark first as read, second as delivered
    client.post("/api/whatsapp/webhook", json=make_status_webhook_payload(wamid1, "read"))
    client.post("/api/whatsapp/webhook", json=make_status_webhook_payload(wamid2, "delivered"))

    assert get_message_status(wamid1) == "READ"
    assert get_message_status(wamid2) == "DELIVERED"
