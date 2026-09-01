import urllib.request
import json
import base64

def check_failed_requests():
    url = "http://127.0.0.1:4040/api/requests/http?limit=50"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            requests_list = data.get("requests", [])
            print(f"Total requests: {len(requests_list)}")
            
            failed_requests = [r for r in requests_list if r.get("response", {}).get("status_code", 200) != 200]
            print(f"Failed requests (status != 200): {len(failed_requests)}")
            
            for idx, r in enumerate(failed_requests):
                req_info = r.get("request", {})
                res_info = r.get("response", {})
                method = req_info.get("method")
                uri = req_info.get("uri")
                status = res_info.get("status_code")
                start = r.get("start")
                user_agent = req_info.get("headers", {}).get("User-Agent", [""])[0]
                
                print(f"\n[{idx}] {method} {uri} -> Status: {status} | User-Agent: {user_agent} | Time: {start}")
                
                # Check body
                raw_req_b64 = req_info.get("raw")
                if raw_req_b64:
                    raw_bytes = base64.b64decode(raw_req_b64)
                    raw_str = raw_bytes.decode("utf-8", errors="ignore")
                    if "\r\n\r\n" in raw_str:
                        headers, body = raw_str.split("\r\n\r\n", 1)
                        print(f"  Request Body: {body.strip()}")
                    else:
                        print(f"  Raw Request (truncated): {raw_str[:300]}")
                        
                # Check response
                raw_res_b64 = res_info.get("raw")
                if raw_res_b64:
                    raw_bytes = base64.b64decode(raw_res_b64)
                    raw_str = raw_bytes.decode("utf-8", errors="ignore")
                    if "\r\n\r\n" in raw_str:
                        headers, body = raw_str.split("\r\n\r\n", 1)
                        print(f"  Response Body: {body.strip()}")
                    else:
                        print(f"  Raw Response (truncated): {raw_str[:300]}")
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    check_failed_requests()
