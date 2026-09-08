"""
===========================================================================
AEGIS GOLD — Attribution Writer
===========================================================================

PURPOSE:
--------
Every time a trade closes, write one row to attribution.db.
This is the single feed that:
  - CalibrationMonitor reads to build the reliability diagram
  - DriftMonitor reads to detect feature distribution shifts
  - BacktestRunner reads to run walk-forward validation
  - KellySizer reads to compute shrunk win-rate estimates

SCHEMA (attributions table):
  id              — auto-increment primary key
  ticket          — MT5 position ticket (int)
  timestamp       — ISO 8601 UTC close time
  confidence      — stated confidence at signal time (0-100)
  regime          — market regime label (e.g. "TRENDING_UP")
  session         — trading session (ASIAN/LONDON/NY/OVERLAP)
  signal_source   — "SCALP" or "SMC"
  outcome         — "WIN" / "LOSS" / "BREAKEVEN"
  pnl_usd         — realised P&L in USD (net of swap/commission)
  rr_multiple     — realised R:R multiple (pnl_pts / sl_pts). None if SL unknown.
  adx             — ADX value at signal time (float, optional)
  rsi             — RSI value at signal time (float, optional)
  spread          — spread in points at entry (float, optional)

USAGE:
  from brain.attribution_writer import write_attribution
  write_attribution(ticket=123456, confidence=72, regime="TRENDING_UP",
                    session="LONDON", signal_source="SCALP",
                    outcome="WIN", pnl_usd=14.50, rr_multiple=1.8)
===========================================================================
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("aegis.attribution")

BASE_DIR = Path(__file__).parent.parent
ATTRIBUTION_DB = BASE_DIR / "data" / "attribution.db"


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def _ensure_schema() -> None:
    """
    Create the attributions table and indexes if they don't already exist.
    Safe to call on every write — all CREATE statements are idempotent.
    """
    ATTRIBUTION_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ATTRIBUTION_DB))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS attributions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket        INTEGER NOT NULL,
                timestamp     TEXT    NOT NULL,
                confidence    REAL    NOT NULL,
                regime        TEXT    DEFAULT 'UNKNOWN',
                session       TEXT    DEFAULT 'UNKNOWN',
                signal_source TEXT    DEFAULT 'SCALP',
                outcome       TEXT    NOT NULL,  -- WIN | LOSS | BREAKEVEN
                pnl_usd       REAL    NOT NULL,
                rr_multiple   REAL    DEFAULT NULL,
                adx           REAL    DEFAULT NULL,
                rsi           REAL    DEFAULT NULL,
                spread        REAL    DEFAULT NULL,
                historical_edge TEXT  DEFAULT 'neutral',
                microstructure_quality TEXT DEFAULT 'clean'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attr_ticket    ON attributions(ticket)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attr_timestamp ON attributions(timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_attr_outcome   ON attributions(outcome)")
        
        # Add all columns dynamically for backward compatibility with existing databases
        expected_columns = {
            "ticket": "INTEGER DEFAULT 0",
            "timestamp": "TEXT DEFAULT ''",
            "confidence": "REAL DEFAULT 50.0",
            "regime": "TEXT DEFAULT 'UNKNOWN'",
            "session": "TEXT DEFAULT 'UNKNOWN'",
            "signal_source": "TEXT DEFAULT 'SCALP'",
            "outcome": "TEXT DEFAULT 'BREAKEVEN'",
            "pnl_usd": "REAL DEFAULT 0.0",
            "rr_multiple": "REAL DEFAULT NULL",
            "adx": "REAL DEFAULT NULL",
            "rsi": "REAL DEFAULT NULL",
            "spread": "REAL DEFAULT NULL",
            "historical_edge": "TEXT DEFAULT 'neutral'",
            "microstructure_quality": "TEXT DEFAULT 'clean'"
        }
        cursor = conn.cursor()
        existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(attributions)").fetchall()}
        for col_name, col_def in expected_columns.items():
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE attributions ADD COLUMN {col_name} {col_def}")
                except sqlite3.OperationalError as ex:
                    logger.debug("Failed adding column %s: %s", col_name, ex)
                    
        conn.commit()
    finally:
        conn.close()


# Bootstrap on import — cheap (no-op after first run)
_ensure_schema()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_attribution(
    ticket: int,
    confidence: float,
    outcome: str,             # "WIN" | "LOSS" | "BREAKEVEN"
    pnl_usd: float,
    regime: str = "UNKNOWN",
    session: str = "UNKNOWN",
    signal_source: str = "SCALP",
    rr_multiple: Optional[float] = None,
    adx: Optional[float] = None,
    rsi: Optional[float] = None,
    spread: Optional[float] = None,
    historical_edge: str = "neutral",
    microstructure_quality: str = "clean",
) -> bool:
    """
    Write a single trade-close attribution row to attribution.db.

    Parameters
    ----------
    ticket                 : MT5 position ticket.
    confidence             : Stated confidence at signal time (0–100).
    outcome                : "WIN", "LOSS", or "BREAKEVEN".
    pnl_usd                : Realised P&L in USD (negative for losses).
    regime                 : Regime label from brain.decide().
    session                : Session name from FeatureFactory.
    signal_source          : "SCALP" or "SMC".
    rr_multiple            : Realised R:R (pnl_pts / sl_pts). Pass None if SL unknown.
    adx                    : ADX at signal time. Pass None if unavailable.
    rsi                    : RSI at signal time. Pass None if unavailable.
    spread                 : Spread in points at entry. Pass None if unavailable.
    historical_edge        : LLM analyst verdict edge (positive/negative/neutral).
    microstructure_quality : LLM analyst verdict microstructure (clean/degraded).

    Returns True on success, False on any write error.
    """
    if outcome not in ("WIN", "LOSS", "BREAKEVEN"):
        logger.warning("[ATTRIBUTION] Invalid outcome '%s' for ticket %s ? skipping write", outcome, ticket)
        return False

    try:
        conn = sqlite3.connect(str(ATTRIBUTION_DB))
        conn.execute(
            """
            INSERT INTO attributions
                (ticket, timestamp, confidence, regime, session,
                 signal_source, outcome, pnl_usd, rr_multiple, adx, rsi, spread,
                 historical_edge, microstructure_quality)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(ticket),
                datetime.now(timezone.utc).isoformat(),
                float(confidence),
                str(regime),
                str(session),
                str(signal_source),
                str(outcome),
                float(pnl_usd),
                float(rr_multiple) if rr_multiple is not None else None,
                float(adx)         if adx         is not None else None,
                float(rsi)         if rsi         is not None else None,
                float(spread)      if spread       is not None else None,
                str(historical_edge),
                str(microstructure_quality)
            )
        )
        conn.commit()
        conn.close()
        logger.debug(
            "[ATTRIBUTION] Wrote ticket=%s outcome=%s conf=%.0f pnl=%.2f edge=%s micro=%s",
            ticket, outcome, confidence, pnl_usd, historical_edge, microstructure_quality
        )
        return True
    except Exception as exc:
        logger.error("[ATTRIBUTION] Write failed for ticket %s: %s", ticket, exc)
        return False


