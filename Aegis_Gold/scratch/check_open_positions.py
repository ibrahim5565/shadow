import MetaTrader5 as mt5
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings as cfg

if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
    print("MT5 Init failed:", mt5.last_error())
    sys.exit(1)

positions = mt5.positions_get()
print(f"=== CURRENTLY OPEN MT5 POSITIONS: {len(positions) if positions else 0} ===")

naked_positions = []
if positions:
    for p in positions:
        direction = "BUY" if p.type == 0 else "SELL"
        print(f"Ticket #{p.ticket}: {p.symbol} {direction} lot={p.volume} open={p.price_open} sl={p.sl} tp={p.tp} pnl=${p.profit:.2f}")
        if p.sl == 0.0:
            naked_positions.append(p)

print(f"\nNaked positions (sl == 0): {len(naked_positions)}")
mt5.shutdown()
