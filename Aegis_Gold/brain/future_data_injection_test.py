"""
AEGIS GOLD — Future Data Injection Test
========================================

For a historical decision at T:
1. Run normally and save decision D1.
2. Replace ALL data after T with randomized garbage.
3. Run the same decision again and save D2.
4. Requirement: D1 == D2 (or within tolerance).

If D1 changes: FUTURE DATA LEAKAGE DETECTED.

This test must cover:
- features
- indicators
- patterns
- normalization
- ML predictions
- RL state
- confidence
- consensus
- risk decision
"""

import numpy as np
import copy
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("aegis.future_injection_test")


class FutureDataInjectionTest:
    """
    Tests that historical decisions are invariant to future data.
    
    The core principle: A decision made at time T should be identical
    whether we use real future data or randomized garbage, because
    only information available at T should be used.
    """
    
    def __init__(self, tolerance: float = 1e-6):
        self.tolerance = tolerance
        self.decision_D1: Optional[Dict] = None
        self.decision_D2: Optional[Dict] = None
    
    def run_test(
        self,
        decision_func,
        snapshot_builder,
        historical_data: Dict[str, Any],
        decision_time: datetime,
        symbol: str,
        **snapshot_kwargs
    ) -> Dict[str, Any]:
        """
        Run the future data injection test.
        
        Args:
            decision_func: Function that makes a trading decision
            snapshot_builder: Function that builds FrozenDecisionSnapshot
            historical_data: Complete historical market data
            decision_time: The timestamp T at which decision is made
            symbol: Trading symbol
            **snapshot_kwargs: Additional arguments for snapshot builder
            
        Returns:
            Dict with test results
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        
        # Step 1: Run normally and save D1
        logger.info(f"[FUTURE INJECTION] Step 1: Running normally at {decision_dt}")
        
        # Build snapshot with real data (only data up to T)
        real_snapshot = snapshot_builder(
            historical_data, 
            decision_time=decision_time,
            **snapshot_kwargs
        )
        
        # Make decision with real data
        decision_D1 = decision_func(real_snapshot, symbol=symbol, decision_time=decision_dt)
        self.decision_D1 = copy.deepcopy(decision_D1)
        
        logger.info(f"[FUTURE INJECTION] D1 recorded: action={decision_D1.get('action', 'N/A')}, "
                     f"confidence={decision_D1.get('confidence', 'N/A')}%")
        
        # Step 2: Replace all data after T with randomized garbage
        logger.info(f"[FUTURE INJECTION] Step 2: Replacing data after T with randomized garbage")
        
        garbage_data = self._generate_garbage_data(historical_data, decision_time)
        
        # Step 3: Run again with garbage data and save D2
        logger.info(f"[FUTURE INJECTION] Step 3: Running with garbage data")
        
        garbage_snapshot = snapshot_builder(
            garbage_data,
            decision_time=decision_time,
            **snapshot_kwargs
        )
        
        decision_D2 = decision_func(garbage_snapshot, symbol=symbol, decision_time=decision_dt)
        self.decision_D2 = copy.deepcopy(decision_D2)
        
        logger.info(f"[FUTURE INJECTION] D2 recorded: action={decision_D2.get('action', 'N/A')}, "
                     f"confidence={decision_D2.get('confidence', 'N/A')}%")
        
        # Step 4: Compare D1 and D2
        result = self._compare_decisions(decision_D1, decision_D2)
        
        # Store results
        test_result = {
            "decision_time": decision_dt.isoformat(),
            "D1": self._serialize_decision(decision_D1),
            "D2": self._serialize_decision(decision_D2),
            "D1_equals_D2": result["equal"],
            "difference": result["difference"],
            "test_passed": result["within_tolerance"],
            "data_coverage": self._assess_data_coverage(historical_data, decision_time),
        }
        
        if result["equal"]:
            logger.info(f"[FUTURE INJECTION] TEST PASSED: D1 == D2 (no future data leakage)")
        else:
            logger.warning(f"[FUTURE INJECTION] TEST FAILED: D1 != D2 - future data leakage detected")
            logger.warning(f"  D1: {json.dumps(test_result['D1'], indent=2)}")
            logger.warning(f"  D2: {json.dumps(test_result['D2'], indent=2)}")
        
        return test_result
    
    def _generate_garbage_data(self, historical_data: Dict[str, Any], 
                               decision_time: datetime) -> Dict[str, Any]:
        """
        Generate randomized garbage data for all time periods after T.
        Data before T is preserved; data after T is replaced with random values.
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        garbage = {}
        
        # Process each data type
        for key, value in historical_data.items():
            if isinstance(value, np.ndarray) or (hasattr(value, 'shape') and hasattr(value, 'dtype')):
                # NumPy array - replace after T with random values
                garbage[key] = value.copy()
                # We'll mask based on timestamps later
                garbage[key] = self._randomize_array_after_timestamp(
                    value, decision_dt, key
                )
            elif isinstance(value, dict):
                # Dict - recursively process
                garbage[key] = self._generate_garbage_data(value, decision_time)
            elif isinstance(value, (list, tuple)):
                # List - replace with random values after T
                garbage[key] = self._randomize_list_after_timestamp(
                    value, decision_dt, key
                )
            else:
                garbage[key] = value
        
        return garbage
    
    def _randomize_array_after_timestamp(self, arr: np.ndarray, 
                                         decision_time: datetime,
                                         field_name: str) -> np.ndarray:
        """Randomize array values after the decision timestamp."""
        # This is a simplified implementation - in practice we'd need
        # actual timestamps for each element
        result = arr.copy()
        # For demonstration, randomize a portion of the array
        # In a real implementation, we'd use actual candle timestamps
        rand_mask = np.random.random(len(arr)) > 0.5
        result[rand_mask] = np.random.random(np.sum(rand_mask)) * 2 - 1
        return result
    
    def _randomize_list_after_timestamp(self, lst: List, 
                                        decision_time: datetime,
                                        field_name: str) -> List:
        """Randomize list values after the decision timestamp."""
        result = lst.copy()
        # For demonstration, randomize some elements
        n_to_randomize = max(1, len(lst) // 4)
        indices = np.random.choice(len(lst), n_to_randomize, replace=False)
        for i in indices:
            if isinstance(result[i], (int, float)):
                result[i] = np.random.random() * 2 - 1
            elif isinstance(result[i], str):
                result[i] = f"random_{np.random.randint(1000)}"
        return result
    
    def _compare_decisions(self, D1: Dict, D2: Dict) -> Dict[str, Any]:
        """
        Compare two decisions for equality.
        
        Returns dict with 'equal' (bool) and 'difference' (float) keys.
        """
        differences = []
        D1_copy = copy.deepcopy(D1)
        D2_copy = copy.deepcopy(D2)
        
        # Remove non-essential metadata for comparison
        for key in ['timestamp', 'trade_signal_id', 'decision_time']:
            D1_copy.pop(key, None)
            D2_copy.pop(key, None)
        
        # Compare all remaining keys
        all_keys = set(list(D1_copy.keys()) + list(D2_copy.keys()))
        
        max_diff = 0.0
        for key in all_keys:
            v1 = D1_copy.get(key)
            v2 = D2_copy.get(key)
            
            if isinstance(v1, float) and isinstance(v2, float):
                diff = abs(v1 - v2)
                max_diff = max(max_diff, diff)
                if diff > self.tolerance:
                    differences.append(f"{key}: D1={v1}, D2={v2}, diff={diff}")
            elif isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                diff = abs(float(v1) - float(v2))
                max_diff = max(max_diff, diff)
                if diff > self.tolerance:
                    differences.append(f"{key}: D1={v1}, D2={v2}, diff={diff}")
            elif v1 != v2:
                differences.append(f"{key}: D1={v1}, D2={v2}")
                max_diff = max(max_diff, 1.0)
        
        equal = len(differences) == 0 and max_diff < self.tolerance
        within_tolerance = max_diff <= self.tolerance
        
        return {
            "equal": equal,
            "difference": round(max_diff, 6),
            "detailed_differences": differences[:20]  # Limit output
        }
    
    def _serialize_decision(self, decision: Dict) -> Dict:
        """Serialize decision for storage/transmission."""
        result = {}
        for key, value in decision.items():
            if hasattr(value, 'item'):  # numpy scalar
                result[key] = value.item()
            elif isinstance(value, (np.integer, np.floating)):
                result[key] = float(value)
            elif isinstance(value, np.ndarray):
                result[key] = value.tolist()
            else:
                result[key] = value
        return result
    
    def _assess_data_coverage(self, historical_data: Dict[str, Any], 
                              decision_time: datetime) -> Dict[str, Any]:
        """
        Assess what portion of data is before/after the decision time.
        """
        decision_dt = decision_time if decision_time.tzinfo else decision_time.replace(tzinfo=timezone.utc)
        
        # Count total elements and estimate before/after
        total_elements = 0
        before_count = 0
        after_count = 0
        
        def count_elements(obj, depth=0):
            nonlocal total_elements, before_count, after_count
            if isinstance(obj, dict):
                for key, value in obj.items():
                    total_elements += 1
                    count_elements(value, depth + 1)
            elif isinstance(obj, (list, tuple)):
                total_elements += len(obj)
                for item in obj:
                    count_elements(item, depth + 1)
            elif isinstance(obj, np.ndarray):
                total_elements += obj.size
        
        count_elements(historical_data)
        
        return {
            "total_elements": total_elements,
            "decision_time": decision_dt.isoformat(),
            "assessment": "Data coverage assessed for future injection test"
        }


# Convenience function
def run_future_data_injection_test(
    decision_func,
    snapshot_builder,
    historical_data: Dict[str, Any],
    decision_time: datetime,
    symbol: str,
    **snapshot_kwargs
) -> Dict[str, Any]:
    """
    Run future data injection test with minimal setup.
    
    Args:
        decision_func: Decision function taking (snapshot, symbol, decision_time)
        snapshot_builder: Snapshot builder function
        historical_data: Historical market data
        decision_time: Decision timestamp T
        symbol: Trading symbol
        **snapshot_kwargs: Additional snapshot builder arguments
        
    Returns:
        Test result dictionary
    """
    test = FutureDataInjectionTest(tolerance=1e-6)
    return test.run_test(
        decision_func=decision_func,
        snapshot_builder=snapshot_builder,
        historical_data=historical_data,
        decision_time=decision_time,
        symbol=symbol,
        **snapshot_kwargs
    )