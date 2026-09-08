"""
===========================================================================
AEGIS GOLD — Decision Arbiter
===========================================================================

Handles explicit arbitration between:
  - Pattern Engine (high-quality A/A+ patterns)
  - ML Ensemble
  - RL / Offline RL
  - Quant
  - OMEGA
  - Kronos
  - Consensus logic

PATTERN SIGNAL PRIORITY:
  A high-quality Pattern Trade (A/A+ grade, high confidence) must NOT be
  overwritten by a weak conflicting prediction. Explicit arbitration rules
  determine whether the pattern is preserved or rejected with a reason.

CONSENSUS FIX:
  Deterministic consensus rules based on:
    - BUY votes
    - SELL votes
    - NEUTRAL votes
    - weighted confidence
    - agreement ratio
    - contradiction score
===========================================================================
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from brain.trading_decision import EngineSignal, TradingDecision

logger = logging.getLogger("aegis.decision_arbiter")

# Pattern arbitration thresholds
HIGH_QUALITY_PATTERN_CONFIDENCE = 80.0  # A/A+ grade threshold
HARD_VETO_THRESHOLD = 0.70  # Contradictory evidence must be >= 70% to veto a high-quality pattern
WEAK_SIGNAL_THRESHOLD = 0.40  # Signals below this are considered weak

# Consensus thresholds
MIN_CONSENSUS_AGREEMENT = 0.50  # 50% agreement required for directional consensus


@dataclass
class ArbitrationResult:
    """Result of decision arbitration."""
    action: str                    # "BUY", "SELL", "WAIT"
    confidence: float              # 0-100
    source: str                    # "PATTERN", "CONSENSUS", "RL", "ARBITRATED"
    reason: str = ""
    pattern_preserved: bool = False
    vetoed: bool = False
    veto_reason: str = ""
    buy_votes: int = 0
    sell_votes: int = 0
    neutral_votes: int = 0
    weighted_buy_confidence: float = 0.0
    weighted_sell_confidence: float = 0.0
    agreement_ratio: float = 0.0
    contradiction_score: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


def _normalize_action(action: str) -> str:
    """Normalize action strings to BUY/SELL/WAIT."""
    if not action:
        return "WAIT"
    a = str(action).strip().upper()
    if a in ("BUY", "BULLISH", "LONG", "STRONG_BUY", "ENTER_LONG"):
        return "BUY"
    if a in ("SELL", "BEARISH", "SHORT", "STRONG_SELL", "ENTER_SHORT"):
        return "SELL"
    return "WAIT"


def _normalize_confidence(conf: Any, max_val: float = 1.0) -> float:
    """Normalize confidence to 0-1 scale."""
    try:
        c = float(conf)
        if c > 1.0:
            c = c / 100.0
        return max(0.0, min(1.0, c))
    except (TypeError, ValueError):
        return 0.0


def arbitrate_pattern_decision(
    pattern_signal: Dict[str, Any],
    ml_signal: Optional[Dict[str, Any]] = None,
    quant_signal: Optional[Dict[str, Any]] = None,
    omega_signal: Optional[Dict[str, Any]] = None,
    kronos_signal: Optional[Dict[str, Any]] = None,
    rl_signal: Optional[Dict[str, Any]] = None,
    offline_rl_signal: Optional[Dict[str, Any]] = None,
) -> ArbitrationResult:
    """
    Arbitrate a high-quality pattern signal against other engine signals.

    A high-quality pattern (A/A+ grade, confidence >= 80) is preserved
    unless contradictory evidence exceeds the HARD_VETO_THRESHOLD.

    A weak conflicting signal (e.g. ML SELL 29%) does NOT overwrite
    a strong pattern signal.
    """
    pattern_action = _normalize_action(pattern_signal.get("direction", pattern_signal.get("action", "WAIT")))
    pattern_conf = _normalize_confidence(pattern_signal.get("confidence", 0.0))
    pattern_grade = pattern_signal.get("grade", "F")
    pattern_name = pattern_signal.get("pattern_name", pattern_signal.get("pattern", "UNKNOWN"))

    is_high_quality = (
        pattern_action in ("BUY", "SELL")
        and pattern_conf >= HIGH_QUALITY_PATTERN_CONFIDENCE / 100.0
        and pattern_grade in ("A", "A+")
    )

    if not is_high_quality:
        # Not a high-quality pattern - fall through to normal arbitration
        return ArbitrationResult(
            action=pattern_action,
            confidence=pattern_conf * 100,
            source="PATTERN",
            reason=f"Pattern {pattern_name} not high-quality (conf={pattern_conf*100:.0f}%, grade={pattern_grade})",
            pattern_preserved=False,
        )

    # Calculate contradictory evidence
    contradictory_evidence = 0.0
    contradictory_sources = []
    supporting_sources = []

    signals = {
        "ml": ml_signal,
        "quant": quant_signal,
        "omega": omega_signal,
        "kronos": kronos_signal,
        "rl": rl_signal,
        "offline_rl": offline_rl_signal,
    }

    for name, sig in signals.items():
        if not sig:
            continue
        sig_action = _normalize_action(sig.get("action", sig.get("direction", "WAIT")))
        sig_conf = _normalize_confidence(sig.get("confidence", 0.0))

        if sig_action == "WAIT" or sig_conf < WEAK_SIGNAL_THRESHOLD:
            continue  # Weak or neutral signals don't count as contradiction

        if sig_action == pattern_action:
            supporting_sources.append((name, sig_conf))
        elif sig_action in ("BUY", "SELL"):
            # Contradictory signal
            contradictory_evidence += sig_conf
            contradictory_sources.append((name, sig_action, sig_conf))

    # Normalize contradiction score
    total_signal_weight = sum(sig_conf for _, sig_conf in supporting_sources) + contradictory_evidence
    if total_signal_weight > 0:
        contradiction_score = contradictory_evidence / total_signal_weight
    else:
        contradiction_score = 0.0

    # Hard veto check
    if contradiction_score >= HARD_VETO_THRESHOLD:
        veto_reason = (
            f"HARD_VETO | Pattern {pattern_name} ({pattern_action} {pattern_conf*100:.0f}% {pattern_grade}) "
            f"contradicted by {len(contradictory_sources)} strong opposing signals "
            f"(contradiction={contradiction_score:.2f})"
        )
        logger.warning("[ARBITRATION] %s", veto_reason)
        return ArbitrationResult(
            action="WAIT",
            confidence=pattern_conf * 100,
            source="ARBITRATED",
            reason=veto_reason,
            pattern_preserved=False,
            vetoed=True,
            veto_reason=veto_reason,
            contradiction_score=contradiction_score,
            details={
                "pattern": pattern_name,
                "pattern_action": pattern_action,
                "pattern_confidence": pattern_conf,
                "contradictory_sources": contradictory_sources,
                "supporting_sources": supporting_sources,
            },
        )

    # Preserve pattern decision
    logger.info(
        "[ARBITRATION] Pattern preserved: %s %s %.0f%% %s (contradiction=%.2f)",
        pattern_action, pattern_name, pattern_conf * 100, pattern_grade, contradiction_score,
    )
    return ArbitrationResult(
        action=pattern_action,
        confidence=pattern_conf * 100,
        source="PATTERN",
        reason=f"High-quality pattern {pattern_name} preserved (contradiction={contradiction_score:.2f})",
        pattern_preserved=True,
        contradiction_score=contradiction_score,
        details={
            "pattern": pattern_name,
            "pattern_action": pattern_action,
            "pattern_confidence": pattern_conf,
            "contradictory_sources": contradictory_sources,
            "supporting_sources": supporting_sources,
        },
    )


def compute_consensus(
    engine_votes: Dict[str, Dict[str, Any]],
    rl_signal: Optional[Dict[str, Any]] = None,
) -> ArbitrationResult:
    """
    Compute deterministic consensus from engine votes.

    Args:
        engine_votes: Dict of engine_name -> {"direction": str, "confidence": float}
        rl_signal: Optional RL signal

    Returns:
        ArbitrationResult with consensus action and detailed vote breakdown.
    """
    buy_votes = 0
    sell_votes = 0
    neutral_votes = 0
    weighted_buy = 0.0
    weighted_sell = 0.0
    total_weight = 0.0

    for engine, vote in engine_votes.items():
        direction = _normalize_action(vote.get("direction", "WAIT"))
        confidence = _normalize_confidence(vote.get("confidence", 0.0))

        if direction == "BUY":
            buy_votes += 1
            weighted_buy += confidence
        elif direction == "SELL":
            sell_votes += 1
            weighted_sell += confidence
        else:
            neutral_votes += 1

        total_weight += confidence

    # Include RL signal if provided
    if rl_signal:
        rl_action = _normalize_action(rl_signal.get("action", rl_signal.get("direction", "WAIT")))
        rl_conf = _normalize_confidence(rl_signal.get("confidence", 0.0))
        if rl_action == "BUY":
            buy_votes += 1
            weighted_buy += rl_conf
        elif rl_action == "SELL":
            sell_votes += 1
            weighted_sell += rl_conf
        else:
            neutral_votes += 1
        total_weight += rl_conf

    total_votes = buy_votes + sell_votes + neutral_votes
    if total_votes == 0:
        return ArbitrationResult(
            action="WAIT",
            confidence=0.0,
            source="CONSENSUS",
            reason="No engine votes available",
        )

    # Weighted confidence (normalized to 0-1)
    if total_weight > 0:
        weighted_buy_conf = weighted_buy / total_weight
        weighted_sell_conf = weighted_sell / total_weight
    else:
        weighted_buy_conf = 0.0
        weighted_sell_conf = 0.0

    # Agreement ratio
    max_directional = max(buy_votes, sell_votes)
    agreement_ratio = max_directional / total_votes if total_votes > 0 else 0.0

    # Determine final action
    if buy_votes > sell_votes and buy_votes >= 1:
        action = "BUY"
        confidence = weighted_buy_conf * 100
    elif sell_votes > buy_votes and sell_votes >= 1:
        action = "SELL"
        confidence = weighted_sell_conf * 100
    else:
        action = "WAIT"
        confidence = max(weighted_buy_conf, weighted_sell_conf) * 100

    # Require minimum agreement for directional action
    if action in ("BUY", "SELL") and agreement_ratio < MIN_CONSENSUS_AGREEMENT:
        action = "WAIT"
        reason = (
            f"Consensus agreement too low: BUY={buy_votes} SELL={sell_votes} "
            f"NEUTRAL={neutral_votes} (agreement={agreement_ratio:.2f})"
        )
    else:
        reason = (
            f"Consensus: BUY={buy_votes} SELL={sell_votes} NEUTRAL={neutral_votes} "
            f"agreement={agreement_ratio:.2f}"
        )

    logger.info(
        "[CONSENSUS] action=%s confidence=%.1f buy_votes=%d sell_votes=%d neutral_votes=%d "
        "agreement=%.2f reason=%s",
        action, confidence, buy_votes, sell_votes, neutral_votes, agreement_ratio, reason,
    )

    return ArbitrationResult(
        action=action,
        confidence=confidence,
        source="CONSENSUS",
        reason=reason,
        buy_votes=buy_votes,
        sell_votes=sell_votes,
        neutral_votes=neutral_votes,
        weighted_buy_confidence=weighted_buy_conf,
        weighted_sell_confidence=weighted_sell_conf,
        agreement_ratio=agreement_ratio,
        details={
            "engine_votes": {k: v.get("direction", "WAIT") for k, v in engine_votes.items()},
        },
    )


def arbitrate_rl_decision(
    consensus_result: ArbitrationResult,
    rl_signal: Optional[Dict[str, Any]] = None,
    offline_rl_signal: Optional[Dict[str, Any]] = None,
) -> ArbitrationResult:
    """
    Arbitrate between consensus and RL signals.

    RL signals are advisory - they can boost confidence but cannot
    silently override a strong consensus.
    """
    if consensus_result.action == "WAIT":
        # No consensus - check if RL provides a strong signal
        rl_action = _normalize_action(rl_signal.get("action", rl_signal.get("direction", "WAIT"))) if rl_signal else "WAIT"
        rl_conf = _normalize_confidence(rl_signal.get("confidence", 0.0)) if rl_signal else 0.0

        if rl_action in ("BUY", "SELL") and rl_conf >= 0.60:
            return ArbitrationResult(
                action=rl_action,
                confidence=rl_conf * 100,
                source="RL",
                reason=f"RL override: {rl_action} {rl_conf*100:.0f}% (no consensus)",
                buy_votes=consensus_result.buy_votes,
                sell_votes=consensus_result.sell_votes,
                neutral_votes=consensus_result.neutral_votes,
                agreement_ratio=consensus_result.agreement_ratio,
            )
        return consensus_result

    # Consensus exists - RL can only adjust confidence, not direction
    if rl_signal:
        rl_action = _normalize_action(rl_signal.get("action", rl_signal.get("direction", "WAIT")))
        rl_conf = _normalize_confidence(rl_signal.get("confidence", 0.0))

        if rl_action == consensus_result.action:
            # RL agrees - boost confidence slightly
            boosted_conf = min(100.0, consensus_result.confidence + rl_conf * 10)
            return ArbitrationResult(
                action=consensus_result.action,
                confidence=boosted_conf,
                source="CONSENSUS+RL",
                reason=f"Consensus {consensus_result.action} with RL agreement (conf={boosted_conf:.1f}%)",
                buy_votes=consensus_result.buy_votes,
                sell_votes=consensus_result.sell_votes,
                neutral_votes=consensus_result.neutral_votes,
                agreement_ratio=consensus_result.agreement_ratio,
            )
        elif rl_action in ("BUY", "SELL") and rl_conf >= 0.80:
            # Strong RL disagreement - reduce confidence but don't flip
            reduced_conf = max(0.0, consensus_result.confidence - rl_conf * 20)
            return ArbitrationResult(
                action=consensus_result.action,
                confidence=reduced_conf,
                source="CONSENSUS",
                reason=f"Consensus {consensus_result.action} with RL disagreement (conf reduced to {reduced_conf:.1f}%)",
                buy_votes=consensus_result.buy_votes,
                sell_votes=consensus_result.sell_votes,
                neutral_votes=consensus_result.neutral_votes,
                agreement_ratio=consensus_result.agreement_ratio,
            )

    return consensus_result


def apply_arbitration_to_decision(
    decision: TradingDecision,
    arbitration: ArbitrationResult,
    stage: str = "DECISION_ARBITRATION",
) -> TradingDecision:
    """Apply an arbitration result to a TradingDecision."""
    decision.transition(
        new_action=arbitration.action,
        stage=stage,
        reason=arbitration.reason,
        confidence=arbitration.confidence,
        metadata={
            "source": arbitration.source,
            "pattern_preserved": arbitration.pattern_preserved,
            "vetoed": arbitration.vetoed,
            "veto_reason": arbitration.veto_reason,
            "buy_votes": arbitration.buy_votes,
            "sell_votes": arbitration.sell_votes,
            "neutral_votes": arbitration.neutral_votes,
            "agreement_ratio": arbitration.agreement_ratio,
            "contradiction_score": arbitration.contradiction_score,
        },
    )
    decision.source = arbitration.source
    if arbitration.action in ("BUY", "SELL"):
        decision.direction = arbitration.action
    return decision