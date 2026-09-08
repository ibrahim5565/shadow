"""
AEGIS GOLD — Phase 2: Live Shadow Run
======================================
Connects to MT5 demo account and runs the FULL 11-stage decision pipeline
in CHAMPION/CHALLENGER SHADOW MODE — reads real market data, generates
signals, but NEVER places, modifies, or closes any trade.

Per-cycle log fields:
  timestamp, session, price, stat_edge, smc_grade, smc_score, smc_dir,
  regime, mtf_alignment, kronos_dir, kronos_vol, dqn_action, dqn_conf,
  ml_dir, ml_prob, fused_dir, fused_conf, final_action, reason,
  subsignal_agreement (0-4)

Usage:
    cd d:\\Trading\\Aegis_Gold
    .venv_cuda\\Scripts\\python.exe scripts\\shadow_run.py [--cycles N] [--symbol XAUUSD]

Defaults: --cycles 50  --symbol XAUUSD
"""

import sys
import os
import logging
import json
import time
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Safety assertion: shadow run must never touch order_send ────
# We deliberately do NOT import any execution modules.
_FORBIDDEN_IMPORTS = {"brain.execution", "execution", "order_send", "place_trade"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
)
logger = logging.getLogger("shadow_run")

SEP  = "=" * 72
SEP2 = "-" * 72


def section(title: str):
    logger.info(SEP)
    logger.info(f"  {title}")
    logger.info(SEP)


# ── MT5 helpers ───────────────────────────────────────────────

def connect_mt5(login: int, password: str, server: str) -> bool:
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return False
        ok = mt5.login(login, password=password, server=server)
        if not ok:
            logger.error(f"[MT5] Login failed: {mt5.last_error()}")
        return ok
    except Exception as e:
        logger.error(f"[MT5] initialize error: {e}")
        return False


def get_m5_candles(symbol: str, count: int = 100):
    try:
        import MetaTrader5 as mt5
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df.rename(columns={"time": "timestamp", "tick_volume": "volume"}, inplace=True)
        return df
    except Exception:
        return None


def get_m1_candles(symbol: str, count: int = 30):
    try:
        import MetaTrader5 as mt5
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, count)
        if rates is None or len(rates) == 0:
            return None
        df = pd.DataFrame(rates)
        df.rename(columns={"time": "timestamp", "tick_volume": "volume"}, inplace=True)
        return df
    except Exception:
        return None


def get_last_tick(symbol: str):
    try:
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(symbol)
        return tick
    except Exception:
        return None


def get_session(utc_hour: int) -> str:
    if 0 <= utc_hour < 7:
        return "ASIAN"
    elif 7 <= utc_hour < 12:
        return "LONDON"
    elif 12 <= utc_hour < 16:
        return "OVERLAP"
    else:
        return "NY"


def get_spread_pts(tick, point: float) -> float:
    try:
        return (tick.ask - tick.bid) / point
    except Exception:
        return 15.0


# ── Sub-signal agreement counter ─────────────────────────────

def count_agreement(smc_dir: str, kronos_dir: str, dqn_action: str,
                    ml_dir: str, fused_dir: str) -> int:
    """Count how many of SMC, Kronos, DQN, ML agree with the fused direction."""
    if fused_dir in ("NA", "NONE", None):
        return 0
    signals = [smc_dir, kronos_dir, dqn_action, ml_dir]
    return sum(1 for s in signals if s == fused_dir)


# ── Per-cycle pipeline ────────────────────────────────────────

