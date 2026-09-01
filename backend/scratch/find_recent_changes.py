import os
import time

def find_recent():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"Scanning files in {backend_dir} modified in the last 15 minutes...")
    now = time.time()
    found = []
    
    for root, dirs, files in os.walk(backend_dir):
        if "venv" in root or ".git" in root or ".pytest_cache" in root or "__pycache__" in root:
            continue
        for file in files:
            full_path = os.path.join(root, file)
            try:
                mtime = os.path.getmtime(full_path)
                if now - mtime < 15 * 60: # 15 minutes
                    found.append((full_path, mtime))
            except Exception:
                pass
                
    found.sort(key=lambda x: x[1], reverse=True)
    print(f"Found {len(found)} files modified recently:")
    for path, mtime in found:
        local_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mtime))
        print(f"  {path} (Modified: {local_time})")

if __name__ == "__main__":
    find_recent()
