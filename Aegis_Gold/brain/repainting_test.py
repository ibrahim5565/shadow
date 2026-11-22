"""
AEGIS GOLD — Repainting Test
============================

For every historical decision T:
1. Run: signal(T)
2. Progressively reveal: T+1, T+2, T+3, ..., T+n
3. The original signal at T must not change.
4. Requirement: signal_at_T_before_future_reveal == signal_at_T_after_future_reveal

If it changes: REPAINTING / FUTURE LEAKAGE
Report the exact component responsible.

This test ensures that decisions are not influenced by future data that
becomes available after the decision time.
"""

import numpy as np
import copy
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("aegis.repainting_test")


class RepaintingTest:
    """
    Tests that historical signals do not change when future data is revealed.
    
    The core principle: A signal generated at time T should remain valid
    even as future data (T+1, T+2, ...) becomes known. If the signal
    repaints (changes) when future data is revealed, it indicates future
    data leakage in the signal generation logic.
    """
    
    def __init__(self, max_bars_revealed: int = 50):
        self.max_bars_revealed = max_bars_revealed
        self.test_results: List[Dict] = []
    
    def run_test(
        self,
        signal_func,
        initial_data: Dict[str, Any],
        decision_time: datetime,
        symbol: str,
        **signal_kwargs
    ) -> List[Dict]:
        """
        Run the repainting test for a historical decision.
        
        Args:
            signal_func: Function that generates a signal given data and decision_time
            initial_data: Market data at time T (only data up to T should be included)
            decision_time: The timestamp T at which signal is generated
            symbol: Trading symbol
            **signal_kwargs: Additional arguments for signal function
            
        Returns:
            List of test results for each revelation step
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        
        # Step 1: Generate the initial signal at T with only data available at T
        logger.info(f"[REPAINTING TEST] Step 1: Generating initial signal at {decision_dt}")
        
        initial_signal = signal_func(initial_data, decision_time=decision_dt, symbol=symbol, **signal_kwargs)
        initial_signal_copy = copy.deepcopy(initial_signal)
        initial_signal_serialized = self._serialize_signal(initial_signal)
        
        logger.info(f"[REPAINTING TEST] Initial signal: action={initial_signal.get('action', 'N/A')}, "
                     f"confidence={initial_signal.get('confidence', 'N/A')}%")
        
        # Step 2: Progressively reveal future data T+1, T+2, ..., T+n
        results = []
        
        # Keep track of data that has been revealed
        revealed_data = copy.deepcopy(initial_data)
        
        for step in range(1, self.max_bars_revealed + 1):
            future_time = decision_dt + timedelta(bars=step)
            
            # Reveal additional future data (simulated by adding future bars)
            # In a real implementation, this would add actual T+step bar data
            revealed_data = self._add_future_bar(revealed_data, future_time, symbol)
            
            # Generate signal with progressively more data
            # The key test: the signal at T should NOT change even as we reveal T+1, T+2, etc.
            current_signal = signal_func(
                revealed_data, 
                decision_time=decision_dt, 
                symbol=symbol,
                **signal_kwargs
            )
            current_signal_serialized = self._serialize_signal(current_signal)
            
            # Compare with initial signal
            changed = self._signals_differ(initial_signal_serialized, current_signal_serialized)
            
            result = {
                "step": step,
                "future_time": future_time.isoformat(),
                "signal_action_before": initial_signal.get('action', 'N/A'),
                "signal_action_after": current_signal.get('action', 'N/A'),
                "signal_confidence_before": initial_signal.get('confidence', 'N/A'),
                "signal_confidence_after": current_signal.get('confidence', 'N/A'),
                "signals_equal": not changed,
                "has_changed": changed,
                "data_revealed": step,
            }
            
            if changed:
                logger.warning(
                    f"[REPAINTING TEST] STEP {step}: SIGNAL CHANGED when revealing {future_time}"
                    f"\n  Before: action={initial_signal.get('action', 'N/A')}, conf={initial_signal.get('confidence', 'N/A')}%"
                    f"\n  After:  action={current_signal.get('action', 'N/A')}, conf={current_signal.get('confidence', 'N/A')}%"
                )
            
            results.append(result)
            
            # Stop early if signal changed (we found repainting)
            if changed:
                logger.critical(
                    f"[REPAINTING TEST] REPAINTING DETECTED at step {step}: "
                    f"Signal changed when revealing future data"
                )
                break
        
        # Store results
        self.test_results.extend(results)
        
        # Overall result
        all_equal = all(r["signals_equal"] for r in results)
        
        if all_equal:
            logger.info(f"[REPAINTING TEST] PASSED: Signal did not repaint over {len(results)} steps")
        else:
            first_change_step = next((i for i, r in enumerate(results) if r["has_changed"]), None)
            logger.warning(
                f"[REPAINTING TEST] FAILED: Signal repainted at step {first_change_step}"
            )
        
        return results
    
    def _add_future_bar(self, data: Dict[str, Any], future_time: datetime, 
                        symbol: str) -> Dict[str, Any]:
        """
        Add a future bar to the data dictionary.
        In a real implementation, this would fetch actual MT5 data for T+1, etc.
        For the test, we simulate by adding synthetic future data.
        """
        decision_dt = data.get('decision_time', datetime.now(timezone.utc))
        
        result = copy.deepcopy(data)
        
        # Add synthetic future bar data
        if 'candles' not in result or result['candles'] is None:
            result['candles'] = []
        
        # Create a synthetic future bar (close price random walk from last close)
        n_candles = len(result['candles']) if result['candles'] else 0
        if n_candles > 0:
            last_close = result['candles'][-1].get('close', 100.0)
            # Random walk: close moves up or down slightly
            change = np.random.random() * 2 - 1  # -1 to +1
            new_close = last_close * (1 + change * 0.01)  # 1% max move
            new_open = new_close * (1 + (np.random.random() - 0.5) * 0.02)
            new_high = max(new_open, new_close) * (1 + abs(np.random.random()) * 0.01)
            new_low = min(new_open, new_close) * (1 - abs(np.random.random()) * 0.01)
            
            future_bar = {
                'time': int(future_time.timestamp()),
                'open': new_open,
                'high': new_high,
                'low': new_low,
                'close': new_close,
                'volume': 1000,
                'symbol': symbol
            }
            result['candles'].append(future_bar)
        else:
            # First bar - create synthetic data
            future_bar = {
                'time': int(future_time.timestamp()),
                'open': 100.0,
                'high': 101.0,
                'low': 99.0,
                'close': 100.5,
                'volume': 1000,
                'symbol': symbol
            }
            result['candles'].append(future_bar)
        
        return result
    
    def _signals_differ(self, signal1: Dict, signal2: Dict) -> bool:
        """
        Check if two signals differ significantly.
        """
        # Compare key decision fields
        key_fields = ['action', 'direction', 'confidence', 'signal_strength', 'grade']
        
        for field in key_fields:
            v1 = signal1.get(field)
            v2 = signal2.get(field)
            
            if v1 is None or v2 is None:
                continue
            
            if isinstance(v1, float) and isinstance(v2, float):
                if abs(v1 - v2) > 0.01:  # 1% tolerance for confidence
                    return True
            elif v1 != v2:
                return True
        
        # If core action changed, definitely different
        if signal1.get('action') != signal2.get('action'):
            return True
        
        return False
    
    def _serialize_signal(self, signal: Dict) -> Dict:
        """Serialize signal for comparison."""
        result = {}
        for key, value in signal.items():
            if hasattr(value, 'item'):  # numpy scalar
                result[key] = value.item()
            elif isinstance(value, (np.integer, np.floating)):
                result[key] = float(value)
            elif isinstance(value, np.ndarray):
                result[key] = value.tolist()
            else:
                result[key] = value
        return result
    
    def run_multiple_tests(
        self,
        signal_func,
        test_cases: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run repainting test on multiple historical decisions.
        
        Args:
            signal_func: Signal generation function
            test_cases: List of dicts with 'initial_data', 'decision_time', 'symbol' keys
            **kwargs: Additional arguments for signal_func
            
        Returns:
            Summary of all test results
        """
        all_results = []
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"[REPAINTING TEST] Running test case {i+1}/{len(test_cases)}")
            
            result = self.run_test(
                signal_func=signal_func,
                initial_data=test_case['initial_data'],
                decision_time=test_case['decision_time'],
                symbol=test_case['symbol'],
                **kwargs
            )
            all_results.append({
                "test_case_index": i,
                "symbol": test_case['symbol'],
                "decision_time": test_case['decision_time'].isoformat(),
                "results": result
            })
        
        # Summary
        total_tests = len(all_results)
        passed_tests = sum(1 for r in all_results 
                          if all(s["signals_equal"] for s in r["results"]))
        
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "pass_rate": passed_tests / total_tests if total_tests > 0 else 0.0,
            "detailed_results": all_results
        }
        
        if passed_tests == total_tests:
            logger.info(f"[REPAINTING BATTERY] ALL {total_tests} TESTS PASSED")
        else:
            logger.warning(
                f"[REPAINTING BATTERY] {passed_tests}/{total_tests} TESTS PASSED, "
                f"{total_tests - passed_tests} FAILED"
            )
        
        return summary


# Convenience function
def run_repainting_test(
    signal_func,
    initial_data: Dict[str, Any],
    decision_time: datetime,
    symbol: str,
    **signal_kwargs
) -> List[Dict]:
    """
    Run repainting test with minimal setup.
    
    Args:
        signal_func: Signal function taking (data, decision_time, symbol)
        initial_data: Market data at time T
        decision_time: Decision timestamp T
        symbol: Trading symbol
        **signal_kwargs: Additional signal function arguments
        
    Returns:
        List of test results for each revelation step
    """
    test = RepaintingTest(max_bars_revealed=50)
    return test.run_test(
        signal_func=signal_func,
        initial_data=initial_data,
        decision_time=decision_time,
        symbol=symbol,
        **signal_kwargs
    )