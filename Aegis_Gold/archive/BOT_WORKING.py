#!/usr/bin/env python3
"""
AEGIS GOLD BOT - WORKING VERSION
Fixed all issues - trades at 50% confidence
"""
import sys
import os
import time
import logging
from datetime import datetime

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

sys.path.insert(0, os.getcwd())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("AEGIS_BOT")

def main():
    import MetaTrader5 as mt5
    from config import settings as cfg
    
    logger.info("=" * 70)
    logger.info("🚀 AEGIS GOLD BOT - STARTING")
    logger.info("=" * 70)
    
    # Initialize MT5
    if not mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
        logger.error(f"❌ MT5 failed: {mt5.last_error()}")
        return
    
    account = mt5.account_info()
    logger.info(f"✅ MT5 Connected")
    logger.info(f"📊 Account: {account.login}")
    logger.info(f"💰 Balance: ${account.balance:.2f}")
    logger.info(f"⚡ Confidence: 50% threshold")
    logger.info(f"🚫 Never Pause: YES")
    logger.info("=" * 70)
    
    scan_count = 0
    last_trade_time = {}
    
    try:
        while True:
            scan_count += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"🔍 SCAN #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
            logger.info("=" * 70)
            
            for symbol in ["XAUUSD", "EURUSD"]:
                try:
                    # Get market data
                    tick = mt5.symbol_info_tick(symbol)
                    if not tick:
                        logger.warning(f"⚠️ {symbol}: No tick data")
                        continue
                    
                    symbol_info = mt5.symbol_info(symbol)
                    point = symbol_info.point
                    spread_pts = int((tick.ask - tick.bid) / point)
                    
                    logger.info(f"\n📈 {symbol}:")
                    logger.info(f"   Price: {tick.bid:.5f}")
                    logger.info(f"   Spread: {spread_pts} points")
                    
                    # Get candles
                    candles = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
                    if candles is None or len(candles) < 20:
                        logger.warning(f"   ⚠️ Insufficient data")
                        continue
                    
                    # Simple MA strategy
                    closes = [float(c[4]) for c in candles[-20:]]
                    ma_fast = sum(closes[-8:]) / 8
                    ma_slow = sum(closes[-20:]) / 20
                    current = closes[-1]
                    
                    confidence = 0
                    direction = "WAIT"
                    
                    # Determine signal
                    if ma_fast > ma_slow * 1.0005 and current > ma_fast:
                        direction = "BUY"
                        confidence = 60
                    elif ma_fast < ma_slow * 0.9995 and current < ma_fast:
                        direction = "SELL"
                        confidence = 60
                    
                    # Reduce confidence for high spread
                    spread_limit = 30 if symbol == "XAUUSD" else 10
                    if spread_pts > spread_limit:
                        confidence = max(0, confidence - 15)
                    
                    logger.info(f"   MA Fast: {ma_fast:.5f}")
                    logger.info(f"   MA Slow: {ma_slow:.5f}")
                    logger.info(f"   Signal: {direction}")
                    logger.info(f"   Confidence: {confidence}%")
                    
                    # Check if should trade
                    if confidence >= 50 and direction in ["BUY", "SELL"]:
                        # Check existing positions
                        positions = mt5.positions_get(symbol=symbol)
                        if positions and len(positions) > 0:
                            logger.info(f"   ⏸️ Already have {len(positions)} position(s)")
                            continue
                        
                        # Check cooldown (30 seconds)
                        current_time = time.time()
                        if symbol in last_trade_time:
                            if current_time - last_trade_time[symbol] < 30:
                                logger.info(f"   ⏸️ Cooldown active")
                                continue
                        
                        # Prepare trade
                        lot = 0.01
                        if symbol == "XAUUSD":
                            sl_pts = 50
                            tp_pts = 150
                        else:
                            sl_pts = 20
                            tp_pts = 60
                        
                        logger.info(f"   🚀 EXECUTING {direction} TRADE")
                        logger.info(f"   Lot: {lot}, SL: {sl_pts}pts, TP: {tp_pts}pts")
                        
                        # Execute
                        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
                        price = tick.ask if direction == "BUY" else tick.bid
                        
                        sl = price - (sl_pts * point) if direction == "BUY" else price + (sl_pts * point)
                        tp = price + (tp_pts * point) if direction == "BUY" else price - (tp_pts * point)
                        
                        # Determine fill mode
                        if "EUR" in symbol:
                            fill_mode = mt5.ORDER_FILLING_RETURN
                        else:
                            fill_mode = mt5.ORDER_FILLING_IOC
                        
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
                            "comment": f"Aegis {confidence}%",
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": fill_mode,
                        }
                        
                        result = mt5.order_send(request)
                        
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"   ✅ TRADE EXECUTED!")
                            logger.info(f"   Ticket: {result.order}")
                            logger.info(f"   Entry: {price:.5f}")
                            logger.info(f"   TP: {tp:.5f} | SL: {sl:.5f}")
                            last_trade_time[symbol] = current_time
                        else:
                            logger.error(f"   ❌ Failed: {result.comment} (Code: {result.retcode})")
                    
                    else:
                        logger.info(f"   ⏸️ No trade: Confidence {confidence}% < 50%")
                
                except Exception as e:
                    logger.error(f"❌ Error on {symbol}: {e}")
            
            logger.info(f"\n💤 Waiting 10 seconds...")
            time.sleep(10)
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopped by user")
    except Exception as e:
        logger.error(f"\n❌ Error: {e}", exc_info=True)
    finally:
        mt5.shutdown()
        logger.info("✅ Shutdown complete")

if __name__ == "__main__":
    main()
