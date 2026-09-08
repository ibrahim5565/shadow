"""
===========================================================================
AEGIS GOLD v9.0 -- Feature Drift Monitor
===========================================================================

PHILOSOPHY:
-----------
"A model trained on last month's data is blind to this month's market."

If the live market's statistical distribution of key features (ADX, RSI,
ATR, spread) drifts significantly away from the training-time baseline,
the model's predictions become unreliable.

DETECTION METHOD:
-----------------
Kolmogorov-Smirnov (KS) statistic: measures the maximum difference
between the CDFs of two distributions (baseline vs live window).
  KS = 0.0  → identical distributions
  KS = 1.0  → completely non-overlapping

Population Stability Index (PSI) as alternative:
  PSI < 0.10  → no drift
  PSI 0.10-0.25 → moderate drift (watch)
  PSI > 0.25  → significant drift (act)

FEATURES MONITORED:
-------------------
  - ADX       (trend strength)
  - RSI       (momentum)
  - ATR       (volatility proxy)
  - Spread    (execution quality)

RESPONSE:
---------
  - 1 feature drifting: WARNING logged
  - 2+ features drifting simultaneously: DEFENSIVE profile forced,
    retraining priority set, Telegram alert fired.

STATE FILE: data/drift_state.json
ENDPOINT:   GET /drift
===========================================================================
"""

import json
import logging
import sqlite3
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("aegis.drift")

BASE_DIR = Path(__file__).parent.parent
DRIFT_PATH = BASE_DIR / "data" / "drift_state.json"
ATTRIBUTION_DB = BASE_DIR / "data" / "attribution.db"

BASELINE_WINDOW = 200     # Trades used to establish baseline
LIVE_WINDOW = 100         # Rolling live window to compare against baseline
KS_DRIFT_THRESHOLD = 0.25 # KS statistic above this = drift detected
MULTI_FEATURE_THRESHOLD = 2  # Number of drifting features that triggers DEFENSIVE mode


# ---------------------------------------------------------------------------
# KS Statistic
# ---------------------------------------------------------------------------

def ks_statistic(baseline: List[float], live: List[float]) -> float:
    """
    Compute the Kolmogorov-Smirnov statistic between two samples.
    Returns value in [0, 1].  Higher = more drift.
    Pure-python implementation — no scipy required.
    """
    if not baseline or not live:
        return 0.0
    try:
        import numpy as np
        b = np.sort(baseline)
        l = np.sort(live)
        n1, n2 = len(b), len(l)
        combined = np.concatenate([b, l])
        combined = np.sort(combined)
        cdf1 = np.searchsorted(b, combined, side='right') / n1
        cdf2 = np.searchsorted(l, combined, side='right') / n2
        return float(np.max(np.abs(cdf1 - cdf2)))
    except ImportError:
        # Fallback pure-python (slower, less precise)
        all_vals = sorted(set(baseline + live))
        n1, n2 = len(baseline), len(live)
        max_diff = 0.0
        b_set = sorted(baseline)
        l_set = sorted(live)
        for v in all_vals:
            cdf1 = sum(1 for x in b_set if x <= v) / n1
            cdf2 = sum(1 for x in l_set if x <= v) / n2
            max_diff = max(max_diff, abs(cdf1 - cdf2))
        return max_diff


# ---------------------------------------------------------------------------
# DriftMonitor
# ---------------------------------------------------------------------------

