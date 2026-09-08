"""
BLOCKER A: Reconcile performance.db vs trade_memory.db
=======================================================
1. Schema and row counts for both DBs
2. Symbol/time-range breakdown for each
3. Overlap analysis — match on entry_price + timestamp proximity
4. Determine which DB is authoritative
"""
import sqlite3
import os
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = r"d:\Trading\Aegis_Gold\data"
PERF_DB  = os.path.join(BASE_DIR, "performance.db")
TM_DB    = os.path.join(BASE_DIR, "trade_memory.db")

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)

print("=" * 70)
print("BLOCKER A: DB RECONCILIATION")
print("=" * 70)

# ── 1. Row counts and time ranges ────────────────────────────────────────────
print("\n--- 1. Row counts and time windows ---")

conn_p = sqlite3.connect(PERF_DB)
df_p = pd.read_sql_query(
    "SELECT id, symbol, direction, entry_price, lot, profit_usd, profit_pips, "
    "win_loss, session, timestamp "
    "FROM trades WHERE profit_usd != 0 ORDER BY timestamp",
    conn_p
)
conn_p.close()

conn_t = sqlite3.connect(TM_DB)
df_t = pd.read_sql_query(
    "SELECT trade_id, symbol, direction, entry_price, exit_price, lot_size, "
    "profit_usd, exit_reason, sl_points, entry_time, exit_time, signal_source "
    "FROM trades WHERE profit_usd != 0 ORDER BY entry_time",
    conn_t
)
conn_t.close()

print(f"\nperformance.db : {len(df_p)} closed trades")
print(f"  Symbols     : {df_p['symbol'].value_counts().to_dict()}")
print(f"  Time range  : {df_p['timestamp'].min()} -> {df_p['timestamp'].max()}")
print(f"  Win rate    : {(df_p['profit_usd']>0).mean()*100:.2f}%")
gp = df_p[df_p['profit_usd']>0]['profit_usd'].sum()
gl = abs(df_p[df_p['profit_usd']<0]['profit_usd'].sum())
print(f"  PF          : {gp/gl:.3f}  (GP={gp:.2f} GL={gl:.2f})")

print(f"\ntrade_memory.db: {len(df_t)} closed trades")
print(f"  Symbols     : {df_t['symbol'].value_counts().to_dict()}")
print(f"  Time range  : {df_t['entry_time'].min()} -> {df_t['entry_time'].max()}")
print(f"  Win rate    : {(df_t['profit_usd']>0).mean()*100:.2f}%")
gp2 = df_t[df_t['profit_usd']>0]['profit_usd'].sum()
gl2 = abs(df_t[df_t['profit_usd']<0]['profit_usd'].sum())
print(f"  PF          : {gp2/gl2:.3f}  (GP={gp2:.2f} GL={gl2:.2f})")
print(f"  signal_source breakdown: {df_t['signal_source'].value_counts().to_dict()}")

# ── 2. Symbol breakdown ──────────────────────────────────────────────────────
print("\n--- 2. Symbol breakdown by DB ---")
print("\nperformance.db by symbol:")
for sym, grp in df_p.groupby('symbol'):
    gp_s = grp[grp['profit_usd']>0]['profit_usd'].sum()
    gl_s = abs(grp[grp['profit_usd']<0]['profit_usd'].sum())
    pf_s = gp_s/gl_s if gl_s>0 else float('inf')
    wr_s = (grp['profit_usd']>0).mean()*100
    print(f"  {sym:12s}: {len(grp):5d} trades | WR={wr_s:.1f}% | PF={pf_s:.3f} | Net=${gp_s-gl_s:.2f}")

print("\ntrade_memory.db by symbol:")
for sym, grp in df_t.groupby('symbol'):
    gp_s = grp[grp['profit_usd']>0]['profit_usd'].sum()
    gl_s = abs(grp[grp['profit_usd']<0]['profit_usd'].sum())
    pf_s = gp_s/gl_s if gl_s>0 else float('inf')
    wr_s = (grp['profit_usd']>0).mean()*100
    print(f"  {sym:12s}: {len(grp):5d} trades | WR={wr_s:.1f}% | PF={pf_s:.3f} | Net=${gp_s-gl_s:.2f}")

# ── 3. Match trades between DBs ──────────────────────────────────────────────
print("\n--- 3. Trade matching (entry_price + approx timestamp) ---")

# Normalize entry times in performance.db
df_p['ts_parsed'] = pd.to_datetime(df_p['timestamp'], errors='coerce')
df_t['ts_parsed'] = pd.to_datetime(df_t['entry_time'], errors='coerce')

