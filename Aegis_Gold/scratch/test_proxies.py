import requests
import urllib3
urllib3.disable_warnings()

proxies_text = requests.get('https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text').text
proxies = [p.strip() for p in proxies_text.splitlines() if p.strip()]

print(f'Fetched {len(proxies)} proxies. Testing first 25...')

found = 0
for p in proxies:
    if not (p.startswith("socks") or p.startswith("http")):
        continue
    try:
        r = requests.head('https://api.telegram.org', proxies={'https': p}, timeout=4, verify=True)
        print(f'{p} -> Success: status={r.status_code}, loc={r.headers.get("Location", "")}')
        found += 1
        if found >= 5:
            break
    except Exception as e:
        print(f'{p} -> Failed: {str(e)[:120]}')