def run_one_cycle(symbol: str, point: float, mt5_connected: bool,
                  engines: dict) -> dict:
    """Run one full decision cycle. Return a dict of per-field results."""
    now_utc = datetime.now(timezone.utc)
    session = get_session(now_utc.hour)
    record = {
        "timestamp": now_utc.isoformat(),
        "session": session,
        "symbol": symbol,
        "mt5_connected": mt5_connected,
    }

    # ── Fetch data ─────────────────────────────────────────
    candles_m5 = get_m5_candles(symbol) if mt5_connected else None
    candles_m1 = get_m1_candles(symbol) if mt5_connected else None
    tick = get_last_tick(symbol) if mt5_connected else None

    if candles_m5 is None or len(candles_m5) < 30:
        record["error"] = "insufficient_candles"
        return record

    current_price = float(candles_m5["close"].iloc[-1])
    spread_pts    = get_spread_pts(tick, point) if tick else 15.0
    record["price"]      = round(current_price, 2)
    record["spread_pts"] = round(spread_pts, 1)

    # ── Stage 2: Feature Engineering ──────────────────────
    try:
        ff = engines["feature_factory"]
        ticks_list = []
        if tick:
            ticks_list = [{"bid": tick.bid, "ask": tick.ask,
                           "last": tick.last, "time": now_utc.timestamp()}]
        fs = ff.extract(ticks_list, tick)
        # Compute ADX/RSI/ATR directly from candles
        from brain.indicators import ATR, RSI, ADX
        closes_arr = candles_m5["close"].values.astype(float).tolist()
        highs_arr  = candles_m5["high"].values.astype(float).tolist()
        lows_arr   = candles_m5["low"].values.astype(float).tolist()
        atr_val  = ATR(highs_arr, lows_arr, closes_arr, 14)[-1] if len(closes_arr) >= 14 else 1.5
        rsi_val  = RSI(closes_arr, 14)[-1] if len(closes_arr) >= 14 else 50.0
        adx_list = ADX(highs_arr, lows_arr, closes_arr, 14) if len(closes_arr) >= 14 else [20.0]
        adx_val  = adx_list[-1] if adx_list else 20.0
        record["adx"]  = round(float(adx_val), 2)
        record["rsi"]  = round(float(rsi_val),  2)
        record["atr"]  = round(float(atr_val),  4)
    except Exception as e:
        record["feat_error"] = str(e)
        record["adx"] = 20.0
        record["rsi"] = 50.0
        record["atr"] = 1.5

    # ── Stage 3: Statistical Engine ───────────────────────
    try:
        stat = engines["stat_engine"]
        stat_res = stat.analyze(candles_m5["close"].values)
        record["stat_edge"] = round(stat_res.get("edge", 0), 3)
        record["stat_dir"]  = stat_res.get("direction", "NEUTRAL")
    except Exception as e:
        record["stat_error"] = str(e)
        record["stat_edge"]  = 0.0
        record["stat_dir"]   = "NEUTRAL"

    # ── Stage 3b: SMC Engine ──────────────────────────────
    try:
        smc = engines["smc_engine"]
        smc_sig = smc.analyze(candles_m5, current_price=current_price,
                              point=point, symbol=symbol,
                              candles_m1=candles_m1)
        record["smc_grade"] = smc_sig.grade
        record["smc_score"] = smc_sig.confidence
        record["smc_dir"]   = smc_sig.direction
        record["smc_bos"]   = smc_sig.bos_confirmed
        record["smc_choch"] = smc_sig.choch_confirmed
    except Exception as e:
        record["smc_error"] = str(e)
        record["smc_grade"] = "ERR"
        record["smc_score"] = 0
        record["smc_dir"]   = "NONE"

    # ── Stage 3c: MTF Regime ────────────────────────────────────
    try:
        mtf = engines["mtf_analyzer"]
        # analyze() accepts symbol string (MT5 fetch) or a dict of tf DataFrames.
        # Pass a dict keyed by 'M5' so it uses the already-fetched candles.
        mtf_input = {"M5": candles_m5}
        if candles_m1 is not None:
            mtf_input["M1"] = candles_m1
        mtf_res = mtf.analyze(mtf_input)
        if mtf_res:
            record["regime"]        = mtf_res.overall_regime.value if hasattr(mtf_res.overall_regime, "value") else str(mtf_res.overall_regime)
            record["mtf_alignment"] = mtf_res.alignment_score
        else:
            record["regime"]        = "UNKNOWN"
            record["mtf_alignment"] = 0
    except Exception as e:
        record["mtf_error"]     = str(e)
        record["regime"]        = "UNKNOWN"
        record["mtf_alignment"] = 0

    # ── Stage 4: Kronos (Neural Forecaster) ───────────────
    try:
        kronos = engines["kronos"]
        closes = candles_m5["close"].values.astype(float)
        k_res = kronos.predict(closes, horizon=5)
        record["kronos_dir"] = k_res.get("direction", "NONE")
        record["kronos_vol"] = round(k_res.get("predicted_volatility", 0), 3)
    except Exception as e:
        record["kronos_error"] = str(e)
        record["kronos_dir"]   = "NONE"
        record["kronos_vol"]   = 0.0

    # ── Stage 4b: DQN / RL Agent ─────────────────────────
    try:
        rl = engines["rl_agent"]
        state_features = [
            record.get("adx", 20), record.get("rsi", 50), record.get("atr", 1.5),
            spread_pts, record.get("stat_edge", 0),
            record.get("smc_score", 0), record.get("mtf_alignment", 0),
        ]
        rl_out = rl.act(state_features)
        if isinstance(rl_out, dict):
            record["dqn_action"] = rl_out.get("action", "WAIT")
            record["dqn_conf"]   = int(rl_out.get("confidence", 50))
        elif isinstance(rl_out, (list, tuple)) and len(rl_out) >= 2:
            record["dqn_action"] = str(rl_out[0])
            record["dqn_conf"]   = int(rl_out[1])
        else:
            record["dqn_action"] = str(rl_out)
            record["dqn_conf"]   = 50
    except Exception as e:
        record["dqn_error"]  = str(e)
        record["dqn_action"] = "WAIT"
        record["dqn_conf"]   = 0

    # ── Stage 4c: ML Ensemble ────────────────────────────────────
    try:
        ml = engines["ml_ensemble"]
        # MLEnsemble.predict() expects a feature dict (not numpy array).
        # Falls back to rule-based if sklearn models are untrained.
        feat_dict = {
            "adx":        record.get("adx", 20),
            "rsi":        record.get("rsi", 50),
            "atr":        record.get("atr", 1.5),
            "spread":     spread_pts,
            "stat_edge":  record.get("stat_edge", 0),
            "confidence": record.get("smc_score", 0),
            "volatility": record.get("kronos_vol", 0),
            "momentum":   record.get("adx", 20),
        }
        ml_res = ml.predict(feat_dict)
        # predict() returns an MLPrediction dataclass (has .direction, .win_probability)
        if hasattr(ml_res, "direction"):
            record["ml_dir"]  = ml_res.direction
            record["ml_prob"] = round(ml_res.win_probability, 3)
        elif isinstance(ml_res, dict):
            record["ml_dir"]  = ml_res.get("direction", "NEUTRAL")
            record["ml_prob"] = round(ml_res.get("win_probability", 0.5), 3)
        else:
            record["ml_dir"]  = "NEUTRAL"
            record["ml_prob"] = 0.5
    except Exception as e:
        record["ml_error"] = str(e)
        record["ml_dir"]   = "NEUTRAL"
        record["ml_prob"]  = 0.5

    # ── Stage 5: Decision Engine ──────────────────────────
    try:
        decision = engines["brain_decide"](
            candles_m5=candles_m5,
            account={"equity": 10000.0, "balance": 10000.0},
            risk_mgr=None,
            session=session,
            spread=spread_pts,
            point=point,
            symbol=symbol,
            candles_m1=candles_m1,
            current_price=current_price,
        )
        record["fused_dir"]    = decision.direction
        record["fused_conf"]   = decision.confidence
        record["final_action"] = decision.action
        record["action_reason"]= getattr(decision, "reason", "")
    except Exception as e:
        record["brain_error"]  = str(e)
        record["fused_dir"]    = "NA"
        record["fused_conf"]   = 0
        record["final_action"] = "WAIT"
        record["action_reason"]= f"brain_error: {e}"

    # ── Agreement metric ──────────────────────────────────
    record["subsignal_agreement"] = count_agreement(
        smc_dir=record.get("smc_dir", "NONE"),
        kronos_dir=record.get("kronos_dir", "NONE"),
        dqn_action=record.get("dqn_action", "WAIT"),
        ml_dir=record.get("ml_dir", "NEUTRAL"),
        fused_dir=record.get("fused_dir", "NA"),
    )

    return record


