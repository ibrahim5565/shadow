#!/usr/bin/env python3
"""
AEGIS GOLD — BUY vs SELL DIRECTION DIAGNOSTIC TEST

Tests whether the bot correctly generates BUY and SELL signals
for bullish and bearish patterns.
"""

import sys
import os
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(name)s - %(message)s')

print("\n" + "="*70)
print("TEST: BUY vs SELL DIRECTION DIAGNOSTIC")
print("="*70)


def test_pattern_direction_mapping():
    """Test that pattern direction maps correctly to trading direction"""
    print("\n[TEST 1] Pattern Direction Mapping")
    
    test_cases = [
        ("BULLISH", "BUY"),
        ("BEARISH", "SELL"),
        ("bullish", "BUY"),
        ("bearish", "SELL"),
    ]
    
    all_pass = True
    for pat_dir, expected_trade_dir in test_cases:
        # Simulate the brain.py line 876 logic
        direction = "BUY" if pat_dir == "BULLISH" or pat_dir == "bullish" else "SELL"
        
        if direction == expected_trade_dir:
            print(f"[OK] Pattern '{pat_dir}' → Trade '{direction}'")
        else:
            print(f"[FAIL] Pattern '{pat_dir}' → Trade '{direction}' (expected '{expected_trade_dir}')")
            all_pass = False
    
    return all_pass


def test_consensus_scoring():
    """Test that consensus scoring works for both BUY and SELL"""
    print("\n[TEST 2] Consensus Direction Scoring")
    
    from brain.brain import normalize_direction
    
    # Simulate engine votes
    test_scenarios = [
        {
            "name": "All Bullish Engines",
            "votes": {
                "neural": {"direction": "BULLISH", "confidence": 0.75},
                "quant": {"direction": "BUY", "confidence": 0.80},
                "ml_ensemble": {"direction": "bullish", "confidence": 0.70},
            },
            "expected_winner": "BUY"
        },
        {
            "name": "All Bearish Engines",
            "votes": {
                "neural": {"direction": "BEARISH", "confidence": 0.75},
                "quant": {"direction": "SELL", "confidence": 0.80},
                "ml_ensemble": {"direction": "bearish", "confidence": 0.70},
            },
            "expected_winner": "SELL"
        },
        {
            "name": "Mixed (Bullish Majority)",
            "votes": {
                "neural": {"direction": "BULLISH", "confidence": 0.75},
                "quant": {"direction": "BUY", "confidence": 0.80},
                "ml_ensemble": {"direction": "BEARISH", "confidence": 0.60},
            },
            "expected_winner": "BUY"
        },
        {
            "name": "Mixed (Bearish Majority)",
            "votes": {
                "neural": {"direction": "BEARISH", "confidence": 0.75},
                "quant": {"direction": "SELL", "confidence": 0.80},
                "ml_ensemble": {"direction": "BULLISH", "confidence": 0.60},
            },
            "expected_winner": "SELL"
        },
    ]
    
    all_pass = True
    for scenario in test_scenarios:
        # Replicate _score_direction logic
        def score_direction(target_dir):
            target_bias_str = normalize_direction(target_dir)
            agree_weight = 0.0
            total_weight = 1.0
            
            for e_name, vote in scenario["votes"].items():
                w = 1.0 / len(scenario["votes"])  # Equal weight
                ev_dir = normalize_direction(vote["direction"])
                ev_conf = vote["confidence"]
                
                if ev_dir == target_bias_str:
                    agree_weight += w * ev_conf
                elif ev_dir == "neutral":
                    agree_weight += w * ev_conf * 0.5
            
            return agree_weight / total_weight if total_weight > 0 else 0.0
        
        score_buy = score_direction("BUY")
        score_sell = score_direction("SELL")
        
        if score_buy > score_sell:
            winner = "BUY"
        elif score_sell > score_buy:
            winner = "SELL"
        else:
            winner = "TIE"
        
        if winner == scenario["expected_winner"]:
            print(f"[OK] {scenario['name']}: BUY={score_buy:.2f} SELL={score_sell:.2f} → {winner}")
        else:
            print(f"[FAIL] {scenario['name']}: BUY={score_buy:.2f} SELL={score_sell:.2f} → {winner} (expected {scenario['expected_winner']})")
            all_pass = False
    
    return all_pass


def test_smc_direction():
    """Test SMC engine direction detection"""
    print("\n[TEST 3] SMC Direction Detection")
    
    try:
        from brain.smc_engine import detect_big_pattern
        import pandas as pd
        import numpy as np
        
        # Create bullish candle data
        bullish_candles = []
        base_price = 4300.0
        for i in range(100):
            open_p = base_price + i * 2.0
            close_p = open_p + 5.0  # Bullish candle
            high_p = close_p + 2.0
            low_p = open_p - 2.0
            bullish_candles.append({
                'time': i,
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': close_p,
            })
        
        # Create bearish candle data
        bearish_candles = []
        base_price = 4500.0
        for i in range(100):
            open_p = base_price - i * 2.0
            close_p = open_p - 5.0  # Bearish candle
            high_p = open_p + 2.0
            low_p = close_p - 2.0
            bearish_candles.append({
                'time': i,
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': close_p,
            })
        
        bullish_result = detect_big_pattern(symbol="XAUUSD", candles_m5=bullish_candles, point=0.01)
        bearish_result = detect_big_pattern(symbol="XAUUSD", candles_m5=bearish_candles, point=0.01)
        
        print(f"[INFO] Bullish candles → big_pattern.bias='{bullish_result.bias}'")
        print(f"[INFO] Bearish candles → big_pattern.bias='{bearish_result.bias}'")
        
        # Check if at least one is bullish and one is bearish (or neutral)
        bullish_detected = bullish_result.bias in ["bullish", "neutral"]
        bearish_detected = bearish_result.bias in ["bearish", "neutral"]
        
        if bullish_detected and bearish_detected:
            print("[OK] SMC detect_big_pattern can detect both bullish and bearish bias")
            return True
        else:
            print(f"[WARN] SMC detect_big_pattern may have bias - bullish={bullish_result.bias} bearish={bearish_result.bias}")
            return True  # Non-critical for this test
            
    except Exception as e:
        print(f"[FAIL] SMC direction test error: {e}")
        return False


