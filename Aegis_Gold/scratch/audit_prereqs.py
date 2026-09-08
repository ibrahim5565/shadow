"""
Pre-implementation audit queries:
1. Check if MFE/MAE columns exist in trade DBs
2. Check sl_points coverage (real vs default)
3. Check spread data in trade history
"""
import sqlite3
import os
import pandas as pd
import numpy as np

base_dir = r"d:\Trading\Aegis_Gold\data"

print("=" * 70)
print("AUDIT 1: MFE/MAE column presence in trade DBs")
print("=" * 70)

for db_name in ["performance.db", "trade_memory.db"]:
    db_path = os.path.join(base_dir, db_name)
    if not os.path.exists(db_path):
        print(f"  {db_name}: NOT FOUND")
        continue
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cur.fetchall()]
    for tname in tables:
        if tname in ("sqlite_sequence",):
            continue
        cur.execute(f"PRAGMA table_info({tname});")
        cols = [row[1] for row in cur.fetchall()]
        mfe_cols = [c for c in cols if any(k in c.lower() for k in ["mfe", "mae", "max_fav", "max_adv", "max_profit", "max_drawdown"])]
        print(f"\n  [{db_name}] Table '{tname}':")
        print(f"    All columns: {cols}")
        print(f"    MFE/MAE related: {mfe_cols if mfe_cols else 'NONE'}")
    conn.close()

print()
print("=" * 70)
print("AUDIT 2: sl_points coverage in trade_memory.db")
print("=" * 70)

db_path = os.path.join(base_dir, "trade_memory.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT profit_usd, sl_points, tp_points, atr, lot_size FROM trades WHERE profit_usd IS NOT NULL AND profit_usd != 0", conn)
    conn.close()

    total = len(df)
    sl_zero = (df['sl_points'].isna() | (df['sl_points'] == 0)).sum()
    sl_positive = (df['sl_points'] > 0).sum()
    sl_negative = (df['sl_points'] < 0).sum()

    print(f"  Total closed trades (non-zero profit): {total}")
    print(f"  sl_points = 0 or NULL: {sl_zero} ({sl_zero/total*100:.1f}%)")
    print(f"  sl_points > 0 (real): {sl_positive} ({sl_positive/total*100:.1f}%)")
    print(f"  sl_points < 0 (anomaly): {sl_negative}")
    if sl_positive > 0:
        print(f"  Avg sl_points (when > 0): {df[df['sl_points'] > 0]['sl_points'].mean():.1f}")
        print(f"  Median sl_points (when > 0): {df[df['sl_points'] > 0]['sl_points'].median():.1f}")

    print()
    print("  ATR at entry coverage:")
    atr_zero = (df['atr'].isna() | (df['atr'] == 0)).sum()
    atr_positive = (df['atr'] > 0).sum()
    print(f"  atr = 0 or NULL: {atr_zero} ({atr_zero/total*100:.1f}%)")
    print(f"  atr > 0 (usable for backfill): {atr_positive} ({atr_positive/total*100:.1f}%)")
    if atr_positive > 0:
        # atr is in price terms, need to convert to pts for XAUUSD (point=0.01)
        atr_pts = df[df['atr'] > 0]['atr'] / 0.01
        print(f"  Avg ATR in pts (XAUUSD, point=0.01): {atr_pts.mean():.1f}")
        print(f"  Median ATR in pts: {atr_pts.median():.1f}")
        print(f"  ATR pts distribution: p25={atr_pts.quantile(0.25):.1f} p50={atr_pts.median():.1f} p75={atr_pts.quantile(0.75):.1f} p90={atr_pts.quantile(0.90):.1f}")

print()
print("=" * 70)
print("AUDIT 3: Spread data in trade_memory.db")
print("=" * 70)
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    df_spread = pd.read_sql_query("SELECT spread, symbol FROM trades WHERE spread IS NOT NULL AND spread > 0", conn)
    conn.close()
    if len(df_spread) > 0:
        xau = df_spread[df_spread['symbol'].str.contains('XAU', na=False)]
        print(f"  Rows with spread > 0: {len(df_spread)}")
        print(f"  XAUUSD rows: {len(xau)}")
        if len(xau) > 0:
            # spread in points (XAUUSD point = 0.01, so spread in price / 0.01)
            # Check if spread looks like it's already in pts or in price
            print(f"  Raw spread values (sample): {xau['spread'].head(10).tolist()}")
            print(f"  Spread stats: min={xau['spread'].min():.4f} max={xau['spread'].max():.4f} mean={xau['spread'].mean():.4f} median={xau['spread'].median():.4f}")
            # If spread < 10, likely in price units; convert to pts
            if xau['spread'].median() < 10:
                spread_pts = xau['spread'] / 0.01
                print(f"  Spread in pts (÷0.01): min={spread_pts.min():.1f} max={spread_pts.max():.1f} mean={spread_pts.mean():.1f} median={spread_pts.median():.1f}")
                print(f"  p90 spread pts: {spread_pts.quantile(0.90):.1f}")
                print(f"  p99 spread pts (news widening): {spread_pts.quantile(0.99):.1f}")
    else:
        print("  No spread data found")

print()
print("=" * 70)
print("AUDIT 4: performance.db - check sl, tp, profit_pips distribution")
print("=" * 70)
perf_path = os.path.join(base_dir, "performance.db")
if os.path.exists(perf_path):
    conn = sqlite3.connect(perf_path)
    df_perf = pd.read_sql_query("SELECT sl, tp, profit_usd, profit_pips, win_loss FROM trades WHERE profit_usd IS NOT NULL AND profit_usd != 0", conn)
    conn.close()
    total_p = len(df_perf)
    sl_zero = (df_perf['sl'].isna() | (df_perf['sl'] == 0)).sum()
    tp_zero = (df_perf['tp'].isna() | (df_perf['tp'] == 0)).sum()
    print(f"  Total closed trades: {total_p}")
    print(f"  sl (price) = 0 or NULL: {sl_zero} ({sl_zero/total_p*100:.1f}%)")
    print(f"  tp (price) = 0 or NULL: {tp_zero} ({tp_zero/total_p*100:.1f}%)")
    print(f"  profit_pips distribution:")
    print(f"    min={df_perf['profit_pips'].min():.1f} max={df_perf['profit_pips'].max():.1f}")
    print(f"    mean={df_perf['profit_pips'].mean():.1f} median={df_perf['profit_pips'].median():.1f}")
    print(f"    p10={df_perf['profit_pips'].quantile(0.10):.1f} p25={df_perf['profit_pips'].quantile(0.25):.1f}")
    print(f"    p75={df_perf['profit_pips'].quantile(0.75):.1f} p90={df_perf['profit_pips'].quantile(0.90):.1f}")
    wins = df_perf[df_perf['profit_usd'] > 0]
    losses = df_perf[df_perf['profit_usd'] < 0]
    print(f"  Wins avg profit_pips: {wins['profit_pips'].mean():.1f}")
    print(f"  Losses avg profit_pips (absolute): {abs(losses['profit_pips'].mean()):.1f}")
