"""AEGIS QUANT AI — naive / statistical baselines (directive Section 30).

These are not "AI", but they are the minimum bar every AI model must beat:
  previous_close, random_walk (seeded), momentum, simple_moving_average,
  ema_trend, rsi_baseline.
They implement the same BaseModelAdapter interface so the tournament can score
them side by side, and each is labelled `name = baseline_<kind>`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from quant_ai.models.base import BaseModelAdapter
from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus

logger = logging.getLogger("quant_ai.models.baselines")

BASELINE_KINDS = ("previous_close", "random_walk", "momentum", "sma", "ema_trend", "rsi_baseline")


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    return 100.0 - 100.0 / (1.0 + rs)


class NaiveBaseline(BaseModelAdapter):
    name = "baseline"
    tier = 3
    min_history = 10

    def __init__(self, kind: str = "previous_close", symbol: str = "XAUUSD",
                 timeframe: str = "M5", device=None):
        if kind not in BASELINE_KINDS:
            raise ValueError(f"unknown baseline kind {kind!r}")
        super().__init__(symbol=symbol, timeframe=timeframe, device=device)
        self.kind = kind
        self.name = f"baseline_{kind}"       # distinct label per baseline kind
        self._loaded = True  # baselines are always "loaded"

    def load(self) -> bool:
        self._loaded = True
        return True

    # NOTE: baseline direction uses only data available up to t-1 (no leakage).
    def predict(self, df: pd.DataFrame, horizon: int, **kwargs) -> ModelPrediction:
        now = datetime.now(timezone.utc).isoformat()
        closes = df["close"].astype(float)
        last = float(closes.iloc[-1])
        sr = closes.copy()
        path = np.full(horizon, last)

        if self.kind == "previous_close":
            pass
        elif self.kind == "random_walk":
            rng = np.random.default_rng(20260909)
            steps = rng.normal(0, float(closes.pct_change().dropna().std()), horizon)
            path = last * np.cumprod(1 + steps)
            path /= path[0] / last
        elif self.kind == "momentum":
            k = min(5, len(closes))
            mom = float((closes.iloc[-1] / closes.iloc[-1 - k] - 1.0) / k)
            path = last * (1.0 + mom) ** np.arange(1, horizon + 1)
        elif self.kind == "sma":
            window = min(20, len(closes))
            mean_last = float(closes.iloc[-window:].mean())
            drift = (mean_last - last) / window
            path = last + drift * np.arange(1, horizon + 1)
        elif self.kind == "ema_trend":
            e = ema(closes, span=10)
            drift = float(e.iloc[-1] - e.iloc[-6]) / 5.0
            path = last + drift * np.arange(1, horizon + 1)
        elif self.kind == "rsi_baseline":
            r = rsi(closes)
            r_now = float(r.iloc[-1])
            drift = 0.0
            if r_now < 30.0:
                drift = float(closes.pct_change().dropna().std())
            elif r_now > 70.0:
                drift = -float(closes.pct_change().dropna().std())
            path = last * (1.0 + drift) ** np.arange(1, horizon + 1)

        ret = (float(path[-1]) - last) / last
        direction = Direction.UP if ret > 0.00025 else Direction.DOWN if ret < -0.00025 else Direction.FLAT
        return ModelPrediction(
            model=f"baseline_{self.kind}", symbol=self.symbol, timeframe=self.timeframe,
            timestamp=now, forecast_price=float(path[-1]), forecast_return=float(ret),
            direction=direction, probability_up=None, probability_down=None,
            uncertainty=None, forecast_horizon=horizon, latency_ms=0.0,
            status=PredictionStatus.OK, prices_path=[float(x) for x in path], raw={"kind": self.kind})

    def health(self) -> dict:
        return {"loaded": True, "weights_available": False, "vendor_present": True,
                "detail": f"statistical baseline ({self.kind})"}


def all_baselines(symbol: str = "XAUUSD", timeframe: str = "M5") -> list:
    return [NaiveBaseline(kind=k, symbol=symbol, timeframe=timeframe) for k in BASELINE_KINDS]