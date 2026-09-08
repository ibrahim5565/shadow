import MetaTrader5 as mt5
from datetime import datetime, timedelta, time
import pandas as pd
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

yesterday_str = "2026-08-06"
print(f"==================================================")
print(f"  MT5 SERVER TRADE HISTORY REPORT FOR {yesterday_str}")
print(f"==================================================\n")

if not mt5.initialize():
    print(f"❌ MT5 initialization failed: {mt5.last_error()}")
    sys.exit(1)

start = datetime(2026, 8, 6, 0, 0, 0)
end = datetime(2026, 8, 6, 23, 59, 59)

deals = mt5.history_deals_get(start, end)
orders = mt5.history_orders_get(start, end)

if not deals:
    print("No deals found for yesterday.")
    mt5.shutdown()
    sys.exit(0)

deals_list = []
for d in deals:
    d_dict = d._asdict()
    d_dt = datetime.fromtimestamp(d.time)
    d_dict['datetime'] = d_dt
    d_dict['time_str'] = d_dt.strftime('%H:%M:%S')
    deals_list.append(d_dict)

df_deals = pd.DataFrame(deals_list)

# Filter deals that affect balance (entry == 1 (OUT), or profit != 0)
# Entry types in MT5: 0=IN, 1=OUT, 2=IN/OUT, 3=OUT_BY
out_deals = df_deals[df_deals['entry'] == 1].copy() # Closing deals
in_deals = df_deals[df_deals['entry'] == 0].copy() # Opening deals

total_gross_profit = out_deals[out_deals['profit'] > 0]['profit'].sum()
total_gross_loss = out_deals[out_deals['profit'] < 0]['profit'].sum()
net_profit = df_deals['profit'].sum()
total_commission = df_deals['commission'].sum()
total_swap = df_deals['swap'].sum()
net_pnl = net_profit + total_commission + total_swap

winning_deals = len(out_deals[out_deals['profit'] > 0])
losing_deals = len(out_deals[out_deals['profit'] < 0])
breakeven_deals = len(out_deals[out_deals['profit'] == 0])
total_closed_trades = len(out_deals)

win_rate = (winning_deals / total_closed_trades * 100) if total_closed_trades > 0 else 0.0

symbols = df_deals['symbol'].unique()
symbols_str = ", ".join([s for s in symbols if s])

print("--------------------------------------------------")
print("                SUMMARY METRICS                   ")
print("--------------------------------------------------")
print(f"📅 Date                       : {yesterday_str}")
print(f"📊 Total Server Deals Recorded: {len(df_deals)}")
print(f"📥 Position Open Deals (IN)   : {len(in_deals)}")
print(f"📤 Position Close Deals (OUT) : {total_closed_trades}")
print(f"🎯 Symbols Traded             : {symbols_str}")
print("--------------------------------------------------")
print(f"✅ Winning Trades             : {winning_deals}")
print(f"❌ Losing Trades              : {losing_deals}")
print(f"⏸️ Breakeven Trades           : {breakeven_deals}")
print(f"📈 Win Rate                   : {win_rate:.2f}%")
print("--------------------------------------------------")
print(f"💵 Gross Profit               : ${total_gross_profit:+.2f}")
print(f"💸 Gross Loss                 : ${total_gross_loss:+.2f}")
print(f"📉 Total Commission           : ${total_commission:.2f}")
print(f"🔄 Total Swap                 : ${total_swap:.2f}")
print(f"💰 NET REALIZED PnL           : ${net_pnl:+.2f}")
print("--------------------------------------------------\n")

# Breakdown by Symbol
print("--------------------------------------------------")
print("              PERFORMACE BY SYMBOL                ")
print("--------------------------------------------------")
for sym in symbols:
    if not sym:
        continue
    sym_deals = out_deals[out_deals['symbol'] == sym]
    sym_profit = sym_deals['profit'].sum()
    sym_wins = len(sym_deals[sym_deals['profit'] > 0])
    sym_losses = len(sym_deals[sym_deals['profit'] < 0])
    sym_total = len(sym_deals)
    sym_wr = (sym_wins / sym_total * 100) if sym_total > 0 else 0.0
    print(f"Symbol: {sym:8s} | Closed Trades: {sym_total:4d} | Wins: {sym_wins:4d} | Losses: {sym_losses:4d} | WinRate: {sym_wr:5.1f}% | Net PnL: ${sym_profit:+.2f}")
print("--------------------------------------------------\n")

# Display Sample Trades (First 20 and Last 20)
print("--------------------------------------------------")
print("      TRADES DETAIL (SAMPLE - OUT/CLOSED DEALS)   ")
print("--------------------------------------------------")

def print_deal_rows(sub_df, title):
    print(f"\n--- {title} ---")
    for idx, row in sub_df.iterrows():
        deal_type = "BUY" if row['type'] == 0 else "SELL" if row['type'] == 1 else f"DEAL_{row['type']}"
        print(f"Time: {row['time_str']} | Ticket: {row['ticket']} | Position ID: {row['position_id']} | "
              f"Symbol: {row['symbol']:6s} | Type: {deal_type:4s} | Vol: {row['volume']:.2f} | "
              f"Price: {row['price']:.5f} | Profit: ${row['profit']:+.2f}")

print_deal_rows(out_deals.head(15), "FIRST 15 CLOSED TRADES OF YESTERDAY")
print_deal_rows(out_deals.tail(15), "LAST 15 CLOSED TRADES OF YESTERDAY")

# Export complete details to CSV
out_deals_export = out_deals[['time_str', 'ticket', 'order', 'position_id', 'symbol', 'type', 'volume', 'price', 'profit', 'commission', 'swap', 'comment']]
out_deals_export.to_csv('d:/Trading/Aegis_Gold/scratch/yesterday_closed_deals.csv', index=False)
df_deals.to_csv('d:/Trading/Aegis_Gold/scratch/yesterday_all_deals.csv', index=False)
print("\n[OK] Full trade dataset saved to 'scratch/yesterday_closed_deals.csv'")

mt5.shutdown()
