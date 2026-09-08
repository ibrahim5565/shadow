#!/usr/bin/env python3
"""
AEGIS GOLD — PATTERN SIGNAL DATA-FLOW TRACE
Complete tracing of pattern detection → fusion integration

This script traces:
1. Pattern detection in SMC Pattern Engine
2. Pattern normalization in brain_decide()
3. How pattern reaches DecisionFusionV2
4. Actual data flowing through the pipeline
"""

import sys
import os
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Setup detailed tracing
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger("pattern_trace")

# Patch to add detailed tracing
original_fuse = None

def traced_fuse(self, smc_signal=None, scalp_signal=None, ml_prediction=None, rl_action="WAIT",
                rl_confidence=0, stat_analysis=None, macro_blackout=False, regime_type="UNKNOWN",
                regime_confidence=0.0, regime_ambiguous=False, calibration_penalty=0,
                drift_defensive=False, pattern_signal=None, unified_decision=None):
    """Traced wrapper around DecisionFusionV2.fuse()"""
    
    logger.info("\n" + "="*80)
    logger.info("FUSION LAYER INVOKED")
    logger.info("="*80)
    
    # Trace inputs
    logger.info(f"smc_signal:       {smc_signal}")
    logger.info(f"scalp_signal:     {scalp_signal}")
    logger.info(f"pattern_signal:   {pattern_signal}  ← EXPLICIT PARAMETER")
    logger.info(f"ml_prediction:    {ml_prediction}")
    logger.info(f"rl_action:        {rl_action}")
    logger.info(f"regime_type:      {regime_type}")
    logger.info(f"drift_defensive:  {drift_defensive}")
    
    # Determine what carries pattern info
    if scalp_signal and scalp_signal.get("direction") != "NONE":
        logger.warning(f"⚠️  PATTERN DATA FOUND IN scalp_signal: {scalp_signal}")
        logger.warning("    This means pattern detection results are being passed as 'scalp_signal'")
        logger.warning("    NOT via the explicit 'pattern_signal' parameter")
    
    if pattern_signal and pattern_signal.get("direction") != "NONE":
        logger.warning(f"✅ PATTERN DATA FOUND IN pattern_signal: {pattern_signal}")
        logger.warning("    This is the correct integration path")
    
    # Call original
    result = original_fuse(self, smc_signal, scalp_signal, ml_prediction, rl_action,
                          rl_confidence, stat_analysis, macro_blackout, regime_type,
                          regime_confidence, regime_ambiguous, calibration_penalty,
                          drift_defensive, pattern_signal, unified_decision)
    
    logger.info(f"\n→ Fusion result: {result.fused_direction} {result.action} (conf={result.confidence}%)")
    logger.info("="*80 + "\n")
    
    return result


def main():
    """Run pattern detection and trace data flow"""
    
    logger.info("\n" + "#"*80)
    logger.info("# AEGIS GOLD — PATTERN SIGNAL DATA-FLOW TRACE")
    logger.info("#"*80)
    
    # Patch DecisionFusionV2.fuse with tracing
    from brain.decision_fusion import DecisionFusionV2
    global original_fuse
    original_fuse = DecisionFusionV2.fuse
    DecisionFusionV2.fuse = traced_fuse
    
    try:
        from brain.brain import decide
        from brain.smc_pattern_engine import get_smc_pattern_engine
        from modules.risk_manager import RiskManager
        from modules.mt5_gateway import MT5Gateway
        from config import settings as cfg
        
        logger.info("\n1. INITIALIZING SYSTEMS")
        logger.info("="*80)
        
        gateway = MT5Gateway()
        if not gateway.initialize():
            logger.error("❌ MT5 initialization failed")
            return 1
        
        logger.info("✅ MT5 connected")
        
        acct = gateway.get_account_info()
        if not acct:
            logger.error("❌ Failed to get account info")
            return 1
        
        logger.info(f"✅ Account info retrieved: Equity=${acct['equity']:.2f}")
        
        risk = RiskManager(gateway)
        risk.init_daily(acct["equity"])
        
        logger.info("\n2. TESTING PATTERN DETECTION → FUSION DATA FLOW")
        logger.info("="*80)
        
        # Test with each symbol
        for sym in ["XAUUSD", "EURUSD"]:
            logger.info(f"\n### Testing {sym} ###\n")
            
            tick = gateway.get_current_tick(sym)
            if tick is None:
                logger.warning(f"No tick data for {sym} (market closed?)")
                continue
            
            ticks = gateway.get_ticks(sym, 200)
            candles_m5 = gateway.get_candles_m5(sym, cfg.CANDLE_COUNT)
            candles_m1 = gateway.get_candles_m1(sym, 30)
            
            if ticks is None or len(ticks) == 0 or candles_m5 is None or len(candles_m5) == 0:
                logger.warning(f"Insufficient data for {sym}")
                continue
            
            sym_point = gateway.symbols_data.get(sym, {}).get("point", 0.00001)
            spread = float(tick.ask - tick.bid) / sym_point if sym_point > 0 else 0
            session = "LONDON"
            
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
                logger.warning(f"Failed to convert {sym} data")
                continue
            
            logger.info(f"\n[PATTERN DETECTION PHASE]")
            logger.info("-"*80)
            
            # Check for patterns before calling brain_decide
            smc_pat_eng = get_smc_pattern_engine()
            patterns_found = smc_pat_eng.find_smc_enhanced_patterns(candles_list_m5, point=sym_point)
            
            if patterns_found:
                for i, pat_info in enumerate(patterns_found[:3]):
                    pat = pat_info['pattern']
                    logger.info(f"  Pattern {i+1}: {pat.name} ({pat.direction}) conf={pat_info['final_confidence']:.1f}%")
                    logger.info(f"             Entry: {pat.entry_price:.5f}, SL: {pat.stop_loss:.5f}, TP: {pat.take_profit:.5f}")
                    logger.info(f"             SMC Factors: {pat_info['smc_factors']}")
            else:
                logger.info("  No patterns detected")
            
            logger.info(f"\n[BRAIN DECISION PHASE]")
            logger.info("-"*80)
            logger.info(f"Calling brain_decide() for {sym}...")
            
            # Call brain_decide which will invoke our traced fusion
            decision = decide(ticks_list, candles_list_m5, acct, risk,
                                   session, spread, sym_point, symbol=sym, candles_m1=candles_list_m1)
            
            if decision:
                logger.info(f"\n[DECISION RESULT for {sym}]")
                logger.info("-"*80)
                logger.info(f"  Action:         {decision.action}")
                logger.info(f"  Direction:      {decision.direction}")
                logger.info(f"  Confidence:     {decision.confidence}%")
                logger.info(f"  Signal Source:  {decision.signal_source}")
                logger.info(f"  Pattern:        {decision.pattern}")
                logger.info(f"  Reason:         {decision.reason[:80]}")
            
            logger.info("")
        
        gateway.shutdown()
        
        logger.info("\n" + "#"*80)
        logger.info("# TRACE COMPLETE")
        logger.info("#"*80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Trace failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
