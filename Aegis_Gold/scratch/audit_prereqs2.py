"""
Audit 5: Spread analysis from performance.db adx_at_entry / via MT5 gateway check
Also check sl column distribution and max_drawdown_pct / max_profit_reached coverage
"""
import sqlite3
import os
import pandas as pd
import numpy as np

base_dir = r"d:\Trading\Aegis_Gold\data"

# Check max_drawdown_pct and max_profit_reached in trade_memory.db
db_path = os.path.join(base_dir, "trade_memory.db")
conn = sqlite3.connect(db_path)
df = pd.read_sql_query("""
    SELECT trade_id, symbol, direction, profit_usd,
           sl_points, tp_points, rr_ratio,
           max_drawdown_pct, max_profit_reached,
           entry_price, exit_price, lot_size, atr,
           spread, sl_was_hit, tp_was_hit, exit_reason,
           duration_seconds
    FROM trades
    WHERE profit_usd IS NOT NULL AND profit_usd != 0
""", conn)
conn.close()

total = len(df)
print("=" * 70)
print(f"AUDIT 5: max_drawdown_pct and max_profit_reached coverage (N={total})")
print("=" * 70)

mdd_present = df['max_drawdown_pct'].notna() & (df['max_drawdown_pct'] != 0)
mpr_present = df['max_profit_reached'].notna() & (df['max_profit_reached'] != 0)

print(f"  max_drawdown_pct > 0: {mdd_present.sum()} ({mdd_present.sum()/total*100:.1f}%)")
print(f"  max_profit_reached > 0: {mpr_present.sum()} ({mpr_present.sum()/total*100:.1f}%)")

if mdd_present.sum() > 0:
    mdd_vals = df[mdd_present]['max_drawdown_pct']
    print(f"  max_drawdown_pct stats: min={mdd_vals.min():.4f} max={mdd_vals.max():.4f} mean={mdd_vals.mean():.4f}")

if mpr_present.sum() > 0:
    mpr_vals = df[mpr_present]['max_profit_reached']
    print(f"  max_profit_reached stats: min={mpr_vals.min():.4f} max={mpr_vals.max():.4f} mean={mpr_vals.mean():.4f}")

print()
print("  sl_was_hit / tp_was_hit coverage:")
slhit = df['sl_was_hit'].notna()
tphit = df['tp_was_hit'].notna()
print(f"  sl_was_hit not null: {slhit.sum()} ({slhit.sum()/total*100:.1f}%)")
print(f"  tp_was_hit not null: {tphit.sum()} ({tphit.sum()/total*100:.1f}%)")
print(f"  sl_was_hit=1 count: {(df['sl_was_hit']==1).sum()}")
print(f"  tp_was_hit=1 count: {(df['tp_was_hit']==1).sum()}")

print()
print("  exit_reason breakdown:")
if 'exit_reason' in df.columns:
    print(df['exit_reason'].value_counts().head(15).to_string())

print()
print("=" * 70)
print("AUDIT 6: XAUUSD spread analysis from performance.db sl column")
print("=" * 70)

# Check performance.db sl column non-zero trades
perf_path = os.path.join(base_dir, "performance.db")
conn = sqlite3.connect(perf_path)
df_perf = pd.read_sql_query("""
    SELECT symbol, sl, tp, entry_price, exit_price,
           profit_usd, profit_pips, win_loss, timestamp
    FROM trades
    WHERE profit_usd IS NOT NULL AND profit_usd != 0
      AND symbol LIKE '%XAU%'
""", conn)
conn.close()

total_xau = len(df_perf)
print(f"  XAUUSD closed trades: {total_xau}")

# Where SL price is set, compute SL distance in pts
sl_set = df_perf[(df_perf['sl'] > 0) & (df_perf['entry_price'] > 0)].copy()
if len(sl_set) > 0:
    # SL distance in pts (XAUUSD point = 0.01)
    sl_set['sl_pts'] = abs(sl_set['entry_price'] - sl_set['sl']) / 0.01
    print(f"  Trades with real SL price set: {len(sl_set)} ({len(sl_set)/total_xau*100:.1f}%)")
    print(f"  SL distance stats (pts):")
    print(f"    min={sl_set['sl_pts'].min():.1f} max={sl_set['sl_pts'].max():.1f}")
    print(f"    mean={sl_set['sl_pts'].mean():.1f} median={sl_set['sl_pts'].median():.1f}")
    print(f"    p10={sl_set['sl_pts'].quantile(0.10):.1f} p25={sl_set['sl_pts'].quantile(0.25):.1f}")
    print(f"    p75={sl_set['sl_pts'].quantile(0.75):.1f} p90={sl_set['sl_pts'].quantile(0.90):.1f}")

print()
print("=" * 70)
print("AUDIT 7: Profit pips distribution — can we use it to estimate MAE?")
print("=" * 70)
# For trades with both entry+exit price and profit_pips known
# Look at loss distribution to understand typical drawdown on losing trades
df_xau = df_perf[df_perf['symbol'].str.contains('XAU', na=False)].copy()
wins = df_xau[df_xau['profit_usd'] > 0]
losses = df_xau[df_xau['profit_usd'] < 0]

print(f"  XAUUSD Wins ({len(wins)}): avg profit_pips={wins['profit_pips'].mean():.1f}")
print(f"    p10={wins['profit_pips'].quantile(0.10):.1f} p25={wins['profit_pips'].quantile(0.25):.1f} p75={wins['profit_pips'].quantile(0.75):.1f} p90={wins['profit_pips'].quantile(0.90):.1f}")
print(f"  XAUUSD Losses ({len(losses)}): avg profit_pips={losses['profit_pips'].mean():.1f}")
print(f"    p10={losses['profit_pips'].quantile(0.10):.1f} p25={losses['profit_pips'].quantile(0.25):.1f} p75={losses['profit_pips'].quantile(0.75):.1f} p90={losses['profit_pips'].quantile(0.90):.1f}")

print()
print("  Worst losses (profit_pips) — sample of top 20 by magnitude:")
worst = losses.nsmallest(20, 'profit_pips')[['timestamp','profit_pips','profit_usd','sl','tp','trade_duration_min']]
print(worst.to_string())

print()
print("  Quick spread proxy: look at near-zero trades")
near_zero = df_xau[(df_xau['profit_pips'].abs() < 5) & (df_xau['profit_pips'].abs() > 0)]
print(f"  Trades with |profit_pips| < 5: {len(near_zero)} ({len(near_zero)/total_xau*100:.1f}%)")
if len(near_zero) > 0:
    print(f"  Near-zero pips mean: {near_zero['profit_pips'].mean():.2f}")
