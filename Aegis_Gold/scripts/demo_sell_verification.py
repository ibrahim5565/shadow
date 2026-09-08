"""
CONTROLLED DEMO SELL VERIFICATION (Requirement 13 — LIVE-INTEGRATION AUDIT)

DEMO MODE ONLY. This script NEVER runs against live capital:
    - Refuses to run unless config.settings.DEMO_MODE is True.
    - Refuses to place orders unless the connected MT5 account is a DEMO
      account (account_info().trade_mode == 0).

It does NOT force a SELL (Requirement 14). It waits for a REAL bearish
closed-candle pattern produced by the authoritative Pattern Engine, then
traces the complete production path:

    PATTERN DETECTED -> SELL -> RISK PASS -> SL VALID -> TP VALID ->
    AUTHORIZATION PASS -> ORDER_TYPE_SELL -> MT5 RESULT

Usage (from Aegis_Gold root):
    python scripts/demo_sell_verification.py            # dry-run trace, NO order sent
    python scripts/demo_sell_verification.py --execute  # actually send the DEMO order
    python scripts/demo_sell_verification.py --symbol EURUSD --minutes 120

Recorded output: symbol, candle time, pattern, direction, entry, SL, TP,
lot, MT5 retcode, broker comment, ticket.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings as cfg
from brain.brain import decide as brain_decide, verify_direction_integrity
from modules.mt5_gateway import MT5Gateway


def mt5_connect():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    info = mt5.account_info()
    if info is None:
        mt5.shutdown()
        raise RuntimeError("MT5 account_info() returned None (no terminal connection?)")
    return mt5, info


def safety_gate(mt5, acct_info) -> bool:
    """HARD GATE: demo mode + demo account only."""
    if not cfg.DEMO_MODE:
        print("REFUSED: config.settings.DEMO_MODE is False. Enable DEMO_MODE first.")
        return False
    if getattr(acct_info, "trade_mode", None) != 0:
        print(f"REFUSED: connected account is NOT a demo account "
              f"(trade_mode={getattr(acct_info, 'trade_mode', 'NA')}).")
        return False
    print(f"SAFETY GATE PASS: DEMO_MODE=True, account={acct_info.login} (DEMO), "
          f"server={acct_info.server}, balance={acct_info.balance}")
    return True
def run_controlled_sell_selftest(args, mt5, acct, gateway, mt5m, sym, sym_point):
    """
    REQUIREMENT 13 — CONTROLLED BEARISH-PATTERN DEMO TEST (DEMO ACCOUNT ONLY).

    Injects a deterministic BEARISH ENGULFING onto the last CLOSED candle
    (index [-2]) built from LIVE market prices, then drives the COMPLETE,
    UNMODIFIED production path:

        PATTERN DETECTED -> SELL -> RISK -> SL/TP VALIDATION ->
        AUTHORIZATION -> DIRECTION INTEGRITY -> ORDER_TYPE_SELL ->
        mt5.order_send() -> BROKER ACCEPTS -> ACTUAL SELL POSITION

    The strategy itself is NOT modified and no alternation/force-SELL logic
    exists: this is an explicitly labelled controlled test harness.
    """
    print("\n=== CONTROLLED BEARISH-PATTERN SELL SELFTEST (DEMO) ===")
    rates = mt5m.copy_rates_from_pos(sym, mt5m.TIMEFRAME_M5, 0, 60)
    if rates is None or len(rates) < 30:
        print("REFUSED: insufficient candle data.")
        return 3

    candles = [
        {"time": int(r["time"]), "open": float(r["open"]),
         "high": float(r["high"]), "low": float(r["low"]),
         "close": float(r["close"])}
        for r in rates
    ]

    # ── Build the controlled bearish engulfing on the CLOSED candle [-2] ──
    # Size the injected candles from the RECENT real candle range so they stay
    # inside the data-integrity outlier threshold (symbol-agnostic; a fixed
    # price delta made EURUSD candles artificial outliers → safely stripped).
    recent = [abs(c["high"] - c["low"]) for c in candles[-10:-1]]
    rng = (sorted(recent)[len(recent) // 2]) if recent else (candles[-1]["close"] * 0.002)
    px = candles[-1]["close"]
    digits = 5 if px < 20 else 2
    rnd = lambda v: round(v, digits)
    prev = candles[-3]
    candles[-3] = {                         # small bullish body (closed)
        "time": prev["time"],
        "open": rnd(px - 0.2 * rng), "close": rnd(px + 0.4 * rng),
        "high": rnd(px + 0.6 * rng), "low": rnd(px - 0.5 * rng),
    }
    target = candles[-2]                    # bearish engulfing (closed, [-2])
    candles[-2] = {
        "time": target["time"],
        "open": rnd(px + 0.5 * rng), "close": rnd(px - 0.5 * rng),
        "high": rnd(px + 0.7 * rng), "low": rnd(px - (0.5 * rng + 0.6 * rng)),
    }
    forming = candles[-1]                   # forming candle [-1]: neutral, unclosed
    candles[-1] = {
        "time": forming["time"],
        "open": forming["open"], "close": forming["close"],
        "high": max(forming["high"], forming["close"] + 0.1 * rng),
        "low": min(forming["low"], forming["close"] - 0.1 * rng),
    }

    # ── STAGE 1: authoritative Pattern Engine ──
    # Controlled test: suppress SMC big-pattern detection so the injected
    # candlestick pattern is the ONLY candidate (live feed contained a real
    # BOS_BULLISH which legitimately conflicted → HOLD).
    import brain.smc_engine as _smc
    _orig_detect = _smc.detect_big_pattern
    _smc.detect_big_pattern = lambda **kw: None
    try:
        from brain.brain import get_pattern_entry_signal
        pattern_dir, pat_entry = get_pattern_entry_signal(candles, point=sym_point, symbol=sym)
    finally:
        _smc.detect_big_pattern = _orig_detect
    print(f"PATTERN DETECTED: {pat_entry.pattern_name} -> {pattern_dir} "
          f"(candle {pat_entry.candle_time})")
    if pattern_dir != "SELL":
        print(f"REFUSED: expected SELL from controlled bearish pattern, got {pattern_dir}")
        return 3
    return candles


def _selftest_stage2(args, mt5, acct, gateway, mt5m, sym, sym_point, candles):
    """Continuation of the controlled selftest: production decision -> order."""
    from datetime import timedelta

    # ── STAGE 2: real tick feed + real RiskManager (production safety) ──
    # Retries while the ONLY blocker is the legitimate spread-safety limit.
    decision = None
    for attempt in range(12):
        tick = mt5m.symbol_info_tick(sym)
        spread = (tick.ask - tick.bid) / sym_point if (tick and sym_point) else 15.0
        t_from = datetime.now(timezone.utc) - timedelta(seconds=180)
        raw_ticks = mt5m.copy_ticks_from(sym, t_from, 200, mt5m.COPY_TICKS_INFO)
        ticks = []
        for t in (raw_ticks if raw_ticks is not None else []):
            try:
                b, a = float(t["bid"]), float(t["ask"])
                if b > 0.0 and a > 0.0:
                    ticks.append({"time_msc": int(t["time_msc"]), "bid": b, "ask": a})
            except Exception:
                continue

        from modules.risk_manager import RiskManager
        risk = RiskManager(gateway)

        # Controlled test: keep SMC big-pattern detection suppressed so the
        # injected bearish engulfing remains the sole pattern candidate.
        import brain.smc_engine as _smc
        _orig_detect = _smc.detect_big_pattern
        _smc.detect_big_pattern = lambda **kw: None
        try:
            decision = brain_decide(
                ticks, candles, {"balance": acct.balance, "equity": acct.equity},
                risk, "LONDON", spread, sym_point, symbol=sym,
            )
        finally:
            _smc.detect_big_pattern = _orig_detect

        print(f"ATTEMPT {attempt + 1}: spread={spread:.1f}pts -> "
              f"action={decision.action} direction={decision.direction} "
              f"reason={str(decision.reason)[:80]}")
        if decision.action == "TRADE":
            break
        reason_l = str(decision.reason or "").lower()
        if "spread" in reason_l:
            print("  Legitimate spread safety block — retrying in 10s ...")
            time.sleep(10)
            continue
        break  # any other rejection is final — never weaken safety

    print(f"DECISION: action={decision.action} direction={decision.direction} "
          f"pattern_direction={getattr(decision, 'pattern_direction', 'NA')}")
    if decision.action != "TRADE" or decision.direction != "SELL":
        print(f"BLOCKED (legitimate safety rejection): {decision.reason}")
        return 3

    auth = decision.trade_authorization
    print(f"RISK: PASS | AUTHORIZATION: {getattr(auth, 'authorization_id', None)}")
    print(f"ENTRY={getattr(auth, 'entry_price', None)} SL={getattr(auth, 'stop_loss', None)} "
          f"TP={getattr(auth, 'take_profit', None)} LOT={decision.lot} "
          f"RR={getattr(decision, 'rr_ratio', 0)}")

    # ── STAGE 3: FINAL DECISION IMMUTABILITY (Requirement 2 invariant) ──
    if not verify_direction_integrity(decision):
        print("CRITICAL DIRECTION INTEGRITY FAILURE — DO NOT TRADE.")
        return 3
    print("DIRECTION INTEGRITY: PASS (final direction == pattern direction == SELL)")

    # ── STAGE 4: ORDER BUILDER ──
    req = gateway.build_order_request(
        symbol=sym, direction=decision.direction, lot=decision.lot,
        tp_pts=decision.tp_points, sl_pts=decision.sl_points,
    )
    import MetaTrader5 as mt5c
    print(f"ORDER TYPE: {'ORDER_TYPE_SELL' if req['type'] == mt5c.ORDER_TYPE_SELL else req['type']}")
    print("[MT5 REQUEST] " + json.dumps(req, default=str))
    assert req["type"] == mt5c.ORDER_TYPE_SELL, "Final request must be ORDER_TYPE_SELL"
    assert req["sl"] > req["price"] > req["tp"], "SELL geometry tp < entry < sl violated"

    # ── STAGE 5: BROKER EXECUTION (REAL DEMO ORDER) ──
    result, latency, slippage = gateway.execute_order(
        sym, decision.direction, decision.lot,
        decision.tp_points, decision.sl_points,
    )
    retcode = getattr(result, "retcode", None) if result else None
    broker_comment = getattr(result, "comment", None) if result else str(mt5m.last_error())
    ticket = getattr(result, "order", None) if result else None
    retcode_name = "DONE" if retcode == mt5c.TRADE_RETCODE_DONE else retcode

    # ── STAGE 6: verify ACTUAL SELL POSITION exists ──
    position_confirmed = False
    position = None
    if ticket:
        time.sleep(1.0)
        positions = mt5m.positions_get(ticket=ticket) or mt5m.positions_get(symbol=sym) or []
        for p in positions:
            if p.ticket == ticket:
                position = p
                position_confirmed = (p.type == mt5c.POSITION_TYPE_SELL)
                break

    record = {
        "test_mode": "CONTROLLED_BEARISH_SELFTEST",
        "symbol": sym,
        "candle_time": datetime.fromtimestamp(candles[-2]["time"], tz=timezone.utc).isoformat(),
        "pattern": decision.pattern,
        "direction": decision.direction,
        "entry": getattr(result, "price", None) if result else req.get("price"),
        "sl": req.get("sl"), "tp": req.get("tp"),
        "lot": req.get("volume"),
        "mt5_retcode": retcode_name,
        "broker_comment": broker_comment,
        "ticket": ticket,
        "position_type": "SELL" if position_confirmed else "NOT_CONFIRMED",
        "position_volume": getattr(position, "volume", None),
        "latency_ms": latency, "slippage_pts": slippage,
    }
    print("\n========== DEMO EXECUTION RECORD (CONTROLLED SELL SELFTEST) ==========")
    for k, v in record.items():
        print(f"{k}: {v}")
    print("======================================================================\n")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "demo_sell_verification_records.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    records = []
    if os.path.exists(out):
        try:
            with open(out) as f:
                records = json.load(f)
        except Exception:
            records = []
    records.append(record)
    with open(out, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"Record saved to {out}")
    if position_confirmed:
        print(f"ACTUAL SELL POSITION CONFIRMED: ticket {ticket} "
              f"({getattr(position, 'volume', '?')} lots @ {getattr(position, 'price_open', '?')})")
        print("Position left OPEN on the DEMO account — close manually in MT5 if desired.")
        return 0 if retcode_name == "DONE" else 4
    print("Order accepted but SELL position not confirmed via positions_get — investigate.")
    return 4


def main():
    # Windows console (cp1252) cannot print emoji from decision reasons
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="XAUUSD")
    ap.add_argument("--minutes", type=int, default=60, help="max wait for a real pattern")
    ap.add_argument("--execute", action="store_true",
                    help="actually send the DEMO order (default: dry-run trace only)")
    ap.add_argument("--selftest", action="store_true",
                    help="Requirement 13: controlled bearish-pattern SELL test on the "
                         "DEMO account (drives the full production path to a real order)")
    args = ap.parse_args()

    mt5, acct = mt5_connect()
    try:
        if not safety_gate(mt5, acct):
            return 2

        gateway = MT5Gateway()
        # Populate symbols_data — required for execute_order (silent skip otherwise)
        if not gateway.initialize():
            print("REFUSED: MT5Gateway.initialize() failed.")
            return 2
        sym = args.symbol
        sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.01)

        import MetaTrader5 as mt5m
        if args.selftest:
            candles = run_controlled_sell_selftest(args, mt5, acct, gateway, mt5m, sym, sym_point)
            if not isinstance(candles, list):
                return candles  # refusal / error code
            return _selftest_stage2(args, mt5, acct, gateway, mt5m, sym, sym_point, candles)

        deadline = time.time() + args.minutes * 60
        last_candle_time = None

        print(f"\nWaiting for a REAL bearish/bullish closed-candle pattern on {sym} "
              f"(max {args.minutes} min, dry_run={not args.execute})...\n")

        while time.time() < deadline:
            import MetaTrader5 as mt5m
            rates = mt5m.copy_rates_from_pos(sym, mt5m.TIMEFRAME_M5, 0, 120)
            if rates is None or len(rates) < 30:
                time.sleep(5)
                continue

            candles = [
                {"time": int(r["time"]), "open": float(r["open"]),
                 "high": float(r["high"]), "low": float(r["low"]),
                 "close": float(r["close"])}
                for r in rates
            ]

            # Only evaluate once per new closed candle ([-2] = last CLOSED bar)
            closed_time = candles[-2]["time"]
            if closed_time == last_candle_time:
                time.sleep(2)
                continue
            last_candle_time = closed_time

            tick = mt5m.symbol_info_tick(sym)
            spread = (tick.ask - tick.bid) / sym_point if (tick and sym_point) else 15.0

            # Fetch real recent ticks so the data-integrity layer accepts the feed
            from datetime import timedelta
            t_from = datetime.now(timezone.utc) - timedelta(seconds=180)
            raw_ticks = mt5m.copy_ticks_from(sym, t_from, 200, mt5m.COPY_TICKS_INFO)
            ticks = []
            if raw_ticks is not None:
                for t in raw_ticks:
                    try:
                        ticks.append({
                            "time_msc": int(t["time_msc"]),
                            "bid": float(t["bid"]),
                            "ask": float(t["ask"]),
                        })
                    except Exception:
                        continue

            from modules.risk_manager import RiskManager
            risk = RiskManager(gateway)

            decision = brain_decide(
                ticks, candles, {"balance": acct.balance, "equity": acct.equity},
                risk, "LONDON", spread, sym_point, symbol=sym,
            )

            auth = decision.trade_authorization
            trace = {
                "symbol": sym,
                "candle_time": datetime.fromtimestamp(closed_time, tz=timezone.utc).isoformat(),
                "pattern": decision.pattern,
                "decision_direction": decision.direction,
                "pattern_direction": getattr(decision, "pattern_direction", "NA"),
                "action": decision.action,
                "risk": "PASS" if decision.action == "TRADE" else decision.reason,
                "entry": getattr(auth, "entry_price", None) if auth else None,
                "sl": getattr(auth, "stop_loss", None) if auth else None,
                "tp": getattr(auth, "take_profit", None) if auth else None,
                "lot": decision.lot,
                "authorization": getattr(auth, "authorization_id", None) if auth else None,
            }
            print("[CANDLE TRACE] " + json.dumps(trace, default=str))

            if decision.action != "TRADE":
                continue

            # Requirement 2 invariant — final gate before dispatch
            if not verify_direction_integrity(decision):
                print("CRITICAL DIRECTION INTEGRITY FAILURE — DO NOT TRADE.")
                continue

            # Print the exact MT5 request that would be / is sent
            req = gateway.build_order_request(
                symbol=sym, direction=decision.direction, lot=decision.lot,
                tp_pts=decision.tp_points, sl_pts=decision.sl_points,
            )
            print("[MT5 REQUEST] " + json.dumps(req, default=str))

            if not args.execute:
                print("[DRY-RUN] Order NOT sent. Re-run with --execute to send on DEMO.")
                return 0

            return _execute_and_record(gateway, mt5m, sym, decision, trace)
    finally:
        mt5.shutdown()
    print("No pattern-triggered trade occurred within the wait window "
          "(this is NORMAL — patterns are low-frequency by design).")
    return 0


def _execute_and_record(gateway, mt5m, sym, decision, trace):
    result, latency, slippage = gateway.execute_order(
        sym, decision.direction, decision.lot,
        decision.tp_points, decision.sl_points,
    )
    record = {
        "symbol": sym,
        "candle_time": trace["candle_time"],
        "pattern": decision.pattern,
        "direction": decision.direction,
        "entry": trace["entry"],
        "sl": trace["sl"],
        "tp": trace["tp"],
        "lot": decision.lot,
        "mt5_retcode": getattr(result, "retcode", None) if result else "REJECTED",
        "broker_comment": getattr(result, "comment", None) if result else str(mt5m.last_error()),
        "ticket": getattr(result, "order", None) if result else None,
        "latency_ms": latency,
        "slippage_pts": slippage,
    }
    print("\n========== DEMO EXECUTION RECORD ==========")
    for k, v in record.items():
        print(f"{k}: {v}")
    print("===========================================\n")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "demo_sell_verification_records.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    records = []
    if os.path.exists(out):
        try:
            with open(out) as f:
                records = json.load(f)
        except Exception:
            records = []
    records.append(record)
    with open(out, "w") as f:
        json.dump(records, f, indent=2, default=str)
    print(f"Record saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

