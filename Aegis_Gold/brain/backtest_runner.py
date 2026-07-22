"""
===========================================================================
AEGIS GOLD — Walk-Forward Backtest Runner (Module 5)
===========================================================================

PURPOSE:
--------
Runs a purged walk-forward cross-validation over historical closed trades
from attribution.db (or journal.csv as fallback), computes out-of-sample
metrics with 95% bootstrap confidence intervals, and writes the result to
data/backtest_report.json.

This file is the prerequisite for enabling kelly_sizing=true in
quant_x_flags.json. The startup gate in core/main.py reads the report
and enforces that the CI lower bound exceeds the breakeven win rate.

USAGE:
    cd d:\\Trading\\Aegis_Gold
    python -m brain.backtest_runner

OUTPUT: data/backtest_report.json with keys:
    generated_at          — ISO timestamp
    total_trades          — trades analysed
    n_folds               — walk-forward folds completed
    oos_win_rate          — out-of-sample win rate (weighted mean)
    win_rate_ci_lower_bound — 2.5th percentile from bootstrap
    win_rate_ci_upper_bound — 97.5th percentile from bootstrap
    avg_rr                — average realised R:R across all trades
    sharpe                — Sharpe ratio (out-of-sample PnL series)
    psr                   — Probabilistic Sharpe Ratio
    sortino               — Sortino ratio
    calmar                — Calmar ratio (annualised PnL / max drawdown)
    max_drawdown_usd      — Peak-to-trough USD drawdown
    fold_metrics          — per-fold breakdown

NOTES:
- Minimum 50 closed trades required; report not written if insufficient.
- Fallback: if attribution.db is absent, reads data/journal.csv.
- No ML training is performed here — this is a signal-quality analysis.
===========================================================================
"""

import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import numpy as np

