"""AEGIS QUANT AI — market regime engine (Section 16).

Detected regimes:
  TRENDING_UP / TRENDING_DOWN / RANGING / HIGH_VOLATILITY / LOW_VOLATILITY /
  BREAKOUT / MEAN_REVERSION / UNCERTAIN
Method: transparent rule-based combination of trend strength (linear slope,
ADX), volatility percentile, and return autocorrelation (mean reversion),
plus a breakout check.  No fabricated probabilities: every label is a
consequence of the listed statistics.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd

from quant_ai.quant.factors import adx

logger = logging.getLogger("quant_ai.quant.regime")


@dataclass
class RegimeReport:
    regime: str
    trend_strength: float          # |slope| normalized
    trend_direction: str           # UP / DOWN / FLAT
    vol_percentile: float
    autocorr_1: float
    breakout_score: float
    reasons: List[str]

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class RegimeEngine:
    def __init__(self, trend_window: int = 40, vol_window: int = 20):
        self.trend_window = trend_window
        self.vol_window = vol_window

    def detect(self, df: pd.DataFrame, vol_percentile: float = 0.5,
               vol_block_mult: float = 4.0) -> RegimeReport:
        closes = df["close"].astype(float)
        highs, lows = df["high"].astype(float), df["low"].astype(float)

        reasons: List[str] = []
        n = len(closes)
        # 1. trend strength via linear slope of last window
        y = closes.iloc[-self.trend_window:].values.astype(float)
        x = np.arange(len(y), dtype=float)
        slope = float(np.polyfit(x, y, 1)[0])
        trend_strength = abs(slope) / (float(closes.iloc[-1]) + 1e-12)
        direction = "UP" if slope > 0 else "DOWN" if slope < 0 else "FLAT"

        # 2. ADX directional index (trading range)
        adx_val = float(adx(highs, lows, closes).iloc[-1]) if n > 30 else 0.0

        # 3. breakout detection: last close beyond recent extreme with volume
        hi_10 = float(highs.iloc[-10:].max())
        lo_10 = float(lows.iloc[-10:].min())
        last = float(closes.iloc[-1])
        breakout_score = 0.0
        if last > hi_10 and n > 10:
            breakout_score = (last - hi_10) / (hi_10 - lo_10 + 1e-9)
        elif last < lo_10 and n > 10:
            breakout_score = (lo_10 - last) / (hi_10 - lo_10 + 1e-9)

        # 4. mean reversion via autocorrelation of returns
        r = closes.pct_change().dropna()
        autocorr = float(r.tail(self.trend_window).autocorr()) if len(r) > 5 else 0.0

        regime = "UNCERTAIN"
        if breakout_score > 0.05 and adx_val > 20:
            regime = "BREAKOUT"
            reasons.append(f"breakout_score={breakout_score:.3f}")
        elif adx_val > 25 and trend_strength > 1e-6 and direction != "FLAT":
            regime = f"TRENDING_{direction}"
            reasons.append(f"adx={adx_val:.1f} slope_norm={trend_strength:.2e}")
        elif autocorr < -0.25:
            regime = "MEAN_REVERSION"
            reasons.append(f"autocorr={autocorr:.2f}")
        elif abs(trend_strength) < 1e-6 or adx_val < 20:
            regime = "RANGING"
            reasons.append(f"adx={adx_val:.1f}")
        regime = self._apply_volatility(regime, vol_percentile, vol_block_mult, reasons)
        return RegimeReport(regime=regime, trend_strength=round(trend_strength, 8),
                            trend_direction=direction, vol_percentile=round(float(vol_percentile), 3),
                            autocorr_1=round(autocorr, 3), breakout_score=round(float(breakout_score), 4),
                            reasons=reasons)

    @staticmethod
    def _apply_volatility(regime: str, vol_pct: float, block_mult: float, reasons: List[str]) -> str:
        if vol_pct >= 0.95:
            reasons.append(f"vol_percentile={vol_pct:.2f} (HIGH_VOLATILITY)")
            return "HIGH_VOLATILITY"
        if vol_pct <= 0.15:
            reasons.append(f"vol_percentile={vol_pct:.2f} (LOW_VOLATILITY)")
            return "LOW_VOLATILITY"
        return regime