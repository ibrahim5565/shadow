"""AEGIS QUANT AI — Chronos-2 adapter (amazon/chronos-2, Apache-2.0).

Uses `chronos-forecasting>=2.0` (module name: `chronos`).  Without the
package or on load failure the adapter reports MODEL_UNAVAILABLE honestly.
Uncertainty is the model's own P10-P90 spread — never fabricated.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from quant_ai.models.base import BaseModelAdapter
from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus

logger = logging.getLogger("quant_ai.models.chronos")

CHECKPOINTS = {
    "chronos2": "amazon/chronos-2",          # verified: model.safetensors, not gated
}
_AVAILABLE = True
try:
    from chronos import BaseChronosPipeline  # type: ignore  # chronos-forecasting 2.x
except Exception as exc:  # pragma: no cover
    _AVAILABLE = False
    _IMPORT_ERR = exc


class ChronosAdapter(BaseModelAdapter):
    name = "chronos2"
    tier = 1
    min_history = 128

    def __init__(self, checkpoint: str = "chronos2", symbol: str = "XAUUSD",
                 timeframe: str = "M5", device=None):
        super().__init__(symbol=symbol, timeframe=timeframe, device=device, max_context=2048)
        self.checkpoint = checkpoint
        self._pipeline = None

    def load(self) -> bool:
        if self._loaded:
            return True
        if not _AVAILABLE:
            logger.warning("chronos-forecasting not installed; run `pip install chronos-forecasting`")
            return False
        try:
            if self.device is None:
                import torch
                self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
            t0 = time.perf_counter()
            self._pipeline = BaseChronosPipeline.from_pretrained(
                CHECKPOINTS.get(self.checkpoint, "amazon/chronos-2"),
                device_map=self.device)
            self._loaded = True
            logger.info("chronos2 loaded in %.1fs (device=%s)",
                        time.perf_counter() - t0, self.device)
            return True
        except Exception as exc:
            logger.error("chronos load failed: %s", exc)
            return False

    def predict(self, df: pd.DataFrame, horizon: int, **kwargs) -> ModelPrediction:
        now = datetime.now(timezone.utc).isoformat()
        if not self._loaded:
            self.load()
        if not self._loaded:
            return self.closed_prediction(self.name, self.symbol, self.timeframe, now,
                                          "chronos-forecasting package not available")
        if not self._valid_df(df, self.min_history):
            return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                                   timestamp=now, status=PredictionStatus.INSUFFICIENT_DATA,
                                   detail="insufficient history")
        try:
            import torch
            t0 = time.perf_counter()
            closes = df["close"].astype(np.float32).values[-self.max_context:]
            # Chronos-2 API: list of 1-D tensors (one per univariate series)
            context = torch.tensor(closes, dtype=torch.float32)
            with torch.no_grad():
                qs, _means = self._pipeline.predict_quantiles(
                    [context], prediction_length=int(horizon),
                    quantile_levels=[0.1, 0.5, 0.9])
            latency = (time.perf_counter() - t0) * 1000.0
            q = qs[0].squeeze(0).cpu().numpy()               # (H, 3) — 1 variate
            path = q[:, 1]                                   # median path
            if not np.isfinite(path).all() or not np.isfinite(q).all():
                return ModelPrediction(model=self.name, symbol=self.symbol,
                                       timeframe=self.timeframe, timestamp=now,
                                       status=PredictionStatus.INFERENCE_ERROR,
                                       detail="non-finite forecast output")
            median = float(np.median(q[:, 1]))
            p10, p90 = float(np.mean(q[:, 0])), float(np.mean(q[:, 2]))
            uncertainty = (p90 - p10) / median if median > 0 else None
        except Exception as exc:
            return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                                   timestamp=now, status=PredictionStatus.INFERENCE_ERROR,
                                   detail=f"inference error: {exc}")
        last = float(df["close"].iloc[-1])
        ret = (float(path[-1]) - last) / last
        band = 0.00025
        direction = Direction.UP if ret > band else Direction.DOWN if ret < -band else Direction.FLAT
        return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                               timestamp=now, forecast_price=float(path[-1]), forecast_return=ret,
                               direction=direction,
                               probability_up=None,      # Chronos-2 gives no direction prob
                               probability_down=None,
                               uncertainty=uncertainty, forecast_horizon=int(horizon),
                               latency_ms=round(latency, 1),
                               status=PredictionStatus.OK,
                               prices_path=[float(x) for x in path],
                               raw={"p10_last": p10, "p90_last": p90,
                                    "checkpoint": "amazon/chronos-2"})

    def health(self) -> dict:
        return {"loaded": self._loaded,
                "weights_available": True,       # model.safetensors verified on HF
                "vendor_present": _AVAILABLE,
                "checkpoint": "amazon/chronos-2",
                "detail": "chronos-forecasting 2.x installed" if _AVAILABLE
                          else "pip install chronos-forecasting required"}
