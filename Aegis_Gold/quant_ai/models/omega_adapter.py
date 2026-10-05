"""AEGIS QUANT AI - OMEGA Forex v3 Model Adapter (Priority 1: Forex-specific).

Open CNN + RegimeGate + Transformer + Standard Candle model for forex pairs (EUR/USD, GBP/USD, etc.).
Repo: https://huggingface.co/sato2ru/omega-forex
License: MIT
Checkpoint: model.pt (~765KB, ~184,354 parameters)
Features: 46 (22 technical, 11 session, 5 Keplerian lag, 5 regime, 3 anchor)
Input: 24 bars x 46 features
Output: binary UP / DOWN direction + calibrated probability (temperature=1.7846)
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from quant_ai.models.base import BaseModelAdapter
from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus

logger = logging.getLogger("quant_ai.models.omega")

_AVAILABLE = True
try:
    import torch
    import torch.nn as nn
except Exception as exc:
    _AVAILABLE = False
    _IMPORT_ERR = exc


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int = 64, max_len: int = 32):
        super().__init__()
        self.register_buffer("pe", torch.zeros(1, max_len, d_model))


class RegimeGate(nn.Module):
    def __init__(self, n_regime: int = 5, d_model: int = 64):
        super().__init__()
        self.regime_proj = nn.Sequential(
            nn.Linear(n_regime, 32),
            nn.ReLU(),
            nn.Linear(32, d_model),
        )
        self.norm = nn.LayerNorm(d_model)

    def forward(self, x: torch.Tensor, regime: torch.Tensor) -> torch.Tensor:
        r = self.regime_proj(regime)
        if r.dim() == 2:
            r = r.unsqueeze(1)
        return self.norm(x + r)


class OmegaForexNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv_block = nn.Sequential(
            nn.Conv1d(46, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Conv1d(64, 64, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.BatchNorm1d(64),
        )
        self.regime_gate = RegimeGate(5, 64)
        self.pos_enc = PositionalEncoding(64, 32)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=64, nhead=4, dim_feedforward=256, dropout=0.1, batch_first=True
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=3)
        self.classifier = nn.Sequential(
            nn.LayerNorm(64),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(32, 2),
        )

    def forward(self, x: torch.Tensor, regime: torch.Tensor) -> torch.Tensor:
        h = self.conv_block(x.transpose(1, 2)).transpose(1, 2)
        h = self.regime_gate(h, regime)
        L = h.size(1)
        h = h + self.pos_enc.pe[:, :L, :]
        enc = self.encoder(h)
        return self.classifier(enc[:, -1, :])


class OmegaForexAdapter(BaseModelAdapter):
    name = "omega_forex_v3"
    tier = 1
    min_history = 60
    max_context = 24

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: str = "H1",
        device: Optional[str] = None,
        checkpoint_dir: Optional[str] = None,
    ):
        super().__init__(symbol=symbol, timeframe=timeframe, device=device, max_context=24)
        self.checkpoint_dir = checkpoint_dir or os.path.join(
            os.path.dirname(__file__), "checkpoints"
        )
        self._model: Optional[OmegaForexNet] = None
        self._temperature = 1.7846

    def load(self) -> bool:
        if self._loaded:
            return True
        if not _AVAILABLE:
            logger.warning("torch not available for OmegaForexAdapter")
            return False

        ckpt_path = os.path.join(self.checkpoint_dir, "omega_model.pt")
        if not os.path.exists(ckpt_path):
            logger.warning("omega_model.pt not found at %s", ckpt_path)
            return False

        try:
            if self.device is None:
                self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
            net = OmegaForexNet()
            sd = torch.load(ckpt_path, map_location="cpu", weights_only=False)
            net.load_state_dict(sd)
            net.to(self.device)
            net.eval()
            self._model = net
            self._loaded = True
            logger.info("OmegaForexAdapter loaded successfully on %s", self.device)
            return True
        except Exception as exc:
            logger.error("Failed to load OmegaForexAdapter: %s", exc)
            return False

    def unload(self) -> None:
        self._model = None
        self._loaded = False
        if _AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _extract_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        try:
            closes = df["close"].values
            highs = df["high"].values
            lows = df["low"].values
            opens = df["open"].values
            n = len(closes)
            if n < 24:
                return None

            feat_matrix = np.zeros((24, 46), dtype=np.float32)

            for step_idx, row_idx in enumerate(range(n - 24, n)):
                c = closes[: row_idx + 1]
                h = highs[: row_idx + 1]
                l = lows[: row_idx + 1]
                o = opens[: row_idx + 1]
                curr_c = c[-1]
                curr_h = h[-1]
                curr_l = l[-1]
                curr_o = o[-1]

                ema9 = pd.Series(c).ewm(span=9).mean().iloc[-1]
                ema21 = pd.Series(c).ewm(span=21).mean().iloc[-1]
                ema50 = pd.Series(c).ewm(span=50).mean().iloc[-1]

                ema9_r = (curr_c - ema9) / (ema9 + 1e-8)
                ema21_r = (curr_c - ema21) / (ema21 + 1e-8)
                ema50_r = (curr_c - ema50) / (ema50 + 1e-8)

                diff = np.diff(c[-15:])
                gain = np.mean(np.maximum(diff, 0.0))
                loss = np.mean(np.maximum(-diff, 0.0))
                rs = gain / (loss + 1e-8)
                rsi = 100.0 - (100.0 / (1.0 + rs))

                ema12 = pd.Series(c).ewm(span=12).mean().iloc[-1]
                ema26 = pd.Series(c).ewm(span=26).mean().iloc[-1]
                macd = ema12 - ema26
                macd_sig = pd.Series(c).ewm(span=9).mean().iloc[-1] * 0.1
                macd_hist = macd - macd_sig

                bb_mid = np.mean(c[-20:])
                bb_std = np.std(c[-20:]) + 1e-8
                bb_w = (4 * bb_std) / (bb_mid + 1e-8)
                bb_pct = (curr_c - (bb_mid - 2 * bb_std)) / (4 * bb_std)

                tr = np.maximum(h[-14:] - l[-14:], np.abs(h[-14:] - c[-15:-1]))
                atr = float(np.mean(tr))

                body = (curr_c - curr_o) / (atr + 1e-8)
                wick_up = (curr_h - max(curr_c, curr_o)) / (atr + 1e-8)
                wick_dn = (min(curr_c, curr_o) - curr_l) / (atr + 1e-8)
                hl_range = (curr_h - curr_l) / (atr + 1e-8)

                feat_matrix[step_idx, 0] = ema9_r
                feat_matrix[step_idx, 1] = ema21_r
                feat_matrix[step_idx, 2] = ema50_r
                feat_matrix[step_idx, 6] = rsi / 100.0
                feat_matrix[step_idx, 7] = macd / (curr_c + 1e-8)
                feat_matrix[step_idx, 8] = macd_sig / (curr_c + 1e-8)
                feat_matrix[step_idx, 9] = macd_hist / (curr_c + 1e-8)
                feat_matrix[step_idx, 15] = atr / (curr_c + 1e-8)
                feat_matrix[step_idx, 16] = bb_w
                feat_matrix[step_idx, 17] = bb_pct
                feat_matrix[step_idx, 18] = body
                feat_matrix[step_idx, 19] = wick_up
                feat_matrix[step_idx, 20] = wick_dn
                feat_matrix[step_idx, 21] = hl_range

                feat_matrix[step_idx, 38] = 0.5
                feat_matrix[step_idx, 39] = 0.5
                feat_matrix[step_idx, 40] = 0.0
                feat_matrix[step_idx, 41] = 1.0 if ema9 > ema21 else -1.0
                feat_matrix[step_idx, 42] = min(float(step_idx) / 24.0, 1.0)

            feat_matrix = np.nan_to_num(feat_matrix, nan=0.0, posinf=1.0, neginf=-1.0)
            return feat_matrix
        except Exception as exc:
            logger.error("Error extracting features for OMEGA Forex: %s", exc)
            return None

    def predict(self, df: pd.DataFrame, horizon: int = 1, **kwargs) -> ModelPrediction:
        now = datetime.now(timezone.utc).isoformat()
        if not self._loaded:
            self.load()
        if not self._loaded:
            return self.closed_prediction(
                self.name, self.symbol, self.timeframe, now, "model weights not loaded"
            )

        if not self._valid_df(df, self.min_history):
            return ModelPrediction(
                model=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                timestamp=now,
                status=PredictionStatus.INSUFFICIENT_DATA,
                detail="insufficient history (min 60 bars required)",
            )

        try:
            t0 = time.perf_counter()
            feats = self._extract_features(df)
            if feats is None:
                return ModelPrediction(
                    model=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    timestamp=now,
                    status=PredictionStatus.INFERENCE_ERROR,
                    detail="feature extraction failed",
                )

            x_t = torch.tensor(feats, dtype=torch.float32).unsqueeze(0).to(self.device)
            reg_t = torch.tensor(feats[-1, 38:43], dtype=torch.float32).unsqueeze(0).to(self.device)

            with torch.no_grad():
                logits = self._model(x_t, reg_t)
                scaled_logits = logits / self._temperature
                probs = torch.softmax(scaled_logits, dim=-1).cpu().numpy()[0]

            latency = (time.perf_counter() - t0) * 1000.0

            prob_down = float(probs[0])
            prob_up = float(probs[1])

            last_close = float(df["close"].iloc[-1])
            atr_est = float(np.mean(df["high"].iloc[-14:] - df["low"].iloc[-14:]))
            delta = (prob_up - 0.5) * 2.0 * atr_est
            forecast_price = last_close + delta
            ret = delta / last_close

            conf = max(prob_up, prob_down)
            uncertainty = 1.0 - conf

            if prob_up > 0.52:
                direction = Direction.UP
            elif prob_down > 0.52:
                direction = Direction.DOWN
            else:
                direction = Direction.FLAT

            return ModelPrediction(
                model=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                timestamp=now,
                forecast_price=round(forecast_price, 5),
                forecast_return=round(ret, 6),
                direction=direction,
                probability_up=round(prob_up, 4),
                probability_down=round(prob_down, 4),
                uncertainty=round(uncertainty, 4),
                forecast_horizon=int(horizon),
                latency_ms=round(latency, 1),
                status=PredictionStatus.OK,
                prices_path=[last_close, forecast_price],
                raw={
                    "logits": [float(x) for x in logits.cpu().numpy()[0]],
                    "temperature": self._temperature,
                    "prob_up": prob_up,
                    "prob_down": prob_down,
                },
            )
        except Exception as exc:
            logger.error("OMEGA Forex inference error: %s", exc)
            return ModelPrediction(
                model=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                timestamp=now,
                status=PredictionStatus.INFERENCE_ERROR,
                detail=f"inference error: {exc}",
            )

    def health(self) -> dict:
        ckpt_path = os.path.join(self.checkpoint_dir, "omega_model.pt")
        return {
            "loaded": self._loaded,
            "weights_available": os.path.exists(ckpt_path),
            "vendor_present": _AVAILABLE,
            "device": self.device,
        }
