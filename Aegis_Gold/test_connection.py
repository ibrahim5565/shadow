import MetaTrader5 as mt5
from config import settings as cfg

print("Testing MT5 connection...")
if mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
    print("✅ MT5 Connected")
    print(f"Account: {mt5.account_info().login}")
    print(f"Balance: ${mt5.account_info().balance:.2f}")
    
    # Test data
    tick = mt5.symbol_info_tick("XAUUSD")
    if tick:
        print(f"✅ XAUUSD Price: {tick.bid}")
    else:
        print("❌ Cannot get XAUUSD data")
        
    candles = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 10)
    if candles is not None:
        print(f"✅ Candles: {len(candles)} received")
    else:
        print("❌ Cannot get candles")
    
    mt5.shutdown()
else:
    print(f"❌ MT5 failed: {mt5.last_error()}")
