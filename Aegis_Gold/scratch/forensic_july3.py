"""
FORENSIC ANALYSIS: July 3, 2026 - +$319,574.61 Outlier Event
Investigates every MT5 deal on 2026-07-03 to determine root cause.
"""
import MetaTrader5 as mt5
from datetime import datetime
from collections import defaultdict
import json

if not mt5.initialize():
    print("MT5 init failed")
    exit()

print("=" * 80)
print("FORENSIC REPORT: 2026-07-03 | OUTLIER: +$319,574.61")
print("=" * 80)

start_dt = datetime(2026, 7, 3, 0, 0, 0)
end_dt   = datetime(2026, 7, 3, 23, 59, 59)

deals = mt5.history_deals_get(start_dt, end_dt)
orders = mt5.history_orders_get(start_dt, end_dt)

if not deals:
    print("No deals found for 2026-07-03.")
    mt5.shutdown()
    exit()

print(f"\nTotal Deals: {len(deals)}")
print(f"Total Orders: {len(orders) if orders else 0}")

# Analyze deals
total_pnl = 0.0
deal_list = []
for d in deals:
    dt = datetime.fromtimestamp(d.time)
    entry_str = "IN" if d.entry == 0 else "OUT" if d.entry == 1 else f"Entry_{d.entry}"
    type_str  = "BUY" if d.type == 0 else "SELL" if d.type == 1 else f"Type_{d.type}"
    deal_list.append({
        "time":    dt.strftime("%H:%M:%S"),
        "ticket":  d.ticket,
        "order":   d.order,
        "symbol":  d.symbol,
        "action":  f"{type_str}({entry_str})",
        "volume":  d.volume,
        "price":   d.price,
        "profit":  d.profit,
        "commission": d.commission,
        "swap":    d.swap,
        "comment": d.comment,
        "magic":   d.magic,
    })
    total_pnl += d.profit

# Summary stats
exits = [d for d in deal_list if "OUT" in d["action"]]
entries = [d for d in deal_list if "IN" in d["action"]]
xau_deals = [d for d in deal_list if d["symbol"] == "XAUUSD"]
eur_deals = [d for d in deal_list if d["symbol"] == "EURUSD"]
profitable = [d for d in exits if d["profit"] > 0]
losing     = [d for d in exits if d["profit"] < 0]

# Volume analysis  
volumes = set(d["volume"] for d in deal_list)
magic_numbers = set(d["magic"] for d in deal_list)
comments = set(d["comment"] for d in deal_list if d["comment"])

print(f"\n--- DEAL SUMMARY ---")
print(f"Total Deals: {len(deal_list)}")
print(f"Entry Deals: {len(entries)}")
print(f"Exit Deals:  {len(exits)}")
print(f"Profitable Exits: {len(profitable)}")
print(f"Losing Exits:     {len(losing)}")
print(f"Net P&L: ${round(total_pnl, 2)}")
print(f"XAUUSD Deals: {len(xau_deals)}")
print(f"EURUSD Deals: {len(eur_deals)}")

print(f"\n--- POSITION SIZING ---")
print(f"Lot sizes used: {sorted(volumes)}")
print(f"Magic numbers:  {magic_numbers}")
print(f"Comments found: {comments}")

# Max single deal profit
if exits:
    max_profit_deal = max(exits, key=lambda x: x["profit"])
    print(f"\n--- BIGGEST SINGLE EXIT DEAL ---")
    print(json.dumps(max_profit_deal, indent=2))

# Hourly breakdown
hourly = defaultdict(lambda: {"deals": 0, "pnl": 0.0, "volume": 0.0})
for d in deal_list:
    hour = d["time"][:2]
    hourly[hour]["deals"] += 1
    hourly[hour]["pnl"] += d["profit"]
    hourly[hour]["volume"] += d["volume"]

print(f"\n--- HOURLY BREAKDOWN ---")
for hour in sorted(hourly.keys()):
    h = hourly[hour]
    print(f"  {hour}:xx | Deals: {h['deals']:3d} | P&L: ${round(h['pnl'],2):>12,.2f} | Volume: {round(h['volume'],2)}")

# Price range analysis
xau_exits = [d for d in exits if d["symbol"] == "XAUUSD"]
if xau_exits:
    prices = [d["price"] for d in xau_exits]
    print(f"\n--- XAUUSD PRICE RANGE ON 2026-07-03 ---")
    print(f"  Min exit price: {min(prices):.2f}")
    print(f"  Max exit price: {max(prices):.2f}")
    print(f"  Price range: {max(prices) - min(prices):.2f} (${(max(prices) - min(prices) * 100):.0f}/lot)")

# Check for unusual lots (>0.01)
unusual_lots = [d for d in deal_list if d["volume"] > 0.01]
if unusual_lots:
    print(f"\n⚠️  UNUSUAL LOT SIZES DETECTED ({len(unusual_lots)} deals > 0.01 lots):")
    for d in unusual_lots[:10]:
        print(f"  {d['time']} | {d['symbol']} | {d['action']} | Vol={d['volume']} | P&L=${d['profit']:.2f}")
else:
    print(f"\n✅ All deals at standard 0.01 lots")

# Check for abnormally large single profits
large_profits = [d for d in exits if abs(d["profit"]) > 100]
if large_profits:
    print(f"\n⚠️  LARGE SINGLE-DEAL PROFITS/LOSSES (>$100):")
    for d in sorted(large_profits, key=lambda x: x["profit"], reverse=True)[:10]:
        print(f"  {d['time']} | {d['symbol']} | {d['action']} | Vol={d['volume']} | P&L=${d['profit']:.2f}")
else:
    print(f"\nNo single deal > $100 profit/loss")

# Check cumulative by hour
cumulative = 0.0
print(f"\n--- CUMULATIVE P&L PROGRESSION ---")
for d in deal_list:
    cumulative += d["profit"]
    if d["profit"] != 0:
        pass
hourly_cum = []
cum = 0.0
for hour in sorted(hourly.keys()):
    cum += hourly[hour]["pnl"]
    hourly_cum.append((hour, round(cum, 2)))
    print(f"  After {hour}:xx → Cumulative: ${cum:,.2f}")

# Verdict
print(f"\n{'='*80}")
print("ROOT CAUSE ASSESSMENT:")
print(f"{'='*80}")
if unusual_lots:
    print("⚠️  CAUSE: LARGE LOT SIZES detected — may explain outlier P&L")
elif max([d["profit"] for d in exits] + [0]) > 10000:
    print("⚠️  CAUSE: ONE/FEW MASSIVE individual profits — position multiplication suspected")
else:
    print("📊 All lot sizes normal — P&L from HIGH TRADE COUNT + FAVORABLE VOLATILITY")

xau_pnl = sum(d["profit"] for d in xau_deals)
eur_pnl = sum(d["profit"] for d in eur_deals)
print(f"\nXAUUSD contribution: ${round(xau_pnl,2):,.2f}")
print(f"EURUSD contribution: ${round(eur_pnl,2):,.2f}")

# Print first 20 and last 20 deals for timeline
print(f"\n--- FIRST 20 DEALS ---")
for d in deal_list[:20]:
    print(f"  {d['time']} | {d['symbol']} | {d['action']} | Vol:{d['volume']} | Price:{d['price']:.2f} | P&L:${d['profit']:+.2f}")

print(f"\n--- LAST 20 DEALS ---")
for d in deal_list[-20:]:
    print(f"  {d['time']} | {d['symbol']} | {d['action']} | Vol:{d['volume']} | Price:{d['price']:.2f} | P&L:${d['profit']:+.2f}")

mt5.shutdown()
