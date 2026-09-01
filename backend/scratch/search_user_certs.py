import os
import sys

def search_user_certs():
    paths_to_search = [
        r"C:\Users\Bsoft137",
        r"C:\Users\Bsoft137\.gemini"
    ]
    found = []
    print("Searching user folder for certificates...")
    
    for base_path in paths_to_search:
        if os.path.exists(base_path):
            print(f"Scanning: {base_path}")
            # Limit depth to avoid scanning everything
            for root, dirs, files in os.walk(base_path):
                # Skip large build or node_modules directories if any
                if any(x in root.lower() for x in ["node_modules", "appdata", "local", "roaming", "searches", "contacts", "links", "saved games", "pictures", "music", "videos", "onedrive"]):
                    continue
                for file in files:
                    if file.endswith((".crt", ".pem", ".cer", ".der")):
                        full_path = os.path.join(root, file)
                        # Avoid certifi's cacert.pem if in some venv
                        if "cacert.pem" in file:
                            continue
                        found.append(full_path)
                        print(f"  Found: {full_path}")
        else:
            print(f"Path does not exist: {base_path}")
            
    print(f"\nTotal: {len(found)}")

if __name__ == "__main__":
    search_user_certs()
