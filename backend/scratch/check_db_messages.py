import psycopg2
import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

import db_config

def check_messages():
    conn = db_config.get_db_connection()
    cur = conn.cursor()
    try:
        print("Checking recent conversations:")
        cur.execute("""
            SELECT id, conversation_code, whatsapp_number, language, current_intent, conversation_status, updated_at 
            FROM conversations 
            ORDER BY id DESC LIMIT 5;
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"Conv ID: {r[0]} | Code: {r[1]} | Phone: {r[2]} | Intent: {r[4]} | Updated: {r[6]}")
            
        print("\nChecking recent messages:")
        cur.execute("""
            SELECT m.id, m.conversation_id, c.conversation_code, m.sender_type, m.message_type, m.message_text, m.intent, m.created_at 
            FROM messages m
            JOIN conversations c ON m.conversation_id = c.id
            ORDER BY m.id DESC LIMIT 10;
        """)
        rows = cur.fetchall()
        for r in rows:
            print(f"Msg ID: {r[0]} | Conv: {r[2]} | Sender: {r[3]} | Type: {r[4]} | Text: {r[5]} | Intent: {r[6]} | Created: {r[7]}")
            
    except Exception as e:
        print("Error:", e)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    check_messages()
