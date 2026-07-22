"""
===========================================================================
AEGIS GOLD v9.0 -- Confidence Calibration Monitor
===========================================================================

PHILOSOPHY:
-----------
"A 70% confidence signal should win 70% of the time — if it doesn't,
your confidence scores are lying to you."

A well-calibrated model's stated confidence aligns with its actual win
rate per bucket. This monitor tracks that alignment on a rolling window
and degrades thresholds gracefully when miscalibration is detected.

CALIBRATION APPROACH:
---------------------
1. Bucket closed trades by confidence band (10-point bands: 40-49%, 50-59%, etc.)
2. Compute Brier Score: mean((confidence - outcome)^2) across all trades
   Perfect calibration = 0.0, worst = 1.0
3. Build reliability curve: for each bucket, compare
   stated_confidence_midpoint vs actual_win_rate
4. Flag bucket as miscalibrated if |actual_win_rate - midpoint| > 15%
   for 2+ consecutive evaluation windows
5. On flag: add threshold_penalty to brain's confidence threshold for
   each affected bucket until the next window shows re-calibration

STATE FILE: data/calibration_state.json
ENDPOINT:   GET /calibration
===========================================================================
"""

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("aegis.calibration")

BASE_DIR = Path(__file__).parent.parent
CALIBRATION_PATH = BASE_DIR / "data" / "calibration_state.json"
ATTRIBUTION_DB = BASE_DIR / "data" / "attribution.db"

ROLLING_WINDOW = 200         # Trades per evaluation window
MISCAL_THRESHOLD = 15.0      # % deviation from bucket midpoint to flag
CONSECUTIVE_FLAGS = 2        # Windows needed before auto-tighten
TIGHTEN_STEP = 5             # Confidence pts added per miscalibrated bucket


# ---------------------------------------------------------------------------
# Brier Score
# ---------------------------------------------------------------------------

def brier_score(confidences: List[float], outcomes: List[int]) -> float:
    """
    Compute Brier Score: mean squared error of (confidence - outcome).
    confidence: 0-100 scale (will be divided by 100 internally)
    outcome: 1 = WIN, 0 = LOSS
    Lower is better (0 = perfect, 1 = worst).
    """
    if not confidences or len(confidences) != len(outcomes):
        return 1.0
    n = len(confidences)
    total = sum((c / 100.0 - o) ** 2 for c, o in zip(confidences, outcomes))
    return round(total / n, 4)


# ---------------------------------------------------------------------------
# Reliability curve builder
# ---------------------------------------------------------------------------

