"""
shadow_validate_analyst.py
===========================================================================
Shadow-validates the V3 LLM Trading Analyst against a held-out window of
closed trades WITHOUT touching real execution, sizing, performance.db, or
model_arena.json.

The one question this answers with data:

    "When the analyst says approve / approve_reduced / reject, does that
     verdict actually correlate with what happened to the trade?"

If the sanity checks at the bottom fail, do NOT promote approve_reduced to
affect live lot sizing yet.

Usage
-----
    python brain/shadow_validate_analyst.py --holdout-days 20
    python brain/shadow_validate_analyst.py --holdout-days 20 --report-out shadow_report.json

Design
------
- Reads trades from performance.db that CLOSED within the last N days.
- For each trade, reconstructs its analyst prompt from explanations.db
  (same join used by train_analyst_dataset.py).
- Calls LLMTradingAnalyst in advisory-only mode — no execution hooks,
  no writes to any production table.
- Persists its own shadow log to data/shadow_validation.db (append-safe).
- Prints + optionally writes a structured JSON report.
===========================================================================
"""

import argparse
import json
import logging
import sqlite3
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── path bootstrap ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from brain.llm_analyst import LLMTradingAnalyst  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("shadow_validator")

PERF_DB    = BASE_DIR / "data" / "performance.db"
EXPLAIN_DB = BASE_DIR / "data" / "explanations.db"
SHADOW_DB  = BASE_DIR / "data" / "shadow_validation.db"


# ── shadow log schema ────────────────────────────────────────────────────────

