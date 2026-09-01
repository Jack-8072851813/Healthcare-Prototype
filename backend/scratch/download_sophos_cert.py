import urllib.request
import sys
import os

def download_cert():
    urls = [
        "http://passthrough.fw-notify.net/cacert.pem",
        "http://passthrough.fw-notify.net/cacert.der",
        "https://passthrough.fw-notify.net/cacert.pem"
    ]
    
    scratch_dir = os.path.dirname(os.path.abspath(__file__))
    
    for url in urls:
        print(f"Attempting to download from {url}...")
        try:
            # We use a short timeout to not block
            with urllib.request.urlopen(url, timeout=3) as response:
                content = response.read()
                filename = url.split("/")[-1]
                target_path = os.path.join(scratch_dir, f"downloaded_{filename}")
                with open(target_path, "wb") as f:
                    f.write(content)
                print(f"Success! Saved to {target_path}")
                # Print first 100 bytes of content
                print(f"Content starts with: {content[:100]}")
                return target_path
        except Exception as e:
            print(f"Failed for {url}: {e}")
            
    print("Could not download Sophos cert from passthrough.fw-notify.net.")
    return None

if __name__ == "__main__":
    download_cert()
