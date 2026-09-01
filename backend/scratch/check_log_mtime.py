import os
import time

def check():
    path = r"c:\Users\Bsoft137\OneDrive\Documents\AI_Conversational_Patient_Desk\Healthcare-Prototype\backend\scratch\whatsapp_webhook_received.log"
    if os.path.exists(path):
        mtime = os.path.getmtime(path)
        local_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
        print(f"File: {path}")
        print(f"Modified: {local_time}")
        print(f"Size: {os.path.getsize(path)} bytes")
    else:
        print("File does not exist.")

if __name__ == "__main__":
    check()
