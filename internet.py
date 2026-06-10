import sys
import urllib.request
import ssl

try:
    import certifi
    ssl_context = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    ssl_context = ssl.create_default_context()

if len(sys.argv) < 2:
    print("Usage: internet.py <URL>")
    sys.exit(1)

url = sys.argv[1]
try:
    with urllib.request.urlopen(url, context=ssl_context) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)