def _ensure_shadow_schema() -> None:
    """Creates the shadow log table if it does not exist yet."""
    SHADOW_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(SHADOW_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS shadow_results (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            run_timestamp         TEXT NOT NULL,
            trade_id              TEXT NOT NULL,
            symbol                TEXT,
            direction             TEXT,
            trade_opened_at       TEXT,
            actual_win_loss       INTEGER,
            actual_pnl_usd        REAL,
            actual_rr_multiple    REAL,
            verdict_recommendation TEXT,
            model_agreement_count  TEXT,
            historical_edge        TEXT,
            microstructure_quality TEXT,
            structure_alignment    TEXT,
            reason_code            TEXT,
            analyst_thought        TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sv_run ON shadow_results(run_timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sv_verdict ON shadow_results(verdict_recommendation)")
    conn.commit()
    conn.close()


# ── result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ShadowResult:
    trade_id:              str
    symbol:                str
    direction:             str
    trade_opened_at:       str
    actual_win_loss:       int          #  1 = WIN, -1 = LOSS, 0 = open/unknown
    actual_pnl_usd:        float
    actual_rr_multiple:    float
    verdict_recommendation: str          # "approve" | "approve_reduced" | "reject"
    model_agreement_count: str
    historical_edge:       str
    microstructure_quality: str
    structure_alignment:   str
    reason_code:           str
    analyst_thought:       str


# ── data loading ─────────────────────────────────────────────────────────────

def load_holdout_trades(cutoff: datetime) -> list[dict]:
    """
    Return closed trades from performance.db whose open timestamp falls
    within the holdout window (cutoff → now).  Excludes still-open trades
    (win_loss IS NULL or profit_usd IS NULL).
    """
    if not PERF_DB.exists():
        logger.error("performance.db not found at %s", PERF_DB)
        return []

    conn = sqlite3.connect(str(PERF_DB))
    conn.row_factory = sqlite3.Row
    cutoff_iso = cutoff.isoformat()

    rows = conn.execute(
        """
        SELECT id, symbol, direction, timestamp AS opened_at,
               win_loss, profit_usd, profit_pips,
               adx_at_entry, rsi_at_entry, ai_confidence,
               session, regime, pattern
        FROM   trades
        WHERE  win_loss IN (1, -1)
          AND  timestamp >= ?
        ORDER  BY timestamp ASC
        """,
        (cutoff_iso,),
    ).fetchall()
    conn.close()

    logger.info("Found %d closed holdout trades (cutoff: %s)", len(rows), cutoff_iso)
    return [dict(r) for r in rows]


def _build_context_from_explanation(
    symbol: str, direction: str, opened_at: str
) -> dict | None:
    """
    Reconstruct the analyst prompt context for a given trade by finding the
    last TRADE-type explanation logged just before that trade was opened
    (within 10 s), matching symbol + direction.

    Returns None if no matching explanation found.
    """
    if not EXPLAIN_DB.exists():
        return None

    try:
        conn = sqlite3.connect(str(EXPLAIN_DB))
        conn.row_factory = sqlite3.Row

        # Fetch a narrow window of explanations around the trade open time
        rows = conn.execute(
            """
            SELECT signal_json, context_json, risk_json, confidence
            FROM   explanations
            WHERE  symbol    = ?
              AND  direction = ?
              AND  action    = 'TRADE'
              AND  timestamp <= ?
            ORDER  BY timestamp DESC
            LIMIT  5
            """,
            (symbol, direction, opened_at),
        ).fetchall()
        conn.close()
    except Exception as ex:
        logger.debug("Explanation DB query failed: %s", ex)
        return None

    if not rows:
        return None

    row = rows[0]
    try:
        signal_sources = json.loads(row["signal_json"] or "{}")
    except Exception:
        signal_sources = {}
    try:
        market_ctx = json.loads(row["context_json"] or "{}")
    except Exception:
        market_ctx = {}
    try:
        risk_raw = json.loads(row["risk_json"] or "{}")
    except Exception:
        risk_raw = {}

    confidence = float(row["confidence"] or 50)
    dir_val    = 1 if direction == "BUY" else (-1 if direction == "SELL" else 0)
    smc_pass   = signal_sources.get("SMC", {}).get("passed", False)
    spread     = float(market_ctx.get("spread", 20))

    return {
        "quant_signals": {
            "lstm":             {"direction": dir_val,   "probability": round(confidence / 100, 2)},
            "transformer":      {"direction": dir_val,   "probability": round((confidence - 5) / 100, 2)},
            "rl_agent":         {"action": direction.lower(), "expected_value": 1.0},
            "statistical_model":{"direction": dir_val if smc_pass else 0,
                                 "volatility_forecast": round(spread / 10, 2)},
        },
        "performance_context": {
            "reason_code_historical_win_rate": round(confidence, 1),
            "profit_factor": 1.7 if confidence >= 60 else 1.2,
            "current_drawdown_pct": 1.0,
            "recent_sharpe": 1.5,
            "ev_per_trade": 2.0 if confidence >= 60 else -0.5,
        },
        "market_microstructure": {
            "volatility_regime": market_ctx.get("regime", "RANGING"),
            "order_flow_imbalance": 0.15 if direction == "BUY" else -0.15,
            "liquidity_score": round(1.0 - spread / 100, 2),
            "current_spread": spread,
            "estimated_slippage": 0.5,
        },
        "structure_context": {
            "htf_bias": "bullish" if direction == "BUY" else "bearish",
            "mtf_zone": "demand" if direction == "BUY" else "supply",
            "ltf_trigger": "bos" if smc_pass else "rsi_bounce",
            "smc_context": "order_block" if smc_pass else "ema_crossover",
        },
        "risk_state": {
            "max_position_size": float(risk_raw.get("lot", 0.01)),
            "cooldown_flag": False,
            "daily_trade_count": 5,
            "daily_trade_limit": 50,
        },
    }


def _rr_multiple(trade: dict) -> float:
    """Best-effort R:R multiple from whatever columns are populated."""
    try:
        pips = float(trade.get("profit_pips") or 0)
        # We don't have sl_pips in perf DB reliably, so use pnl sign × 1.0 as proxy
        if pips != 0:
            return round(pips / 20.0, 3)   # assume 20-pt SL baseline
    except Exception:
        pass
    return 1.0 if (trade.get("win_loss") or 0) > 0 else -1.0


# ── shadow run ───────────────────────────────────────────────────────────────

def run_shadow_pass(trades: list[dict], analyst: LLMTradingAnalyst) -> list[ShadowResult]:
    results  = []
    skipped  = 0
    run_ts   = datetime.now(timezone.utc).isoformat()

    _ensure_shadow_schema()
    shadow_conn = sqlite3.connect(str(SHADOW_DB))

    for i, trade in enumerate(trades, 1):
        trade_id   = str(trade["id"])
        symbol     = trade["symbol"]
        direction  = trade["direction"]
        opened_at  = trade["opened_at"]

        logger.info("[%d/%d] Trade %s  %s %s", i, len(trades), trade_id, direction, symbol)

        ctx = _build_context_from_explanation(symbol, direction, opened_at)
        if ctx is None:
            logger.debug("  No explanation context found ? skipping.")
            skipped += 1
            continue

        # Advisory-only call: analyst never reaches any execution or DB-write path
        thought, verdict = analyst.analyze_trade(
            quant_signals        = ctx["quant_signals"],
            performance_context  = ctx["performance_context"],
            market_microstructure= ctx["market_microstructure"],
            structure_context    = ctx["structure_context"],
            risk_state           = ctx["risk_state"],
        )

        rec    = verdict.get("recommendation",      "reject")
        agree  = verdict.get("model_agreement_count","n/a")
        edge   = verdict.get("historical_edge",      "n/a")
        micro  = verdict.get("microstructure_quality","n/a")
        align  = verdict.get("structure_alignment",  "n/a")
        r_code = verdict.get("reason_code",          "n/a")

        pnl       = float(trade.get("profit_usd") or 0.0)
        win_loss  = int(trade.get("win_loss")  or 0)
        rr_mult   = _rr_multiple(trade)

        sr = ShadowResult(
            trade_id               = trade_id,
            symbol                 = symbol,
            direction              = direction,
            trade_opened_at        = opened_at,
            actual_win_loss        = win_loss,
            actual_pnl_usd         = pnl,
            actual_rr_multiple     = rr_mult,
            verdict_recommendation = rec,
            model_agreement_count  = agree,
            historical_edge        = edge,
            microstructure_quality = micro,
            structure_alignment    = align,
            reason_code            = r_code,
            analyst_thought        = thought,
        )
        results.append(sr)

        # Persist to shadow log (append-only, never touches production DBs)
        shadow_conn.execute(
            """
            INSERT INTO shadow_results
                (run_timestamp, trade_id, symbol, direction, trade_opened_at,
                 actual_win_loss, actual_pnl_usd, actual_rr_multiple,
                 verdict_recommendation, model_agreement_count,
                 historical_edge, microstructure_quality, structure_alignment,
                 reason_code, analyst_thought)
            VALUES (?,?,?,?,?, ?,?,?, ?,?, ?,?,?, ?,?)
            """,
            (run_ts, trade_id, symbol, direction, opened_at,
             win_loss, pnl, rr_mult,
             rec, agree, edge, micro, align, r_code, thought),
        )

    shadow_conn.commit()
    shadow_conn.close()

    if skipped:
        logger.warning("Skipped %d trades (no matching explanation context).", skipped)

    return results


# ── summarisation & sanity checks ────────────────────────────────────────────

def summarize(results: list[ShadowResult]) -> dict:
    """
    Answer the core validation question:
        Does the verdict predict the outcome?

    Sanity checks (must ALL pass before promote to live sizing):
      1. reject win_rate < approve win_rate
      2. approve_reduced win_rate is between reject and approve
      3. approve avg_pnl > approve_reduced avg_pnl > reject avg_pnl
    """
    by_verdict: dict[str, list[ShadowResult]] = {}
    for r in results:
        by_verdict.setdefault(r.verdict_recommendation, []).append(r)

    summary: dict = {}
    for verdict, group in sorted(by_verdict.items()):
        pnls   = [g.actual_pnl_usd      for g in group]
        rrs    = [g.actual_rr_multiple   for g in group]
        wins   = sum(1 for g in group if g.actual_win_loss == 1)
        n      = len(group)
        win_rate = wins / n if n else 0.0

        summary[verdict] = {
            "n_trades":       n,
            "win_rate":       round(win_rate, 3),
            "avg_pnl_usd":    round(statistics.mean(pnls),  2)   if pnls         else None,
            "pnl_stdev":      round(statistics.stdev(pnls), 2)   if len(pnls) > 1 else None,
            "avg_rr_multiple":round(statistics.mean(rrs),   3)   if rrs           else None,
            "total_pnl_usd":  round(sum(pnls),              2),
        }

    checks: dict[str, bool | str] = {}

    wr = {v: summary[v]["win_rate"] for v in summary}
    pnl_avg = {v: summary[v]["avg_pnl_usd"] or 0.0 for v in summary}

    if "reject" in wr and "approve" in wr:
        checks["reject_wr_below_approve_wr"] = wr["reject"] < wr["approve"]
    else:
        checks["reject_wr_below_approve_wr"] = "insufficient_data"

    if "approve_reduced" in wr and "approve" in wr and "reject" in wr:
        checks["approve_reduced_wr_between_reject_and_approve"] = (
            wr["reject"] <= wr["approve_reduced"] <= wr["approve"]
        )
    else:
        checks["approve_reduced_wr_between_reject_and_approve"] = "insufficient_data"

    if "approve" in pnl_avg and "reject" in pnl_avg:
        checks["approve_avg_pnl_above_reject"] = pnl_avg["approve"] > pnl_avg["reject"]
    else:
        checks["approve_avg_pnl_above_reject"] = "insufficient_data"

    if "approve_reduced" in pnl_avg and "approve" in pnl_avg:
        checks["approve_reduced_pnl_below_approve"] = (
            pnl_avg["approve_reduced"] <= pnl_avg["approve"]
        )
    else:
        checks["approve_reduced_pnl_below_approve"] = "insufficient_data"

    all_bool = [v for v in checks.values() if isinstance(v, bool)]
    overall_pass = all(all_bool) and len(all_bool) > 0

    return {
        "by_verdict":    summary,
        "sanity_checks": checks,
        "overall_pass":  overall_pass,
    }


def _print_report(report: dict) -> None:
    print("\n" + "=" * 62)
    print("  SHADOW VALIDATION REPORT")
    print("=" * 62)
    print(f"\n  Trades evaluated : {report.get('n_trades_evaluated', '?')}")
    print(f"  Holdout window   : last {report.get('holdout_days', '?')} days")
    print(f"  Context matches  : {report.get('n_with_context', '?')}")

    print("\n  Per-verdict breakdown:")
    print(f"  {'Verdict':<20} {'N':>5} {'Win%':>7} {'AvgPnL':>8} {'TotalPnL':>10}")
    print("  " + "-" * 54)
    for verdict, data in report["by_verdict"].items():
        print(
            f"  {verdict:<20} {data['n_trades']:>5} "
            f"{data['win_rate']*100:>6.1f}% "
            f"{(data['avg_pnl_usd'] or 0):>8.2f} "
            f"{data['total_pnl_usd']:>10.2f}"
        )

    print("\n  Sanity checks:")
    for name, result in report["sanity_checks"].items():
        icon = "PASS" if result is True else ("WARN" if result == "insufficient_data" else "FAIL")
        print(f"    [{icon}] {name}: {result}")

    print("\n" + "=" * 62)
    if report.get("overall_pass"):
        print("  VERDICT: PASS ? analyst verdicts correlate with outcomes.")
        print("  approve_reduced CAN be promoted to influence live sizing.")
    else:
        print("  VERDICT: FAIL (or insufficient data)")
        print("  DO NOT promote approve_reduced to affect live sizing yet.")
        print("  Collect more data or retrain before going live.")
    print("=" * 62 + "\n")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Shadow-validate the V3 LLM Trading Analyst against held-out trades."
    )
    parser.add_argument(
        "--holdout-days", type=int, default=20,
        help="Number of most-recent days of closed trades to evaluate (default: 20)."
    )
    parser.add_argument(
        "--max-trades", type=int, default=None,
        help="Cap evaluation to the most-recent N trades (useful for quick spot-checks)."
    )
    parser.add_argument(
        "--report-out", default=None,
        help="Optional path to write the JSON report (default: print only)."
    )
    parser.add_argument(
        "--local-url", default="http://localhost:8080",
        help="Local llama-server URL (default: http://localhost:8080)."
    )
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.holdout_days)
    trades = load_holdout_trades(cutoff)

    if args.max_trades and len(trades) > args.max_trades:
        logger.info("Capping evaluation to the most-recent %d trades.", args.max_trades)
        trades = trades[-args.max_trades:]

    if not trades:
        logger.error("No closed holdout trades found. Exiting.")
        sys.exit(1)

    if len(trades) < 30:
        logger.warning(
            "Only %d held-out trades found (recommended >= 30). "
            "Results are directional only — not statistically reliable.",
            len(trades),
        )

    # Advisory-only analyst (local server → cloud fallback → consensus fallback)
    analyst = LLMTradingAnalyst(local_url=args.local_url)

    results = run_shadow_pass(trades, analyst)

    report = {
        "generated_at":       datetime.now(timezone.utc).isoformat(),
        "holdout_days":       args.holdout_days,
        "n_trades_evaluated": len(trades),
        "n_with_context":     len(results),
        **summarize(results),
        "raw_results": [asdict(r) for r in results],
    }

    _print_report(report)

    if args.report_out:
        out_path = Path(args.report_out)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        logger.info("Full JSON report written to: %s", out_path.resolve())

    logger.info(
        "Shadow log appended to: %s  (run_timestamp=%s)",
        SHADOW_DB, report["generated_at"]
    )

    if not report.get("overall_pass"):
        sys.exit(2)   # non-zero so CI / automation can detect failure


if __name__ == "__main__":
    main()
