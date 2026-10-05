"""AEGIS QUANT AI — anomaly detection layer (Section 17).

Detects: broken candles, NaNs/zeros, price spikes, abnormal spread and
abnormal volatility using Isolation Forest + statistical checks.
The layer can BLOCK a trade (anomaly.block = True).
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger("quant_ai.quant.anomaly")


class AnomalyDetector:
    def __init__(self, contamination: float = 0.05, returns_window: int = 60,
                 spread_z_limit: float = 4.0):
        self.contamination = contamination
        self.returns_window = returns_window
        self.spread_z_limit = spread_z_limit
        self._iso = None

    def _fit_isolation_forest(self, features: np.ndarray) -> None:
        try:
            from sklearn.ensemble import IsolationForest
            iso = IsolationForest(contamination=self.contamination, random_state=42, n_jobs=1)
            iso.fit(features)
            self._iso = iso
        except Exception as exc:
            logger.warning("IsolationForest unavailable: %s", exc)
            self._iso = None

    def detect(self, df: pd.DataFrame, spread_pts: float = 0.0,
               spread_history: Optional[List[float]] = None,
               vol_percentile: float = 0.5) -> Dict:
        """Return {'block': bool, 'checks': {...}}."""
        checks: Dict[str, dict] = {}
        block = False

        # 1. NaN / Inf
        matrix = df[["open", "high", "low", "close"]]
        nan_count = int(matrix.isnull().sum().sum())
        inf_count = int(np.isinf(matrix.astype(float).values).sum())
        checks["nan_check"] = {"ok": nan_count == 0, "nan": nan_count}
        checks["inf_check"] = {"ok": inf_count == 0, "inf": inf_count}
        if nan_count or inf_count:
            block = True

        # 2. broken candles / non-positive prices
        closes = df["close"].astype(float)
        broken = int((df["high"] < df[["open", "close"]].max(axis=1)).sum() +
                     (df["low"] > df[["open", "close"]].min(axis=1)).sum() +
                     (closes <= 0).sum())
        checks["candle_integrity"] = {"ok": broken == 0, "broken_candles": broken}
        if broken:
            block = True

        # 3. return spike via z-score
        r = closes.pct_change().dropna()
        if len(r) > 10:
            z = np.abs((r - r.mean()) / (r.std() + 1e-12))
            max_z = float(np.nanmax(z.values))
            spike = bool(max_z > 10.0)
            checks["return_spike"] = {"ok": not spike, "max_z": round(max_z, 1)}
            if spike:
                block = True
        else:
            checks["return_spike"] = {"ok": True, "max_z": 0.0}

        # 4. spread anomaly (broker/data-feed)
        spread_ok = True
        if spread_history and spread_pts > 0:
            arr = np.asarray(spread_history, dtype=float)
            if len(arr) >= 5 and arr.std() > 0:
                z = abs((spread_pts - arr.mean()) / (arr.std() + 1e-12))
                spread_ok = bool(z <= self.spread_z_limit)
            checks["spread"] = {"ok": spread_ok, "spread_pts": float(spread_pts),
                                "z": round(float(z), 1) if len(arr) >= 5 and arr.std() > 0 else 0.0}
            if not spread_ok:
                block = True
        else:
            checks["spread"] = {"ok": True, "spread_pts": float(spread_pts)}

        # 5. IsolationForest multivariate context anomaly (returns + range)
        if len(df) >= self.returns_window:
            feats = pd.DataFrame({
                "ret": r.tail(self.returns_window).values,
                "range": (df["high"] - df["low"]).tail(self.returns_window).values / (closes.tail(self.returns_window).values + 1e-9),
            }).replace([np.inf, -np.inf], np.nan).dropna()
            if len(feats) > 20 and feats.std().sum() > 0:
                self._fit_isolation_forest(feats.values)
                if self._iso is not None:
                    pred = self._iso.predict(feats.tail(1).values)
                    iso_anomaly = bool(pred[0] == -1)
                    checks["isolation_forest"] = {"ok": not iso_anomaly, "label": int(pred[0])}
                    if iso_anomaly:
                        block = True
        if "isolation_forest" not in checks:
            checks["isolation_forest"] = {"ok": True, "label": 1}

        # 6. volatility percentile extreme
        checks["vol_percentile"] = {"ok": vol_percentile < 1.0, "vol_percentile": round(float(vol_percentile), 3)}

        return {"block": block, "checks": checks}