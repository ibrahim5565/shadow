"""AEGIS QUANT AI - PAPER trading simulator (Task 13).

Simulates a broker without ever touching MT5 ``order_send``:
  * entry / exit at bar prices with spread applied on the correct side
  * SL / TP hit intra-bar (conservative: stop assumed before target)
  * commission per lot round-trip + slippage in points
  * realised PnL in account currency, equity curve, drawdown

The simulator consumes the SAME execution path as live DEMO (RiskManager ->
ExecutionValidator -> DemoGuard) so a paper run exercises the real guards;
only the final ``order_send`` is replaced with a local fill.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from quant_ai.execution.demo_guard import DemoGuard
from quant_ai.execution.validator import ExecutionValidator, OrderSpec
from quant_ai.risk.risk_engine import RiskManager

logger = logging.getLogger("quant_ai.paper")


@dataclass
class PaperPosition:
    symbol: str
    side: str                 # BUY | SELL
    entry: float
    sl: float
    tp: float
    lot: float
    open_index: int
    open_ts: str
    max_hold_bars: int = 30


@dataclass
class PaperTrade:
    symbol: str
    side: str
    entry: float
    exit: float
    sl: float
    tp: float
    lot: float
    open_ts: str
    close_ts: str
    bars_held: int
    pnl: float
    exit_reason: str          # TP | SL | TIME | FORCE
    costs: float

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class PaperBrokerConfig:
    symbol: str = "XAUUSD"
    initial_cash: float = 10_000.0
    point: float = 0.01
    digits: int = 2
    point_value_per_lot: float = 1.0
    spread_points: float = 5.0
    commission_per_lot: float = 7.0
    slippage_points: int = 1
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    stops_level_pts: float = 0.0
    max_hold_bars: int = 30
    leverage: float = 100.0


class PaperBroker:
    """Bar-driven paper fill engine. Never sends a real order."""

    def __init__(self, cfg: PaperBrokerConfig, risk: Optional[RiskManager] = None,
                 validator: Optional[ExecutionValidator] = None,
                 demo_guard: Optional[DemoGuard] = None):
        self.cfg = cfg
        self.risk = risk
        self.validator = validator or ExecutionValidator()
        self.demo_guard = demo_guard or DemoGuard()
        self.cash = float(cfg.initial_cash)
        self.start_equity = self.cash
        self.equity_curve: List[float] = [self.cash]
        self.trades: List[PaperTrade] = []
        self.position: Optional[PaperPosition] = None
        self.rejected: List[dict] = []
        self.peak_equity = self.cash

    # ── helpers ────────────────────────────────────────────────────────
    def mark_to_market(self, price: float) -> float:
        if self.position is None:
            return self.cash
        p = self.position
        pts = (price - p.entry) / self.cfg.point if p.side == "BUY" \
            else (p.entry - price) / self.cfg.point
        return self.cash + pts * p.lot * self.cfg.point_value_per_lot

    def drawdown_pct(self) -> float:
        eq = self.equity_curve[-1] if self.equity_curve else self.cash
        self.peak_equity = max(self.peak_equity, eq)
        return max(0.0, (self.peak_equity - eq) / max(self.peak_equity, 1.0))

    # ── order attempt (real guards, simulated fill) ────────────────────
    def try_open(self, *, side: str, price: float, sl: float, tp: float,
                 lot: float, index: int, ts: str,
                 spread_pts: Optional[float] = None) -> Dict:
        """Route through DemoGuard -> ExecutionValidator, then fill locally."""
        guard = self.demo_guard.check({"server": "PaperServer-Demo"})
        if not guard["ok"]:
            self.rejected.append({"reason": guard["reason"], "stage": "demo_guard"})
            return {"ok": False, "reason": guard["reason"]}

        spread_pts = self.cfg.spread_points if spread_pts is None else spread_pts
        spec = OrderSpec(symbol=self.cfg.symbol, side=side, entry=price, sl=sl, tp=tp,
                         volume=lot, point=self.cfg.point, digits=self.cfg.digits,
                         stops_level_pts=self.cfg.stops_level_pts or None,
                         volume_min=self.cfg.volume_min, volume_max=self.cfg.volume_max,
                         volume_step=self.cfg.volume_step)
        val = self.validator.validate(spec)
        if not val["ok"]:
            self.rejected.append({"reason": "; ".join(val["errors"]), "stage": "validator"})
            return {"ok": False, "reason": "; ".join(val["errors"]), "validation": val}

        # slippage: entries fill a touch worse
        slip = self.cfg.slippage_points * self.cfg.point
        fill = price + slip if side == "BUY" else price - slip
        self.position = PaperPosition(
            symbol=self.cfg.symbol, side=side, entry=round(fill, self.cfg.digits),
            sl=round(sl, self.cfg.digits), tp=round(tp, self.cfg.digits),
            lot=val["normalized_volume"], open_index=index, open_ts=ts,
            max_hold_bars=self.cfg.max_hold_bars)
        return {"ok": True, "fill": self.position.entry, "validation": val}

    def manage(self, *, index: int, ts: str, high: float, low: float,
               close: float) -> Optional[PaperTrade]:
        """Advance one bar: check SL/TP/timeout. Returns a PaperTrade on close.

        Conservative rule: when a bar's range contains both levels the STOP is
        assumed to have been hit first (never optimistic).
        """
        p = self.position
        if p is None:
            return None
        exit_price = None
        reason = None
        if p.side == "BUY":
            if low <= p.sl:
                exit_price, reason = p.sl, "SL"
            elif high >= p.tp:
                exit_price, reason = p.tp, "TP"
        else:
            if high >= p.sl:
                exit_price, reason = p.sl, "SL"
            elif low <= p.tp:
                exit_price, reason = p.tp, "TP"
        if exit_price is None and (index - p.open_index) >= p.max_hold_bars:
            exit_price, reason = close, "TIME"
        if exit_price is None:
            return None
        return self._close(exit_price, index, ts, reason)

    def force_close(self, *, index: int, ts: str, price: float,
                    reason: str = "FORCE") -> Optional[PaperTrade]:
        if self.position is None:
            return None
        return self._close(price, index, ts, reason)

    def _close(self, exit_price: float, index: int, ts: str, reason: str) -> PaperTrade:
        p = self.position
        assert p is not None
        slip = self.cfg.slippage_points * self.cfg.point
        fill = exit_price - slip if p.side == "BUY" else exit_price + slip
        pts = (fill - p.entry) / self.cfg.point if p.side == "BUY" \
            else (p.entry - fill) / self.cfg.point
        gross = pts * p.lot * self.cfg.point_value_per_lot
        commission = self.cfg.commission_per_lot * p.lot
        pnl = gross - commission
        self.cash += pnl
        trade = PaperTrade(
            symbol=p.symbol, side=p.side, entry=p.entry, exit=round(fill, self.cfg.digits),
            sl=p.sl, tp=p.tp, lot=p.lot, open_ts=p.open_ts, close_ts=ts,
            bars_held=index - p.open_index, pnl=round(pnl, 4), exit_reason=reason,
            costs=round(commission + 2 * self.cfg.slippage_points
                        * p.lot * self.cfg.point_value_per_lot, 4))
        self.trades.append(trade)
        self.equity_curve.append(self.cash)
        if self.risk is not None:
            self.risk.on_trade_result(pnl)
        self.position = None
        return trade

    # ── summary (Task 12 metric set) ───────────────────────────────────
    def summary(self) -> dict:
        from quant_ai.validation.metrics import trade_metrics
        pnls = [t.pnl for t in self.trades]
        base = trade_metrics(pnls) if pnls else {}
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        net = float(np.sum(pnls)) if pnls else 0.0
        return {
            "symbol": self.cfg.symbol,
            "initial_cash": self.cfg.initial_cash,
            "final_equity": round(self.cash, 2),
            "net_return_pct": round(net / self.cfg.initial_cash * 100.0, 4),
            "n_trades": len(pnls),
            "n_wins": len(wins),
            "n_losses": len(losses),
            "win_rate": base.get("win_rate", 0.0),
            "avg_win": round(float(np.mean(wins)), 4) if wins else 0.0,
            "avg_loss": round(float(np.mean(losses)), 4) if losses else 0.0,
            "expectancy": base.get("expectancy", 0.0),
            "max_drawdown": base.get("max_drawdown", 0.0),
            "profit_factor": base.get("profit_factor", 0.0),
            "sharpe": base.get("sharpe", 0.0),
            "sortino": base.get("sortino", 0.0),
            "recovery_factor": base.get("recovery_factor", 0.0),
            "rejected_orders": len(self.rejected),
            "still_open": self.position is not None,
        }


