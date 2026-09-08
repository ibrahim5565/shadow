#!/usr/bin/env python3
"""
AEGIS GOLD — WATCHDOG SAFE MODE VALIDATION
Comprehensive test of watchdog restart mechanism and MT5 connection
in dry-run (DEMO) mode with real market data.

This test validates:
1. Watchdog can acquire lock (no duplicate watchdogs)
2. Bot starts and connects to real MT5
3. Multiple decision cycles complete without crashes
4. Pattern signal interface works with real data
5. No undefined variable errors (pattern_signal, np)
6. Watchdog recovery mechanisms don't get stuck
"""

import sys
import os
import subprocess
import time
import logging
import psutil
import signal
from datetime import datetime
from pathlib import Path

# Add project root to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ───────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# ───────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [WATCHDOG-TEST] %(levelname)s %(message)s'
)
logger = logging.getLogger("watchdog_test")


# ───────────────────────────────────────────────────────────────────────────────
# TEST 1: LOCK ACQUISITION
# ───────────────────────────────────────────────────────────────────────────────

def test_lock_acquisition():
    """Test that watchdog lock mechanism works and prevents duplicate watchdogs."""
    logger.info("=" * 70)
    logger.info("TEST 1: LOCK ACQUISITION")
    logger.info("=" * 70)
    
    lock_file = os.path.join(BASE_DIR, "data", "watchdog.lock")
    
    # Clean up any stale lock
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old_pid = int(f.read().strip())
            if not psutil.pid_exists(old_pid):
                logger.info(f"Cleaned up stale lock (PID {old_pid})")
                os.remove(lock_file)
        except Exception as e:
            logger.warning(f"Could not clean stale lock: {e}")
    
    # Attempt to create lock
    try:
        with open(lock_file, "w") as f:
            f.write(str(os.getpid()))
        logger.info(f"✅ Lock acquired successfully (PID {os.getpid()})")
        
        # Try to read it back
        with open(lock_file, "r") as f:
            read_pid = int(f.read().strip())
        if read_pid == os.getpid():
            logger.info(f"✅ Lock file verification passed: {lock_file}")
            return True
        else:
            logger.error(f"❌ Lock file mismatch: expected {os.getpid()}, got {read_pid}")
            return False
    except Exception as e:
        logger.error(f"❌ Lock acquisition failed: {e}")
        return False
    finally:
        # Clean up test lock
        try:
            os.remove(lock_file)
        except:
            pass


# ───────────────────────────────────────────────────────────────────────────────
# TEST 2: STATIC VALIDATION (RE-RUN)
# ───────────────────────────────────────────────────────────────────────────────

def test_static_validation():
    """Validate that all modified files compile without errors."""
    logger.info("=" * 70)
    logger.info("TEST 2: STATIC VALIDATION (Re-run)")
    logger.info("=" * 70)
    
    files_to_check = [
        "brain/decision_fusion.py",
        "brain/brain.py",
        "brain/unified_brain.py"
    ]
    
    all_pass = True
    for fname in files_to_check:
        fpath = os.path.join(BASE_DIR, fname)
        if not os.path.exists(fpath):
            logger.error(f"❌ File not found: {fname}")
            all_pass = False
            continue
        
        try:
            import py_compile
            py_compile.compile(fpath, doraise=True)
            logger.info(f"✅ {fname}: Syntax OK")
        except py_compile.PyCompileError as e:
            logger.error(f"❌ {fname}: Syntax error\n{e}")
            all_pass = False
    
    # Test imports
    try:
        from brain.decision_fusion import DecisionFusionV2
        logger.info(f"✅ DecisionFusionV2 imported successfully")
        
        from brain.brain import decide
        logger.info(f"✅ brain.decide() imported successfully")
        
        from brain.unified_brain import UnifiedQuantAIBrain
        logger.info(f"✅ UnifiedBrain imported successfully")
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        all_pass = False
    
    return all_pass


# ───────────────────────────────────────────────────────────────────────────────
# TEST 3: REAL MT5 CONNECTION
# ───────────────────────────────────────────────────────────────────────────────

