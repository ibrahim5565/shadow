import MetaTrader5 as mt5
import sqlite3
import pandas as pd
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings as cfg

conn = sqlite3.connect(BASE_DIR / "data" / "trade_memory.db")
df = pd.read_sql_query("SELECT trade_id, symbol, entry_time, sl_points, tp_points FROM trades WHERE sl_points = 0 AND profit_usd IS NOT NULL ORDER BY entry_time ASC", conn)
conn.close()

print(f"Total trades with sl_points=0: {len(df)}")
sample_idx = [0, len(df)//4, len(df)//2, 3*len(df)//4, len(df)-1]
sample_tickets = df.iloc[sample_idx]["trade_id"].tolist()

if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
    print("MT5 Init failed:", mt5.last_error())
    sys.exit(1)

for t in sample_tickets:
    row = df[df["trade_id"] == t].iloc[0]
    orders = mt5.history_orders_get(position=t)
    deals = mt5.history_deals_get(position=t)
    print(f"=== Ticket #{t} ({row['symbol']} @ {row['entry_time']}) ===")
    if orders:
        for o in orders:
            print(f"  ORDER #{o.ticket}: type={o.type}, sl={o.sl}, tp={o.tp}, comment='{o.comment}'")
    else:
        print("  No orders found.")
    if deals:
        for d in deals:
            print(f"  DEAL #{d.ticket}: type={d.type}, price={d.price}, profit={d.profit}, comment='{d.comment}'")
    print()

mt5.shutdown()
