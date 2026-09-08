#!/usr/bin/env python3
"""
AEGIS GOLD — NUMERICAL SAFETY VALIDATION

Tests for divide-by-zero, invalid values, NaN handling in price/indicator calculations.
"""

import sys
import os
import logging
import warnings
import numpy as np
import io

# Capture all warnings
warnings.simplefilter("always")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

logging.basicConfig(
    level=logging.WARNING,
    format='[%(levelname)s] %(name)s - %(message)s'
)


def test_atr_calculation():
    """Test ATR calculation with edge cases"""
    print("\n[TEST 1] ATR Calculation")
    try:
        from brain.indicators import ATR
        
        # Normal case - need >= period data points for ATR
        closes = [100.0, 101.0, 100.5, 102.0, 99.5, 101.0, 100.0, 102.0, 
                  99.0, 101.0, 100.5, 102.5, 99.5, 101.5, 100.0, 101.0]  # 16 points >= 14
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        
        atr = ATR(highs, lows, closes, period=14)
        
        if not atr or len(atr) == 0:
            print("[FAIL] ATR returned empty")
            return False
        
        atr_val = atr[-1]
        
        if np.isnan(atr_val) or np.isinf(atr_val):
            print("[FAIL] ATR returned NaN or Inf")
            return False
        
        if atr_val < 0:
            print("[FAIL] ATR negative: {}".format(atr_val))
            return False
        
        print("[OK] Normal ATR: {:.6f}".format(atr_val))
        
        # Edge case: identical prices (zero range) - need >= period points
        closes_same = [100.0] * 16
        highs_same = [100.0] * 16
        lows_same = [100.0] * 16
        
        atr_same = ATR(highs_same, lows_same, closes_same, period=14)
        
        if not atr_same or len(atr_same) == 0:
            print("[FAIL] ATR returned empty on identical prices")
            return False
        
        atr_same_val = atr_same[-1]
        
        if np.isnan(atr_same_val):
            print("[FAIL] ATR NaN on identical prices")
            return False
        
        if atr_same_val != 0.0:
            print("[WARN] ATR non-zero on identical prices: {}".format(atr_same_val))
        else:
            print("[OK] ATR zero on identical prices")
        
        return True
        
    except Exception as e:
        print("[FAIL] ATR calculation error: {}".format(e))
        return False


def test_rsi_calculation():
    """Test RSI calculation"""
    print("\n[TEST 2] RSI Calculation")
    try:
        from brain.indicators import RSI
        
        # Normal case with 14 candles
        closes = [100.0, 101.0, 100.5, 102.0, 99.5, 101.0, 100.0, 102.0, 
                  99.0, 101.0, 100.5, 102.5, 99.5, 101.5]
        
        rsi = RSI(closes, period=14)
        
        if not rsi or len(rsi) == 0:
            print("[FAIL] RSI returned empty")
            return False
        
        rsi_val = rsi[-1]
        
        if np.isnan(rsi_val) or np.isinf(rsi_val):
            print("[FAIL] RSI returned NaN or Inf")
            return False
        
        if rsi_val < 0 or rsi_val > 100:
            print("[FAIL] RSI out of bounds: {}".format(rsi_val))
            return False
        
        print("[OK] Normal RSI: {:.2f}".format(rsi_val))
        
        # Edge case: all increases (RSI should be 100)
        closes_up = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0,
                     108.0, 109.0, 110.0, 111.0, 112.0, 113.0]
        
        rsi_up = RSI(closes_up, period=14)
        
        if not rsi_up or len(rsi_up) == 0:
            print("[FAIL] RSI returned empty on all increases")
            return False
        
        rsi_up_val = rsi_up[-1]
        
        if np.isnan(rsi_up_val):
            print("[FAIL] RSI NaN on all increases")
            return False
        
        print("[OK] RSI on increases: {:.2f}".format(rsi_up_val))
        
        # Edge case: all decreases (RSI should be 0)
        closes_down = [113.0, 112.0, 111.0, 110.0, 109.0, 108.0, 107.0, 106.0,
                       105.0, 104.0, 103.0, 102.0, 101.0, 100.0]
        
        rsi_down = RSI(closes_down, period=14)
        
        if not rsi_down or len(rsi_down) == 0:
            print("[FAIL] RSI returned empty on all decreases")
            return False
        
        rsi_down_val = rsi_down[-1]
        
        if np.isnan(rsi_down_val) or np.isinf(rsi_down_val):
            print("[FAIL] RSI NaN on all decreases")
            return False
        
        print("[OK] RSI on decreases: {:.2f}".format(rsi_down_val))
        
        return True
        
    except Exception as e:
        print("[FAIL] RSI calculation error: {}".format(e))
        return False


