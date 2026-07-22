import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings()

PROXY_LIST_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text"

def test_p(p):
    proxy_url = p if (p.startswith("socks") or p.startswith("http")) else f"socks5://{p}"
    try:
        r = requests.head("https://api.telegram.org", proxies={"https": proxy_url}, timeout=5, verify=True)
        if r.status_code in [302, 307]:
            loc = r.headers.get("Location", "")
            if "172.16." in loc or "block" in loc:
                return None
        return proxy_url, r.status_code
    except Exception:
        return None

try:
    resp = requests.get(PROXY_LIST_URL, timeout=10)
    lines = resp.text.splitlines()
    candidates = [l.strip() for l in lines if l.strip()]
    print(f"Testing all {len(candidates)} proxies concurrently with 50 workers...")
    
    successes = []
    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(test_p, c): c for c in candidates}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                print("FOUND WORKING PROXY:", res)
                successes.append(res)
                # Keep printing, but we can stop after 5
                if len(successes) >= 5:
                    break
    print("Done. Total working found:", len(successes))
except Exception as e:
    print("Error:", e)
