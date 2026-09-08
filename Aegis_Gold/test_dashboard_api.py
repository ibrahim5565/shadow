"""
Quick diagnostic test for dashboard API
Verifies that all required fields are present for XAUUSD
"""
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import requests
import json

API_URL = "http://127.0.0.1:5001"

print("="*60)
print("AEGIS DASHBOARD API DIAGNOSTIC TEST")
print("="*60)

# Test /aistate endpoint
print("\n[1] Testing /aistate endpoint...")
try:
    resp = requests.get(f"{API_URL}/aistate", timeout=5)
    if resp.ok:
        data = resp.json()
        print(f"✅ /aistate endpoint OK (HTTP {resp.status_code})")
        
        # Check XAUUSD data
        if "XAUUSD" in data:
            xauusd = data["XAUUSD"]
            print(f"\n📊 XAUUSD Data:")
            print(f"   Confidence: {xauusd.get('confidence', 'MISSING')}%")
            print(f"   Action: {xauusd.get('action', 'MISSING')}")
            print(f"   Direction: {xauusd.get('direction', 'MISSING')}")
            print(f"   ADX: {xauusd.get('adx', 'MISSING')}")
            print(f"   RSI: {xauusd.get('rsi', 'MISSING')}")
            print(f"   Grade: {xauusd.get('grade', 'MISSING')}")
            print(f"   Regime: {xauusd.get('regime', 'MISSING')}")
            print(f"   Regime Score: {xauusd.get('regime_score', 'MISSING')}")
            print(f"   Structure Score: {xauusd.get('structure_score', 'MISSING')}")
            print(f"   Entry Score: {xauusd.get('entry_score', 'MISSING')}")
            print(f"   Reason: {xauusd.get('reason', 'MISSING')}")
            
            # Check for missing fields
            required_fields = ['confidence', 'action', 'direction', 'adx', 'rsi', 'grade', 
                             'regime', 'regime_score', 'structure_score', 'entry_score']
            missing = [f for f in required_fields if f not in xauusd]
            if missing:
                print(f"\n⚠️  MISSING FIELDS: {', '.join(missing)}")
            else:
                print(f"\n✅ All required fields present")
                
            # Pretty print full response
            print(f"\n📄 Full XAUUSD Response:")
            print(json.dumps(xauusd, indent=2))
        else:
            print("❌ XAUUSD data not found in response")
            
        # Check EURUSD data
        if "EURUSD" in data:
            eurusd = data["EURUSD"]
            print(f"\n📊 EURUSD Data:")
            print(f"   Confidence: {eurusd.get('confidence', 'MISSING')}%")
            print(f"   Action: {eurusd.get('action', 'MISSING')}")
            print(f"   Direction: {eurusd.get('direction', 'MISSING')}")
    else:
        print(f"❌ /aistate endpoint failed (HTTP {resp.status_code})")
except requests.exceptions.ConnectionError:
    print("❌ Bot not running - API unreachable")
except Exception as e:
    print(f"❌ Error: {e}")

# Test /status endpoint
print("\n[2] Testing /status endpoint...")
try:
    resp = requests.get(f"{API_URL}/status", timeout=5)
    if resp.ok:
        data = resp.json()
        print(f"✅ /status endpoint OK")
        print(f"   Bot Status: {data.get('status', 'UNKNOWN')}")
        print(f"   Equity: ${data.get('equity', 0):.2f}")
        print(f"   Daily P&L: ${data.get('daily_pnl', 0):.2f}")
    else:
        print(f"❌ /status endpoint failed (HTTP {resp.status_code})")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)
print("\nIf all data is present above but dashboard shows 0%:")
print("1. Open browser DevTools (F12)")
print("2. Check Console tab for JavaScript errors")
print("3. Check Network tab to see if API calls are successful")
print("4. Try hard refresh (Ctrl+Shift+R) to clear cache")
print("5. Check if CORS is enabled in browser")