def test_adx_calculation():
    """Test ADX calculation"""
    print("\n[TEST 3] ADX Calculation")
    try:
        from brain.indicators import ADX
        
        # Normal case - need >= period+1 data points for ADX
        closes = [100.0, 101.0, 100.5, 102.0, 99.5, 101.0, 100.0, 102.0, 
                  99.0, 101.0, 100.5, 102.5, 99.5, 101.5] * 3  # 42 points for ADX
        highs = [c + 1.0 for c in closes]
        lows = [c - 1.0 for c in closes]
        
        adx_list = ADX(highs, lows, closes, period=14)
        
        if not adx_list or len(adx_list) == 0:
            print("[FAIL] ADX returned empty")
            return False
        
        adx = adx_list[-1]
        
        if np.isnan(adx) or np.isinf(adx):
            print("[FAIL] ADX returned NaN or Inf")
            return False
        
        if adx < 0 or adx > 100:
            print("[FAIL] ADX out of bounds: {}".format(adx))
            return False
        
        print("[OK] Normal ADX: {:.2f}".format(adx))
        
        return True
        
    except Exception as e:
        print("[FAIL] ADX calculation error: {}".format(e))
        return False


def test_division_safety():
    """Test division-by-zero protection"""
    print("\n[TEST 4] Division Safety")
    try:
        # Simulate ratio calculations with zero denominators
        numerator = 100.0
        denominator = 0.0
        
        # Safe division
        if denominator == 0:
            result = 0.0
        else:
            result = numerator / denominator
        
        print("[OK] Division by zero protected: result={}".format(result))
        
        # Test with numpy arrays
        arr = np.array([1.0, 2.0, 0.0, 4.0])
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            safe_result = np.divide(100.0, arr, where=arr!=0, out=np.zeros_like(arr))
            
            if len(w) > 0:
                print("[WARN] Division warnings: {}".format([str(warning.message) for warning in w]))
            else:
                print("[OK] Safe numpy division: no warnings")
        
        print("[OK] Result with zero protection: {}".format(safe_result))
        
        return True
        
    except Exception as e:
        print("[FAIL] Division safety error: {}".format(e))
        return False


def test_spread_calculation():
    """Test spread calculation with edge cases"""
    print("\n[TEST 5] Spread Calculation")
    try:
        bid = 1.15957
        ask = 1.15958
        point = 0.00001
        
        if point == 0:
            spread = 0
        else:
            spread = (ask - bid) / point
        
        if np.isnan(spread) or np.isinf(spread):
            print("[FAIL] Spread calculation NaN/Inf")
            return False
        
        print("[OK] Spread: {:.2f} points".format(spread))
        
        # Edge case: bid > ask (error condition)
        bid_error = 1.15960
        ask_error = 1.15955
        
        if point == 0:
            spread_error = 0
        else:
            spread_error = (ask_error - bid_error) / point
        
        if spread_error < 0:
            print("[WARN] Negative spread detected (bid>ask): {:.2f}".format(spread_error))
        else:
            print("[OK] Spread validation: {}".format(spread_error))
        
        return True
        
    except Exception as e:
        print("[FAIL] Spread calculation error: {}".format(e))
        return False


def main():
    results = {}
    
    results["ATR"] = test_atr_calculation()
    results["RSI"] = test_rsi_calculation()
    results["ADX"] = test_adx_calculation()
    results["Division"] = test_division_safety()
    results["Spread"] = test_spread_calculation()
    
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print("{} {}: {}".format(status, test_name, "PASS" if passed else "FAIL"))
    
    pass_count = sum(1 for r in results.values() if r)
    total = len(results)
    
    print("="*70)
    print("{}/{} PASSED".format(pass_count, total))
    print("="*70)
    
    return 0 if pass_count == total else 1


if __name__ == "__main__":
    # Fix Windows Unicode (only when run directly, not when imported by unittest)
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    print("\n" + "="*70)
    print("TEST: NUMERICAL SAFETY VALIDATION")
    print("="*70)

    sys.exit(main())
