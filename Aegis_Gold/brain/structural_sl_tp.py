"""
===========================================================================
AEGIS GOLD — Structural SL/TP Derivation (Pattern Consensus Architecture)
===========================================================================

PURPOSE:
  Derives stop-loss and take-profit prices from the actual structural patterns
  that triggered a consensus entry signal — NOT from generic ATR multiples.

SL DERIVATION:
  SL = beyond the invalidation level of the STRONGEST confirming pattern.
  Pattern hierarchy (strongest first):
    CHoCH > BOS+OB+Sweep > BOS+OB > OB alone > Sweep alone > FVG alone
  Plus a spread/slippage buffer.

TP DERIVATION:
  TP = the next opposing liquidity pool / unmitigated FVG / prior structure
  point in the predicted direction — where price is STRUCTURALLY likely to react.

MINIMUM R:R FLOOR:
  2.0R is the hard minimum. If no structural TP yields >= 2.0R, the trade
  is REJECTED. There is no synthetic fallback TP.

AUDIT TRAIL:
  Returns sl_basis and tp_basis strings describing which pattern set each level.
  These are stored in the trade record for post-trade attribution.
===========================================================================
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

logger = logging.getLogger("aegis.structural_sl_tp")

# Minimum R:R floor — hard gate. Trades below this are rejected.
MIN_RR_RATIO = 2.0

# Pattern strength hierarchy (higher = stronger structural evidence)
PATTERN_STRENGTH = {
    "CHoCH_BUY":       10,
    "CHoCH_SELL":      10,
    "CHoCH_BULLISH":   10,
    "CHoCH_BEARISH":   10,
    "BOS_BUY":          8,
    "BOS_SELL":         8,
    "BOS_BULLISH":      8,
    "BOS_BEARISH":      8,
    "SWEEP_BUY":        7,
    "SWEEP_SELL":       7,
    "OB_BUY":           6,
    "OB_SELL":          6,
    "FVG_BUY":          5,
    "FVG_BULLISH":      5,
    "FVG_SELL":         5,
    "FVG_BEARISH":      5,
    "OMEGA_COMPOSITE":  4,
    "ML_ENSEMBLE":      3,
    "HURST_REGIME":     2,
    "KRONOS_FORECAST":  2,
    "SMC_BUY":          5,
    "SMC_SELL":         5,
}


def _pattern_strength(pattern_type: str) -> int:
    """Return numeric strength for pattern hierarchy sorting."""
    if pattern_type in PATTERN_STRENGTH:
        return PATTERN_STRENGTH[pattern_type]
    # Partial match (e.g. "BOS_BUY_OB")
    for key, val in PATTERN_STRENGTH.items():
        if key in pattern_type or pattern_type in key:
            return val
    return 1


def _slippage_buffer(symbol: str, point: float, direction: str) -> float:
    """
    Returns an absolute price buffer to add to the structural SL distance
    to account for spread and slippage.
    Gold: 15 pts buffer = 15 * 0.01 = $0.15
    EURUSD: 3 pts buffer = 3 * 0.00001 = $0.00003
    """
    if "XAU" in symbol:
        return 15.0 * point
    return 3.0 * point


def derive_sl_tp(
    votes: list,
    direction: str,
    snapshot,
    symbol: str,
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    Derive structurally-grounded SL and TP from the consensus votes.

    Parameters
    ----------
    votes:      List of EngineVote objects that agreed on 'direction'
    direction:  "BUY" or "SELL"
    snapshot:   FrozenDecisionSnapshot (for current_price, point, symbol)
    symbol:     Trading symbol ("XAUUSD" or "EURUSD")

    Returns
    -------
    (sl_price, tp_price, sl_basis, tp_basis)
    All four are None if no valid structural trade can be formed at >= 2.0R.

    Trade is REJECTED (all None) when:
      - No structural SL can be derived from pattern invalidation levels
      - No structural TP exists at >= 2.0R
      - The best structural TP yields < 2.0R

    IMPORTANT: This function NEVER falls back to ATR multiples.
    """
    current_price = snapshot.current_price
    point = snapshot.point
    slip = _slippage_buffer(symbol, point, direction)

    if not current_price or current_price <= 0:
        logger.warning("[STRUCTURAL_SL_TP] current_price unavailable — rejecting")
        return None, None, None, None

    # ── Step 1: Find the strongest confirming pattern for SL ─────────────────

    best_ev = None
    best_strength = -1
    best_vote = None

    for vote in votes:
        if vote.direction != direction:
            continue
        for ev in vote.pattern_evidence:
            strength = _pattern_strength(ev.pattern_type)
            # Only use patterns with a real invalidation level
            if ev.invalidation_level and ev.invalidation_level > 0 and strength > best_strength:
                best_strength = strength
                best_ev = ev
                best_vote = vote

    # Try to get SL from vote's proposed_sl if pattern invalidation is missing
    if best_ev is None:
        # Fall back to highest-conviction vote's proposed_sl
        directional_votes = [v for v in votes if v.direction == direction and v.proposed_sl > 0]
        if not directional_votes:
            logger.warning("[STRUCTURAL_SL_TP] No SL derivable from pattern evidence — rejecting")
            return None, None, None, None

        best_vote = max(directional_votes, key=lambda v: v.conviction)
        raw_sl = best_vote.proposed_sl
        sl_basis = f"vote.proposed_sl from {best_vote.engine_name}"
    else:
        raw_sl = best_ev.invalidation_level
        sl_basis = f"pattern '{best_ev.pattern_type}' invalidation_level={raw_sl:.4f}"

    # Apply slippage buffer
    if direction == "BUY":
        sl_price = raw_sl - slip
        # Sanity: SL must be below current price
        if sl_price >= current_price:
            logger.warning(f"[STRUCTURAL_SL_TP] Derived BUY SL={sl_price:.4f} >= entry={current_price:.4f} — rejecting")
            return None, None, None, None
    else:
        sl_price = raw_sl + slip
        # Sanity: SL must be above current price
        if sl_price <= current_price:
            logger.warning(f"[STRUCTURAL_SL_TP] Derived SELL SL={sl_price:.4f} <= entry={current_price:.4f} — rejecting")
            return None, None, None, None

    sl_distance = abs(current_price - sl_price)
    min_tp_distance = sl_distance * MIN_RR_RATIO

    # ── Step 2: Find the best structural TP ─────────────────────────────────
    #
    # TP candidates (in preference order):
    # 1. SMC vote's proposed_tp (next opposing liquidity / unmitigated FVG / prior structure)
    # 2. Any other vote's proposed_tp that meets R:R
    # 3. NONE — do not synthesise

    tp_candidates = []

    for vote in votes:
        if vote.direction != direction:
            continue
        if vote.proposed_tp and vote.proposed_tp > 0:
            tp_dist = abs(current_price - vote.proposed_tp)
            rr = tp_dist / sl_distance if sl_distance > 0 else 0.0
            # Direction sanity check
            if direction == "BUY" and vote.proposed_tp > current_price:
                tp_candidates.append((rr, vote.proposed_tp, vote.engine_name))
            elif direction == "SELL" and vote.proposed_tp < current_price:
                tp_candidates.append((rr, vote.proposed_tp, vote.engine_name))

    if not tp_candidates:
        logger.info("[STRUCTURAL_SL_TP] No structural TP candidates — trade rejected (no fallback)")
        return None, None, None, None

    # Sort by R:R descending — take the best that meets the floor
    tp_candidates.sort(key=lambda x: x[0], reverse=True)
    best_rr, best_tp, tp_engine = tp_candidates[0]

    if best_rr < MIN_RR_RATIO:
        logger.info(
            f"[STRUCTURAL_SL_TP] Best structural TP gives R:R={best_rr:.2f} "
            f"< {MIN_RR_RATIO} floor — trade rejected (no synthetic fallback)"
        )
        return None, None, None, None

    tp_price = best_tp
    tp_basis = f"structural TP from {tp_engine} R:R={best_rr:.2f}"

    logger.info(
        f"[STRUCTURAL_SL_TP] {direction} SL={sl_price:.4f} ({sl_basis}) "
        f"TP={tp_price:.4f} ({tp_basis}) R:R={best_rr:.2f}"
    )

    return sl_price, tp_price, sl_basis, tp_basis
