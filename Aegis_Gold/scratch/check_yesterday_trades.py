import MetaTrader5 as mt5
from datetime import datetime, timedelta, time
import pandas as pd
import os

import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

print("==================================================")
print("       YESTERDAY'S TRADES HISTORY REPORT         ")
print("==================================================")

today = datetime.now().date()
yesterday = today - timedelta(days=1)
print(f"Report Date (Yesterday): {yesterday}")
print(f"Current System Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 1. MT5 History Check
mt5_connected = mt5.initialize()
if not mt5_connected:
    print(f"[FAIL] MT5 Connection Failed: {mt5.last_error()}")
else:
    print("[OK] MT5 Connected Successfully\n")
    account = mt5.account_info()
    if account:
        print(f"Account Login: {account.login} | Server: {account.server} | Currency: {account.currency}")
        print(f"Balance: ${account.balance:.2f} | Equity: ${account.equity:.2f}\n")
    
    # Query ranges:
    # Server time vs local time might differ, so let's fetch past 48 hours and filter for yesterday strictly & display
    start_dt = datetime.combine(yesterday, time.min)
    end_dt = datetime.combine(yesterday, time.max)
    
    # Also fetch full 3-day history to make sure no timezone discrepancy misses trades
    wide_start = datetime.combine(yesterday - timedelta(days=1), time.min)
    wide_end = datetime.now()
    
    deals = mt5.history_deals_get(wide_start, wide_end)
    
    if deals is None or len(deals) == 0:
        print(f"ℹ️ No deals returned by MT5 for period {wide_start} to {wide_end}")
    else:
        deals_list = []
        for d in deals:
            d_dict = d._asdict()
            d_dt = datetime.fromtimestamp(d.time)
            d_dict['datetime'] = d_dt
            d_dict['date_str'] = d_dt.strftime('%Y-%m-%d')
            deals_list.append(d_dict)
            
        df = pd.DataFrame(deals_list)
        
        # Filter for yesterday
        yesterday_str = yesterday.strftime('%Y-%m-%d')
        df_yesterday = df[df['date_str'] == yesterday_str]
        
        print(f"--- MT5 DEALS FOR YESTERDAY ({yesterday_str}) ---")
        if df_yesterday.empty:
            print(f"No MT5 deals found strictly on {yesterday_str}.")
        else:
            total_profit = 0.0
            total_commission = 0.0
            total_swap = 0.0
            
            for idx, row in df_yesterday.iterrows():
                entry_str = "IN" if row['entry'] == 0 else "OUT" if row['entry'] == 1 else "IN/OUT" if row['entry'] == 2 else f"Type_{row['entry']}"
                type_str = "BUY" if row['type'] == 0 else "SELL" if row['type'] == 1 else f"Deal_{row['type']}"
                profit = row['profit']
                comm = row['commission']
                swap = row['swap']
                total_profit += profit
                total_commission += comm
                total_swap += swap
                
                print(f"Time: {row['datetime'].strftime('%H:%M:%S')} | Ticket: {row['ticket']} | Order: {row['order']} | "
                      f"Symbol: {row['symbol']} | Action: {type_str} ({entry_str}) | Vol: {row['volume']} | "
                      f"Price: {row['price']:.5f} | Profit: ${profit:+.2f} | Comm: ${comm:.2f} | Swap: ${swap:.2f}")
            
            net_result = total_profit + total_commission + total_swap
            print("-" * 75)
            print(f"TOTAL PROFIT: ${total_profit:+.2f} | COMMISSIONS: ${total_commission:.2f} | SWAP: ${total_swap:.2f}")
            print(f"NET YESTERDAY P&L: ${net_result:+.2f}")
            print("-" * 75)

        # Print all recent deals in 48h range for full visibility
        print(f"\n--- ALL MT5 DEALS PAST 48 HOURS ---")
        for idx, row in df.iterrows():
            entry_str = "IN" if row['entry'] == 0 else "OUT" if row['entry'] == 1 else f"Type_{row['entry']}"
            type_str = "BUY" if row['type'] == 0 else "SELL" if row['type'] == 1 else f"Deal_{row['type']}"
            print(f"[{row['date_str']} {row['datetime'].strftime('%H:%M:%S')}] Ticket: {row['ticket']} | Order: {row['order']} | "
                  f"Symbol: {row['symbol']} | Action: {type_str} ({entry_str}) | Vol: {row['volume']} | "
                  f"Price: {row['price']:.5f} | Profit: ${row['profit']:+.2f}")

    mt5.shutdown()

# 2. Log File Check (trades.log & aegis.log)
print("\n==================================================")
print("       LOG FILE CHECK FOR TRADES (2026-08-06)     ")
print("==================================================")

log_paths = [
    "d:/Trading/Aegis_Gold/logs/trades.log",
    "d:/Trading/Aegis_Gold/logs/aegis.log",
    "d:/Trading/bot_trades.txt"
]

yesterday_str = yesterday.strftime('%Y-%m-%d')

for path in log_paths:
    if os.path.exists(path):
        print(f"\n--- Checking: {path} ---")
        matched_lines = []
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if yesterday_str in line and ("trade" in line.lower() or "order" in line.lower() or "deal" in line.lower() or "buy" in line.lower() or "sell" in line.lower() or "position" in line.lower() or "executed" in line.lower() or "closed" in line.lower()):
                        matched_lines.append(line.strip())
            
            if matched_lines:
                print(f"Found {len(matched_lines)} trade-related log entries on {yesterday_str}:")
                for line in matched_lines[:30]:  # Show top 30
                    print("  ", line)
                if len(matched_lines) > 30:
                    print(f"  ... and {len(matched_lines) - 30} more lines.")
            else:
                print(f"No trade log entries found for date {yesterday_str}.")
        except Exception as e:
            print(f"Error reading log file {path}: {e}")
    else:
        print(f"File not found: {path}")

