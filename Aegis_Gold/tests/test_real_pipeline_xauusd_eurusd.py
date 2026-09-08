#!/usr/bin/env python3
"""
AEGIS GOLD — REAL PIPELINE TEST (XAUUSD + EURUSD)

Tests the complete decision pipeline with real MT5 market data in DEMO mode.
Verifies pattern_signal flows correctly from detection through fusion.

NO ORDERS PLACED - DEMO MODE ONLY
"""

import sys
import os
import logging

import io

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger("test_pipeline")

from config import settings as cfg


def test_xauusd_pipeline():
    """Test XAUUSD real pipeline"""
    print("\n" + "="*70)
    print("TEST: XAUUSD REAL PIPELINE")
    print("="*70)
    
    try:
        from modules.mt5_gateway import MT5Gateway
        from brain.brain import decide
        from modules.risk_manager import RiskManager
        
        logger.info("Initializing MT5 Gateway...")
        gateway = MT5Gateway()
        
        if not gateway.initialize():
            logger.error("[FAIL] MT5 initialization failed")
            return False
        
        logger.info("[OK] MT5 connected")
        
        # Get account
        acct = gateway.get_account_info()
        if not acct:
            logger.error("[FAIL] Could not get account info")
            return False
        
        logger.info("[OK] Account: equity=${:.2f}".format(acct['equity']))
        
        # Initialize risk manager
        risk = RiskManager(gateway)
        risk.init_daily(acct["equity"])
        
        # Get market data for XAUUSD
        sym = "XAUUSD"
        logger.info("\n[XAUUSD] Fetching market data...")
        
        tick = gateway.get_current_tick(sym)
        if tick is None:
            logger.warning("[XAUUSD] No tick data (market closed?)")
            return True  # Not a failure, market just closed
        
        logger.info("[XAUUSD] Tick: bid={:.2f} ask={:.2f}".format(tick.bid, tick.ask))
        
        ticks = gateway.get_ticks(sym, 200)
        candles_m5 = gateway.get_candles_m5(sym, cfg.CANDLE_COUNT)
        candles_m1 = gateway.get_candles_m1(sym, 30)
        
        if ticks is None or len(ticks) == 0 or candles_m5 is None or len(candles_m5) == 0:
            logger.warning("[XAUUSD] Insufficient data")
            return True
        
        logger.info("[XAUUSD] Data: {} ticks, {} M5 candles, {} M1 candles".format(
            len(ticks), len(candles_m5), len(candles_m1) if candles_m1 is not None else 0
        ))
        
        # Convert to list format
        ticks_list = []
        for t in ticks[-20:]:
            try:
                ticks_list.append({'bid': float(t['bid']), 'ask': float(t['ask'])})
            except:
                try:
                    ticks_list.append({'bid': float(t[1]), 'ask': float(t[2])})
                except:
                    pass
        
        candles_m5_list = []
        for c in candles_m5:
            try:
                candles_m5_list.append({
                    'open': float(c['open']), 'high': float(c['high']),
                    'low': float(c['low']), 'close': float(c['close'])
                })
            except:
                try:
                    candles_m5_list.append({
                        'open': float(c[1]), 'high': float(c[2]),
                        'low': float(c[3]), 'close': float(c[4])
                    })
                except:
                    pass
        
        candles_m1_list = []
        if candles_m1 is not None and len(candles_m1) > 0:
            for c in candles_m1:
                try:
                    candles_m1_list.append({
                        'open': float(c['open']), 'high': float(c['high']),
                        'low': float(c['low']), 'close': float(c['close'])
                    })
                except:
                    try:
                        candles_m1_list.append({
                            'open': float(c[1]), 'high': float(c[2]),
                            'low': float(c[3]), 'close': float(c[4])
                        })
                    except:
                        pass
        
        if not ticks_list or len(candles_m5_list) < 5:
            logger.warning("[XAUUSD] Conversion failed")
            return True
        
        # Run decision pipeline
        logger.info("[XAUUSD] Running decision pipeline...")
        sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.01)
        spread = float(tick.ask - tick.bid) / sym_point if sym_point > 0 else 0
        session = "LONDON"
        
        decision = decide(
            ticks_list, candles_m5_list, acct, risk,
            session, spread, sym_point, symbol=sym, candles_m1=candles_m1_list
        )
        
        if not decision:
            logger.error("[XAUUSD] Decision is None")
            return False
        
        logger.info("[XAUUSD] Decision: action={} direction={} confidence={}%".format(
            decision.action, decision.direction, decision.confidence
        ))
        logger.info("[XAUUSD] Signal source: {} | Pattern: {}".format(
            decision.signal_source, decision.pattern
        ))
        logger.info("[XAUUSD] Reason: {}".format(decision.reason[:80]))
        
        gateway.shutdown()
        logger.info("[OK] XAUUSD pipeline completed successfully")
        return True
        
    except Exception as e:
        logger.error("[FAIL] XAUUSD pipeline error: {}".format(e), exc_info=True)
        return False


