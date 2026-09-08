"""
Canonical Authorization Builder for Aegis-Gold v6.0.

Validates a TradeCandidate and produces a TradeAuthorization (or None).
All validation in one place:
    1. causal_valid  — no future data
    2. risk_valid    — EV, RR, spread, lot, SL floor
    3. execution_valid — direction, symbol, no duplicate
    4. risk_mgr.can_trade()
    5. Daily loss circuit breaker
"""

from datetime import datetime, timezone
from typing import Optional
import logging
import uuid

from brain.trade_candidate import TradeCandidate, TradeClass
from brain.canonical_types import TradeAuthorization

logger = logging.getLogger("aegis.authorization_builder")

# WAIT reason codes
WAIT_MACRO_NEUTRAL = "WAIT_MACRO_NEUTRAL"
WAIT_NO_SETUP = "WAIT_NO_SETUP"
WAIT_TRIGGER_MISSING = "WAIT_TRIGGER_MISSING"
WAIT_NEGATIVE_EV = "WAIT_NEGATIVE_EV"
WAIT_RR_TOO_LOW = "WAIT_RR_TOO_LOW"
WAIT_SPREAD_TOO_HIGH = "WAIT_SPREAD_TOO_HIGH"
WAIT_RISK_LIMIT = "WAIT_RISK_LIMIT"
WAIT_DUPLICATE_SIGNAL = "WAIT_DUPLICATE_SIGNAL"
WAIT_CAUSALITY_FAILURE = "WAIT_CAUSALITY_FAILURE"
WAIT_CONTRADICTORY_ENGINES = "WAIT_CONTRADICTORY_ENGINES"
WAIT_AUTHORIZATION_FAILED = "WAIT_AUTHORIZATION_FAILED"
WAIT_ALL_PATHS_REJECTED = "WAIT_ALL_PATHS_REJECTED"
WAIT_INVALID_DIRECTION = "WAIT_INVALID_DIRECTION"
WAIT_SL_TOO_TIGHT = "WAIT_SL_TOO_TIGHT"
WAIT_LOT_INVALID = "WAIT_LOT_INVALID"
WAIT_DAILY_LOSS_LIMIT = "WAIT_DAILY_LOSS_LIMIT"
WAIT_STALE_SETUP = "WAIT_STALE_SETUP"
WAIT_MACRO_CONTRADICTION = "WAIT_MACRO_CONTRADICTION"

# SL floors (points)
SL_FLOOR_GOLD = 150
SL_FLOOR_EURUSD = 40

# Max spread as fraction of $3.50 target
MAX_SPREAD_FRACTION = 0.50

# Stale setup threshold (seconds)
STALE_SETUP_SECONDS = 180


def _is_stale(data_timestamp: str, decision_timestamp: str, max_age_sec: int = STALE_SETUP_SECONDS) -> bool:
    """Check if the data timestamp is older than max_age_sec."""
    try:
        from datetime import datetime
        dt_data = datetime.fromisoformat(data_timestamp.replace("Z", "+00:00"))
        dt_decision = datetime.fromisoformat(decision_timestamp.replace("Z", "+00:00"))
        age = (dt_decision - dt_data).total_seconds()
        return age > max_age_sec
    except Exception:
        return False


