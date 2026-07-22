"""Quick self-test for modules/local_ai.py using synthetic data."""
import sys, random
sys.path.insert(0, '.')

from modules.local_ai import (
    detect_trend, analyze_structure, analyze_momentum,
    analyze_volatility, detect_support_resistance,
    score_risk, score_confidence, filter_entry, optimize_exit, full_analysis
)

random.seed(42)

# Synthetic M5 candles — slight uptrend
base = 2000.0
candles_m5 = []
for i in range(120):
    o = base + random.uniform(-1, 1)
    h = o + random.uniform(0, 2)
    l = o - random.uniform(0, 2)
    c = random.uniform(l, h)
    candles_m5.append({'open': o, 'high': h, 'low': l, 'close': c})
    base = c + 0.05

candles_m1 = candles_m5[-30:]
ticks = [
    {'bid': 2000.0 + i*0.01, 'ask': 2000.01 + i*0.01, 'time_msc': 1700000000000 + i*100}
    for i in range(50)
]
account = {'equity': 10000.0, 'balance': 10000.0}

PASS = 0
FAIL = 0

def check(name, result, key, expected_type):
    global PASS, FAIL
    val = result.get(key)
    if isinstance(val, expected_type):
        print(f"  [OK]  {name}.{key} = {val}")
        PASS += 1
    else:
        print(f"  [FAIL] {name}.{key} expected {expected_type.__name__}, got {type(val).__name__}: {val}")
        FAIL += 1

print("\n=== LOCAL AI ENGINE TEST ===\n")

t = detect_trend(candles_m5, candles_m1)
check("trend", t, "trend", str)
check("trend", t, "trend_score", int)
check("trend", t, "adx_m5", float)

s = analyze_structure(candles_m5, 2003.0, 0.01, 50.0)
check("structure", s, "position", str)
check("structure", s, "preferred_direction", str)
check("structure", s, "structure_score", int)

m = analyze_momentum(ticks, candles_m1, 0.01)
check("momentum", m, "strong_momentum", bool)
check("momentum", m, "momentum_score", int)
check("momentum", m, "tps", float)

v = analyze_volatility(candles_m5, 0.01)
check("volatility", v, "volatility_state", str)
check("volatility", v, "news_spike_detected", bool)
check("volatility", v, "volatility_ratio", float)

sr = detect_support_resistance(candles_m5, 0.01)
check("sr", sr, "supports", list)
check("sr", sr, "resistances", list)
check("sr", sr, "count", int)

r = score_risk(account, "LONDON", 18.0, 25.0, 40.0)
check("risk", r, "approved", bool)
check("risk", r, "risk_score", int)
check("risk", r, "rr_ratio", float)

conf = score_confidence(t, s, m, v, r, entry_score=60)
check("confidence", conf, "confidence", int)
check("confidence", conf, "grade", str)
check("confidence", conf, "tradeable", bool)

e = filter_entry(candles_m5, ticks, "BUY", 0.01)
check("entry", e, "entry_approved", bool)
check("entry", e, "entry_score", int)
check("entry", e, "pattern", str)
check("entry", e, "rsi", float)

ex = optimize_exit(candles_m5, candles_m1, 0.01, "BUY")
check("exit", ex, "tp", int)
check("exit", ex, "sl", int)
check("exit", ex, "exhaustion", bool)

fa = full_analysis(candles_m5, candles_m1, ticks, 2003.0, 0.01,
                   account, "LONDON", 18.0)
check("full", fa, "action", str)
check("full", fa, "direction", str)
check("full", fa, "confidence", int)
check("full", fa, "grade", str)

print(f"\n=== RESULTS: {PASS} passed, {FAIL} failed ===\n")
sys.exit(0 if FAIL == 0 else 1)
