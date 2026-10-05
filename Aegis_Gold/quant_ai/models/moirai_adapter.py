"""AEGIS QUANT AI — Moirai adapter (SalesforceAIResearch/uni2ts, Apache-2.0 research-purposes).

Requires `pip install uni2ts`.  Without it the adapter reports MODEL_UNAVAILABLE.
This adapter is registered but DISABLED by default in QAIConfig; the uni2ts
dependency tree is heavy and the model is large for a 6GB GPU — enabling it is
an explicit, documented choice.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from quant_ai.models.base import BaseModelAdapter
from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus

logger = logging.getLogger("quant_ai.models.moirai")

_AVAILABLE = True
try:
    import torch
    from uni2ts.eval_util import get_uni2ts_eval  # noqa: F401
except Exception as exc:  # pragma: no cover
    _AVAILABLE = False
    _IMPORT_ERR = exc


class MoiraiAdapter(BaseModelAdapter):
    name = "moirai"
    tier = 2
    min_history = 128

    def __init__(self, model_name: str = "Salesforce/moirai-1.1-R-small",
                 symbol: str = "XAUUSD", timeframe: str = "M5", device=None):
        super().__init__(symbol=symbol, timeframe=timeframe, device=device, max_context=512)
        self.model_name = model_name
        self._model = None

    def load(self) -> bool:
        if self._loaded:
            return True
        if not _AVAILABLE:
            logger.warning("uni2ts not installed; run `pip install uni2ts` to enable moirai")
            return False
        try:
            from uni2ts.model.moirai import MoiraiForecast, MoiraiModule
            self._model = MoiraiModule.from_pretrained(self.model_name)
            self._loaded = True
            return True
        except Exception as exc:
            logger.error("moirai load failed: %s", exc)
            return False

    def predict(self, df: pd.DataFrame, horizon: int, **kwargs) -> ModelPrediction:
        now = datetime.now(timezone.utc).isoformat()
        if not self._loaded:
            self.load()
        if not self._loaded:
            return self.closed_prediction(self.name, self.symbol, self.timeframe, now,
                                          "uni2ts package not installed")
        if not self._valid_df(df, self.min_history):
            return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                                   timestamp=now, status=PredictionStatus.INSUFFICIENT_DATA,
                                   detail="insufficient history")
        try:
            import torch
            target = torch.tensor(df["close"].astype(np.float32).values[-self.max_context:],
                                  dtype=torch.float32).unsqueeze(0)
            forecast = MoiraiForecast(self._model, target=target, prediction_length=horizon,
                                      num_samples=10)
            samples = forecast.samples.numpy().squeeze(0)          # (num_samples, horizon)
            path = np.median(samples, axis=0)
            prob_up = float(np.mean(samples[:, -1] > samples[:, 0]))
        except Exception as exc:
            return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                                   timestamp=now, status=PredictionStatus.INFERENCE_ERROR,
                                   detail=f"inference error: {exc}")
        last = float(df["close"].iloc[-1])
        ret = (float(path[-1]) - last) / last
        direction = Direction.UP if ret > 0.00025 else Direction.DOWN if ret < -0.00025 else Direction.FLAT
        return ModelPrediction(model=self.name, symbol=self.symbol, timeframe=self.timeframe,
                               timestamp=now, forecast_price=float(path[-1]), forecast_return=ret,
                               direction=direction, probability_up=prob_up, probability_down=1 - prob_up,
                               uncertainty=float(np.std(samples[:, -1])), forecast_horizon=horizon,
                               latency_ms=0.0, status=PredictionStatus.OK,
                               prices_path=[float(x) for x in path], raw={})

    def health(self) -> dict:
        return {"loaded": self._loaded, "weights_available": False, "vendor_present": _AVAILABLE,
                "detail": "uni2ts package installed" if _AVAILABLE else "pip install uni2ts required"}