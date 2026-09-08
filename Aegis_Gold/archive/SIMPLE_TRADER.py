#!/usr/bin/env python3
"""
SIMPLE AEGIS GOLD TRADER
========================
Simplified trading bot that works without PyTorch
Takes trades at 50% confidence threshold
"""
import sys
import os
import time
import logging
from datetime import datetime

# Fix encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass

sys.path.insert(0, os.getcwd())

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("SIMPLE_TRADER")

def main():
    logger.info("=" * 60)
    logger.info("🚀 SIMPLE AEGIS GOLD TRADER")
    logger.info("=" * 60)
    
    try:
        import MetaTrader5 as mt5
        from config import settings as cfg
        
        # Initialize MT5
        logger.info("🔌 Connecting to MT5...")
        if not mt5.initialize(
            login=cfg.MT5_LOGIN,
            password=cfg.MT5_PASSWORD,
            server=cfg.MT5_SERVER
        ):
            logger.error(f"❌ MT5 failed: {mt5.last_error()}")
            return
        
        logger.info("✅ MT5 Connected")
        account = mt5.account_info()
        logger.info(f"📊 Account: {account.login}")
        logger.info(f"💰 Balance: ${account.balance:.2f}")
        logger.info(f"💎 Equity: ${account.equity:.2f}")
        logger.info("")
        logger.info("⚡ SETTINGS:")
        logger.info(f"   • Confidence Threshold: 50%")
        logger.info(f"   • Never Pause: YES")
        logger.info(f"   • Trading Mode: CONTINUOUS")
        logger.info(f"   • Symbols: {cfg.ACTIVE_SYMBOLS}")
        logger.info("=" * 60)
        
        # Import simplified brain components
        try:
            from brain.regime import analyze_regime
            from brain.structure import analyze_structure
            from brain.entry import analyze_entry
            logger.info("✅ Brain modules loaded")
        except Exception as e:
            logger.warning(f"⚠️ Brain modules error: {e}")
            logger.info("📊 Using simplified logic")
        
        # Trading loop
        scan_count = 0
        while True:
            scan_count += 1
            logger.info(f"\n🔍 SCAN #{scan_count} - {datetime.now().strftime('%H:%M:%S')}")
            
            for symbol in cfg.ACTIVE_SYMBOLS:
                try:
                    # Get market data
                    tick = mt5.symbol_info_tick(symbol)
                    if not tick:
                        continue
                    
                    symbol_info = mt5.symbol_info(symbol)
                    point = symbol_info.point
                    spread_pts = int((tick.ask - tick.bid) / point)
                    
                    logger.info(f"📈 {symbol}: Price={tick.bid:.2f}, Spread={spread_pts}pts")
                    
                    # Get candles
                    candles_m5 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
                    candles_m1 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 30)
                    
                    if candles_m5 is None or len(candles_m5) < 50:
                        logger.warning(f"⚠️ {symbol}: Insufficient candle data")
                        continue
                    
                    # Simple decision logic (without PyTorch)
                    confidence = 0
                    direction = "WAIT"
                    
                    # Calculate simple moving averages
                    closes = [c[4] for c in candles_m5[-20:]]  # Last 20 closes
                    ma_fast = sum(closes[-8:]) / 8   # 8-period MA
                    ma_slow = sum(closes[-21:-1]) / 20 if len(closes) >= 21 else sum(closes) / len(closes)  # 20-period MA
                    current_price = closes[-1]
                    
                    # Simple trend detection
                    if ma_fast > ma_slow and current_price > ma_fast:
                        direction = "BUY"
                        confidence = 55  # Base confidence
                    elif ma_fast < ma_slow and current_price < ma_fast:
                        direction = "SELL"
                        confidence = 55  # Base confidence
                    
                    # Adjust confidence based on spread
                    sym_cfg = cfg.get_symbol_config(symbol)
                    spread_limit = sym_cfg.get("spread_limits", {}).get("LONDON", 30)
                    
                    if spread_pts > spread_limit:
                        confidence = max(0, confidence - 10)
                        logger.info(f"   ⚠️ High spread ({spread_pts}pts) - confidence reduced")
                    
                    # Check if we should trade (50% threshold)
                    if confidence >= 50 and direction in ["BUY", "SELL"]:
                        logger.info(f"   ✅ SIGNAL: {direction} {symbol}")
                        logger.info(f"   📊 Confidence: {confidence}%")
                        logger.info(f"   💡 Reason: MA crossover + trend confirmation")
                        
                        # Check if we have open positions
                        positions = mt5.positions_get(symbol=symbol)
                        if positions and len(positions) > 0:
                            logger.info(f"   ⏸️ Already have {len(positions)} position(s) open")
                            continue
                        
                        # Calculate lot size
                        lot = sym_cfg.get("base_lot_demo", 0.01)
                        
                        # Calculate TP/SL
                        if symbol == "XAUUSD":
                            sl_pts = 50
                            tp_pts = 150
                        else:
                            sl_pts = 20
                            tp_pts = 60
                        
                        # Execute trade
                        logger.info(f"   🚀 EXECUTING TRADE...")
                        logger.info(f"   📊 Lot: {lot}, SL: {sl_pts}pts, TP: {tp_pts}pts")
                        
                        # Prepare order
                        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
                        price = tick.ask if direction == "BUY" else tick.bid
                        
                        sl_price = price - (sl_pts * point) if direction == "BUY" else price + (sl_pts * point)
                        tp_price = price + (tp_pts * point) if direction == "BUY" else price - (tp_pts * point)
                        
                        # Determine filling mode based on symbol
                        if "EURUSD" in symbol or "EUR" in symbol:
                            filling_mode = mt5.ORDER_FILLING_RETURN  # EURUSD uses RETURN mode
                        else:
                            filling_mode = mt5.ORDER_FILLING_IOC  # Gold uses IOC mode
                        
                        request = {
                            "action": mt5.TRADE_ACTION_DEAL,
                            "symbol": symbol,
                            "volume": lot,
                            "type": order_type,
                            "price": price,
                            "sl": sl_price,
                            "tp": tp_price,
                            "deviation": 20,
                            "magic": 20250101,
                            "comment": f"Aegis {confidence}%",
                            "type_time": mt5.ORDER_TIME_GTC,
                            "type_filling": filling_mode,
                        }
                        
                        result = mt5.order_send(request)
                        
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            logger.info(f"   ✅ TRADE EXECUTED!")
                            logger.info(f"   🎫 Ticket: {result.order}")
                            logger.info(f"   💰 Entry: {price:.5f}")
                            logger.info(f"   🎯 TP: {tp_price:.5f}")
                            logger.info(f"   🛡️ SL: {sl_price:.5f}")
                        else:
                            logger.error(f"   ❌ Trade failed: {result.comment}")
                            logger.error(f"   📋 Code: {result.retcode}")
                    
                    else:
                        if direction == "WAIT":
                            logger.info(f"   ⏸️ No clear signal")
                        else:
                            logger.info(f"   ⏸️ Confidence too low: {confidence}% < 50%")
                
                except Exception as e:
                    logger.error(f"❌ Error processing {symbol}: {e}")
                    continue
            
            # Wait before next scan
            logger.info(f"\n💤 Waiting {cfg.SCAN_INTERVAL}s before next scan...")
            time.sleep(cfg.SCAN_INTERVAL)
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Bot stopped by user")
        mt5.shutdown()
    
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        mt5.shutdown()

if __name__ == "__main__":
    logger.info("🤖 AEGIS GOLD - SIMPLE TRADER")
    logger.info("🚫 NEVER PAUSE MODE")
    logger.info("")
    main()
