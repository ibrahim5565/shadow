import sqlite3
import pandas as pd
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
TRADE_MEMORY_DB = DATA_DIR / "trade_memory.db"

conn = sqlite3.connect(TRADE_MEMORY_DB)
df = pd.read_sql_query("SELECT * FROM trades", conn)
conn.close()

print(f"Total Rows in trade_memory: {len(df)}")
pnl = df['profit_usd']

wins = df[pnl > 0]
losses = df[pnl < 0]

print("\n--- EXIT REASONS ---")
print(df['exit_reason'].value_counts())

print("\n--- PNL & STATS BY EXIT REASON ---")
for reason in df['exit_reason'].unique():
    sub = df[df['exit_reason'] == reason]
    sub_wins = sub[sub['profit_usd'] > 0]
    sub_losses = sub[sub['profit_usd'] < 0]
    wr = len(sub_wins) / len(sub) * 100 if len(sub) > 0 else 0
    print(f"Reason: {reason}")
    print(f"  Count: {len(sub)} | WR: {wr:.1f}% | Net PnL: ${sub['profit_usd'].sum():.2f}")
    print(f"  Avg Win: ${sub_wins['profit_usd'].mean():.4f} (Count: {len(sub_wins)})")
    print(f"  Avg Loss: ${abs(sub_losses['profit_usd'].mean()):.4f} (Count: {len(sub_losses)})")
    print(f"  Avg Duration: {sub['duration_seconds'].mean():.1f}s")
    print(f"  Avg SL Pts: {sub['sl_points'].mean():.1f} | Avg TP Pts: {sub['tp_points'].mean():.1f}")
    print(f"  Avg MAE (%): {sub['max_drawdown_pct'].mean():.4f}")
    print(f"  Avg MFE (%): {sub['max_profit_reached'].mean():.4f}")

print("\n--- SIGNAL SOURCE DETAILED STATS ---")
for sig in df['signal_source'].unique():
    sub = df[df['signal_source'] == sig]
    sub_wins = sub[sub['profit_usd'] > 0]
    sub_losses = sub[sub['profit_usd'] < 0]
    wr = len(sub_wins) / len(sub) * 100 if len(sub) > 0 else 0
    print(f"Signal Source: {sig}")
    print(f"  Count: {len(sub)} | WR: {wr:.1f}% | Net PnL: ${sub['profit_usd'].sum():.2f}")
    print(f"  Avg Win: ${sub_wins['profit_usd'].mean():.4f}")
    print(f"  Avg Loss: ${abs(sub_losses['profit_usd'].mean()):.4f}")

print("\n--- REGIME DETAILED STATS ---")
for reg in df['regime'].unique():
    sub = df[df['regime'] == reg]
    sub_wins = sub[sub['profit_usd'] > 0]
    sub_losses = sub[sub['profit_usd'] < 0]
    wr = len(sub_wins) / len(sub) * 100 if len(sub) > 0 else 0
    print(f"Regime: {reg}")
    print(f"  Count: {len(sub)} | WR: {wr:.1f}% | Net PnL: ${sub['profit_usd'].sum():.2f}")
    print(f"  Avg Win: ${sub_wins['profit_usd'].mean():.4f}")
    print(f"  Avg Loss: ${abs(sub_losses['profit_usd'].mean()):.4f}")

print("\n--- MAE & MFE DISTRIBUTION ---")
print(f"Winning Trades Max Profit Reached (MFE): mean = {wins['max_profit_reached'].mean():.4f}, median = {wins['max_profit_reached'].median():.4f}, 75th percentile = {wins['max_profit_reached'].quantile(0.75):.4f}")
print(f"Losing Trades Max Drawdown (MAE): mean = {losses['max_drawdown_pct'].mean():.4f}, median = {losses['max_drawdown_pct'].median():.4f}, 75th percentile = {losses['max_drawdown_pct'].quantile(0.75):.4f}")
print(f"Winning Trades Max Drawdown (MAE before win): mean = {wins['max_drawdown_pct'].mean():.4f}, median = {wins['max_drawdown_pct'].median():.4f}, 90th percentile = {wins['max_drawdown_pct'].quantile(0.90):.4f}")

