import requests
import json

def simulate():
    url = "http://localhost:8000/api/whatsapp/webhook"
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
                                    "profile": {"name": "Audit Tester"},
                                    "wa_id": "919999999999"
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919999999999",
                                    "id": "wamid.ABGGFlA5FVEVAgIQg4Y10001",
                                    "timestamp": "1672531199",
                                    "type": "text",
                                    "text": {
                                        "body": "What departments are available?"
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
    
    print(f"Sending POST request to {url}...")
    try:
        res = requests.post(url, json=payload, timeout=5)
        print(f"Response Status: {res.status_code}")
        print("Response Body:")
        print(res.text)
    except Exception as e:
        print("Connection failed:", e)

if __name__ == "__main__":
    simulate()
