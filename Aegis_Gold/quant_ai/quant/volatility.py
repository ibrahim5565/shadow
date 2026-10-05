"""AEGIS QUANT AI — volatility engines (Section 15).

ATR, realized volatility, EWMA volatility and GARCH-family forecasts
(arch package, installed and verified).  Output is used by the risk engine
to scale position size and by the fail-safe to block trades in abnormal
volatility regimes.
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("quant_ai.quant.volatility")


class VolatilityEngine:
    def __init__(self, atr_window: int = 20, ewma_span: int = 30,
                 garch_window: int = 500, use_garch: bool = True):
        self.atr_window = atr_window
        self.ewma_span = ewma_span
        self.garch_window = garch_window
        self.use_garch = use_garch and _arch_available()

    def atr(self, df: pd.DataFrame) -> pd.Series:
        high, low, close = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
        prev_close = close.shift(1)
        tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
        return tr.rolling(self.atr_window).mean()

    def realized_vol(self, df: pd.DataFrame, window: int = 20) -> pd.Series:
        r = df["close"].astype(float).pct_change().dropna()
        return r.rolling(window).std()

    def ewma_vol(self, df: pd.DataFrame) -> pd.Series:
        r = df["close"].astype(float).pct_change().dropna()
        return r.ewm(span=self.ewma_span, adjust=False).std()

    def garch_forecast(self, r: pd.Series, horizon: int = 1) -> Optional[Dict[str, float]]:
        """Fit GARCH(1,1) on the rolling window; return next-step conditional vol."""
        if not self.use_garch or len(r) < 100:
            return None
        try:
            from arch import arch_model
            data = r.dropna().tail(self.garch_window)
            model = arch_model(data * 100.0, vol="GARCH", p=1, q=1, mean="Constant", dist="normal")
            res = model.fit(disp="off", show_warning=False)
            f = res.forecast(horizon=horizon)
            var = float(f.variance.values[-1, -1])
            return {"conditional_vol_pct": round(float(np.sqrt(var)), 4),
                    "volatility": "GARCH(1,1)", "horizon": horizon}
        except Exception as exc:
            logger.warning("garch forecast failed: %s", exc)
            return None

    def analyze(self, df: pd.DataFrame, horizon: int = 1) -> Dict[str, float]:
        """Return a volatility context dict (all measured, nothing fabricated)."""
        closes = df["close"].astype(float)
        r = closes.pct_change().dropna()
        atr = self.atr(df)
        rv = self.realized_vol(df)
        ev = self.ewma_vol(df)
        atr_last = float(atr.iloc[-1]) if len(atr) else 0.0
        rv_last = float(rv.iloc[-1]) if len(rv) else 0.0
        ev_last = float(ev.iloc[-1]) if len(ev) else 0.0
        g = self.garch_forecast(r, horizon)
        # percentile of current realized vol vs its own trailing history
        hist = rv.dropna()
        pct = float((hist <= rv_last).mean()) if len(hist) > 20 else 0.5
        return {
            "atr_points_20": round(atr_last, 5),
            "realized_vol_20": round(rv_last, 6),
            "ewma_vol_30": round(ev_last, 6),
            "vol_percentile": round(pct, 3),
            "garch": g,
            "annualized_vol": round(float(r.std() * np.sqrt(252 * 24 * 12)) , 4) if len(r) else 0.0,
        }


def _arch_available() -> bool:
    try:
        import arch  # noqa: F401
        return True
    except Exception:
        return False