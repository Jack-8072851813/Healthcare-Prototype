import sys
import os

# Add backend dir to sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import voice.whatsapp_client as whatsapp_client
import requests

def test_config():
    print("Environment variables loaded:")
    print("  META_GRAPH_API_VERSION:", os.getenv("META_GRAPH_API_VERSION"))
    print("  REQUESTS_CA_BUNDLE:", os.getenv("REQUESTS_CA_BUNDLE"))
    print("  META_WHATSAPP_PHONE_NUMBER_ID:", os.getenv("META_WHATSAPP_PHONE_NUMBER_ID"))
    
    # Check is_mock_mode
    print("  whatsapp_client.is_mock_mode():", whatsapp_client.is_mock_mode())
    
    # Check URL construction
    expected_url = f"https://graph.facebook.com/{whatsapp_client.API_VERSION}/{whatsapp_client.PHONE_NUMBER_ID}/messages"
    actual_url = f"{whatsapp_client.API_URL}/{whatsapp_client.PHONE_NUMBER_ID}/messages"
    print("  Expected constructed message URL:", expected_url)
    print("  Actual constructed message URL in code:", actual_url)
    assert actual_url == expected_url, "URL construction mismatch!"
    print("[PASS] URL Construction matches expectations.")

    # Safe connectivity test
    test_url = f"https://graph.facebook.com/{whatsapp_client.API_VERSION}"
    print(f"Performing safe connectivity test to {test_url}...")
    
    try:
        res = requests.get(test_url, timeout=5)
        print(f"[SUCCESS] Reached graph.facebook.com successfully!")
        print(f"  HTTP Status Code: {res.status_code}")
        # Note: Do not print token, headers might contain connection info but safe
        print(f"  Response starts with: {res.text[:300].strip()}...")
    except Exception as e:
        print(f"[FAIL] Connection test failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_config()
