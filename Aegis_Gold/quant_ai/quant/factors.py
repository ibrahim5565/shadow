"""AEGIS QUANT AI — technical & quant factor engines (Sections 20-21)."""
from __future__ import annotations

import logging
from typing import Dict

import numpy as np
import pandas as pd

logger = logging.getLogger("quant_ai.quant.factors")


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    ag = gain.ewm(alpha=1 / period, adjust=False).mean()
    al = loss.ewm(alpha=1 / period, adjust=False).mean()
    return 100.0 - 100.0 / (1.0 + ag / (al + 1e-12))


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def macd(series: pd.Series, fast=12, slow=26, signal=9) -> Dict[str, pd.Series]:
    ema_fast, ema_slow = ema(series, fast), ema(series, slow)
    m = ema_fast - ema_slow
    s = m.ewm(span=signal, adjust=False).mean()
    return {"macd": m, "signal": s, "hist": m - s}


def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """ADX (Average Directional Index) — a plain-pandas implementation."""
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    up_move = high - prev_high
    down_move = prev_low - low
    dmp = pd.Series(0.0, index=close.index)
    dmm = pd.Series(0.0, index=close.index)
    cond_up = (up_move > down_move) & (up_move > 0)
    cond_dn = (down_move > up_move) & (down_move > 0)
    dmp[cond_up] = up_move[cond_up]
    dmm[cond_dn] = down_move[cond_dn]
    tr_sum = tr.rolling(period).sum().replace(0.0, np.nan)
    dmp_s = 100.0 * (dmp.rolling(period).sum() / tr_sum)
    dmm_s = 100.0 * (dmm.rolling(period).sum() / tr_sum)
    diff = (dmp_s - dmm_s).abs()
    return diff.ewm(alpha=1 / period, adjust=False).mean()


class QuantFactorEngine:
    """Compute a clean feature frame from OHLCV data (no future information)."""

    def __init__(self):
        pass

    def compute(self, df: pd.DataFrame, spread_pts: float = 0.0, point: float = 0.01) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        r = close.pct_change()

        out["ret"] = r
        out["returns_autocorr_1"] = r.rolling(20).apply(lambda x: x.autocorr() if x.std() > 0 else 0.0, raw=False)
        out["zscore_20"] = (close - close.rolling(20).mean()) / (close.rolling(20).std() + 1e-12)
        out["rsi_14"] = rsi(close, 14)
        out["ema_10"] = ema(close, 10)
        out["ema_50"] = ema(close, 50)
        out["ema_ratio"] = out["ema_10"] / (out["ema_50"] + 1e-12) - 1.0
        out["sma_20"] = close.rolling(20).mean()
        out["slope_20"] = (out["sma_20"] - out["sma_20"].shift(10)) / 10.0 / (close + 1e-12)
        m = macd(close)
        out["macd_hist"] = m["hist"]
        out["adx_14"] = adx(high, low, close, 14)
        out["atr_20"] = (high - low).rolling(20).mean()
        out["bollinger_pos"] = (close - close.rolling(20).mean()) / (2 * close.rolling(20).std() + 1e-12)
        ll, ul = close.rolling(20).mean() - 2 * close.rolling(20).std(), \
                 close.rolling(20).mean() + 2 * close.rolling(20).std()
        out["bollinger_upper_break"] = (close > ul).astype(float)
        out["bollinger_lower_break"] = (close < ll).astype(float)
        cci = (close - out["sma_20"]) / (0.015 * (close - out["sma_20"]).abs().rolling(20).mean() + 1e-12)
        out["cci_20"] = cci
        out["roc_20"] = close.pct_change(20)
        out["momentum_10"] = close.diff(10) / (close + 1e-12)
        if "volume" in df.columns:
            vol = df["volume"].astype(float)
            out["volume_z"] = (vol - vol.rolling(20).mean()) / (vol.rolling(20).std() + 1e-12)
        else:
            out["volume_z"] = 0.0
        out["range_expansion"] = (high.rolling(10).max() - low.rolling(10).min()) / \
            (high.rolling(20).max() - low.rolling(20).min() + 1e-12)
        out["drawdown_hwm"] = close.cummax() - close
        out["spread_pts"] = spread_pts
        out["point"] = point
        return out

    def latest(self, df: pd.DataFrame, spread_pts: float = 0.0, point: float = 0.01) -> Dict[str, float]:
        f = self.compute(df, spread_pts=spread_pts, point=point)
        row = f.iloc[-1]
        return {k: (float(v) if pd.notna(v) else None) for k, v in row.items()}