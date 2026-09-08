"""
Segment the shadow validation results from shadow_validation.db to answer:
"Does the 68.3% win-rate-of-rejected trades cluster in one regime/session/spread bucket?"

If it does, we can add a regime-conditional threshold to the fallback consensus
instead of doing a full retrain.

Usage:
    python scratch/segment_shadow_results.py
"""

import json
import sqlite3
from pathlib import Path

SHADOW_DB = Path(__file__).parent.parent / "data" / "shadow_validation.db"
PERF_DB   = Path(__file__).parent.parent / "data" / "performance.db"

ATTR_DB   = Path(__file__).parent.parent / "data" / "attribution.db"

def load_joined():
    """
    Join shadow results with:
      - performance.db  → adx_at_entry (used as spread proxy), regime, session
      - attribution.db  → session, regime fallback (has trade_id FK)
    """
    conn_s = sqlite3.connect(str(SHADOW_DB))
    conn_s.row_factory = sqlite3.Row
    shadow_rows = conn_s.execute(
        "SELECT * FROM shadow_results ORDER BY id ASC"
    ).fetchall()
    conn_s.close()

    conn_p = sqlite3.connect(str(PERF_DB))
    conn_p.row_factory = sqlite3.Row

    # Build attr lookup by trade_id for session/regime (often richer than perf.db)
    attr_by_id = {}
    if ATTR_DB.exists():
        conn_a = sqlite3.connect(str(ATTR_DB))
        conn_a.row_factory = sqlite3.Row
        attr_rows = conn_a.execute(
            "SELECT trade_id, session, regime FROM attributions"
        ).fetchall()
        conn_a.close()
        for ar in attr_rows:
            attr_by_id[str(ar["trade_id"])] = dict(ar)

    joined = []
    for sr in shadow_rows:
        perf = conn_p.execute(
            "SELECT session, regime, adx_at_entry FROM trades WHERE id = ?",
            (sr["trade_id"],)
        ).fetchone()

        attr = attr_by_id.get(str(sr["trade_id"]), {})

        session = (
            (perf["session"] if perf and perf["session"] else None)
            or attr.get("session")
            or "UNKNOWN"
        )
        regime = (
            (perf["regime"] if perf and perf["regime"] else None)
            or attr.get("regime")
            or "UNKNOWN"
        )
        adx = float(perf["adx_at_entry"] if perf and perf["adx_at_entry"] else 0.0)

        # ADX bucket — proxy for trend strength at entry
        adx_bucket = (
            "weak_trend  (ADX<20)"  if adx < 20 else
            "medium_trend(ADX20-30)" if adx < 30 else
            "strong_trend(ADX>30)"
        )

        joined.append({
            "trade_id":   sr["trade_id"],
            "verdict":    sr["verdict_recommendation"],
            "win_loss":   int(sr["actual_win_loss"] or 0),
            "pnl":        float(sr["actual_pnl_usd"] or 0.0),
            "session":    session,
            "regime":     regime,
            "adx":        adx,
            "adx_bucket": adx_bucket,
        })

    conn_p.close()
    return joined


def segment(rows, key):
    buckets = {}
    for r in rows:
        k = r[key]
        buckets.setdefault(k, []).append(r)

    print(f"\n  By {key}:")
    print(f"  {'Bucket':<25} {'N':>5} {'Win%':>7}  (rejected only)")
    print("  " + "-" * 42)

    by_winrate = []
    for k, group in buckets.items():
        n = len(group)
        wins = sum(1 for r in group if r["win_loss"] == 1)
        wr = wins / n if n else 0.0
        by_winrate.append((k, n, wr))

    for k, n, wr in sorted(by_winrate, key=lambda x: -x[2]):
        bar = "#" * int(wr * 20)
        print(f"  {k:<25} {n:>5}  {wr*100:>5.1f}%  {bar}")


def main():
    if not SHADOW_DB.exists():
        print(f"ERROR: {SHADOW_DB} not found. Run shadow_validate_analyst.py first.")
        return

    rows = load_joined()
    rejected = [r for r in rows if r["verdict"] == "reject"]

    print(f"\n{'='*55}")
    print(f"  SHADOW VALIDATION — REJECTION SEGMENTATION")
    print(f"  Total rows in shadow log : {len(rows)}")
    print(f"  Rejected trades          : {len(rejected)}")
    overall_wr = sum(1 for r in rejected if r["win_loss"] == 1) / len(rejected) if rejected else 0
    print(f"  Overall reject win-rate  : {overall_wr*100:.1f}%")
    print(f"{'='*55}")

    if not rejected:
        print("No rejected trades found.")
        return

    segment(rejected, "session")
    segment(rejected, "regime")
    segment(rejected, "adx_bucket")

    # Summary verdict
    print(f"\n{'='*55}")
    print("  INTERPRETATION GUIDE")
    print("  If one bucket has win-rate > 65% and n > 20:")
    print("  -> Add a regime/session exception to _consensus_fallback")
    print("     (cheaper than retraining).")
    print("  If win-rate is uniformly high across all buckets:")
    print("  -> The fallback is globally too conservative.")
    print("     Retrain the local model to fix calibration.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
