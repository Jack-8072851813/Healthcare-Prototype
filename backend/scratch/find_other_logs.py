import os
import time

def find_other_logs():
    paths_to_search = [
        r"C:\Users\Bsoft137"
    ]
    found = []
    print("Searching for whatsapp_webhook_received.log...")
    
    for base_path in paths_to_search:
        if os.path.exists(base_path):
            print(f"Scanning: {base_path}")
            for root, dirs, files in os.walk(base_path):
                if any(x in root.lower() for x in ["node_modules", "appdata", "local", "roaming", "searches", "contacts", "links", "saved games", "pictures", "music", "videos", "onedrive"]):
                    continue
                for file in files:
                    if file == "whatsapp_webhook_received.log":
                        full_path = os.path.join(root, file)
                        mtime = os.path.getmtime(full_path)
                        local_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
                        found.append((full_path, mtime, local_time))
                        print(f"  Found: {full_path} (Modified: {local_time})")
                        
    print(f"\nTotal copies found: {len(found)}")

if __name__ == "__main__":
    find_other_logs()
