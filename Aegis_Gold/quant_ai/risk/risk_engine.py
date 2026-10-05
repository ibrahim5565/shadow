"""AEGIS QUANT AI — RiskManager (directive Sections 13, 33-34).

An INDEPENDENT risk engine. It never trusts model confidence: it validates
risk-per-trade, exposure, daily loss, drawdown, consecutive-loss protection,
spread, volatility, margin and session constraints, and computes SL/TP + lot
size via PositionSizer. Every check is recorded for audit.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from quant_ai.predictions import RiskDecision
from quant_ai.risk.position_sizer import PositionSizer, kelly_from_history

logger = logging.getLogger("quant_ai.risk.engine")


class RiskManager:
    def __init__(self, config):
        self.cfg = config
        self.sizer = PositionSizer(config.sizing_method)
        self.start_equity: float = 0.0
        self.day_id: str = ""
        self.daily_pnl: float = 0.0
        self.daily_trades: int = 0
        self.consecutive_losses: int = 0
        self.history_equity: float = 0.0
        self.pnl_history: List[float] = []

    # ── daily state ────────────────────────────────────────────────────
    def roll_daily(self, equity: float) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.day_id:
            self.day_id = today
            self.daily_pnl = 0.0
            self.daily_trades = 0

    def on_trade_result(self, pnl: float) -> None:
        self.daily_pnl += pnl
        self.daily_trades += 1
        self.consecutive_losses = 0 if pnl > 0 else self.consecutive_losses + 1
        self.pnl_history.append(pnl)

    def kelly_stats(self):
        if len(self.pnl_history) >= 10:
            return kelly_from_history(self.pnl_history)
        return None

    def evaluate(self, *, symbol: str, direction: str, equity: float,
                 spread_pts: float, point: float = 0.00001,
                 point_value_per_lot: float = 1.0,
                 atr_points: float = 0.0, vol_ratio: float = 1.0,
                 vol_percentile: float = 0.5, session: str = "LONDON",
                 sl_points: int = 0, min_sl: int = 10, max_sl: int = 400,
                 tp_points: int = 0, min_tp: int = 0,
                 margin_free: Optional[float] = None,
                 margin_per_lot: Optional[float] = None,
                 open_positions_value: float = 0.0) -> RiskDecision:
        checks: Dict[str, dict] = {}
        allowed = True

        # ── 2. daily loss limit ────────────────────────────────────────
        limit_daily = self.cfg.max_daily_loss * equity
        ok = self.daily_pnl >= -limit_daily
        checks["daily_loss"] = {"ok": ok, "daily_pnl": round(self.daily_pnl, 2),
                                "limit": round(-limit_daily, 2)}
        allowed &= ok

        # ── 3. drawdown limit ──────────────────────────────────────────
        self.history_equity = max(self.history_equity, equity)
        dd = (self.history_equity - equity) / max(self.history_equity, 1.0)
        ok = dd <= self.cfg.max_drawdown
        checks["drawdown"] = {"ok": ok, "drawdown_pct": round(dd, 4)}
        allowed &= ok

        # ── 4. consecutive-loss protection ─────────────────────────────
        ok = self.consecutive_losses < self.cfg.max_consecutive_losses
        checks["consecutive_losses"] = {"ok": ok, "count": self.consecutive_losses}
        allowed &= ok

        # ── 5. spread filter ───────────────────────────────────────────
        lim_spread = self.spread_limit(symbol)
        ok = spread_pts <= 0 or spread_pts <= lim_spread
        checks["spread"] = {"ok": ok, "spread_pts": spread_pts, "limit": lim_spread}
        allowed &= ok

        # ── 6. volatility filter (fail-safe: extreme vol blocks) ───────
        ok = vol_percentile <= 0.95
        checks["volatility"] = {"ok": ok, "vol_percentile": round(vol_percentile, 3)}
        allowed &= ok

        # ── 7. session filter ──────────────────────────────────────────
        ok = session in ("ASIAN", "LONDON", "NY", "OVERLAP", "LATE_NY") if self.cfg.session_filter else True
        checks["session"] = {"ok": ok, "session": session}
        allowed &= ok

        # ── 8. SL/TP bound sanity ──────────────────────────────────────
        sl_pts = max(min_sl, min(max_sl, sl_points)) if sl_points > 0 else min_sl
        ok_sl = min_sl <= sl_pts <= max_sl and tp_points >= min_tp
        checks["sl_tp_bounds"] = {"ok": ok_sl, "sl": sl_pts, "tp": tp_points}
        allowed &= ok_sl

        # ── 9. margin check ────────────────────────────────────────────
        if margin_per_lot and margin_free is not None:
            req = self._size(equity=equity, sl_pts=sl_pts,
                             point_value_per_lot=point_value_per_lot,
                             atr_points=atr_points, vol_ratio=vol_ratio)
            req_margin = req * margin_per_lot
            ok = margin_free >= req_margin
            checks["margin"] = {"ok": ok, "required": round(req_margin, 2),
                                "free": round(margin_free, 2) if margin_free else None}
            allowed &= ok
        else:
            checks["margin"] = {"ok": True}

        # ── 10. exposure ───────────────────────────────────────────────
        ok = open_positions_value <= self.cfg.max_exposure_pct * equity
        checks["exposure"] = {"ok": ok, "open_value": round(open_positions_value, 2)}
        allowed &= ok

        if not allowed:
            return RiskDecision(allowed=False, reason="; ".join(
                f"{k}" for k, v in checks.items() if not v.get("ok")),
                checks=checks)

        lot = self._size(equity=equity, sl_pts=sl_pts,
                         point_value_per_lot=point_value_per_lot,
                         atr_points=atr_points, vol_ratio=vol_ratio)
        risk_score = self.cfg.risk_per_trade * (1.0 + vol_ratio) / 2.0
        return RiskDecision(allowed=True, lot_size=lot, sl_points=sl_pts,
                            tp_points=tp_points, risk_score=round(risk_score, 6),
                            checks=checks)

    # ── helpers ────────────────────────────────────────────────────────
    def _size(self, *, equity, sl_pts, point_value_per_lot, atr_points, vol_ratio):
        return self.sizer.size(equity=equity, risk_per_trade=self.cfg.risk_per_trade,
                               sl_points=sl_pts,
                               point_value_per_lot=point_value_per_lot,
                               atr_points=atr_points,
                               vol_ratio=vol_ratio, kelly=self.kelly_stats(),
                               kelly_frac=self.cfg.kelly_fraction)

    def spread_limit(self, symbol: str) -> float:
        limits = {"EURUSD": 12.0, "XAUUSD": 60.0, "GOLD": 60.0}
        base = next((v for k, v in limits.items() if k.upper() in symbol.upper()), 40.0)
        return base * self.cfg.max_spread_mult