"""
🧠 AEGIS GOLD — Model Reliability Tracker
==========================================
Tracks rolling performance of every model and analysis component.
Maintains Win Rate, Profit Factor, and Net PnL per engine.
Returns adaptive reliability multipliers [0.5 - 1.2] to dynamically weight signals
in the Meta Decision Score engine.
"""

import os
import sqlite3
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("aegis.model_reliability")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "model_reliability.sqlite")


class ModelReliabilityTracker:
    """Tracks and calculates adaptive reliability scores for each trading engine."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database table for model reliability."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS model_outcomes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        engine_name TEXT NOT NULL,
                        won INTEGER NOT NULL,
                        pnl REAL NOT NULL,
                        confidence REAL DEFAULT 0.5
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_engine ON model_outcomes(engine_name)")
                conn.commit()
        except Exception as e:
            logger.error(f"[ModelReliability] Database init error: {e}")

    def record_outcome(self, engine_name: str, won: bool, pnl: float, confidence: float = 0.5):
        """Record trade result for a specific engine."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO model_outcomes (engine_name, won, pnl, confidence) VALUES (?, ?, ?, ?)",
                    (engine_name.lower().strip(), 1 if won else 0, float(pnl), float(confidence))
                )
                conn.commit()
        except Exception as e:
            logger.error(f"[ModelReliability] Error recording outcome for {engine_name}: {e}")

    def get_reliability_factor(self, engine_name: str, lookback: int = 30) -> float:
        """
        Returns adaptive reliability factor in range [0.5, 1.2].

        - 1.0  : Baseline (default or insufficient sample < 5 trades)
        - > 1.0: High performing (Win Rate > 60% or PF > 1.3) up to 1.2
        - < 1.0: Low performing (Win Rate < 45% or PF < 0.9) down to 0.5
        """
        key = engine_name.lower().strip()
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT won, pnl FROM model_outcomes WHERE engine_name = ? ORDER BY id DESC LIMIT ?",
                    (key, lookback)
                )
                rows = cursor.fetchall()

            if len(rows) < 5:
                return 1.0  # Insufficient sample — neutral factor

            wins = sum(r[0] for r in rows)
            n_trades = len(rows)
            win_rate = wins / n_trades

            gross_win = sum(r[1] for r in rows if r[1] > 0)
            gross_loss = abs(sum(r[1] for r in rows if r[1] < 0))
            profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (2.5 if gross_win > 0 else 1.0)

            # Base factor driven by win rate and profit factor
            if win_rate >= 0.65 and profit_factor >= 1.5:
                factor = 1.20
            elif win_rate >= 0.55 and profit_factor >= 1.2:
                factor = 1.10
            elif win_rate >= 0.45 and profit_factor >= 0.95:
                factor = 1.00
            elif win_rate >= 0.35 and profit_factor >= 0.70:
                factor = 0.80
            else:
                factor = 0.50

            return round(factor, 2)
        except Exception as e:
            logger.debug(f"[ModelReliability] Error fetching factor for {engine_name}: {e}")
            return 1.0

    def get_all_stats(self, lookback: int = 50) -> Dict[str, Dict[str, Any]]:
        """Returns statistics for all registered engines."""
        stats = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT engine_name FROM model_outcomes")
                engines = [r[0] for r in cursor.fetchall()]

                for eng in engines:
                    cursor.execute(
                        "SELECT won, pnl FROM model_outcomes WHERE engine_name = ? ORDER BY id DESC LIMIT ?",
                        (eng, lookback)
                    )
                    rows = cursor.fetchall()
                    if not rows:
                        continue
                    n = len(rows)
                    w = sum(r[0] for r in rows)
                    wr = round(w / n, 3)
                    gw = sum(r[1] for r in rows if r[1] > 0)
                    gl = abs(sum(r[1] for r in rows if r[1] < 0))
                    pf = round((gw / gl) if gl > 0 else (2.5 if gw > 0 else 1.0), 2)
                    rel = self.get_reliability_factor(eng, lookback)

                    stats[eng] = {
                        "trades": n,
                        "wins": w,
                        "win_rate": wr,
                        "profit_factor": pf,
                        "reliability_factor": rel
                    }
        except Exception as e:
            logger.error(f"[ModelReliability] Error getting all stats: {e}")
        return stats
