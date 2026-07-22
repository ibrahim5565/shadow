"""
===========================================================================
AEGIS GOLD — Fractional Kelly Position Sizer
===========================================================================

PURPOSE:
--------
Compute evidence-based position sizes using the fractional Kelly criterion
with three user-mandated safety properties:

  1. Hard equity-risk cap (2% default) — independent of Kelly math.
     Even if win-rate estimates drift or the kelly_fraction is bumped,
     no single trade can risk more than MAX_RISK_PCT_OF_EQUITY of the
     current account equity.

  2. Bayesian win-rate shrinkage — prevents whipsaw sizing before
     live trade evidence accumulates. Blends rolling observed win-rate
     with the omega_performance.json prior (69%) using a 100-trade
     equivalent prior weight.

  3. Sequencing gate — kelly_sizing=true is blocked at startup unless
     data/backtest_report.json exists and passes the breakeven bar.
     (Gate is enforced in core/main.py._validate_kelly_flag().)

All functions are pure (no side-effects). The module is imported lazily
inside RiskManager — zero overhead when kelly_sizing flag is off.

USAGE (RiskManager):
    from brain.kelly_sizer import fractional_kelly_lot, get_prior_win_rate
    lot = fractional_kelly_lot(
        win_rate=shrunk_win_rate(rolling_wr, n, get_prior_win_rate()),
        avg_win_pts=1.8,
        avg_loss_pts=1.0,
        equity=10_000.0,
        risk_per_lot=200.0,        # $200 dollar risk per 1.0 lot at current SL
        kelly_fraction=0.25,
        max_lot_cap=1.0,
        max_risk_pct=0.02,
    )
===========================================================================
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aegis.kelly_sizer")

BASE_DIR = Path(__file__).parent.parent

# Hard equity-risk ceiling — the binding constraint in practice.
# Overridable via KELLY_MAX_RISK_PCT env var (see config/settings.py).
MAX_RISK_PCT_OF_EQUITY: float = float(os.getenv("KELLY_MAX_RISK_PCT", "0.02"))  # 2%


# ---------------------------------------------------------------------------
# 1. Bayesian Win-Rate Shrinkage
# ---------------------------------------------------------------------------

def get_prior_win_rate() -> float:
    """
    Read win_rate prior from omega_performance.json.
    Falls back to 0.5 (coin-flip) if the file is missing or malformed.
    This prior is used as the cold-start estimate before live trades accumulate.
    """
    try:
        perf_path = BASE_DIR / "data" / "omega_performance.json"
        if perf_path.exists():
            with open(perf_path) as f:
                data = json.load(f)
            total = data.get("total_trades", 0)
            wins  = data.get("wins", 0)
            if total > 0:
                return round(wins / total, 4)
    except Exception as exc:
        logger.debug("[KELLY] Could not load prior from omega_performance.json: %s", exc)
    return 0.5


def shrunk_win_rate(
    rolling_wr: float,
    rolling_n: int,
    prior_wr: Optional[float] = None,
    prior_weight: int = 100,
) -> float:
    """
    Bayesian shrinkage estimator — blends rolling observed win-rate with a prior.

    Formula:
        shrunk = (rolling_wr * rolling_n + prior_wr * prior_weight)
                 / (rolling_n + prior_weight)

    Behaviour:
        rolling_n = 0   → returns prior_wr exactly  (cold-start)
        rolling_n = 100 → 50/50 blend between prior and rolling
        rolling_n → ∞   → converges to rolling_wr

    This prevents whipsaw sizing when a short losing streak makes the
    rolling estimate temporarily negative-edge before statistical weight
    accumulates behind it.

    Parameters
    ----------
    rolling_wr    : Observed win fraction from attribution.db (0.0–1.0).
    rolling_n     : Number of trades in the rolling window.
    prior_wr      : Prior belief. If None, loaded from omega_performance.json.
    prior_weight  : Equivalent trade-count weight of the prior (default 100).

    Returns
    -------
    float — blended win-rate estimate (0.0–1.0)
    """
    if prior_wr is None:
        prior_wr = get_prior_win_rate()

    # Guard against degenerate inputs
    rolling_n  = max(0, int(rolling_n))
    rolling_wr = float(max(0.0, min(1.0, rolling_wr)))
    prior_wr   = float(max(0.0, min(1.0, prior_wr)))

    blended = (rolling_wr * rolling_n + prior_wr * prior_weight) / (rolling_n + prior_weight)
    return round(blended, 4)


# ---------------------------------------------------------------------------
# 2. Core Kelly Lot Calculator
# ---------------------------------------------------------------------------

def fractional_kelly_lot(
    win_rate: float,
    avg_win_pts: float,
    avg_loss_pts: float,
    equity: float,
    risk_per_lot: float,
    kelly_fraction: float = 0.25,
    max_lot_cap: float = 1.0,
    max_risk_pct: float = MAX_RISK_PCT_OF_EQUITY,
) -> float:
    """
    Compute the position size using fractional Kelly with a hard equity-risk cap.

    Parameters
    ----------
    win_rate      : Blended win probability (use shrunk_win_rate() output).
    avg_win_pts   : Average R:R multiple on winning trades.
    avg_loss_pts  : Average R:R multiple on losing trades (absolute value).
    equity        : Current account equity in USD.
    risk_per_lot  : Dollar risk per 1.0 lot at the current SL distance.
                    Computed as: sl_pts × pip_value_per_lot.
    kelly_fraction: Fraction of full Kelly to apply (default 0.25 = 25%).
    max_lot_cap   : Absolute lot ceiling (e.g. 1.0 lot).
    max_risk_pct  : Hard equity-risk ceiling (default 2%). Independent of
                    Kelly math — binding even if kelly_fraction is raised.

    Returns
    -------
    float — recommended lot size rounded to 2 d.p., or 0.0 if edge is
            negative (caller should fall back to base_lot).

    Ceiling precedence (lowest wins):
        1. Hard equity-risk cap  (equity × max_risk_pct / risk_per_lot)
        2. Absolute lot cap      (max_lot_cap)
        3. Fractional Kelly lot  (kelly_fraction × f* × equity / risk_per_lot)
    """
    # Guard degenerate inputs
    if avg_loss_pts <= 0 or equity <= 0 or risk_per_lot <= 0:
        logger.debug("[KELLY] Degenerate inputs — returning 0.0 (fallback to base_lot)")
        return 0.0

    # Full Kelly fraction
    rr = avg_win_pts / avg_loss_pts
    f_star = (rr * win_rate - (1.0 - win_rate)) / rr
    if f_star <= 0:
        logger.debug(
            "[KELLY] Negative edge f*=%.4f at WR=%.2f%% RR=%.2f — returning 0.0",
            f_star, win_rate * 100, rr
        )
        return 0.0

    # Fractional Kelly lot
    kelly_lot = (kelly_fraction * f_star * equity) / risk_per_lot

    # Hard equity-risk cap (Amendment 1 — independent ceiling)
    hard_cap_lot = (equity * max_risk_pct) / risk_per_lot

    # Take the most conservative of all three ceilings
    final_lot = round(min(kelly_lot, hard_cap_lot, max_lot_cap), 2)
    final_lot = max(0.01, final_lot)   # always at least one micro-lot

    hard_cap_active = (hard_cap_lot < kelly_lot) and (hard_cap_lot < max_lot_cap)

    logger.debug(
        "[KELLY] WR=%.1f%% RR=%.2f f*=%.4f fraction=%.2f | "
        "kelly_lot=%.2f hard_cap=%.2f max_cap=%.2f → final=%.2f (hard_cap=%s)",
        win_rate * 100, rr, f_star, kelly_fraction,
        kelly_lot, hard_cap_lot, max_lot_cap, final_lot,
        "ACTIVE" if hard_cap_active else "inactive",
    )

    return final_lot


# ---------------------------------------------------------------------------
# 3. Convenience: load stats from attribution.db and compute full lot
# ---------------------------------------------------------------------------

def compute_kelly_lot(
    equity: float,
    risk_per_lot: float,
    rolling_n: int = 100,
    kelly_fraction: float = 0.25,
    max_lot_cap: float = 1.0,
    max_risk_pct: float = MAX_RISK_PCT_OF_EQUITY,
) -> tuple:
    """
    High-level convenience function used by RiskManager.

    Loads rolling win stats from attribution.db, applies shrinkage,
    and returns (lot_size, metadata_dict).

    Returns (0.0, metadata) to signal "fall back to base_lot" when
    edge is negative or data is insufficient.

    Returns
    -------
    (lot: float, meta: dict)
        meta keys: n, raw_win_rate, blended_win_rate, hard_cap_active,
                   kelly_lot_raw, final_lot, fallback_reason
    """
    meta = {
        "n": 0,
        "raw_win_rate": None,
        "blended_win_rate": None,
        "hard_cap_active": False,
        "kelly_lot_raw": None,
        "final_lot": None,
        "fallback_reason": None,
    }

    try:
        from brain.attribution_writer import get_rolling_win_stats
        stats = get_rolling_win_stats(last_n=rolling_n)
        n           = stats["n"]
        raw_wr      = stats["win_rate"]
        avg_win_pts = stats["avg_win_pts"]
        avg_loss_pts = stats["avg_loss_pts"]

        meta["n"]            = n
        meta["raw_win_rate"] = raw_wr

        prior_wr    = get_prior_win_rate()
        blended_wr  = shrunk_win_rate(raw_wr, n, prior_wr)
        meta["blended_win_rate"] = blended_wr

        lot = fractional_kelly_lot(
            win_rate=blended_wr,
            avg_win_pts=avg_win_pts,
            avg_loss_pts=avg_loss_pts,
            equity=equity,
            risk_per_lot=risk_per_lot,
            kelly_fraction=kelly_fraction,
            max_lot_cap=max_lot_cap,
            max_risk_pct=max_risk_pct,
        )

        # Recompute whether hard cap was binding for metadata
        if avg_loss_pts > 0:
            rr     = avg_win_pts / avg_loss_pts
            f_star = (rr * blended_wr - (1 - blended_wr)) / rr
            if f_star > 0:
                kelly_raw = (kelly_fraction * f_star * equity) / risk_per_lot
                hard_cap  = (equity * max_risk_pct) / risk_per_lot
                meta["kelly_lot_raw"]    = round(kelly_raw, 2)
                meta["hard_cap_active"]  = hard_cap < kelly_raw

        meta["final_lot"] = lot
        return lot, meta

    except Exception as exc:
        logger.error("[KELLY] compute_kelly_lot failed: %s", exc)
        meta["fallback_reason"] = str(exc)
        return 0.0, meta
