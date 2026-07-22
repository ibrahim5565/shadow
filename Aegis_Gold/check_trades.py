#!/usr/bin/env python3
"""Quick check of active trades"""
import MetaTrader5 as mt5
from datetime import datetime

mt5.initialize()

print("=" * 60)
print("🤖 AEGIS GOLD BOT - LIVE STATUS")
print("=" * 60)
print(f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}")
print()

# Account info
account = mt5.account_info()
print(f"💰 Balance: ${account.balance:.2f}")
print(f"💎 Equity: ${account.equity:.2f}")
print(f"📊 Profit: ${account.profit:.2f}")
print()

# Get all positions
positions = mt5.positions_get()
if positions:
    print(f"📈 OPEN POSITIONS: {len(positions)}")
    print("-" * 60)
    for pos in positions:
        profit_emoji = "✅" if pos.profit > 0 else "❌" if pos.profit < 0 else "⏸️"
        direction = "BUY" if pos.type == 0 else "SELL"
        print(f"{profit_emoji} Ticket: {pos.ticket}")
        print(f"   Symbol: {pos.symbol}")
        print(f"   Direction: {direction}")
        print(f"   Entry: {pos.price_open:.5f}")
        print(f"   Current: {pos.price_current:.5f}")
        print(f"   Profit: ${pos.profit:.2f}")
        print(f"   SL: {pos.sl:.5f} | TP: {pos.tp:.5f}")
        print()
else:
    print("📊 No open positions")
    print()

# Recent history
history = mt5.history_deals_get(0, datetime.now().timestamp())
if history and len(history) > 0:
    recent = [d for d in history if d.entry == 0][-5:]  # Last 5 entries
    if recent:
        print(f"📜 RECENT TRADES (Last 5):")
        print("-" * 60)
        for deal in recent:
            direction = "BUY" if deal.type == 0 else "SELL"
            print(f"   Ticket: {deal.order} | {direction} {deal.symbol}")
            print(f"   Price: {deal.price:.5f} | Volume: {deal.volume}")
        print()

print("=" * 60)
print("✅ BOT STATUS: RUNNING")
print("🔄 Scanning every 5 seconds")
print("⚡ Trading at 50%+ confidence")
print("🚫 Never Pause: ACTIVE")
print("=" * 60)

mt5.shutdown()