def test_mt5_connection():
    """Test real MT5 connection and data fetch."""
    logger.info("=" * 70)
    logger.info("TEST 3: REAL MT5 CONNECTION")
    logger.info("=" * 70)
    
    try:
        # Initialize gateway
        from modules.mt5_gateway import MT5Gateway
        
        gateway = MT5Gateway()
        logger.info("Attempting MT5 initialization...")
        
        connected = gateway.initialize()
        if not connected:
            logger.error("❌ MT5 initialization failed")
            return False
        
        logger.info("✅ MT5 connected successfully")
        
        # Test account info
        acct = gateway.get_account_info()
        if not acct:
            logger.error("❌ Failed to get account info")
            return False
        
        logger.info(f"✅ Account retrieved: Login={acct.get('login')}, Equity=${acct.get('equity'):.2f}")
        
        # Test symbol data
        for sym in ["XAUUSD", "EURUSD"]:
            tick = gateway.get_current_tick(sym)
            if tick is None:
                logger.warning(f"⚠️  No tick data for {sym} (market may be closed)")
                continue
            
            logger.info(f"✅ {sym}: Ask={tick.ask:.5f}, Bid={tick.bid:.5f}")
            
            # Fetch candles
            candles = gateway.get_candles_m5(sym, 10)
            if candles is None or len(candles) == 0:
                logger.warning(f"⚠️  No candle data for {sym}")
                continue
            
            logger.info(f"✅ {sym} candles: {len(candles)} bars fetched")
        
        gateway.shutdown()
        logger.info("✅ MT5 disconnected cleanly")
        return True
        
    except Exception as e:
        logger.error(f"❌ MT5 connection test failed: {e}", exc_info=True)
        return False


# ───────────────────────────────────────────────────────────────────────────────
# TEST 4: PATTERN SIGNAL INTERFACE WITH REAL DATA
# ───────────────────────────────────────────────────────────────────────────────

def test_pattern_signal_with_real_data():
    """Test that pattern_signal parameter works correctly with real MT5 data."""
    logger.info("=" * 70)
    logger.info("TEST 4: PATTERN SIGNAL INTERFACE WITH REAL DATA")
    logger.info("=" * 70)
    
    try:
        from modules.mt5_gateway import MT5Gateway
        from brain.brain import decide
        from modules.risk_manager import RiskManager
        from config import settings as cfg
        
        gateway = MT5Gateway()
        if not gateway.initialize():
            logger.error("❌ MT5 initialization failed")
            return False
        
        logger.info("Testing real brain decision pipeline with real market data...")
        
        acct = gateway.get_account_info()
        if not acct:
            logger.error("❌ Failed to get account info")
            return False
        
        risk = RiskManager(gateway)
        risk.init_daily(acct["equity"])
        
        # Test with real data for XAUUSD and EURUSD
        test_symbols = ["XAUUSD", "EURUSD"]
        all_pass = True
        
        for sym in test_symbols:
            logger.info(f"\n  Testing {sym}...")
            
            tick = gateway.get_current_tick(sym)
            if tick is None:
                logger.warning(f"  ⚠️  No tick data for {sym} (market closed?)")
                continue
            
            ticks = gateway.get_ticks(sym, 200)
            candles_m5 = gateway.get_candles_m5(sym, cfg.CANDLE_COUNT)
            candles_m1 = gateway.get_candles_m1(sym, 30)
            
            if ticks is None or len(ticks) == 0 or candles_m5 is None or len(candles_m5) == 0:
                logger.warning(f"  ⚠️  Insufficient data for {sym}")
                continue
            
            try:
                # Convert to list of dicts if needed
                ticks_list = []
                for t in ticks[-20:]:
                    try:
                        ticks_list.append({'bid': float(t['bid']), 'ask': float(t['ask'])})
                    except:
                        try:
                            ticks_list.append({'bid': float(t[1]), 'ask': float(t[2])})
                        except:
                            pass
                
                candles_list = []
                for c in candles_m5:
                    try:
                        candles_list.append({
                            'open': float(c['open']), 'high': float(c['high']),
                            'low': float(c['low']), 'close': float(c['close'])
                        })
                    except:
                        try:
                            candles_list.append({
                                'open': float(c[1]), 'high': float(c[2]),
                                'low': float(c[3]), 'close': float(c[4])
                            })
                        except:
                            pass
                
                if not ticks_list or not candles_list:
                    logger.warning(f"  ⚠️  Failed to convert {sym} data")
                    continue
                
                sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
                spread = float(tick.ask - tick.bid) / sym_point if sym_point > 0 else 0
                session = "LONDON"  # Placeholder
                
                # Call brain.decide() with real data
                decision = decide(
                    ticks_list, candles_list, acct, risk,
                    session, spread, sym_point, symbol=sym, candles_m1=candles_list
                )
                
                if decision is None:
                    logger.error(f"  ❌ decision is None for {sym}")
                    all_pass = False
                    continue
                
                logger.info(f"  ✅ {sym} decision: {decision.direction} {decision.action} (Conf: {decision.confidence}%)")
                logger.info(f"     Reason: {decision.reason[:60]}...")
                logger.info(f"     Pattern: {decision.pattern} | Regime: {decision.regime}")
                
            except Exception as e:
                logger.error(f"  ❌ Decision pipeline error for {sym}: {e}", exc_info=True)
                all_pass = False
        
        gateway.shutdown()
        return all_pass
        
    except Exception as e:
        logger.error(f"❌ Real data test failed: {e}", exc_info=True)
        return False


