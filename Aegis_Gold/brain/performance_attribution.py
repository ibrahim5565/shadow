"""
===========================================================================
AEGIS GOLD v8.0 -- Performance Attribution Engine
===========================================================================

PURPOSE:
--------
After every trade closes, dissect WHAT caused the outcome:
- Which signal sources (SCALP, SMC, ML, RL) were present → did they predict correctly?
- Which confidence components (structure, MTF, momentum...) were high → did they add value?
- Was the session/regime combination profitable?

This feeds directly into the SelfOptimizer's weight adjustments and the
ConfidenceEngine's component reweighting.

ATTRIBUTION REPORT (per trade):
{
  "source_accuracy": {
      "SCALP": { "predicted": "BUY", "correct": True/False },
      "SMC":   { ... },
      "ML":    { ... },
      "RL":    { ... }
  },
  "component_scores_at_entry": { ... },  # from explainability record
  "regime_at_entry": str,
  "session_at_entry": str,
  "outcome": "WIN" | "LOSS" | "BREAKEVEN",
  "pnl": float,
  "holding_minutes": float
}

AGGREGATED STATS (updated after every trade):
{
  "SCALP_win_rate": float,       # running win rate when SCALP fired
  "SMC_win_rate": float,         # running win rate when SMC fired
  "ML_win_rate": float,
  "RL_win_rate": float,
  "LONDON_win_rate": float,
  "NY_win_rate": float,
  "TREND_win_rate": float,
  "RANGE_win_rate": float,
  "structure_score_correlation": float,  # corr between structure score and winning
  "smc_score_correlation": float,
  ...
}
===========================================================================
"""

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger("aegis.attribution")

