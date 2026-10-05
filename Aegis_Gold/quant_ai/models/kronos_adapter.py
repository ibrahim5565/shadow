"""AEGIS QUANT AI — KronosAdapter.

Real pretrained Kronos (NeoQuasar/Kronos-small et al., MIT) — a financial
K-line foundation model trained on 45 global exchanges.  Vendored source:
quant_ai/vendor/kronos (https://github.com/shiyu-coder/Kronos).  Only real
outputs are reported: forecast_price = median sampled path close;
probability_up/down = empirical frequencies across sampled paths (not
fabricated classifier probabilities); uncertainty = std of sampled closes.
"""
from __future__ import annotations

import logging
import os
import sys
import time as _time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from quant_ai.models.base import BaseModelAdapter
from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus

logger = logging.getLogger("quant_ai.models.kronos")

VENDOR_DIR = os.path.join(os.path.dirname(__file__), "..", "vendor", "kronos")

KRONOS_KEYS = {
    "kronos_mini":  "NeoQuasar/Kronos-mini",
    "kronos_small": "NeoQuasar/Kronos-small",
    "kronos_base":  "NeoQuasar/Kronos-base",
}
TOKENIZER_KEYS = {
    "kronos_mini":  "NeoQuasar/Kronos-Tokenizer-2k",
    "kronos_small": "NeoQuasar/Kronos-Tokenizer-base",
    "kronos_base":  "NeoQuasar/Kronos-Tokenizer-base",
}
MAX_CONTEXTS = {"kronos_mini": 2048, "kronos_small": 512, "kronos_base": 512}
DEAD_ZONE = 0.00025  # 2.5 bps — ignore tiny forecast moves


