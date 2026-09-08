import sqlite3
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta, time
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

yesterday_str = "2026-08-06"
print(f"=== COMPREHENSIVE TRADE HISTORY REPORT FOR YESTERDAY: {yesterday_str} ===\n")

# 1. Fetch MT5 History Deals
mt5_deals = []
if mt5.initialize():
    start = datetime(2026, 8, 6, 0, 0, 0)
    end = datetime(2026, 8, 6, 23, 59, 59)
    deals = mt5.history_deals_get(start, end)
    if deals:
        for d in deals:
            d_dict = d._asdict()
            d_dt = datetime.fromtimestamp(d.time)
            d_dict['datetime_str'] = d_dt.strftime('%Y-%m-%d %H:%M:%S')
            d_dict['time_only'] = d_dt.strftime('%H:%M:%S')
            mt5_deals.append(d_dict)
    mt5.shutdown()

print(f"Total MT5 Deals recorded directly on MT5 server for {yesterday_str}: {len(mt5_deals)}")

# 2. Fetch Performance DB records
db_path = 'd:/Trading/Aegis_Gold/data/performance.db'
db_trades = []
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM attributions", conn)
        df_yesterday = df[df['timestamp'].astype(str).str.contains(yesterday_str, na=False)]
        db_trades = df_yesterday.to_dict('records')
    except Exception as e:
        print("DB error:", e)
    conn.close()

print(f"Total Trade Records in Performance DB for {yesterday_str}: {len(db_trades)}\n")

# 3. Parse trades.log
log_path = 'd:/Trading/Aegis_Gold/logs/trades.log'
log_trades = []
if os.path.exists(log_path):
    import json
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if yesterday_str in line:
                try:
                    # JSON line payload usually after timestamp bracket
                    json_start = line.find('{')
                    if json_start != -1:
                        data = json.loads(line[json_start:])
                        log_trades.append(data)
                except Exception:
                    pass

print(f"Total Trade Log Entries in trades.log for {yesterday_str}: {len(log_trades)}\n")

# Process performance.db data for detailed display
if db_trades:
    df_perf = pd.DataFrame(db_trades)
    
    # Calculate key statistics
    total_trades = len(df_perf)
    wins = len(df_perf[df_perf['outcome'] == 'WIN'])
    losses = len(df_perf[df_perf['outcome'] == 'LOSS'])
    breakeven = len(df_perf[df_perf['outcome'] == 'BREAKEVEN'])
    unknown = total_trades - wins - losses - breakeven
    
    # PnL USD numeric
    df_perf['pnl_usd_num'] = pd.to_numeric(df_perf['pnl_usd'], errors='coerce').fillna(0.0)
    total_pnl = df_perf['pnl_usd_num'].sum()
    
    print("==================================================")
    print("           YESTERDAY'S SUMMARY (2026-08-06)       ")
    print("==================================================")
    print(f"📊 Total Executed Trades : {total_trades}")
    print(f"✅ Wins                 : {wins}")
    print(f"❌ Losses               : {losses}")
    print(f"⏸️ Breakeven            : {breakeven}")
    print(f"❓ Other/Pending        : {unknown}")
    print(f"💰 Net Realized PnL ($) : ${total_pnl:+.2f}")
    if total_trades > 0:
        win_rate = (wins / total_trades) * 100
        print(f"📈 Win Rate             : {win_rate:.1f}%")
    print("==================================================\n")
    
    print("--- INDIVIDUAL TRADES LIST (Sample / First 30 Trades) ---")
    cols_to_print = ['ticket', 'timestamp', 'signal_source', 'session', 'outcome', 'pnl_usd', 'historical_edge', 'microstructure_quality']
    available_cols = [c for c in cols_to_print if c in df_perf.columns]
    
    sample_df = df_perf[available_cols].copy()
    # Format timestamp to readable HH:MM:SS
    sample_df['time'] = sample_df['timestamp'].apply(lambda x: str(x)[11:19] if len(str(x)) >= 19 else str(x))
    
    for idx, row in sample_df.iterrows():
        pnl_val = float(row['pnl_usd']) if row['pnl_usd'] is not None else 0.0
        pnl_str = f"${pnl_val:+.2f}"
        print(f"Ticket: {row['ticket']} | Time: {row['time']} | Source: {row['signal_source']} | "
              f"Session: {row['session']} | Outcome: {row['outcome']} | PnL: {pnl_str}")

# Save full processed dataframe to CSV for quick reference
if db_trades:
    df_perf.to_csv('d:/Trading/Aegis_Gold/scratch/yesterday_trades_summary.csv', index=False)
    print("\nSaved full trades list to scratch/yesterday_trades_summary.csv")
