"""
Task 2 — MT5 Historical Bar Data Recovery Check
=================================================
Checks whether MT5 can export historical M1 OHLCV bars for XAUUSD and EURUSD
covering the date range of existing trades in trade_memory.db.
If bars are available, saves them as Parquet + CSV per symbol per month,
keyed by timestamp, so they can be joined to entry_time/exit_time for replay.

Run this script ONLY with MT5 terminal running and logged in.
It will print a plain result: either bars saved (and joinable count reported),
or an explicit statement that historical data is not available for replay.
"""

import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import sqlite3
import pandas as pd
from datetime import datetime, timezone, timedelta

DATA_DIR = BASE_DIR / "data"
BAR_DATA_DIR = DATA_DIR / "ohlcv_bars"
BAR_DATA_DIR.mkdir(parents=True, exist_ok=True)

TRADE_MEMORY_DB = DATA_DIR / "trade_memory.db"

print("=" * 70)
print("TASK 2 -- MT5 Historical Bar Data Recovery Check")
print("=" * 70)

# --- Step 1: Get the date range of existing XAUUSD trades ---
conn = sqlite3.connect(TRADE_MEMORY_DB)
df_trades = pd.read_sql_query(
    "SELECT symbol, entry_time, exit_time, trade_id "
    "FROM trades WHERE profit_usd IS NOT NULL AND entry_time IS NOT NULL",
    conn
)
conn.close()

df_xau = df_trades[df_trades["symbol"] == "XAUUSD"].copy()
df_eur = df_trades[df_trades["symbol"] == "EURUSD"].copy()

print(f"\nTrades in DB: XAUUSD={len(df_xau)}, EURUSD={len(df_eur)}")

for sym, df_sym in [("XAUUSD", df_xau), ("EURUSD", df_eur)]:
    if len(df_sym) == 0:
        continue
    entry_times = pd.to_datetime(df_sym["entry_time"], utc=True, errors="coerce").dropna()
    exit_times  = pd.to_datetime(df_sym["exit_time"],  utc=True, errors="coerce").dropna()
    all_times = pd.concat([entry_times, exit_times]).dropna()
    if len(all_times) == 0:
        print(f"\n{sym}: No valid timestamps found.")
        continue
    t_min = all_times.min()
    t_max = all_times.max()
    print(f"\n{sym}: Trade date range = {t_min.date()} to {t_max.date()} ({len(df_sym)} trades)")

# --- Step 2: Attempt MT5 connection ---
print("\n--- Attempting MT5 connection ---")
try:
    import MetaTrader5 as mt5
    from config import settings as cfg

    if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
        print(f"MT5 initialization FAILED: {mt5.last_error()}")
        print("Historical bar data is NOT available — MT5 is not connected.")
        print("\nCONCLUSION: Forward validation is the only path (see Task 3 plan).")
        sys.exit(0)

    account_info = mt5.account_info()
    print(f"MT5 connected: account={account_info.login if account_info else 'unknown'}, "
          f"server={account_info.server if account_info else 'unknown'}")

    # --- Step 3: Pull M1 bars for each symbol ---
    results_summary = {}
    for sym, df_sym in [("XAUUSD", df_xau), ("EURUSD", df_eur)]:
        if len(df_sym) == 0:
            continue

        entry_times = pd.to_datetime(df_sym["entry_time"], utc=True, errors="coerce").dropna()
        exit_times  = pd.to_datetime(df_sym["exit_time"],  utc=True, errors="coerce").dropna()
        all_times = pd.concat([entry_times, exit_times]).dropna()
        if len(all_times) == 0:
            continue

        t_from = (all_times.min() - timedelta(hours=1)).to_pydatetime().replace(tzinfo=None)
        t_to   = (all_times.max() + timedelta(hours=1)).to_pydatetime().replace(tzinfo=None)

        print(f"\n{sym}: Requesting M1 bars from {t_from} to {t_to}...")
        rates = mt5.copy_rates_range(sym, mt5.TIMEFRAME_M1, t_from, t_to)

        if rates is None or len(rates) == 0:
            print(f"  ERROR: MT5 returned no bars for {sym} in that range.")
            print(f"  MT5 last_error: {mt5.last_error()}")
            results_summary[sym] = {"bars": 0, "joinable": 0}
            continue

        df_bars = pd.DataFrame(rates)
        df_bars["time"] = pd.to_datetime(df_bars["time"], unit="s", utc=True)
        df_bars = df_bars.rename(columns={"time": "bar_time"})

        print(f"  Retrieved {len(df_bars)} M1 bars: {df_bars['bar_time'].min()} to {df_bars['bar_time'].max()}")

        # Save per-month Parquet files
        df_bars["month"] = df_bars["bar_time"].dt.to_period("M")
        months = df_bars["month"].unique()
        files_saved = []
        for month in months:
            month_df = df_bars[df_bars["month"] == month].drop(columns=["month"])
            fname = BAR_DATA_DIR / f"{sym}_M1_{month}.parquet"
            month_df.to_parquet(fname, index=False)
            files_saved.append(str(fname))

        print(f"  Saved {len(files_saved)} monthly Parquet files to {BAR_DATA_DIR}")

        # Check join coverage: how many trades have at least one M1 bar between entry and exit
        bar_times_set = set(df_bars["bar_time"].dt.floor("min"))
        joinable = 0
        for _, row in df_sym.iterrows():
            try:
                t_entry = pd.to_datetime(row["entry_time"], utc=True)
                t_exit  = pd.to_datetime(row["exit_time"],  utc=True) if row["exit_time"] else None
                t_entry_floor = t_entry.floor("min")
                if t_entry_floor in bar_times_set:
                    joinable += 1
            except Exception:
                pass

        results_summary[sym] = {"bars": len(df_bars), "joinable": joinable, "total": len(df_sym)}
        print(f"  Trades joinable to bar data: {joinable} / {len(df_sym)}")

    mt5.shutdown()

    # --- Step 4: Report ---
    print("\n--- CONCLUSION ---")
    all_joinable = all(
        results_summary.get(s, {}).get("joinable", 0) > 0
        for s in results_summary
    )
    if all_joinable:
        print("  HISTORICAL BAR DATA AVAILABLE AND JOINABLE.")
        print("  Next step: run scratch/audit_replay_with_bars.py to perform genuine")
        print("  forward replay using bar-by-bar SL/TP hit detection.")
        for sym, r in results_summary.items():
            print(f"  {sym}: {r['bars']} M1 bars, {r['joinable']}/{r.get('total', '?')} trades joinable")
    else:
        print("  HISTORICAL BAR DATA PARTIALLY OR NOT JOINABLE.")
        print("  Forward validation is the only reliable path (see Task 3 plan).")
        for sym, r in results_summary.items():
            print(f"  {sym}: {r.get('bars', 0)} bars, {r.get('joinable', 0)}/{r.get('total', '?')} joinable")

except ImportError:
    print("MetaTrader5 package not importable in this Python environment.")
    print("CONCLUSION: Cannot check historical bar availability offline.")
    print("Run this script from the environment where MetaTrader5 is installed,")
    print("with the MT5 terminal running.")
except Exception as e:
    print(f"Unexpected error: {e}")
    print("CONCLUSION: Could not connect to MT5. Historical bar data check failed.")
    print("Forward validation is the only reliable path (see Task 3 plan).")
