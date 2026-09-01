import urllib.request
import json

def check_tunnels():
    url = "http://127.0.0.1:4040/api/tunnels"
    print(f"Querying ngrok tunnels: {url}")
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            print(json.dumps(data, indent=2))
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    check_tunnels()
