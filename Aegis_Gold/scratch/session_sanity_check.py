"""
Session Sanity-Check Script — Trade Logging Quality Monitor
============================================================
Run after each trading session (or daily via scheduler) to flag any trade row
with logging gaps that would block future replay or analysis.

Flags:
  - NULL sl_was_hit or tp_was_hit
  - atr == 0.0 or NULL
  - Duplicate exit_time across many rows (mass-close signal)
  - NULL exit_time on trades that have a profit_usd (closed but not recorded)
  - NULL entry_time
  - Trades with sl_points == 0 (cannot replay even with bars)

Exit codes:
  0 = all checks pass (clean session)
  1 = warnings found (print summary, do not abort)
"""

import sys
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
TRADE_MEMORY_DB = DATA_DIR / "trade_memory.db"

print("=" * 70)
print(f"SESSION SANITY CHECK -- {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
print(f"Database: {TRADE_MEMORY_DB}")
print("=" * 70)

conn = sqlite3.connect(TRADE_MEMORY_DB)
df = pd.read_sql_query(
    "SELECT trade_id, symbol, entry_time, exit_time, profit_usd, "
    "sl_was_hit, tp_was_hit, atr, sl_points, exit_reason "
    "FROM trades",
    conn
)
conn.close()

warnings = []
total = len(df)
closed = df[df["profit_usd"].notna()]

print(f"\nTotal rows: {total} | Closed (profit_usd set): {len(closed)}")

# --- CHECK 1: sl_was_hit / tp_was_hit NULL on closed trades ---
null_hit_flags = closed[closed["sl_was_hit"].isna() | closed["tp_was_hit"].isna()]
if len(null_hit_flags) > 0:
    warnings.append(
        f"CHECK 1 FAIL: {len(null_hit_flags)} closed trades have NULL sl_was_hit or tp_was_hit.\n"
        f"  These trades cannot be classified by exit type. Fix: ensure log_trade_close() "
        f"always sets tp_was_hit/sl_was_hit.\n"
        f"  Oldest offending trade: {null_hit_flags['entry_time'].min()}\n"
        f"  Most recent offending trade: {null_hit_flags['entry_time'].max()}"
    )
else:
    print("  CHECK 1 PASS: All closed trades have sl_was_hit/tp_was_hit set.")

# --- CHECK 2: atr == 0 or NULL on closed trades ---
zero_atr = closed[(closed["atr"].isna()) | (closed["atr"] == 0.0)]
if len(zero_atr) > 0:
    # Separate historical (pre-fix) from new trades by checking recent entry_times
    try:
        zero_atr_times = pd.to_datetime(zero_atr["entry_time"], utc=True, errors="coerce")
        fix_timestamp = pd.Timestamp("2026-07-28 02:00:00", tz="UTC")  # When this fix deployed
        new_zero_atr = zero_atr[zero_atr_times >= fix_timestamp]
        old_zero_atr = zero_atr[zero_atr_times < fix_timestamp]
        if len(new_zero_atr) > 0:
            warnings.append(
                f"CHECK 2 FAIL: {len(new_zero_atr)} NEW trades (after fix deployment) have atr=0.\n"
                f"  This indicates the fix is not propagating ATR to log_trade_open().\n"
                f"  Affected trade_ids: {list(new_zero_atr['trade_id'].head(5))}"
            )
        else:
            print(f"  CHECK 2 PASS (new trades): No new trades have atr=0.")
            print(f"  CHECK 2 NOTE: {len(old_zero_atr)} historical trades (pre-fix) have atr=0. "
                  f"This is expected and cannot be backfilled.")
    except Exception:
        warnings.append(
            f"CHECK 2 WARN: {len(zero_atr)} closed trades have atr=0 or NULL. "
            f"Cannot separate pre/post-fix without parseable entry_time."
        )
else:
    print("  CHECK 2 PASS: No closed trades have atr=0 or NULL.")

# --- CHECK 3: Duplicate exit_time across many rows (mass-close indicator) ---
exit_times = closed["exit_time"].dropna()
if len(exit_times) > 0:
    exit_time_counts = exit_times.value_counts()
    # Suspicious if a single timestamp appears for >5 trades (mass close / bot restart)
    mass_closes = exit_time_counts[exit_time_counts > 5]
    if len(mass_closes) > 0:
        warnings.append(
            f"CHECK 3 WARN: {len(mass_closes)} exit_time value(s) appear on >5 trades "
            f"(potential mass-close event):\n"
            + "\n".join(f"    '{ts}': {cnt} trades" for ts, cnt in mass_closes.head(5).items())
            + f"\n  These trades have no reliable per-trade exit timing. "
              f"Their SL/TP hit order cannot be determined even with bar data."
        )
    else:
        print("  CHECK 3 PASS: No suspicious duplicate exit_times found.")

# --- CHECK 4: Closed trades with NULL exit_time ---
no_exit_time = closed[closed["exit_time"].isna()]
if len(no_exit_time) > 0:
    warnings.append(
        f"CHECK 4 FAIL: {len(no_exit_time)} trades have profit_usd set but NULL exit_time.\n"
        f"  These are closed but their exit was not fully logged.\n"
        f"  trade_ids: {list(no_exit_time['trade_id'].head(10))}"
    )
else:
    print("  CHECK 4 PASS: All closed trades have exit_time set.")

# --- CHECK 5: sl_points == 0 on closed trades ---
zero_sl = closed[closed["sl_points"] == 0]
if len(zero_sl) > 0:
    warnings.append(
        f"CHECK 5 WARN: {len(zero_sl)} closed trades have sl_points=0.\n"
        f"  ATR-scaled SL replay requires a non-zero SL. These trades are unrepayable.\n"
        f"  Fraction: {len(zero_sl)/len(closed)*100:.1f}% of closed trades."
    )
else:
    print("  CHECK 5 PASS: All closed trades have sl_points > 0.")

# --- CHECK 6: NULL entry_time ---
null_entry = df[df["entry_time"].isna()]
if len(null_entry) > 0:
    warnings.append(
        f"CHECK 6 FAIL: {len(null_entry)} trades have NULL entry_time.\n"
        f"  trade_ids: {list(null_entry['trade_id'].head(10))}"
    )
else:
    print("  CHECK 6 PASS: All trades have entry_time set.")

# --- Summary ---
print(f"\n{'=' * 70}")
if warnings:
    print(f"RESULT: {len(warnings)} WARNING(S) FOUND\n")
    for i, w in enumerate(warnings, 1):
        print(f"[WARNING {i}] {w}\n")
    sys.exit(1)
else:
    print("RESULT: ALL CHECKS PASS. Logging is clean.")
    sys.exit(0)