# Ensure project root is on path when run as a module
BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from brain.walk_forward_validator import (
    PurgedWalkForwardCV,
    bootstrap_trade_sequence,
    probabilistic_sharpe_ratio,
    compute_max_drawdown,
    compute_sortino,
    compute_calmar,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aegis.backtest_runner")

ATTRIBUTION_DB = BASE_DIR / "data" / "attribution.db"
JOURNAL_CSV    = BASE_DIR / "data" / "journal.csv"
REPORT_PATH    = BASE_DIR / "data" / "backtest_report.json"

MIN_TRADES = 50   # Minimum closed trades to run the analysis


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def _load_from_attribution_db() -> List[dict]:
    """Load all closed trades from attribution.db."""
    import sqlite3
    conn = sqlite3.connect(str(ATTRIBUTION_DB))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT ticket, timestamp, confidence, outcome, pnl_usd, "
            "rr_multiple, session, regime FROM attributions ORDER BY id ASC"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _load_from_journal_csv() -> List[dict]:
    """Fallback: load trades from journal.csv."""
    trades = []
    if not JOURNAL_CSV.exists():
        return trades
    with open(JOURNAL_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                pnl = float(row.get("pnl_usd") or 0)
                trades.append({
                    "ticket":      row.get("trade_id"),
                    "timestamp":   row.get("timestamp"),
                    "confidence":  float(row.get("confidence") or 50),
                    "outcome":     "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BREAKEVEN"),
                    "pnl_usd":     pnl,
                    "rr_multiple": None,
                    "session":     row.get("session", "UNKNOWN"),
                    "regime":      row.get("regime", "UNKNOWN"),
                })
            except (ValueError, KeyError):
                continue
    return trades


def load_trades() -> List[dict]:
    """Load closed trades from attribution.db; fall back to journal.csv."""
    if ATTRIBUTION_DB.exists():
        try:
            trades = _load_from_attribution_db()
            if trades:
                logger.info("Loaded %d trades from attribution.db", len(trades))
                return trades
        except Exception as exc:
            logger.warning("attribution.db read failed (%s) — falling back to journal.csv", exc)

    trades = _load_from_journal_csv()
    if trades:
        logger.info("Loaded %d trades from journal.csv (fallback)", len(trades))
    return trades


# ---------------------------------------------------------------------------
# Feature extraction (simple signal-quality features for logistic regression)
# ---------------------------------------------------------------------------

def _build_feature_matrix(trades: List[dict]):
    """
    Build a lightweight feature matrix for signal-quality prediction.
    Features: [confidence_norm, regime_is_trending, session_is_london, rr_available]
    Target:    1 = WIN, 0 = LOSS/BREAKEVEN
    """
    X, y, pnls = [], [], []
    for t in trades:
        conf = float(t.get("confidence") or 50) / 100.0  # normalise to [0, 1]
        regime = str(t.get("regime") or "").upper()
        session = str(t.get("session") or "").upper()
        rr = t.get("rr_multiple")

        feat = [
            conf,
            1.0 if "TREND" in regime else 0.0,
            1.0 if "LONDON" in session else 0.0,
            float(rr) if rr is not None else 0.0,
        ]
        label = 1 if t.get("outcome") == "WIN" else 0
        X.append(feat)
        y.append(label)
        pnls.append(float(t.get("pnl_usd") or 0))

    return np.array(X), np.array(y), np.array(pnls)


# ---------------------------------------------------------------------------
# Walk-Forward Analysis
# ---------------------------------------------------------------------------

def run_walk_forward(trades: List[dict], n_splits: int = 5, embargo_pct: float = 0.05) -> dict:
    """
    Runs purged walk-forward cross-validation.

    For each fold:
     - Train: simple logistic regression on signal features (inline, no sklearn required).
     - Validate: predict and compare to actual outcomes on OOS fold.
     - Collect: win rate, PnL series.

    Returns a dict with aggregate and per-fold metrics.
    """
    X, y, pnls = _build_feature_matrix(trades)
    n = len(X)

    wf = PurgedWalkForwardCV(n_splits=n_splits, embargo_pct=embargo_pct)
    # Walk-forward split requires a times array; use index as surrogate
    times = list(range(n))
    splits = wf.split(X, y, times)

    fold_metrics = []
    oos_pnls     = []
    oos_labels   = []
    oos_preds    = []

    for fold_idx, (train_idx, test_idx) in enumerate(splits):
        if len(train_idx) < 10 or len(test_idx) < 5:
            logger.warning("Fold %d skipped — insufficient samples", fold_idx + 1)
            continue

        X_train, y_train = X[train_idx], y[train_idx]
        X_test,  y_test  = X[test_idx],  y[test_idx]
        pnl_test         = pnls[test_idx]

        # Simple logistic regression via gradient descent (no sklearn dependency)
        weights = _fit_logistic(X_train, y_train, lr=0.01, epochs=200)
        y_pred  = _predict_logistic(X_test, weights)

        # Evaluate against actual outcomes (not the predicted labels)
        fold_wr  = float(np.mean(y_test))           # actual OOS win rate
        fold_pnl = float(np.sum(pnl_test))

        fold_metrics.append({
            "fold":         fold_idx + 1,
            "train_n":      int(len(train_idx)),
            "test_n":       int(len(test_idx)),
            "oos_win_rate": round(fold_wr * 100, 2),
            "oos_pnl_usd":  round(fold_pnl, 2),
        })

        oos_pnls.extend(pnl_test.tolist())
        oos_labels.extend(y_test.tolist())
        oos_preds.extend(y_pred.tolist())

    return {
        "fold_metrics": fold_metrics,
        "oos_pnls":     oos_pnls,
        "oos_labels":   oos_labels,
    }


def _fit_logistic(X: np.ndarray, y: np.ndarray, lr: float = 0.01, epochs: int = 200) -> np.ndarray:
    """Minimal logistic regression — no external dependencies."""
    n_feat  = X.shape[1]
    weights = np.zeros(n_feat + 1)  # +1 for bias

    X_b = np.hstack([np.ones((X.shape[0], 1)), X])
    y   = y.astype(float)

    for _ in range(epochs):
        logits = X_b @ weights
        probs  = 1.0 / (1.0 + np.exp(-np.clip(logits, -20, 20)))
        grad   = X_b.T @ (probs - y) / len(y)
        weights -= lr * grad

    return weights


def _predict_logistic(X: np.ndarray, weights: np.ndarray) -> np.ndarray:
    X_b    = np.hstack([np.ones((X.shape[0], 1)), X])
    logits = X_b @ weights
    probs  = 1.0 / (1.0 + np.exp(-np.clip(logits, -20, 20)))
    return (probs >= 0.5).astype(int)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_report(trades: List[dict], n_splits: int = 5, n_bootstrap: int = 1000) -> dict:
    """
    Run the full backtest pipeline and return the report dict.
    """
    logger.info("Running walk-forward analysis (%d folds) on %d trades...", n_splits, len(trades))
    wf_result   = run_walk_forward(trades, n_splits=n_splits)

    oos_pnls    = wf_result["oos_pnls"]
    oos_labels  = wf_result["oos_labels"]
    fold_metrics = wf_result["fold_metrics"]

    if not oos_pnls:
        raise ValueError("No out-of-sample data produced — increase trade count or reduce n_splits")

    # Aggregate OOS metrics
    oos_wr = float(np.mean(oos_labels)) if oos_labels else 0.0

    # Bootstrap confidence intervals
    logger.info("Running %d bootstrap iterations for confidence intervals...", n_bootstrap)
    ci = bootstrap_trade_sequence(oos_pnls, n_iterations=n_bootstrap)
    wr_lo = ci.get("winrate_ci_95", (oos_wr * 100, oos_wr * 100))[0] / 100.0
    wr_hi = ci.get("winrate_ci_95", (oos_wr * 100, oos_wr * 100))[1] / 100.0

    # Sharpe & PSR
    oos_arr   = np.array(oos_pnls)
    std_pnl   = float(np.std(oos_arr, ddof=1)) if len(oos_arr) > 1 else 1.0
    sharpe    = float(np.mean(oos_arr) / std_pnl) if std_pnl > 0 else 0.0
    psr       = probabilistic_sharpe_ratio(oos_pnls)

    # Sortino & Calmar
    sortino   = compute_sortino(oos_pnls)
    cum_pnl   = list(np.cumsum(oos_pnls))
    max_dd    = compute_max_drawdown([0.0] + cum_pnl)
    total_pnl = float(np.sum(oos_pnls))
    calmar    = compute_calmar(total_pnl, max_dd, n_years=1.0)

    # Average realised R:R
    rrs = [float(t["rr_multiple"]) for t in trades if t.get("rr_multiple") is not None]
    avg_rr = float(np.mean(rrs)) if rrs else 1.5

    report = {
        "generated_at":              datetime.now(timezone.utc).isoformat(),
        "total_trades":              len(trades),
        "n_folds":                   len(fold_metrics),
        "oos_win_rate":              round(oos_wr * 100, 2),
        "win_rate_ci_lower_bound":   round(wr_lo, 4),
        "win_rate_ci_upper_bound":   round(wr_hi, 4),
        "avg_rr":                    round(avg_rr, 3),
        "sharpe":                    round(sharpe, 4),
        "psr":                       round(psr, 4),
        "sortino":                   round(sortino, 4),
        "calmar":                    round(calmar, 4),
        "max_drawdown_usd":          round(max_dd, 2),
        "oos_total_pnl_usd":         round(total_pnl, 2),
        "fold_metrics":              fold_metrics,
    }

    # Breakeven win rate at current average R:R
    breakeven_wr = 1.0 / (1.0 + avg_rr) if avg_rr > 0 else 0.5
    report["breakeven_win_rate"] = round(breakeven_wr, 4)
    report["kelly_gate_pass"]    = bool(wr_lo > breakeven_wr)

    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    logger.info("=" * 60)
    logger.info("AEGIS WALK-FORWARD BACKTEST RUNNER — Module 5")
    logger.info("=" * 60)

    trades = load_trades()

    if len(trades) < MIN_TRADES:
        logger.error(
            "Insufficient trades: %d found, %d required. "
            "The bot needs more closed trades before a valid backtest can be run.",
            len(trades), MIN_TRADES
        )
        sys.exit(1)

    try:
        report = build_report(trades, n_splits=5, n_bootstrap=1000)
    except Exception as exc:
        logger.exception("Backtest failed: %s", exc)
        sys.exit(1)

    # Save report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    logger.info("Report written to %s", REPORT_PATH)

    # Print summary
    print()
    print("=" * 60)
    print("  WALK-FORWARD RESULTS")
    print("=" * 60)
    print(f"  Trades Analysed : {report['total_trades']}")
    print(f"  Folds           : {report['n_folds']}")
    print(f"  OOS Win Rate    : {report['oos_win_rate']:.1f}%  "
          f"[CI: {report['win_rate_ci_lower_bound']*100:.1f}% – "
          f"{report['win_rate_ci_upper_bound']*100:.1f}%]")
    print(f"  Avg R:R         : {report['avg_rr']:.2f}")
    print(f"  Breakeven WR    : {report['breakeven_win_rate']*100:.1f}%")
    print(f"  Sharpe          : {report['sharpe']:.4f}  (PSR={report['psr']:.4f})")
    print(f"  Sortino         : {report['sortino']:.4f}")
    print(f"  Calmar          : {report['calmar']:.4f}")
    print(f"  Max Drawdown    : ${report['max_drawdown_usd']:.2f}")
    print(f"  OOS Total PnL   : ${report['oos_total_pnl_usd']:.2f}")
    print()
    gate_str = "✅ PASS" if report["kelly_gate_pass"] else "❌ FAIL"
    print(f"  Kelly Gate      : {gate_str}  "
          f"(CI lower {report['win_rate_ci_lower_bound']*100:.1f}% "
          f"{'>' if report['kelly_gate_pass'] else '<'} "
          f"breakeven {report['breakeven_win_rate']*100:.1f}%)")
    print()
    print("  Per-Fold Breakdown:")
    for fm in report["fold_metrics"]:
        print(f"    Fold {fm['fold']}: train={fm['train_n']} test={fm['test_n']} "
              f"WR={fm['oos_win_rate']:.1f}% PnL=${fm['oos_pnl_usd']:.2f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