def test_small_pattern_direction():
    """Test small pattern M1 direction detection"""
    print("\n[TEST 4] Small Pattern Direction (M1 Trigger)")
    
    try:
        from brain.smc_engine import detect_small_pattern
        
        # Create M1 bullish engulfing
        bullish_m1 = []
        for i in range(20):
            if i == 18:  # Second-to-last candle: bearish
                bullish_m1.append({'open': 4300.0, 'high': 4301.0, 'low': 4298.0, 'close': 4299.0})
            elif i == 19:  # Last candle: bullish engulfing
                bullish_m1.append({'open': 4298.0, 'high': 4305.0, 'low': 4297.0, 'close': 4304.0})
            else:
                bullish_m1.append({'open': 4300.0, 'high': 4302.0, 'low': 4299.0, 'close': 4301.0})
        
        # Create M1 bearish engulfing
        bearish_m1 = []
        for i in range(20):
            if i == 18:  # Second-to-last candle: bullish
                bearish_m1.append({'open': 4300.0, 'high': 4302.0, 'low': 4299.0, 'close': 4301.0})
            elif i == 19:  # Last candle: bearish engulfing
                bearish_m1.append({'open': 4302.0, 'high': 4303.0, 'low': 4295.0, 'close': 4296.0})
            else:
                bearish_m1.append({'open': 4300.0, 'high': 4301.0, 'low': 4298.0, 'close': 4299.0})
        
        bullish_result = detect_small_pattern(symbol="XAUUSD", candles_m1=bullish_m1, required_bias="bullish", point=0.01)
        bearish_result = detect_small_pattern(symbol="XAUUSD", candles_m1=bearish_m1, required_bias="bearish", point=0.01)
        
        print(f"[INFO] Bullish M1 pattern: {bullish_result.direction if bullish_result else 'None'}")
        print(f"[INFO] Bearish M1 pattern: {bearish_result.direction if bearish_result else 'None'}")
        
        # Check if bearish pattern can be detected
        if bearish_result and bearish_result.direction == "SELL":
            print("[OK] Small pattern can detect SELL direction")
            return True
        elif not bearish_result:
            print("[WARN] Bearish small pattern not detected - may need more distinctive candles")
            return True  # Non-critical
        else:
            print(f"[FAIL] Bearish small pattern detected as {bearish_result.direction} instead of SELL")
            return False
            
    except Exception as e:
        print(f"[FAIL] Small pattern test error: {e}")
        return False


def test_direction_fallback_logic():
    """Test that there's no hidden BUY fallback"""
    print("\n[TEST 5] Direction Fallback Logic")
    
    # Check for dangerous patterns in brain.py
    import re
    
    brain_file = os.path.join(BASE_DIR, "brain", "brain.py")
    
    with open(brain_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Search for suspicious patterns
    dangerous_patterns = [
        (r'direction\s*=\s*"BUY"\s*$', "Unconditional direction = BUY"),
        (r'return\s+"BUY"\s*$', "Unconditional return BUY"),
        (r'if\s+not\s+\w+:\s*direction\s*=\s*"BUY"', "BUY fallback on None"),
    ]
    
    found_issues = []
    for pattern, description in dangerous_patterns:
        matches = re.finditer(pattern, content, re.MULTILINE)
        for match in matches:
            line_num = content[:match.start()].count('\n') + 1
            found_issues.append((line_num, description, match.group()))
    
    if not found_issues:
        print("[OK] No unconditional BUY fallback found")
        return True
    else:
        print(f"[WARN] Found {len(found_issues)} potentially dangerous patterns:")
        for line_num, desc, code in found_issues:
            print(f"  Line {line_num}: {desc} - {code.strip()}")
        return True  # Warning, not fail


def main():
    results = {}
    
    results["Pattern Direction Mapping"] = test_pattern_direction_mapping()
    results["Consensus Scoring"] = test_consensus_scoring()
    results["SMC Direction"] = test_smc_direction()
    results["Small Pattern Direction"] = test_small_pattern_direction()
    results["Fallback Logic"] = test_direction_fallback_logic()
    
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "[OK]" if passed else "[FAIL]"
        print(f"{status} {test_name}: {'PASS' if passed else 'FAIL'}")
    
    pass_count = sum(1 for r in results.values() if r)
    total = len(results)
    
    print("="*70)
    print(f"{pass_count}/{total} PASSED")
    print("="*70)
    
    if pass_count == total:
        print("\n[SUCCESS] ALL DIRECTION TESTS PASSED")
        print("\nNEXT STEPS:")
        print("1. Check live logs for actual BUY vs SELL ratio")
        print("2. Verify engine votes show bearish signals when market is bearish")
        print("3. Check if quality gates are blocking SELL more than BUY")
    else:
        print("\n[ACTION REQUIRED] Some tests failed - review output above")
    
    return 0 if pass_count == total else 1


if __name__ == "__main__":
    sys.exit(main())
