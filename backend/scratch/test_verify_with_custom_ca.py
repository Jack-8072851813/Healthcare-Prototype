import requests
import os

def test_custom_ca():
    scratch_dir = os.path.dirname(os.path.abspath(__file__))
    ca_path = os.path.join(scratch_dir, "extracted_cert_1.pem")
    
    print(f"Testing requests.get with verify='{ca_path}'...")
    try:
        # Fetch root page of graph.facebook.com to verify SSL handshake
        res = requests.get("https://graph.facebook.com/v17.0", verify=ca_path, timeout=5)
        print(f"Success! Status code: {res.status_code}")
        print("Response body:", res.text)
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_custom_ca()
