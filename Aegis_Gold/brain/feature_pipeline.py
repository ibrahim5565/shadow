"""
AEGIS QUANT X — Extended Feature Pipeline
==========================================
Configurable, versioned feature engineering pipeline.

Feature families:
  ┌─────────────────────────────────────────────────────┐
  │  1. Multi-scale returns (1, 5, 15, 60 bar windows)  │
  │  2. Rolling realized variance, Yang-Zhang estimator │
  │  3. Higher-order moments (skew, kurtosis)           │
  │  4. Shannon entropy, approximate entropy            │
  │  5. Hurst exponent (R/S analysis)                   │
  │  6. Fractal dimension (Higuchi method)              │
  │  7. Wavelet energy ratios (Haar, 3-level)           │
  │  8. Trend persistence / autocorrelation             │
  │  9. Session & calendar features                     │
  │ 10. Macro / cross-asset tags (from macro_context)   │
  │ 11. Meta features (calibration, drift, regime conf) │
  └─────────────────────────────────────────────────────┘

POINT-IN-TIME CORRECTNESS
--------------------------
Every feature is computed from data available at bar CLOSE time.
No feature uses the current bar's close to compute something attributed
to that bar's open (look-ahead).  The pipeline only calls the PIT
decorator on the entry point; individual helpers are always called with
explicit bar arrays truncated to the decision bar.

VERSIONING
-----------
  - Schema hash (SHA-1 of feature name list) stored in every record.
  - Changing the feature set bumps the schema hash; CalibrationMonitor
    can detect this and force a baseline reset.

FEATURE FLAG
-----------
  QX["extended_features"].  When off, extract() returns an empty
  ExtendedFeatureSet and the existing pipeline continues unchanged.
"""

from __future__ import annotations

import hashlib
import logging
import math
import statistics
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger("aegis.feature_pipeline")


# ---------------------------------------------------------------------------
# Extended feature dataclass
# ---------------------------------------------------------------------------

@dataclass
class ExtendedFeatureSet:
    """
    Full quantitative feature vector for one decision bar.
    All fields default to None so partial extraction is safe.
    """

    # ── Multi-scale returns ──────────────────────────────────────────────────
    ret_1:  Optional[float] = None   # log return over 1 bar
    ret_5:  Optional[float] = None
    ret_15: Optional[float] = None
    ret_60: Optional[float] = None

    # ── Volatility ───────────────────────────────────────────────────────────
    realized_var_20:   Optional[float] = None  # 20-bar realized variance
    realized_vol_20:   Optional[float] = None  # sqrt(realized_var)
    yang_zhang_vol:    Optional[float] = None  # Yang-Zhang close-to-close + open/high/low
    atr_normalized:    Optional[float] = None  # ATR / price (dimensionless)

    # ── Higher-order moments ─────────────────────────────────────────────────
    skewness_50:   Optional[float] = None
    kurtosis_50:   Optional[float] = None

    # ── Entropy ─────────────────────────────────────────────────────────────
    shannon_entropy_50: Optional[float] = None
    approx_entropy_50:  Optional[float] = None

    # ── Hurst exponent ───────────────────────────────────────────────────────
    hurst_100:   Optional[float] = None   # H < 0.5 = mean-reverting, H > 0.5 = trending

    # ── Fractal dimension ────────────────────────────────────────────────────
    fractal_dim_50:  Optional[float] = None  # 1-2; closer to 2 = more complex/noisy

    # ── Wavelet features ─────────────────────────────────────────────────────
    wavelet_energy_l1: Optional[float] = None  # Level-1 detail energy ratio
    wavelet_energy_l2: Optional[float] = None
    wavelet_energy_l3: Optional[float] = None

    # ── Trend persistence ────────────────────────────────────────────────────
    autocorr_lag1:  Optional[float] = None
    autocorr_lag5:  Optional[float] = None

    # ── Price acceleration ───────────────────────────────────────────────────
    price_accel:    Optional[float] = None   # Δ(return) — derivative of momentum

    # ── Session & calendar ───────────────────────────────────────────────────
    hour_utc:      Optional[int]   = None
    day_of_week:   Optional[int]   = None   # 0=Mon … 6=Sun
    days_to_monday: Optional[int]  = None   # proxy for week position

    # ── Macro / cross-asset ──────────────────────────────────────────────────
    event_blackout:        Optional[bool]  = None
    event_reduced_size:    Optional[bool]  = None
    minutes_to_next_high:  Optional[int]   = None
    macro_dxy:             Optional[float] = None
    macro_dxy_chg:         Optional[float] = None
    macro_us10y:           Optional[float] = None
    macro_real_yield:      Optional[float] = None
    macro_gold_dxy_corr:   Optional[float] = None

    # ── Meta / system features ───────────────────────────────────────────────
    calibration_brier:     Optional[float] = None
    calibration_ece:       Optional[float] = None
    drift_defensive:       Optional[bool]  = None
    drift_features_count:  Optional[int]   = None
    regime_confidence:     Optional[float] = None
    regime_ambiguous:      Optional[bool]  = None

    # ── Schema version ───────────────────────────────────────────────────────
    schema_hash:   str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def to_model_vector(self, exclude_meta: bool = True) -> List[float]:
        """
        Flatten to a numeric list for ML model input.
        None values → 0.0.  Booleans → 1.0 / 0.0.
        Meta fields and schema_hash are excluded by default.
        """
        meta_keys = {"schema_hash", "event_blackout", "event_reduced_size",
                     "drift_defensive", "regime_ambiguous"}
        if exclude_meta:
            meta_keys.update({"calibration_brier", "calibration_ece",
                               "drift_features_count", "regime_confidence"})
        d = self.to_dict()
        vec = []
        for k, v in d.items():
            if k in meta_keys:
                continue
            if v is None:
                vec.append(0.0)
            elif isinstance(v, bool):
                vec.append(1.0 if v else 0.0)
            else:
                try:
                    vec.append(float(v))
                except (TypeError, ValueError):
                    vec.append(0.0)
        return vec


