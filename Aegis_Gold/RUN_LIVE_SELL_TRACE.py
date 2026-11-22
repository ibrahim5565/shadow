"""
LIVE SELL PATH TRACER

Instruments the ACTUAL production bot to trace real SELL patterns.
Run this BEFORE starting the bot to enable forensic logging.

This will:
1. Patch the pattern detection function
2. Patch the decision creation function
3. Patch the MT5 order execution
4. Log every step of SELL patterns vs BUY patterns
"""

import sys
import os

# Add project to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

print("="*80)
print("LIVE SELL PATH TRACER - Instrumenting Production Bot")
print("="*80)

# Import the diagnostic module
from LIVE_SELL_DIAGNOSTIC import live_diagnostic, forensic_logger
import logging

# Patch brain.decide to add tracing
from brain import brain
from brain.smc_engine import detect_big_pattern as original_detect_big_pattern

forensic_logger.info("Patching detect_big_pattern function...")

def traced_detect_big_pattern(symbol="XAUUSD", candles_m5=None, candles_h1=None, point=0.01, require_htf_sweep=False):
    """Traced version of detect_big_pattern"""
    
    # Call original
    result = original_detect_big_pattern(symbol, candles_m5, candles_h1, point, require_htf_sweep)
    
    # Trace the pattern
    live_diagnostic.trace_pattern_detection(result)
    
    # Log critical info
    if result.bias == "bearish":
        forensic_logger.warning(f"🎯 BEARISH PATTERN DETECTED: {result.pattern_type} conf={result.confidence*100:.1f}%")
    elif result.bias == "bullish":
        forensic_logger.info(f"✓ Bullish pattern detected: {result.pattern_type} conf={result.confidence*100:.1f}%")
    
    return result

# Replace the function
import brain.smc_engine
brain.smc_engine.detect_big_pattern = traced_detect_big_pattern
forensic_logger.info("✓ detect_big_pattern patched")

# Patch brain.decide
original_decide = brain.decide

def traced_decide(ticks, candles_m5, account, risk_mgr, session, spread, point, symbol="XAUUSD", candles_m1=None):
    """Traced version of brain.decide"""
    
    # Trace candles
    live_diagnostic.trace_candle_retrieval(symbol, "M5", candles_m5)
    
    # Call original
    decision = original_decide(ticks, candles_m5, account, risk_mgr, session, spread, point, symbol, candles_m1)
    
    # Determine pattern direction from the decision's thought log or attributes
    pattern_direction = "UNKNOWN"
    if hasattr(decision, 'direction'):
        pattern_direction = decision.direction
    
    # Trace decision
    live_diagnostic.trace_decision(decision, pattern_direction)
    
    # Log SELL specifically
    if decision.direction == "SELL":
        forensic_logger.warning(f"🎯 DECISION IS SELL: action={decision.action} confidence={decision.confidence} reason={decision.reason}")
    
    return decision

brain.decide = traced_decide
forensic_logger.info("✓ brain.decide patched")

# Patch MT5Gateway.execute_order
from modules.mt5_gateway import MT5Gateway
original_execute_order = MT5Gateway.execute_order

def traced_execute_order(self, symbol, direction, lot, tp_pts, sl_pts, session="LONDON"):
    """Traced version of execute_order"""
    
    forensic_logger.info(f"\n>>> MT5 EXECUTION REQUEST: {direction} {symbol} lot={lot} sl={sl_pts} tp={tp_pts}")
    
    # Build order request first
    try:
        order_request = self.build_order_request(symbol, direction, lot, tp_pts, sl_pts)
        
        # Create a mock authorization for tracing
        from dataclasses import dataclass
        @dataclass
        class MockAuth:
            direction: str
            lot: float
            entry_price: float
            stop_loss: float
            take_profit: float
        
        mock_auth = MockAuth(
            direction=direction,
            lot=lot,
            entry_price=order_request.get('price', 0),
            stop_loss=order_request.get('sl', 0),
            take_profit=order_request.get('tp', 0)
        )
        
        # Trace order construction
        live_diagnostic.trace_order_construction(order_request, mock_auth)
        
    except Exception as e:
        forensic_logger.error(f"❌ Order construction failed: {e}")
    
    # Call original
    result, latency, slippage = original_execute_order(self, symbol, direction, lot, tp_pts, sl_pts, session)
    
    # Trace result
    if result:
        live_diagnostic.trace_mt5_execution(result, order_request if 'order_request' in locals() else {})
    
    return result, latency, slippage

MT5Gateway.execute_order = traced_execute_order
forensic_logger.info("✓ MT5Gateway.execute_order patched")

print("\n" + "="*80)
print("✅ LIVE SELL TRACER INITIALIZED")
print("="*80)
print("All production functions patched with forensic logging.")
print("Log file: logs/LIVE_SELL_FORENSIC.log")
print("\nNow start the bot normally:")
print("  python core/main.py")
print("\nThe tracer will log every SELL pattern detected and where it gets blocked.")
print("="*80)

# Keep the script running so patches remain active
if __name__ == "__main__":
    print("\n⚠️  Run this BEFORE starting the bot, or import it in main.py")
    print("Add this line at the top of core/main.py:")
    print("  import RUN_LIVE_SELL_TRACE  # Enable SELL forensic tracing")
