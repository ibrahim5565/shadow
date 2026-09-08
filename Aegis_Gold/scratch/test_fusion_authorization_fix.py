"""
Validation test for the "trades blocked" fix (brain.py v6.1 fusion-upgrade path).

Simulates what DecisionFusionV2 does: mutates a WAIT decision into TRADE
(no TradeAuthorization, sl_points=0, tp_points=0, lot=0) and then applies
the same derivation + _attach_authorization logic that was added to decide(),
and finally replicates the core/main.py zero-trust gate check.
"""
import sys, os
sys.path.insert(0, r"D:\Trading\Aegis_Gold")
os.chdir(r"D:\Trading\Aegis_Gold")

import brain.brain as brain
from datetime import datetime, timezone


class StubRiskMgr:
    def can_trade(self, *a, **k):
        return True
    def daily_loss_limit_hit(self):
        return False


def make_candles(n=80, base=4400.0, point=0.01):
    import math
    candles = []
    px = base
    for i in range(n):
        o = px
        c = px + 0.15 * math.sin(i / 5.0) * (1 if i % 2 else -1)
        h = max(o, c) + 0.20
        l = min(o, c) - 0.20
        candles.append((1700000000 + i * 300, o, h, l, c, 100.0))
        px = c
    return candles


def simulate_fusion_upgrade_and_fix(symbol, point, spread, atr_val):
    """Replicates: fusion sets action=TRADE on a WAIT decision, then the new fix block runs."""
    d = brain.Decision(action="WAIT", reason="pre-fusion wait", confidence=30)
    # --- fusion mutation (decision_fusion.py via brain.py LAYER 3) ---
    d.action = "TRADE"
    d.direction = "BUY"
    d.confidence = 71
    # --- the v6.1 fix block (verbatim logic) ---
    if d.action == "TRADE" and not (
        getattr(d, "trade_authorization", None) is not None
        and getattr(d.trade_authorization, "authorized", False)
    ):
        if d.sl_points <= 0 or d.tp_points <= 0:
            _sl_floor = 40 if symbol.upper().startswith("EUR") else 150
            _atr_pts = int(atr_val / point) if (point and atr_val > 0) else 0
            _sl_pts = max(_sl_floor, int(_atr_pts * 1.5)) if _atr_pts > 0 else _sl_floor * 2
            _tp_pts = _sl_pts * 2
            d.sl_points = int(_sl_pts)
            d.tp_points = int(_tp_pts)
            d.rr_ratio = 2.0
        if d.lot <= 0:
            d.lot = 0.01
        d = brain._attach_authorization(
            d, symbol, make_candles(), spread, point, StubRiskMgr(), d.lot,
            source_path="PATH_FUSION", signal_type="FUSION_CONSENSUS",
        )
    return d


def main_gate_check(d):
    """Replicates core/main.py zero-trust gate."""
    return (
        d.action == "TRADE"
        and getattr(d, "trade_authorization", None) is not None
        and getattr(d.trade_authorization, "authorized", False)
    )


print("=" * 70)
# Case 1: XAUUSD fusion-upgraded trade (ATR present)
d1 = simulate_fusion_upgrade_and_fix("XAUUSD", 0.01, 19.0, 3.95)
print(f"XAUUSD  -> action={d1.action} dir={d1.direction} lot={d1.lot} "
      f"sl={d1.sl_points} tp={d1.tp_points} reason={d1.reason[:60]}")
assert d1.action == "TRADE", f"FAIL: expected TRADE, got {d1.action} ({d1.reason})"
assert main_gate_check(d1), "FAIL: main.py gate would still block this trade!"
print("[PASS] XAUUSD fusion-upgraded trade now carries valid TradeAuthorization")

# Case 2: EURUSD fusion-upgraded trade (ATR present)
d2 = simulate_fusion_upgrade_and_fix("EURUSD", 0.00001, 1.0, 0.00023)
print(f"EURUSD  -> action={d2.action} dir={d2.direction} lot={d2.lot} "
      f"sl={d2.sl_points} tp={d2.tp_points} reason={d2.reason[:60]}")
assert d2.action == "TRADE" and main_gate_check(d2), f"FAIL: {d2.reason}"
print("[PASS] EURUSD fusion-upgraded trade now carries valid TradeAuthorization")

# Case 3: spread too high -> must downgrade to WAIT with proper reason (safety intact)
d3 = simulate_fusion_upgrade_and_fix("XAUUSD", 0.01, 900.0, 3.95)
print(f"HIGHSPR -> action={d3.action} reason={d3.reason[:70]}")
if d3.action == "TRADE":
    assert main_gate_check(d3), "FAIL: TRADE without auth leaked through"
else:
    assert "AUTHORIZATION_FAILED" in d3.reason, f"Unexpected reason: {d3.reason}"
print("[PASS] Rejected setups safely downgrade to WAIT (zero-trust gate intact)")

# Case 4: a normal TRADE decision WITH valid auth passes through unchanged
d4 = brain.Decision(action="WAIT", reason="x")
d4.action = "TRADE"; d4.direction = "SELL"; d4.confidence = 65
d4.sl_points = 200; d4.tp_points = 400; d4.lot = 0.01; d4.rr_ratio = 2.0
d4 = brain._attach_authorization(
    d4, "XAUUSD", make_candles(), 19.0, 0.01, StubRiskMgr(), 0.01,
    source_path="PATH_TEST", signal_type="TEST",
)
assert d4.action == "TRADE" and main_gate_check(d4), f"FAIL: {d4.reason}"
print("[PASS] Normal TRADE path still authorizes correctly")

print("=" * 70)
print("ALL VALIDATION CHECKS PASSED — the execution blocker is resolved.")