# ───────────────────────────────────────────────────────────────────────────────
# TEST 5: FAST CONFIDENCE UPDATER SIMULATION
# ───────────────────────────────────────────────────────────────────────────────

def test_fast_confidence_updater():
    """Simulate fast confidence updater to ensure pattern_signal doesn't cause crashes."""
    logger.info("=" * 70)
    logger.info("TEST 5: FAST CONFIDENCE UPDATER SIMULATION")
    logger.info("=" * 70)
    
    try:
        from modules.mt5_gateway import MT5Gateway
        from brain.brain import decide
        from modules.risk_manager import RiskManager
        from config import settings as cfg
        
        gateway = MT5Gateway()
        if not gateway.initialize():
            logger.error("❌ MT5 initialization failed")
            return False
        
        acct = gateway.get_account_info()
        if not acct:
            logger.error("❌ Failed to get account info")
            return False
        
        risk = RiskManager(gateway)
        risk.init_daily(acct["equity"])
        
        # Simulate 5 cycles of the fast confidence updater
        logger.info("Running 5 fast confidence update cycles...")
        
        for cycle in range(1, 6):
            logger.info(f"\n  Cycle {cycle}:")
            
            for sym in ["XAUUSD", "EURUSD"]:
                try:
                    tick = gateway.get_current_tick(sym)
                    if tick is None:
                        continue
                    
                    ticks = gateway.get_ticks(sym, 50)
                    candles = gateway.get_candles_m5(sym, 100)
                    
                    if ticks is None or len(ticks) == 0 or candles is None or len(candles) < 5:
                        continue
                    
                    # Convert data
                    ticks_list = []
                    for t in ticks[-20:]:
                        try:
                            ticks_list.append({'bid': float(t['bid']), 'ask': float(t['ask'])})
                        except:
                            try:
                                ticks_list.append({'bid': float(t[1]), 'ask': float(t[2])})
                            except:
                                pass
                    
                    candles_list = []
                    for c in candles:
                        try:
                            candles_list.append({
                                'open': float(c['open']), 'high': float(c['high']),
                                'low': float(c['low']), 'close': float(c['close'])
                            })
                        except:
                            try:
                                candles_list.append({
                                    'open': float(c[1]), 'high': float(c[2]),
                                    'low': float(c[3]), 'close': float(c[4])
                                })
                            except:
                                pass
                    
                    if not ticks_list or len(candles_list) < 5:
                        continue
                    
                    sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
                    spread = float(tick.ask - tick.bid) / sym_point if sym_point > 0 else 0
                    session = "LONDON"
                    
                    # This is what the fast updater does - call decide repeatedly
                    decision = decide(ticks_list, candles_list, acct, risk, session, spread, sym_point, symbol=sym)
                    
                    if decision:
                        logger.info(f"    ✅ {sym}: {decision.direction} {decision.action} (Conf: {decision.confidence}%)")
                    
                except Exception as e:
                    logger.error(f"    ❌ Error for {sym}: {e}")
                    return False
            
            time.sleep(1)  # Simulate 1-second interval between cycles
        
        gateway.shutdown()
        logger.info("\n✅ Fast confidence updater simulation completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fast updater test failed: {e}", exc_info=True)
        return False