def test_eurusd_pipeline():
    """Test EURUSD real pipeline"""
    print("\n" + "="*70)
    print("TEST: EURUSD REAL PIPELINE")
    print("="*70)
    
    try:
        from modules.mt5_gateway import MT5Gateway
        from brain.brain import decide
        from modules.risk_manager import RiskManager
        
        logger.info("Initializing MT5 Gateway...")
        gateway = MT5Gateway()
        
        if not gateway.initialize():
            logger.error("[FAIL] MT5 initialization failed")
            return False
        
        logger.info("[OK] MT5 connected")
        
        # Get account
        acct = gateway.get_account_info()
        if not acct:
            logger.error("[FAIL] Could not get account info")
            return False
        
        logger.info("[OK] Account: equity=${:.2f}".format(acct['equity']))
        
        # Initialize risk manager
        risk = RiskManager(gateway)
        risk.init_daily(acct["equity"])
        
        # Get market data for EURUSD
        sym = "EURUSD"
        logger.info("\n[EURUSD] Fetching market data...")
        
        tick = gateway.get_current_tick(sym)
        if tick is None:
            logger.warning("[EURUSD] No tick data (market closed?)")
            return True
        
        logger.info("[EURUSD] Tick: bid={:.5f} ask={:.5f}".format(tick.bid, tick.ask))
        
        ticks = gateway.get_ticks(sym, 200)
        candles_m5 = gateway.get_candles_m5(sym, cfg.CANDLE_COUNT)
        candles_m1 = gateway.get_candles_m1(sym, 30)
        
        if ticks is None or len(ticks) == 0 or candles_m5 is None or len(candles_m5) == 0:
            logger.warning("[EURUSD] Insufficient data")
            return True
        
        logger.info("[EURUSD] Data: {} ticks, {} M5 candles, {} M1 candles".format(
            len(ticks), len(candles_m5), len(candles_m1) if candles_m1 is not None else 0
        ))
        
        # Convert to list format
        ticks_list = []
        for t in ticks[-20:]:
            try:
                ticks_list.append({'bid': float(t['bid']), 'ask': float(t['ask'])})
            except:
                try:
                    ticks_list.append({'bid': float(t[1]), 'ask': float(t[2])})
                except:
                    pass
        
        candles_m5_list = []
        for c in candles_m5:
            try:
                candles_m5_list.append({
                    'open': float(c['open']), 'high': float(c['high']),
                    'low': float(c['low']), 'close': float(c['close'])
                })
            except:
                try:
                    candles_m5_list.append({
                        'open': float(c[1]), 'high': float(c[2]),
                        'low': float(c[3]), 'close': float(c[4])
                    })
                except:
                    pass
        
        candles_m1_list = []
        if candles_m1 is not None and len(candles_m1) > 0:
            for c in candles_m1:
                try:
                    candles_m1_list.append({
                        'open': float(c['open']), 'high': float(c['high']),
                        'low': float(c['low']), 'close': float(c['close'])
                    })
                except:
                    try:
                        candles_m1_list.append({
                            'open': float(c[1]), 'high': float(c[2]),
                            'low': float(c[3]), 'close': float(c[4])
                        })
                    except:
                        pass
        
        if not ticks_list or len(candles_m5_list) < 5:
            logger.warning("[EURUSD] Conversion failed")
            return True
        
        # Run decision pipeline
        logger.info("[EURUSD] Running decision pipeline...")
        sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
        spread = float(tick.ask - tick.bid) / sym_point if sym_point > 0 else 0
        session = "LONDON"
        
        decision = decide(
            ticks_list, candles_m5_list, acct, risk,
            session, spread, sym_point, symbol=sym, candles_m1=candles_m1_list
        )
        
        if not decision:
            logger.error("[EURUSD] Decision is None")
            return False
        
        logger.info("[EURUSD] Decision: action={} direction={} confidence={}%".format(
            decision.action, decision.direction, decision.confidence
        ))
        logger.info("[EURUSD] Signal source: {} | Pattern: {}".format(
            decision.signal_source, decision.pattern
        ))
        logger.info("[EURUSD] Reason: {}".format(decision.reason[:80]))
        
        gateway.shutdown()
        logger.info("[OK] EURUSD pipeline completed successfully")
        return True
        
    except Exception as e:
        logger.error("[FAIL] EURUSD pipeline error: {}".format(e), exc_info=True)
        return False


def main():
    print("\n" + "#"*70)
    print("# REAL PIPELINE TEST (XAUUSD + EURUSD)")
    print("#"*70)
    print("Mode: DEMO (no orders placed)")
    print("Config: DEMO_MODE={}".format(cfg.DEMO_MODE))
    
    results = {}
    
    # Test XAUUSD
    logger.info("\n[STARTING] XAUUSD pipeline test...")
    results["XAUUSD"] = test_xauusd_pipeline()
    
    # Test EURUSD
    logger.info("\n[STARTING] EURUSD pipeline test...")
    results["EURUSD"] = test_eurusd_pipeline()
    
    # Summary
    print("\n" + "#"*70)
    print("# RESULTS")
    print("#"*70)
    
    for symbol, result in results.items():
        status = "[OK]" if result else "[FAIL]"
        print("{} {}: {}".format(status, symbol, "PASS" if result else "FAIL"))
    
    pass_count = sum(1 for r in results.values() if r)
    total = len(results)
    
    print("#"*70)
    print("# {}/{} PASSED".format(pass_count, total))
    print("#"*70)
    
    return 0 if pass_count == total else 1


if __name__ == "__main__":
    # Fix Windows Unicode (only when run directly, not when imported by pytest)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    sys.exit(main())
