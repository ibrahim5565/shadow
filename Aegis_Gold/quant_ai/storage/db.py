"""AEGIS QUANT AI — storage (Sections 43-44).
SQLite persistence: model_predictions, forecast_errors, model_tournament,
regime_log, decisions (full audit record), signals. Uses stdlib sqlite3.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from typing import Dict, List

logger = logging.getLogger("quant_ai.storage")

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "data", "quant_ai.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, model TEXT, symbol TEXT, timeframe TEXT,
    forecast_price REAL, forecast_return REAL, direction TEXT,
    probability_up REAL, probability_down REAL, uncertainty REAL,
    horizon INT, latency_ms REAL, status TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS forecast_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, model TEXT, symbol TEXT, timeframe TEXT,
    horizon INT, actual REAL, forecast REAL, error REAL, squared_error REAL
);
CREATE TABLE IF NOT EXISTS model_tournament (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT, model TEXT, symbol TEXT, timeframe TEXT,
    mae REAL, rmse REAL, directional_accuracy REAL, brier REAL,
    win_rate REAL, profit_factor REAL, expectancy REAL, sharpe REAL,
    max_drawdown REAL, n_trades INT
);
CREATE TABLE IF NOT EXISTS regime_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, symbol TEXT, timeframe TEXT, regime TEXT,
    trend_strength REAL, vol_percentile REAL, autocorr REAL, reasons TEXT
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, action TEXT, symbol TEXT, timeframe TEXT, full_record TEXT
);
CREATE INDEX IF NOT EXISTS idx_pred_model ON model_predictions(model);
CREATE INDEX IF NOT EXISTS idx_err_model ON forecast_errors(model);
"""


class QuantAIStore:
    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def record_prediction(self, p: dict) -> None:
        try:
            self._conn.execute(
                "INSERT INTO model_predictions (ts, model, symbol, timeframe, forecast_price,"
                " forecast_return, direction, probability_up, probability_down, uncertainty,"
                " horizon, latency_ms, status, detail) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (p.get("timestamp"), p.get("model"), p.get("symbol"), p.get("timeframe"),
                 p.get("forecast_price"), p.get("forecast_return"),
                 (p.get("direction") or "").upper(), p.get("probability_up"),
                 p.get("probability_down"), p.get("uncertainty"), p.get("forecast_horizon"),
                 p.get("latency_ms"), (p.get("status") or "").upper(), p.get("detail")))
            self._conn.commit()
        except Exception as exc:
            logger.error("record_prediction failed: %s", exc)

    def record_forecast_error(self, *, ts: str, model: str, symbol: str, timeframe: str,
                              horizon: int, actual: float, forecast: float) -> None:
        err = float(forecast) - float(actual)
        try:
            self._conn.execute(
                "INSERT INTO forecast_errors (ts, model, symbol, timeframe, horizon,"
                " actual, forecast, error, squared_error) VALUES (?,?,?,?,?,?,?,?,?)",
                (ts, model, symbol, timeframe, horizon, actual, forecast, err, err * err))
            self._conn.commit()
        except Exception as exc:
            logger.error("record_forecast_error failed: %s", exc)

    def record_tournament(self, row: Dict) -> None:
        try:
            self._conn.execute(
                "INSERT INTO model_tournament (run_id, model, symbol, timeframe, mae, rmse,"
                " directional_accuracy, brier, win_rate, profit_factor, expectancy, sharpe,"
                " max_drawdown, n_trades) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row.get("run_id"), row.get("model"), row.get("symbol"), row.get("timeframe"),
                 row.get("mae"), row.get("rmse"), row.get("directional_accuracy"),
                 row.get("brier"), row.get("win_rate"), row.get("profit_factor"),
                 row.get("expectancy"), row.get("sharpe"), row.get("max_drawdown"),
                 row.get("n_trades")))
            self._conn.commit()
        except Exception as exc:
            logger.error("record_tournament failed: %s", exc)

    def record_regime(self, *, ts: str, symbol: str, timeframe: str, regime: str,
                      trend_strength: float, vol_percentile: float, autocorr: float,
                      reasons: List[str]) -> None:
        try:
            self._conn.execute(
                "INSERT INTO regime_log (ts, symbol, timeframe, regime, trend_strength,"
                " vol_percentile, autocorr, reasons) VALUES (?,?,?,?,?,?,?,?)",
                (ts, symbol, timeframe, regime, trend_strength, vol_percentile, autocorr,
                 json.dumps(reasons)))
            self._conn.commit()
        except Exception as exc:
            logger.error("record_regime failed: %s", exc)

    def record_decision(self, *, ts: str, action: str, symbol: str, timeframe: str,
                        record: dict) -> None:
        try:
            self._conn.execute(
                "INSERT INTO decisions (ts, action, symbol, timeframe, full_record) VALUES (?,?,?,?,?)",
                (ts, action, symbol, timeframe, json.dumps(record, default=str)))
            self._conn.commit()
        except Exception as exc:
            logger.error("record_decision failed: %s", exc)

    def recent_forecast_errors(self, symbol: str, limit: int = 2000) -> list:
        """Symbol-scoped error history across ALL models (for ModelSelector)."""
        rows = self._conn.execute(
            "SELECT model, actual, forecast FROM forecast_errors WHERE symbol=?"
            " ORDER BY id DESC LIMIT ?", (symbol, limit)).fetchall()
        return [{"model": m, "actual": float(a), "forecast": float(f)}
                for m, a, f in rows]

    def recent_errors(self, model: str, symbol: str = None, limit: int = 500) -> list:
        q = "SELECT actual, forecast FROM forecast_errors WHERE model=? ORDER BY id DESC LIMIT ?"
        args: list = [model, limit]
        if symbol:
            q = "SELECT actual, forecast FROM forecast_errors WHERE model=? AND symbol=? ORDER BY id DESC LIMIT ?"
            args = [model, symbol, limit]
        rows = self._conn.execute(q, args).fetchall()
        return [{"actual": float(a), "forecast": float(f)} for a, f in rows]