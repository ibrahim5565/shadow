import sqlite3
import pandas as pd
import json
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

db_path = 'd:/Trading/Aegis_Gold/data/decision_records.db'
conn = sqlite3.connect(db_path)

df = pd.read_sql_query("SELECT * FROM decision_records WHERE timestamp LIKE '%2026-08-06%'", conn)
conn.close()

print(f"Total Decision Records on Aug 6: {len(df)}")
print("\n--- Breakdown by 'direction' ---")
print(df['direction'].value_counts(dropna=False))

print("\n--- Breakdown by 'action' ---")
print(df['action'].value_counts(dropna=False))

print("\n--- Breakdown by 'direction' and 'action' ---")
print(pd.crosstab(df['direction'], df['action']))

# Filter for SELL directions
df_sell = df[df['direction'] == 'SELL']
print(f"\nTotal SELL direction setups evaluated: {len(df_sell)}")
if len(df_sell) > 0:
    print(df_sell['action'].value_counts())
    print("\nSample SELL setups:")
    print(df_sell[['timestamp', 'symbol', 'action', 'direction', 'confidence', 'model_outputs', 'risk_assessment']].head(15).to_string())

# Also check MT5 deals executed on Aug 6
import MetaTrader5 as mt5
from datetime import datetime

if mt5.initialize():
    start = datetime(2026, 8, 6, 0, 0, 0)
    end = datetime(2026, 8, 6, 23, 59, 59)
    deals = mt5.history_deals_get(start, end)
    if deals:
        deals_list = [d._asdict() for d in deals]
        df_deals = pd.DataFrame(deals_list)
        # Entry 0 = IN (Position Open)
        in_deals = df_deals[df_deals['entry'] == 0]
        print(f"\n--- MT5 OPEN DEALS ON AUG 6 (Total: {len(in_deals)}) ---")
        # Type 0 = BUY, Type 1 = SELL
        print(in_deals['type'].value_counts().rename(index={0: 'BUY (0)', 1: 'SELL (1)'}))
    mt5.shutdown()

