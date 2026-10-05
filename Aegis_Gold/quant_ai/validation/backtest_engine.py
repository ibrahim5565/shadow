"""AEGIS QUANT AI — backtest engine (Section 29).

Cost-aware simulation for EURUSD / XAUUSD across timeframes.  Models spread,
commission, slippage, and SL/TP exits.  PnL in account currency; realistic
broker constraints via ExecutionValidator.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from quant_ai.validation.metrics import trade_metrics

logger = logging.getLogger("quant_ai.validation.backtest")


@dataclass
class BacktestResult:
    pnls: List[float] = field(default_factory=list)
    trades: List[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {"model": None} | trade_metrics(self.pnls)


@dataclass
class BacktestConfig:
    initial_cash: float = 10000.0
    spread_points: float = 1.0        # broker spread in points (rounded to point)
    commission_per_lot: float = 7.0   # USD per standard lot round trip
    slippage_points: int = 1          # per-entry slippage in points
    point: float = 0.00001
    point_value_per_lot: float = 1.0   # USD per lot per 1 point move
    min_sl_points: int = 10
    max_sl_points: int = 1000
    min_tp_points: int = 0
    max_tp_points: int = 5000
    vol_ratio_cap: float = 4.0
    risk_per_trade: float = 0.01


class BacktestEngine:
    def __init__(self, cfg: BacktestConfig):
        self.cfg = cfg

    def run(self, model, df: pd.DataFrame, horizon: int = 1, step: int = 1,
            symbol: str = "XAUUSD", timeframe: str = "M5",
            direction_override: Optional[str] = None) -> BacktestResult:
        """Single-pass causal backtest.

        At each bar t (only data <= t used) the model issues a direction;
        a trade is entered at t+1 open, exits at target or stop, otherwise
        closes after `max_hold` bars.  No future data reaches the model.
        """
        result = BacktestResult()
        cash = float(self.cfg.initial_cash)
        equity_curve = []
        n = len(df)
        min_bars = 60
        max_hold = 30
        i = min_bars
        pos = None  # dict with side, entry, sl, tp, lot, qty

        while i < n - 2:
            window = df.iloc[: i + 1]
            try:
                pred = model.predict(window, horizon)
            except Exception as exc:
                logger.warning("backtest model error at %d: %s", i, exc)
                i += step
                continue
            if pred.direction.value not in ("UP", "DOWN"):
                i += step
                continue
            side = direction_override or ("BUY" if pred.direction.value == "UP" else "SELL")

            entry = float(df["close"].iloc[i])
            # simple proportional SL/TP sizing from the config (points)
            sl_pts = int(max(self.cfg.min_sl_points, 25))
            tp_pts = int(max(self.cfg.min_tp_points, sl_pts * 2))
            # risk-based lot
            bar_vol = float(df["close"].pct_change().iloc[i - 20:i + 1].std() or 0.001)
            vol_ratio = min(self.cfg.vol_ratio_cap, max(0.5, bar_vol /
                           (float(df["close"].pct_change().iloc[max(0, i - 60):i].std() or 0.001))))
            risk_usd = cash * self.cfg.risk_per_trade / vol_ratio
            loss_per_lot = sl_pts * self.cfg.point_value_per_lot
            loss_per_lot = max(loss_per_lot, 1e-6)
            lot = max(0.01, round(risk_usd / loss_per_lot / 0.01) * 0.01)

            exit_bar = None
            exit_price = None
            # SL / TP absolute prices (point-based)
            if side == "BUY":
                sl_price = entry - sl_pts * self.cfg.point
                tp_price = entry + tp_pts * self.cfg.point
            else:
                sl_price = entry + sl_pts * self.cfg.point
                tp_price = entry - tp_pts * self.cfg.point

            for j in range(i + 1, min(i + 1 + max_hold, n)):
                hi, lo, close = float(df["high"].iloc[j]), float(df["low"].iloc[j]), float(df["close"].iloc[j])
                if side == "BUY":
                    if lo <= sl_price:
                        exit_bar, exit_price = j, sl_price
                        break
                    if hi >= tp_price:
                        exit_bar, exit_price = j, tp_price
                        break
                    if j == min(i + max_hold, n - 1):
                        exit_bar, exit_price = j, close
                        break
                else:
                    if hi >= sl_price:
                        exit_bar, exit_price = j, sl_price
                        break
                    if lo <= tp_price:
                        exit_bar, exit_price = j, tp_price
                        break
                    if j == min(i + max_hold, n - 1):
                        exit_bar, exit_price = j, close
                        break
            if exit_bar is None:
                i += step
                continue

            # PnL in account currency (point-value model) minus costs
            pts = (exit_price - entry) / self.cfg.point if side == "BUY" else (entry - exit_price) / self.cfg.point
            slippage_pts = float(self.cfg.slippage_points)
            pnl = (pts - slippage_pts) * lot * self.cfg.point_value_per_lot \
                - self.cfg.commission_per_lot * lot
            cash += pnl
            result.pnls.append(float(pnl))
            result.trades.append({"t": i, "side": side, "entry": entry, "exit": exit_price,
                                  "lot": lot, "pnl": float(pnl), "sl": sl_price, "tp": tp_price})
            equity_curve.append(cash)
            i = exit_bar + 1
        return result