# Round prices to 2 decimals for matching
df_p['ep_round'] = df_p['entry_price'].round(2)
df_t['ep_round'] = df_t['entry_price'].round(2)
df_p['pnl_round'] = df_p['profit_usd'].round(3)
df_t['pnl_round'] = df_t['profit_usd'].round(3)

# Match on entry_price + profit_usd (rounded) — most reliable without ticket ID
merged = pd.merge(
    df_p[['id','symbol','ep_round','pnl_round','ts_parsed','lot']],
    df_t[['trade_id','symbol','ep_round','pnl_round','ts_parsed','lot_size','sl_points','exit_reason']],
    on=['symbol','ep_round','pnl_round'],
    how='inner',
    suffixes=('_p','_t')
)
# Remove duplicate matches
merged = merged.drop_duplicates(subset=['id'])
merged_t = merged.drop_duplicates(subset=['trade_id'])

print(f"\nMatched {len(merged)} perf.db rows to trade_memory rows (on symbol+entry_price+pnl)")
print(f"  perf.db trades with a match    : {merged['id'].nunique()} / {len(df_p)} ({merged['id'].nunique()/len(df_p)*100:.1f}%)")
print(f"  trade_memory trades with a match: {merged['trade_id'].nunique()} / {len(df_t)} ({merged['trade_id'].nunique()/len(df_t)*100:.1f}%)")

# ── 4. Check if perf.db is subset of trade_memory or separate ───────────────
print("\n--- 4. Time-window overlap ---")
perf_min = df_p['ts_parsed'].dropna().min()
perf_max = df_p['ts_parsed'].dropna().max()
tm_min   = df_t['ts_parsed'].dropna().min()
tm_max   = df_t['ts_parsed'].dropna().max()
print(f"performance.db: {perf_min} -> {perf_max}")
print(f"trade_memory:   {tm_min} -> {tm_max}")

overlap_start = max(perf_min, tm_min)
overlap_end   = min(perf_max, tm_max)
print(f"Overlap window: {overlap_start} -> {overlap_end}")

# Count trades in overlap window in each DB
perf_in_overlap = df_p[(df_p['ts_parsed']>=overlap_start) & (df_p['ts_parsed']<=overlap_end)]
tm_in_overlap   = df_t[(df_t['ts_parsed']>=overlap_start) & (df_t['ts_parsed']<=overlap_end)]
print(f"Trades in overlap: perf.db={len(perf_in_overlap)} | trade_memory={len(tm_in_overlap)}")

# ── 5. Check for ticket ID / trade_id in performance.db ─────────────────────
print("\n--- 5. ID field check ---")
conn_p = sqlite3.connect(PERF_DB)
cur = conn_p.cursor()
cur.execute("PRAGMA table_info(trades);")
perf_cols = [r[1] for r in cur.fetchall()]
conn_p.close()
print(f"performance.db columns: {perf_cols}")

# check if 'lot' values match between DBs in the matched set
print(f"\nLot size comparison in matched trades (sample 10):")
print(merged[['id','trade_id','ep_round','pnl_round','lot','lot_size']].head(10).to_string())

# ── 6. Which DB has the 2,760 trades from the original diagnosis? ─────────────
print("\n--- 6. Original diagnosis: 2,760 trades, 60.33% WR, PF 0.63 ---")
print(f"\nperformance.db: {len(df_p)} trades | WR={((df_p['profit_usd']>0).mean()*100):.2f}%")
print(f"trade_memory.db: {len(df_t)} trades | WR={((df_t['profit_usd']>0).mean()*100):.2f}%")

# Check perf.db without any filter
conn_p = sqlite3.connect(PERF_DB)
all_p = pd.read_sql_query("SELECT COUNT(*) as n, SUM(CASE WHEN profit_usd>0 THEN 1 ELSE 0 END)*1.0/COUNT(*) as wr FROM trades WHERE profit_usd IS NOT NULL AND profit_usd != 0", conn_p)
conn_p.close()
print(f"\nperformance.db raw count+WR: {all_p.to_string()}")

conn_t = sqlite3.connect(TM_DB)
all_t = pd.read_sql_query("SELECT COUNT(*) as n, SUM(CASE WHEN profit_usd>0 THEN 1 ELSE 0 END)*1.0/COUNT(*) as wr FROM trades WHERE profit_usd IS NOT NULL AND profit_usd != 0", conn_t)
conn_t.close()
print(f"trade_memory.db raw count+WR: {all_t.to_string()}")