# ── Summary report ────────────────────────────────────────────

def print_summary(records: list, symbol: str):
    section(f"SHADOW RUN SUMMARY — {symbol} ({len(records)} cycles)")

    actions    = Counter(r.get("final_action", "WAIT") for r in records)
    fused_dirs = Counter(r.get("fused_dir", "NA") for r in records)
    smc_grades = Counter(r.get("smc_grade", "?") for r in records)
    kronos_dirs= Counter(r.get("kronos_dir", "?") for r in records)
    dqn_acts   = Counter(r.get("dqn_action","?") for r in records)
    ml_dirs    = Counter(r.get("ml_dir", "?") for r in records)
    regimes    = Counter(r.get("regime", "?") for r in records)

    agreements = [r.get("subsignal_agreement", 0) for r in records]
    confs      = [r.get("fused_conf", 0) for r in records]
    smc_scores = [r.get("smc_score", 0) for r in records]

    logger.info(f"{'FINAL ACTION DISTRIBUTION':}")
    for action, cnt in sorted(actions.items(), key=lambda x: -x[1]):
        pct = cnt / len(records) * 100
        logger.info(f"  {action:<8}  {cnt:>4}  ({pct:.1f}%)")

    logger.info(SEP2)
    logger.info("FUSED DIRECTION DISTRIBUTION:")
    for d, cnt in sorted(fused_dirs.items(), key=lambda x: -x[1]):
        logger.info(f"  {d:<6}  {cnt:>4}  ({cnt/len(records)*100:.1f}%)")

    logger.info(SEP2)
    logger.info("SMC GRADE DISTRIBUTION:")
    for g in ["A","B","C","D","F","ERR"]:
        cnt = smc_grades.get(g, 0)
        logger.info(f"  Grade {g}: {cnt:>4}  ({cnt/len(records)*100:.1f}%)")

    logger.info(SEP2)
    logger.info("REGIME DISTRIBUTION:")
    for r, cnt in sorted(regimes.items(), key=lambda x: -x[1]):
        logger.info(f"  {r:<20}  {cnt:>4}  ({cnt/len(records)*100:.1f}%)")

    logger.info(SEP2)
    logger.info("SUB-SIGNAL INDIVIDUAL DIRECTIONS:")
    logger.info(f"  Kronos:  {dict(kronos_dirs)}")
    logger.info(f"  DQN/RL:  {dict(dqn_acts)}")
    logger.info(f"  ML:      {dict(ml_dirs)}")

    logger.info(SEP2)
    if agreements:
        avg_agree = np.mean(agreements)
        full_agree_rate = sum(1 for a in agreements if a == 4) / len(agreements) * 100
        no_agree_rate   = sum(1 for a in agreements if a == 0) / len(agreements) * 100
        logger.info("SUB-SIGNAL AGREEMENT (0=none agree, 4=all agree with fused direction):")
        logger.info(f"  Mean agreement:      {avg_agree:.2f}/4")
        logger.info(f"  Full consensus (4/4):{full_agree_rate:.1f}% of cycles")
        logger.info(f"  Zero agreement (0/4):{no_agree_rate:.1f}% of cycles (high uncertainty)")
        for v in range(5):
            cnt = sum(1 for a in agreements if a == v)
            logger.info(f"  Agreement={v}: {cnt:>4}  ({cnt/len(agreements)*100:.1f}%)")

    if confs:
        logger.info(SEP2)
        logger.info("CONFIDENCE DISTRIBUTION:")
        logger.info(f"  Mean:   {np.mean(confs):.1f}%")
        logger.info(f"  Median: {np.median(confs):.1f}%")
        logger.info(f"  ≥50%:   {sum(1 for c in confs if c >= 50):>4}  ({sum(1 for c in confs if c >= 50)/len(confs)*100:.1f}%)")
        logger.info(f"  ≥70%:   {sum(1 for c in confs if c >= 70):>4}  ({sum(1 for c in confs if c >= 70)/len(confs)*100:.1f}%)")
        logger.info(f"  ≥80%:   {sum(1 for c in confs if c >= 80):>4}  ({sum(1 for c in confs if c >= 80)/len(confs)*100:.1f}%)")

    if smc_scores:
        logger.info(SEP2)
        logger.info("SMC SCORE DISTRIBUTION:")
        logger.info(f"  Mean:  {np.mean(smc_scores):.1f}")
        logger.info(f"  Max:   {np.max(smc_scores)}")
        logger.info(f"  ≥50:   {sum(1 for s in smc_scores if s >= 50)} cycles")

    logger.info(SEP)


# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AEGIS GOLD Shadow Run")
    parser.add_argument("--cycles", type=int, default=50,
                        help="Number of decision cycles to run (default: 50)")
    parser.add_argument("--symbol", type=str, default="XAUUSD")
    parser.add_argument("--interval", type=float, default=5.0,
                        help="Seconds between cycles (default: 5.0)")
    args = parser.parse_args()

    section(f"AEGIS GOLD SHADOW RUN — {args.symbol} × {args.cycles} cycles")
    logger.info("MODE: CHAMPION/CHALLENGER SHADOW — READ-ONLY, NO TRADES PLACED")
    logger.info(SEP2)

    # ── Load .env ────────────────────────────────────────────
    from dotenv import load_dotenv
    load_dotenv()
    import os as _os
    mt5_login    = int(_os.environ.get("MT5_LOGIN", "0"))
    mt5_password = _os.environ.get("MT5_PASSWORD", "")
    mt5_server   = _os.environ.get("MT5_SERVER", "MetaQuotes-Demo")

    # ── Connect MT5 ──────────────────────────────────────────
    mt5_connected = connect_mt5(mt5_login, mt5_password, mt5_server)
    if mt5_connected:
        logger.info(f"✅ MT5 connected to {mt5_server} (login={mt5_login})")
    else:
        logger.warning("⚠️  MT5 not connected — shadow run will use synthetic data fallback")

    # ── Bootstrap engines ────────────────────────────────────
    from brain.feature_pipeline import FeaturePipeline
    from brain.statistical_engine import StatisticalEngine
    from brain.smc_engine import SMCEngine
    from brain.multi_timeframe_analyzer import MultiTimeframeAnalyzer
    from brain.kronos_forecaster import KronosForecaster
    from brain.reinforcement_agent import AegisRLAgent
    from brain.ml_ensemble import MLEnsemble
    from brain.brain import decide as brain_decide
    from modules.feature_factory import FeatureFactory

    logger.info("Initializing engines...")
    point = 0.01 if "XAU" in args.symbol else 0.00001
    engines = {
        "feature_factory": FeatureFactory(point=point),
        "stat_engine":     StatisticalEngine(),
        "smc_engine":      SMCEngine(default_point=0.01, symbol=args.symbol),
        "mtf_analyzer":    MultiTimeframeAnalyzer(),
        "kronos":          KronosForecaster(),
        "rl_agent":        AegisRLAgent(),
        "ml_ensemble":     MLEnsemble(),
        "brain_decide":    brain_decide,
    }
    logger.info("All engines ready.")

    # ── Get point value ──────────────────────────────────────
    point = 0.01 if "XAU" in args.symbol else 0.00001

    # ── Synthetic fallback candles (if MT5 disconnected) ────
    def make_synthetic_m5():
        np.random.seed(int(time.time()) % 1000)
        prices = [2648.0]
        for _ in range(99):
            prices.append(prices[-1] + np.random.uniform(-1.5, 1.5))
        rows = []
        for i, c in enumerate(prices):
            o = prices[i-1] if i > 0 else c
            h = c + abs(np.random.uniform(0, 0.8))
            l = c - abs(np.random.uniform(0, 0.8))
            rows.append({"open": o, "high": h, "low": l, "close": c, "volume": 100})
        return pd.DataFrame(rows)

    # ── Run cycles ───────────────────────────────────────────
    records = []
    out_path = os.path.join(os.path.dirname(__file__), "..", "data", "shadow_run_results.jsonl")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    logger.info(f"Starting {args.cycles} cycles (interval={args.interval}s)...")
    logger.info(SEP2)

    with open(out_path, "w") as fh:
        for cycle in range(1, args.cycles + 1):
            try:
                # Inject synthetic candles if disconnected
                if not mt5_connected:
                    # Patch get_m5_candles to return synthetic
                    import scripts.shadow_run as _self
                    _orig = _self.get_m5_candles
                    _self.get_m5_candles = lambda sym, count=100: make_synthetic_m5()

                rec = run_one_cycle(args.symbol, point, mt5_connected, engines)

                if not mt5_connected:
                    _self.get_m5_candles = _orig

                records.append(rec)
                fh.write(json.dumps(rec) + "\n")
                fh.flush()

                agree = rec.get("subsignal_agreement", 0)
                logger.info(
                    f"[{cycle:>3}/{args.cycles}] {rec.get('timestamp','')[:19]}  "
                    f"price={rec.get('price','?'):<8}  "
                    f"smc={rec.get('smc_grade','?')}/{rec.get('smc_score',0):<3}  "
                    f"regime={rec.get('regime','?'):<18}  "
                    f"kronos={rec.get('kronos_dir','?'):<5}  "
                    f"dqn={rec.get('dqn_action','?'):<5} ({rec.get('dqn_conf',0)}%)  "
                    f"ml={rec.get('ml_dir','?'):<5}  "
                    f"fused={rec.get('fused_dir','?'):<5} {rec.get('fused_conf',0)}%  "
                    f"action={rec.get('final_action','?'):<5}  agree={agree}/4"
                )

            except Exception as e:
                logger.error(f"[{cycle}] Cycle error: {e}")

            if cycle < args.cycles:
                time.sleep(args.interval)

    logger.info(SEP2)
    logger.info(f"Results written to: {os.path.abspath(out_path)}")

    print_summary(records, args.symbol)

    # ── Shutdown MT5 ─────────────────────────────────────────
    if mt5_connected:
        try:
            import MetaTrader5 as mt5
            mt5.shutdown()
            logger.info("MT5 connection closed.")
        except Exception:
            pass


if __name__ == "__main__":
    main()
