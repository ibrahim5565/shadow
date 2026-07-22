import os
import json
import sqlite3
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

logger = logging.getLogger("aegis.observability")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISION_DB_PATH = os.path.join(BASE_DIR, "data", "decision_records.db")

@dataclass
class DecisionRecord:
    timestamp: str
    symbol: str
    action: str
    direction: str
    confidence: int
    uncertainty: float
    regime: str
    regime_confidence: float
    features_summary: str  # JSON representation of top features
    model_outputs: str     # JSON representation of all model predictions
    risk_assessment: str   # JSON of risk details
    sizing_rationale: str
    execution_details: str # JSON of slippage/spread metrics
    outcome: str
    shap_top_3: str        # JSON list
    config_hash: str
    model_version_id: str


class ObservabilityLogger:
    """
    Log aggregator to write structured decision records to decision_records.db.
    Ensures absolute audibility and reproducibility.
    """
    def __init__(self, db_path: str = DECISION_DB_PATH):
        self.db_path = db_path
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decision_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    action TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    confidence INTEGER,
                    uncertainty REAL,
                    regime TEXT,
                    regime_confidence REAL,
                    features_summary TEXT,
                    model_outputs TEXT,
                    risk_assessment TEXT,
                    sizing_rationale TEXT,
                    execution_details TEXT,
                    outcome TEXT,
                    shap_top_3 TEXT,
                    config_hash TEXT,
                    model_version_id TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize observability database: {e}")

    def log_decision_record(self, record: DecisionRecord) -> bool:
        """Writes the structured decision record to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO decision_records (
                    timestamp, symbol, action, direction, confidence, uncertainty,
                    regime, regime_confidence, features_summary, model_outputs,
                    risk_assessment, sizing_rationale, execution_details, outcome,
                    shap_top_3, config_hash, model_version_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.timestamp,
                record.symbol,
                record.action,
                record.direction,
                record.confidence,
                record.uncertainty,
                record.regime,
                record.regime_confidence,
                record.features_summary,
                record.model_outputs,
                record.risk_assessment,
                record.sizing_rationale,
                record.execution_details,
                record.outcome,
                record.shap_top_3,
                record.config_hash,
                record.model_version_id
            ))
            conn.commit()
            conn.close()
            
            # Emit structured JSON log to stdout/file for external ingestors
            structured_log = {
                "level": "INFO",
                "message": "Structured Decision Record emitted",
                "data": asdict(record)
            }
            logger.info(json.dumps(structured_log))
            return True
        except Exception as e:
            logger.error(f"Failed to log decision to observability database: {e}")
            return False


_obs_logger: Optional[ObservabilityLogger] = None

def get_observability_logger() -> ObservabilityLogger:
    global _obs_logger
    if _obs_logger is None:
        _obs_logger = ObservabilityLogger()
    return _obs_logger
