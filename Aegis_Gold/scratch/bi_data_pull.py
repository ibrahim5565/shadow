import MetaTrader5 as mt5
from datetime import datetime, timedelta
from collections import defaultdict

if not mt5.initialize():
    print("MT5 init failed")
    exit()

acc = mt5.account_info()
print("=== ACCOUNT INFO ===")
print(f"Login: {acc.login} | Server: {acc.server} | Currency: {acc.currency}")
print(f"Balance: ${acc.balance:,.2f} | Equity: ${acc.equity:,.2f} | Leverage: {acc.leverage}x")

# All deals since start
start_dt = datetime(2026, 6, 1, 0, 0, 0)
end_dt = datetime.now()
deals = mt5.history_deals_get(start_dt, end_dt)

if not deals:
    print("No deals found.")
    mt5.shutdown()
    exit()

print(f"\nTotal deals retrieved: {len(deals)}")

# Aggregate by day
daily = defaultdict(lambda: {"deals": 0, "exits": 0, "wins": 0, "losses": 0,
                              "pnl": 0.0, "win_pnl": 0.0, "loss_pnl": 0.0,
                              "xau_pnl": 0.0, "eur_pnl": 0.0})
all_exit_profits = []
all_win_profits = []
all_loss_profits = []

for d in deals:
    day = datetime.fromtimestamp(d.time).strftime("%Y-%m-%d")
    daily[day]["deals"] += 1
    if d.entry == 1:  # exit deal
        daily[day]["exits"] += 1
        daily[day]["pnl"] += d.profit
        if d.profit > 0:
            daily[day]["wins"] += 1
            daily[day]["win_pnl"] += d.profit
            all_win_profits.append(d.profit)
        elif d.profit < 0:
            daily[day]["losses"] += 1
            daily[day]["loss_pnl"] += d.profit
            all_loss_profits.append(d.profit)
        all_exit_profits.append(d.profit)
        if d.symbol == "XAUUSD":
            daily[day]["xau_pnl"] += d.profit
        elif d.symbol == "EURUSD":
            daily[day]["eur_pnl"] += d.profit

print("\n=== DAILY P&L HISTORY ===")
print(f"{'DATE':<12} | {'DEALS':>6} | {'EXITS':>6} | {'WINS':>5} | {'LOSSES':>7} | {'WIN%':>6} | {'PNL':>10} | {'XAU_PNL':>10} | {'EUR_PNL':>10}")
print("-" * 100)

total_pnl = 0.0
days_up = 0
days_down = 0
days_flat = 0
trading_days = []

for day in sorted(daily.keys()):
    r = daily[day]
    exits = r["exits"]
    wr = round(r["wins"] / exits * 100, 1) if exits > 0 else 0
    pnl = round(r["pnl"], 2)
    total_pnl += pnl
    trading_days.append(pnl)
    if pnl > 0.01: days_up += 1
    elif pnl < -0.01: days_down += 1
    else: days_flat += 1
    print(f"{day:<12} | {r['deals']:>6} | {exits:>6} | {r['wins']:>5} | {r['losses']:>7} | {wr:>5}% | {pnl:>+10.2f} | {round(r['xau_pnl'],2):>+10.2f} | {round(r['eur_pnl'],2):>+10.2f}")

print("-" * 100)

# Overall stats
total_exits = len(all_exit_profits)
total_wins = len(all_win_profits)
total_losses = len(all_loss_profits)
win_rate = round(total_wins / total_exits * 100, 2) if total_exits > 0 else 0
gross_profit = sum(all_win_profits)
gross_loss = sum(all_loss_profits)
avg_win = sum(all_win_profits) / total_wins if total_wins > 0 else 0
avg_loss = sum(all_loss_profits) / total_losses if total_losses > 0 else 0
profit_factor = abs(gross_profit / gross_loss) if gross_loss != 0 else float("inf")

print(f"\n=== OVERALL PERFORMANCE METRICS ===")
print(f"Total Trading Exits:          {total_exits}")
print(f"Winning Exits:                {total_wins} ({win_rate}%)")
print(f"Losing Exits:                 {total_losses}")
print(f"Gross Profit (from wins):     ${gross_profit:+,.2f}")
print(f"Gross Loss (from losses):     ${gross_loss:+,.2f}")
print(f"NET P&L (all history):        ${total_pnl:+,.2f}")
print(f"Average Win:                  ${avg_win:+.4f}")
print(f"Average Loss:                 ${avg_loss:+.4f}")
print(f"Profit Factor:                {profit_factor:.3f}")
print(f"Profitable Days:              {days_up}")
print(f"Loss Days:                    {days_down}")
print(f"Flat Days:                    {days_flat}")
print(f"Day Win Rate:                 {round(days_up/(days_up+days_down)*100,1) if days_up+days_down>0 else 0}%")
print(f"Starting Balance (est.):      ${acc.balance - total_pnl:,.2f}")
print(f"Current Balance:              ${acc.balance:,.2f}")
print(f"Total Return:                 {round(total_pnl / (acc.balance - total_pnl) * 100, 4)}%")

mt5.shutdown()