# ---------------------------------------------------------------------------
# Schema hash (version fingerprint)
# ---------------------------------------------------------------------------

def _compute_schema_hash() -> str:
    """SHA-1 of the sorted field names — bumps when feature set changes."""
    names = sorted(f.name for f in ExtendedFeatureSet.__dataclass_fields__.values()
                   if f.name != "schema_hash")
    raw = ",".join(names).encode()
    return hashlib.sha1(raw).hexdigest()[:12]


_SCHEMA_HASH = _compute_schema_hash()


# ---------------------------------------------------------------------------
# Feature Pipeline
# ---------------------------------------------------------------------------

class FeaturePipeline:
    """
    Stateless pipeline: call extract() each decision cycle.
    Thread-safe (no mutable state).
    """

    def process_market_data(self, bars, ticks=None, **kwargs) -> ExtendedFeatureSet:
        """Alias for extract()."""
        return self.extract(bars, ticks=ticks, **kwargs)

    def process_data(self, bars, ticks=None, **kwargs) -> ExtendedFeatureSet:
        """Alias for extract()."""
        return self.extract(bars, ticks=ticks, **kwargs)

    def extract(
        self,
        bars,
        ticks=None,
        macro_tags: Optional[dict] = None,
        regime_state=None,
        calibration_state: Optional[dict] = None,
        drift_state: Optional[dict] = None,
    ) -> ExtendedFeatureSet:
        """
        Build ExtendedFeatureSet from raw inputs.

        Parameters
        ----------
        bars            : list/array of MT5 bars (dict or structured array)
        ticks           : optional tick array (for velocity/microstructure)
        macro_tags      : dict from MacroContext.get_bar_tags()
        regime_state    : brain.regime.RegimeState (with optional .regime_confidence)
        calibration_state: dict from CalibrationMonitor.get_status()
        drift_state     : dict from DriftMonitor.get_status()

        Returns
        -------
        ExtendedFeatureSet — all fields None on failure.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("extended_features"):
                return ExtendedFeatureSet(schema_hash=_SCHEMA_HASH)
        except Exception:
            return ExtendedFeatureSet(schema_hash=_SCHEMA_HASH)

        fs = ExtendedFeatureSet(schema_hash=_SCHEMA_HASH)

        try:
            closes = _extract_closes(bars)
            highs  = _extract_highs(bars)
            lows   = _extract_lows(bars)
            opens  = _extract_opens(bars)

            if len(closes) < 15:
                return fs

            # 1. Multi-scale returns
            for window, attr in [(1, "ret_1"), (5, "ret_5"),
                                  (15, "ret_15"), (60, "ret_60")]:
                if len(closes) > window:
                    val = _log_return(closes, window)
                    setattr(fs, attr, val)

            # 2. Volatility
            fs.realized_var_20 = _realized_variance(closes, 20)
            fs.realized_vol_20 = math.sqrt(fs.realized_var_20) if fs.realized_var_20 else None
            fs.yang_zhang_vol  = _yang_zhang_vol(opens, highs, lows, closes, 20)
            if closes[-1] > 0 and len(highs) >= 14 and len(lows) >= 14:
                fs.atr_normalized = _simple_atr(highs, lows, closes, 14) / closes[-1]

            # 3. Higher-order moments
            if len(closes) >= 50:
                rets = _returns_series(closes, 50)
                fs.skewness_50 = _skewness(rets)
                fs.kurtosis_50 = _kurtosis(rets)

            # 4. Entropy
            if len(closes) >= 50:
                fs.shannon_entropy_50 = _shannon_entropy(closes[-50:])
                fs.approx_entropy_50  = _approx_entropy(closes[-50:], m=2, r_factor=0.2)

            # 5. Hurst exponent
            if len(closes) >= 100:
                fs.hurst_100 = _hurst_exponent(closes[-100:])

            # 6. Fractal dimension
            if len(closes) >= 50:
                fs.fractal_dim_50 = _higuchi_fractal_dim(closes[-50:], k_max=5)

            # 7. Wavelet features
            if len(closes) >= 16:
                e1, e2, e3 = _haar_wavelet_energies(closes[-64:] if len(closes) >= 64 else closes[-16:])
                fs.wavelet_energy_l1 = e1
                fs.wavelet_energy_l2 = e2
                fs.wavelet_energy_l3 = e3

            # 8. Autocorrelation
            if len(closes) >= 20:
                rets_full = _returns_series(closes, min(len(closes)-1, 60))
                fs.autocorr_lag1 = _autocorrelation(rets_full, 1)
                fs.autocorr_lag5 = _autocorrelation(rets_full, 5)

            # 9. Price acceleration
            if len(closes) >= 4:
                r1 = _log_return(closes, 1)
                r2 = _log_return(closes[:-1], 1) if len(closes) >= 3 else 0.0
                fs.price_accel = (r1 or 0.0) - (r2 or 0.0)

            # 10. Session & calendar
            now = datetime.now(timezone.utc)
            fs.hour_utc      = now.hour
            fs.day_of_week   = now.weekday()
            fs.days_to_monday = (7 - now.weekday()) % 7

            # 11. Macro tags
            if macro_tags:
                fs.event_blackout       = macro_tags.get("event_blackout")
                fs.event_reduced_size   = macro_tags.get("event_reduced_size")
                fs.minutes_to_next_high = macro_tags.get("minutes_to_next_high")
                fs.macro_dxy            = macro_tags.get("macro_dxy")
                fs.macro_dxy_chg        = macro_tags.get("macro_dxy_chg")
                fs.macro_us10y          = macro_tags.get("macro_us10y")
                fs.macro_real_yield     = macro_tags.get("macro_real_yield")
                fs.macro_gold_dxy_corr  = macro_tags.get("macro_gold_dxy_corr")

            # 12. Meta / system features
            if regime_state is not None:
                fs.regime_confidence = getattr(regime_state, "regime_confidence", None)
                fs.regime_ambiguous  = getattr(regime_state, "ambiguous", None)

            if calibration_state:
                fs.calibration_brier = calibration_state.get("brier_score")
                fs.calibration_ece   = calibration_state.get("ece")

            if drift_state:
                fs.drift_defensive      = drift_state.get("defensive_forced", False)
                fs.drift_features_count = len(drift_state.get("drifting_features", []))

        except Exception as exc:
            logger.warning("[FEATURES] Extraction error (returning partial): %s", exc)

        return fs


# ---------------------------------------------------------------------------
# Mathematical helpers — all pure Python, no scipy
# ---------------------------------------------------------------------------

def _extract_closes(bars) -> List[float]:
    try:
        if bars is None or len(bars) == 0:
            return []
        if isinstance(bars[0], dict):
            return [float(b["close"]) for b in bars]
        return [float(b[4]) for b in bars]
    except Exception:
        return []

def _extract_highs(bars) -> List[float]:
    try:
        if isinstance(bars[0], dict):
            return [float(b["high"]) for b in bars]
        return [float(b[2]) for b in bars]
    except Exception:
        return []

def _extract_lows(bars) -> List[float]:
    try:
        if isinstance(bars[0], dict):
            return [float(b["low"]) for b in bars]
        return [float(b[3]) for b in bars]
    except Exception:
        return []

def _extract_opens(bars) -> List[float]:
    try:
        if isinstance(bars[0], dict):
            return [float(b["open"]) for b in bars]
        return [float(b[1]) for b in bars]
    except Exception:
        return []


def _log_return(closes: List[float], window: int) -> Optional[float]:
    if len(closes) <= window or closes[-1-window] <= 0:
        return None
    try:
        return math.log(closes[-1] / closes[-1-window])
    except (ValueError, ZeroDivisionError):
        return None


def _returns_series(closes: List[float], n: int) -> List[float]:
    """Log returns for last n bars."""
    c = closes[-n-1:]
    rets = []
    for i in range(1, len(c)):
        if c[i-1] > 0:
            try:
                rets.append(math.log(c[i] / c[i-1]))
            except (ValueError, ZeroDivisionError):
                rets.append(0.0)
    return rets


def _realized_variance(closes: List[float], n: int) -> Optional[float]:
    if len(closes) < n + 1:
        return None
    rets = _returns_series(closes[-n-1:], n)
    if not rets:
        return None
    mean = sum(rets) / len(rets)
    return sum((r - mean) ** 2 for r in rets) / len(rets)


def _yang_zhang_vol(opens, highs, lows, closes, n: int) -> Optional[float]:
    """
    Simplified Yang-Zhang volatility estimator.
    Full YZ = σ_open + k·σ_close + (1−k)·σ_range
    We use a practical approximation.
    """
    if len(closes) < n + 1:
        return None
    try:
        oc_rets = [math.log(opens[i] / closes[i-1])
                   for i in range(-n, 0) if closes[i-1] > 0 and opens[i] > 0]
        co_rets = [math.log(closes[i] / opens[i])
                   for i in range(-n, 0) if opens[i] > 0 and closes[i] > 0]
        hl_rets = [(math.log(highs[i] / lows[i])) ** 2
                   for i in range(-n, 0) if lows[i] > 0 and highs[i] > 0]
        if not oc_rets or not co_rets or not hl_rets:
            return None
        var_oc = sum(r**2 for r in oc_rets) / len(oc_rets)
        var_co = sum(r**2 for r in co_rets) / len(co_rets)
        var_hl = sum(hl_rets) / len(hl_rets)
        k = 0.34 / (1.34 + (n + 1) / (n - 1))
        yz_var = var_oc + k * var_co + (1 - k) * var_hl
        return math.sqrt(yz_var) if yz_var >= 0 else None
    except Exception:
        return None


def _simple_atr(highs, lows, closes, n: int) -> float:
    trs = []
    for i in range(1, min(n + 1, len(closes))):
        tr = max(
            highs[-i] - lows[-i],
            abs(highs[-i] - closes[-i-1]),
            abs(lows[-i] - closes[-i-1]),
        )
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


def _skewness(rets: List[float]) -> Optional[float]:
    n = len(rets)
    if n < 3:
        return None
    try:
        mean = sum(rets) / n
        std  = statistics.stdev(rets)
        if std == 0:
            return 0.0
        return sum((r - mean) ** 3 for r in rets) / (n * std ** 3)
    except Exception:
        return None


def _kurtosis(rets: List[float]) -> Optional[float]:
    n = len(rets)
    if n < 4:
        return None
    try:
        mean = sum(rets) / n
        std  = statistics.stdev(rets)
        if std == 0:
            return 0.0
        return sum((r - mean) ** 4 for r in rets) / (n * std ** 4) - 3.0
    except Exception:
        return None


def _shannon_entropy(values: List[float], bins: int = 20) -> Optional[float]:
    if len(values) < bins:
        return None
    try:
        mn, mx = min(values), max(values)
        if mx == mn:
            return 0.0
        bin_size = (mx - mn) / bins
        counts = [0] * bins
        for v in values:
            idx = min(int((v - mn) / bin_size), bins - 1)
            counts[idx] += 1
        n = len(values)
        entropy = 0.0
        for c in counts:
            if c > 0:
                p = c / n
                entropy -= p * math.log2(p)
        return entropy
    except Exception:
        return None


def _approx_entropy(values: List[float], m: int = 2, r_factor: float = 0.2) -> Optional[float]:
    """
    Approximate entropy (Pincus, 1991).  Reduced implementation.
    r = r_factor × std(values).
    """
    n = len(values)
    if n < 2 * m + 1:
        return None
    try:
        std = statistics.stdev(values)
        r = r_factor * std
        if r == 0:
            return 0.0

        def _phi(m_val: int) -> float:
            templates = [values[i:i+m_val] for i in range(n - m_val + 1)]
            c = []
            for i, ti in enumerate(templates):
                count = sum(
                    1 for tj in templates
                    if all(abs(ti[k] - tj[k]) <= r for k in range(m_val))
                )
                c.append(count / (n - m_val + 1))
            return sum(math.log(ci) for ci in c if ci > 0) / (n - m_val + 1)

        return abs(_phi(m) - _phi(m + 1))
    except Exception:
        return None


def _hurst_exponent(values: List[float]) -> Optional[float]:
    """
    Hurst exponent via R/S analysis (Hurst, 1951).
    H < 0.5 = mean-reverting, H ≈ 0.5 = random walk, H > 0.5 = trending.
    """
    n = len(values)
    if n < 20:
        return None
    try:
        lags = [2, 4, 8, 16, 32]
        lags = [l for l in lags if l < n // 2]
        if not lags:
            return None

        rs_vals = []
        for lag in lags:
            chunks = [values[i:i+lag] for i in range(0, n - lag, lag)]
            chunk_rs = []
            for chunk in chunks:
                if len(chunk) < 2:
                    continue
                mean_c = sum(chunk) / len(chunk)
                deviations = [c - mean_c for c in chunk]
                cumulative = [sum(deviations[:i+1]) for i in range(len(deviations))]
                r_range = max(cumulative) - min(cumulative)
                std_c = statistics.stdev(chunk)
                if std_c > 0:
                    chunk_rs.append(r_range / std_c)
            if chunk_rs:
                rs_vals.append((math.log(lag), math.log(sum(chunk_rs) / len(chunk_rs))))

        if len(rs_vals) < 2:
            return None

        # Linear regression slope = Hurst exponent
        xs = [v[0] for v in rs_vals]
        ys = [v[1] for v in rs_vals]
        n_pts = len(xs)
        x_mean = sum(xs) / n_pts
        y_mean = sum(ys) / n_pts
        num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n_pts))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n_pts))
        if den == 0:
            return None
        return round(num / den, 4)
    except Exception:
        return None


def _higuchi_fractal_dim(values: List[float], k_max: int = 5) -> Optional[float]:
    """
    Higuchi fractal dimension.  Range [1, 2].
    1 = smooth trend, 2 = completely noisy/complex.
    """
    n = len(values)
    if n < k_max * 2:
        return None
    try:
        lm_k = []
        for k in range(1, k_max + 1):
            lm = 0.0
            for m in range(1, k + 1):
                indices = list(range(m - 1, n, k))
                if len(indices) < 2:
                    continue
                total = sum(abs(values[indices[i]] - values[indices[i-1]])
                            for i in range(1, len(indices)))
                norm = (n - 1) / (k * len(indices))
                lm += (total * norm) / k
            if k > 0:
                lm_k.append((math.log(k), math.log(lm / k) if lm > 0 else 0))

        if len(lm_k) < 2:
            return None

        xs = [v[0] for v in lm_k]
        ys = [v[1] for v in lm_k]
        n_pts = len(xs)
        x_mean = sum(xs) / n_pts
        y_mean = sum(ys) / n_pts
        num = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n_pts))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n_pts))
        if den == 0:
            return None
        slope = num / den
        return round(abs(slope), 4)
    except Exception:
        return None


def _haar_wavelet_energies(values: List[float]) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    3-level Haar DWT decomposition.
    Returns energy ratio at each level (detail energy / total energy).
    """
    def _dwt_level(s: List[float]) -> tuple[List[float], List[float]]:
        n = len(s) - (len(s) % 2)  # ensure even length
        approx = [(s[i] + s[i+1]) / math.sqrt(2) for i in range(0, n, 2)]
        detail = [(s[i] - s[i+1]) / math.sqrt(2) for i in range(0, n, 2)]
        return approx, detail

    try:
        if len(values) < 8:
            return None, None, None
        total_energy = sum(v**2 for v in values)
        if total_energy == 0:
            return 0.0, 0.0, 0.0

        approx, d1 = _dwt_level(values)
        approx2, d2 = _dwt_level(approx)
        approx3, d3 = _dwt_level(approx2)

        e1 = sum(v**2 for v in d1) / total_energy
        e2 = sum(v**2 for v in d2) / total_energy
        e3 = sum(v**2 for v in d3) / total_energy

        return round(e1, 6), round(e2, 6), round(e3, 6)
    except Exception:
        return None, None, None


def _autocorrelation(rets: List[float], lag: int) -> Optional[float]:
    n = len(rets)
    if n <= lag:
        return None
    try:
        mean = sum(rets) / n
        num  = sum((rets[i] - mean) * (rets[i - lag] - mean)
                   for i in range(lag, n))
        den  = sum((r - mean) ** 2 for r in rets)
        if den == 0:
            return 0.0
        return round(num / den, 6)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_pipeline: Optional[FeaturePipeline] = None


def get_feature_pipeline() -> FeaturePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = FeaturePipeline()
    return _pipeline


FEATURE_SCHEMA_HASH = _SCHEMA_HASH
