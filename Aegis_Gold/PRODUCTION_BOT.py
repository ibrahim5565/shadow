#!/usr/bin/env python3
"""
AEGIS GOLD - PRODUCTION BOT
Stable, validated, no watchdog chaos
"""
import sys
import os
import time
import logging
from datetime import datetime

sys.path.insert(0, os.getcwd())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger()

def validate_system():
    """Validate all systems before starting"""
    logger.info("="*70)
    logger.info("AEGIS GOLD - SYSTEM VALIDATION")
    logger.info("="*70)
    
    # Import MT5
    try:
        import MetaTrader5 as mt5
        logger.info("[1/5] MT5 Module: OK")
    except ImportError as e:
        logger.error(f"[1/5] MT5 Module: FAILED - {e}")
        return None
    
    # Import Config
    try:
        from config import settings as cfg
        logger.info("[2/5] Config Module: OK")
    except ImportError as e:
        logger.error(f"[2/5] Config Module: FAILED - {e}")
        return None
    
    # Connect MT5
    logger.info("[3/5] Connecting to MT5...")
    if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
        logger.error(f"[3/5] MT5 Connection: FAILED - {mt5.last_error()}")
        return None
    
    account = mt5.account_info()
    if not account:
        logger.error("[3/5] MT5 Connection: No account info")
        mt5.shutdown()
        return None
    
    logger.info(f"[3/5] MT5 Connection: OK (Account: {account.login})")
    logger.info(f"      Balance: ${account.balance:.2f} | Equity: ${account.equity:.2f}")
    
    # Verify Market Data
    tick = mt5.symbol_info_tick("XAUUSD")
    if not tick:
        logger.error("[4/5] Market Data: FAILED")
        mt5.shutdown()
        return None
    
    logger.info(f"[4/5] Market Data: OK (XAUUSD: {tick.bid:.2f})")
    
    # Verify Candles
    rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 10)
    if rates is None or len(rates) < 10:
        logger.error("[5/5] Candle Data: FAILED")
        mt5.shutdown()
        return None
    
    logger.info(f"[5/5] Candle Data: OK ({len(rates)} candles)")
    
    logger.info("="*70)
    logger.info("ALL SYSTEMS VALIDATED - READY TO TRADE")
    logger.info("="*70 + "\n")
    
    return mt5

def trade_loop(mt5):
    """Main trading loop"""
    scan = 0
    last_trade = {}
    
    while True:
        scan += 1
        logger.info(f"\n{'='*70}")
        logger.info(f"SCAN #{scan} - {datetime.now().strftime('%H:%M:%S')}")
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
                
                closes = [float(r[4]) for r in rates[-20:]]
                sma5 = sum(closes[-5:]) / 5
                sma20 = sum(closes[-20:]) / 20
                
                direction = "WAIT"
                confidence = 0
                
                if sma5 > sma20 * 1.001 and closes[-1] > sma5:
                    direction = "BUY"
                    confidence = 55
                elif sma5 < sma20 * 0.999 and closes[-1] < sma5:
                    direction = "SELL"
                    confidence = 55
                
                logger.info(f"\n{symbol}:")
                logger.info(f"  Price: {tick.bid:.5f} | Spread: {spread}pts")
                logger.info(f"  Signal: {direction} | Confidence: {confidence}%")
                
                if confidence >= 50 and direction in ["BUY", "SELL"]:
                    positions = mt5.positions_get(symbol=symbol)
                    if positions and len(positions) > 0:
                        logger.info(f"  Status: Position exists")
                        continue
                    
                    now = time.time()
                    if symbol in last_trade and now - last_trade[symbol] < 30:
                        logger.info(f"  Status: Cooldown active")
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
                    
                    logger.info(f"  EXECUTING {direction} TRADE...")
                    result = mt5.order_send(request)
                    
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"  SUCCESS! Ticket: {result.order}")
                        logger.info(f"  Entry: {price:.5f} | TP: {tp:.5f} | SL: {sl:.5f}")
                        last_trade[symbol] = now
                    else:
                        logger.error(f"  FAILED: {result.comment}")
            
            except Exception as e:
                logger.error(f"{symbol} Error: {e}")
        
        logger.info(f"\nNext scan in 10 seconds...\n")
        time.sleep(10)

def main():
    mt5 = validate_system()
    if not mt5:
        logger.error("\nVALIDATION FAILED - CANNOT START\n")
        return 1
    
    try:
        trade_loop(mt5)
    except KeyboardInterrupt:
        logger.info("\nShutdown requested")
    except Exception as e:
        logger.error(f"\nCritical error: {e}")
    finally:
        mt5.shutdown()
        logger.info("Shutdown complete")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
