"""AEGIS QUANT AI - integration bridge into the existing AEGIS engine (Task 14).

This is the ONLY module that touches the legacy system.  It is ADDITIVE:
nothing in ``brain/``, ``core/``, ``modules/`` or ``config/`` is modified.

The bridge:
  * fetches OHLCV from MT5 (read-only),
  * runs the QuantAIPipeline,
  * returns a normalised signal object for the legacy brain to log/inspect,
  * NEVER calls ``mt5.order_send`` - execution stays with the legacy gateway,
    which performs its own RiskManager + ExecutionValidator + DemoGuard checks.

If MT5 is unavailable the bridge returns a HOLD signal with an explicit
reason (offline operation, Task 10).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from quant_ai.config import QAIConfig
from quant_ai.pipeline import QuantAIPipeline, symbol_profile
from quant_ai.storage.db import QuantAIStore

logger = logging.getLogger("quant_ai.aegis_bridge")

# timeframe name -> MT5 constant name
_TF_MAP = {
    "M1": "TIMEFRAME_M1", "M5": "TIMEFRAME_M5", "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


@dataclass
class QuantAISignal:
    """Normalised, advisory signal for the legacy AEGIS engine."""
    symbol: str
    timeframe: str
    action: str                     # BUY | SELL | HOLD
    reason: str
    timestamp: str
    price: Optional[float] = None
    lot: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    sl_points: int = 0
    tp_points: int = 0
    regime: str = ""
    volatility: Dict = field(default_factory=dict)
    anomaly: Dict = field(default_factory=dict)
    risk: Dict = field(default_factory=dict)
    ensemble: Dict = field(default_factory=dict)
    members: List[dict] = field(default_factory=list)
    llm_reasoning: Optional[Dict] = None
    validation: Dict = field(default_factory=dict)
    demo_guard: Dict = field(default_factory=dict)
    mt5: str = "unknown"            # connected | unavailable | n/a

    def to_dict(self) -> dict:
        return dict(self.__dict__)

    @property
    def tradable(self) -> bool:
        return self.action in ("BUY", "SELL") and bool(self.validation.get("ok"))


def fetch_mt5_history(symbol: str, timeframe: str, bars: int = 600,
                      mt5_module=None) -> Optional[pd.DataFrame]:
    """Read-only OHLCV fetch from the running MT5 terminal. Returns None on
    any failure so the caller degrades to HOLD (never crashes)."""
    try:
        if mt5_module is None:
            import MetaTrader5 as mt5_module          # noqa: F811
        tf_name = _TF_MAP.get(timeframe.upper())
        if tf_name is None:
            logger.warning("unknown timeframe %s", timeframe)
            return None
        tf = getattr(mt5_module, tf_name)
        if not mt5_module.initialize():
            logger.warning("MT5 initialize() failed")
            return None
        rates = mt5_module.copy_rates_from_pos(symbol, tf, 0, int(bars))
        if rates is None or len(rates) == 0:
            logger.warning("MT5 returned no rates for %s %s", symbol, timeframe)
            return None
        df = pd.DataFrame(rates)
        df = df.rename(columns={"tick_volume": "volume"})
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.set_index("time")
        return df[["open", "high", "low", "close", "volume"]]
    except Exception as exc:
        logger.error("MT5 history fetch failed: %s", exc)
        return None


class AegisQuantBridge:
    """Adapter exposing the Quant-AI decision to the legacy AEGIS engine."""

    def __init__(self, config: Optional[QAIConfig] = None,
                 store: Optional[QuantAIStore] = None,
                 pipeline: Optional[QuantAIPipeline] = None,
                 llm=None, mt5_module=None):
        self.cfg = config or QAIConfig()
        self.pipeline = pipeline or QuantAIPipeline(config=self.cfg, store=store,
                                                    llm=llm)
        self.mt5 = mt5_module
        self.last_signal: Optional[QuantAISignal] = None

    # ── data acquisition ───────────────────────────────────────────────
    def load_history(self, symbol: str, timeframe: str, bars: int = 600,
                     df: Optional[pd.DataFrame] = None):
        """Return (df, source). ``source`` is 'provided' | 'mt5' | 'unavailable'."""
        if df is not None:
            return df, "provided"
        got = fetch_mt5_history(symbol, timeframe, bars=bars, mt5_module=self.mt5)
        if got is None:
            return None, "unavailable"
        return got, "mt5"

    # ── main entry ─────────────────────────────────────────────────────
    def analyze(self, symbol: str, timeframe: str = "M5", *,
                bars: int = 600, equity: float = 10_000.0,
                spread_pts: float = 0.0, session: str = "LONDON",
                headlines: Optional[List[str]] = None,
                df: Optional[pd.DataFrame] = None) -> QuantAISignal:
        """Run the full pipeline; always returns a signal (HOLD on failure)."""
        now = datetime.now(timezone.utc).isoformat()
        prof = symbol_profile(symbol)
        if spread_pts <= 0:
            spread_pts = prof["spread_points"]

        data, source = self.load_history(symbol, timeframe, bars=bars, df=df)
        if data is None:
            sig = QuantAISignal(symbol=symbol, timeframe=timeframe, action="HOLD",
                                reason="MT5 market data unavailable (offline)",
                                timestamp=now, mt5="unavailable")
            self.last_signal = sig
            return sig

        decision = self.pipeline.decide(
            data, symbol=symbol, timeframe=timeframe, equity=equity,
            spread_pts=spread_pts, session=session, headlines=headlines)

        sig = QuantAISignal(
            symbol=symbol, timeframe=timeframe,
            action=decision.action, reason=decision.reason, timestamp=now,
            regime=decision.regime, volatility=decision.volatility,
            anomaly=decision.anomaly, risk=decision.risk,
            validation=decision.validation, demo_guard=decision.demo_guard,
            mt5="connected" if source == "mt5" else "n/a")
        if decision.action in ("BUY", "SELL"):
            pos = decision.position or {}
            sig.price = pos.get("entry")
            sig.lot = float(pos.get("lot", 0.0) or 0.0)
            sig.sl = float(pos.get("sl", 0.0) or 0.0)
            sig.tp = float(pos.get("tp", 0.0) or 0.0)
            sig.sl_points = int(pos.get("sl_points", 0) or 0)
            sig.tp_points = int(pos.get("tp_points", 0) or 0)
            ens = (decision.predictions or {}).get("ensemble")
            if ens:
                sig.ensemble = {"forecast_return": ens.get("forecast_return"),
                                "uncertainty": ens.get("uncertainty")}
                raw = ens.get("raw") or {}
                if isinstance(raw, dict):
                    sig.members = raw.get("members", [])
        sig.llm_reasoning = getattr(decision, "reason_llm", None)
        self.last_signal = sig
        return sig

    # ── introspection ──────────────────────────────────────────────────
    def health(self) -> dict:
        h = self.pipeline.health()
        from quant_ai.config import ALLOW_LIVE_TRADING, TRADING_MODE
        h["trading_mode"] = TRADING_MODE
        h["allow_live_trading"] = ALLOW_LIVE_TRADING
        h["mt5_bridge"] = "module bound" if self.mt5 is not None else "lazy import"
        return h