def build_reliability_curve(
    confidences: List[float],
    outcomes: List[int]
) -> Dict[str, dict]:
    """
    Groups trades into 10-point bands and computes actual win rate per band.
    Returns dict keyed by band label e.g. "50-59%".
    """
    bands = defaultdict(lambda: {"count": 0, "wins": 0})
    for conf, outcome in zip(confidences, outcomes):
        low = (int(conf) // 10) * 10
        high = low + 9
        key = f"{low}-{high}%"
        bands[key]["count"] += 1
        bands[key]["wins"] += outcome

    result = {}
    for band, data in sorted(bands.items()):
        count = data["count"]
        wins = data["wins"]
        actual_wr = (wins / count * 100.0) if count > 0 else 0.0
        # Extract midpoint of stated confidence band
        low_pct = int(band.split("-")[0])
        midpoint = low_pct + 5.0
        deviation = actual_wr - midpoint
        result[band] = {
            "count": count,
            "actual_win_rate": round(actual_wr, 1),
            "stated_midpoint": midpoint,
            "deviation_pct": round(deviation, 1),
            "miscalibrated": abs(deviation) > MISCAL_THRESHOLD,
        }
    return result


# ---------------------------------------------------------------------------
# CalibrationMonitor
# ---------------------------------------------------------------------------

class CalibrationMonitor:
    """
    Periodically evaluates calibration from attribution.db and adjusts
    the confidence threshold penalty in response to miscalibration.
    """

    def __init__(self):
        self._state = self._load()
        self._alert_fn = None

    def set_alert(self, fn):
        self._alert_fn = fn

    def _alert(self, text: str):
        logger.warning(f"[CALIBRATION] {text}")
        if self._alert_fn:
            try:
                self._alert_fn(text)
            except Exception:
                pass

    def _load(self) -> dict:
        CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
        if CALIBRATION_PATH.exists():
            try:
                return json.loads(CALIBRATION_PATH.read_text())
            except Exception:
                pass
        return {
            "brier_score": None,
            "reliability_curve": {},
            "miscalibrated_buckets": [],
            "consecutive_flag_counts": {},
            "threshold_penalty": 0,
            "last_evaluated": None,
            "evaluation_count": 0,
            "total_trades_analyzed": 0,
        }

    def _save(self):
        try:
            CALIBRATION_PATH.write_text(json.dumps(self._state, indent=2))
        except Exception as e:
            logger.error(f"[CALIBRATION] Save failed: {e}")

    # ── Data loading ────────────────────────────────────────────

    def _load_recent_trades(self) -> Tuple[List[float], List[int]]:
        """Load last ROLLING_WINDOW trades from attribution.db."""
        # Ensure schema exists before reading (attribution_writer bootstraps on import,
        # but CalibrationMonitor may be instantiated before any trade has been written)
        try:
            from brain.attribution_writer import _ensure_schema as _aw_schema
            _aw_schema()
        except Exception:
            pass
        if not ATTRIBUTION_DB.exists():
            return [], []
        try:
            conn = sqlite3.connect(str(ATTRIBUTION_DB))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT confidence, outcome FROM attributions "
                "WHERE outcome IN ('WIN','LOSS') "
                "ORDER BY id DESC LIMIT ?",
                (ROLLING_WINDOW,)
            ).fetchall()
            conn.close()
            confidences = [float(r["confidence"] or 50) for r in rows]
            outcomes = [1 if r["outcome"] == "WIN" else 0 for r in rows]
            return confidences, outcomes
        except Exception as e:
            logger.error(f"[CALIBRATION] DB load failed: {e}")
            return [], []

    # ── Evaluation ─────────────────────────────────────────────

    def evaluate(self) -> dict:
        """
        Run a calibration evaluation pass.
        Returns the new calibration state dict.
        """
        confidences, outcomes = self._load_recent_trades()

        if len(confidences) < 20:
            logger.info(f"[CALIBRATION] Insufficient data ({len(confidences)} trades, need 20). Skipping.")
            return self._state

        bs = brier_score(confidences, outcomes)
        curve = build_reliability_curve(confidences, outcomes)

        # Find miscalibrated buckets
        miscal_buckets = [band for band, data in curve.items() if data["miscalibrated"]]

        # Update consecutive flag counts
        flag_counts = self._state.get("consecutive_flag_counts", {})
        # Decay all counts by 1 (buckets that recovered lose a flag)
        for k in list(flag_counts.keys()):
            if k not in miscal_buckets:
                flag_counts[k] = max(0, flag_counts.get(k, 0) - 1)
        # Increment active flags
        for bucket in miscal_buckets:
            flag_counts[bucket] = flag_counts.get(bucket, 0) + 1

        # Determine penalty
        # Any bucket flagged for CONSECUTIVE_FLAGS+ windows adds TIGHTEN_STEP
        chronic_buckets = [b for b, c in flag_counts.items() if c >= CONSECUTIVE_FLAGS]
        new_penalty = len(chronic_buckets) * TIGHTEN_STEP

        old_penalty = self._state.get("threshold_penalty", 0)
        if new_penalty != old_penalty:
            if new_penalty > old_penalty:
                self._alert(
                    f"[CALIBRATION] Miscalibration detected in {chronic_buckets}. "
                    f"Confidence threshold tightened by +{new_penalty}pts"
                )
            else:
                logger.info(
                    f"[CALIBRATION] Calibration improving — threshold penalty reduced to +{new_penalty}pts"
                )

        self._state.update({
            "brier_score": bs,
            "reliability_curve": curve,
            "miscalibrated_buckets": miscal_buckets,
            "chronic_buckets": chronic_buckets,
            "consecutive_flag_counts": flag_counts,
            "threshold_penalty": new_penalty,
            "last_evaluated": datetime.now(timezone.utc).isoformat(),
            "evaluation_count": self._state.get("evaluation_count", 0) + 1,
            "total_trades_analyzed": len(confidences),
            "calibration_ok": len(chronic_buckets) == 0,
        })
        self._save()

        brier_label = "GOOD" if bs < 0.20 else ("FAIR" if bs < 0.25 else "POOR")
        logger.info(
            f"[CALIBRATION] Eval #{self._state['evaluation_count']}: "
            f"Brier={bs:.4f} ({brier_label}), "
            f"Misc={miscal_buckets}, Penalty=+{new_penalty}pts"
        )
        return self._state

    # ── Live threshold adjustment ───────────────────────────────

    def get_threshold_penalty(self) -> int:
        """
        Returns the number of confidence points to ADD to any threshold
        to compensate for detected miscalibration. 0 = well-calibrated.
        """
        return int(self._state.get("threshold_penalty", 0))

    # ── QUANT X: Expected Calibration Error ─────────────────────

    def get_ece(self) -> Optional[float]:
        """
        Expected Calibration Error (ECE):
        Weighted average of |actual_win_rate - stated_confidence| per bucket.
        Lower is better (0 = perfectly calibrated).

        Returns None if reliability curve not yet computed.
        """
        curve = self._state.get("reliability_curve", {})
        if not curve:
            return None
        try:
            total_trades = sum(data["count"] for data in curve.values())
            if total_trades == 0:
                return None
            ece = sum(
                data["count"] / total_trades * abs(data["actual_win_rate"] - data["stated_midpoint"]) / 100.0
                for data in curve.values()
            )
            return round(ece, 6)
        except Exception:
            return None

    def reliability_diagram_data(self) -> list:
        """
        Returns list of dicts suitable for charting a reliability diagram.
        Each element: {band, stated_midpoint, actual_win_rate, count, deviation_pct}
        """
        curve = self._state.get("reliability_curve", {})
        return [
            {
                "band":              band,
                "stated_midpoint":   data["stated_midpoint"],
                "actual_win_rate":   data["actual_win_rate"],
                "count":             data["count"],
                "deviation_pct":     data["deviation_pct"],
                "miscalibrated":     data.get("miscalibrated", False),
            }
            for band, data in sorted(curve.items())
        ]

    # ── QUANT X: Demotion trigger ────────────────────────────────

    def is_demotion_candidate(self) -> bool:
        """
        Returns True when chronic miscalibration has persisted for
        QX["arena_demotion_miscal_windows"] consecutive evaluation windows.
        A miscalibrated model is a demotion candidate even when its raw
        win rate still looks fine — confidence scores are lying to you.
        """
        try:
            from config.quant_x_config import QX
            required_windows = int(QX.get("arena_demotion_miscal_windows") or 3)
        except Exception:
            required_windows = 3

        flag_counts = self._state.get("consecutive_flag_counts", {})
        chronic = [b for b, c in flag_counts.items() if c >= required_windows]
        return len(chronic) > 0

    def set_arena_callback(self, fn) -> None:
        """
        Register a callback that will be invoked when is_demotion_candidate()
        becomes True after an evaluate() call.
        fn signature: fn(reason: str) -> None
        """
        self._arena_callback = fn

    def get_status(self) -> dict:
        state = dict(self._state)
        state["ece"] = self.get_ece()
        state["is_demotion_candidate"] = self.is_demotion_candidate()
        return state


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_monitor: Optional[CalibrationMonitor] = None


