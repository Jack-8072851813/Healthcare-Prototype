import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config
import voice.whatsapp_client as whatsapp_client

def test_send():
    # Sender/recipient number for the test
    # In real Meta WhatsApp Cloud API test accounts, you must send to the registered test number.
    # The user's test number from database conversations is 919999999999 or they might have their own.
    # Let's try sending a message to a real-looking test number or a known number.
    to_num = "919999999999" # Default fallback
    
    # We can query the database conversations to see if there is any other number registered
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT whatsapp_number FROM conversations ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        if row and row[0] and "919999999999" not in row[0]:
            to_num = row[0]
    except Exception:
        pass
    finally:
        cur.close()
        conn.close()

    print(f"Testing send_text_message to: {to_num}...")
    res = whatsapp_client.send_text_message(
        to_number=to_num,
        text="Hello! This is a test message from the Meridian Hospital AI Patient Desk verification script."
    )
    print("Result:")
    print(res)

if __name__ == "__main__":
    test_send()
