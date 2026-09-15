"""
test_meta_portal_test_button.py
=================================
Unit test to verify that when Meta Developer Console fires a test message status webhook,
the backend automatically dispatches the Meridian Hospital welcome message to the recipient.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from main import app

client = TestClient(app)

def test_meta_portal_test_button_webhook_trigger():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "2303959047073307",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15556698871",
                                "phone_number_id": "1332015746651819"
                            },
                            "statuses": [
                                {
                                    "id": "wamid.HBgMOTE4MDcyODUxODEzFQIAERgS_TEST_PORTAL_BUTTON_123",
                                    "status": "sent",
                                    "timestamp": "1726394400",
                                    "recipient_id": "918072851813"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }

    with patch("voice.whatsapp_client.send_welcome_message") as mock_send_welcome:
        response = client.post("/api/whatsapp/webhook", json=payload)
        assert response.status_code == 200
        assert mock_send_welcome.called
        mock_send_welcome.assert_called_with("918072851813")