BASE_DIR = Path(__file__).parent.parent
ATTRIB_DB_PATH = BASE_DIR / "data" / "attribution.db"
ATTRIB_STATS_PATH = BASE_DIR / "data" / "attribution_stats.json"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def _init_db():
    ATTRIB_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ATTRIB_DB_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attributions (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id       TEXT,
                timestamp      TEXT,
                symbol         TEXT,
                direction      TEXT,
                outcome        TEXT,
                pnl            REAL,
                holding_min    REAL,
                signal_scalp   INTEGER,
                signal_smc     INTEGER,
                signal_ml      INTEGER,
                signal_rl      TEXT,
                regime         TEXT,
                session        TEXT,
                confidence     INTEGER,
                score_structure INTEGER,
                score_smc       INTEGER,
                score_mtf       INTEGER,
                score_statistical INTEGER,
                score_ml         INTEGER,
                score_momentum   INTEGER,
                score_volatility INTEGER,
                raw_json       TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_att_trade ON attributions(trade_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_att_outcome ON attributions(outcome)")
        conn.commit()
    finally:
        conn.close()


_init_db()


# ---------------------------------------------------------------------------
# Record attribution for a closed trade
# ---------------------------------------------------------------------------

def record_attribution(
    trade_id: str,
    symbol: str,
    direction: str,
    outcome: str,       # "WIN" | "LOSS" | "BREAKEVEN"
    pnl: float,
    holding_minutes: float,
    explanation: dict,  # from explainability.get_explanation_for_trade
):
    """
    Store attribution record for a closed trade.
    `explanation` is the full dict from explainability.py.
    """
    try:
        sig = explanation.get("signal_sources", {})
        ctx = explanation.get("market_context", {})
        bd = explanation.get("component_breakdown", {})

        conn = sqlite3.connect(str(ATTRIB_DB_PATH))
        conn.execute("""
            INSERT INTO attributions (
                trade_id, timestamp, symbol, direction, outcome, pnl, holding_min,
                signal_scalp, signal_smc, signal_ml, signal_rl,
                regime, session, confidence,
                score_structure, score_smc, score_mtf, score_statistical,
                score_ml, score_momentum, score_volatility,
                raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(trade_id),
            datetime.now(timezone.utc).isoformat(),
            symbol, direction, outcome, pnl, holding_minutes,
            1 if sig.get("SCALP", {}).get("passed") else 0,
            1 if sig.get("SMC", {}).get("passed") else 0,
            1 if sig.get("ML", {}).get("passed") else 0,
            sig.get("RL", {}).get("action", "WAIT"),
            ctx.get("regime", ""),
            ctx.get("session", ""),
            explanation.get("final_confidence", 0),
            bd.get("structure", {}).get("score", 0),
            bd.get("smc", {}).get("score", 0),
            bd.get("mtf", {}).get("score", 0),
            bd.get("statistical", {}).get("score", 0),
            bd.get("ml", {}).get("score", 0),
            bd.get("momentum", {}).get("score", 0),
            bd.get("volatility", {}).get("score", 0),
            json.dumps(explanation),
        ))
        conn.commit()
        conn.close()

        logger.info(f"[ATTRIB] Recorded attribution for trade {trade_id}: {outcome} PnL={pnl:.2f}")
        _update_aggregated_stats()

    except Exception as e:
        logger.error(f"[ATTRIB] Failed to record attribution: {e}")


# ---------------------------------------------------------------------------
# Aggregated stats computation
# ---------------------------------------------------------------------------

def _update_aggregated_stats():
    """Recompute rolling attribution stats and save to JSON."""
    try:
        conn = sqlite3.connect(str(ATTRIB_DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM attributions ORDER BY id DESC LIMIT 500").fetchall()
        conn.close()

        if not rows:
            return

        stats: dict = defaultdict(lambda: {"wins": 0, "total": 0})

        for r in rows:
            is_win = (r["outcome"] == "WIN")
            _tally(stats, "overall", is_win)

            # Signal source accuracy
            if r["signal_scalp"]:
                _tally(stats, "SCALP", is_win)
            if r["signal_smc"]:
                _tally(stats, "SMC", is_win)
            if r["signal_ml"]:
                _tally(stats, "ML", is_win)
            if r["signal_rl"] in ("BUY", "SELL"):
                _tally(stats, "RL", is_win)

            # Session accuracy
            sess = r["session"] or "UNKNOWN"
            _tally(stats, f"session_{sess}", is_win)

            # Regime accuracy
            regime = r["regime"] or "UNKNOWN"
            _tally(stats, f"regime_{regime}", is_win)

            # Confidence bucket
            conf = r["confidence"] or 0
            bucket = f"conf_{(conf // 10) * 10}"
            _tally(stats, bucket, is_win)

        # Convert to win rates
        result = {}
        for k, v in stats.items():
            total = v["total"]
            wins = v["wins"]
            result[k] = {
                "win_rate": round(wins / total, 4) if total > 0 else 0.0,
                "wins": wins,
                "total": total
            }

        ATTRIB_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(str(ATTRIB_STATS_PATH), "w") as f:
            json.dump(result, f, indent=2)

        logger.info(f"[ATTRIB] Updated aggregated stats ({len(rows)} records analyzed)")

    except Exception as e:
        logger.error(f"[ATTRIB] Failed to update aggregated stats: {e}")


def _tally(stats: dict, key: str, is_win: bool):
    stats[key]["total"] += 1
    if is_win:
        stats[key]["wins"] += 1


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_aggregated_stats() -> dict:
    """Return the last computed aggregated attribution stats."""
    try:
        if ATTRIB_STATS_PATH.exists():
            with open(str(ATTRIB_STATS_PATH)) as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"[ATTRIB] Failed to load stats: {e}")
    return {}


def get_source_win_rates() -> dict:
    """Returns win rates per signal source (SCALP, SMC, ML, RL)."""
    stats = get_aggregated_stats()
    return {
        "SCALP": stats.get("SCALP", {}).get("win_rate", 0.5),
        "SMC":   stats.get("SMC",   {}).get("win_rate", 0.5),
        "ML":    stats.get("ML",    {}).get("win_rate", 0.5),
        "RL":    stats.get("RL",    {}).get("win_rate", 0.5),
    }


def get_session_win_rates() -> dict:
    """Returns win rates per session."""
    stats = get_aggregated_stats()
    return {
        "ASIAN":   stats.get("session_ASIAN",   {}).get("win_rate", 0.5),
        "LONDON":  stats.get("session_LONDON",  {}).get("win_rate", 0.5),
        "NY":      stats.get("session_NY",      {}).get("win_rate", 0.5),
        "OVERLAP": stats.get("session_OVERLAP", {}).get("win_rate", 0.5),
    }


def get_confidence_bucket_win_rates() -> dict:
    """Returns win rates per 10-point confidence band."""
    stats = get_aggregated_stats()
    return {
        f"{b}-{b+9}%": stats.get(f"conf_{b}", {}).get("win_rate", 0.0)
        for b in range(0, 100, 10)
    }


def get_regime_win_rates() -> dict:
    """Returns win rates per regime type."""
    stats = get_aggregated_stats()
    result = {}
    for k, v in stats.items():
        if k.startswith("regime_"):
            regime = k[len("regime_"):]
            result[regime] = v.get("win_rate", 0.5)
    return result
