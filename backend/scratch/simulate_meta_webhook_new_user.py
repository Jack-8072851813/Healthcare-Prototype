import requests
import json
import random

def simulate():
    url = "http://localhost:8000/api/whatsapp/webhook"
    # Generate a random 10 digit number
    rand_phone = f"91{random.randint(1000000000, 9999999999)}"
    
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
                                    "profile": {"name": "New Tester"},
                                    "wa_id": rand_phone
                                }
                            ],
                            "messages": [
                                {
                                    "from": rand_phone,
                                    "id": f"wamid.mock_{random.randint(100000, 999999)}",
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
    
    print(f"Sending POST request to {url} with sender {rand_phone}...")
    try:
        res = requests.post(url, json=payload, timeout=5)
        print(f"Response Status: {res.status_code}")
        print("Response Body:")
        print(res.text)
    except Exception as e:
        print("Connection failed:", e)

if __name__ == "__main__":
    simulate()
