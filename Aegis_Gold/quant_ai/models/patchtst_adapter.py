"""AEGIS QUANT AI - PatchTST adapter (Priority 3, DOMAIN-MISMATCHED).

Checkpoint: ``ibm/patchtst-etth1-pretrain`` (Apache-2.0), loaded through
``transformers.PatchTSTForPrediction``.

HONEST STATUS: the weights are REAL and inference was measured locally
(load ~3.1s, ~110ms/forecast on CPU, output [1, 24, 7]).  However the
checkpoint was pretrained on **ETTh1** (electricity-transformer temperature /
load), NOT on FX or gold.  It is therefore registered as RUNNING /
domain-mismatched and is **disabled by default** (`model_enable["patchtst"]
= False`).  It must not be promoted into signals until it beats the naive
baselines on the target asset out-of-sample.

The model emits no probability; `probability_up`/`probability_down` stay
``None`` - never fabricated.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from quant_ai.models.base import BaseModelAdapter
from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus

logger = logging.getLogger("quant_ai.models.patchtst")

DEFAULT_REPO = "ibm/patchtst-etth1-pretrain"

_AVAILABLE = True
try:
    import torch
    from transformers import PatchTSTForPrediction
except Exception as exc:                                     # pragma: no cover
    _AVAILABLE = False
    _IMPORT_ERR = exc


class PatchTSTAdapter(BaseModelAdapter):
    name = "patchtst"
    tier = 3
    min_history = 600
    domain_note = "pretrained on ETTh1 (electricity) - out-of-domain for FX/gold"

    def __init__(self, symbol: str = "XAUUSD", timeframe: str = "M5",
                 device: Optional[str] = None, repo: str = DEFAULT_REPO):
        super().__init__(symbol=symbol, timeframe=timeframe, device=device,
                         max_context=512)
        self.repo = repo
        self._model = None
        self._n_channels = 7
        self._ctx = 512
        self._refuse_reason = ""
        self._missing_keys: list = []

    # ── lifecycle ──────────────────────────────────────────────────────
    def load(self) -> bool:
        if self._loaded:
            return True
        if not _AVAILABLE:
            logger.warning("transformers PatchTST unavailable: %s",
                           globals().get("_IMPORT_ERR"))
            return False
        try:
            model, info = PatchTSTForPrediction.from_pretrained(
                self.repo, output_loading_info=True)
            missing = list(info.get("missing_keys") or [])
            # HONESTY GUARD: a masked-pretraining checkpoint has no forecast
            # head; those weights would be RANDOMLY INITIALISED.  A randomly
            # initialised head is not a pretrained forecaster, so refuse it
            # instead of silently emitting fabricated forecasts.
            random_head = [k for k in missing if "head" in k or "projection" in k]
            self._missing_keys = missing
            if random_head:
                self._refuse_reason = (
                    f"checkpoint '{self.repo}' has no pretrained forecast head "
                    f"({len(random_head)} random head params, e.g. {random_head[0]}); "
                    "randomly-initialised head is NOT a pretrained forecaster")
                logger.warning("PatchTST refused: %s", self._refuse_reason)
                self._model = None
                self._loaded = False
                return False
            self._model = model
            self._model.eval()
            self._ctx = int(getattr(self._model.config, "context_length", 512) or 512)
            self._n_channels = int(
                getattr(self._model.config, "num_input_channels", 7) or 7)
            self._loaded = True
            logger.info("PatchTST loaded: %s (ctx=%d ch=%d)", self.repo,
                        self._ctx, self._n_channels)
            return True
        except Exception as exc:
            logger.error("PatchTST load failed: %s", exc)
            self._refuse_reason = str(exc)
            self._model = None
            self._loaded = False
            return False

    def unload(self) -> None:
        self._model = None
        self._loaded = False

    # ── input construction ─────────────────────────────────────────────
    def _channels(self, df: pd.DataFrame):
        """Build exactly ``num_input_channels`` causal channels from OHLCV.

        Returns (array(T,C), channel_mean, channel_std) or None.
        """
        try:
            c = df["close"].astype(float).values
            o = df["open"].astype(float).values
            h = df["high"].astype(float).values
            l = df["low"].astype(float).values
            vol = (df["volume"].astype(float).values if "volume" in df.columns
                   else np.ones_like(c))
            ret = np.zeros_like(c)
            ret[1:] = np.diff(np.log(c))
            feats = [c, o, h, l, (h + l + c) / 3.0,
                     np.log1p(np.abs(vol)), ret]
            window = feats[: self._n_channels]
            while len(window) < self._n_channels:      # pad by repeating close
                window.append(c)
            arr = np.stack(window, axis=-1)            # (T, C)
            arr = arr[-self._ctx:]
            if len(arr) < self._ctx:
                pad = np.repeat(arr[:1], self._ctx - len(arr), axis=0)
                arr = np.concatenate([pad, arr], axis=0)
            mu = arr.mean(axis=0, keepdims=True)
            sd = arr.std(axis=0, keepdims=True) + 1e-9
            arr = (arr - mu) / sd
            return arr.astype(np.float32), mu, sd
        except Exception as exc:
            logger.warning("PatchTST channel build failed: %s", exc)
            return None

    # ── inference ──────────────────────────────────────────────────────
    def predict(self, df: pd.DataFrame, horizon: int, **kwargs) -> ModelPrediction:
        now = datetime.now(timezone.utc).isoformat()
        if not _AVAILABLE:
            return self.closed_prediction(self.name, self.symbol, self.timeframe,
                                          now, "transformers PatchTST missing")
        if not self._loaded and not self.load():
            return self.closed_prediction(self.name, self.symbol, self.timeframe,
                                          now,
                                          self._refuse_reason or
                                          "checkpoint not loadable")
        if not self._valid_df(df, self.min_history):
            return ModelPrediction(model=self.name, symbol=self.symbol,
                                   timeframe=self.timeframe, timestamp=now,
                                   status=PredictionStatus.INSUFFICIENT_DATA,
                                   detail=f"needs >= {self.min_history} bars")
        built = self._channels(df)
        if built is None:
            return ModelPrediction(model=self.name, symbol=self.symbol,
                                   timeframe=self.timeframe, timestamp=now,
                                   status=PredictionStatus.INFERENCE_ERROR,
                                   detail="channel construction failed")
        arr, mu, sd = built
        try:
            t0 = time.perf_counter()
            x = torch.tensor(arr.reshape(1, arr.shape[0], arr.shape[1]),
                             dtype=torch.float32)
            with torch.no_grad():
                out = self._model(past_values=x).prediction_outputs
            path_n = out.cpu().numpy()[0]                       # (H, C)
            latency = (time.perf_counter() - t0) * 1000.0
        except Exception as exc:
            logger.error("PatchTST inference failed: %s", exc)
            return ModelPrediction(model=self.name, symbol=self.symbol,
                                   timeframe=self.timeframe, timestamp=now,
                                   status=PredictionStatus.INFERENCE_ERROR,
                                   detail=f"inference error: {exc}")

        h = min(int(horizon), path_n.shape[0])
        close_ch = path_n[:h, 0] * sd[0, 0] + mu[0, 0]           # de-normalise
        last = float(df["close"].iloc[-1])
        path = [last] + [float(v) for v in close_ch]
        ret = (path[-1] - last) / last
        band = 0.00025
        direction = (Direction.UP if ret > band else
                     Direction.DOWN if ret < -band else Direction.FLAT)
        spread_unc = float(np.std(np.diff(path))) if len(path) > 2 else None
        return ModelPrediction(
            model=self.name, symbol=self.symbol, timeframe=self.timeframe,
            timestamp=now, forecast_price=round(float(path[-1]), 5),
            forecast_return=round(float(ret), 6), direction=direction,
            probability_up=None, probability_down=None,
            uncertainty=round(spread_unc, 6) if spread_unc is not None else None,
            forecast_horizon=h, latency_ms=round(latency, 1),
            status=PredictionStatus.OK, prices_path=path,
            raw={"repo": self.repo, "domain_note": self.domain_note,
                 "context_length": self._ctx, "channels": self._n_channels,
                 "probability_available": False})

    def health(self) -> dict:
        return {"loaded": self._loaded, "weights_available": _AVAILABLE,
                "vendor_present": _AVAILABLE, "device": "cpu",
                "repo": self.repo, "domain_note": self.domain_note,
                "refused": bool(self._refuse_reason),
                "refuse_reason": self._refuse_reason,
                "missing_keys": len(self._missing_keys)}

