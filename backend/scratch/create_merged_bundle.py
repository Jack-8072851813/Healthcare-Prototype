import certifi
import os
import requests

def create_merged_bundle():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sophos_cert_path = os.path.join(backend_dir, "scratch", "extracted_cert_1.pem")
    
    if not os.path.exists(sophos_cert_path):
        print("Sophos cert not found at scratch/extracted_cert_1.pem!")
        return
        
    merged_bundle_path = os.path.join(backend_dir, "merged_ca_bundle.pem")
    
    print("Reading standard certifi bundle...")
    with open(certifi.where(), "r", encoding="utf-8") as f:
        certifi_data = f.read()
        
    print("Reading Sophos Root CA certificate...")
    with open(sophos_cert_path, "r", encoding="utf-8") as f:
        sophos_data = f.read()
        
    print(f"Writing merged bundle to {merged_bundle_path}...")
    with open(merged_bundle_path, "w", encoding="utf-8") as f:
        f.write(certifi_data)
        f.write("\n\n# Sophos SSL Interception Root CA\n")
        f.write(sophos_data)
        
    print("Setting REQUESTS_CA_BUNDLE environment variable...")
    os.environ["REQUESTS_CA_BUNDLE"] = merged_bundle_path
    
    print("Testing connection to graph.facebook.com WITHOUT manual verify param...")
    try:
        res = requests.get("https://graph.facebook.com/v17.0", timeout=5)
        print(f"Success! Status code: {res.status_code}")
        print("Response headers:", dict(res.headers))
    except Exception as e:
        print(f"Failed with merged bundle: {type(e).__name__}: {e}")

if __name__ == "__main__":
    create_merged_bundle()
