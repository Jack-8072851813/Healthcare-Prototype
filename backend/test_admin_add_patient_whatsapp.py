"""
test_admin_add_patient_whatsapp.py
===================================
Unit test for Admin Portal '+ Add Patients' API endpoint:
POST /api/dashboard/patients/add-whatsapp
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
from api.auth_helper import encode_token

client = TestClient(app)

def get_admin_headers():
    token = encode_token({"user_id": 1, "username": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


def test_add_patient_whatsapp_validation():
    # Invalid empty phone
    res = client.post(
        "/api/dashboard/patients/add-whatsapp",
        json={"whatsapp_number": ""},
        headers=get_admin_headers()
    )
    assert res.status_code == 400
    assert "Please enter a valid WhatsApp number." in res.json().get("detail", "")


def test_add_patient_whatsapp_success():
    with patch("voice.whatsapp_client.send_welcome_message") as mock_welcome:
        mock_welcome.return_value = {"success": True, "message_id": "wam.test_123"}
        
        res = client.post(
            "/api/dashboard/patients/add-whatsapp",
            json={"whatsapp_number": "+91 80728 51813"},
            headers=get_admin_headers()
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "Welcome message successfully sent" in data["message"]
        assert mock_welcome.called
