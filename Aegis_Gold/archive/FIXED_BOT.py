#!/usr/bin/env python3
"""
AEGIS GOLD - FIXED STABLE BOT
No watchdog chaos, no restart loops, just clean trading
"""
import sys
import os
import time
import logging
from datetime import datetime

# Add to path
sys.path.insert(0, os.getcwd())

# Configure logging (NO UNICODE)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('data/trading.log', encoding='utf-8')
    ]
)
logger = logging.getLogger("AEGIS")

def main():
    logger.info("="*70)
    logger.info("AEGIS GOLD - STARTING")
    logger.info("="*70)
    
    # Phase 1: Import validation
    try:
        import MetaTrader5 as mt5
        logger.info("MT5 module: OK")
    except ImportError as e:
        logger.error(f"MT5 module: FAILED - {e}")
        return False
    
    try:
        from config import settings as cfg
        logger.info("Config module: OK")
    except ImportError as e:
        logger.error(f"Config module: FAILED - {e}")
        return False
    
    # Phase 2: MT5 Connection
    logger.info("Connecting to MT5...")
    if not mt5.initialize(
        login=cfg.MT5_LOGIN,
        password=cfg.MT5_PASSWORD,
        server=cfg.MT5_SERVER
    ):
        error = mt5.last_error()
        logger.error(f"MT5 Connection: FAILED - {error}")
        return False
    
    logger.info("MT5 Connection: OK")
    
    # Phase 3: Verify Account
    account = mt5.account_info()
    if not account:
        logger.error("Account info: FAILED")
        mt5.shutdown()
        return False
    
    logger.info(f"Account: {account.login}")
    logger.info(f"Balance: ${account.balance:.2f}")
    logger.info(f"Equity: ${account.equity:.2f}")
    
    # Phase 4: Verify Market Data
    tick = mt5.symbol_info_tick("XAUUSD")
    if not tick:
        logger.error("Market data: FAILED")
        mt5.shutdown()
        return False
    
    logger.info(f"Market data: OK (XAUUSD: {tick.bid})")
    
    # Phase 5: Verify Candles
    rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, 10)
    if rates is None or len(rates) < 10:
        logger.error("Candle data: FAILED")
        mt5.shutdown()
        return False
    
    logger.info(f"Candle data: OK ({len(rates)} candles)")
    
    logger.info("="*70)
    logger.info("ALL SYSTEMS VALIDATED")
    logger.info("="*70)
    
    # Main trading loop
    scan = 0
    last_trade = {}
    
    try:
        while True:
            scan += 1
            logger.info("")
            logger.info("="*70)
            logger.info(f"SCAN #{scan} - {datetime.now().strftime('%H:%M:%S')}")
            logger.info("="*70)
            
            for symbol in ["XAUUSD", "EURUSD"]:
                try:
                    # Get tick
                    tick = mt5.symbol_info_tick(symbol)
                    if not tick:
                        logger.warning(f"{symbol}: No tick data")
                        continue
                    
                    # Get symbol info
                    info = mt5.symbol_info(symbol)
                    point = info.point
                    spread = int((tick.ask - tick.bid) / point)
                    
                    # Get candles
                    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 50)
                    if rates is None or len(rates) < 20:
                        logger.warning(f"{symbol}: Insufficient candles")
                        continue
                    
                    # Calculate indicators
                    closes = [float(r[4]) for r in rates[-20:]]
                    sma5 = sum(closes[-5:]) / 5
                    sma20 = sum(closes[-20:]) / 20
                    current = closes[-1]
                    
                    # Determine signal
                    direction = "WAIT"
                    confidence = 0
                    
                    if sma5 > sma20 * 1.001 and current > sma5:
                        direction = "BUY"
                        confidence = 55
                    elif sma5 < sma20 * 0.999 and current < sma5:
                        direction = "SELL"
                        confidence = 55
                    
                    logger.info(f"{symbol}:")
                    logger.info(f"  Price: {tick.bid:.5f} | Spread: {spread}pts")
                    logger.info(f"  SMA5: {sma5:.5f} | SMA20: {sma20:.5f}")
                    logger.info(f"  Signal: {direction} | Confidence: {confidence}%")
                    
                    # Execute trade if signal
                    if confidence >= 50 and direction in ["BUY", "SELL"]:
                        # Check existing positions
                        positions = mt5.positions_get(symbol=symbol)
                        if positions and len(positions) > 0:
                            logger.info(f"  Position exists - skipping")
                            continue
                        
                        # Cooldown check
                        now = time.time()
                        if symbol in last_trade and now - last_trade[symbol] < 30:
                            logger.info(f"  Cooldown active - skipping")
                            continue
                        
                        # Prepare order
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
                        logger.info(f"    Lot: {lot} | SL: {sl_pts}pts | TP: {tp_pts}pts")
                        
                        result = mt5.order_send(request)
                        
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"  TRADE EXECUTED! Ticket: {result.order}")
                            logger.info(f"    Entry: {price:.5f}")
                            logger.info(f"    TP: {tp:.5f} | SL: {sl:.5f}")
                            last_trade[symbol] = now
                        else:
                            logger.error(f"  Trade failed: {result.comment} (Code: {result.retcode})")
                    
                except Exception as e:
                    logger.error(f"{symbol} error: {e}")
                    continue
            
            logger.info("")
            logger.info("Next scan in 10 seconds...")
            time.sleep(10)
    
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user")
    except Exception as e:
        logger.error(f"Critical error: {e}", exc_info=True)
    finally:
        mt5.shutdown()
        logger.info("MT5 shutdown complete")
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