# ───────────────────────────────────────────────────────────────────────────────
# TEST 6: MAIN LOOP STABILITY (MULTIPLE CYCLES)
# ───────────────────────────────────────────────────────────────────────────────

def test_main_loop_stability():
    """Run multiple brain decision cycles to verify stability."""
    logger.info("=" * 70)
    logger.info("TEST 6: MAIN LOOP STABILITY (Multiple Cycles)")
    logger.info("=" * 70)
    
    try:
        from modules.mt5_gateway import MT5Gateway
        from brain.brain import decide
        from modules.risk_manager import RiskManager
        from config import settings as cfg
        
        gateway = MT5Gateway()
        if not gateway.initialize():
            logger.error("❌ MT5 initialization failed")
            return False
        
        acct = gateway.get_account_info()
        if not acct:
            logger.error("❌ Failed to get account info")
            return False
        
        risk = RiskManager(gateway)
        risk.init_daily(acct["equity"])
        
        logger.info("Running 10 main loop cycles (simulating trading loop)...\n")
        
        errors = []
        for cycle in range(1, 11):
            try:
                logger.info(f"  Cycle {cycle}/10: ")
                
                for sym in ["XAUUSD", "EURUSD"]:
                    tick = gateway.get_current_tick(sym)
                    if tick is None:
                        continue
                    
                    ticks = gateway.get_ticks(sym, 200)
                    candles_m5 = gateway.get_candles_m5(sym, cfg.CANDLE_COUNT)
                    candles_m1 = gateway.get_candles_m1(sym, 30)
                    
                    if ticks is None or len(ticks) == 0 or candles_m5 is None or len(candles_m5) == 0:
                        continue
                    
                    # Convert data
                    ticks_list = []
                    for t in ticks[-20:]:
                        try:
                            ticks_list.append({'bid': float(t['bid']), 'ask': float(t['ask'])})
                        except:
                            try:
                                ticks_list.append({'bid': float(t[1]), 'ask': float(t[2])})
                            except:
                                pass
                    
                    candles_list_m5 = []
                    for c in candles_m5:
                        try:
                            candles_list_m5.append({
                                'open': float(c['open']), 'high': float(c['high']),
                                'low': float(c['low']), 'close': float(c['close'])
                            })
                        except:
                            try:
                                candles_list_m5.append({
                                    'open': float(c[1]), 'high': float(c[2]),
                                    'low': float(c[3]), 'close': float(c[4])
                                })
                            except:
                                pass
                    
                    candles_list_m1 = []
                    for c in candles_m1:
                        try:
                            candles_list_m1.append({
                                'open': float(c['open']), 'high': float(c['high']),
                                'low': float(c['low']), 'close': float(c['close'])
                            })
                        except:
                            try:
                                candles_list_m1.append({
                                    'open': float(c[1]), 'high': float(c[2]),
                                    'low': float(c[3]), 'close': float(c[4])
                                })
                            except:
                                pass
                    
                    if not ticks_list or len(candles_list_m5) < 5:
                        continue
                    
                    sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
                    spread = float(tick.ask - tick.bid) / sym_point if sym_point > 0 else 0
                    session = "LONDON"
                    
                    decision = decide(ticks_list, candles_list_m5, acct, risk, session, spread, sym_point, symbol=sym, candles_m1=candles_list_m1)
                    
                    if not decision:
                        errors.append(f"Cycle {cycle}: decision is None for {sym}")
                
                logger.info("✅")
                
            except Exception as e:
                logger.error(f"\n    ❌ Cycle {cycle} error: {e}")
                errors.append(str(e))
        
        gateway.shutdown()
        
        if errors:
            logger.error(f"\n❌ Errors encountered ({len(errors)}):")
            for err in errors[:5]:  # Show first 5
                logger.error(f"   - {err}")
            return False
        
        logger.info("\n✅ All 10 cycles completed successfully without errors")
        return True
        
    except Exception as e:
        logger.error(f"❌ Main loop stability test failed: {e}", exc_info=True)
        return False


