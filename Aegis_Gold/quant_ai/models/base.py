"""AEGIS QUANT AI — BaseModelAdapter.

Contract every adapter must satisfy. Adapts a model's native input/output to
the canonical ModelPrediction schema (directive Section 23).  Models that do
not output probabilities leave them None.
"""
from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional

import pandas as pd

from quant_ai.predictions import ModelPrediction


class BaseModelAdapter(abc.ABC):
    """Interface for a single pretrained-model adapter.

    Subclasses must implement load(), predict(), health() and unload().
    They should be import-safe: the module may import even if the underlying
    model library is missing; load() then returns False and predict()
    returns MODEL_UNAVAILABLE.
    """

    name: str = "base"
    tier: int = 3
    min_history: int = 64
    max_context: int = 512

    def __init__(self, symbol: str = "XAUUSD", timeframe: str = "M5",
                 device: Optional[str] = None, max_context: Optional[int] = None):
        self.symbol = symbol
        self.timeframe = timeframe
        self.device = device
        if max_context is not None:
            self.max_context = max_context
        self._loaded = False

    # ── lifecycle ──────────────────────────────────────────────────────
    @abc.abstractmethod
    def load(self) -> bool:
        """Load weights into memory exactly once. Return success."""

    def unload(self) -> None:
        """Release memory (drop references, clear cache)."""
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── inference ──────────────────────────────────────────────────────
    @abc.abstractmethod
    def predict(self, df: pd.DataFrame, horizon: int, **kwargs) -> ModelPrediction:
        """Produce a canonical ModelPrediction from an OHLCV DataFrame.

        Must never raise on bad input: return a prediction with an explicit
        status (INSUFFICIENT_DATA / INFERENCE_ERROR / MODEL_UNAVAILABLE).
        """

    # ── health ─────────────────────────────────────────────────────────
    @abc.abstractmethod
    def health(self) -> dict:
        """Return dict with keys: loaded, weights_available, detail."""

    # ── helpers ────────────────────────────────────────────────────────
    @staticmethod
    def _valid_df(df: pd.DataFrame, min_rows: Optional[int] = None) -> bool:
        if df is None or len(df) == 0:
            return False
        need = min_rows or 4
        if len(df) < need:
            return False
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                return False
        values = df[["open", "high", "low", "close"]]
        if values.isnull().values.any():
            return False
        if values.shape[0] < need or not values.iloc[-1]["close"] > 0:
            return False
        return True

    @staticmethod
    def closed_prediction(model: str, symbol: str, timeframe: str, now_iso: str,
                          detail: str) -> ModelPrediction:
        from quant_ai.predictions import PredictionStatus
        return ModelPrediction(model=model, symbol=symbol, timeframe=timeframe,
                               timestamp=now_iso, status=PredictionStatus.MODEL_UNAVAILABLE,
                               detail=detail)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.name} loaded={self._loaded}>"