def get_calibration_monitor() -> CalibrationMonitor:
    global _monitor
    if _monitor is None:
        _monitor = CalibrationMonitor()
    return _monitor


def get_threshold_penalty() -> int:
    """Convenience: get calibration-based confidence penalty."""
    return get_calibration_monitor().get_threshold_penalty()


# ---------------------------------------------------------------------------
# QUANT X: Meta-Labeler (separate secondary model)
# ---------------------------------------------------------------------------

class MetaLabeler:
    """
    Secondary meta-model:
    "Given this primary signal and current conditions, is the bet actually good?"

    Separates "which direction" from "should I take this trade" — the latter
    is predicted by this model from past closed-trade outcomes and current
    market state.

    Features:
        - Primary signal strength (confidence from brain.py)
        - Current regime label + ambiguity flag
        - Calibration state (Brier score, ECE)
        - Drift state (n drifting features)
        - Macro context (blackout, time to next event)

    Target:
        1 if the primary signal's trade won, 0 if it lost.

    FEATURE FLAG: QX["meta_labeler"]
    """

    MIN_TRADES = 100

    def __init__(self):
        self._model   = None
        self._scaler  = None
        self._fitted  = False
        self._n_trained = 0

    def _build_feature_row(self, context: dict) -> List[float]:
        """
        Build a feature vector from a context dict.
        Keys: primary_confidence, regime_label, regime_ambiguous,
              brier_score, ece, n_drifting, event_blackout, minutes_to_next_high
        """
        regime_map = {
            "TRENDING_UP": 1.0, "TRENDING_DOWN": -1.0,
            "RANGING": 0.0, "VOLATILE": 0.5,
            "WEAK_TREND": 0.25, "TRANSITIONAL": 0.0,
        }
        return [
            float(context.get("primary_confidence", 50)) / 100.0,
            float(regime_map.get(context.get("regime_label", "RANGING"), 0.0)),
            1.0 if context.get("regime_ambiguous", False) else 0.0,
            float(context.get("brier_score") or 0.25),
            float(context.get("ece") or 0.10),
            float(context.get("n_drifting", 0)) / 4.0,  # normalised 0-1
            1.0 if context.get("event_blackout", False) else 0.0,
            min(float(context.get("minutes_to_next_high", 9999)), 120.0) / 120.0,
        ]

    def fit(self, trade_contexts: List[dict], outcomes: List[int]) -> bool:
        """
        Train on historical trade context dicts and their binary outcomes.
        Returns True on success.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("meta_labeler"):
                return False
            min_trades = int(QX.get("meta_labeler_min_trades") or self.MIN_TRADES)
        except Exception:
            return False

        if len(trade_contexts) < min_trades:
            logger.info(
                "[META-LABEL] Need %d trades, have %d — not training yet",
                min_trades, len(trade_contexts)
            )
            return False

        try:
            if not SKLEARN_AVAILABLE_CALIB:
                return False
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler

            X = [self._build_feature_row(ctx) for ctx in trade_contexts]
            self._scaler = StandardScaler()
            X_sc = self._scaler.fit_transform(X)
            self._model = LogisticRegression(
                max_iter=300, random_state=42, class_weight="balanced"
            )
            self._model.fit(X_sc, outcomes)
            self._fitted    = True
            self._n_trained = len(trade_contexts)
            logger.info("[META-LABEL] Trained on %d trades", self._n_trained)
            return True
        except Exception as exc:
            logger.warning("[META-LABEL] fit() failed: %s", exc)
            return False

    def predict_meta_confidence(self, context: dict) -> float:
        """
        Returns a meta-confidence multiplier (0-1).
        1.0 = fully trust primary signal.
        <0.5 = primary signal probably not good in current conditions.
        Falls back to 1.0 (neutral) when not fitted.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("meta_labeler") or not self._fitted:
                return 1.0
        except Exception:
            return 1.0

        try:
            x = self._build_feature_row(context)
            x_sc = self._scaler.transform([x])
            prob = float(self._model.predict_proba(x_sc)[0][1])
            return round(prob, 4)
        except Exception as exc:
            logger.debug("[META-LABEL] predict error: %s", exc)
            return 1.0

    def get_status(self) -> dict:
        return {
            "fitted":    self._fitted,
            "n_trained": self._n_trained,
        }


