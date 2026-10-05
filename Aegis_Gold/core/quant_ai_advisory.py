"""AEGIS QUANT AI - advisory hook for the legacy engine (additive, DEMO-only).

WHAT THIS IS
    A *read-only observer*.  It runs the Quant-AI pipeline on market data and
    publishes the resulting opinion into ``shared_state["quant_ai"]`` plus a
    JSONL audit trail so a human can compare it against the legacy brain.

WHAT THIS IS NOT
    It never places, modifies or closes an order.  It is not wired into the
    legacy risk gate, the champion/challenger arena, the LLM analyst veto or
    ``gateway`` execution in any way.  Deleting this file and its two call
    sites in ``core/main.py`` returns the engine to its exact prior behaviour.

Safety properties
    * Gated by the ``quant_ai_advisory`` feature flag, default False, re-read
      every cycle so it can be switched on/off at runtime via QX.reload().
    * Every exception is swallowed into a log line + an "error" payload; the
      function cannot raise into the trading loop.
    * Heavy work (model load + inference + MT5 reads) happens in the shared
      executor thread pool under an asyncio timeout, so the 1-second trading
      loop is never blocked by it.
    * Market data is fetched through the read-only MT5 path; nothing is sent.

Audit trail: ``data/quant_ai_advisory.jsonl``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("quant_ai.advisory")

FLAG = "quant_ai_advisory"
_INTERVAL_KEY = "quant_ai_advisory_interval_sec"
_SYMBOLS_KEY = "quant_ai_advisory_symbols"
_TIMEOUT_KEY = "quant_ai_advisory_timeout_sec"
_DEFAULT_INTERVAL = 300.0
_DEFAULT_TIMEOUT = 120.0
_IDLE_SLEEP = 15.0            # poll cadence while the flag is off
_JOURNAL = os.path.join("data", "quant_ai_advisory.jsonl")

_bridge = None                # lazily constructed, reused across cycles
_stats_lock = threading.Lock()
_stats: Dict[str, Any] = {"cycles": 0, "errors": 0, "last_run_ts": 0.0}


# ── helpers ─────────────────────────────────────────────────────────────────
def _flag_on() -> bool:
    """Feature flag, resolved lazily so an absent config cannot break boot."""
    try:
        from config.quant_x_config import QX
        return bool(QX.flag(FLAG))
    except Exception as exc:                      # pragma: no cover
        logger.debug("[QUANT-AI] flag lookup failed, staying off: %s", exc)
        return False


def _cfg(key: str, default):
    try:
        from config.quant_x_config import QX
        val = QX.get(key)
        return default if val is None else val
    except Exception:
        return default


def _bridge_instance():
    """Build the bridge on first use (importing torch/transformers is slow)."""
    global _bridge
    if _bridge is not None:
        return _bridge
    from quant_ai.aegis_bridge import AegisQuantBridge
    _bridge = AegisQuantBridge()
    logger.info("[QUANT-AI] advisory bridge initialised (advisory only, no "
                "order path). models=%s", _bridge.health().get("models_loaded"))
    return _bridge


def _analyze_sync(symbol: str, timeframe: str, equity: float, session: str):
    """Blocking: MT5 read + full pipeline. Runs in the executor thread."""
    sig = _bridge_instance().analyze(symbol, timeframe=timeframe,
                                     equity=equity, session=session)
    return sig.to_dict()


def _append_journal(payload: Dict) -> None:
    try:
        os.makedirs(os.path.dirname(_JOURNAL) or ".", exist_ok=True)
        with open(_JOURNAL, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception as exc:                      # audit trail is best-effort
        logger.debug("[QUANT-AI] advisory journal write failed: %s", exc)


def _publish(state_lock, shared_state: Dict, symbol: str, body: Dict) -> None:
    try:
        with state_lock:
            blk = shared_state.setdefault("quant_ai", {})
            blk[symbol] = body
            blk["_updated"] = body.get("timestamp")
    except Exception as exc:                      # pragma: no cover
        logger.debug("[QUANT-AI] shared_state publish failed: %s", exc)


def _hold_payload(symbol: str, reason: str) -> Dict:
    return {"symbol": symbol, "action": "HOLD", "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(), "mt5": "n/a"}


def _bump(key: str) -> None:
    with _stats_lock:
        _stats[key] = _stats.get(key, 0) + 1


def snapshot(shared_state: Dict) -> Dict:
    """Read-only view for the Flask endpoints."""
    with _stats_lock:
        st = dict(_stats)
    try:
        signals = dict(shared_state.get("quant_ai") or {})
    except Exception:
        signals = {}
    return {"flag": _flag_on(), "stats": st, "signals": signals,
            "trading_mode": "DEMO", "advisory_only": True,
            "places_orders": False}


def _equity(shared_state: Dict) -> float:
    try:
        return float(shared_state.get("equity") or 10_000.0)
    except Exception:
        return 10_000.0


def _session(shared_state: Dict) -> str:
    try:
        return str(shared_state.get("session") or "LONDON")
    except Exception:
        return "LONDON"


# ── background loop ─────────────────────────────────────────────────────────
async def quant_ai_advisory_loop(gateway, loop, executor, shared_state,
                                 state_lock, symbols: Optional[List[str]] = None,
                                 timeframe: str = "M5"):
    """Advisory-only background task. Never raises, never trades."""
    logger.info("[QUANT-AI] advisory observer started (flag '%s' off by default)",
                FLAG)
    while True:
        try:
            if not _flag_on():
                await asyncio.sleep(_IDLE_SLEEP)
                continue

            interval = float(_cfg(_INTERVAL_KEY, _DEFAULT_INTERVAL) or
                             _DEFAULT_INTERVAL)
            timeout = float(_cfg(_TIMEOUT_KEY, _DEFAULT_TIMEOUT) or
                            _DEFAULT_TIMEOUT)
            syms = symbols or _cfg(_SYMBOLS_KEY, None)
            if isinstance(syms, str):
                syms = [syms]
            if not isinstance(syms, (list, tuple)) or not syms:
                # misconfigured flag value must never break the observer
                syms = None
            if not syms:
                try:
                    syms = list(gateway.active_symbols)[:2]
                except Exception:
                    syms = []
            syms = [s for s in (syms or []) if isinstance(s, str) and s]
            if not syms:
                await asyncio.sleep(max(1.0, interval))
                continue

            for sym in (syms or []):
                t0 = time.time()
                try:
                    body = await asyncio.wait_for(
                        loop.run_in_executor(executor, _analyze_sync, sym,
                                             timeframe, _equity(shared_state),
                                             _session(shared_state)),
                        timeout=timeout)
                    _stats["cycles"] += 1
                except asyncio.TimeoutError:
                    body = _hold_payload(sym, f"advisory timed out ({timeout}s)")
                    _bump("errors")
                except Exception as exc:
                    logger.warning("[QUANT-AI] advisory cycle failed for %s: %s",
                                   sym, exc)
                    body = _hold_payload(
                        sym, f"advisory error: {type(exc).__name__}: {exc}")
                    _bump("errors")
                body["cycle_seconds"] = round(time.time() - t0, 2)
                body["advisory_only"] = True
                body["places_orders"] = False
                with _stats_lock:
                    _stats["last_run_ts"] = time.time()
                _publish(state_lock, shared_state, sym, body)
                _append_journal(body)
                logger.info("[QUANT-AI] advisory %s -> %s (%s)", sym,
                            body.get("action"), str(body.get("reason"))[:90])

            await asyncio.sleep(max(1.0, interval))
        except asyncio.CancelledError:
            raise
        except Exception as exc:                  # loop must never die
            _bump("errors")
            logger.warning("[QUANT-AI] advisory loop error (kept alive): %s", exc)
            await asyncio.sleep(_IDLE_SLEEP)

