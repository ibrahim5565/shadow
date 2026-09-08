import sqlite3
import pandas as pd
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("==================================================")
print("     AUDIT OF AUG 6 DECISIONS & ORDER EXECUTIONS  ")
print("==================================================")

# 1. Check decision_records.db
db_path = 'd:/Trading/Aegis_Gold/data/decision_records.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    try:
        tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)
        print("decision_records.db Tables:", tables['name'].tolist())
        for t in tables['name']:
            df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
            print(f"\n--- Table {t} (Total Rows: {len(df)}) ---")
            if 'timestamp' in df.columns or 'created_at' in df.columns:
                col = 'timestamp' if 'timestamp' in df.columns else 'created_at'
                df_aug6 = df[df[col].astype(str).str.contains('2026-08-06', na=False)]
                print(f"Aug 6 rows: {len(df_aug6)}")
                if len(df_aug6) > 0:
                    print(df_aug6.head(10).to_string())
    except Exception as e:
        print("Error reading decision_records.db:", e)
    conn.close()

# 2. Check aegis.log for RAW_ENGINE_VOTES or SELL decisions vs actual orders
log_path = 'd:/Trading/Aegis_Gold/logs/aegis.log'
if os.path.exists(log_path):
    raw_vote_lines = []
    order_lines = []
    decision_records = []
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if '2026-08-06' in line:
                if 'RAW_ENGINE_VOTES' in line:
                    raw_vote_lines.append(line.strip())
                elif 'ORDER' in line or 'order' in line:
                    if 'BUY' in line or 'SELL' in line or 'ORDER' in line:
                        order_lines.append(line.strip())
                elif 'Structured Decision Record' in line:
                    decision_records.append(line.strip())

    print(f"\nFound {len(raw_vote_lines)} RAW_ENGINE_VOTES lines on Aug 6.")
    print(f"Found {len(decision_records)} Structured Decision Record lines on Aug 6.")
    print(f"Found {len(order_lines)} ORDER log lines on Aug 6.")

    if raw_vote_lines:
        print("\n--- SAMPLE RAW_ENGINE_VOTES (Aug 6) ---")
        for line in raw_vote_lines[:10]:
            print("  ", line)

    if order_lines:
        print("\n--- SAMPLE ORDER LINES (Aug 6) ---")
        for line in order_lines[:15]:
            print("  ", line)