# Detect sklearn availability for meta-labeler (separate guard)
try:
    from sklearn.linear_model import LogisticRegression as _LR
    SKLEARN_AVAILABLE_CALIB = True
except ImportError:
    SKLEARN_AVAILABLE_CALIB = False


_meta_labeler: Optional[MetaLabeler] = None

def get_meta_labeler() -> MetaLabeler:
    global _meta_labeler
    if _meta_labeler is None:
        _meta_labeler = MetaLabeler()
    return _meta_labeler


# ---------------------------------------------------------------------------
# Calibrated Confidence Lookup (Isotonic Regression output)
# ---------------------------------------------------------------------------

_CALIB_MODEL_PATH = BASE_DIR / "data" / "calibration_model.json"
_calib_lookup_cache: Optional[dict] = None

def get_calibrated_confidence(raw_confidence: float) -> float:
    """
    Map a raw stated confidence score (50–100%) to its empirical calibrated win rate (50–100%)
    using the isotonic regression lookup table saved in data/calibration_model.json.
    Falls back to raw_confidence if calibration_model.json is absent.
    """
    global _calib_lookup_cache
    try:
        if _calib_lookup_cache is None and _CALIB_MODEL_PATH.exists():
            with open(_CALIB_MODEL_PATH) as f:
                data = json.load(f)
            _calib_lookup_cache = {int(k): float(v) for k, v in data.get("confidence_lookup_table", {}).items()}

        if _calib_lookup_cache:
            key = int(round(clamp_confidence(raw_confidence)))
            return _calib_lookup_cache.get(key, float(raw_confidence))
    except Exception as exc:
        logger.debug("[CALIBRATION] get_calibrated_confidence error: %s", exc)

    return float(raw_confidence)


def clamp_confidence(conf: float) -> float:
    """Clamp confidence score to [50.0, 100.0]."""
    return max(50.0, min(100.0, float(conf)))