class KronosAdapter(BaseModelAdapter):
    name = "kronos"
    tier = 1
    min_history = 60

    def __init__(self, model_key: str = "kronos_small", symbol: str = "XAUUSD",
                 timeframe: str = "M5", device: Optional[str] = None,
                 uncertainty_runs: int = 5, forecast_runs: int = 1):
        self.model_key = model_key.lower()
        if self.model_key not in KRONOS_KEYS:
            raise ValueError(f"unknown kronos model key {model_key!r}")
        super().__init__(symbol=symbol, timeframe=timeframe, device=device,
                         max_context=MAX_CONTEXTS[self.model_key])
        self.uncertainty_runs = max(1, uncertainty_runs)
        self.forecast_runs = max(1, forecast_runs)
        self._tokenizer = None
        self._model = None
        self._predictor = None

    # ── lifecycle ──────────────────────────────────────────────────────
    def load(self) -> bool:
        if self._loaded:
            return True
        if not os.path.isdir(VENDOR_DIR):
            logger.error("vendored Kronos missing at %s", VENDOR_DIR)
            return False
        try:
            sys.path.insert(0, VENDOR_DIR)
            from model import Kronos, KronosPredictor, KronosTokenizer

            os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
            if self.device is None:
                import torch
                self.device = "cuda:0" if torch.cuda.is_available() else "cpu"

            t0 = _time.time()
            self._tokenizer = KronosTokenizer.from_pretrained(TOKENIZER_KEYS[self.model_key])
            self._model = Kronos.from_pretrained(KRONOS_KEYS[self.model_key])
            self._predictor = KronosPredictor(self._model, self._tokenizer,
                                              device=self.device, max_context=self.max_context)
            logger.info("kronos %s loaded on %s in %.1fs", KRONOS_KEYS[self.model_key],
                        self.device, _time.time() - t0)
            self._loaded = True
            return True
        except Exception as exc:
            logger.error("kronos load failed: %s", exc)
            self._loaded = False
            return False

    def unload(self) -> None:
        self._tokenizer = None
        self._model = None
        self._predictor = None
        self._loaded = False

    # ── inference ──────────────────────────────────────────────────────
    def _sample_paths(self, df: pd.DataFrame, horizon: int, runs: int) -> np.ndarray:
        """Return (runs, horizon) matrix of sampled forecast closes."""
        freq = self._timeframe_freq()
        last_ts = pd.to_datetime(df.index[-1])
        y_ts = pd.Series(pd.date_range(last_ts + freq, periods=horizon, freq=freq))
        x_ts = pd.Series(pd.to_datetime(df.index)[-self.max_context:])
        window = df.iloc[-self.max_context:].copy()
        if "volume" not in window.columns:               # MT5 exposes tick_volume
            if "tick_volume" in window.columns:
                window["volume"] = window["tick_volume"]
            else:
                window["volume"] = 1.0                   # neutral placeholder
        window = window[["open", "high", "low", "close", "volume"]]
        paths = []
        for _ in range(max(1, runs)):
            pred_df = self._predictor.predict(df=window, x_timestamp=x_ts,
                                              y_timestamp=y_ts, pred_len=horizon,
                                              T=1.0, top_p=0.9, sample_count=1,
                                              verbose=False)
            paths.append(pred_df["close"].values)
        return np.vstack(paths)

    def _timeframe_freq(self) -> pd.DateOffset:
        tf_map = {"M1": "min", "M5": "5min", "M15": "15min", "M30": "30min",
                  "H1": "h", "H4": "4h", "D1": "D"}
        return pd.tseries.frequencies.to_offset(tf_map.get(self.timeframe, "5min"))

    def predict(self, df: pd.DataFrame, horizon: int, **kwargs) -> ModelPrediction:
        now = datetime.now(timezone.utc).isoformat()
        if not self._loaded:
            self.load()
        if not self._loaded:
            return self.closed_prediction("kronos_" + self.model_key, self.symbol,
                                          self.timeframe, now, "model not loaded")
        if not self._valid_df(df, self.min_history):
            return ModelPrediction(model="kronos_" + self.model_key, symbol=self.symbol,
                                   timeframe=self.timeframe, timestamp=now,
                                   status=PredictionStatus.INSUFFICIENT_DATA,
                                   detail="insufficient history")
        closes = df["close"].astype(float)
        last_price = float(closes.iloc[-1])
        runs = self.forecast_runs * self.uncertainty_runs
        t0 = _time.time()
        try:
            arr = self._sample_paths(df, horizon, runs)
        except Exception as exc:
            return ModelPrediction(model="kronos_" + self.model_key, symbol=self.symbol,
                                   timeframe=self.timeframe, timestamp=now,
                                   status=PredictionStatus.INFERENCE_ERROR,
                                   detail=f"inference error: {exc}")
        latency_ms = (_time.time() - t0) * 1000.0

        median_path = np.median(arr, axis=0)
        horizon_close = float(np.median(arr[:, -1]))
        fc_ret = (horizon_close - last_price) / last_price
        uncertainty = float(np.std(arr[:, -1]))
        prob_up = float(np.mean(arr[:, -1] > last_price))
        prob_down = float(np.mean(arr[:, -1] < last_price))

        if fc_ret > DEAD_ZONE:
            direction = Direction.UP
        elif fc_ret < -DEAD_ZONE:
            direction = Direction.DOWN
        else:
            direction = Direction.FLAT

        return ModelPrediction(
            model="kronos_" + self.model_key, symbol=self.symbol, timeframe=self.timeframe,
            timestamp=now, forecast_price=round(horizon_close, 5),
            forecast_return=float(fc_ret), direction=direction,
            probability_up=prob_up, probability_down=prob_down,
            uncertainty=round(uncertainty, 5), forecast_horizon=horizon,
            latency_ms=round(latency_ms, 1), status=PredictionStatus.OK,
            detail=f"median of {int(arr.shape[0])} sampled Kronos paths",
            prices_path=[round(float(x), 5) for x in median_path],
            raw={"model_key": self.model_key, "runs": int(arr.shape[0])},
        )

    # ── health ─────────────────────────────────────────────────────────
    def health(self) -> dict:
        return {"loaded": self._loaded, "weights_available": self._loaded,
                "vendor_present": os.path.isdir(VENDOR_DIR),
                "model": KRONOS_KEYS[self.model_key], "device": self.device,
                "detail": "real NeoQuasar checkpoint" if self._loaded else "not loaded"}