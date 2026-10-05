"""AEGIS QUANT AI — performance metrics (Section 31).

Forecast metrics (MAE/RMSE/directional accuracy/Brier/calibration) and
trading metrics (win rate, profit factor, expectancy, Sharpe, Sortino,
Calmar, max drawdown, recovery factor).
"""
from __future__ import annotations

import logging
from typing import List, Optional, Sequence

import numpy as np

logger = logging.getLogger("quant_ai.validation.metrics")


def mae(actual: Sequence[float], forecast: Sequence[float]) -> float:
    return float(np.mean(np.abs(np.asarray(forecast) - np.asarray(actual))))


def rmse(actual: Sequence[float], forecast: Sequence[float]) -> float:
    return float(np.sqrt(np.mean((np.asarray(forecast) - np.asarray(actual)) ** 2)))


def directional_accuracy(actual: Sequence[float], forecast: Sequence[float]) -> float:
    a = np.asarray(actual)
    f = np.asarray(forecast)
    actual_dir = np.sign(np.diff(np.concatenate([[a[0]], a])))
    fc_dir = np.sign(np.diff(np.concatenate([[a[0]], f])))
    valid = (actual_dir != 0)
    if valid.sum() == 0:
        return 0.0
    return float(np.mean(actual_dir[valid] == fc_dir[valid]))


def brier_score(prob_up: Sequence[float], actual_up: Sequence[int]) -> float:
    p = np.asarray(prob_up, dtype=float)
    y = np.asarray(actual_up, dtype=int)
    if len(p) == 0 or np.any((p < 0) | (p > 1)):
        return float("nan")
    return float(np.mean((p - y) ** 2))


def calibration_curve(prob_up: Sequence[float], actual_up: Sequence[int],
                      bins: int = 5) -> List[dict]:
    p = np.asarray(prob_up, dtype=float)
    y = np.asarray(actual_up, dtype=int)
    if len(p) == 0 or np.any((p < 0) | (p > 1)):
        return []
    edges = np.linspace(0, 1, bins + 1)
    curve = []
    for i in range(bins):
        mask = (p > edges[i]) & (p <= edges[i + 1])
        if mask.sum() == 0:
            continue
        curve.append({"bin_low": float(edges[i]), "bin_high": float(edges[i + 1]),
                      "n": int(mask.sum()), "predicted": float(p[mask].mean()),
                      "observed": float(y[mask].mean())})
    return curve


def max_drawdown(pnls: Sequence[float]) -> float:
    eq = np.cumsum(np.asarray(pnls, dtype=float))
    peak = np.maximum.accumulate(eq)
    trough = np.minimum.accumulate(eq)
    return float(np.max(peak - trough) if len(eq) else 0.0)


def win_rate(pnls: Sequence[float]) -> float:
    arr = np.asarray(pnls, dtype=float)
    return float(np.mean(arr > 0)) if len(arr) else 0.0


def profit_factor(pnls: Sequence[float]) -> float:
    arr = np.asarray(pnls, dtype=float)
    gross = arr[arr > 0].sum()
    gross_loss = abs(arr[arr < 0].sum())
    return float(gross / gross_loss) if gross_loss > 0 else float("inf")


def expectancy(pnls: Sequence[float]) -> float:
    arr = np.asarray(pnls, dtype=float)
    return float(arr.mean()) if len(arr) else 0.0


def sharpe(pnls: Sequence[float], periods_per_year: float = 252 * 24 * 12) -> float:
    arr = np.asarray(pnls, dtype=float)
    if len(arr) < 2 or arr.std() == 0:
        return 0.0
    return float(arr.mean() / arr.std() * np.sqrt(periods_per_year))


def sortino(pnls: Sequence[float], periods_per_year: float = 252 * 24 * 12) -> float:
    arr = np.asarray(pnls, dtype=float)
    downside = arr[arr < 0]
    if len(arr) < 2 or len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(arr.mean() / downside.std() * np.sqrt(periods_per_year))


def calmar(pnls: Sequence[float]) -> float:
    md = max_drawdown(pnls)
    ann = float(np.asarray(pnls, dtype=float).sum())
    return float(ann / md) if md > 0 else (float("inf") if ann > 0 else 0.0)


def recovery_factor(pnls: Sequence[float]) -> float:
    md = max_drawdown(pnls)
    net = float(np.asarray(pnls, dtype=float).sum())
    return float(net / md) if md > 0 else 0.0


def trade_metrics(pnls: Sequence[float]) -> dict:
    arr = np.asarray(pnls, dtype=float)
    return {
        "n_trades": int(len(arr)),
        "win_rate": round(win_rate(arr), 4),
        "profit_factor": round(profit_factor(arr), 4) if len(arr) else 0.0,
        "expectancy": round(expectancy(arr), 4),
        "sharpe": round(sharpe(arr), 4),
        "sortino": round(sortino(arr), 4),
        "calmar": round(calmar(arr), 4) if len(arr) else 0.0,
        "max_drawdown": round(max_drawdown(arr), 4),
        "recovery_factor": round(recovery_factor(arr), 4),
        "avg_trade": round(float(arr.mean()), 4) if len(arr) else 0.0,
        "total_pnl": round(float(arr.sum()), 4),
    }


def forecast_metrics(actual: Sequence[float], forecast: Sequence[float]) -> dict:
    return {
        "mae": round(mae(actual, forecast), 6),
        "rmse": round(rmse(actual, forecast), 6),
        "directional_accuracy": round(directional_accuracy(actual, forecast), 4),
    }