import os

def print_last_lines():
    log_path = r"c:\Users\Bsoft137\OneDrive\Documents\AI_Conversational_Patient_Desk\Healthcare-Prototype\backend\scratch\whatsapp_webhook_received.log"
    if not os.path.exists(log_path):
        print("Log not found.")
        return
        
    with open(log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    print(f"Total lines: {len(lines)}")
    print("Last 5 lines:")
    for idx in range(max(0, len(lines)-5), len(lines)):
        print(f"[{idx}]: {lines[idx].strip()[:300]}...")

if __name__ == "__main__":
    print_last_lines()
