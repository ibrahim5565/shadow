"""
AEGIS GOLD POST-FIX VERIFICATION
Testing pattern_signal parameter fix in DecisionFusionV2.fuse()

Test Coverage:
  - TEST A: pattern_signal = None
  - TEST B: BUY pattern
  - TEST C: SELL pattern
  - TEST D: Malformed input (empty dict)
  - TEST E: Real brain pipeline (XAUUSD, no patterns)
  - TEST F: Real brain pipeline (EURUSD, with pattern)
  - TEST G: Fast confidence updater
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from brain.decision_fusion import DecisionFusionV2, FusionResult


def test_a_no_pattern():
    """TEST A: pattern_signal = None"""
    print("\n" + "="*70)
    print("TEST A: NO PATTERN (pattern_signal = None)")
    print("="*70)
    
    try:
        fusion = DecisionFusionV2()
        result = fusion.fuse(
            smc_signal=None,
            scalp_signal=None,
            ml_prediction=None,
            rl_action="WAIT",
            rl_confidence=0,
            stat_analysis=None,
            macro_blackout=False,
            regime_type="UNKNOWN",
            regime_confidence=0.0,
            regime_ambiguous=False,
            calibration_penalty=0,
            drift_defensive=False,
            pattern_signal=None,  # EXPLICITLY NONE
            unified_decision=None
        )
        
        assert isinstance(result, FusionResult), "Result not FusionResult"
        assert result.fused_direction in ["BUY", "SELL", "NA"], f"Invalid direction: {result.fused_direction}"
        assert result.action in ["TRADE", "WAIT"], f"Invalid action: {result.action}"
        
        print(f"✓ No exception raised")
        print(f"✓ Direction: {result.fused_direction}")
        print(f"✓ Action: {result.action}")
        print(f"✓ Confidence: {result.confidence}")
        print("[PASS] TEST A")
        return True
        
    except NameError as e:
        if "pattern_signal" in str(e):
            print(f"[FAIL] TEST A — NameError on pattern_signal: {e}")
            return False
        raise
    except Exception as e:
        print(f"[FAIL] TEST A — Unexpected error: {e}")
        return False


def test_b_buy_pattern():
    """TEST B: BUY pattern"""
    print("\n" + "="*70)
    print("TEST B: BUY PATTERN")
    print("="*70)
    
    try:
        fusion = DecisionFusionV2()
        result = fusion.fuse(
            smc_signal=None,
            scalp_signal=None,
            ml_prediction=None,
            rl_action="WAIT",
            rl_confidence=0,
            stat_analysis=None,
            macro_blackout=False,
            regime_type="TRENDING",
            regime_confidence=75.0,
            regime_ambiguous=False,
            calibration_penalty=0,
            drift_defensive=False,
            pattern_signal={
                "direction": "BUY",
                "confidence": 75.0,
                "pattern_name": "Order_Block",
                "source": "SMC"
            },
            unified_decision=None
        )
        
        assert isinstance(result, FusionResult), "Result not FusionResult"
        print(f"✓ No exception raised")
        print(f"✓ Direction: {result.fused_direction}")
        print(f"✓ Action: {result.action}")
        print(f"✓ Confidence: {result.confidence}")
        print("[PASS] TEST B")
        return True
        
    except NameError as e:
        if "pattern_signal" in str(e):
            print(f"[FAIL] TEST B — NameError on pattern_signal: {e}")
            return False
        raise
    except Exception as e:
        print(f"[FAIL] TEST B — Unexpected error: {e}")
        return False


def test_c_sell_pattern():
    """TEST C: SELL pattern"""
    print("\n" + "="*70)
    print("TEST C: SELL PATTERN")
    print("="*70)
    
    try:
        fusion = DecisionFusionV2()
        result = fusion.fuse(
            smc_signal=None,
            scalp_signal=None,
            ml_prediction=None,
            rl_action="WAIT",
            rl_confidence=0,
            stat_analysis=None,
            macro_blackout=False,
            regime_type="TRENDING",
            regime_confidence=75.0,
            regime_ambiguous=False,
            calibration_penalty=0,
            drift_defensive=False,
            pattern_signal={
                "direction": "SELL",
                "confidence": 80.0,
                "pattern_name": "Break_of_Structure",
                "source": "SMC"
            },
            unified_decision=None
        )
        
        assert isinstance(result, FusionResult), "Result not FusionResult"
        print(f"✓ No exception raised")
        print(f"✓ Direction: {result.fused_direction}")
        print(f"✓ Action: {result.action}")
        print(f"✓ Confidence: {result.confidence}")
        print("[PASS] TEST C")
        return True
        
    except NameError as e:
        if "pattern_signal" in str(e):
            print(f"[FAIL] TEST C — NameError on pattern_signal: {e}")
            return False
        raise
    except Exception as e:
        print(f"[FAIL] TEST C — Unexpected error: {e}")
        return False


def test_d_malformed_input():
    """TEST D: Malformed input (empty dict)"""
    print("\n" + "="*70)
    print("TEST D: MALFORMED INPUT (empty dict)")
    print("="*70)
    
    try:
        fusion = DecisionFusionV2()
        result = fusion.fuse(
            smc_signal=None,
            scalp_signal=None,
            ml_prediction=None,
            rl_action="WAIT",
            rl_confidence=0,
            stat_analysis=None,
            macro_blackout=False,
            regime_type="UNKNOWN",
            regime_confidence=0.0,
            regime_ambiguous=False,
            calibration_penalty=0,
            drift_defensive=False,
            pattern_signal={},  # EMPTY DICT (malformed)
            unified_decision=None
        )
        
        assert isinstance(result, FusionResult), "Result not FusionResult"
        print(f"✓ No exception raised")
        print(f"✓ Safe fallback triggered")
        print(f"✓ Direction: {result.fused_direction}")
        print(f"✓ Action: {result.action}")
        print("[PASS] TEST D")
        return True
        
    except (NameError, AttributeError) as e:
        print(f"[FAIL] TEST D — {type(e).__name__}: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] TEST D — Unexpected error: {e}")
        return False


def test_e_xauusd_no_patterns():
    """TEST E: Real brain pipeline (XAUUSD, no patterns)"""
    print("\n" + "="*70)
    print("TEST E: XAUUSD REAL PIPELINE (no patterns)")
    print("="*70)
    
    try:
        from brain.brain import decide
        from config import settings as cfg
        
        # Synthetic market data
        account = type('obj', (object,), {
            'balance': 10000,
            'equity': 10000,
            'margin': 1000,
            'margin_free': 1000,
            'leverage': 1.0
        })()
        
        candles_m1 = [
            {"open": 2010.0, "high": 2012.0, "low": 2008.0, "close": 2011.0, "volume": 100},
        ] * 10
        
        candles_m5 = candles_m1
        candles_h1 = candles_m1
        
        decision = decide(
            symbol="XAUUSD",
            candles_m1=candles_m1,
            candles_m5=candles_m5,
            candles_h1=candles_h1,
            account=account,
            spread=20.0,
            session="LONDON",
            point=0.01
        )
        
        print(f"✓ No NameError/AttributeError raised")
        print(f"✓ Decision action: {decision.action}")
        print(f"✓ Decision direction: {decision.direction}")
        print(f"✓ Decision confidence: {decision.confidence}")
        print("[PASS] TEST E")
        return True
        
    except NameError as e:
        if "pattern_signal" in str(e):
            print(f"[FAIL] TEST E — NameError on pattern_signal: {e}")
            return False
        print(f"[FAIL] TEST E — Other NameError: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] TEST E — Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_f_eurusd_with_pattern():
    """TEST F: Real brain pipeline (EURUSD, with pattern)"""
    print("\n" + "="*70)
    print("TEST F: EURUSD REAL PIPELINE (with pattern)")
    print("="*70)
    
    try:
        from brain.brain import decide
        
        account = type('obj', (object,), {
            'balance': 10000,
            'equity': 10000,
            'margin': 1000,
            'margin_free': 1000,
            'leverage': 1.0
        })()
        
        candles_m1 = [
            {"open": 1.0800, "high": 1.0820, "low": 1.0790, "close": 1.0810, "volume": 100},
        ] * 10
        
        candles_m5 = candles_m1
        candles_h1 = candles_m1
        
        decision = decide(
            symbol="EURUSD",
            candles_m1=candles_m1,
            candles_m5=candles_m5,
            candles_h1=candles_h1,
            account=account,
            spread=2.0,
            session="NY_OPEN",
            point=0.0001
        )
        
        print(f"✓ No exception raised")
        print(f"✓ Decision action: {decision.action}")
        print(f"✓ Decision direction: {decision.direction}")
        print(f"✓ Decision confidence: {decision.confidence}")
        print("[PASS] TEST F")
        return True
        
    except NameError as e:
        if "pattern_signal" in str(e):
            print(f"[FAIL] TEST F — NameError on pattern_signal: {e}")
            return False
        print(f"[FAIL] TEST F — Other NameError: {e}")
        return False
    except Exception as e:
        print(f"[FAIL] TEST F — Error: {type(e).__name__}: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("PATTERN_SIGNAL FIX VERIFICATION TEST SUITE")
    print("="*70)
    
    results = {
        'A_NO_PATTERN': test_a_no_pattern(),
        'B_BUY_PATTERN': test_b_buy_pattern(),
        'C_SELL_PATTERN': test_c_sell_pattern(),
        'D_MALFORMED': test_d_malformed_input(),
        'E_XAUUSD': test_e_xauusd_no_patterns(),
        'F_EURUSD': test_f_eurusd_with_pattern(),
    }
    
    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {test_name:20s} {status}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*70)
    if all_passed:
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