def build_trade_authorization(
    candidate: TradeCandidate,
    risk_mgr,
    spread_pts: float,
    point: float,
    decision_timestamp: str = "",
    anti_duplicate_engine=None,
) -> Optional[TradeAuthorization]:
    """
    Build a canonical TradeAuthorization from a TradeCandidate.

    Returns TradeAuthorization(authorized=True) or None with logged reason.
    """
    if not decision_timestamp:
        decision_timestamp = datetime.now(timezone.utc).isoformat()

    # ── 1. Direction validation ──────────────────────────────────────────────
    if candidate.direction not in ("BUY", "SELL"):
        logger.warning(f"[AUTH] {candidate.symbol} invalid direction: {candidate.direction}")
        candidate.wait_reason = WAIT_INVALID_DIRECTION
        return None

    # ── 2. Causality validation ──────────────────────────────────────────────
    if not candidate.causal_valid:
        logger.warning(f"[AUTH] {candidate.symbol} causality violation for {candidate.source_path}")
        candidate.wait_reason = WAIT_CAUSALITY_FAILURE
        return None

    # Check stale setup
    if candidate.data_timestamp and _is_stale(candidate.data_timestamp, decision_timestamp):
        logger.warning(f"[AUTH] {candidate.symbol} stale setup (data older than {STALE_SETUP_SECONDS}s)")
        candidate.wait_reason = WAIT_STALE_SETUP
        return None

    # ── 3. Risk validation ───────────────────────────────────────────────────
    # EV > 0
    if candidate.expected_value <= 0:
        logger.warning(f"[AUTH] {candidate.symbol} negative EV: {candidate.expected_value:.2f}")
        candidate.wait_reason = WAIT_NEGATIVE_EV
        return None

    # RR >= min threshold (1.25 small, 1.5 macro)
    min_rr = 1.5 if candidate.trade_class == TradeClass.MACRO_CONTINUATION.value else 1.25
    if candidate.risk_reward < min_rr:
        logger.warning(f"[AUTH] {candidate.symbol} RR too low: {candidate.risk_reward:.2f} < {min_rr}")
        candidate.wait_reason = WAIT_RR_TOO_LOW
        return None

    # Spread check
    if spread_pts > 0 and point > 0:
        spread_cost = spread_pts * point * candidate.lot * 100  # rough USD estimate
        target_usd = candidate.expected_value
        if spread_cost > MAX_SPREAD_FRACTION * max(target_usd, 1.0):
            logger.warning(f"[AUTH] {candidate.symbol} spread too high: {spread_cost:.2f} USD")
            candidate.wait_reason = WAIT_SPREAD_TOO_HIGH
            return None

    # SL floor
    sl_floor = SL_FLOOR_GOLD if ("XAU" in candidate.symbol.upper() or "GOLD" in candidate.symbol.upper()) else SL_FLOOR_EURUSD
    if candidate.sl_points < sl_floor:
        logger.warning(f"[AUTH] {candidate.symbol} SL too tight: {candidate.sl_points} < {sl_floor}")
        candidate.wait_reason = WAIT_SL_TOO_TIGHT
        return None

    # Lot validation
    if candidate.lot <= 0 or candidate.lot > 10.0:
        logger.warning(f"[AUTH] {candidate.symbol} invalid lot: {candidate.lot}")
        candidate.wait_reason = WAIT_LOT_INVALID
        return None

    # ── 4. Macro contradiction check ─────────────────────────────────────────
    from brain.macro_analyzer import macro_bias_contradicts
    if macro_bias_contradicts(candidate.macro_bias, candidate.direction):
        logger.warning(f"[AUTH] {candidate.symbol} macro contradicts direction: {candidate.macro_bias} vs {candidate.direction}")
        candidate.wait_reason = WAIT_MACRO_CONTRADICTION
        return None

    # ── 5. Anti-duplicate check ──────────────────────────────────────────────
    if anti_duplicate_engine is not None:
        try:
            sig_hash = candidate.signal_hash()
            if anti_duplicate_engine.is_duplicate(sig_hash):
                logger.warning(f"[AUTH] {candidate.symbol} duplicate signal: {sig_hash}")
                candidate.wait_reason = WAIT_DUPLICATE_SIGNAL
                return None
        except Exception as exc:
            logger.debug(f"[AUTH] anti-duplicate check error: {exc}")

    # ── 6. Risk manager check ────────────────────────────────────────────────
    if risk_mgr is not None:
        try:
            if hasattr(risk_mgr, "can_trade") and callable(getattr(risk_mgr, "can_trade")):
                if risk_mgr.can_trade() is False:
                    logger.warning(f"[AUTH] {candidate.symbol} risk manager blocks trade")
                    candidate.wait_reason = WAIT_RISK_LIMIT
                    return None
            # Daily loss circuit breaker
            if hasattr(risk_mgr, "daily_loss_limit_hit") and callable(getattr(risk_mgr, "daily_loss_limit_hit")):
                if risk_mgr.daily_loss_limit_hit() is True:
                    logger.warning(f"[AUTH] {candidate.symbol} daily loss limit active")
                    candidate.wait_reason = WAIT_DAILY_LOSS_LIMIT
                    return None
        except Exception as exc:
            logger.debug(f"[AUTH] risk manager check error: {exc}")

    # ── Build authorization ──────────────────────────────────────────────────
    auth_id = f"AUTH_{uuid.uuid4().hex[:8]}"

    auth = TradeAuthorization(
        authorized=True,
        authorization_id=auth_id,
        opportunity_id=f"OPP_{candidate.source_path}_{auth_id}",
        pattern_id=candidate.signal_type,
        symbol=candidate.symbol,
        direction=candidate.direction,
        lot=candidate.lot,
        entry_price=candidate.entry_price,
        stop_loss=candidate.stop_loss,
        take_profit=candidate.take_profit,
        target_usd=candidate.expected_value,
        risk_usd=abs(candidate.entry_price - candidate.stop_loss) * candidate.lot * 100,
        sl_points=candidate.sl_points,
        tp_points=candidate.tp_points,
        news_regime="NORMAL",
        local_ai_context={
            "source_path": candidate.source_path,
            "signal_type": candidate.signal_type,
            "macro_bias": candidate.macro_bias,
            "macro_score": candidate.macro_score,
            "setup_score": candidate.setup_score,
            "trigger_score": candidate.trigger_score,
            "quant_score": candidate.quant_score,
            "ml_score": candidate.ml_score,
            "pattern_score": candidate.pattern_score,
            "final_score": candidate.final_score,
            "risk_reward": candidate.risk_reward,
            "expected_value": candidate.expected_value,
            "spread_cost": candidate.spread_cost,
            "trade_class": candidate.trade_class,
        },
        timestamp=decision_timestamp,
        reason=f"Authorized via {candidate.source_path} ({candidate.signal_type})",
        source_path=candidate.source_path,
        signal_type=candidate.signal_type,
        macro_bias=candidate.macro_bias,
        authorization_version="v2.0",
        causal_validity=candidate.causal_valid,
        data_timestamp=candidate.data_timestamp,
    )

    logger.info(
        f"[TRADE-AUTHORIZED] symbol={candidate.symbol} source={candidate.source_path} "
        f"auth_id={auth_id} type={candidate.signal_type} rr={candidate.risk_reward:.2f}"
    )
    return auth