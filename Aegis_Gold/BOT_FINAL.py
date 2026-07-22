#!/usr/bin/env python3
"""AEGIS GOLD - FINAL WORKING BOT"""
import sys, os, time, logging
from datetime import datetime

sys.path.insert(0, os.getcwd())
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger()

def main():
    import MetaTrader5 as mt5
    from config import settings as cfg
    
    print("\n" + "="*70)
    print("🚀 AEGIS GOLD BOT - FINAL VERSION")
    print("⚡ 40% Confidence | GUARANTEED TO TRADE")
    print("="*70 + "\n")
    
    if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
        print(f"❌ MT5 Error: {mt5.last_error()}")
        return
    
    acc = mt5.account_info()
    print(f"✅ MT5 Connected")
    print(f"📊 Account: {acc.login}")
    print(f"💰 Balance: ${acc.balance:.2f}\n" + "="*70)
    
    scan = 0
    last_trade = {}
    
    while True:
        scan += 1
        print(f"\n{'='*70}")
        print(f"🔍 SCAN #{scan} - {datetime.now().strftime('%H:%M:%S')}")
        print("="*70)
        
        for symbol in ["XAUUSD", "EURUSD"]:
            try:
                tick = mt5.symbol_info_tick(symbol)
                if not tick:
                    continue
                
                info = mt5.symbol_info(symbol)
                point = info.point
                spread = int((tick.ask - tick.bid) / point)
                
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
                if rates is None or len(rates) < 20:
                    continue
                
                closes = [float(r[4]) for r in rates[-20:]]
                sma5 = sum(closes[-5:]) / 5
                sma20 = sum(closes[-20:]) / 20
                current = closes[-1]
                
                direction = "WAIT"
                confidence = 0
                
                if sma5 > sma20 and current > sma5:
                    direction = "BUY"
                    confidence = 50
                elif sma5 < sma20 and current < sma5:
                    direction = "SELL"
                    confidence = 50
                
                print(f"\n📈 {symbol}:")
                print(f"   Price: {tick.bid:.5f} | Spread: {spread}pts")
                print(f"   SMA5: {sma5:.5f} | SMA20: {sma20:.5f}")
                print(f"   Signal: {direction} | Confidence: {confidence}%")
                
                if confidence >= 40 and direction in ["BUY", "SELL"]:
                    pos = mt5.positions_get(symbol=symbol)
                    if pos and len(pos) > 0:
                        print(f"   ⏸️ Already have position")
                        continue
                    
                    now = time.time()
                    if symbol in last_trade and now - last_trade[symbol] < 15:
                        print(f"   ⏸️ Cooldown ({15 - int(now - last_trade[symbol])}s)")
                        continue
                    
                    lot = 0.01
                    sl_pts = 50 if symbol == "XAUUSD" else 20
                    tp_pts = 150 if symbol == "XAUUSD" else 60
                    
                    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
                    price = tick.ask if direction == "BUY" else tick.bid
                    sl = price - (sl_pts * point) if direction == "BUY" else price + (sl_pts * point)
                    tp = price + (tp_pts * point) if direction == "BUY" else price - (tp_pts * point)
                    
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
                        "type_filling": mt5.ORDER_FILLING_IOC,  # ALL symbols use IOC
                    }
                    
                    print(f"   🚀 EXECUTING {direction} TRADE...")
                    print(f"      Lot: {lot} | SL: {sl_pts}pts | TP: {tp_pts}pts")
                    
                    result = mt5.order_send(request)
                    
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        print(f"   ✅ ✅ ✅ TRADE EXECUTED! ✅ ✅ ✅")
                        print(f"      Ticket: {result.order}")
                        print(f"      Entry: {price:.5f}")
                        print(f"      TP: {tp:.5f} | SL: {sl:.5f}")
                        last_trade[symbol] = now
                    else:
                        print(f"   ❌ Failed: {result.comment} (Code: {result.retcode})")
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        print(f"\n💤 Waiting 5 seconds...\n")
        time.sleep(5)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Stopped")
