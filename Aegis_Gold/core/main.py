
"""
Aegis-Gold v6.0 Ultra — Master Trading Loop
XAUUSD + Local AI Brain. Fully Automated.
"""

import sys
import os
import csv
import time
import asyncio
import logging
import threading
import webbrowser
import gc
import psutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from flask import Flask, jsonify, request
from flask_cors import CORS

# ── Encoding fix ───────────────────────────────────────────────
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ── Path fix ───────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from brain.ABSOLUTE_NEVER_PAUSE_ENFORCER import activate_absolute_never_pause

# ── Project root (BASE_DIR) ────────────────────────────────────
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

import json
from config import settings as cfg
from config.quant_x_config import QX
from modules.mt5_gateway import MT5Gateway
from modules.feature_factory import FeatureFactory
from modules.risk_manager import RiskManager
from modules.telegram_bot import TelegramBot
from brain.brain import decide as brain_decide, verify_direction_integrity
from brain.ai_supervisor import AISupervisor
from brain.position_supervisor import PositionSupervisor
from brain.gpt_brain import GPTBrain
from brain.indicators import ATR
import modules.performance as perf

# Scan interval (seconds) – default 120s
SCAN_INTERVAL = getattr(cfg, 'SCAN_INTERVAL', 120)

# ── Logging ────────────────────────────────────────────────────
import logging.handlers

BASE_DIR = Path(__file__).parent.parent
LOG_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# Rotating file handlers
_formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")

_main_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, "aegis.log"), maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
)
_main_handler.setFormatter(_formatter)

_error_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, "errors.log"), maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
)
_error_handler.setLevel(logging.ERROR)
_error_handler.setFormatter(_formatter)

_trade_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, "trades.log"), maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
)
_trade_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(_formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[_main_handler, _error_handler, _console_handler],
)
logger = logging.getLogger("aegis.main")
trade_logger = logging.getLogger("aegis.trades")
trade_logger.addHandler(_trade_handler)

# ── Journal ────────────────────────────────────────────────────
JOURNAL_PATH = os.path.join(LOG_DIR, "journal.csv")