# ---------------------------------------------------------------------------
# Query helpers (used by KellySizer and CalibrationMonitor)
# ---------------------------------------------------------------------------

def get_rolling_win_stats(last_n: int = 100) -> dict:
    """
    Returns win-rate and average pts statistics for the last N closed trades.

    Returns dict with keys:
        n            — number of trades found
        win_rate     — fraction (0.0–1.0)
        avg_win_pts  — average rr_multiple on winning trades (or 1.5 if none)
        avg_loss_pts — average |rr_multiple| on losing trades (or 1.0 if none)
    """
    try:
        if not ATTRIBUTION_DB.exists():
            return {"n": 0, "win_rate": 0.0, "avg_win_pts": 1.5, "avg_loss_pts": 1.0}

        conn = sqlite3.connect(str(ATTRIBUTION_DB))
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            "SELECT outcome, rr_multiple FROM attributions "
            "ORDER BY id DESC LIMIT ?",
            (last_n,)
        ).fetchall()
        conn.close()

        if not rows:
            return {"n": 0, "win_rate": 0.0, "avg_win_pts": 1.5, "avg_loss_pts": 1.0}

        n = len(rows)
        wins   = [r for r in rows if r["outcome"] == "WIN"]
        losses = [r for r in rows if r["outcome"] == "LOSS"]

        win_rate = len(wins) / n if n > 0 else 0.0

        # Use rr_multiple when available, fall back to 1.5 / 1.0
        win_rrs  = [r["rr_multiple"] for r in wins   if r["rr_multiple"] is not None]
        loss_rrs = [r["rr_multiple"] for r in losses if r["rr_multiple"] is not None]

        avg_win_pts  = (sum(win_rrs)  / len(win_rrs))  if win_rrs  else 1.5
        avg_loss_pts = (sum(loss_rrs) / len(loss_rrs)) if loss_rrs else 1.0
        avg_loss_pts = abs(avg_loss_pts)  # losses are stored negative in rr_multiple

        return {
            "n":            n,
            "win_rate":     round(win_rate, 4),
            "avg_win_pts":  round(avg_win_pts, 4),
            "avg_loss_pts": round(avg_loss_pts, 4),
        }

    except Exception as exc:
        logger.error("[ATTRIBUTION] get_rolling_win_stats failed: %s", exc)
        return {"n": 0, "win_rate": 0.0, "avg_win_pts": 1.5, "avg_loss_pts": 1.0}


def get_all_pnl_series(last_n: int = 500) -> list:
    """
    Returns list of pnl_usd values for the last N closed trades,
    ordered oldest-first. Used by BacktestRunner.
    """
    try:
        if not ATTRIBUTION_DB.exists():
            return []
        conn = sqlite3.connect(str(ATTRIBUTION_DB))
        rows = conn.execute(
            "SELECT pnl_usd FROM attributions ORDER BY id DESC LIMIT ?",
            (last_n,)
        ).fetchall()
        conn.close()
        return [r[0] for r in reversed(rows)]
    except Exception as exc:
        logger.error("[ATTRIBUTION] get_all_pnl_series failed: %s", exc)
        return []


def row_count() -> int:
    """Returns total number of attribution rows written to date."""
    try:
        if not ATTRIBUTION_DB.exists():
            return 0
        conn = sqlite3.connect(str(ATTRIBUTION_DB))
        n = conn.execute("SELECT COUNT(*) FROM attributions").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0
