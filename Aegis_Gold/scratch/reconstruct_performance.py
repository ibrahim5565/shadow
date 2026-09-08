import sys
import MetaTrader5 as mt5
from datetime import datetime
import pandas as pd
import numpy as np

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

if not mt5.initialize():
    print("MT5 init failed")
    exit()

print("=" * 80)
print("COMPREHENSIVE FORENSIC AUDIT: OUTLIERS & PERFORMANCE RECONSTRUCTION")
print("=" * 80)

# Fetch all deals since June 1, 2026
start_dt = datetime(2026, 6, 1, 0, 0, 0)
end_dt = datetime.now()
deals = mt5.history_deals_get(start_dt, end_dt)

if not deals:
    print("No deals found.")
    mt5.shutdown()
    exit()

deal_data = []
for d in deals:
    dt = datetime.fromtimestamp(d.time)
    deal_data.append({
        'time': dt,
        'date': dt.strftime('%Y-%m-%d'),
        'ticket': d.ticket,
        'order': d.order,
        'symbol': d.symbol,
        'type': d.type,
        'entry': d.entry,
        'volume': d.volume,
        'price': d.price,
        'profit': d.profit,
        'commission': d.commission,
        'swap': d.swap,
        'magic': d.magic,
        'comment': d.comment
    })

df = pd.DataFrame(deal_data)
exits_df = df[df['entry'] == 1].copy()

print(f"Total deals: {len(df)}")
print(f"Total exit deals: {len(exits_df)}")

# June 19 analysis
print("\n--- JUNE 19, 2026 DEALS ---")
june19_deals = df[df['date'] == '2026-06-19']
for _, d in june19_deals.iterrows():
    print(f"[{d['time'].strftime('%H:%M:%S')}] {d['symbol']} Vol:{d['volume']} Price:{d['price']:.2f} Profit:${d['profit']:+.2f} Magic:{d['magic']} Comm:{d['comment']}")

# Daily Aggregation
daily_pnl = exits_df.groupby('date')['profit'].sum().reset_index()
daily_pnl = daily_pnl.sort_values(by='profit', ascending=False)

print("\n--- TOP 10 PROFITABLE DAYS ---")
print(daily_pnl.head(10).to_string(index=False))

print("\n--- TOP 5 LOSS DAYS ---")
print(daily_pnl.tail(5).to_string(index=False))

# Calculate metrics helper
def calc_metrics(data_df, label):
    if len(data_df) == 0:
        return {}
    wins = data_df[data_df['profit'] > 0]['profit']
    losses = data_df[data_df['profit'] < 0]['profit']
    
    total_pnl = data_df['profit'].sum()
    gross_win = wins.sum() if len(wins) > 0 else 0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 0
    win_rate = (len(wins) / len(data_df)) * 100 if len(data_df) > 0 else 0
    pf = (gross_win / gross_loss) if gross_loss > 0 else float('inf')
    avg_win = wins.mean() if len(wins) > 0 else 0
    avg_loss = losses.mean() if len(losses) > 0 else 0
    expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)
    
    # Daily metrics
    daily = data_df.groupby('date')['profit'].sum()
    med_daily = daily.median() if len(daily) > 0 else 0
    mean_daily = daily.mean() if len(daily) > 0 else 0
    p95_daily = np.percentile(daily, 95) if len(daily) > 0 else 0
    p05_daily = np.percentile(daily, 5) if len(daily) > 0 else 0
    
    # Drawdown
    cum = daily.cumsum()
    peak = cum.cummax()
    dd = peak - cum
    max_dd = dd.max() if len(dd) > 0 else 0
    
    return {
        'Scenario': label,
        'Trades': len(data_df),
        'Days': len(daily),
        'Net PnL ($)': round(total_pnl, 2),
        'Profit Factor': round(pf, 3),
        'Win Rate (%)': round(win_rate, 2),
        'Avg Win ($)': round(avg_win, 2),
        'Avg Loss ($)': round(avg_loss, 2),
        'Expectancy ($)': round(expectancy, 2),
        'Max DD ($)': round(max_dd, 2),
        'Median Daily ($)': round(med_daily, 2),
        'Mean Daily ($)': round(mean_daily, 2),
        'P05 Daily ($)': round(p05_daily, 2),
        'P95 Daily ($)': round(p95_daily, 2)
    }

scenarios = []
scenarios.append(calc_metrics(exits_df, "1. ALL TRADES & DAYS"))

# Exclude July 3
no_july3 = exits_df[exits_df['date'] != '2026-07-03']
scenarios.append(calc_metrics(no_july3, "2. EXCLUDING JULY 3"))

# Exclude June 19
no_june19 = exits_df[exits_df['date'] != '2026-06-19']
scenarios.append(calc_metrics(no_june19, "3. EXCLUDING JUNE 19"))

# Exclude Top 1 Day
top1_day = daily_pnl.iloc[0]['date']
no_top1 = exits_df[exits_df['date'] != top1_day]
scenarios.append(calc_metrics(no_top1, f"4. EXCLUDING TOP 1 DAY ({top1_day})"))

# Exclude Top 2 Days (July 3 & June 19)
top2_days = daily_pnl.iloc[:2]['date'].tolist()
no_top2 = exits_df[~exits_df['date'].isin(top2_days)]
scenarios.append(calc_metrics(no_top2, f"5. EXCLUDING TOP 2 DAYS ({', '.join(top2_days)})"))

# Exclude Top 5 Days
top5_days = daily_pnl.iloc[:5]['date'].tolist()
no_top5 = exits_df[~exits_df['date'].isin(top5_days)]
scenarios.append(calc_metrics(no_top5, f"6. EXCLUDING TOP 5 DAYS"))

# Only Bot Trades (magic != 0 or volume <= 0.1)
bot_only = exits_df[(exits_df['magic'] != 0) | (exits_df['volume'] <= 0.05)]
scenarios.append(calc_metrics(bot_only, "7. BOT EXITS ONLY (<=0.05 lot)"))

res_df = pd.DataFrame(scenarios)
print("\n" + "=" * 120)
print("RECONSTRUCTED PROFITABILITY MATRIX")
print("=" * 120)
print(res_df.to_string(index=False))

# Contribution %
total_net = exits_df['profit'].sum()
top1_net = exits_df[exits_df['date'] == top1_day]['profit'].sum()
top2_net = exits_df[exits_df['date'].isin(top2_days)]['profit'].sum()
top5_net = exits_df[exits_df['date'].isin(top5_days)]['profit'].sum()

print("\n--- OUTLIER CONCENTRATION METRICS ---")
print(f"Total Net P&L: ${total_net:,.2f}")
print(f"Top 1 Day Contribution: ${top1_net:,.2f} ({top1_net/total_net*100:.2f}%)")
print(f"Top 2 Days Contribution: ${top2_net:,.2f} ({top2_net/total_net*100:.2f}%)")
print(f"Top 5 Days Contribution: ${top5_net:,.2f} ({top5_net/total_net*100:.2f}%)")

mt5.shutdown()
