"""AEGIS QUANT AI — TimesFM adapter (google-research/timesfm, Apache-2.0).

Requires `pip install timesfm` (pulls JAX).  Disabled by default in QAIConfig.
Reports MODEL_UNAVAILABLE honestly when the package is absent.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from quant_ai.models.base import BaseModelAdapter
from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus

logger = logging.getLogger("quant_ai.models.timesfm")

_AVAILABLE = True
try:
    from timesfm import TimesFm  # noqa: F401  (v1/v2 API)
except Exception:
    _AVAILABLE = False


class TimesFMAdapter(BaseModelAdapter):
    name = "timesfm"
    tier = 2
    min_history = 128

    def __init__(self, model_name: str = "google/timesfm-2.0-200m-pytorch",
                 symbol: str = "XAUUSD", timeframe: str = "M5", device=None):
        super().__init__(symbol=symbol, timeframe=timeframe, device=device, max_context=512)
        self.model_name = model_name
        self._model = None

    def load(self) -> bool:
        if self._loaded:
            return True
        if not _AVAILABLE:
            logger.warning("timesfm not installed; run `pip install timesfm`")
            return False
        try:
            from timesfm import TimesFm
            self._model = TimesFm(backend="gpu" if self.device else "cpu",
                                  checkpoint_path=self.model_name, mode=1, context_len=512, horizon_len=128)
            self._loaded = True
            return True
        except Exception as exc:
            logger.error("timesfm load failed: %s", exc)
            return False

    def predict(self, df: pd.DataFrame, horizon: int, **kwargs) -> ModelPrediction:
        now = datetime.now(timezone.utc).isoformat()
        if not self._loaded:
            self.load()
        if not self._loaded:
            return self.closed_prediction(self.name, self.symbol, self.timeframe, now,
                                          "timesfm package not installed")
        if not self._valid_df(df, self.min_history):
            return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                                   timestamp=now, status=PredictionStatus.INSUFFICIENT_DATA,
                                   detail="insufficient history")
        try:
            context = df["close"].astype(np.float32).values[-self.max_context:]
            out = self._model.forecast([context], [horizon])
            path = np.asarray(out[0][0], dtype=float)          # (horizon,)
            quantiles = np.asarray(out[0][1], dtype=float) if len(out[0]) > 1 else None
        except Exception as exc:
            return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                                   timestamp=now, status=PredictionStatus.INFERENCE_ERROR,
                                   detail=f"inference error: {exc}")
        last = float(df["close"].iloc[-1])
        ret = (float(path[-1]) - last) / last
        direction = Direction.UP if ret > 0.00025 else Direction.DOWN if ret < -0.00025 else Direction.FLAT
        uncertainty = float(np.std(path)) if len(path) > 1 else None
        return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                               timestamp=now, forecast_price=float(path[-1]), forecast_return=ret,
                               direction=direction, probability_up=None, probability_down=None,
                               uncertainty=uncertainty, forecast_horizon=horizon, latency_ms=0.0,
                               status=PredictionStatus.OK, prices_path=[float(x) for x in path],
                               raw={"quantiles": None if quantiles is None else quantiles.tolist()})

    def health(self) -> dict:
        return {"loaded": self._loaded, "weights_available": False, "vendor_present": _AVAILABLE,
                "detail": "timesfm package installed" if _AVAILABLE else "pip install timesfm required"}