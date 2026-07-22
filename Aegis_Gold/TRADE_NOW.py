#!/usr/bin/env python3
"""
AEGIS GOLD - AGGRESSIVE TRADER
Takes trades immediately - 40% confidence threshold
"""
import sys
import os
import time
import logging
from datetime import datetime

sys.path.insert(0, os.getcwd())

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger("TRADE_NOW")

def main():
    import MetaTrader5 as mt5
    from config import settings as cfg
    
    print("="*70)
    print("🚀 AEGIS GOLD - AGGRESSIVE TRADER")
    print("⚡ 40% Confidence - MORE TRADES")
    print("="*70)
    
    if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
        print(f"❌ MT5 failed: {mt5.last_error()}")
        return
    
    print(f"✅ Connected | Account: {mt5.account_info().login}")
    print(f"💰 Balance: ${mt5.account_info().balance:.2f}")
    print("="*70)
    
    scan = 0
    last_trade = {}
    
    while True:
        scan += 1
        print(f"\n🔍 SCAN #{scan} - {datetime.now().strftime('%H:%M:%S')}")
        print("-"*70)
        
        for symbol in ["XAUUSD", "EURUSD"]:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                continue
            
            info = mt5.symbol_info(symbol)
            point = info.point
            spread = int((tick.ask - tick.bid) / point)
            
            # Get candles
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
            if rates is None or len(rates) < 20:
                continue
            
            # Simple strategy
            closes = [float(r[4]) for r in rates[-20:]]
            sma5 = sum(closes[-5:]) / 5
            sma20 = sum(closes[-20:]) / 20
            current = closes[-1]
            
            direction = "WAIT"
            confidence = 0
            
            # More sensitive signals
            if sma5 > sma20 and current > sma5:
                direction = "BUY"
                confidence = 50
            elif sma5 < sma20 and current < sma5:
                direction = "SELL"
                confidence = 50
            
            print(f"\n{symbol}: {tick.bid:.5f} | Spread: {spread}pts")
            print(f"  SMA5: {sma5:.5f} | SMA20: {sma20:.5f}")
            print(f"  Signal: {direction} | Confidence: {confidence}%")
            
            # Execute if confidence >= 40%
            if confidence >= 40 and direction in ["BUY", "SELL"]:
                # Check positions
                pos = mt5.positions_get(symbol=symbol)
                if pos and len(pos) > 0:
                    print(f"  ⏸️ Position exists")
                    continue
                
                # Cooldown check
                now = time.time()
                if symbol in last_trade and now - last_trade[symbol] < 20:
                    print(f"  ⏸️ Cooldown")
                    continue
                
                # Trade parameters
                lot = 0.01
                sl_pts = 50 if symbol == "XAUUSD" else 20
                tp_pts = 150 if symbol == "XAUUSD" else 60
                
                order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
                price = tick.ask if direction == "BUY" else tick.bid
                sl = price - (sl_pts * point) if direction == "BUY" else price + (sl_pts * point)
                tp = price + (tp_pts * point) if direction == "BUY" else price - (tp_pts * point)
                
                # Fill mode - Try FOK first, fallback to RETURN
                symbol_info_obj = mt5.symbol_info(symbol)
                filling = symbol_info_obj.filling_mode
                
                # Choose appropriate fill mode
                if filling & 2:  # FOK supported
                    fill = mt5.ORDER_FILLING_FOK
                elif filling & 1:  # IOC supported
                    fill = mt5.ORDER_FILLING_IOC
                else:  # RETURN
                    fill = mt5.ORDER_FILLING_RETURN
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lot,
                    "type": order_type,
                    "price": price,
                    "sl": sl,
                    "tp": tp,
                    "deviation": 20,
                    "magic": 20250101,
                    "comment": f"Aegis{confidence}%",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": fill,
                }
                
                print(f"  🚀 EXECUTING {direction} | Lot:{lot} SL:{sl_pts} TP:{tp_pts}")
                result = mt5.order_send(request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"  ✅ SUCCESS! Ticket: {result.order}")
                    print(f"     Entry: {price:.5f} | TP: {tp:.5f} | SL: {sl:.5f}")
                    last_trade[symbol] = now
                else:
                    print(f"  ❌ Failed: {result.comment}")
        
        print(f"\n💤 Next scan in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    main()
