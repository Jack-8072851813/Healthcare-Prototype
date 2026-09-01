import sys
import os

def test_connection():
    import requests
    print("Testing connection to graph.facebook.com WITHOUT truststore...")
    try:
        res = requests.get("https://graph.facebook.com/v17.0", timeout=5)
        print(f"Success! Status code: {res.status_code}, body: {res.text}")
    except Exception as e:
        print(f"Failed WITHOUT truststore: {type(e).__name__}: {e}")

    print("\nInjecting truststore into ssl...")
    try:
        import truststore
        truststore.inject_into_ssl()
        print("truststore injected successfully!")
    except Exception as e:
        print(f"Failed to inject truststore: {e}")
        return

    print("Testing connection to graph.facebook.com WITH truststore...")
    try:
        res = requests.get("https://graph.facebook.com/v17.0", timeout=5)
        print(f"Success! Status code: {res.status_code}, body: {res.text}")
    except Exception as e:
        print(f"Failed WITH truststore: {type(e).__name__}: {e}")

if __name__ == "__main__":
    test_connection()
