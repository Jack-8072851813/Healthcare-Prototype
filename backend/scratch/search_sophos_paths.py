import os
import sys

def search_certificates():
    search_paths = [
        r"C:\ProgramData\Sophos",
        r"C:\Program Files\Sophos",
        r"C:\Program Files (x86)\Sophos",
        r"C:\ProgramData\Sophos\Sophos Network Threat Protection\Certificates"
    ]
    
    found_certs = []
    print("Searching for certificate files in Sophos installation directories...")
    
    for path in search_paths:
        if os.path.exists(path):
            print(f"Scanning: {path}")
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file.endswith((".crt", ".pem", ".cer", ".der", ".pem")):
                        full_path = os.path.join(root, file)
                        found_certs.append(full_path)
                        print(f"  Found: {full_path}")
        else:
            print(f"Path does not exist: {path}")
            
    print(f"\nTotal certs found: {len(found_certs)}")

if __name__ == "__main__":
    search_certificates()
