"""
AEGIS GOLD AI — Segmented Profit Factor Analysis
==================================================
Purpose: verify whether today's changes (consensus threshold 65%->38%,
LLM Analyst veto bypass, neutral-bias gate removal) helped or hurt PF,
by re-running the confidence-bucket / session breakdown.
"""

import argparse
import sqlite3
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# COLUMN MAP — Mapped to performance.db schema
# ---------------------------------------------------------------------------
COL_PNL = "profit_usd"           # realized profit/loss in $ (negative = loss)
COL_CONFIDENCE = "ai_confidence" # decision confidence, 0-100 or 0-1
COL_SESSION = "session"          # e.g. "ASIAN", "OVERLAP", "LONDON", "NY"
COL_TIMESTAMP = "timestamp"      # ISO timestamp trade was closed
COL_SYMBOL = "symbol"
COL_DIRECTION = "direction"      # "BUY" / "SELL"

CONFIDENCE_BUCKETS = [
    (0, 50), (50, 55), (55, 60), (60, 65), (65, 70), (70, 75), (75, 100)
]


def profit_factor(pnls):
    gains = sum(p for p in pnls if p > 0)
    losses = abs(sum(p for p in pnls if p < 0))
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / losses


def win_rate(pnls):
    if not pnls:
        return 0.0
    wins = sum(1 for p in pnls if p > 0)
    return 100.0 * wins / len(pnls)


def normalize_confidence(val):
    """Handle both 0-1 and 0-100 confidence scales."""
    if val is None:
        return None
    v = float(val)
    return v * 100 if v <= 1.0 else v


def fetch_trades(db_path, table):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cols = [COL_PNL, COL_CONFIDENCE, COL_SESSION, COL_TIMESTAMP,
                COL_SYMBOL, COL_DIRECTION]
        query = f"SELECT {', '.join(cols)} FROM {table} WHERE {COL_PNL} IS NOT NULL"
        rows = conn.execute(query).fetchall()
    except sqlite3.OperationalError as e:
        print(f"Query failed: {e}")
        print("Check COLUMN MAP at the top of this script against your actual schema.")
        sys.exit(1)
    finally:
        conn.close()
    return rows


def bucket_report(rows, label):
    print(f"\n{'=' * 70}")
    print(f"{label}  (n={len(rows)})")
    print(f"{'=' * 70}")
    if not rows:
        print("  no trades in this segment")
        return

    all_pnls = [r[COL_PNL] for r in rows]
    print(f"  Overall: PF={profit_factor(all_pnls):.3f}  "
          f"WinRate={win_rate(all_pnls):.2f}%  "
          f"NetPnL=${sum(all_pnls):.2f}")

    # by confidence bucket
    print("\n  By confidence bucket:")
    buckets = defaultdict(list)
    for r in rows:
        c = normalize_confidence(r[COL_CONFIDENCE])
        if c is None:
            continue
        for lo, hi in CONFIDENCE_BUCKETS:
            if lo <= c < hi:
                buckets[(lo, hi)].append(r[COL_PNL])
                break
    total_loss = sum(abs(p) for p in all_pnls if p < 0)
    for lo, hi in CONFIDENCE_BUCKETS:
        pnls = buckets.get((lo, hi), [])
        if not pnls:
            continue
        pf = profit_factor(pnls)
        wr = win_rate(pnls)
        seg_loss = abs(sum(p for p in pnls if p < 0))
        pct_of_total_loss = (100 * seg_loss / total_loss) if total_loss else 0
        print(f"    {lo:3d}-{hi:3d}%: n={len(pnls):4d}  PF={pf:6.3f}  "
              f"WinRate={wr:5.2f}%  NetPnL=${sum(pnls):8.2f}  "
              f"% of total losses={pct_of_total_loss:5.1f}%")

    # by session
    print("\n  By session:")
    sessions = defaultdict(list)
    for r in rows:
        s = r[COL_SESSION] or "UNKNOWN"
        sessions[s].append(r[COL_PNL])
    for s, pnls in sorted(sessions.items(), key=lambda kv: -len(kv[1])):
        print(f"    {s:10s}: n={len(pnls):4d}  PF={profit_factor(pnls):6.3f}  "
              f"WinRate={win_rate(pnls):5.2f}%  NetPnL=${sum(pnls):8.2f}")

    # by direction
    print("\n  By direction:")
    directions = defaultdict(list)
    for r in rows:
        d = r[COL_DIRECTION] or "UNKNOWN"
        directions[d].append(r[COL_PNL])
    for d, pnls in sorted(directions.items(), key=lambda kv: -len(kv[1])):
        print(f"    {d:6s}: n={len(pnls):4d}  PF={profit_factor(pnls):6.3f}  "
              f"WinRate={win_rate(pnls):5.2f}%  NetPnL=${sum(pnls):8.2f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True, help="Path to trades sqlite db")
    ap.add_argument("--table", default="trades", help="Trades table name")
    ap.add_argument("--cutoff", default=None,
                     help="ISO timestamp splitting pre/post today's changes, "
                          "e.g. '2026-08-05T00:00:00'. If omitted, only overall "
                          "report is shown.")
    args = ap.parse_args()

    rows = fetch_trades(args.db, args.table)
    bucket_report(rows, "ALL TRADES")

    if args.cutoff:
        pre = [r for r in rows if str(r[COL_TIMESTAMP]) < args.cutoff]
        post = [r for r in rows if str(r[COL_TIMESTAMP]) >= args.cutoff]
        bucket_report(pre, f"BEFORE {args.cutoff} (pre-change baseline)")
        bucket_report(post, f"AFTER {args.cutoff} (post-change: 38% threshold, "
                             f"LLM veto bypass, bidirectional scan)")

        print(f"\n{'=' * 70}")
        print("COMPARISON")
        print(f"{'=' * 70}")
        pre_pf = profit_factor([r[COL_PNL] for r in pre]) if pre else 0
        post_pf = profit_factor([r[COL_PNL] for r in post]) if post else 0
        print(f"  Pre-change PF:  {pre_pf:.3f}")
        print(f"  Post-change PF: {post_pf:.3f}")
        if post and pre and post_pf < pre_pf:
            print("  >>> WARNING: post-change PF is LOWER. The threshold/veto-bypass "
                  "changes may be diluting quality — consider reverting on live.")
        elif post and pre and post_pf >= pre_pf:
            print("  Post-change PF held or improved — but check sample size (n) "
                  "above before trusting this on small post-change n.")


if __name__ == "__main__":
    main()
