"""
REGRESSION TEST: pattern_signal parameter fix
Prevents regression of: NameError: pattern_signal is not defined
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.decision_fusion import DecisionFusionV2


def test_fusion_no_pattern():
    """Regression: fusion must handle pattern_signal=None"""
    fusion = DecisionFusionV2()
    result = fusion.fuse(
        smc_signal=None, scalp_signal=None, ml_prediction=None,
        rl_action="WAIT", rl_confidence=0, stat_analysis=None,
        macro_blackout=False, regime_type="UNKNOWN", regime_confidence=0.0,
        regime_ambiguous=False, calibration_penalty=0, drift_defensive=False,
        pattern_signal=None, unified_decision=None
    )
    assert result is not None, "Fusion returned None"
    assert result.action in ["TRADE", "WAIT"], f"Invalid action: {result.action}"
    print("[PASS] test_fusion_no_pattern")


def test_fusion_buy_pattern():
    """Regression: fusion must process BUY pattern"""
    fusion = DecisionFusionV2()
    result = fusion.fuse(
        smc_signal=None, scalp_signal=None, ml_prediction=None,
        rl_action="WAIT", rl_confidence=0, stat_analysis=None,
        macro_blackout=False, regime_type="TRENDING", regime_confidence=75.0,
        regime_ambiguous=False, calibration_penalty=0, drift_defensive=False,
        pattern_signal={"direction": "BUY", "confidence": 75.0, "pattern_name": "OB"},
        unified_decision=None
    )
    assert result is not None, "Fusion returned None"
    print("[PASS] test_fusion_buy_pattern")


def test_fusion_sell_pattern():
    """Regression: fusion must process SELL pattern"""
    fusion = DecisionFusionV2()
    result = fusion.fuse(
        smc_signal=None, scalp_signal=None, ml_prediction=None,
        rl_action="WAIT", rl_confidence=0, stat_analysis=None,
        macro_blackout=False, regime_type="TRENDING", regime_confidence=75.0,
        regime_ambiguous=False, calibration_penalty=0, drift_defensive=False,
        pattern_signal={"direction": "SELL", "confidence": 80.0, "pattern_name": "BoS"},
        unified_decision=None
    )
    assert result is not None, "Fusion returned None"
    print("[PASS] test_fusion_sell_pattern")


def test_fusion_malformed_pattern():
    """Regression: fusion must handle malformed pattern_signal safely"""
    fusion = DecisionFusionV2()
    
    # Empty dict
    result = fusion.fuse(
        smc_signal=None, scalp_signal=None, ml_prediction=None,
        rl_action="WAIT", rl_confidence=0, stat_analysis=None,
        macro_blackout=False, regime_type="UNKNOWN", regime_confidence=0.0,
        regime_ambiguous=False, calibration_penalty=0, drift_defensive=False,
        pattern_signal={}, unified_decision=None
    )
    assert result is not None, "Fusion returned None on empty dict"
    
    # Invalid type (converted to dict internally)
    result = fusion.fuse(
        smc_signal=None, scalp_signal=None, ml_prediction=None,
        rl_action="WAIT", rl_confidence=0, stat_analysis=None,
        macro_blackout=False, regime_type="UNKNOWN", regime_confidence=0.0,
        regime_ambiguous=False, calibration_penalty=0, drift_defensive=False,
        pattern_signal="invalid", unified_decision=None
    )
    assert result is not None, "Fusion returned None on string input"
    
    print("[PASS] test_fusion_malformed_pattern")


def test_brain_without_pattern():
    """Regression: brain.decide must not crash without patterns"""
    from brain.brain import decide
    
    account = type('obj', (object,), {
        'balance': 10000, 'equity': 10000, 'margin': 1000, 'margin_free': 1000, 'leverage': 1.0
    })()
    
    candles = [
        {"open": 2010.0, "high": 2012.0, "low": 2008.0, "close": 2011.0, "volume": 100},
    ] * 10
    
    decision = decide(
        symbol="XAUUSD", candles_m1=candles, candles_m5=candles, candles_h1=candles,
        account=account, spread=20.0, session="LONDON", point=0.01
    )
    
    assert decision is not None, "decide() returned None"
    assert decision.action in ["TRADE", "WAIT"], f"Invalid action: {decision.action}"
    print("[PASS] test_brain_without_pattern")


def test_brain_with_pattern():
    """Regression: brain.decide must not crash with patterns"""
    from brain.brain import decide
    
    account = type('obj', (object,), {
        'balance': 10000, 'equity': 10000, 'margin': 1000, 'margin_free': 1000, 'leverage': 1.0
    })()
    
    candles = [
        {"open": 1.0800, "high": 1.0820, "low": 1.0790, "close": 1.0810, "volume": 100},
    ] * 10
    
    decision = decide(
        symbol="EURUSD", candles_m1=candles, candles_m5=candles, candles_h1=candles,
        account=account, spread=2.0, session="NY_OPEN", point=0.0001
    )
    
    assert decision is not None, "decide() returned None"
    assert decision.action in ["TRADE", "WAIT"], f"Invalid action: {decision.action}"
    print("[PASS] test_brain_with_pattern")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("REGRESSION TEST: pattern_signal Fix")
    print("="*70 + "\n")
    
    try:
        test_fusion_no_pattern()
        test_fusion_buy_pattern()
        test_fusion_sell_pattern()
        test_fusion_malformed_pattern()
        test_brain_without_pattern()
        test_brain_with_pattern()
        
        print("\n" + "="*70)
        print("✓ ALL REGRESSION TESTS PASSED")
        print("="*70)
        sys.exit(0)
        
    except Exception as e:
        print(f"\n✗ REGRESSION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
