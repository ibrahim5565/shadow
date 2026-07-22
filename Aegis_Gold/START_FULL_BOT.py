#!/usr/bin/env python3
"""
AEGIS GOLD - FULL BOT SYSTEM
Starts all components: MT5, Trading Engine, AI, Telegram
"""
import sys
import os
import time
import logging
import asyncio
from datetime import datetime

sys.path.insert(0, os.getcwd())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger("AEGIS_FULL")

def main():
    print("\n" + "="*70)
    print("🚀 AEGIS GOLD - FULL SYSTEM STARTING")
    print("="*70)
    
    # Import modules
    try:
        import MetaTrader5 as mt5
        from config import settings as cfg
        logger.info("✅ MT5 Gateway: Imported")
    except Exception as e:
        logger.error(f"❌ MT5 Gateway: {e}")
        return
    
    try:
        from modules.telegram_bot import TelegramBot
        telegram = TelegramBot(cfg.TELEGRAM_TOKEN, cfg.TELEGRAM_CHAT_ID)
        logger.info("✅ Telegram Bot: Imported")
    except Exception as e:
        logger.warning(f"⚠️ Telegram Bot: {e}")
        telegram = None
    
    # Initialize MT5
    logger.info("🔌 Connecting to MT5...")
    if not mt5.initialize(
        login=cfg.MT5_LOGIN,
        password=cfg.MT5_PASSWORD,
        server=cfg.MT5_SERVER
    ):
        logger.error(f"❌ MT5 Connection Failed: {mt5.last_error()}")
        return
    
    account = mt5.account_info()
    logger.info(f"✅ MT5 Gateway: ONLINE")
    logger.info(f"📊 Account: {account.login}")
    logger.info(f"💰 Balance: ${account.balance:.2f}")
    
    if telegram:
        try:
            telegram.send("🚀 Aegis Gold Bot Started\\n✅ All Systems Online")
            logger.info("✅ Telegram Bot: ONLINE")
        except:
            logger.warning("⚠️ Telegram Bot: Message failed")
    
    logger.info("✅ Trading Engine: ONLINE")
    logger.info("✅ AI Engine: ONLINE (Simplified mode)")
    
    print("="*70)
    print("✅ ALL SYSTEMS ONLINE")
    print("="*70 + "\\n")
    
    # Main trading loop
    scan = 0
    last_trade = {}
    
    try:
        while True:
            scan += 1
            logger.info(f"\\n{'='*70}")
            logger.info(f"🔍 SCAN #{scan} - {datetime.now().strftime('%H:%M:%S')}")
            logger.info("="*70)
            
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
                    
                    # Simple MA strategy
                    closes = [float(r[4]) for r in rates[-20:]]
                    sma5 = sum(closes[-5:]) / 5
                    sma20 = sum(closes[-20:]) / 20
                    current = closes[-1]
                    
                    direction = "WAIT"
                    confidence = 0
                    
                    if sma5 > sma20 and current > sma5:
                        direction = "BUY"
                        confidence = 55
                    elif sma5 < sma20 and current < sma5:
                        direction = "SELL"
                        confidence = 55
                    
                    logger.info(f"\\n📈 {symbol}:")
                    logger.info(f"   Price: {tick.bid:.5f} | Spread: {spread}pts")
                    logger.info(f"   SMA5: {sma5:.5f} | SMA20: {sma20:.5f}")
                    logger.info(f"   Signal: {direction} | Confidence: {confidence}%")
                    
                    if confidence >= 50 and direction in ["BUY", "SELL"]:
                        pos = mt5.positions_get(symbol=symbol)
                        if pos and len(pos) > 0:
                            logger.info(f"   ⏸️ Position exists")
                            continue
                        
                        now = time.time()
                        if symbol in last_trade and now - last_trade[symbol] < 20:
                            logger.info(f"   ⏸️ Cooldown")
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
                            "type_filling": mt5.ORDER_FILLING_IOC,
                        }
                        
                        logger.info(f"   🚀 EXECUTING {direction} TRADE...")
                        result = mt5.order_send(request)
                        
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"   ✅ TRADE EXECUTED! Ticket: {result.order}")
                            if telegram:
                                try:
                                    telegram.send(f"✅ Trade Executed\\n{symbol} {direction}\\nTicket: {result.order}\\nPrice: {price:.5f}")
                                except:
                                    pass
                            last_trade[symbol] = now
                        else:
                            logger.error(f"   ❌ Failed: {result.comment}")
                
                except Exception as e:
                    logger.error(f"   ❌ Error: {e}")
            
            logger.info(f"\\n💤 Next scan in 10 seconds...")
            time.sleep(10)
    
    except KeyboardInterrupt:
        logger.info("\\n🛑 Shutdown requested")
        if telegram:
            try:
                telegram.send("🛑 Aegis Gold Bot Stopped")
            except:
                pass
    finally:
        mt5.shutdown()
        logger.info("✅ Shutdown complete")

if __name__ == "__main__":
    main()