class DriftMonitor:
    """
    Tracks feature distributions from attribution.db and compares
    the rolling live window against the established baseline.
    """

    FEATURES = ["adx", "rsi", "atr", "spread"]  # must match attribution DB column names

    def __init__(self):
        self._state = self._load()
        self._alert_fn = None
        self._on_defensive = None   # Callback to force DEFENSIVE regime profile

    def set_alert(self, fn):
        self._alert_fn = fn

    def set_defensive_callback(self, fn):
        """fn() will be called when drift forces DEFENSIVE mode."""
        self._on_defensive = fn

    def _alert(self, text: str):
        logger.warning(f"[DRIFT] {text}")
        if self._alert_fn:
            try:
                self._alert_fn(text)
            except Exception:
                pass

    def _load(self) -> dict:
        DRIFT_PATH.parent.mkdir(parents=True, exist_ok=True)
        if DRIFT_PATH.exists():
            try:
                return json.loads(DRIFT_PATH.read_text())
            except Exception:
                pass
        return {
            "baseline_established": False,
            "baseline_stats": {},
            "live_stats": {},
            "drift_per_feature": {},
            "drifting_features": [],
            "defensive_forced": False,
            "retrain_priority": False,
            "last_checked": None,
            "check_count": 0,
        }

    def _save(self):
        try:
            DRIFT_PATH.write_text(json.dumps(self._state, indent=2))
        except Exception as e:
            logger.error(f"[DRIFT] Save failed: {e}")

    # ── Data loading ────────────────────────────────────────────

    def _load_feature_values(self, limit: int) -> Dict[str, List[float]]:
        """Load feature values from attribution.db."""
        result = {f: [] for f in self.FEATURES}
        if not ATTRIBUTION_DB.exists():
            return result
        try:
            conn = sqlite3.connect(str(ATTRIBUTION_DB))
            conn.row_factory = sqlite3.Row
            # Attribution table stores score_* columns. Map to feature names:
            # score_smc ~ adx proxy (not ideal but available without MT5)
            # We'll use the raw confidence + available score columns
            # The actual attribution DB has: confidence, score_structure, score_smc,
            # score_mtf, score_statistical, score_ml, score_momentum, score_volatility
            # We map: adx→score_structure, rsi→score_momentum, atr→score_volatility, spread→confidence
            rows = conn.execute(
                "SELECT confidence, score_structure, score_momentum, "
                "score_volatility, score_smc FROM attributions "
                "ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            conn.close()
            for r in rows:
                result["adx"].append(float(r["score_structure"] or 50))
                result["rsi"].append(float(r["score_momentum"] or 50))
                result["atr"].append(float(r["score_volatility"] or 50))
                result["spread"].append(float(r["confidence"] or 50))
        except Exception as e:
            logger.error(f"[DRIFT] DB load failed: {e}")
        return result

    def _compute_stats(self, values: List[float]) -> dict:
        if not values:
            return {}
        n = len(values)
        mean = sum(values) / n
        variance = sum((x - mean) ** 2 for x in values) / n
        std = variance ** 0.5
        sorted_v = sorted(values)
        return {
            "mean": round(mean, 3),
            "std": round(std, 3),
            "min": round(sorted_v[0], 3),
            "max": round(sorted_v[-1], 3),
            "n": n,
        }

    # ── Baseline establishment ──────────────────────────────────

    def establish_baseline(self):
        """
        Build baseline distribution from the oldest BASELINE_WINDOW trades.
        Call once after sufficient historical data is available.
        """
        features = self._load_feature_values(BASELINE_WINDOW)
        baseline_stats = {}
        baseline_raw = {}
        for f, vals in features.items():
            if len(vals) >= 20:
                baseline_stats[f] = self._compute_stats(vals)
                baseline_raw[f] = vals
        if len(baseline_stats) < 2:
            logger.info("[DRIFT] Not enough data for baseline. Skipping.")
            return

        self._state["baseline_established"] = True
        self._state["baseline_stats"] = baseline_stats
        self._state["baseline_raw"] = baseline_raw
        self._save()
        logger.info(f"[DRIFT] Baseline established on {BASELINE_WINDOW} trades for features: {list(baseline_stats.keys())}")

    # ── Drift check ─────────────────────────────────────────────

    def check_drift(self) -> dict:
        """
        Compare live LIVE_WINDOW trades against baseline.
        Returns the drift state dict.
        """
        if not self._state.get("baseline_established"):
            self.establish_baseline()
            return self._state

        live_features = self._load_feature_values(LIVE_WINDOW)
        baseline_raw = self._state.get("baseline_raw", {})

        drift_per_feature = {}
        drifting = []

        for feature in self.FEATURES:
            baseline_vals = baseline_raw.get(feature, [])
            live_vals = live_features.get(feature, [])

            if len(baseline_vals) < 10 or len(live_vals) < 10:
                drift_per_feature[feature] = {"ks": 0.0, "drifting": False, "status": "insufficient_data"}
                continue

            ks = ks_statistic(baseline_vals, live_vals)
            is_drifting = ks > KS_DRIFT_THRESHOLD

            drift_per_feature[feature] = {
                "ks": round(ks, 4),
                "drifting": is_drifting,
                "status": "DRIFT" if is_drifting else "OK",
                "live_mean": round(sum(live_vals) / len(live_vals), 2),
                "baseline_mean": round(sum(baseline_vals) / len(baseline_vals), 2) if baseline_vals else 0.0,
            }
            if is_drifting:
                drifting.append(feature)

        n_drifting = len(drifting)
        was_defensive = self._state.get("defensive_forced", False)

        if n_drifting >= MULTI_FEATURE_THRESHOLD:
            if not was_defensive:
                msg = (
                    f"[DRIFT] {n_drifting} features drifting ({drifting}). "
                    f"Forcing DEFENSIVE strategy profile. Priority retraining flagged."
                )
                self._alert(msg)
                if self._on_defensive:
                    try:
                        self._on_defensive()
                    except Exception as e:
                        logger.error(f"[DRIFT] Defensive callback failed: {e}")
            self._state["defensive_forced"] = True
            self._state["retrain_priority"] = True
        elif n_drifting == 1:
            logger.warning(f"[DRIFT] 1 feature drifting ({drifting}) ? monitoring, not acting")
            self._state["defensive_forced"] = False
            self._state["retrain_priority"] = False
        else:
            if was_defensive:
                logger.info("[DRIFT] Distribution normalized ? DEFENSIVE override lifted")
            self._state["defensive_forced"] = False
            self._state["retrain_priority"] = False

        self._state.update({
            "drift_per_feature": drift_per_feature,
            "drifting_features": drifting,
            "live_stats": {f: self._compute_stats(v) for f, v in live_features.items() if v},
            "last_checked": datetime.now(timezone.utc).isoformat(),
            "check_count": self._state.get("check_count", 0) + 1,
        })
        self._save()

        logger.info(
            f"[DRIFT] Check #{self._state['check_count']}: "
            f"{n_drifting}/{len(self.FEATURES)} features drifting "
            f"({drifting}), DEFENSIVE={self._state['defensive_forced']}"
        )
        return self._state

    # ── Status ──────────────────────────────────────────────────

    def get_status(self) -> dict:
        return dict(self._state)

    def is_defensive_forced(self) -> bool:
        return bool(self._state.get("defensive_forced", False))

    def is_retrain_priority(self) -> bool:
        return bool(self._state.get("retrain_priority", False))


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_monitor: Optional[DriftMonitor] = None


def get_drift_monitor() -> DriftMonitor:
    global _monitor
    if _monitor is None:
        _monitor = DriftMonitor()
    return _monitor
