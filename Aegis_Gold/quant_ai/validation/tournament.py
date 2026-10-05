"""AEGIS QUANT AI — ModelTournament (Section 33-34).

Evaluates every adapter + every baseline independently on the same out-of-
sample walk-forward split and produces a MODEL LEADERBOARD.  Results are
measured, never hard-coded.  Every model is compared against the naive
baselines (Section 30).
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd

from quant_ai.models.baselines import all_baselines
from quant_ai.storage.db import QuantAIStore
from quant_ai.validation.metrics import trade_metrics
from quant_ai.validation.walk_forward import WalkForwardValidator

logger = logging.getLogger("quant_ai.validation.tournament")


class ModelTournament:
    def __init__(self, store: Optional[QuantAIStore] = None, embargo: int = 1,
                 min_samples: int = 120):
        self.store = store
        self.embargo = embargo
        self.min_samples = min_samples
        self.walk = WalkForwardValidator(embargo=embargo)

    def run(self, models: List, df: pd.DataFrame, horizon: int,
            symbol: str = "XAUUSD", timeframe: str = "M5",
            step: int = 5, run_id: Optional[str] = None) -> List[dict]:
        run_id = run_id or f"tourney-{uuid.uuid4().hex[:8]}"
        leaderboard: List[dict] = []
        for model in models:
            m0 = time.time()
            try:
                res = self.walk.evaluate(model, df, horizon, symbol=symbol,
                                         timeframe=timeframe, step=step,
                                         min_samples=self.min_samples)
                mets = res.metrics()
            except Exception as exc:
                logger.error("tournament eval failed for %s: %s", model.name, exc)
                mets = {"error": str(exc), "n": 0}
            row = {
                "run_id": run_id,
                "model": model.name,
                "symbol": symbol,
                "timeframe": timeframe,
                "elapsed_s": round(time.time() - m0, 2),
                **mets,
            }
            leaderboard.append(row)
            if self.store is not None:
                self.store.record_tournament({**row, "brier": row.get("brier"),
                                              "win_rate": row.get("win_rate", 0),
                                              "profit_factor": row.get("profit_factor", 0),
                                              "expectancy": row.get("expectancy", 0),
                                              "sharpe": row.get("sharpe", 0),
                                              "max_drawdown": row.get("max_drawdown", 0),
                                              "n_trades": row.get("n", 0)})
        leaderboard.sort(key=lambda r: (r.get("directional_accuracy") is not None,
                                        r.get("directional_accuracy", -1)), reverse=True)
        return leaderboard

    @staticmethod
    def print_leaderboard(leaderboard: List[dict]) -> str:
        lines = [f"{'model':<24} {'n':>5} {'MAE':>10} {'RMSE':>10} {'dirAcc':>7} {'Brier':>7}",
                 "-" * 70]
        for r in leaderboard:
            lines.append(
                f"{str(r.get('model')):<24} {r.get('n', 0):>5} "
                f"{_fmt(r.get('mae')):>10} {_fmt(r.get('rmse')):>10} "
                f"{_fmt(r.get('directional_accuracy')):>7} {_fmt(r.get('brier')):>7}")
        return "\n".join(lines)


def _fmt(v) -> str:
    return "nan" if v is None else f"{v:.5f}"