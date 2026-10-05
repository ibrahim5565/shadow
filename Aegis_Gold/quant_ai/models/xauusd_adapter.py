"""AEGIS QUANT AI - XAU/USD Smart Money Concepts XGBoost Adapter (Priority 2: Gold-specific).

Open XGBoost model trained on multi-timeframe gold price action and Smart Money Concepts (FVG, Order Blocks, Liquidity).
Repo: https://huggingface.co/JonusNattapong/xauusd-trading-ai-smc-v2
License: MIT
Checkpoint: xauusd_smc_xgb.json (native XGBoost format, warning-free)
Features: 21 (OHLC, SMA20/50, EMA12/26, RSI14, MACD+signal+hist, Bollinger Bands, FVG size/type, OB type, Close lags)
Input: OHLCV DataFrame (minimum 60 bars)
Output: Direction UP / DOWN + calibrated probability + uncertainty
"""
from __future__ import annotations

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

logger = logging.getLogger("quant_ai.models.xauusd")

_AVAILABLE = True
try:
    import xgboost as xgb
except Exception as exc:
    _AVAILABLE = False
    _IMPORT_ERR = exc


class XAUUSD_SMC_Adapter(BaseModelAdapter):
    name = "xauusd_smc_xgb"
    tier = 2
    min_history = 60
    max_context = 150

    def __init__(
        self,
        symbol: str = "XAUUSD",
        timeframe: str = "M15",
        device: Optional[str] = None,
        checkpoint_dir: Optional[str] = None,
    ):
        super().__init__(symbol=symbol, timeframe=timeframe, device=device, max_context=150)
        self.checkpoint_dir = checkpoint_dir or os.path.join(
            os.path.dirname(__file__), "checkpoints"
        )
        self._booster: Optional[xgb.Booster] = None
        self._feature_names = [
            "Close", "High", "Low", "Open", "SMA_20", "SMA_50", "EMA_12", "EMA_26",
            "RSI", "MACD", "MACD_signal", "MACD_hist", "BB_upper", "BB_middle", "BB_lower",
            "FVG_Size", "FVG_Type", "OB_Type", "Close_lag1", "Close_lag2", "Close_lag3"
        ]

    def load(self) -> bool:
        if self._loaded:
            return True
        if not _AVAILABLE:
            logger.warning("xgboost not installed")
            return False

        json_path = os.path.join(self.checkpoint_dir, "xauusd_smc_xgb.json")
        pkl_path = os.path.join(self.checkpoint_dir, "xauusd_smc_xgb.pkl")

        try:
            b = xgb.Booster()
            if os.path.exists(json_path):
                b.load_model(json_path)
            elif os.path.exists(pkl_path):
                import joblib
                model_sk = joblib.load(pkl_path)
                b = model_sk.get_booster()
            else:
                logger.warning("No XAUUSD SMC model checkpoint found at %s", json_path)
                return False

            self._booster = b
            self._loaded = True
            logger.info("XAUUSD_SMC_Adapter loaded successfully")
            return True
        except Exception as exc:
            logger.error("Failed to load XAUUSD_SMC_Adapter: %s", exc)
            return False

    def unload(self) -> None:
        self._booster = None
        self._loaded = False

    def _compute_features(self, df_raw: pd.DataFrame) -> Optional[np.ndarray]:
        try:
            df = df_raw.copy()
            c = df["close"].values
            h = df["high"].values
            l = df["low"].values
            o = df["open"].values
            n = len(c)
            if n < self.min_history:
                return None

            curr_c, curr_h, curr_l, curr_o = c[-1], h[-1], l[-1], o[-1]

            sma20 = float(np.mean(c[-20:]))
            sma50 = float(np.mean(c[-50:]))

            ema12 = float(pd.Series(c).ewm(span=12).mean().iloc[-1])
            ema26 = float(pd.Series(c).ewm(span=26).mean().iloc[-1])

            diff = np.diff(c[-15:])
            gain = np.mean(np.maximum(diff, 0.0))
            loss = np.mean(np.maximum(-diff, 0.0))
            rs = gain / (loss + 1e-12)
            rsi = float(100.0 - (100.0 / (1.0 + rs)))

            macd = ema12 - ema26
            macd_sig = float(pd.Series(c).ewm(span=9).mean().iloc[-1] * 0.1)
            macd_hist = macd - macd_sig

            bb_mid = sma20
            bb_std = float(np.std(c[-20:]))
            bb_upper = bb_mid + 2.0 * bb_std
            bb_lower = bb_mid - 2.0 * bb_std

            fvg_size = 0.0
            fvg_type = 0.0
            if n >= 3:
                if l[-1] > h[-3]:
                    fvg_size = l[-1] - h[-3]
                    fvg_type = 1.0
                elif h[-1] < l[-3]:
                    fvg_size = l[-3] - h[-1]
                    fvg_type = -1.0

            ob_type = 1.0 if c[-2] < o[-2] and c[-1] > o[-1] else (-1.0 if c[-2] > o[-2] and c[-1] < o[-1] else 0.0)

            close_lag1 = c[-2] if n >= 2 else curr_c
            close_lag2 = c[-3] if n >= 3 else curr_c
            close_lag3 = c[-4] if n >= 4 else curr_c

            feat_vector = np.array([
                curr_c, curr_h, curr_l, curr_o,
                sma20, sma50, ema12, ema26,
                rsi, macd, macd_sig, macd_hist,
                bb_upper, bb_mid, bb_lower,
                fvg_size, fvg_type, ob_type,
                close_lag1, close_lag2, close_lag3
            ], dtype=np.float32).reshape(1, -1)

            return feat_vector
        except Exception as exc:
            logger.error("Error computing features for XAUUSD SMC: %s", exc)
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
                detail=f"insufficient history (min {self.min_history} bars required)",
            )

        try:
            t0 = time.perf_counter()
            feats = self._compute_features(df)
            if feats is None:
                return ModelPrediction(
                    model=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    timestamp=now,
                    status=PredictionStatus.INFERENCE_ERROR,
                    detail="feature computation failed",
                )

            dmat = xgb.DMatrix(feats, feature_names=self._feature_names)
            preds = self._booster.predict(dmat)
            prob_raw = float(preds[0])

            prob_up = prob_raw if 0.0 <= prob_raw <= 1.0 else 1.0 / (1.0 + math.exp(-prob_raw))
            prob_down = 1.0 - prob_up

            latency = (time.perf_counter() - t0) * 1000.0

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
                forecast_price=round(forecast_price, 3),
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
                    "raw_score": prob_raw,
                    "prob_up": prob_up,
                    "prob_down": prob_down,
                },
            )
        except Exception as exc:
            logger.error("XAUUSD SMC inference error: %s", exc)
            return ModelPrediction(
                model=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                timestamp=now,
                status=PredictionStatus.INFERENCE_ERROR,
                detail=f"inference error: {exc}",
            )

    def health(self) -> dict:
        json_path = os.path.join(self.checkpoint_dir, "xauusd_smc_xgb.json")
        pkl_path = os.path.join(self.checkpoint_dir, "xauusd_smc_xgb.pkl")
        return {
            "loaded": self._loaded,
            "weights_available": os.path.exists(json_path) or os.path.exists(pkl_path),
            "vendor_present": _AVAILABLE,
            "device": "cpu",
        }
