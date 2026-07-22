#!/usr/bin/env python3
"""SIMPLE BOT - NO WATCHDOG - JUST TRADE"""
import sys, os, time
sys.path.insert(0, os.getcwd())

def main():
    import MetaTrader5 as mt5
    from config import settings as cfg
    
    print("\n🚀 SIMPLE BOT STARTING...")
    
    if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
        print(f"❌ MT5 Error")
        return
    
    print(f"✅ Connected | Balance: ${mt5.account_info().balance:.2f}\n")
    
    scan = 0
    while True:
        scan += 1
        print(f"🔍 SCAN #{scan}")
        
        for symbol in ["XAUUSD"]:  # Only Gold for now
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue
            
            info = mt5.symbol_info(symbol)
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 30)
            if rates is None:
                continue
            
            closes = [float(r[4]) for r in rates[-10:]]
            sma5 = sum(closes[-5:]) / 5
            sma10 = sum(closes) / 10
            
            direction = "BUY" if sma5 > sma10 else "SELL" if sma5 < sma10 else "WAIT"
            
            print(f"{symbol}: {tick.bid:.2f} | Signal: {direction}")
            
            if direction in ["BUY", "SELL"]:
                pos = mt5.positions_get(symbol=symbol)
                if pos and len(pos) > 0:
                    print(f"  ⏸️ Position exists\n")
                    continue
                
                order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
                price = tick.ask if direction == "BUY" else tick.bid
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": 0.01,
                    "type": order_type,
                    "price": price,
                    "sl": price - 0.50 if direction == "BUY" else price + 0.50,
                    "tp": price + 1.50 if direction == "BUY" else price - 1.50,
                    "deviation": 20,
                    "magic": 20250101,
                    "comment": "SimpleBot",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                print(f"  🚀 EXECUTING {direction}...")
                result = mt5.order_send(request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"  ✅✅✅ TRADE EXECUTED! Ticket: {result.order}\n")
                else:
                    print(f"  ❌ Failed: {result.comment}\n")
            else:
                print(f"  ⏸️ No signal\n")
        
        time.sleep(10)

if __name__ == "__main__":
    main()
