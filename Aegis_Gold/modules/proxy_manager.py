import os
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger("aegis.proxy")

PROXY_CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "active_proxy.txt")
PROXY_LIST_URL = "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocolipport&format=text&timeout=1200"

_current_proxy = None
_last_check_time = 0
_check_interval = 300  # 5 minutes

def get_working_proxy() -> str | None:
    """Retrieve the cached working proxy, or find a new one."""
    global _current_proxy, _last_check_time
    
    now = time.time()
    if _current_proxy and (now - _last_check_time < _check_interval):
        return _current_proxy
        
    # Read from file cache if available
    if not _current_proxy and os.path.exists(PROXY_CACHE_FILE):
        try:
            with open(PROXY_CACHE_FILE, "r") as f:
                cached = f.read().strip()
            if cached:
                if test_proxy_sync(cached):
                    _current_proxy = cached
                    _last_check_time = now
                    return _current_proxy
        except Exception:
            pass

    logger.info("Current proxy invalid or expired. Finding a new working proxy...")
    new_proxy = find_proxy_concurrent()
    
    if new_proxy:
        _current_proxy = new_proxy
        _last_check_time = now
        try:
            os.makedirs(os.path.dirname(PROXY_CACHE_FILE), exist_ok=True)
            with open(PROXY_CACHE_FILE, "w") as f:
                f.write(new_proxy)
        except Exception:
            pass
            
    return _current_proxy

def test_proxy_sync(proxy_url: str) -> bool:
    """Test a proxy synchronously."""
    try:
        resp = requests.head(
            "https://api.telegram.org",
            proxies={"https": proxy_url},
            timeout=4,
            verify=True
        )
        if resp.status_code in [302, 307]:
            loc = resp.headers.get("Location", "")
            if "172.16." in loc or "block" in loc:
                return False
        return True
    except Exception:
        return False

def find_proxy_concurrent() -> str | None:
    """Find a working proxy concurrently using a ThreadPoolExecutor."""
    try:
        resp = requests.get(PROXY_LIST_URL, timeout=8)
        if not resp.ok:
            return None
        raw_proxies = [p.strip() for p in resp.text.splitlines() if p.strip()]
    except Exception as e:
        logger.error(f"Failed to fetch proxy list: {e}")
        return None

    proxies = []
    for p in raw_proxies:
        if p.startswith("socks") or p.startswith("http"):
            proxies.append(p)
        elif ":" in p:
            proxies.append(f"socks5://{p}")

    # Prioritize socks5, socks4, then http
    socks5 = [p for p in proxies if p.startswith("socks5")]
    socks4 = [p for p in proxies if p.startswith("socks4")]
    http = [p for p in proxies if p.startswith("http")]
    candidates = socks5[:40] + socks4[:20] + http[:20]

    if not candidates:
        return None

    logger.info(f"Testing {len(candidates)} candidates concurrently...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_proxy = {executor.submit(test_proxy_sync, p): p for p in candidates}
        for future in as_completed(future_to_proxy):
            proxy = future_to_proxy[future]
            try:
                is_working = future.result()
                if is_working:
                    return proxy
            except Exception:
                pass
    return None
