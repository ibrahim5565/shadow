"""
LIVE SELL PATH FORENSIC TRACER

This script instruments the ACTUAL production code path to identify
exactly where and why SELL trades are being blocked or converted to WAIT/BUY.

Requirements:
- Trace REAL bearish patterns from live MT5 data
- Log every decision point in the execution chain
- Compare BUY vs SELL paths side-by-side
- Identify the FIRST blocking condition

DO NOT rely on synthetic test patterns.
"""

import logging
import json
from datetime import datetime
from pathlib import Path

# Setup forensic logging
forensic_log_path = Path("logs/LIVE_SELL_FORENSIC.log")
forensic_log_path.parent.mkdir(exist_ok=True)

forensic_logger = logging.getLogger("LIVE_SELL_FORENSIC")
forensic_logger.setLevel(logging.DEBUG)

# File handler
fh = logging.FileHandler(forensic_log_path, mode='w')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s | %(message)s')
fh.setFormatter(formatter)
forensic_logger.addHandler(fh)

# Console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
forensic_logger.addHandler(ch)


class LiveSellDiagnostic:
    """Forensic tracer for live SELL execution path"""
    
    def __init__(self):
        self.traces = []
        self.sell_blocks = []
        self.buy_traces = []
        
    def trace_candle_retrieval(self, symbol, timeframe, candles_raw):
        """Step 1: MT5 Candle Retrieval"""
        forensic_logger.info("="*80)
        forensic_logger.info("STEP 1: MT5 CANDLE RETRIEVAL")
        forensic_logger.info("="*80)
        
        if candles_raw is None or len(candles_raw) == 0:
            forensic_logger.error("❌ NO CANDLES RETRIEVED FROM MT5")
            return
        
        # Check if DataFrame or dict/list
        try:
            if hasattr(candles_raw, 'iloc'):
                # Pandas DataFrame
                last_candle = candles_raw.iloc[-1]
                second_last = candles_raw.iloc[-2] if len(candles_raw) > 1 else None
            elif isinstance(candles_raw, list):
                last_candle = candles_raw[-1]
                second_last = candles_raw[-2] if len(candles_raw) > 1 else None
            else:
                forensic_logger.error(f"❌ Unknown candle format: {type(candles_raw)}")
                return
            
            forensic_logger.info(f"Symbol: {symbol}")
            forensic_logger.info(f"Timeframe: {timeframe}")
            forensic_logger.info(f"Total candles: {len(candles_raw)}")
            forensic_logger.info(f"\nLast candle ([-1] - FORMING):")
            forensic_logger.info(f"  Time: {last_candle.get('time') if isinstance(last_candle, dict) else getattr(last_candle, 'time', 'N/A')}")
            forensic_logger.info(f"  OHLC: O={last_candle.get('open') if isinstance(last_candle, dict) else getattr(last_candle, 'open', 'N/A'):.2f} "
                               f"H={last_candle.get('high') if isinstance(last_candle, dict) else getattr(last_candle, 'high', 'N/A'):.2f} "
                               f"L={last_candle.get('low') if isinstance(last_candle, dict) else getattr(last_candle, 'low', 'N/A'):.2f} "
                               f"C={last_candle.get('close') if isinstance(last_candle, dict) else getattr(last_candle, 'close', 'N/A'):.2f}")
            
            if second_last is not None:
                forensic_logger.info(f"\nSecond last candle ([-2] - COMPLETED):")
                forensic_logger.info(f"  Time: {second_last.get('time') if isinstance(second_last, dict) else getattr(second_last, 'time', 'N/A')}")
                forensic_logger.info(f"  OHLC: O={second_last.get('open') if isinstance(second_last, dict) else getattr(second_last, 'open', 'N/A'):.2f} "
                                   f"H={second_last.get('high') if isinstance(second_last, dict) else getattr(second_last, 'high', 'N/A'):.2f} "
                                   f"L={second_last.get('low') if isinstance(second_last, dict) else getattr(second_last, 'low', 'N/A'):.2f} "
                                   f"C={second_last.get('close') if isinstance(second_last, dict) else getattr(second_last, 'close', 'N/A'):.2f}")
            
            forensic_logger.info("✓ Candles retrieved successfully")
            
        except Exception as e:
            forensic_logger.error(f"❌ Error analyzing candles: {e}")
    
    def trace_pattern_detection(self, big_pattern, small_pattern=None):
        """Step 3-4: Pattern Detection & Direction"""
        forensic_logger.info("\n" + "="*80)
        forensic_logger.info("STEP 3-4: PATTERN DETECTION & DIRECTION")
        forensic_logger.info("="*80)
        
        if big_pattern is None:
            forensic_logger.error("❌ BIG_PATTERN IS NONE")
            return
        
        forensic_logger.info(f"Big Pattern Bias: {big_pattern.bias}")
        forensic_logger.info(f"Big Pattern Type: {big_pattern.pattern_type}")
        forensic_logger.info(f"Big Pattern Confidence: {big_pattern.confidence*100:.1f}%")
        forensic_logger.info(f"Invalidation Level: {big_pattern.invalidation_level:.2f}")
        
        # Check pattern direction logic
        if big_pattern.bias == "bullish":
            forensic_logger.info("✓ BULLISH PATTERN DETECTED → Should return BUY")
        elif big_pattern.bias == "bearish":
            forensic_logger.warning("⚠️  BEARISH PATTERN DETECTED → Should return SELL")
        else:
            forensic_logger.info("○ NEUTRAL PATTERN → Should return HOLD")
        
        if small_pattern:
            forensic_logger.info(f"\nSmall Pattern: {small_pattern.pattern_type}")
            forensic_logger.info(f"Small Pattern Direction: {small_pattern.direction}")
    
    def trace_decision(self, decision, pattern_direction):
        """Step 5: Decision Object"""
        forensic_logger.info("\n" + "="*80)
        forensic_logger.info("STEP 5: DECISION OBJECT")
        forensic_logger.info("="*80)
        
        forensic_logger.info(f"Pattern Direction: {pattern_direction}")
        forensic_logger.info(f"Decision Action: {decision.action}")
        forensic_logger.info(f"Decision Direction: {decision.direction}")
        forensic_logger.info(f"Decision Confidence: {decision.confidence}")
        forensic_logger.info(f"Decision Reason: {decision.reason}")
        
        # Check for direction mismatch
        if pattern_direction == "SELL" and decision.direction != "SELL":
            forensic_logger.error(f"🚨 DIRECTION CHANGED: Pattern={pattern_direction} → Decision={decision.direction}")
            self.sell_blocks.append({
                "stage": "DECISION_CREATION",
                "pattern_direction": pattern_direction,
                "decision_direction": decision.direction,
                "reason": decision.reason
            })
        
        if pattern_direction == "SELL" and decision.action == "WAIT":
            forensic_logger.error(f"🚨 SELL CONVERTED TO WAIT: Reason={decision.reason}")
            self.sell_blocks.append({
                "stage": "DECISION_ACTION",
                "pattern_direction": pattern_direction,
                "decision_action": decision.action,
                "reason": decision.reason
            })
    
    def trace_risk_validation(self, decision, risk_result, symbol, spread):
        """Step 6: Risk Validation"""
        forensic_logger.info("\n" + "="*80)
        forensic_logger.info("STEP 6: RISK VALIDATION")
        forensic_logger.info("="*80)
        
        forensic_logger.info(f"Symbol: {symbol}")
        forensic_logger.info(f"Spread: {spread:.1f} points")
        forensic_logger.info(f"Direction: {decision.direction}")
        forensic_logger.info(f"Lot: {decision.lot}")
        forensic_logger.info(f"SL Points: {decision.sl_points}")
        forensic_logger.info(f"TP Points: {decision.tp_points}")
        
        if risk_result:
            forensic_logger.info(f"Risk Result: {risk_result}")
        else:
            forensic_logger.warning("⚠️  No risk validation result")
    
    def trace_authorization(self, authorization, decision):
        """Step 7: Authorization"""
        forensic_logger.info("\n" + "="*80)
        forensic_logger.info("STEP 7: AUTHORIZATION")
        forensic_logger.info("="*80)
        
        if authorization is None:
            forensic_logger.error("❌ AUTHORIZATION IS NONE")
            return False
        
        if not authorization.authorized:
            forensic_logger.error(f"❌ AUTHORIZATION DENIED: {authorization.reason}")
            if decision.direction == "SELL":
                self.sell_blocks.append({
                    "stage": "AUTHORIZATION",
                    "direction": decision.direction,
                    "reason": authorization.reason
                })
            return False
        
        forensic_logger.info(f"✓ Authorization ID: {authorization.authorization_id}")
        forensic_logger.info(f"  Direction: {authorization.direction}")
        forensic_logger.info(f"  Lot: {authorization.lot:.2f}")
        forensic_logger.info(f"  Entry: {authorization.entry_price:.2f}")
        forensic_logger.info(f"  SL: {authorization.stop_loss:.2f}")
        forensic_logger.info(f"  TP: {authorization.take_profit:.2f}")
        
        return True
    
    def trace_order_construction(self, order_request, authorization):
        """Step 8: Order Construction"""
        forensic_logger.info("\n" + "="*80)
        forensic_logger.info("STEP 8: ORDER CONSTRUCTION")
        forensic_logger.info("="*80)
        
        if order_request is None:
            forensic_logger.error("❌ ORDER REQUEST IS NONE")
            return
        
        import MetaTrader5 as mt5
        
        forensic_logger.info(f"Symbol: {order_request.get('symbol')}")
        forensic_logger.info(f"Volume: {order_request.get('volume')}")
        forensic_logger.info(f"Type: {order_request.get('type')} " +
                           f"({'ORDER_TYPE_BUY' if order_request.get('type') == mt5.ORDER_TYPE_BUY else 'ORDER_TYPE_SELL'})")
        forensic_logger.info(f"Price: {order_request.get('price'):.2f}")
        forensic_logger.info(f"SL: {order_request.get('sl'):.2f}")
        forensic_logger.info(f"TP: {order_request.get('tp'):.2f}")
        
        # Check order type vs authorization direction
        auth_dir = authorization.direction if authorization else "UNKNOWN"
        order_type = order_request.get('type')
        
        if auth_dir == "SELL" and order_type == mt5.ORDER_TYPE_BUY:
            forensic_logger.error("🚨 CRITICAL: Authorization=SELL but ORDER_TYPE=BUY")
            self.sell_blocks.append({
                "stage": "ORDER_CONSTRUCTION",
                "authorization_direction": auth_dir,
                "order_type": "BUY",
                "error": "Direction mismatch"
            })
        elif auth_dir == "SELL" and order_type == mt5.ORDER_TYPE_SELL:
            forensic_logger.info("✓ SELL order type correct")
        
        # Validate SL/TP geometry for SELL
        if order_type == mt5.ORDER_TYPE_SELL:
            entry = order_request.get('price')
            sl = order_request.get('sl')
            tp = order_request.get('tp')
            
            if sl <= entry:
                forensic_logger.error(f"🚨 INVALID SELL SL: {sl:.2f} must be > entry {entry:.2f}")
            else:
                forensic_logger.info(f"✓ SELL SL valid: {sl:.2f} > entry {entry:.2f}")
            
            if tp >= entry:
                forensic_logger.error(f"🚨 INVALID SELL TP: {tp:.2f} must be < entry {entry:.2f}")
            else:
                forensic_logger.info(f"✓ SELL TP valid: {tp:.2f} < entry {entry:.2f}")
    
    def trace_mt5_execution(self, result, order_request):
        """Step 9-10: MT5 Execution & Retcode"""
        forensic_logger.info("\n" + "="*80)
        forensic_logger.info("STEP 9-10: MT5 EXECUTION & RETCODE")
        forensic_logger.info("="*80)
        
        if result is None:
            forensic_logger.error("❌ MT5 RESULT IS NONE")
            return
        
        forensic_logger.info(f"Retcode: {result.retcode}")
        forensic_logger.info(f"Deal: {result.deal}")
        forensic_logger.info(f"Order: {result.order}")
        forensic_logger.info(f"Volume: {result.volume}")
        forensic_logger.info(f"Price: {result.price}")
        forensic_logger.info(f"Comment: {result.comment}")
        
        import MetaTrader5 as mt5
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            forensic_logger.info("✓ TRADE EXECUTED SUCCESSFULLY")
            forensic_logger.info(f"  Ticket: {result.order}")
            
            order_type = order_request.get('type')
            if order_type == mt5.ORDER_TYPE_SELL:
                forensic_logger.info("✓ SELL ORDER EXECUTED")
        else:
            forensic_logger.error(f"❌ TRADE FAILED: {result.comment}")
            if order_request.get('type') == mt5.ORDER_TYPE_SELL:
                self.sell_blocks.append({
                    "stage": "MT5_EXECUTION",
                    "retcode": result.retcode,
                    "comment": result.comment
                })
    
    def summarize_blocks(self):
        """Summarize all SELL blocking points"""
        forensic_logger.info("\n" + "="*80)
        forensic_logger.info("SELL BLOCKING SUMMARY")
        forensic_logger.info("="*80)
        
        if not self.sell_blocks:
            forensic_logger.info("✓ No SELL blocks detected")
            return
        
        forensic_logger.error(f"🚨 {len(self.sell_blocks)} SELL BLOCKING POINT(S) FOUND:")
        for i, block in enumerate(self.sell_blocks, 1):
            forensic_logger.error(f"\nBlock #{i}:")
            for key, value in block.items():
                forensic_logger.error(f"  {key}: {value}")
    
    def save_trace(self, trace_data, filename="LIVE_SELL_TRACE.json"):
        """Save complete trace to JSON"""
        output_path = Path("logs") / filename
        output_path.parent.mkdir(exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(trace_data, f, indent=2, default=str)
        
        forensic_logger.info(f"\n✓ Trace saved to {output_path}")


# Global diagnostic instance
live_diagnostic = LiveSellDiagnostic()


def instrument_brain_decide():
    """Instrument the brain._decide_impl function"""
    forensic_logger.info("\n" + "="*80)
    forensic_logger.info("INSTRUMENTING BRAIN DECISION FUNCTION")
    forensic_logger.info("="*80)
    
    from brain import brain
    
    original_decide = brain._decide_impl
    
    def instrumented_decide(ticks, candles_m5, account, risk_mgr, session, spread, point, symbol="XAUUSD", candles_m1=None):
        """Instrumented version with full tracing"""
        
        # Trace candle retrieval
        live_diagnostic.trace_candle_retrieval(symbol, "M5", candles_m5)
        
        # Call original
        decision = original_decide(ticks, candles_m5, account, risk_mgr, session, spread, point, symbol, candles_m1)
        
        # Log decision outcome
        forensic_logger.info(f"\n>>> FINAL DECISION: action={decision.action} direction={decision.direction} reason={decision.reason}")
        
        return decision
    
    # Replace function
    brain._decide_impl = instrumented_decide
    forensic_logger.info("✓ Brain decide function instrumented")


if __name__ == "__main__":
    forensic_logger.info("="*80)
    forensic_logger.info("LIVE SELL DIAGNOSTIC INITIALIZED")
    forensic_logger.info("="*80)
    forensic_logger.info("This diagnostic will trace the REAL production execution path")
    forensic_logger.info("for both BUY and SELL patterns to identify blocking conditions.")
    forensic_logger.info("="*80)
