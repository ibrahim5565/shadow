import MetaTrader5 as mt5
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings as cfg

if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
    print("MT5 Init failed:", mt5.last_error())
    sys.exit(1)

tickets = [152393396394, 152393395673, 152393395162, 152393309088, 152393254242, 152393212818, 152393191561]
print(f"Checking {len(tickets)} tickets in MT5 history...\n")

for t in tickets:
    deals = mt5.history_deals_get(position=t)
    orders = mt5.history_orders_get(position=t)
    print(f"=== Ticket #{t} ===")
    if orders:
        for o in orders:
            print(f"  ORDER #{o.ticket}: symbol={o.symbol}, type={o.type}, price_open={o.price_open}, sl={o.sl}, tp={o.tp}, state={o.state}, comment='{o.comment}'")
    else:
        print("  No orders found in history.")
        
    if deals:
        for d in deals:
            print(f"  DEAL  #{d.ticket}: symbol={d.symbol}, type={d.type}, entry={d.entry}, price={d.price}, volume={d.volume}, profit={d.profit}, comment='{d.comment}'")
    else:
        print("  No deals found in history.")
    print()

mt5.shutdown()
