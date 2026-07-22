import sys
import os
import MetaTrader5 as mt5
from dotenv import load_dotenv

# Load env variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

login = int(os.environ.get("MT5_LOGIN", 0))
password = os.environ.get("MT5_PASSWORD", "")
server = os.environ.get("MT5_SERVER", "")

print(f"Connecting to server: {server} with login: {login}...")

if not mt5.initialize(login=login, password=password, server=server):
    print("Failed to initialize MT5:", mt5.last_error())
    sys.exit(1)

for sym in ["XAUUSD", "XAUUSD.a", "XAUUSD.m", "EURUSD", "EURUSD.a", "EURUSD.m"]:
    info = mt5.symbol_info(sym)
    if info:
        print(f"--- Symbol: {sym} ---")
        print(f"  Point: {info.point}")
        print(f"  Digits: {info.digits}")
        print(f"  Trade Mode: {info.trade_mode}")
        print(f"  Execution Mode: {info.trade_exemode}")
        print(f"  Stops Level: {info.trade_stops_level}")
        print(f"  Freeze Level: {info.trade_freeze_level}")
        print(f"  Volume Min: {info.volume_min}")
        print(f"  Volume Max: {info.volume_max}")
        print(f"  Volume Step: {info.volume_step}")
        tick = mt5.symbol_info_tick(sym)
        if tick:
            print(f"  Bid: {tick.bid}, Ask: {tick.ask}, Spread: {tick.ask - tick.bid:.5f}")
            print(f"  Spread in Points: {(tick.ask - tick.bid) / info.point:.1f}")

mt5.shutdown()
