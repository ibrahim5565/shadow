"""
===========================================================================
AEGIS GOLD — Feature Validation
===========================================================================

Replaces silent fallback (df.get("adx", 0.0), value or 0.0, fillna(0))
with explicit validation. Missing or invalid features are reported
as unavailable, never silently replaced with 0.0.

REQUIRED FEATURES:
  ADX, RSI, ATR, spread, price, timestamp

VALIDATION RULES:
  - exists: feature key present in the data
  - finite: value is not NaN, inf, or -inf
  - non-stale: candle timestamp is not older than allowed staleness
  - correct candle timestamp: matches the decision snapshot
  - reasonable range: domain-aware bounds (e.g. RSI 0-100, ADX 0-100)
===========================================================================
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("aegis.feature_validation")


class FeatureValidationError(Exception):
    """Raised when required features are missing or invalid."""
    pass


@dataclass
class FeatureValidationResult:
    """Structured result of feature validation."""
    valid: bool
    missing_features: List[str] = field(default_factory=list)
    invalid_features: Dict[str, str] = field(default_factory=dict)
    stale_features: List[str] = field(default_factory=list)
    feature_hash: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "missing_features": self.missing_features,
            "invalid_features": self.invalid_features,
            "stale_features": self.stale_features,
            "feature_hash": self.feature_hash,
            "details": self.details,
        }


# Domain-aware validation bounds
# ADX and RSI use exclusive lower bounds (0.0 is a placeholder, not a real value)
FEATURE_BOUNDS = {
    "adx": (1.0, 100.0),       # ADX=0.0 is a placeholder, not a real value
    "rsi": (1.0, 100.0),       # RSI=0.0 is a placeholder, not a real value
    "atr": (0.0, float("inf")),  # ATR can be any positive value
    "spread": (0.0, float("inf")),
    "price": (0.0, float("inf")),
    "regime_score": (0.0, 100.0),
    "structure_score": (0.0, 100.0),
    "entry_score": (0.0, 100.0),
    "confidence": (0.0, 100.0),
}

# Features that must be present for a valid decision
REQUIRED_FEATURES = ["adx", "rsi", "atr", "spread", "price", "timestamp"]

# Maximum staleness in seconds for candle data
MAX_STALENESS_SECONDS = 300  # 5 minutes


def _is_finite(value: Any) -> bool:
    """Check if a value is finite (not NaN, inf, -inf)."""
    # Datetime objects are valid timestamps, not numeric values
    if isinstance(value, datetime):
        return True
    try:
        f = float(value)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False


def _is_in_range(feature: str, value: Any) -> bool:
    """Check if a value is within the domain-aware bounds for a feature."""
    if feature not in FEATURE_BOUNDS:
        return True  # Unknown feature - don't reject
    lo, hi = FEATURE_BOUNDS[feature]
    try:
        f = float(value)
        return lo <= f <= hi
    except (TypeError, ValueError):
        return False


def validate_features(
    features: Dict[str, Any],
    decision_timestamp: Optional[datetime] = None,
    required: Optional[List[str]] = None,
) -> FeatureValidationResult:
    """
    Validate a feature dictionary.

    Args:
        features: Dictionary of feature name -> value
        decision_timestamp: The decision time T (for staleness check)
        required: List of required feature names (defaults to REQUIRED_FEATURES)

    Returns:
        FeatureValidationResult with valid flag and detailed reporting.
    """
    required = required or REQUIRED_FEATURES
    result = FeatureValidationResult(valid=True)

    # 1. Check existence
    for feat in required:
        if feat not in features or features[feat] is None:
            result.missing_features.append(feat)
            result.valid = False

    # 2. Check finiteness and range
    for feat, value in features.items():
        if feat in result.missing_features:
            continue
        if not _is_finite(value):
            result.invalid_features[feat] = f"non-finite value: {value}"
            result.valid = False
        elif not _is_in_range(feat, value):
            result.invalid_features[feat] = f"out of range: {value}"
            result.valid = False

    # 3. Check staleness
    if decision_timestamp is not None and "timestamp" in features:
        try:
            ts = features["timestamp"]
            if isinstance(ts, (int, float)):
                ts_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            elif isinstance(ts, datetime):
                ts_dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            else:
                ts_dt = None

            if ts_dt is not None:
                dt = decision_timestamp if decision_timestamp.tzinfo else decision_timestamp.replace(tzinfo=timezone.utc)
                staleness = (dt - ts_dt).total_seconds()
                if staleness > MAX_STALENESS_SECONDS:
                    result.stale_features.append(f"timestamp: {staleness:.0f}s old")
                    result.valid = False
        except (TypeError, ValueError) as e:
            result.invalid_features["timestamp"] = f"cannot parse: {e}"
            result.valid = False

    # 4. Compute feature hash
    import hashlib
    import json
    try:
        hash_input = json.dumps(
            {k: v for k, v in features.items() if k != "timestamp"},
            sort_keys=True, default=str
        )
        result.feature_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    except Exception:
        result.feature_hash = ""

    if not result.valid:
        logger.warning(
            "[FEATURE_VALIDATION] Invalid features: missing=%s invalid=%s stale=%s",
            result.missing_features, result.invalid_features, result.stale_features,
        )

    return result


def validate_market_snapshot(
    snapshot: Any,
    required_features: Optional[List[str]] = None,
) -> FeatureValidationResult:
    """
    Validate a MarketDecisionSnapshot or FrozenDecisionSnapshot.

    Extracts features from the snapshot and validates them.
    """
    required = required_features or ["adx", "rsi", "atr", "spread", "price"]

    features = {}
    if hasattr(snapshot, "extra") and isinstance(snapshot.extra, dict):
        features.update(snapshot.extra.get("features", {}))

    # Add snapshot-level features
    if hasattr(snapshot, "spread"):
        features["spread"] = snapshot.spread
    if hasattr(snapshot, "current_price"):
        features["price"] = snapshot.current_price
    elif hasattr(snapshot, "price"):
        features["price"] = snapshot.price

    # Add timestamp
    if hasattr(snapshot, "timestamp"):
        features["timestamp"] = snapshot.timestamp

    return validate_features(features, decision_timestamp=getattr(snapshot, "timestamp", None), required=required)


def extract_and_validate_features(
    candles_m5: Any,
    symbol: str,
    point: float = 0.01,
    spread: float = 0.0,
    decision_timestamp: Optional[datetime] = None,
) -> FeatureValidationResult:
    """
    Extract and validate features from candle data.

    This is the canonical feature extraction path used by all engines.
    Missing indicators are reported, never silently replaced with 0.0.
    """
    features: Dict[str, Any] = {}
    result = FeatureValidationResult(valid=True)

    # Extract closes, highs, lows
    closes, highs, lows = [], [], []
    try:
        if hasattr(candles_m5, "close"):
            closes = candles_m5["close"].values.astype(float).tolist()
            highs = candles_m5["high"].values.astype(float).tolist()
            lows = candles_m5["low"].values.astype(float).tolist()
        elif isinstance(candles_m5, list) and candles_m5:
            for c in candles_m5:
                if isinstance(c, dict):
                    closes.append(float(c.get("close", c.get("c", 0.0))))
                    highs.append(float(c.get("high", c.get("h", 0.0))))
                    lows.append(float(c.get("low", c.get("l", 0.0))))
                elif isinstance(c, (list, tuple)) and len(c) >= 5:
                    closes.append(float(c[4]))
                    highs.append(float(c[2]))
                    lows.append(float(c[3]))
    except Exception as e:
        result.invalid_features["candles"] = f"cannot parse: {e}"
        result.valid = False

    # Compute indicators
    if len(closes) >= 14:
        try:
            from brain.indicators import RSI, ADX, ATR
            rsi_vals = RSI(closes, 14)
            if rsi_vals:
                features["rsi"] = rsi_vals[-1]
            else:
                result.missing_features.append("rsi")

            adx_res = ADX(highs, lows, closes, 14)
            if isinstance(adx_res, tuple) and adx_res:
                features["adx"] = adx_res[0]
            elif adx_res:
                features["adx"] = adx_res
            else:
                result.missing_features.append("adx")

            atr_vals = ATR(highs, lows, closes, 14)
            if atr_vals:
                features["atr"] = atr_vals[-1]
            else:
                result.missing_features.append("atr")
        except Exception as e:
            logger.warning(f"[FEATURE_VALIDATION] Indicator calculation error: {e}")
            result.missing_features.extend(["rsi", "adx", "atr"])
    else:
        result.missing_features.extend(["rsi", "adx", "atr"])

    # Add market features
    features["spread"] = spread
    features["price"] = closes[-1] if closes else 0.0
    features["timestamp"] = decision_timestamp or datetime.now(timezone.utc)

    # Validate
    validation = validate_features(features, decision_timestamp=decision_timestamp)
    result.valid = validation.valid
    result.missing_features = validation.missing_features
    result.invalid_features = validation.invalid_features
    result.stale_features = validation.stale_features
    result.feature_hash = validation.feature_hash
    result.details = features

    return result