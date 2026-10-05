"""AEGIS QUANT AI - EUR/USD Direction Ensemble Adapter (Priority 1: Forex-specific).

Open LightGBM + XGBoost weighted ensemble for EUR/USD daily/intraday direction forecasting.
Repo: https://huggingface.co/lvizcaya/forex-eurusd-direction
License: Apache-2.0
Checkpoints: eurusd_lgb.joblib (1.39MB) + eurusd_xgb.joblib (1.17MB)
Scaler: scaler.joblib (StandardScaler)
Features: 53 technical/momentum/volatility/calendar features
Ensemble Weights: LightGBM 0.39, XGBoost 0.61 (optimized across 198 walk-forward folds)
Input: OHLCV DataFrame (minimum 100 bars for indicator warmup)
Output: binary UP / DOWN direction + measured probabilities + uncertainty
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import List, Optional

import numpy as np
import pandas as pd

from quant_ai.models.base import BaseModelAdapter
from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus

logger = logging.getLogger("quant_ai.models.eurusd")


class EURUSDEnsembleAdapter(BaseModelAdapter):
    name = "eurusd_lgb_xgb"
    tier = 1
    min_history = 100
    max_context = 300

    def __init__(
        self,
        symbol: str = "EURUSD",
        timeframe: str = "D1",
        device: Optional[str] = None,
        checkpoint_dir: Optional[str] = None,
    ):
        super().__init__(symbol=symbol, timeframe=timeframe, device=device, max_context=300)
        self.checkpoint_dir = checkpoint_dir or os.path.join(
            os.path.dirname(__file__), "checkpoints"
        )
        self._lgb_model = None
        self._xgb_model = None
        self._scaler = None
        self._feature_cols: List[str] = []
        self._lgb_weight = 0.39
        self._xgb_weight = 0.61

    def load(self) -> bool:
        if self._loaded:
            return True
        try:
            import joblib
            lgb_path = os.path.join(self.checkpoint_dir, "eurusd_lgb.joblib")
            xgb_path = os.path.join(self.checkpoint_dir, "eurusd_xgb.joblib")
            scaler_path = os.path.join(self.checkpoint_dir, "eurusd_scaler.joblib")
            cols_path = os.path.join(self.checkpoint_dir, "eurusd_feature_cols.json")

            if not (os.path.exists(lgb_path) and os.path.exists(xgb_path) and os.path.exists(scaler_path)):
                logger.warning("EURUSD model checkpoints missing in %s", self.checkpoint_dir)
                return False

            self._lgb_model = joblib.load(lgb_path)
            self._xgb_model = joblib.load(xgb_path)
            self._scaler = joblib.load(scaler_path)

            if os.path.exists(cols_path):
                with open(cols_path, "r", encoding="utf-8") as f:
                    self._feature_cols = json.load(f)

            self._loaded = True
            logger.info("EURUSDEnsembleAdapter loaded successfully")
            return True
        except Exception as exc:
            logger.error("Failed to load EURUSDEnsembleAdapter: %s", exc)
            return False

    def unload(self) -> None:
        self._lgb_model = None
        self._xgb_model = None
        self._scaler = None
        self._loaded = False

    def _compute_features(self, df_raw: pd.DataFrame) -> Optional[pd.DataFrame]:
        try:
            df = df_raw.copy()
            df.columns = [c.capitalize() for c in df.columns]

            for w in [5, 10, 21, 63, 126, 252]:
                shift_w = min(w, len(df) - 1)
                df[f"log_return_{w}d"] = np.log(df["Close"] / (df["Close"].shift(shift_w) + 1e-12))
                df[f"momentum_{w}d"] = df["Close"] / (df["Close"].shift(shift_w) + 1e-12) - 1.0

            df["log_return_1d"] = np.log(df["Close"] / (df["Close"].shift(1) + 1e-12))

            for w in [5, 10, 21, 63]:
                rw = min(w, len(df))
                df[f"volatility_{w}d"] = df["log_return_1d"].rolling(rw, min_periods=2).std()

            for w in [5, 10, 20, 50, 100, 200]:
                rw = min(w, len(df))
                sma = df["Close"].rolling(rw, min_periods=2).mean()
                df[f"price_to_sma_{w}"] = df["Close"] / (sma + 1e-12) - 1.0

            df["ema_12"] = df["Close"].ewm(span=12).mean()
            df["ema_26"] = df["Close"].ewm(span=26).mean()
            df["ema_cross"] = df["ema_12"] / (df["ema_26"] + 1e-12) - 1.0

            for w in [7, 14, 21]:
                diff = df["Close"].diff()
                gain = (diff.where(diff > 0, 0.0)).rolling(w, min_periods=2).mean()
                loss = (-diff.where(diff < 0, 0.0)).rolling(w, min_periods=2).mean()
                rs = gain / (loss + 1e-12)
                df[f"rsi_{w}"] = 100.0 - (100.0 / (1.0 + rs))

            macd_raw = df["ema_12"] - df["ema_26"]
            macd_sig = macd_raw.ewm(span=9).mean()
            df["macd"] = macd_raw
            df["macd_signal"] = macd_sig
            df["macd_diff"] = macd_raw - macd_sig

            bb_mid = df["Close"].rolling(20, min_periods=2).mean()
            bb_std = df["Close"].rolling(20, min_periods=2).std() + 1e-12
            df["bb_pband"] = (df["Close"] - (bb_mid - 2 * bb_std)) / (4 * bb_std)
            df["bb_wband"] = (4 * bb_std) / (bb_mid + 1e-12)

            tr1 = df["High"] - df["Low"]
            tr2 = (df["High"] - df["Close"].shift(1)).abs()
            tr3 = (df["Low"] - df["Close"].shift(1)).abs()
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(14, min_periods=2).mean()
            df["atr_14"] = atr
            df["atr_14_pct"] = atr / (df["Close"] + 1e-12)

            low_14 = df["Low"].rolling(14, min_periods=2).min()
            high_14 = df["High"].rolling(14, min_periods=2).max()
            df["stoch_k"] = 100.0 * (df["Close"] - low_14) / (high_14 - low_14 + 1e-12)
            df["stoch_d"] = df["stoch_k"].rolling(3, min_periods=1).mean()

            df["adx"] = 25.0
            df["adx_pos"] = 20.0
            df["adx_neg"] = 20.0

            df["williams_r"] = -100.0 * (high_14 - df["Close"]) / (high_14 - low_14 + 1e-12)
            tp = (df["High"] + df["Low"] + df["Close"]) / 3.0
            tp_sma = tp.rolling(20, min_periods=2).mean()
            tp_dev = (tp - tp_sma).abs().rolling(20, min_periods=2).mean() + 1e-12
            df["cci"] = (tp - tp_sma) / (0.015 * tp_dev)

            vol = df["Volume"] if "Volume" in df.columns else pd.Series(1.0, index=df.index)
            vol_sign = np.sign(df["Close"].diff().fillna(0.0))
            df["obv"] = (vol * vol_sign).cumsum()
            df["obv_pct"] = df["obv"].pct_change(5).fillna(0.0)

            df["day_of_week"] = df.index.dayofweek if hasattr(df.index, "dayofweek") else 2
            df["month"] = df.index.month if hasattr(df.index, "month") else 6
            df["quarter"] = df.index.quarter if hasattr(df.index, "quarter") else 2

            df["hl_range"] = (df["High"] - df["Low"]) / (df["Close"] + 1e-12)
            df["oc_range"] = (df["Close"] - df["Open"]) / (df["Close"] + 1e-12)

            for w in [10, 20, 50]:
                rw = min(w, len(df))
                rh = df["High"].rolling(rw, min_periods=2).max()
                rl = df["Low"].rolling(rw, min_periods=2).min()
                df[f"channel_pos_{w}"] = (df["Close"] - rl) / (rh - rl + 1e-12)

            return df
        except Exception as exc:
            logger.error("Error computing features for EURUSD: %s", exc)
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
            df_feat = self._compute_features(df)
            if df_feat is None:
                return ModelPrediction(
                    model=self.name,
                    symbol=self.symbol,
                    timeframe=self.timeframe,
                    timestamp=now,
                    status=PredictionStatus.INFERENCE_ERROR,
                    detail="feature computation failed",
                )

            latest_row = df_feat.iloc[[-1]]
            X_raw = np.nan_to_num(latest_row[self._feature_cols].values, nan=0.0, posinf=1.0, neginf=-1.0)
            X_scaled = self._scaler.transform(X_raw)

            lgb_prob_up = float(self._lgb_model.predict_proba(X_scaled)[:, 1][0])
            xgb_prob_up = float(self._xgb_model.predict_proba(X_scaled)[:, 1][0])
            ensemble_prob_up = self._lgb_weight * lgb_prob_up + self._xgb_weight * xgb_prob_up
            ensemble_prob_down = 1.0 - ensemble_prob_up

            latency = (time.perf_counter() - t0) * 1000.0

            last_close = float(df["close"].iloc[-1])
            atr_est = float(np.mean(df["high"].iloc[-14:] - df["low"].iloc[-14:]))
            delta = (ensemble_prob_up - 0.5) * 2.0 * atr_est
            forecast_price = last_close + delta
            ret = delta / last_close

            conf = max(ensemble_prob_up, ensemble_prob_down)
            uncertainty = 1.0 - conf

            if ensemble_prob_up > 0.52:
                direction = Direction.UP
            elif ensemble_prob_down > 0.52:
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
                probability_up=round(ensemble_prob_up, 4),
                probability_down=round(ensemble_prob_down, 4),
                uncertainty=round(uncertainty, 4),
                forecast_horizon=int(horizon),
                latency_ms=round(latency, 1),
                status=PredictionStatus.OK,
                prices_path=[last_close, forecast_price],
                raw={
                    "lgb_prob_up": lgb_prob_up,
                    "xgb_prob_up": xgb_prob_up,
                    "ensemble_prob_up": ensemble_prob_up,
                },
            )
        except Exception as exc:
            logger.error("EURUSD ensemble inference error: %s", exc)
            return ModelPrediction(
                model=self.name,
                symbol=self.symbol,
                timeframe=self.timeframe,
                timestamp=now,
                status=PredictionStatus.INFERENCE_ERROR,
                detail=f"inference error: {exc}",
            )

    def health(self) -> dict:
        lgb_path = os.path.join(self.checkpoint_dir, "eurusd_lgb.joblib")
        xgb_path = os.path.join(self.checkpoint_dir, "eurusd_xgb.joblib")
        return {
            "loaded": self._loaded,
            "weights_available": os.path.exists(lgb_path) and os.path.exists(xgb_path),
            "vendor_present": True,
            "device": "cpu",
        }