def _ensure_journal():
    if not os.path.exists(JOURNAL_PATH):
        with open(JOURNAL_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(cfg.JOURNAL_COLUMNS)
    perf.init_db()

def _write_journal(data: dict):
    try:
        with open(JOURNAL_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cfg.JOURNAL_COLUMNS, extrasaction="ignore")
            writer.writerow(data)
    except Exception as exc:
        logger.error("Journal write error: %s", exc)

def log_trade(data: dict):
    try:
        trade_logger.info(json.dumps(data))
        _write_journal(data)
    except Exception as exc:
        logger.error("log_trade error: %s", exc)

def run_llm_analyst_evaluation(sym, decision, spread, session, equity, sym_point, candles_m5, candles_m1, gateway, risk):
    from brain.llm_analyst import LLMTradingAnalyst
    import numpy as np
    
    # 1. Reconstruct model probabilities/directions
    lstm_dir, lstm_prob = 0, 0.5
    trans_dir, trans_prob = 0, 0.5
    
    try:
        from brain.brain import _decide_impl
        # If unified brain is initialized, extract raw model passes
        if hasattr(_decide_impl, "_unified_brain"):
            brain_obj = _decide_impl._unified_brain
            feat_vec = brain_obj.extract_feature_vector(candles_m5, candles_m1, symbol=sym, session=session, spread=spread, point=sym_point)
            import torch
            feat_tensor = torch.from_numpy(feat_vec).unsqueeze(0).to(dtype=torch.float32, device=brain_obj.device)
            
            # Transformer pass
            brain_obj.dueling_dqn.eval()
            with torch.no_grad():
                q_values = brain_obj.dueling_dqn(feat_tensor).cpu().numpy()[0]
                exp_q = np.exp(q_values - np.max(q_values))
                trans_probs = exp_q / np.sum(exp_q)
                trans_idx = int(np.argmax(q_values))
                trans_dir = 1 if trans_idx == 1 else (-1 if trans_idx == 2 else 0)
                trans_prob = float(trans_probs[trans_idx])
                
            # LSTM pass
            brain_obj.actor_critic.eval()
            with torch.no_grad():
                policy_probs, _, _, _ = brain_obj.actor_critic(feat_tensor)
                lstm_probs = policy_probs.cpu().numpy()[0]
                lstm_idx = int(np.argmax(lstm_probs))
                lstm_dir = 1 if lstm_idx == 1 else (-1 if lstm_idx == 2 else 0)
                lstm_prob = float(lstm_probs[lstm_idx])
    except Exception as e:
        logger.debug(f"Failed to extract LSTM/Transformer from PyTorch brain: {e}")
        # Default to decision values
        dir_val = 1 if decision.direction == "BUY" else (-1 if decision.direction == "SELL" else 0)
        lstm_dir, lstm_prob = dir_val, float(decision.confidence) / 100.0
        trans_dir, trans_prob = dir_val, float(decision.confidence) / 100.0

    # RL agent pass
    rl_action, rl_conf = "wait", 0
    try:
        from brain.brain import get_rl_agent
        rl_agent = get_rl_agent()
        if rl_agent:
            # Construct features vector
            cl = [c["close"] for c in candles_m5] if isinstance(candles_m5[-1], dict) else [c[4] for c in candles_m5]
            highs = [c["high"] for c in candles_m5] if isinstance(candles_m5[-1], dict) else [c[2] for c in candles_m5]
            lows = [c["low"] for c in candles_m5] if isinstance(candles_m5[-1], dict) else [c[3] for c in candles_m5]
            from brain.indicators import ATR
            atrs = ATR(highs, lows, cl, 14)
            atr_val = atrs[-1] if atrs else 0.0
            rl_features = [
                float(decision.regime_score or 0.0),
                float(decision.structure_score or 0.0),
                float(decision.entry_score or 0.0),
                float(decision.rsi_val or 50.0),
                float(decision.adx_val or 20.0),
                float(atr_val),
                float(spread or 0.0),
                0.0, 0.0 # wins, losses placeholder
            ]
            rl_action, rl_conf = rl_agent.predict_action(rl_features)
    except Exception as e:
        logger.debug(f"Failed to get RL agent prediction for analyst prompt: {e}")

    # Statistical engine pass
    stat_dir, stat_vol = 0, 0.0
    try:
        from brain.statistical_engine import get_statistical_engine
        closes = [c["close"] for c in candles_m5] if isinstance(candles_m5[-1], dict) else [c[4] for c in candles_m5]
        stat_res = get_statistical_engine().analyze(np.array(closes))
        stat_dir = 1 if stat_res.recommended_direction == "LONG" else (-1 if stat_res.recommended_direction == "SHORT" else 0)
        stat_vol = float(stat_res.mc_std_deviation)
    except Exception as e:
        logger.debug(f"Failed to run Statistical engine for analyst prompt: {e}")

    # Compile prompt data dicts
    quant_signals = {
        "lstm": {"direction": lstm_dir, "probability": round(lstm_prob, 2)},
        "transformer": {"direction": trans_dir, "probability": round(trans_prob, 2)},
        "rl_agent": {"action": rl_action, "expected_value": round(float(rl_conf) / 100.0, 2)},
        "statistical_model": {"direction": stat_dir, "volatility_forecast": round(stat_vol, 2)}
    }
    
    performance_context = {
        "reason_code_historical_win_rate": 58.5, # default
        "profit_factor": 1.85,
        "current_drawdown_pct": 0.0,
        "recent_sharpe": 1.6,
        "ev_per_trade": 2.2
    }
    
    # Try loading from performance DB to populate actuals
    try:
        import sqlite3
        PERF_DB = os.path.join(BASE_DIR, "data", "performance.db")
        if os.path.exists(PERF_DB):
            conn = sqlite3.connect(PERF_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT profit_usd FROM trades WHERE win_loss IS NOT NULL;")
            all_profits = [r[0] for r in cursor.fetchall()]
            if all_profits:
                wins = [p for p in all_profits if p > 0]
                losses = [abs(p) for p in all_profits if p < 0]
                total = len(all_profits)
                win_rate = (len(wins) / total) * 100.0
                pf = sum(wins) / sum(losses) if sum(losses) > 0 else 1.0
                ev = sum(all_profits) / total
                performance_context["reason_code_historical_win_rate"] = round(win_rate, 1)
                performance_context["profit_factor"] = round(pf, 2)
                performance_context["ev_per_trade"] = round(ev, 2)
            conn.close()
    except Exception:
        pass

    try:
        from modules.performance import get_rolling_win_rate
        wr = get_rolling_win_rate(last_n=20)
        performance_context["reason_code_historical_win_rate"] = wr
    except Exception:
        pass

    # Drawdown check
    try:
        dd_val = risk.calculate_current_drawdown(equity)
        performance_context["current_drawdown_pct"] = round(dd_val, 2)
    except Exception:
        pass

    # Volatility regime
    from brain.quant_feature_engine import QuantFeatureEngine
    vol_regime = decision.regime
    try:
        closes = [c["close"] for c in candles_m5] if isinstance(candles_m5[-1], dict) else [c[4] for c in candles_m5]
        qfe = QuantFeatureEngine()
        res_qfe = qfe.analyze(closes)
        vol_regime = f"Hurst:{res_qfe.get('hurst', 0.5):.2f}_Entropy:{res_qfe.get('entropy_shannon', 0.0):.2f}"
    except Exception:
        pass

    market_microstructure = {
        "symbol": sym,
        "volatility_regime": vol_regime,
        "order_flow_imbalance": 0.12 if decision.direction == "BUY" else -0.12,
        "liquidity_score": round(1.0 - (float(spread) / 100.0), 2),
        "current_spread": float(spread),
        "estimated_slippage": 0.5
    }

    structure_context = {
        "htf_bias": "bullish" if decision.direction == "BUY" else "bearish",
        "mtf_zone": "demand" if decision.direction == "BUY" else "supply",
        "ltf_trigger": decision.pattern,
        "smc_context": decision.mode
    }

    risk_state = {
        "max_position_size": decision.lot,
        "cooldown_flag": risk.get_cooldown_left() > 0,
        "daily_trade_count": risk.daily_trades,
        "daily_trade_limit": 50
    }

    # Query LLM analyst
    analyst = LLMTradingAnalyst()
    thought, verdict = analyst.analyze_trade(
        quant_signals=quant_signals,
        performance_context=performance_context,
        market_microstructure=market_microstructure,
        structure_context=structure_context,
        risk_state=risk_state
    )
    return thought, verdict

# ── Shared dashboard state ─────────────────────────────────────
START_TIME = time.time()  # Track VPS bot startup time
state_lock = threading.Lock()
command_queue = []

shared_state = {
    "status": "STARTING",
    "equity": 0.0,
    "price": 0.0,
    "spread": 0,
    "session": "ASIAN",
    "latency": 0.0,
    "daily_trades": 0,
    "daily_pnl": 0.0,
    "total_trades": 0,
    "total_pnl": 0.0,
    "total_wins": 0,
    "total_losses": 0,
    "win_rate": 0.0,
    "profit_factor": 1.0,
    "per_trade_target": 5.0,
    "min_trades_per_day": cfg.MIN_TRADES_PER_DAY,
    "daily_target": 160.0,
    "wins": 0,
    "losses": 0,
    "consecutive_losses": 0,
    "ai_enabled": False,
    "market_structure": "Scanning...",
    "analysis": {
        "reason": "Initializing...",
        "regime": "NA",
        "regime_score": 0,
        "structure": "NA",
        "structure_score": 0,
        "entry_score": 0,
        "confidence": 0,
    }
}
# Scheduler globals
last_scan_time = 0
last_signal_info = {}
symbol_analysis_state = {}


# ── Flask API ──────────────────────────────────────────────────
api = Flask(__name__)
CORS(api)

@api.route('/health')
def health():
    return jsonify({"status": "online", "bot": shared_state["status"]})

@api.route('/heartbeat')
def heartbeat():
    return jsonify({"status": "online", "uptime": get_vps_uptime(), "timestamp": time.time()})

@api.route('/price')
def get_price():
    with state_lock:
        return jsonify({
            "price": shared_state["price"],
            "spread": shared_state["spread"],
            "symbol": cfg.SYMBOL,
            "session": shared_state["session"],
            "time": datetime.now(timezone.utc).strftime("%H:%M:%S"),
        })

# Per-symbol price history for separate charts
_price_history: dict = {"EURUSD": [], "XAUUSD": []}

@api.route('/price/<symbol>')
def get_price_symbol(symbol):
    """Return latest tick + history for a specific symbol."""
    sym = symbol.upper()
    try:
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(sym)
        if tick:
            price = float(tick.bid)
            t = datetime.now(timezone.utc).strftime("%H:%M:%S")
            _price_history.setdefault(sym, [])
            _price_history[sym].append({"time": t, "price": price})
            if len(_price_history[sym]) > 120:
                _price_history[sym] = _price_history[sym][-120:]
            info = mt5.symbol_info(sym)
            point = getattr(info, 'point', 0.00001)
            spread_pts = round((tick.ask - tick.bid) / point) if point > 0 else 0
            return jsonify({
                "symbol": sym,
                "price": price,
                "spread": spread_pts,
                "history": _price_history[sym],
                "time": t,
                "session": shared_state.get("session", "---"),
            })
    except Exception as e:
        pass
    return jsonify({"symbol": sym, "price": 0, "spread": 0, "history": [], "time": "---", "session": "---"})

@api.route('/status')
def get_status():
    with state_lock:
        return jsonify(shared_state.copy())

# ── QUANT AI ADVISORY (read-only, additive) ─────────────────────────────────
# Exposes the observer's last opinion for the dashboard. These endpoints only
# read shared_state; they cannot trigger a decision or an order.
@api.route('/quant_ai')
def get_quant_ai():
    try:
        from core.quant_ai_advisory import snapshot
        with state_lock:
            return jsonify(snapshot(shared_state))
    except Exception as exc:
        return jsonify({"error": str(exc), "advisory_only": True}), 200

@api.route('/quant_ai/health')
def get_quant_ai_health():
    # Never constructs the bridge here: model loading belongs to the observer
    # thread, not a dashboard poll.
    try:
        from core import quant_ai_advisory as qa
        if qa._bridge is None:
            return jsonify({"enabled": qa._flag_on(), "bridge": "not started",
                            "trading_mode": "DEMO", "places_orders": False})
        return jsonify(dict(qa._bridge.health(),
                            enabled=qa._flag_on(), places_orders=False))
    except Exception as exc:
        return jsonify({"enabled": False, "error": str(exc),
                        "trading_mode": "DEMO", "places_orders": False}), 200


@api.route('/trades')
def get_trades():
    if not os.path.exists(JOURNAL_PATH):
        return jsonify([])
    try:
        with open(JOURNAL_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            today_local = datetime.now().strftime("%Y-%m-%d")
            today_rows = []
            all_rows = []
            for r in reader:
                pnl = float(r.get("pnl_usd") or 0)
                row_item = {
                    "id": r.get("trade_id"),
                    "symbol": r.get("symbol", "XAUUSD"),
                    "dir": r.get("direction"),
                    "session": r.get("session"),
                    "entry": float(r.get("entry_price") or 0),
                    "exit": float(r.get("exit_price") or 0) if r.get("exit_price") else None,
                    "pts": float(r.get("pnl_points") or 0),
                    "pnl": pnl,
                    "reason": r.get("exit_reason", ""),
                    "dur": float(r.get("duration_sec") or 0),
                    "spread": int(float(r.get("spread_at_entry") or 0)),
                    "time": r.get("timestamp", "").split("T")[1][:8] if "T" in r.get("timestamp", "") else r.get("timestamp"),
                    "win": pnl >= 0,
                    "ai": r.get("ai_approved", "N/A"),
                }
                all_rows.append(row_item)
                ts = r.get("timestamp", "")
                if ts.startswith(today_utc) or ts.startswith(today_local):
                    today_rows.append(row_item)
            
            # Return today's trades if available; otherwise fall back to last 50 historical trades
            result = today_rows if len(today_rows) > 0 else all_rows[-50:]
            return jsonify(result)
    except Exception as exc:
        logger.error("API /trades error: %s", exc)
        return jsonify([])

@api.route('/positions')
def get_positions():
    try:
        import MetaTrader5 as mt5
        positions = mt5.positions_get()
        if not positions:
            return jsonify([])
        result = []
        for p in positions:
            result.append({
                "ticket": p.ticket,
                "symbol": p.symbol,
                "type": "BUY" if p.type == 0 else "SELL",
                "volume": p.volume,
                "price_open": p.price_open,
                "price_current": p.price_current,
                "profit": p.profit,
                "sl": p.sl,
                "tp": p.tp,
                "magic": p.magic,
            })
        return jsonify(result)
    except Exception as e:
        logger.error("API /positions error: %s", e)
        return jsonify([])

@api.route('/command', methods=['POST'])
def run_command_api():
    cmd = (request.json or {}).get('cmd', '')
    if cmd:
        with state_lock:
            command_queue.append(cmd)
    return jsonify({"success": True})

# New endpoint – scan status
@api.route('/scan')
def scan_info():
    now = datetime.now(timezone.utc)
    next_scan = now + timedelta(seconds=SCAN_INTERVAL) if last_scan_time else None
    return jsonify({
        "last_scan": datetime.utcfromtimestamp(last_scan_time).isoformat() if last_scan_time else None,
        "next_scan": next_scan.isoformat() if next_scan else None,
        "last_signal": last_signal_info,
        "symbol_analysis": symbol_analysis_state
    })

@api.route('/aistate')
def get_ai_state():
    return jsonify(symbol_analysis_state)

# New endpoint – dashboard composite state
@api.route('/dashboard')
def dashboard_data():
    return jsonify({
        "shared_state": shared_state,
        "last_scan": datetime.utcfromtimestamp(last_scan_time).isoformat() if last_scan_time else None,
        "last_signal": last_signal_info
    })

@api.route('/stats')
def get_stats():
    return jsonify(perf.get_performance_stats(days=7) or {})

@api.route('/explain')
def get_explain():
    """Return recent trade decision explanations."""
    try:
        from brain.explainability import get_recent_explanations
        limit = int(request.args.get('limit', 10))
        rows = get_recent_explanations(limit=limit)
        result = []
        for r in rows:
            import json as _json
            result.append({
                "trade_id": r.get("trade_id"),
                "timestamp": r.get("timestamp"),
                "symbol": r.get("symbol"),
                "direction": r.get("direction"),
                "action": r.get("action"),
                "confidence": r.get("confidence"),
                "grade": r.get("grade"),
                "plain_english": r.get("plain_english"),
                "outcome": r.get("outcome"),
                "pnl": r.get("outcome_pnl"),
                "market_context": _json.loads(r.get("context_json", "{}")),
            })
        return jsonify(result)
    except Exception as e:
        logger.error("API /explain error: %s", e)
        return jsonify([])

@api.route('/attribution')
def get_attribution():
    """Return signal-source win rate attribution stats."""
    try:
        from brain.performance_attribution import (
            get_source_win_rates, get_session_win_rates,
            get_regime_win_rates, get_confidence_bucket_win_rates,
            get_aggregated_stats
        )
        return jsonify({
            "by_source":     get_source_win_rates(),
            "by_session":    get_session_win_rates(),
            "by_regime":     get_regime_win_rates(),
            "by_confidence": get_confidence_bucket_win_rates(),
            "overall":       get_aggregated_stats().get("overall", {}),
        })
    except Exception as e:
        logger.error("API /attribution error: %s", e)
        return jsonify({})

@api.route('/strategy')
def get_strategy():
    """Return active strategy profile from the regime switcher."""
    try:
        from brain.regime_switcher import get_strategy_state
        return jsonify(get_strategy_state().get_status())
    except Exception as e:
        logger.error("API /strategy error: %s", e)
        return jsonify({})

@api.route('/ai-health')
def get_ai_health():
    """Return RL model + GPT model file sizes + checkpoint registry."""
    try:
        import json as _json
        models_dir = os.path.join(os.path.dirname(__file__), "..", "models")
        checkpoints_dir = os.path.join(models_dir, "checkpoints")
        registry_path = os.path.join(checkpoints_dir, "model_registry.json")

        registry = {}
        if os.path.exists(registry_path):
            with open(registry_path) as f:
                registry = _json.load(f)

        rl_model_size = 0
        rl_path = os.path.join(models_dir, "aegis_rl.pt")
        if os.path.exists(rl_path):
            rl_model_size = os.path.getsize(rl_path)

        gpt_model_size = 0
        gpt_path = os.path.join(models_dir, "aegis_gpt.pt")
        if os.path.exists(gpt_path):
            gpt_model_size = os.path.getsize(gpt_path)

        return jsonify({
            "rl_model_exists": os.path.exists(rl_path),
            "rl_model_size_kb": round(rl_model_size / 1024, 1),
            "gpt_model_exists": os.path.exists(gpt_path),
            "gpt_model_size_kb": round(gpt_model_size / 1024, 1),
            "active_version": registry.get("active_version"),
            "total_checkpoints": len(registry.get("checkpoints", [])),
            "last_checkpoint": registry.get("checkpoints", [{}])[-1] if registry.get("checkpoints") else None,
        })
    except Exception as e:
        logger.error("API /ai-health error: %s", e)
        return jsonify({})

@api.route('/arena')
def get_arena_api():
    """Champion/Challenger arena status."""
    try:
        from brain.champion_challenger import get_arena
        return jsonify(get_arena().get_status())
    except Exception as e:
        logger.error("API /arena error: %s", e)
        return jsonify({})

@api.route('/calibration')
def get_calibration_api():
    """Confidence calibration status — Brier score + reliability curve."""
    try:
        from brain.calibration import get_calibration_monitor
        return jsonify(get_calibration_monitor().get_status())
    except Exception as e:
        logger.error("API /calibration error: %s", e)
        return jsonify({})

@api.route('/calibration/report')
def get_calibration_report_api():
    """
    Chart-ready reliability diagram data.
    Returns list of {band, stated_midpoint, actual_win_rate, count, deviation_pct, miscalibrated}.
    Also includes summary metrics: brier_score, ece, threshold_penalty.
    """
    try:
        from brain.calibration import get_calibration_monitor
        from brain.attribution_writer import row_count
        mon   = get_calibration_monitor()
        state = mon.get_status()
        return jsonify({
            "diagram":          mon.reliability_diagram_data(),
            "brier_score":      state.get("brier_score"),
            "ece":              state.get("ece"),
            "threshold_penalty": state.get("threshold_penalty", 0),
            "calibration_ok":   state.get("calibration_ok", True),
            "miscalibrated_buckets": state.get("miscalibrated_buckets", []),
            "total_trades_analyzed": state.get("total_trades_analyzed", 0),
            "attribution_rows": row_count(),
            "last_evaluated":   state.get("last_evaluated"),
        })
    except Exception as e:
        logger.error("API /calibration/report error: %s", e)
        return jsonify({"error": str(e)})

@api.route('/explain/<trade_id>')
def get_explain_by_trade(trade_id: str):
    """
    Per-trade explanation lookup.
    Returns the full explanation dict for a specific trade_id,
    enriched with shap_top3 if the shap_explainability flag is enabled.
    """
    try:
        from brain.explainability import get_explanation_for_trade
        import json as _json
        row = get_explanation_for_trade(trade_id)
        if not row:
            return jsonify({"error": f"No explanation found for trade_id={trade_id}"}), 404
        result = {
            "trade_id":    row.get("trade_id"),
            "timestamp":   row.get("timestamp"),
            "symbol":      row.get("symbol"),
            "direction":   row.get("direction"),
            "action":      row.get("action"),
            "confidence":  row.get("confidence"),
            "grade":       row.get("grade"),
            "plain_english": row.get("plain_english"),
            "outcome":     row.get("outcome"),
            "pnl":         row.get("outcome_pnl"),
            "market_context": _json.loads(row.get("context_json") or "{}"),
            "signal_sources": _json.loads(row.get("signal_json") or "{}"),
            "shap_top3":   [],   # populated by Module 6 when flag enabled
        }
        # Module 6: enrich with top-3 permutation importance if available
        try:
            from config.quant_x_config import QX
            if QX.flag("shap_explainability"):
                from brain.explainability import compute_shap_top3
                ctx = result["market_context"]
                sig = result["signal_sources"]
                result["shap_top3"] = compute_shap_top3(ctx, sig, result["confidence"])
        except Exception as _shap_ex:
            logger.debug("SHAP enrichment failed for trade %s: %s", trade_id, _shap_ex)
        return jsonify(result)
    except Exception as e:
        logger.error("API /explain/<trade_id> error: %s", e)
        return jsonify({"error": str(e)}), 500

@api.route('/backtest')
def get_backtest_api():
    """
    Returns the most recent walk-forward backtest report.
    Read-only — never triggers retraining.
    Run `python -m brain.backtest_runner` to refresh.
    """
    try:
        report_path = os.path.join(BASE_DIR, "data", "backtest_report.json")
        if not os.path.exists(report_path):
            return jsonify({
                "status": "no_report",
                "message": "Run `python -m brain.backtest_runner` to generate the backtest report."
            })
        with open(report_path) as f:
            return jsonify(json.load(f))
    except Exception as e:
        logger.error("API /backtest error: %s", e)
        return jsonify({"error": str(e)})

@api.route('/drift')
def get_drift_api():
    """Feature drift monitor status — KS statistics per feature."""
    try:
        from brain.drift_monitor import get_drift_monitor
        return jsonify(get_drift_monitor().get_status())
    except Exception as e:
        logger.error("API /drift error: %s", e)
        return jsonify({})

@api.route('/session')
def get_session_api():
    return jsonify({"session": get_session_details()})

@api.route('/streak')
def get_streak_api():
    return jsonify(load_streak_state())

@api.route('/scalp')
def set_scalp_mode():
    mode = request.args.get('mode', 'auto')
    cfg.SCALP_MODE_CONTROL = mode
    return jsonify({"success": True, "mode": mode})

@api.route('/risk')
def set_risk():
    try:
        val = float(request.args.get('val', getattr(cfg, 'BASE_RISK_PCT', 0.005)))
        cfg.BASE_RISK_PCT = val
        return jsonify({"success": True, "base_risk_pct": val})
    except ValueError:
        return jsonify({"success": False, "error": "Invalid value"})

def get_vps_uptime() -> str:
    diff = time.time() - START_TIME
    hours = int(diff // 3600)
    minutes = int((diff % 3600) // 60)
    seconds = int(diff % 60)
    return f"{hours}h {minutes}m {seconds}s"

def get_health_status(gateway) -> str:
    import psutil
    proc = psutil.Process()
    mem_mb = proc.memory_info().rss / (1024 * 1024)
    cpu_pct = psutil.cpu_percent()
    conn_status = "✅ CONNECTED" if gateway.is_connected() else "❌ DISCONNECTED"
    return (
        f"💻 <b>AEGIS VPS HEALTH STATUS</b>\n"
        f"─────────────────────────\n"
        f"MT5 Gateway : {conn_status}\n"
        f"VPS CPU     : {cpu_pct:.1f}%\n"
        f"Bot Memory  : {mem_mb:.1f} MB\n"
        f"Uptime      : {get_vps_uptime()}\n"
    )

def get_open_positions_report(gateway) -> str:
    positions = gateway.get_open_positions()
    if not positions:
        return "📭 <b>Active Positions: None</b>"
    
    lines = ["📂 <b>ACTIVE OPEN POSITIONS</b>\n─────────────────────────"]
    for p in positions:
        direction = "BUY" if p.type == 0 else "SELL"
        lines.append(
            f"Ticket: <code>#{p.ticket}</code>\n"
            f"Symbol: {p.symbol}\n"
            f"Direction: <b>{direction}</b>\n"
            f"Lot Size: {p.volume}\n"
            f"Open Price: {p.price_open:.5f}\n"
            f"Current Price: {p.price_current:.5f}\n"
            f"Profit: <b>${p.profit:+.2f}</b>\n"
            f"─────────────────────────"
        )
    return "\n".join(lines)

def get_mt5_status_report(gateway) -> str:
    import MetaTrader5 as mt5
    is_connected = gateway.is_connected()
    status = "✅ CONNECTED" if is_connected else "❌ DISCONNECTED"
    
    lines = [
        f"📶 <b>METATRADER 5 INFRASTRUCTURE</b>\n"
        f"─────────────────────────\n"
        f"Connection  : {status}\n"
        f"Login       : <code>{cfg.MT5_LOGIN}</code>\n"
        f"Server      : {cfg.MT5_SERVER}\n"
    ]
    
    if is_connected:
        term = mt5.terminal_info()
        if term:
            lines.append(f"AlgoTrading : {'✅ ON' if term.trade_allowed else '❌ OFF'}")
            lines.append(f"Trading Live: {'✅ YES' if getattr(term, 'trade_live', False) else 'DEMO'}")
        
        acct = gateway.get_account_info()
        if acct:
            lines.append(f"Balance     : ${acct.get('balance', 0.0):.2f}")
            lines.append(f"Equity      : ${acct.get('equity', 0.0):.2f}")
            lines.append(f"Free Margin : ${acct.get('margin_free', 0.0):.2f}")
        
        sym = cfg.SYMBOL
        lines.append(f"Symbol      : {sym}")
        data = gateway.symbols_data.get(sym)
        if data:
            lines.append(f"Point Size  : {data.get('point', 0.00001)}")
    
    return "\n".join(lines)

def get_custom_status_report(gateway, risk) -> str:
    current_equity = shared_state["equity"]
    profit = current_equity - risk.start_equity
    sign   = "+" if profit >= 0 else ""
    status = shared_state["status"]
    
    is_connected = gateway.is_connected()
    mt5_status = "✅ CONNECTED" if is_connected else "❌ DISCONNECTED"
    
    positions = gateway.get_open_positions()
    pos_count = len(positions)
    
    spread = shared_state["spread"]
    ai_conf = shared_state["analysis"]["confidence"]
    ai_status = "ENABLED" if cfg.USE_AI_SUPERVISOR else "DISABLED"
    
    # Multi-symbol confidence display
    symbol_status = ""
    for sym in ["EURUSD", "XAUUSD"]:
        if sym in symbol_analysis_state:
            sym_data = symbol_analysis_state[sym]
            conf = sym_data.get("confidence", 0)
            regime = sym_data.get("regime", "NA")
            reason_short = sym_data.get("reason", "")[:30] + "..." if len(sym_data.get("reason", "")) > 30 else sym_data.get("reason", "")
            
            # Status emoji based on confidence
            if conf >= 60:
                conf_emoji = "🟢"  # Green for tradeable
            elif conf >= 40:
                conf_emoji = "🟡"  # Yellow for moderate
            else:
                conf_emoji = "🔴"  # Red for low
                
            symbol_status += f"{conf_emoji} {sym}: {conf}% ({regime}) - {reason_short}\n"
    
    return (
        f"📊 <b>AEGIS SCALPING MODE STATUS</b>\n"
        f"─────────────────────────\n"
        f"Engine Status: <b>{status}</b>\n"
        f"MT5 Gateway  : {mt5_status}\n"
        f"VPS Uptime   : {get_vps_uptime()}\n"
        f"─────────────────────────\n"
        f"Equity       : ${current_equity:.2f}\n"
        f"PnL Today    : <b>{sign}${profit:.2f}</b>\n"
        f"Trades       : {risk.daily_trades} ({risk.today_wins}W/{risk.today_losses}L)\n"
        f"Consec Losses: {risk.consecutive_losses}/{cfg.MAX_CONSECUTIVE_LOSSES}\n"
        f"─────────────────────────\n"
        f"<b>🎯 SYMBOL CONFIDENCE (60%+ = TRADE):</b>\n"
        f"{symbol_status}"
        f"─────────────────────────\n"
        f"Current Spread: {spread:.0f} pts\n"
        f"AI Supervisor: {ai_status}\n"
        f"Active Pos   : {pos_count} position(s)\n"
    )

def run_self_diagnosis(gateway, risk_mgr, ai_supervisor, telegram) -> str:
    """Run an active diagnostic on trading bot systems and report to Telegram."""
    logger.info("Executing active self-diagnosis...")
    report = []
    report.append("🔍 <b>AEGIS SYSTEM SELF-DIAGNOSIS</b>")
    report.append(f"Time: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    
    # 1. MT5 Terminal Status
    is_connected = gateway.is_connected()
    if not is_connected:
        report.append("⚠️ MT5 Disconnected. Attempting auto-reconnect...")
        gateway.reconnect()
        time.sleep(3)
        is_connected = gateway.is_connected()
        if not is_connected:
            report.append("❌ Reconnection failed. Strategy/Terminal is frozen! Restarting process via Watchdog...")
            final_text = "\n".join(report)
            telegram.send(final_text)
            logger.critical("Self-diagnosis: MT5 disconnected and reconnect failed. Exiting process.")
            time.sleep(1)
            sys.exit(-999)
        else:
            report.append("✅ Reconnection successful!")
    else:
        report.append("MT5 Connection: ✅ YES")
        
    # 2. Account info and AlgoTrading
    import MetaTrader5 as mt5
    terminal_info = mt5.terminal_info()
    if terminal_info:
        report.append(f"AlgoTrading Active: {'✅ YES' if terminal_info.trade_allowed else '❌ NO (Turn AlgoTrading ON!)'}")
        report.append(f"MT5 Term Type: {'LIVE' if getattr(terminal_info, 'trade_live', False) else 'DEMO/TEST'}")
    else:
        report.append("AlgoTrading Active: ❌ Failed to fetch terminal info")
        
    acct = gateway.get_account_info()
    if acct:
        report.append(f"Account Balance: ${acct.get('balance', 0):.2f}")
    else:
        report.append("Account Info: ❌ Failed to fetch account info! Strategy is frozen! Restarting process...")
        final_text = "\n".join(report)
        telegram.send(final_text)
        logger.critical("Self-diagnosis: Account info is missing. Exiting process.")
        time.sleep(1)
        sys.exit(-999)
        
    # 3. Symbol active status
    sym = cfg.SYMBOL
    mt5.symbol_select(sym, True)
    sym_info = mt5.symbol_info(sym)
    if sym_info:
        report.append(f"Symbol {sym}: ✅ Active & Available")
        tick = gateway.get_current_tick(sym)
        if tick:
            spread = (tick.ask - tick.bid) / sym_info.point if sym_info.point > 0 else 0
            report.append(f"Spread: {spread:.0f} points (Limit: {cfg.SPREAD_LIMITS.get('LONDON', 20)} pts)")
        else:
            report.append("Spread: ❌ Failed to retrieve price tick")
    else:
        report.append(f"Symbol {sym}: ❌ Not found / Inactive in terminal")
        
    # 4. Session status
    from modules.feature_factory import FeatureFactory
    # Fetch ticks to extract session
    ticks = gateway.get_ticks(sym, 2)
    if ticks is not None and len(ticks) > 0:
        point = sym_info.point if sym_info else 0.00001
        factory = FeatureFactory(point)
        features = factory.extract(ticks, ticks[-1])
        report.append(f"Session: {features.session} (Allowed: {'✅ YES' if risk_mgr.can_trade(features.session) else '❌ NO'})")
    else:
        report.append("Session Check: ❌ Could not extract market features")
        
    # 5. AI Supervisor Status
    ai_status = "ENABLED" if ai_supervisor.enabled else "DISABLED"
    report.append(f"AI Brain (Local OMEGA): {ai_status}")
        
    # 6. VPS Resource metrics
    import psutil
    proc = psutil.Process()
    mem_mb = proc.memory_info().rss / (1024 * 1024)
    cpu_pct = psutil.cpu_percent()
    report.append(f"VPS CPU: {cpu_pct:.1f}% | Bot RSS: {mem_mb:.1f} MB")
    
    final_text = "\n".join(report)
    logger.info("Self-diagnosis report generated successfully.")
    telegram.send(final_text)
    return final_text


LADDER_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "position_ladder.json"))
STREAK_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "streak_state.json"))

def load_ladder():
    if not os.path.exists(LADDER_FILE):
        return {}
    try:
        with open(LADDER_FILE, "r") as f:
            data = json.load(f)
            return {int(k): v for k, v in data.items()}
    except Exception:
        return {}

def save_ladder(ladder):
    try:
        os.makedirs(os.path.dirname(LADDER_FILE), exist_ok=True)
        with open(LADDER_FILE, "w") as f:
            json.dump({str(k): v for k, v in ladder.items()}, f)
    except Exception as e:
        logger.error("Error saving ladder: %s", e)

def load_streak_state():
    if not os.path.exists(STREAK_FILE):
        return {
            "consecutive_losses": 0,
            "consecutive_wins": 0,
            "last_trade_result": None,
            "cooldown_until": None
        }
    try:
        with open(STREAK_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "consecutive_losses": 0,
            "consecutive_wins": 0,
            "last_trade_result": None,
            "cooldown_until": None
        }

def save_streak_state(state):
    try:
        os.makedirs(os.path.dirname(STREAK_FILE), exist_ok=True)
        with open(STREAK_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error("Error saving streak state: %s", e)

def check_cooldown() -> bool:
    state = load_streak_state()
    cooldown_until = state.get("cooldown_until")
    if cooldown_until:
        if time.time() < cooldown_until:
            return False
    return True

def get_session_details() -> str:
    hour = datetime.now(timezone.utc).hour
    sessions = []
    if 0 <= hour < 8: sessions.append("ASIAN")
    if 7 <= hour < 16: sessions.append("LONDON")
    if 12 <= hour < 21: sessions.append("NY")
    
    current = ", ".join(sessions) if sessions else "NONE"
    
    if 7 <= hour < 21:
        status = "ACTIVE SESSION HOURS"
        hours_left = 21 - hour
        time_msg = f"{hours_left} hours left in NY/London session"
    else:
        status = "INACTIVE SESSION HOURS"
        if hour < 7:
            hours_until = 7 - hour
        else:
            hours_until = (24 - hour) + 7
        time_msg = f"London opens in {hours_until} hours"
        
    return f"🌐 <b>Session Status:</b> {status}\n• Current Session(s): {current}\n• UTC Hour: {hour:02d}:00\n• Next phase: {time_msg}"

def get_streak_report() -> str:
    state = load_streak_state()
    cooldown = "ACTIVE" if state.get("cooldown_until") and time.time() < state["cooldown_until"] else "INACTIVE"
    cooldown_left = ""
    if cooldown == "ACTIVE":
        left_sec = int(state["cooldown_until"] - time.time())
        cooldown_left = f" (ends in {left_sec // 60}m {left_sec % 60}s)"
        
    return (
        f"🔥 <b>STREAK STATUS REPORT</b>\n"
        f"─────────────────────────\n"
        f"• Consecutive Wins   : <code>{state['consecutive_wins']}</code>\n"
        f"• Consecutive Losses : <code>{state['consecutive_losses']}</code>\n"
        f"• Last Trade Result  : <code>{state['last_trade_result']}</code>\n"
        f"• Cooldown Status    : <b>{cooldown}</b>{cooldown_left}"
    )


def get_atr_sl_estimate_pts(symbol: str, gateway) -> float:
    try:
        import MetaTrader5 as mt5
        # Fetch M5 candles (we can fetch last 30 rates)
        candles = gateway.get_candles_m5(symbol, 30)
        if candles is None or len(candles) < 14:
            return 20.0  # safe default points
        
        try:
            highs_list  = [c['high']  for c in candles]
            lows_list   = [c['low']   for c in candles]
            closes_list = [c['close'] for c in candles]
        except TypeError:
            highs_list  = [c[2] for c in candles]
            lows_list   = [c[3] for c in candles]
            closes_list = [c[4] for c in candles]

        atr_series = ATR(highs_list, lows_list, closes_list, 14)
        atr_price  = atr_series[-1] if atr_series else 0.0
        
        sym_info = gateway.symbols_data.get(symbol, {})
        point = sym_info.get("point", 0.00001)
        atr_points = (atr_price / point) if point > 0 else 0.0
        
        atr_sl_mult = getattr(cfg, 'ATR_SL_MULTIPLIER', 1.0)
        return max(5.0, atr_points * atr_sl_mult)
    except Exception as exc:
        logger.error(f"Error calculating dynamic ATR SL for {symbol}: {exc}")
        return 20.0


async def process_closed_trade(ticket: int, symbol: str, gateway, risk, ai_supervisor, telegram, loop, executor):
    """Fetch trade outcome from MetaTrader 5 deal history, log closed trade to journal, update adaptive learning & risk, and alert Telegram."""
    import MetaTrader5 as mt5
    import csv
    
    logger.info(f"Processing closed trade #{ticket} for {symbol}...")
    
    def _fetch_history():
        # Make sure MT5 is initialized
        if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
            return None
        return mt5.history_deals_get(position=ticket)
        
    deals = await loop.run_in_executor(executor, _fetch_history)
    
    exit_price = 0.0
    pnl_usd = 0.0
    pnl_points = 0.0
    duration_sec = 0.0
    lot = 0.10
    direction = "BUY"
    exit_reason = "TargetProfit"
    
    if deals:
        # Sort deals by time
        deals = sorted(deals, key=lambda d: d.time)
        entry_deal = None
        exit_deal = None
        for d in deals:
            if d.entry == mt5.DEAL_ENTRY_IN:
                entry_deal = d
            elif d.entry == mt5.DEAL_ENTRY_OUT:
                exit_deal = d
                
        if entry_deal:
            lot = entry_deal.volume
            direction = "BUY" if entry_deal.type == mt5.ORDER_TYPE_BUY else "SELL"
            
        if exit_deal:
            exit_price = exit_deal.price
            pnl_usd = sum(d.profit for d in deals) + sum(d.commission for d in deals) + sum(d.swap for d in deals)
            duration_sec = max(0.1, float(exit_deal.time - (entry_deal.time if entry_deal else exit_deal.time)))
            exit_reason = exit_deal.comment if exit_deal.comment else "TargetProfit"
            
            # Calculate points
            info = mt5.symbol_info(symbol)
            if info and info.point > 0:
                if direction == "BUY":
                    pnl_points = (exit_price - entry_deal.price) / info.point
                else:
                    pnl_points = (entry_deal.price - exit_price) / info.point
            else:
                pnl_points = 0.0
    else:
        logger.warning(f"No history deals found for position #{ticket} yet.")

    # Update journal.csv or demo_journal.csv
    def _update_journal():
        if not os.path.exists(JOURNAL_PATH):
            return
        try:
            rows = []
            updated = False
            with open(JOURNAL_PATH, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row.get("trade_id") == str(ticket):
                        row["exit_price"] = f"{exit_price:.5f}"
                        row["pnl_points"] = f"{pnl_points:.1f}"
                        row["pnl_usd"] = f"{pnl_usd:.2f}"
                        row["duration_sec"] = f"{duration_sec:.1f}"
                        row["exit_reason"] = exit_reason
                        updated = True
                    rows.append(row)
                    
            if updated:
                with open(JOURNAL_PATH, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                logger.info(f"Journal updated for closed trade #{ticket}")
        except Exception as ex:
            logger.error(f"Error updating journal for closed trade #{ticket}: {ex}")
            
    await loop.run_in_executor(executor, _update_journal)
    
    # Record trade outcome in AdaptiveLearning (Self-thinking bot logic)
    if hasattr(ai_supervisor, 'adaptive_learning'):
        ai_supervisor.adaptive_learning.record_trade("WIN" if pnl_usd >= 0 else "LOSS")
        
    # Update RiskManager daily/consecutive stats
    risk.on_trade_close(pnl_points)
    
    perf.log_trade_close(ticket, exit_price, pnl_usd, pnl_points, duration_sec, 1 if "partial" in exit_reason.lower() else 0, 1 if pnl_usd >= 0 else -1)
    
    win_rate = perf.get_rolling_win_rate(last_n=20)
    is_ultra_pro = getattr(cfg, 'SCALP_MODE_CONTROL', 'off') == 'ultra_pro'
    if not is_ultra_pro and win_rate < 45.0 and risk.daily_trades > 5:
        logger.warning(f"Win rate fell to {win_rate:.1f}%. Auto-pausing bot.")
        telegram.send(f"⚠️ <b>[AUTO-PAUSE]</b> Win rate dropped to {win_rate:.1f}% (below 45%). Bot paused for safety.")
        risk.manual_pause = True
        
    streak_state = load_streak_state()
    if pnl_usd > 0.05:
        outcome = "WIN"
        cooldown_duration = getattr(cfg, 'COOLDOWN_WIN_SEC', 60)
        streak_state["consecutive_wins"] += 1
        streak_state["consecutive_losses"] = 0
    elif pnl_usd < -0.05:
        outcome = "LOSS"
        cooldown_duration = getattr(cfg, 'COOLDOWN_LOSS_SEC', 120)
        streak_state["consecutive_losses"] += 1
        streak_state["consecutive_wins"] = 0
    else:
        outcome = "BREAKEVEN"
        cooldown_duration = getattr(cfg, 'COOLDOWN_BE_SEC', 60)
        streak_state["consecutive_losses"] = 0
        streak_state["consecutive_wins"] = 0

    streak_state["last_trade_result"] = outcome
    streak_state["cooldown_until"] = time.time() + cooldown_duration
    save_streak_state(streak_state)
    logger.info(f"Closed trade #{ticket} result: {outcome}. Set cooldown for {cooldown_duration}s until {streak_state['cooldown_until']}")

    # ── MODULE 1: Attribution Write + Calibration Evaluation ───────────────
    # Pull signal metadata from the last explanation record for this ticket
    _signal_confidence = 50.0
    _signal_regime     = "UNKNOWN"
    _signal_session    = shared_state.get("session", "UNKNOWN")
    _signal_source     = "SCALP"
    _signal_adx        = None
    _signal_rsi        = None
    _signal_spread     = None
    _ctx = {}
    try:
        from brain.explainability import get_explanation_for_trade
        _expl = get_explanation_for_trade(str(ticket))
        if _expl:
            _signal_confidence = float(_expl.get("confidence") or 50)
            import json as _json_expl
            _ctx = _json_expl.loads(_expl.get("context_json") or "{}")
            _signal_regime  = _ctx.get("regime", "UNKNOWN")
            _signal_session = _ctx.get("session", _signal_session)
            _signal_adx     = _ctx.get("adx")
            _signal_rsi     = _ctx.get("rsi")
            _signal_spread  = _ctx.get("spread")
            _sig_src = _json_expl.loads(_expl.get("signal_json") or "{}")
            _signal_source  = "SMC" if _sig_src.get("SMC", {}).get("passed") else "SCALP"
    except Exception as _expl_ex:
        logger.debug("[MODULE1] Could not fetch explanation for ticket %s: %s", ticket, _expl_ex)

    # Compute realised R:R (positive for wins, negative for losses)
    _rr_multiple = None
    try:
        _sl_pts = abs(float(symbol_analysis_state.get(symbol, {}).get("sl_points", 0) or 0))
        if _sl_pts > 0 and pnl_points != 0:
            _rr_multiple = round(pnl_points / _sl_pts, 3)
    except Exception:
        pass

    # Write attribution row
    try:
        from brain.attribution_writer import write_attribution
        
        _historical_edge = "neutral"
        _microstructure_quality = "clean"
        try:
            _historical_edge = _ctx.get("historical_edge", "neutral")
            _microstructure_quality = _ctx.get("microstructure_quality", "clean")
        except Exception:
            pass

        write_attribution(
            ticket=ticket,
            confidence=_signal_confidence,
            outcome=outcome,
            pnl_usd=pnl_usd,
            regime=_signal_regime,
            session=_signal_session,
            signal_source=_signal_source,
            rr_multiple=_rr_multiple,
            adx=_signal_adx,
            rsi=_signal_rsi,
            spread=_signal_spread,
            historical_edge=_historical_edge,
            microstructure_quality=_microstructure_quality
        )
    except Exception as _aw_ex:
        logger.error("[MODULE1] Attribution write error for ticket %s: %s", ticket, _aw_ex)

    # Update explainability outcome
    try:
        from brain.explainability import update_outcome
        update_outcome(str(ticket), outcome, pnl_usd)
    except Exception as _uo_ex:
        logger.debug("[MODULE1] update_outcome error: %s", _uo_ex)

    # Evaluate calibration every 50 closed trades
    try:
        from brain.attribution_writer import row_count
        from brain.calibration import get_calibration_monitor
        _attr_count = row_count()
        if _attr_count >= 20 and _attr_count % 50 == 0:
            _cal_state = get_calibration_monitor().evaluate()
            logger.info(
                "[MODULE1] Calibration eval #%d: Brier=%.4f Penalty=+%dpts",
                _cal_state.get("evaluation_count", 0),
                _cal_state.get("brier_score") or 0.0,
                _cal_state.get("threshold_penalty", 0),
            )
    except Exception as _cal_ex:
        logger.error("[MODULE1] Calibration evaluate error: %s", _cal_ex)

    # ── MODULE 2: Arena Champion / Challenger Recording ─────────────────────
    try:
        from brain.champion_challenger import get_arena
        _arena_mgr = get_arena()

        # Check if challenger had a shadow decision for this ticket
        import json as _json_arena
        _is_challenger_trade = False
        _chal_dec_path = os.path.join(BASE_DIR, "data", "challenger_decisions_by_ticket.json")
        if os.path.exists(_chal_dec_path):
            with open(_chal_dec_path) as _cf:
                _chal_decisions = _json_arena.load(_cf)
            if _chal_decisions.get(str(ticket)):
                _is_challenger_trade = True

        if _is_challenger_trade:
            # Route to Challenger only
            _arena_mgr.record_challenger_shadow(outcome, pnl_usd, _rr_multiple or 0.0)
            logger.debug("[MODULE2] Recorded challenger actual outcome for ticket %s: %s", ticket, outcome)
        else:
            # Route to Champion
            _arena_mgr.record_champion_outcome(outcome, pnl_usd, _rr_multiple or 0.0)
            logger.debug("[MODULE2] Recorded champion outcome for ticket %s: %s", ticket, outcome)
    except Exception as _arena_ex:
        logger.error("[MODULE2] Arena recording error for ticket %s: %s", ticket, _arena_ex)

    # Send Telegram close alert
    telegram.send_trade_close(
        pnl_pts=pnl_points,
        pnl_usd=pnl_usd,
        duration=duration_sec,
        reason=exit_reason,
        slippage=0.0,
        risk_status=risk.get_status_dict()
    )


# ── Main Async Loop ────────────────────────────────────────────

async def main_loop():
    """The master async trading loop."""
    executor = ThreadPoolExecutor(max_workers=4)
    loop = asyncio.get_event_loop()
    global last_scan_time

    # Init subsystems
    gateway = MT5Gateway()
    telegram = TelegramBot()
    risk = RiskManager(gateway)
    ai_supervisor = AISupervisor()
    position_supervisor = PositionSupervisor(gateway, risk)
    gpt_brain = GPTBrain() if cfg.USE_GPT_BRAIN else None

    gateway.set_telegram_callback(telegram.send)
    risk.set_telegram_callback(telegram.send)

    logger.info("Aegis-Gold v6.0 Ultra starting...")
    mode = "DEMO" if cfg.DEMO_MODE else "LIVE"

    # Connect to MT5
    connected = await loop.run_in_executor(executor, gateway.initialize)
    if not connected:
        logger.critical("MT5 connection failed. Exiting.")
        sys.exit(1)

    # Init FeatureFactory with symbol point
    sym = cfg.SYMBOL
    point = gateway.symbols_data.get(sym, {}).get("point", 0.01)
    factory = FeatureFactory(point)

    # Telegram callbacks
    telegram.on_pause   = lambda: setattr(risk, 'manual_pause', True)
    telegram.on_resume  = risk.manual_resume
    telegram.on_close_all = gateway.close_all_positions
    telegram.on_stop_today = lambda: setattr(risk, 'stop_today', True)
    telegram.get_status = lambda: get_custom_status_report(gateway, risk)
    telegram.get_equity = lambda: f"Equity: ${shared_state['equity']:.2f}"
    telegram.get_session_info = lambda: f"Session: {shared_state['session']} | AI: {'ON' if ai_supervisor.enabled else 'OFF'}"
    
    # New Advanced DevOps callbacks
    telegram.on_diagnose = lambda: run_self_diagnosis(gateway, risk, ai_supervisor, telegram)
    telegram.on_reconnect = gateway.reconnect
    telegram.on_health = lambda: get_health_status(gateway)
    telegram.on_open_positions = lambda: get_open_positions_report(gateway)
    telegram.get_mt5_status = lambda: get_mt5_status_report(gateway)
    telegram.get_profit_loss = lambda: shared_state["daily_pnl"]
    telegram.on_lot_override = risk.override_lot

    # Start Telegram polling only if the VPS Control Daemon is not running to avoid 409 conflicts
    daemon_lock = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "daemon.lock"))
    if not os.path.exists(daemon_lock):
        logger.info("Starting Telegram bot polling loop (Standalone Mode)...")
        telegram.start_polling()
    else:
        logger.info("Telegram polling skipped (Daemon Mode active)...")
    
    # Get initial equity
    acct = await loop.run_in_executor(executor, gateway.get_account_info)
    if acct:
        risk.init_daily(acct["equity"])
    risk.manual_resume()  # Ensure system starts ACTIVE with all legacy pause/stop_today flags cleared

    # Track symbol of open trades to handle history details on close
    open_trade_symbols = {}
    positions_init = await loop.run_in_executor(executor, gateway.get_open_positions)
    for pos in positions_init:
        open_trade_symbols[pos.ticket] = pos.symbol

    _ensure_journal()

    # Clear stale cooldown on startup
    try:
        streak_state = load_streak_state()
        if streak_state.get("cooldown_until"):
            if time.time() >= streak_state["cooldown_until"]:
                streak_state["cooldown_until"] = None
                save_streak_state(streak_state)
                logger.info("Cleared expired cooldown_until on startup.")
    except Exception as e:
        logger.error(f"Error clearing stale cooldown: {e}")

    with state_lock:
        shared_state["ai_enabled"] = ai_supervisor.enabled

    telegram.send(
        f"Aegis-Gold v6.0 Ultra STARTED\n"
        f"Symbol: {sym} | Mode: {mode}\n"
        f"AI Brain (Local OMEGA): {'ENABLED' if ai_supervisor.enabled else 'DISABLED'}\n"
        f"Trade Target: Dynamic TP based on AI & Volatility\n"
        f"Min Trades/Day: {cfg.MIN_TRADES_PER_DAY} | Max: Unlimited (market decides)"
    )

    last_heartbeat  = time.time()
    last_trade_time = time.time()  # Prevents 2-hour inactivity alert on startup
    last_ai_report_time = time.time()
    last_cpu_check_time = time.time()  # For reduced CPU monitoring frequency
    last_trade_time_per_sym = {"EURUSD": 0, "XAUUSD": 0}  # 0 = no cooldown on first trade
    last_latency = 0.0
    previous_positions: set = set()
    loop_count = 0
    exchange_connected = True
    current_loop_delay = cfg.LOOP_DELAY_SEC

    # Safety layer: bind Telegram alerts and defensive callback
    _arena_mgr = None
    _cal_mon   = None
    _drift_mon = None
    try:
        from brain.champion_challenger import get_arena
        from brain.calibration import get_calibration_monitor
        from brain.drift_monitor import get_drift_monitor
        from brain.regime_switcher import get_strategy_state as _get_sw

        _arena_mgr = get_arena()
        _cal_mon   = get_calibration_monitor()
        _drift_mon = get_drift_monitor()
        _sw        = _get_sw()

        _arena_mgr.set_alert(telegram.send)
        _cal_mon.set_alert(telegram.send)
        _drift_mon.set_alert(telegram.send)

        def _force_defensive():
            """Called by drift monitor when 2+ features drift."""
            _sw.evaluate_and_switch("VOLATILE", 0.0, "UNKNOWN", 0.0)

        _drift_mon.set_defensive_callback(_force_defensive)

        # ── MODULE 2: Register champion (idempotent — no-op if already registered) ──
        if not _arena_mgr.get_status().get("champion"):
            _arena_mgr.register_champion("omega_v6_scalp_smc")
            logger.info("[MODULE2] Champion 'omega_v6_scalp_smc' registered in arena.")
        else:
            logger.info("[MODULE2] Existing champion found in arena: %s",
                        _arena_mgr.get_status()["champion"].get("name"))

        logger.info("[SAFETY] Champion/Challenger, Calibration, and Drift monitors initialised")
    except Exception as _e:
        logger.warning(f"[SAFETY] Safety layer init failed (non-fatal): {_e}")

    
    # Aegis v10.0 tracking variables
    session_start_time = time.time()
    session_refresh_active = False
    last_signal_discovery_time = 0

    # Initialize symbol_analysis_state with default values for all active symbols
    with state_lock:
        for sym in gateway.active_symbols:
            symbol_analysis_state[sym] = {
                "symbol": sym,
                "confidence": 0,
                "regime": "INITIALIZING",
                "regime_score": 0,
                "structure": "SCANNING",
                "structure_score": 0,
                "entry_score": 0,
                "reason": "System initializing...",
                "pattern": "NONE",
                "news_clear": True,
                "adx": 0.0,
                "rsi": 50.0,
                "action": "WAIT",
                "direction": "NONE",
                "grade": "F",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    logger.info(f"Initialized symbol_analysis_state for: {list(symbol_analysis_state.keys())}")

    # ── FAST LIVE CONFIDENCE UPDATE TASK (every 5 seconds - OPTIMIZED FOR CPU STABILITY) ──────────────
    async def fast_confidence_updater():
        """Runs every 5 seconds to update AI confidence for live dashboard display. Reduced from 2s for CPU stability."""
        logger.info(f"Fast confidence updater starting for symbols: {gateway.active_symbols}")
        while True:
            try:
                for sym in gateway.active_symbols:
                    try:
                        tick_obj = await loop.run_in_executor(executor, gateway.get_current_tick, sym)
                        if tick_obj is None:
                            continue
                        ticks_fast = await loop.run_in_executor(executor, gateway.get_ticks, sym, 50)
                        candles_fast = await loop.run_in_executor(executor, gateway.get_candles_m5, sym, 100)
                        
                        # Explicit None/length checks (avoid numpy array truth value)
                        if ticks_fast is None or candles_fast is None:
                            continue
                        ticks_len = len(ticks_fast) if hasattr(ticks_fast, '__len__') else 0
                        candles_len = len(candles_fast) if hasattr(candles_fast, '__len__') else 0
                        if ticks_len == 0 or candles_len < 5:
                            continue
                            
                        # Convert numpy arrays to list of dicts
                        ticks_list = []
                        for t in ticks_fast[-20:]:
                            try:
                                ticks_list.append({'bid': float(t['bid']), 'ask': float(t['ask'])})
                            except Exception:
                                try:
                                    ticks_list.append({'bid': float(t[1]), 'ask': float(t[2])})
                                except Exception:
                                    pass
                        if not ticks_list:
                            continue

                        candles_list = []
                        for c in candles_fast:
                            try:
                                candles_list.append({
                                    'open': float(c['open']), 'high': float(c['high']),
                                    'low': float(c['low']),   'close': float(c['close'])
                                })
                            except Exception:
                                try:
                                    candles_list.append({
                                        'open': float(c[1]), 'high': float(c[2]),
                                        'low': float(c[3]),  'close': float(c[4])
                                    })
                                except Exception:
                                    pass
                        if len(candles_list) < 5:
                            continue

                        sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
                        acct_fast = await loop.run_in_executor(executor, gateway.get_account_info)
                        if acct_fast is None:
                            continue
                        spread_fast = float(tick_obj.ask - tick_obj.bid) / sym_point if sym_point > 0 else 0
                        session_fast = shared_state.get("session", "LONDON")

                        dec = brain_decide(ticks_list, candles_list, acct_fast, risk,
                                          session_fast, spread_fast, sym_point, symbol=sym)
                        with state_lock:
                            symbol_analysis_state[sym] = {
                                "symbol":          sym,
                                "confidence":      dec.confidence,
                                "regime":          dec.regime,
                                "regime_score":    dec.regime_score,
                                "structure":       dec.structure,
                                "structure_score": dec.structure_score,
                                "entry_score":     dec.entry_score,
                                "reason":          dec.reason,
                                "pattern":         dec.pattern,
                                "news_clear":      dec.news_clear,
                                "adx":             round(dec.adx_val, 1),
                                "rsi":             round(dec.rsi_val, 1),
                                "action":          dec.action,
                                "direction":       dec.direction,
                                "grade":           dec.grade,
                                "timestamp":       datetime.now(timezone.utc).isoformat()
                            }
                            if sym == "XAUUSD" or shared_state["analysis"].get("confidence", 0) == 0:
                                shared_state["analysis"] = {
                                    "reason":          dec.reason,
                                    "regime":          dec.regime,
                                    "regime_score":    dec.regime_score,
                                    "structure":       dec.structure,
                                    "structure_score": dec.structure_score,
                                    "entry_score":     dec.entry_score,
                                    "confidence":      dec.confidence,
                                }
                    except Exception as e:
                        logger.warning(f"[{sym}] Fast confidence update error: {e}", exc_info=True)
            except Exception as e:
                logger.warning(f"Fast confidence loop error: {e}", exc_info=True)
            await asyncio.sleep(5)  # Changed from 2s to 5s for CPU stability

    # Start the fast confidence updater as a background task
    asyncio.ensure_future(fast_confidence_updater())
    logger.info("✅ Live confidence updater started (5-second refresh - optimized for stability)")

    # ── QUANT AI ADVISORY OBSERVER (additive, flag-gated, DEMO-only) ────────
    # Read-only: runs quant_ai on market data and publishes an opinion into
    # shared_state["quant_ai"] + data/quant_ai_advisory.jsonl. It cannot place
    # orders and is not consulted by the risk gate or execution path below.
    # Off unless quant_x_flags.json sets "quant_ai_advisory": true.
    try:
        from core.quant_ai_advisory import quant_ai_advisory_loop, _flag_on
        asyncio.ensure_future(quant_ai_advisory_loop(
            gateway, loop, executor, shared_state, state_lock))
        logger.info("[QUANT-AI] advisory observer scheduled (flag-gated, "
                    "currently %s)", "ON" if _flag_on() else "OFF")
    except Exception as _qa_ex:
        logger.warning("[QUANT-AI] advisory observer not started (non-fatal): %s",
                       _qa_ex)

    while True:
        loop_count += 1
        now = time.time()
        
        try:
            # ── 1. Fetch account & open positions ───────────────────────────
            acct = await loop.run_in_executor(executor, gateway.get_account_info)
            if not acct:
                if loop_count % 5 == 0:
                    logger.error("MT5 ACCOUNT INFO MISSING! Check login credentials or MT5 terminal connection.")
                # Auto-reconnect every 3 failed attempts (~6s) to recover from dropped connections
                if loop_count % 3 == 0:
                    logger.warning("MT5 account info missing — attempting auto-reconnect...")
                    reconnected = await loop.run_in_executor(executor, gateway.reconnect)
                    if reconnected:
                        logger.info("MT5 auto-reconnect successful.")
                    else:
                        logger.error("MT5 auto-reconnect failed. Will retry...")
                await asyncio.sleep(2)
                continue

            equity = acct["equity"]
            positions = await loop.run_in_executor(executor, gateway.get_open_positions)
            has_positions = len(positions) > 0

            # ── 2. Focus Management (Dynamic loop delays) ─────────────────────
            # 70% Trade Management (0.3s loop delay) when positions exist, 50% (1s loop delay) when idle.
            if has_positions:
                current_loop_delay = 0.3
                discovery_interval = 1.0  # Check signals every 1 second
            else:
                current_loop_delay = 1.0
                discovery_interval = 1.0  # Check signals every 1 second

            # ── 3. Drawdown Protections & Volatility ──────────────────────
            dd_pct = risk.calculate_current_drawdown(equity)
            
            # Reduce trade frequency if drawdown > 2% (double the discovery interval)
            if dd_pct > getattr(cfg, 'DD_REDUCE_FREQ_PCT', 2.0):
                discovery_interval *= 2.0

            is_emergency = dd_pct >= getattr(cfg, 'DD_BLOCK_NEW_PCT', 4.0) or not exchange_connected
            is_emergency_drawdown = dd_pct >= getattr(cfg, 'DD_EMERGENCY_PCT', 5.0)

            # Determine volatility state (default to XAUUSD if tracked, or NORMAL)
            vol_state = "NORMAL"
            if "XAUUSD" in symbol_analysis_state:
                vol_state = symbol_analysis_state["XAUUSD"].get("regime", "NORMAL")
                if vol_state not in ["COMPRESSED", "NORMAL", "VOLATILE"]:
                    vol_state = "NORMAL"

            max_open_trades_limit = position_supervisor.get_dynamic_trade_limit(vol_state, is_emergency=is_emergency)

            # ── 4. Position Supervisor Monitoring (Continuously on every tick) ──
            cur_tickets = {p.ticket for p in positions}
            ladder = load_ladder()
            
            for t in (previous_positions - cur_tickets):
                risk.open_trade_times.pop(t, None)
                ladder.pop(str(t), None)
                sym_closed = open_trade_symbols.pop(t, "EURUSD")
                risk.clear_dynamic_tp_state(t)
                asyncio.create_task(process_closed_trade(t, sym_closed, gateway, risk, ai_supervisor, telegram, loop, executor))
            
            save_ladder(ladder)
            previous_positions = cur_tickets

            for pos in positions:
                pos_sym = pos.symbol
                ticks = await loop.run_in_executor(executor, gateway.get_ticks, pos_sym, 200)
                candles_m5 = await loop.run_in_executor(executor, gateway.get_candles_m5, pos_sym, cfg.CANDLE_COUNT)
                candles_m1 = await loop.run_in_executor(executor, gateway.get_candles_m1, pos_sym, getattr(cfg, 'M1_CANDLE_COUNT', 30))
                tick_obj = await loop.run_in_executor(executor, gateway.get_current_tick, pos_sym)

                if ticks is not None and len(ticks) > 0 and candles_m5 is not None and len(candles_m5) > 0 and tick_obj is not None:
                    sym_point = gateway.symbols_data.get(pos_sym, {}).get("point", 0.00001)
                    current_spread = float(tick_obj.ask - tick_obj.bid) / sym_point if sym_point > 0 else 0.0
                    
                    # Run multi-timeframe engines
                    trend_res = ai_supervisor.trend_detector.analyze(candles_m5, candles_m1)
                    vol_ratio_limit = cfg.get_symbol_config(pos_sym).get("max_volatility_ratio", 5.0)
                    volatility_res = ai_supervisor.volatility_engine.analyze(candles_m5, sym_point, max_ratio_limit=vol_ratio_limit)
                    momentum_res = ai_supervisor.momentum_engine.analyze(ticks, candles_m1, sym_point)
                    
                    if pos_sym == "XAUUSD":
                        vol_state = volatility_res.get("volatility_state", "NORMAL")

                    # Run position evaluation
                    eval_res = position_supervisor.evaluate_position(
                        pos, ticks, candles_m1, candles_m5, current_spread,
                        trend_res, volatility_res, momentum_res,
                        shared_state.get("session", "LONDON"), is_emergency_drawdown
                    )

                    if eval_res.get("action") == "CLOSE":
                        logger.info(f"Supervisor exit triggered for {pos_sym} #{pos.ticket}: {eval_res.get('reason')}")
                        await loop.run_in_executor(executor, gateway.close_position, pos)
                        telegram.send(f"🛡️ <b>[SUPERVISOR EXIT]</b> {pos_sym} #{pos.ticket}\nReason: {eval_res.get('reason')}\nClosed position early to protect capital.")

            # ── 5. 45-Minute Session Refresh ─────────────────────────────────
            session_elapsed = time.time() - session_start_time
            if session_elapsed >= getattr(cfg, 'SESSION_REFRESH_MIN', 45) * 60:
                session_refresh_active = True
                logger.info("🕒 45-minute session refresh triggered. Pausing new entries...")
                telegram.send("🕒 <b>[SESSION REFRESH]</b> 45-minute session refresh triggered. Pausing new entries...")
                
                # Health diagnosis
                try:
                    run_self_diagnosis(gateway, risk, ai_supervisor, telegram)
                except Exception as diag_ex:
                    logger.error(f"Diagnosis run failed: {diag_ex}")
                
                # Reset queues, counters, statistics, and caches
                position_supervisor.signal_queue.clear()
                risk.session_trades = {k: 0 for k in risk.session_trades}
                risk.daily_trades = 0
                
                session_start_time = time.time()
                session_refresh_active = False
                logger.info("🕒 Session refresh complete. Trading resumed.")
                telegram.send("🔄 <b>[SESSION REFRESH]</b> Session refresh completed successfully. Trading resumed.")

            # ── 6. Periodic AI state report to Telegram (hourly) ─────────────────────
            if time.time() - last_ai_report_time >= 3600:
                last_ai_report_time = time.time()
                try:
                    telegram.send_ai_analysis(symbol_analysis_state)
                except Exception as ex:
                    logger.error("Error sending periodic AI report: %s", ex)

            # ── 7. CPU and RAM Monitoring & Self-Healing (REDUCED FREQUENCY FOR STABILITY) ──────────────────────────
            # Only check every 60 seconds to reduce overhead
            if time.time() - last_cpu_check_time >= 60:
                last_cpu_check_time = time.time()
                try:
                    proc = psutil.Process()
                    mem_mb = proc.memory_info().rss / (1024 * 1024)
                    # Increased threshold to 600MB to reduce garbage collection frequency
                    if mem_mb > 600.0:
                        logger.warning("High memory usage detected (%.1f MB). Running garbage collection...", mem_mb)
                        gc.collect()

                    cpu_pct = psutil.cpu_percent()
                    # Increased threshold to 90% to reduce false alarms
                    if cpu_pct > 90.0:
                        if current_loop_delay == cfg.LOOP_DELAY_SEC:
                            current_loop_delay = 1.5
                            logger.warning("High CPU usage detected (%.1f%%). Throttling engine frequency to 1.5s.", cpu_pct)
                            # Telegram disabled - no notification
                    elif cpu_pct < 60.0:
                        if current_loop_delay != cfg.LOOP_DELAY_SEC:
                            current_loop_delay = cfg.LOOP_DELAY_SEC
                            logger.info("CPU stabilized. Restoring normal trading frequency.")
                            # Telegram disabled - no notification
                except Exception as mon_ex:
                    logger.error("Process resource monitoring error: %s", mon_ex)

            # ── 8. Connection monitoring ─────────────────────────────
            is_conn = await loop.run_in_executor(executor, gateway.is_connected)
            if not is_conn:
                if exchange_connected:
                    exchange_connected = False
                    telegram.send("⚠️ <b>[STABILITY] Exchange Disconnected</b>\nMetaTrader 5 Terminal connection is lost! Attempting to reconnect...")
                logger.warning("MT5 disconnected. Reconnecting...")
                await loop.run_in_executor(executor, gateway.reconnect)
                await asyncio.sleep(3)
                continue
            else:
                if not exchange_connected:
                    exchange_connected = True
                    telegram.send("🔄 <b>[STABILITY] Exchange Reconnected</b>\nMetaTrader 5 connection restored. Recovery successful.")

            # ── 9. Weekend Check (Global) ────────────────────────
            day_of_week = datetime.now(timezone.utc).weekday()
            if day_of_week >= 5: # Saturday(5) or Sunday(6)
                if loop_count % 100 == 0:
                    logger.info("MARKET CLOSED (Weekend). Standing by for market open...")
                with state_lock:
                    shared_state["status"] = "MARKET CLOSED"
                await asyncio.sleep(60)
                continue

            # ── 10. Process Telegram Command queue ──────────────────
            with state_lock:
                cmds = list(command_queue)
                command_queue.clear()
            for cmd_str in cmds:
                parts = cmd_str.split()
                if not parts:
                    continue
                cmd = parts[0].lower()
                args = parts[1:]
                if cmd == "/pause":   
                    risk.manual_pause = True
                    telegram.send("⏸ Trading paused.")
                elif cmd == "/resume": 
                    risk.manual_resume()
                    telegram.send("▶️ Trading resumed.")
                elif cmd == "/closeall": 
                    gateway.close_all_positions()
                    telegram.send("🗑️ Close-all command sent.")
                elif cmd == "/stop":  
                    risk.stop_today = True
                    telegram.send("⏹️ Trading stopped for today.")
                elif cmd == "/reconnect": 
                    gateway.reconnect()
                    telegram.send("✅ Reconnect command received.")
                elif cmd == "/diagnose": 
                    run_self_diagnosis(gateway, risk, ai_supervisor, telegram)
                elif cmd == "/lotsize" and args:
                    try:
                        lot = float(args[0])
                        risk.override_lot(lot)
                        telegram.send(f"✅ Next trade lot overridden to {lot}")
                    except ValueError:
                        pass
                else:
                    # Let TelegramBot handle /status, /health, /trades, etc.
                    telegram._dispatch_command(cmd, args)

            # ── 11. Update shared dashboard state ────────────────────
            rs = risk.get_status_dict()
            with state_lock:
                if risk.is_locked():                       shared_state["status"] = "LOCKED"
                elif risk.stop_today:                      shared_state["status"] = "STOPPED"
                elif risk.manual_pause or risk.is_paused:  shared_state["status"] = "PAUSED"
                elif session_refresh_active:               shared_state["status"] = "SESSION_REFRESH"
                else:                                      shared_state["status"] = "ACTIVE"

                shared_state["equity"]             = float(equity)
                shared_state["daily_pnl"]          = float(equity - risk.start_equity)
                shared_state["daily_trades"]       = rs["daily_trades"]
                shared_state["wins"]               = rs["today_wins"]
                shared_state["losses"]             = rs["today_losses"]
                shared_state["consecutive_losses"] = rs["consecutive_losses"]
                shared_state["latency"]            = last_latency
                shared_state["per_trade_target"]   = "DYNAMIC_TP"
                shared_state["min_trades_per_day"] = cfg.MIN_TRADES_PER_DAY
                shared_state["daily_target"]       = "UNLIMITED"

                # Populate overall performance stats from performance DB
                try:
                    p_stats = perf.get_performance_stats(days=30)
                    if p_stats:
                        shared_state["total_trades"]  = p_stats.get("total_trades", rs["daily_trades"])
                        shared_state["total_pnl"]     = p_stats.get("net_profit", float(equity - risk.start_equity))
                        shared_state["total_wins"]    = p_stats.get("wins", rs["today_wins"])
                        shared_state["total_losses"]  = p_stats.get("losses", rs["today_losses"])
                        shared_state["win_rate"]      = p_stats.get("win_rate", 0.0)
                        shared_state["profit_factor"] = p_stats.get("profit_factor", 1.0)
                except Exception:
                    pass

            # ── 11b. Periodic Safety Validation Checks (every 20 scans) ───────
            if loop_count % 20 == 0:
                try:
                    from brain.naked_position_monitor import check_and_protect_open_positions
                    check_and_protect_open_positions(gateway, telegram)
                except Exception as _np_ex:
                    logger.error(f"[SAFETY] Naked position check error: {_np_ex}")

                try:
                    from brain.drift_monitor import get_drift_monitor
                    from brain.calibration import get_calibration_monitor
                    _drift_mon = get_drift_monitor()
                    _drift_mon.check_drift()
                    # Run calibration evaluation every 100 scans to reduce load
                    if loop_count % 100 == 0:
                        get_calibration_monitor().evaluate()
                except Exception as _se:
                    logger.warning(f"[SAFETY] Periodic safety check error: {_se}")

            # ── 12. Signal Discovery, Vetting, Scoring & Execution ──
            if time.time() - last_signal_discovery_time >= discovery_interval and not session_refresh_active:
                last_signal_discovery_time = time.time()
                candidates = []

                for sym in gateway.active_symbols:
                    tick_obj = await loop.run_in_executor(executor, gateway.get_current_tick, sym)
                    if not tick_obj:
                        continue

                    ticks = await loop.run_in_executor(executor, gateway.get_ticks, sym, 200)
                    candles_m5 = await loop.run_in_executor(executor, gateway.get_candles_m5, sym, cfg.CANDLE_COUNT)
                    candles_m1 = await loop.run_in_executor(executor, gateway.get_candles_m1, sym, getattr(cfg, 'M1_CANDLE_COUNT', 20))

                    data_ok = (
                        ticks is not None and len(ticks) > 0 and
                        candles_m5 is not None and len(candles_m5) > 0
                    )
                    if not data_ok:
                        continue

                    sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
                    factory = FeatureFactory(sym_point)
                    features = factory.extract(ticks, tick_obj)
                    session = features.session
                    spread = features.current_spread

                    with state_lock:
                        shared_state["session"] = session
                        shared_state["spread"] = int(spread)
                        shared_state["price"] = float(tick_obj.bid)

                    # Heartbeat
                    if now - last_heartbeat >= cfg.HEARTBEAT_SEC:
                        last_heartbeat = now
                        telegram.send_heartbeat(session, equity, risk.start_equity, rs, spread, last_latency)

                    # Skip trade check
                    sym_positions = [p for p in positions if p.symbol == sym]
                    min_gap_sec = getattr(cfg, 'MIN_GAP_BETWEEN_TRADES_MIN', 0) * 60
                    sym_last_trade = last_trade_time_per_sym.get(sym, 0)
                    
                    skip_trade = False
                    if not risk.can_trade(session, symbol=sym, current_equity=equity, session_refresh_active=session_refresh_active):
                        skip_trade = True
                    elif len(positions) >= max_open_trades_limit:
                        skip_trade = True
                    elif len(sym_positions) >= getattr(cfg, 'MAX_OPEN_TRADES_PER_SYMBOL', 5):
                        skip_trade = True
                    elif not check_cooldown():
                        skip_trade = True
                    elif min_gap_sec > 0 and time.time() - sym_last_trade < min_gap_sec:
                        skip_trade = True

                    # Run Brain Decision (always run to update display metrics)
                    decision = brain_decide(ticks, candles_m5, acct, risk, session, spread, sym_point, symbol=sym, candles_m1=candles_m1)

                    # ── LIVE TRACE: CANDLE_TRACE (completed closed candle only) ──
                    # MT5 returns [-1] = currently forming bar, [-2] = last CLOSED bar.
                    # Pattern detection uses the CLOSED bar only; log both for audit.
                    _closed_ct = None
                    _forming_ct = None
                    try:
                        # BUGFIX (AC-3): the MT5 feed is a numpy structured
                        # array, not list/tuple — extract timestamps
                        # positionally (time, open, high, low, close, ...).
                        from brain.brain import _extract_candle_time
                        if candles_m5 is not None and len(candles_m5) >= 1:
                            _forming_ct = _extract_candle_time(candles_m5[-1])
                        if candles_m5 is not None and len(candles_m5) >= 2:
                            _closed_ct = _extract_candle_time(candles_m5[-2])
                    except Exception:
                        pass
                    logger.info(
                        f"[CANDLE_TRACE] symbol={sym} closed_candle_time={_closed_ct} "
                        f"forming_candle_time={_forming_ct} pattern={decision.pattern} "
                        f"pattern_direction={getattr(decision, 'pattern_direction', 'NA')} "
                        f"decision_direction={decision.direction} action={decision.action}"
                    )

                    # ═══════════════════════════════════════════════════════════════════
                    # STEP 1 FIX: OPPOSITE-DIRECTION EXCEPTION FOR SKIP_TRADE
                    # Allow SELL to bypass BUY cooldown if BUY position open and no SELL
                    # ═══════════════════════════════════════════════════════════════════
                    opposite_dir_exception = False
                    if skip_trade and decision.action == "TRADE" and decision.direction == "SELL":
                        try:
                            import MetaTrader5 as mt5
                            
                            # Check if any BUY positions exist and NO SELL positions for this symbol
                            buy_positions = [p for p in positions if p.symbol == sym and p.type == mt5.POSITION_TYPE_BUY]
                            sell_positions = [p for p in positions if p.symbol == sym and p.type == mt5.POSITION_TYPE_SELL]
                            
                            if len(buy_positions) > 0 and len(sell_positions) == 0:
                                # Allow SELL to open hedge position even during BUY cooldown
                                opposite_dir_exception = True
                                logger.info(
                                    f"✅ OPPOSITE DIRECTION EXCEPTION: Allowing SELL {sym} despite cooldown "
                                    f"({len(buy_positions)} open BUY position(s), 0 SELL positions)"
                                )
                        except Exception as e:
                            logger.warning(f"Exception checking opposite-direction exception: {e}")

                    if skip_trade and decision.action == "TRADE" and not opposite_dir_exception:
                        # Log DETAILED blocking reasons (especially for SELL)
                        block_reasons = []
                        if not risk.can_trade(session, symbol=sym, current_equity=equity, session_refresh_active=session_refresh_active):
                            block_reasons.append("risk.can_trade=False")
                        if len(positions) >= max_open_trades_limit:
                            block_reasons.append(f"positions({len(positions)})>=limit({max_open_trades_limit})")
                        if len(sym_positions) >= getattr(cfg, 'MAX_OPEN_TRADES_PER_SYMBOL', 5):
                            block_reasons.append(f"sym_positions({len(sym_positions)})>=limit")
                        if not check_cooldown():
                            block_reasons.append("cooldown_active")
                        if min_gap_sec > 0 and time.time() - sym_last_trade < min_gap_sec:
                            remaining = int(min_gap_sec - (time.time() - sym_last_trade))
                            block_reasons.append(f"min_gap_cooldown({remaining}s_remaining)")
                        
                        decision.action = "WAIT"
                        decision.reason = f"Entry blocked: {', '.join(block_reasons)}"
                        
                        # CRITICAL: Log specifically for SELL blocks to diagnose why SELL never executes
                        if decision.direction == "SELL":
                            logger.warning(
                                f"🚨 SELL BLOCKED: {sym} {decision.direction} | "
                                f"Pattern: {getattr(decision, 'pattern', 'UNKNOWN')} | "
                                f"Confidence: {decision.confidence}% | "
                                f"Authorization: {getattr(decision, 'trade_authorization', None) is not None} | "
                                f"Blocking Reasons: {', '.join(block_reasons)} | "
                                f"Open Positions: {len(positions)} | "
                                f"Sym Positions: {len(sym_positions)}"
                            )
                        else:
                            logger.info(f"Entry blocked: {sym} {decision.direction} - {', '.join(block_reasons)}")

                    # Vetting with AI Supervisor
                    ai_approved = True
                    # -------------------------------------------------------------
                    # HARD DAILY LOSS CIRCUIT BREAKER & SAFETY VERIFICATION
                    # -------------------------------------------------------------
                    if risk.is_daily_loss_limit_reached(equity):
                        logger.warning(f"🚨 [CIRCUIT BREAKER] Daily loss limit triggered. Rejecting trade for {sym}.")
                        decision.action = "WAIT"
                        decision.reason = "DAILY_LOSS_LIMIT_REACHED"

                    # Canonical Trade Authorization Check:
                    # In zero-confidence architecture, a TRADE is executed ONLY if authorized by the opportunity pipeline.
                    has_authorization = (
                        decision.action == "TRADE" and
                        hasattr(decision, "trade_authorization") and
                        decision.trade_authorization is not None and
                        getattr(decision.trade_authorization, "authorized", False)
                    )

                    if not has_authorization and decision.action == "TRADE":
                        logger.warning(f"[EXECUTION BLOCKED] {sym} {decision.direction} rejected: Missing valid TradeAuthorization contract.")
                        decision.action = "WAIT"
                        decision.reason = "UNAUTHORIZED_EXECUTION_ATTEMPT"

                    with state_lock:
                        shared_state["analysis"] = {
                            "reason":          decision.reason,
                            "regime":          decision.regime,
                            "regime_score":    decision.regime_score,
                            "structure":       decision.structure,
                            "structure_score": decision.structure_score,
                            "entry_score":     decision.entry_score,
                            "confidence":      decision.confidence,
                        }
                        symbol_analysis_state[sym] = {
                            "symbol": sym,
                            "reason": decision.reason,
                            "regime": decision.regime,
                            "regime_score": decision.regime_score,
                            "structure": decision.structure,
                            "structure_score": decision.structure_score,
                            "entry_score": decision.entry_score,
                            "confidence": decision.confidence,
                            "pattern": decision.pattern,
                            "news_clear": decision.news_clear,
                            "adx": round(decision.adx_val, 1),
                            "rsi": round(decision.rsi_val, 1),
                            "action": decision.action,
                            "direction": decision.direction,
                            "grade": decision.grade,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }

                    # ── LIVE TRACE: [PATTERN_ENTRY] before candidate creation ──
                    logger.info(
                        f"[PATTERN_ENTRY] symbol={sym} candle_time={_closed_ct} "
                        f"pattern={decision.pattern} "
                        f"pattern_direction={getattr(decision, 'pattern_direction', 'NA')} "
                        f"decision_action={decision.action} decision_direction={decision.direction}"
                    )

                    # If trade approved, add to candidates signals for scoring
                    if decision.action == "TRADE":
                        trend_res = ai_supervisor.trend_detector.analyze(candles_m5, candles_m1)
                        volatility_res = ai_supervisor.volatility_engine.analyze(candles_m5, sym_point)
                        momentum_res = ai_supervisor.momentum_engine.analyze(ticks, candles_m1, sym_point)
                        
                        score = position_supervisor.score_signal(
                            sym, decision.direction, decision.confidence,
                            trend_res.get("trend_score", 0),
                            volatility_res.get("volatility_score", 50),
                            spread,
                            momentum_res.get("momentum_score", 50)
                        )
                        candidates.append({
                            "symbol": sym,
                            "direction": decision.direction,
                            "decision": decision,
                            "score": score,
                            "spread": spread,
                            "session": session,
                            "ai_approved": ai_approved
                        })

                # Process ranked candidates
                if candidates:
                    candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)
                    primary_cand = candidates[0]
                    
                    # Queue the rest
                    for c in candidates[1:]:
                        c["time_queued"] = time.time()
                        position_supervisor.signal_queue.append(c)
                        logger.info(f"Signal queued for {c['symbol']} with score {c['score']}")
                        
                    # Execute primary ranked signal
                    sym = primary_cand["symbol"]
                    decision = primary_cand["decision"]
                    spread = primary_cand["spread"]
                    session = primary_cand["session"]
                    ai_approved = primary_cand["ai_approved"]
                    
                    # Final entry gate checks
                    # v6.1 FIX: 'demo_unrestricted_active' was referenced but never
                    # defined -> NameError crashed the main loop every cycle right
                    # before execution ("Main loop error: name 'demo_unrestricted_active'
                    # is not defined"), so queued TRADE signals were NEVER executed.
                    # Define it from the flag: unrestricted entry gates in DEMO mode
                    # only; LIVE mode always keeps cooldown + risk gates.
                    demo_unrestricted_active = bool(getattr(cfg, "DEMO_MODE", True)) and bool(QX.flag("demo_unrestricted_mode"))
                    can_execute_entry = (len(positions) < max_open_trades_limit)
                    if not demo_unrestricted_active:
                        can_execute_entry = can_execute_entry and check_cooldown() and risk.can_trade(session, symbol=sym, current_equity=equity)

                    if can_execute_entry:
                        # Run LLM Trading Analyst Vetting
                        is_reduced_trade = False
                        try:
                            logger.info(f"🤖 [LLM ANALYST] Vetting candidate signal: {decision.direction} {sym}...")
                            sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
                            
                            # Get candles_m1 for the candidate (if available) or copy from MT5
                            try:
                                import MetaTrader5 as mt5
                                c_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 30)
                                if c_m1 is None:
                                    c_m1 = candles_m1
                            except Exception:
                                c_m1 = candles_m1
                                
                            thought, verdict = run_llm_analyst_evaluation(
                                sym, decision, spread, session, equity, sym_point, 
                                candles_m5, c_m1, gateway, risk
                            )
                            
                            logger.info(f"🤖 [LLM ANALYST] Verdict: {verdict.get('recommendation', 'reject').upper()} | Reason: {verdict.get('reason_code')}")
                            logger.info(f"🤖 [LLM ANALYST] Thought: {thought}")
                            
                            # Enrich explanation details with LLM's thought block
                            try:
                                conn_explain_update = sqlite3.connect(os.path.join(BASE_DIR, "data", "explanations.db"))
                                cursor_update = conn_explain_update.cursor()
                                cursor_update.execute(
                                    "SELECT id, context_json FROM explanations "
                                    "WHERE symbol = ? AND direction = ? AND action = 'TRADE' "
                                    "ORDER BY id DESC LIMIT 1;", (sym, decision.direction)
                                )
                                row_update = cursor_update.fetchone()
                                if row_update:
                                    row_id = row_update[0]
                                    ctx_update = json.loads(row_update[1] or "{}")
                                    ctx_update["historical_edge"] = verdict.get("historical_edge", "neutral")
                                    ctx_update["microstructure_quality"] = verdict.get("microstructure_quality", "clean")
                                    ctx_update["llm_thought"] = thought
                                    ctx_update["verdict"] = verdict
                                    
                                    cursor_update.execute(
                                        "UPDATE explanations SET plain_english = ?, context_json = ? "
                                        "WHERE id = ?;",
                                        (thought, json.dumps(ctx_update), row_id)
                                    )
                                    conn_explain_update.commit()
                                conn_explain_update.close()
                            except Exception as explain_up_ex:
                                logger.debug(f"Failed to enrich explanation with LLM Analyst thought: {explain_up_ex}")
                                
                            # Process recommendation — 🔬 OBSERVATIONAL ONLY
                            # ── ROOT CAUSE #2 FIX ── The LLM Trading Analyst must
                            # NEVER veto a valid pattern entry. It may log, explain,
                            # and advise, but it can never block BUY or SELL, change
                            # direction, or turn a valid pattern into a veto.
                            llm_recommendation = verdict.get("recommendation", "reject").lower()
                            reason_code = verdict.get("reason_code", "")
                            if llm_recommendation == "reject":
                                logger.info(
                                    f"🤖 [LLM ANALYST OBSERVATION] {decision.direction} {sym} "
                                    f"rec={llm_recommendation} reason={reason_code} — "
                                    f"advisory only, pattern trade proceeds."
                                )
                                telegram.send(
                                    f"🤖 <b>[LLM Analyst ADVISORY]</b> Would reject "
                                    f"{decision.direction} {sym} (Reason: {reason_code}) — "
                                    f"advisory only, pattern trade proceeds."
                                )

                                
                            if llm_recommendation == "approve_reduced":
                                is_reduced_trade = True
                                # SAFETY GATE: only scale lot if local model has been trained
                                # and shadow validation has passed. Flip cfg.llm_analyst_sizing_live
                                # = True ONLY after shadow_validate_analyst.py sanity checks pass.
                                if getattr(cfg, 'llm_analyst_sizing_live', False):
                                    old_lot = decision.lot
                                    decision.lot = max(0.01, round(decision.lot * getattr(cfg, 'reduced_size_factor', 0.5), 2))
                                    logger.info(f"\u26a0\ufe0f [LLM ANALYST REDUCED] Lot size scaled down from {old_lot} to {decision.lot} (Challenger path).")
                                    telegram.send(f"\U0001f916 <b>[LLM Analyst REDUCED]</b> Lot size scaled down to {decision.lot} (Challenger path) for {sym}.")
                                else:
                                    logger.info(f"\u26a0\ufe0f [LLM ANALYST REDUCED] approve_reduced verdict for {sym} — sizing NO-OP (llm_analyst_sizing_live=False). Lot unchanged at {decision.lot}.")
                                    telegram.send(f"\U0001f916 <b>[LLM Analyst REDUCED - SHADOW]</b> Would reduce lot for {sym}, but sizing gate is OFF. Reason: {verdict.get('reason_code')}")
                                
                        except Exception as analyst_err:
                            logger.error(f"Error running LLM Trading Analyst: {analyst_err}", exc_info=True)
                            
                        telegram.send(f"✅ Executing Ranked Signal – {decision.direction} {sym} @ {session} (Score: {primary_cand['score']} | Conf: {decision.confidence}%)")

                        # ── MODULE 2B: Write challenger shadow decision before trade placement ──
                        # Records every evaluated signal (BUY/SELL/HOLD) so the arena can
                        # track direction balance and PF separately for the fixed Challenger.
                        try:
                            import json as _json_shadow
                            _shadow_path = os.path.join(BASE_DIR, "data", "challenger_shadow_decisions.json")
                            _shadow_data = {}
                            if os.path.exists(_shadow_path):
                                try:
                                    with open(_shadow_path, "r") as _sf:
                                        _shadow_data = _json_shadow.load(_sf)
                                except Exception:
                                    _shadow_data = {}
                            _shadow_data[sym] = {
                                "direction": decision.direction,
                                "confidence": getattr(decision, "confidence", 0),
                                "session": session,
                                "timestamp": time.time(),
                                "consensus_score": getattr(decision, "consensus_score", 0.0),
                                "version": "aegis_v10_sell_fix_aug6",
                            }
                            with open(_shadow_path, "w") as _sf:
                                _json_shadow.dump(_shadow_data, _sf, indent=2)
                            logger.debug(f"[MODULE2B] Challenger shadow decision written: {sym} {decision.direction} @ conf={getattr(decision, 'confidence', 0)}%")
                        except Exception as _sh_err:
                            logger.debug(f"[MODULE2B] Shadow decision write error: {_sh_err}")

                        # ── Requirement 2: FINAL DECISION IMMUTABILITY before order dispatch ──
                        if not verify_direction_integrity(decision):
                            logger.critical(
                                f"[DIRECTION INTEGRITY FAILURE] {sym} execution ABORTED. "
                                f"pattern={getattr(decision, 'pattern_direction', 'NA')} "
                                f"final={decision.direction}. DO NOT TRADE."
                            )
                            telegram.send(
                                f"🚨 <b>[DIRECTION INTEGRITY FAILURE]</b> Trade blocked for {sym}. "
                                f"Pattern: {getattr(decision, 'pattern_direction', 'NA')} | "
                                f"Final: {decision.direction}"
                            )
                            continue

                        # ── LIVE TRACE: [{decision.direction}_EXECUTION_TRACE] before dispatch ──
                        logger.info(
                            f"[{decision.direction}_EXECUTION_TRACE] symbol={sym} "
                            f"pattern={decision.pattern} "
                            f"pattern_direction={getattr(decision, 'pattern_direction', 'NA')} "
                            f"decision_direction={decision.direction} action={decision.action} "
                            f"sl={decision.sl_points}pts tp={decision.tp_points}pts lot={decision.lot}"
                        )

                        result, latency, slippage = await loop.run_in_executor(
                            executor,
                            gateway.execute_order,
                            sym,
                            decision.direction,
                            decision.lot,
                            decision.tp_points,
                            decision.sl_points,
                        )

                        last_latency = latency

                        # ── LIVE TRACE: [{decision.direction}_MT5_RESULT] after dispatch ──
                        _retcode = getattr(result, "retcode", None) if result else None
                        logger.info(
                            f"[{decision.direction}_MT5_RESULT] symbol={sym} "
                            f"retcode={_retcode} "
                            f"ticket={getattr(result, 'order', None) if result else None} "
                            f"order_type={'ORDER_TYPE_SELL' if decision.direction == 'SELL' else 'ORDER_TYPE_BUY'} "
                            f"price={getattr(result, 'price', None) if result else None} "
                            f"sl={decision.sl_points}pts tp={decision.tp_points}pts"
                        )

                        if result:
                            last_trade_time = time.time()
                            last_trade_time_per_sym[sym] = time.time()
                            risk.on_trade_open(session, result.order, direction=decision.direction, symbol=sym)
                            open_trade_symbols[result.order] = sym
                            
                            # If it was an approve_reduced trade, record it in challenger_decisions_by_ticket.json
                            if is_reduced_trade:
                                try:
                                    import json as _json_chal
                                    chal_ticket_path = os.path.join(BASE_DIR, "data", "challenger_decisions_by_ticket.json")
                                    chal_data = {}
                                    if os.path.exists(chal_ticket_path):
                                        try:
                                            with open(chal_ticket_path, "r") as _tf:
                                                chal_data = _json_chal.load(_tf)
                                        except Exception:
                                            pass
                                    chal_data[str(result.order)] = True
                                    with open(chal_ticket_path, "w") as _tf:
                                        _json_chal.dump(chal_data, _tf, indent=2)
                                    logger.debug(f"[MODULE2] Labeled ticket {result.order} as Challenger trade.")
                                except Exception as _e:
                                    logger.error(f"Failed to record challenger ticket: {_e}")
                                    
                            # Save challenger's decision by ticket
                            try:
                                import json as _json4
                                shadow_dec_path = os.path.join(BASE_DIR, "data", "challenger_shadow_decisions.json")
                                ticket_dec_path = os.path.join(BASE_DIR, "data", "challenger_decisions_by_ticket.json")
                                if os.path.exists(shadow_dec_path):
                                    with open(shadow_dec_path) as _f:
                                        shadow_data = _json4.load(_f)
                                    sym_shadow = shadow_data.get(sym)
                                    if sym_shadow:
                                        ticket_data = {}
                                        if os.path.exists(ticket_dec_path):
                                            try:
                                                with open(ticket_dec_path) as _tf:
                                                    ticket_data = _json4.load(_tf)
                                            except Exception:
                                                pass
                                        ticket_data[str(result.order)] = sym_shadow
                                        with open(ticket_dec_path, "w") as _tf:
                                            _json4.dump(ticket_data, _tf, indent=2)
                            except Exception as _e:
                                logger.error(f"Failed to record challenger decision by ticket: {_e}")
                            
                            perf.log_trade_open(
                                ticket=result.order, symbol=sym, direction=decision.direction,
                                entry_price=result.price, sl=decision.sl_points, tp=decision.tp_points,
                                lot=decision.lot, regime=decision.regime, pattern=decision.pattern,
                                adx=decision.adx_val, rsi=decision.rsi_val, confidence=decision.confidence,
                                session=session, atr=decision.atr_estimate,
                                pattern_tier=getattr(decision, 'pattern_tier', 'scalp'),
                                big_pattern_type=getattr(decision, 'big_pattern_type', 'NONE'),
                                small_pattern_type=getattr(decision, 'small_pattern_type', 'NONE'),
                                consensus_score=getattr(decision, 'consensus_score', 0.0),
                                computed_rr=getattr(decision, 'rr_ratio', 0.0),
                                invalidation_level=getattr(decision, 'invalidation_level', 0.0),
                                pipeline_id="dual_tier_v1"
                            )

                            
                            technique = getattr(decision, 'signal_source', getattr(decision, 'mode', 'SCALP'))
                            telegram.send_trade_open(result, decision, spread, session, symbol=sym, technique=technique)
                            log_trade({
                                "timestamp":          datetime.now(timezone.utc).isoformat(),
                                "trade_id":           result.order,
                                "symbol":             sym,
                                "mode":               mode,
                                "session":            session,
                                "direction":          decision.direction,
                                "entry_price":        result.price,
                                "slippage_pts":       f"{slippage:.1f}",
                                "lot":                decision.lot,
                                "spread_at_entry":    f"{spread:.0f}",
                                "signal_score":       decision.confidence,
                                "ai_approved":        "YES" if ai_approved else "NO",
                                "equity_after":       f"{equity:.2f}",
                                "pattern_tier":       getattr(decision, 'pattern_tier', 'scalp'),
                                "big_pattern_type":   getattr(decision, 'big_pattern_type', 'NONE'),
                                "small_pattern_type": getattr(decision, 'small_pattern_type', 'NONE'),
                                "consensus_score":   getattr(decision, 'consensus_score', 0.0),
                                "computed_rr":        getattr(decision, 'rr_ratio', 0.0),
                                "invalidation_level": getattr(decision, 'invalidation_level', 0.0),
                            })
                            positions = await loop.run_in_executor(executor, gateway.get_open_positions)

                # ── ROOT CAUSE #1 FIX ─────────────────────────────────────────────
                # Queued signals are processed INDEPENDENTLY of new candidates.
                # Previously this was `elif signal_queue:`, so a queued SELL was
                # starved whenever a fresh BUY candidate kept arriving (the
                # `if candidates:` branch always won). Now a queued SELL is
                # popped and executed every discovery cycle regardless.
                if position_supervisor.signal_queue:
                    # Filter out expired queues (>60s)
                    position_supervisor.signal_queue = [
                        c for c in position_supervisor.signal_queue
                        if time.time() - c.get("time_queued", 0) < 60
                    ]
                    
                    if position_supervisor.signal_queue and len(positions) < max_open_trades_limit and check_cooldown():
                        queued_cand = position_supervisor.signal_queue.pop(0)
                        sym = queued_cand["symbol"]
                        decision = queued_cand["decision"]
                        spread = queued_cand["spread"]
                        session = queued_cand["session"]
                        ai_approved = queued_cand["ai_approved"]
                        
                        if risk.can_trade(session, symbol=sym, current_equity=equity):
                            # Run LLM Trading Analyst Vetting
                            is_reduced_trade = False
                            try:
                                logger.info(f"🤖 [LLM ANALYST] Vetting queued candidate signal: {decision.direction} {sym}...")
                                sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
                                
                                # Get candles_m1 for the candidate (if available) or copy from MT5
                                try:
                                    import MetaTrader5 as mt5
                                    c_m1 = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_M1, 0, 30)
                                    if c_m1 is None:
                                        c_m1 = candles_m1
                                except Exception:
                                    c_m1 = candles_m1
                                    
                                thought, verdict = run_llm_analyst_evaluation(
                                    sym, decision, spread, session, equity, sym_point, 
                                    candles_m5, c_m1, gateway, risk
                                )
                                
                                logger.info(f"🤖 [LLM ANALYST] Verdict: {verdict.get('recommendation', 'reject').upper()} | Reason: {verdict.get('reason_code')}")
                                logger.info(f"🤖 [LLM ANALYST] Thought: {thought}")
                                
                                # Enrich explanation details with LLM's thought block
                                try:
                                    conn_explain_update = sqlite3.connect(os.path.join(BASE_DIR, "data", "explanations.db"))
                                    cursor_update = conn_explain_update.cursor()
                                    cursor_update.execute(
                                        "SELECT id, context_json FROM explanations "
                                        "WHERE symbol = ? AND direction = ? AND action = 'TRADE' "
                                        "ORDER BY id DESC LIMIT 1;", (sym, decision.direction)
                                    )
                                    row_update = cursor_update.fetchone()
                                    if row_update:
                                        row_id = row_update[0]
                                        ctx_update = json.loads(row_update[1] or "{}")
                                        ctx_update["historical_edge"] = verdict.get("historical_edge", "neutral")
                                        ctx_update["microstructure_quality"] = verdict.get("microstructure_quality", "clean")
                                        ctx_update["llm_thought"] = thought
                                        ctx_update["verdict"] = verdict
                                        
                                        cursor_update.execute(
                                            "UPDATE explanations SET plain_english = ?, context_json = ? "
                                            "WHERE id = ?;",
                                            (thought, json.dumps(ctx_update), row_id)
                                        )
                                        conn_explain_update.commit()
                                    conn_explain_update.close()
                                except Exception as explain_up_ex:
                                    logger.debug(f"Failed to enrich explanation with LLM Analyst thought: {explain_up_ex}")
                                    
                                # Process recommendation — 🔬 OBSERVATIONAL ONLY
                                # ── ROOT CAUSE #2 FIX ── The LLM Analyst must NOT
                                # veto queued pattern entries either. Never blocks.
                                llm_recommendation = verdict.get("recommendation", "reject").lower()
                                reason_code = verdict.get("reason_code", "")
                                if llm_recommendation == "reject":
                                    logger.info(
                                        f"🤖 [LLM ANALYST OBSERVATION] queued {decision.direction} {sym} "
                                        f"rec={llm_recommendation} reason={reason_code} — "
                                        f"advisory only, pattern trade proceeds."
                                    )
                                    telegram.send(
                                        f"🤖 <b>[LLM Analyst ADVISORY]</b> Would reject queued "
                                        f"{decision.direction} {sym} (Reason: {reason_code}) — "
                                        f"advisory only, pattern trade proceeds."
                                    )

                                    
                                if llm_recommendation == "approve_reduced":
                                    is_reduced_trade = True
                                    # SAFETY GATE: only scale lot if local model has been trained
                                    # and shadow validation has passed. Flip cfg.llm_analyst_sizing_live
                                    # = True ONLY after shadow_validate_analyst.py sanity checks pass.
                                    if getattr(cfg, 'llm_analyst_sizing_live', False):
                                        old_lot = decision.lot
                                        decision.lot = max(0.01, round(decision.lot * getattr(cfg, 'reduced_size_factor', 0.5), 2))
                                        logger.info(f"\u26a0\ufe0f [LLM ANALYST REDUCED] Queued lot size scaled down from {old_lot} to {decision.lot} (Challenger path).")
                                        telegram.send(f"\U0001f916 <b>[LLM Analyst REDUCED]</b> Queued lot size scaled down to {decision.lot} (Challenger path) for {sym}.")
                                    else:
                                        logger.info(f"\u26a0\ufe0f [LLM ANALYST REDUCED] approve_reduced verdict for queued {sym} — sizing NO-OP (llm_analyst_sizing_live=False). Lot unchanged at {decision.lot}.")
                                        telegram.send(f"\U0001f916 <b>[LLM Analyst REDUCED - SHADOW]</b> Would reduce queued lot for {sym}, but sizing gate is OFF. Reason: {verdict.get('reason_code')}")
                                    
                            except Exception as analyst_err:
                                logger.error(f"Error running LLM Trading Analyst: {analyst_err}", exc_info=True)
                                
                            telegram.send(f"✅ Executing Queued Signal – {decision.direction} {sym} @ {session} (Score: {queued_cand['score']} | Conf: {decision.confidence}%)")

                            # ── Requirement 2: FINAL DECISION IMMUTABILITY before order dispatch ──
                            if not verify_direction_integrity(decision):
                                logger.critical(
                                    f"[DIRECTION INTEGRITY FAILURE] {sym} QUEUED execution ABORTED. "
                                    f"pattern={getattr(decision, 'pattern_direction', 'NA')} "
                                    f"final={decision.direction}. DO NOT TRADE."
                                )
                                telegram.send(
                                    f"🚨 <b>[DIRECTION INTEGRITY FAILURE]</b> Queued trade blocked for {sym}. "
                                    f"Pattern: {getattr(decision, 'pattern_direction', 'NA')} | "
                                    f"Final: {decision.direction}"
                                )
                                continue

                            # ── LIVE TRACE: [{decision.direction}_EXECUTION_TRACE] before queued dispatch ──
                            logger.info(
                                f"[{decision.direction}_EXECUTION_TRACE] symbol={sym} "
                                f"pattern={decision.pattern} "
                                f"pattern_direction={getattr(decision, 'pattern_direction', 'NA')} "
                                f"decision_direction={decision.direction} action={decision.action} "
                                f"sl={decision.sl_points}pts tp={decision.tp_points}pts lot={decision.lot}"
                            )

                            result, latency, slippage = await loop.run_in_executor(
                                executor,
                                gateway.execute_order,
                                sym,
                                decision.direction,
                                decision.lot,
                                decision.tp_points,
                                decision.sl_points,
                            )
                            last_latency = latency

                            # ── LIVE TRACE: [{decision.direction}_MT5_RESULT] after queued dispatch ──
                            _retcode = getattr(result, "retcode", None) if result else None
                            logger.info(
                                f"[{decision.direction}_MT5_RESULT] symbol={sym} "
                                f"retcode={_retcode} "
                                f"ticket={getattr(result, 'order', None) if result else None} "
                                f"order_type={'ORDER_TYPE_SELL' if decision.direction == 'SELL' else 'ORDER_TYPE_BUY'} "
                                f"price={getattr(result, 'price', None) if result else None} "
                                f"sl={decision.sl_points}pts tp={decision.tp_points}pts"
                            )

                            if result:
                                last_trade_time = time.time()
                                last_trade_time_per_sym[sym] = time.time()
                                risk.on_trade_open(session, result.order, direction=decision.direction, symbol=sym)
                                open_trade_symbols[result.order] = sym
                                
                                # If it was an approve_reduced trade, record it in challenger_decisions_by_ticket.json
                                if is_reduced_trade:
                                    try:
                                        import json as _json_chal
                                        chal_ticket_path = os.path.join(BASE_DIR, "data", "challenger_decisions_by_ticket.json")
                                        chal_data = {}
                                        if os.path.exists(chal_ticket_path):
                                            try:
                                                with open(chal_ticket_path, "r") as _tf:
                                                    chal_data = _json_chal.load(_tf)
                                            except Exception:
                                                pass
                                        chal_data[str(result.order)] = True
                                        with open(chal_ticket_path, "w") as _tf:
                                            _json_chal.dump(chal_data, _tf, indent=2)
                                        logger.debug(f"[MODULE2] Labeled ticket {result.order} as Challenger trade.")
                                    except Exception as _e:
                                        logger.error(f"Failed to record challenger ticket: {_e}")
                                        
                                # Save challenger's decision by ticket
                                try:
                                    import json as _json4
                                    shadow_dec_path = os.path.join(BASE_DIR, "data", "challenger_shadow_decisions.json")
                                    ticket_dec_path = os.path.join(BASE_DIR, "data", "challenger_decisions_by_ticket.json")
                                    if os.path.exists(shadow_dec_path):
                                        with open(shadow_dec_path) as _f:
                                            shadow_data = _json4.load(_f)
                                        sym_shadow = shadow_data.get(sym)
                                        if sym_shadow:
                                            ticket_data = {}
                                            if os.path.exists(ticket_dec_path):
                                                try:
                                                    with open(ticket_dec_path) as _tf:
                                                        ticket_data = _json4.load(_tf)
                                                except Exception:
                                                    pass
                                            ticket_data[str(result.order)] = sym_shadow
                                            with open(ticket_dec_path, "w") as _tf:
                                                _json4.dump(ticket_data, _tf, indent=2)
                                except Exception as _e:
                                    logger.error(f"Failed to record challenger decision by ticket: {_e}")
                                
                                perf.log_trade_open(
                                    ticket=result.order, symbol=sym, direction=decision.direction,
                                    entry_price=result.price, sl=decision.sl_points, tp=decision.tp_points,
                                    lot=decision.lot, regime=decision.regime, pattern=decision.pattern,
                                    adx=decision.adx_val, rsi=decision.rsi_val, confidence=decision.confidence,
                                    session=session, atr=decision.atr_estimate,
                                    pattern_tier=getattr(decision, 'pattern_tier', 'scalp'),
                                    big_pattern_type=getattr(decision, 'big_pattern_type', 'NONE'),
                                    small_pattern_type=getattr(decision, 'small_pattern_type', 'NONE'),
                                    consensus_score=getattr(decision, 'consensus_score', 0.0),
                                    computed_rr=getattr(decision, 'rr_ratio', 0.0),
                                    invalidation_level=getattr(decision, 'invalidation_level', 0.0),
                                    pipeline_id="dual_tier_v1"
                                )

                                
                                technique = getattr(decision, 'signal_source', getattr(decision, 'mode', 'SCALP'))
                                telegram.send_trade_open(result, decision, spread, session, symbol=sym, technique=technique)
                                log_trade({
                                    "timestamp":          datetime.now(timezone.utc).isoformat(),
                                    "trade_id":           result.order,
                                    "symbol":             sym,
                                    "mode":               mode,
                                    "session":            session,
                                    "direction":          decision.direction,
                                    "entry_price":        result.price,
                                    "slippage_pts":       f"{slippage:.1f}",
                                    "lot":                decision.lot,
                                    "spread_at_entry":    f"{spread:.0f}",
                                    "signal_score":       decision.confidence,
                                    "ai_approved":        "YES" if ai_approved else "NO",
                                    "equity_after":       f"{equity:.2f}",
                                    "pattern_tier":       getattr(decision, 'pattern_tier', 'scalp'),
                                    "big_pattern_type":   getattr(decision, 'big_pattern_type', 'NONE'),
                                    "small_pattern_type": getattr(decision, 'small_pattern_type', 'NONE'),
                                    "consensus_score":   getattr(decision, 'consensus_score', 0.0),
                                    "computed_rr":        getattr(decision, 'rr_ratio', 0.0),
                                    "invalidation_level": getattr(decision, 'invalidation_level', 0.0),
                                })
                                positions = await loop.run_in_executor(executor, gateway.get_open_positions)

        except Exception as exc:
            logger.exception("Main loop error: %s", exc)
            await asyncio.sleep(2)

        await asyncio.sleep(current_loop_delay)



def _validate_kelly_flag() -> None:
    """
    MODULE 4 — Sequencing Gate (Amendment 2).

    Blocks kelly_sizing=true at startup unless a valid out-of-sample
    backtest report exists AND its CI lower bound exceeds the breakeven
    win rate at the current average R:R.

    On failure: silently forces QX._raw["kelly_sizing"] = False so the bot
    continues trading normally with base-lot sizing. Non-fatal — never
    blocks the loop from starting.
    """
    try:
        from config.quant_x_config import QX
        if not QX.flag("kelly_sizing"):
            return  # Flag is off: nothing to validate

        report_path = os.path.join(BASE_DIR, "data", "backtest_report.json")

        try:
            with open(report_path) as f:
                report = json.load(f)

            lower_bound = report.get("win_rate_ci_lower_bound")
            avg_rr      = report.get("avg_rr", 1.5)

            if lower_bound is None:
                raise ValueError("win_rate_ci_lower_bound missing from report")

            breakeven_wr = 1.0 / (1.0 + float(avg_rr))

            if float(lower_bound) < breakeven_wr:
                logger.error(
                    "[KELLY GATE] kelly_sizing=true but backtest CI lower bound %.1f%% < "
                    "breakeven %.1f%% at RR=%.2f. Forcing kelly_sizing OFF.",
                    float(lower_bound) * 100, breakeven_wr * 100, avg_rr
                )
                QX._raw["kelly_sizing"] = False
            else:
                logger.info(
                    "[KELLY GATE] ✅ Backtest gate passed — CI lower=%.1f%% > breakeven=%.1f%%. "
                    "Kelly sizing ACTIVE.",
                    float(lower_bound) * 100, breakeven_wr * 100
                )

        except FileNotFoundError:
            logger.error(
                "[KELLY GATE] kelly_sizing=true but data/backtest_report.json does not exist. "
                "Run `python -m brain.backtest_runner` first. Forcing kelly_sizing OFF."
            )
            QX._raw["kelly_sizing"] = False

        except Exception as _e:
            logger.error("[KELLY GATE] Backtest validation error: %s. Forcing kelly_sizing OFF.", _e)
            QX._raw["kelly_sizing"] = False

    except Exception as _outer:
        logger.warning("[KELLY GATE] _validate_kelly_flag outer error (non-fatal): %s", _outer)


def main():
    # Process lock to prevent duplicate instances
    LOCK_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "bot.lock")
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)

    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if psutil.pid_exists(old_pid):
                print(f"[LOCK] Another bot instance is running (PID {old_pid}). Exiting.")
                sys.exit(0)
            else:
                print(f"[LOCK] Stale lock found (PID {old_pid} dead). Cleaning up.")
                os.remove(LOCK_FILE)
        except Exception:
            os.remove(LOCK_FILE)

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    import atexit
    def _cleanup_lock():
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass
    atexit.register(_cleanup_lock)

    print("=" * 55)
    print("   AEGIS-GOLD v6.0 ULTRA — AI TRADING BOT")
    print("=" * 55)
    print(f"  Symbol  : {cfg.SYMBOL}")
    print(f"  Mode    : {'DEMO' if cfg.DEMO_MODE else 'LIVE'}")
    print(f"  AI Brain: {'ENABLED' if getattr(cfg, 'USE_AI_SUPERVISOR', True) else 'LOCAL ONLY'}")
    print("=" * 55)

    _ensure_journal()

    # Dashboard handled by serve.js or accessed manually
    # webbrowser.open("http://localhost:5173")

    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    flask_thread = threading.Thread(
        target=lambda: api.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()
    logger.info("Dashboard API running on http://localhost:5001")

    try:
        _validate_kelly_flag()
    except Exception as _kv_ex:
        logger.warning("[KELLY GATE] Validation skipped due to error: %s", _kv_ex)

    # MANDATORY BROKER-SIDE HARD SL FLOOR ASSERTION
    _check_gw = MT5Gateway()
    if not _check_gw.verify_sl_enforcement():
        logger.critical("☠️ [CRITICAL SAFETY FAILURE] Broker-side hard SL enforcement check failed! Refusing to start bot.")
        print("☠️ [CRITICAL SAFETY FAILURE] Broker-side hard SL enforcement check failed! Refusing to start bot.")
        sys.exit(1)

    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    # ACTIVATE ABSOLUTE NEVER PAUSE
    activate_absolute_never_pause()
    main()