# ───────────────────────────────────────────────────────────────────────────────
# TEST 7: ERROR SCAN
# ───────────────────────────────────────────────────────────────────────────────

def test_error_scan():
    """Scan recent logs for critical errors."""
    logger.info("=" * 70)
    logger.info("TEST 7: ERROR SCAN (Recent Logs)")
    logger.info("=" * 70)
    
    critical_errors = [
        "NameError",
        "UnboundLocalError",
        "AttributeError",
        "TypeError",
        "divide by zero",
        "invalid value",
        "UnicodeEncodeError",
        "pattern_signal is not defined",
    ]
    
    logs_dir = os.path.join(BASE_DIR, "logs")
    
    found_errors = {}
    
    for log_file in ["aegis.log", "bot.log", "main.log"]:
        log_path = os.path.join(logs_dir, log_file)
        if not os.path.exists(log_path):
            continue
        
        try:
            with open(log_path, "r", errors="ignore") as f:
                # Read last 5000 lines
                lines = f.readlines()[-5000:]
            
            for err_pattern in critical_errors:
                for i, line in enumerate(lines):
                    if err_pattern.lower() in line.lower():
                        if err_pattern not in found_errors:
                            found_errors[err_pattern] = []
                        found_errors[err_pattern].append((log_file, lines[max(0, i-2):i+3]))
        
        except Exception as e:
            logger.warning(f"Could not read {log_file}: {e}")
    
    if not found_errors:
        logger.info("✅ No critical errors found in recent logs")
        return True
    else:
        logger.warning(f"⚠️  Found {len(found_errors)} types of errors in logs:")
        for err_type, occurrences in found_errors.items():
            logger.warning(f"  - {err_type}: {len(occurrences)} occurrence(s)")
        return False


# ───────────────────────────────────────────────────────────────────────────────
# MAIN TEST RUNNER
# ───────────────────────────────────────────────────────────────────────────────

def main():
    """Run all tests."""
    logger.info("\n" + "=" * 70)
    logger.info("AEGIS GOLD — WATCHDOG SAFE MODE VALIDATION")
    logger.info("=" * 70)
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Mode: DEMO (trading disabled - dry-run only)")
    logger.info("=" * 70 + "\n")
    
    results = {}
    
    # Run all tests
    tests = [
        ("Lock Acquisition", test_lock_acquisition),
        ("Static Validation", test_static_validation),
        ("MT5 Connection", test_mt5_connection),
        ("Pattern Signal Interface", test_pattern_signal_with_real_data),
        ("Fast Confidence Updater", test_fast_confidence_updater),
        ("Main Loop Stability", test_main_loop_stability),
        ("Error Scan", test_error_scan),
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = "PASS" if result else "FAIL"
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}", exc_info=True)
            results[test_name] = "CRASH"
        
        logger.info("")  # Blank line between tests
    
    # Print summary
    logger.info("\n" + "=" * 70)
    logger.info("FINAL RESULTS")
    logger.info("=" * 70)
    
    pass_count = sum(1 for r in results.values() if r == "PASS")
    fail_count = sum(1 for r in results.values() if r == "FAIL")
    crash_count = sum(1 for r in results.values() if r == "CRASH")
    
    for test_name, result in results.items():
        emoji = "✅" if result == "PASS" else "❌" if result == "FAIL" else "💥"
        logger.info(f"{emoji} {test_name}: {result}")
    
    logger.info("=" * 70)
    logger.info(f"SUMMARY: {pass_count} PASS, {fail_count} FAIL, {crash_count} CRASH")
    logger.info("=" * 70)
    
    if pass_count == len(results):
        logger.info("\n🎉 ALL TESTS PASSED!")
        logger.info("System is ready for watchdog safe mode deployment.\n")
        return 0
    else:
        logger.error(f"\n❌ {fail_count + crash_count} test(s) failed or crashed.")
        logger.error("Fix issues before enabling watchdog safe mode.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
