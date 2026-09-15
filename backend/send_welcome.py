"""
send_welcome.py
================
Run this script to send the Meridian Hospital plain-text welcome message 
directly to your WhatsApp phone number via Meta Cloud API.

Usage:
    python send_welcome.py [phone_number]
Example:
    python send_welcome.py 918072851813
"""

import sys
import os

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from voice import whatsapp_client

def main():
    phone_num = sys.argv[1] if len(sys.argv) > 1 else "918072851813"
    print(f"Sending Meridian Hospital welcome message to: {phone_num}...")
    res = whatsapp_client.send_welcome_message(phone_num)
    print("Result:", res)

if __name__ == "__main__":
    main()
