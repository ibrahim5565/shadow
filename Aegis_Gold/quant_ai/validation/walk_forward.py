"""AEGIS QUANT AI — walk-forward & purged/embargoed validation (Sections 27-28).

WalkForwardEvaluator replays history in chronological order. At each step the
forecaster sees ONLY data before t (no future leakage) and the realized label
is matched with a configurable embargo (label must be fully matured before it
is scored — this prevents overlapping-horizon leakage in rolling performance
tracking, mirroring purged/embargoed CV).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from quant_ai.validation.metrics import (brier_score, directional_accuracy,
                                         mae, rmse)

logger = logging.getLogger("quant_ai.validation.walk_forward")


@dataclass
class WalkForwardResult:
    predictions: List[dict] = field(default_factory=list)
    actuals: List[float] = field(default_factory=list)
    timestamps: List[str] = field(default_factory=list)
    n_scored: int = 0
    excluded_by_embargo: int = 0

    def metrics(self) -> dict:
        scored_rows = [p for p in self.predictions if p.get("scored") and p.get("forecast_price") is not None]
        scored_rows_actual = [p for p in self.predictions if p.get("scored") and p.get("actual") is not None]
        # Origin accounting: how many walk-forward origins were attempted, how
        # many were actually scored, and how many were dropped by the embargo.
        origins = {"n_origins": len(self.predictions),
                   "n_excluded_embargo": self.excluded_by_embargo}
        if not scored_rows_actual:
            return {"n": 0, "mae": None, "rmse": None,
                    "directional_accuracy": None, "brier": None, **origins}
        fc = [p["forecast_price"] for p in scored_rows_actual]
        ac = [p["actual"] for p in scored_rows_actual]
        m = {"n": len(ac), "mae": mae(ac, fc), "rmse": rmse(ac, fc),
             "directional_accuracy": directional_accuracy(ac, fc), **origins}
        prob_rows = [(p.get("probability_up"), p["actual"]) for p in scored_rows_actual
                     if p.get("probability_up") is not None]
        m["brier"] = brier_score([r[0] for r in prob_rows],
                                 [1 if r[1] > 0 else 0 for r in prob_rows]) if prob_rows else None
        for k, v in m.items():
            if isinstance(v, float):
                m[k] = round(v, 6) if k != "directional_accuracy" else round(v, 4)
        return m


class WalkForwardValidator:
    def __init__(self, embargo: int = 1):
        self.embargo = max(0, embargo)

    def evaluate(self, model, df: pd.DataFrame, horizon: int,
                 symbol: str = "XAUUSD", timeframe: str = "M5",
                 min_samples: int = 100, step: int = 1,
                 report: Optional[Callable[[dict], None]] = None) -> WalkForwardResult:
        """Run the forecaster chronologically over `df` (OHLCV indexed by time).

        The model instance must implement predict(df_t, horizon).
        For each t, only df.iloc[:t+1] is passed — future rows are never seen.
        Predictions whose horizon label has not yet matured (embargo) are
        recorded but not scored.
        """
        result = WalkForwardResult()
        n = len(df)
        if n < min_samples + horizon:
            logger.warning("insufficient data for walk-forward (%d < %d + %d)",
                           n, min_samples, horizon)
            return result

        for t in range(min_samples, n - 1, step):
            window = df.iloc[: t + 1]
            try:
                pred = model.predict(window, horizon)
            except Exception as exc:
                logger.warning("walk-forward predict failed at %d: %s", t, exc)
                continue
            if pred.forecast_price is None:
                continue
            label_idx = t + horizon
            if label_idx > n - 1:
                # The label bar does not exist inside this sample, so there is
                # nothing to score and nothing to read. Reading past the end
                # raised IndexError, which made ModelTournament discard the
                # metrics for the WHOLE model. Origins only move forward, so
                # stop here instead.
                break
            # label exists at t+horizon; embargo pushes scoring boundary
            scored = (label_idx + self.embargo) <= (n - 1)
            actual = float(df["close"].iloc[label_idx])
            if scored:
                result.actuals.append(actual)
                if report is not None:
                    # Optional observer payload: the forecast plus the realized
                    # label and its origin, so a caller can audit per-origin
                    # performance. Nothing here feeds back into the model.
                    report({**pred.to_dict(), "actual": actual,
                            "origin_index": int(t),
                            "origin_time": str(window.index[-1])})
            row = {
                "forecast_price": pred.forecast_price,
                "probability_up": pred.probability_up,
                "scored": scored,
                "actual": actual if scored else None,
                "model": pred.model,
                "timestamp": pred.timestamp,
                "horizon": horizon,
            }
            result.predictions.append(row)
            result.timestamps.append(str(window.index[-1]))
        result.n_scored = sum(1 for p in result.predictions if p["scored"])
        result.excluded_by_embargo = len(result.predictions) - result.n_scored
        return result