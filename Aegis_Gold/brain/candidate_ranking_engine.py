"""
Candidate Ranking Engine for Aegis-Gold v6.0.

Scores each TradeCandidate by:
    FinalScore = macro_score(0.25) * setup_score(0.25) *
                 trigger_score(0.20) * quant_score(0.15) *
                 ml_score(0.10) * pattern_score(0.05)
                 - spread_penalty - contradiction_penalty

Deduplicates by signal hash and returns the best candidate (or None).
"""

from typing import List, Optional
import logging

from brain.trade_candidate import TradeCandidate

logger = logging.getLogger("aegis.candidate_ranking")

# Score weights
W_MACRO = 0.25
W_SETUP = 0.25
W_TRIGGER = 0.20
W_QUANT = 0.15
W_ML = 0.10
W_PATTERN = 0.05

# Penalties
SPREAD_PENALTY_FACTOR = 0.10       # per $1 of spread cost
CONTRADICTION_PENALTY = 0.30       # if macro contradicts direction


class CandidateRankingEngine:
    """Scores, deduplicates, and ranks TradeCandidates."""

    def __init__(self):
        self._seen_hashes = set()

    def score(self, candidate: TradeCandidate) -> float:
        """
        Compute the composite final score for a candidate.
        Returns a value in [0, 1] range (higher is better).
        """
        # Clamp scores to [0, 1]
        macro = max(0.0, min(1.0, candidate.macro_score))
        setup = max(0.0, min(1.0, candidate.setup_score))
        trigger = max(0.0, min(1.0, candidate.trigger_score))
        quant = max(0.0, min(1.0, candidate.quant_score))
        ml = max(0.0, min(1.0, candidate.ml_score))
        pattern = max(0.0, min(1.0, candidate.pattern_score))

        # Weighted product (all must be non-zero for a high score)
        score = (
            (macro ** W_MACRO) *
            (setup ** W_SETUP) *
            (trigger ** W_TRIGGER) *
            (quant ** W_QUANT) *
            (ml ** W_ML) *
            (pattern ** W_PATTERN)
        )

        # Spread penalty
        if candidate.spread_cost > 0:
            score -= SPREAD_PENALTY_FACTOR * candidate.spread_cost

        # Contradiction penalty
        from brain.macro_analyzer import macro_bias_contradicts
        if macro_bias_contradicts(candidate.macro_bias, candidate.direction):
            score -= CONTRADICTION_PENALTY

        # Clamp to [0, 1]
        score = max(0.0, min(1.0, score))
        candidate.final_score = round(score, 4)
        return candidate.final_score

    def rank(self, candidates: List[TradeCandidate]) -> Optional[TradeCandidate]:
        """
        Score all candidates, deduplicate by signal hash, return the best.
        Returns None if no valid candidates.
        """
        if not candidates:
            return None

        scored = []
        for c in candidates:
            # Skip candidates that are already marked invalid
            if not c.causal_valid or not c.risk_valid:
                continue

            # Deduplicate
            sig_hash = c.signal_hash()
            if sig_hash in self._seen_hashes:
                logger.debug(f"[RANK] Duplicate signal skipped: {sig_hash}")
                continue
            self._seen_hashes.add(sig_hash)

            s = self.score(c)
            scored.append((s, c))

        if not scored:
            return None

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best = scored[0]

        logger.info(
            f"[TRADE-CANDIDATE] symbol={best.symbol} direction={best.direction} "
            f"type={best.signal_type} macro={best.macro_bias} "
            f"macro_score={best.macro_score:.2f} setup_score={best.setup_score:.2f} "
            f"trigger_score={best.trigger_score:.2f} rr={best.risk_reward:.2f} "
            f"ev=+${best.expected_value:.2f} source={best.source_path} "
            f"final_score={best.final_score:.4f}"
        )
        return best

    def reset(self):
        """Clear the seen-hash set (e.g., at start of a new cycle)."""
        self._seen_hashes.clear()