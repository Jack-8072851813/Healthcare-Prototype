"""
test_whatsapp_welcome_message.py
==================================
Unit test to verify that the Meridian Hospital welcome message uses the active
Meta WhatsApp template 'meridian_patient_welcome' with language code 'en'.
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from voice import whatsapp_client


def test_send_welcome_message_template_payload():
    test_number = "918072851813"
    
    with patch("voice.whatsapp_client.is_mock_mode", return_value=False), \
         patch("requests.post") as mock_post:
        
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = {"messages": [{"id": "wam.test_template_123"}]}
        mock_post.return_value = mock_response
        
        res = whatsapp_client.send_welcome_message(test_number)
        
        assert res["success"] is True
        assert mock_post.called
        
        # Extract sent payload
        call_kwargs = mock_post.call_args[1]
        sent_payload = call_kwargs.get("json", {})
        
        # Assert payload matches template specifications
        assert sent_payload.get("messaging_product") == "whatsapp"
        assert sent_payload.get("to") == "918072851813"
        assert sent_payload.get("type") == "template"
        
        template_obj = sent_payload.get("template", {})
        assert template_obj.get("name") == "meridian_patient_welcome"
        assert template_obj.get("language", {}).get("code") == "en"


def test_send_welcome_message_mock_mode():
    test_number = "+91 80728 51813"
    res = whatsapp_client.send_welcome_message(test_number)
    assert res["success"] is True
    assert "message_id" in res
