import sqlite3
import pandas as pd
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

db_files = [
    'd:/Trading/Aegis_Gold/data/performance.db',
    'd:/Trading/Aegis_Gold/data/trade_memory.db',
    'd:/Trading/Aegis_Gold/data/decision_records.db',
    'd:/Trading/Aegis_Gold/data/attribution.db'
]

for db_path in db_files:
    if not os.path.exists(db_path):
        continue
    print(f"\n==========================================")
    print(f"DATABASE: {os.path.basename(db_path)}")
    print(f"==========================================")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    print("Tables:", tables)
    
    for t in tables:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {t}", conn)
            print(f"\n--- Table: {t} (Total Rows: {len(df)}) ---")
            
            # Check for yesterday's date '2026-08-06'
            matched = False
            for col in df.columns:
                # check string representation
                mask = df[col].astype(str).str.contains('2026-08-06', na=False)
                if mask.any():
                    matched_df = df[mask]
                    print(f"Found {len(matched_df)} rows matching '2026-08-06' in column '{col}'")
                    print(matched_df.head(20).to_string())
                    matched = True
                    break
            if not matched and len(df) > 0:
                print("No rows matching '2026-08-06'. Recent 5 rows:")
                print(df.tail(5).to_string())
        except Exception as e:
            print(f"Error querying table {t}: {e}")
    conn.close()
