import os
import glob
import sqlite3
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta, time

date_target = "2026-08-19"
print("==================================================")
print(f"       REPORT FOR DATE: {date_target}            ")
print("==================================================")

# 1. MT5 History Check
if mt5.initialize():
    print("[OK] Connected to MT5 Terminal.")
    # Fetch deals around 2026-08-19
    start_dt = datetime(2026, 8, 19, 0, 0, 0)
    end_dt = datetime(2026, 8, 19, 23, 59, 59)
    
    deals = mt5.history_deals_get(start_dt, end_dt)
    if deals:
        print(f"\n--- MT5 DEALS ON {date_target} ({len(deals)} deals) ---")
        for d in deals:
            d_dt = datetime.fromtimestamp(d.time)
            action = "BUY" if d.type == 0 else "SELL" if d.type == 1 else f"Type_{d.type}"
            entry = "IN" if d.entry == 0 else "OUT" if d.entry == 1 else f"Entry_{d.entry}"
            print(f"[{d_dt.strftime('%H:%M:%S')}] Ticket: {d.ticket} | Order: {d.order} | Symbol: {d.symbol} | "
                  f"Action: {action} ({entry}) | Vol: {d.volume} | Price: {d.price:.2f} | Profit: ${d.profit:+.2f}")
    else:
        print(f"\nNo MT5 deals found directly on {date_target}.")
    mt5.shutdown()
else:
    print("[INFO] Could not initialize MT5 (terminal might not be open).")

# 2. Check Database Files
print("\n=== SEARCHING DATABASES ===")
db_files = glob.glob("d:/Trading/**/*.db", recursive=True)
for db in db_files:
    try:
        conn = sqlite3.connect(db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for t in tables:
            t_name = t[0]
            try:
                cursor.execute(f"SELECT * FROM {t_name} LIMIT 1;")
                cols = [desc[0] for desc in cursor.description]
                for col in cols:
                    if any(k in col.lower() for k in ['date', 'time', 'timestamp']):
                        query = f"SELECT * FROM {t_name} WHERE {col} LIKE '%{date_target}%'"
                        cursor.execute(query)
                        rows = cursor.fetchall()
                        if rows:
                            print(f"\nDB: {os.path.basename(db)} | Table: {t_name} ({len(rows)} matching rows):")
                            for r in rows[:10]:
                                print(dict(zip(cols, r)))
            except Exception as e:
                pass
        conn.close()
    except Exception as e:
        pass

# 3. Check Log Files
print("\n=== SEARCHING LOG FILES ===")
log_files = glob.glob("d:/Trading/**/*.log", recursive=True) + glob.glob("d:/Trading/**/*.txt", recursive=True)
for fpath in log_files:
    if os.path.isfile(fpath) and "check_19_august" not in fpath:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                matched = [line.strip() for line in f if date_target in line and any(w in line.lower() for w in ['trade', 'order', 'deal', 'buy', 'sell', 'profit', 'signal', 'rsi'])]
                if matched:
                    print(f"\nLog: {fpath} ({len(matched)} matching lines):")
                    for m in matched[:15]:
                        print("  ", m)
        except Exception:
            pass
