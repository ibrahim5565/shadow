"""
Aegis-Gold v6.0 — Stabilization Verification
Tests local AI supervisor, Flask health API, and resource monitoring.
No external AI dependencies. Fully local.
"""

import sys
import os
import asyncio
import requests

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.ai_supervisor import AISupervisor


async def test_local_ai_supervisor():
    print("\n--- TEST 1: Local AI Supervisor ---")
    supervisor = AISupervisor()
    assert supervisor.enabled, "AISupervisor should be enabled by default"
    print(f"  AI Supervisor enabled: {supervisor.enabled}")
    print("  [PASS] Local AI Supervisor initialized successfully")


def test_heartbeat_api():
    print("\n--- TEST 2: Flask Heartbeat API ---")
    try:
        resp = requests.get("http://127.0.0.1:5001/health", timeout=5)
        print(f"  HTTP Status: {resp.status_code}")
        data = resp.json()
        assert resp.ok, f"Health endpoint failed: {resp.status_code}"
        assert data.get("status") == "online", f"Expected 'online', got '{data.get('status')}'"
        print("  [PASS] Flask Health API is online")
    except requests.exceptions.ConnectionError:
        print("  [SKIP] Bot not running — Flask API unreachable (start bot first)")
    except Exception as e:
        print(f"  [FAIL] {e}")
        raise


def test_resource_monitoring():
    print("\n--- TEST 3: Resource Monitoring ---")
    import psutil, gc
    proc = psutil.Process()
    mem_mb = proc.memory_info().rss / (1024 * 1024)
    cpu_pct = psutil.cpu_percent()
    gc.collect()
    print(f"  Memory: {mem_mb:.1f} MB | CPU: {cpu_pct:.1f}%")
    print("  [PASS] psutil and gc operational")


def test_local_ai_engine():
    print("\n--- TEST 4: Local AI Engine ---")
    import random
    from modules.local_ai import full_analysis
    random.seed(42)
    base = 2000.0
    cands = []
    for _ in range(100):
        o = base + random.uniform(-1, 1)
        h = o + random.uniform(0, 2)
        l = o - random.uniform(0, 2)
        c = random.uniform(l, h)
        cands.append({'open': o, 'high': h, 'low': l, 'close': c})
        base = c + 0.05
    ticks = [{'bid': 2000+i*0.01, 'ask': 2000.01+i*0.01, 'time_msc': 1700000000000+i*100} for i in range(50)]
    result = full_analysis(cands, cands[-30:], ticks, 2003.0, 0.01, {'equity': 10000.0}, 'LONDON', 18.0)
    assert result['action'] in ('TRADE', 'WAIT')
    assert 0 <= result['confidence'] <= 100
    print(f"  action={result['action']} conf={result['confidence']} grade={result['grade']}")
    print("  [PASS] Local AI Engine functional")


async def main():
    print("=" * 52)
    print("   AEGIS-GOLD STABILIZATION VERIFICATION TEST")
    print("=" * 52)
    await test_local_ai_supervisor()
    test_heartbeat_api()
    test_resource_monitoring()
    test_local_ai_engine()
    print("=" * 52)
    print("   ALL TESTS COMPLETE")
    print("=" * 52)


if __name__ == "__main__":
    asyncio.run(main())
