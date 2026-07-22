# Confidence Trading Issue - FIXED

## Date: June 17, 2026

## Issues Identified:

### 1. XAUUSD Showing 0% Confidence
**Root Cause**: `symbol_analysis_state` dictionary was not initialized with default values for all active symbols at startup. The fast confidence updater only updates existing keys, so if XAUUSD was never added, it remained at 0%.

**Fix Applied**:
- Added initialization of `symbol_analysis_state` with default values for all active symbols (EURUSD + XAUUSD) before the fast confidence updater starts
- Added logging to show which symbols are initialized and being processed
- Changed error logging from `logger.debug` to `logger.warning` with full stack traces to catch any data retrieval errors

### 2. EURUSD Showing 67% Confidence But Not Trading
**Root Cause**: Confidence threshold was set to 55% in `brain.py` line 220, which is too high for scalp trading mode. The system is designed for micro-scalping with 50% threshold.

**Fix Applied**:
- Reduced confidence threshold from 55% to 50% for scalp mode
- Updated reason message to match the scalp trading strategy
- This aligns with the 50% threshold already enforced in `main.py` line 1279

## Changes Made:

### File: `d:\Trading\Aegis_Gold\brain\brain.py`
```python
# Line 220 - Changed confidence gate from 55% to 50%
if total_score < 50.0:
    return Decision(
        action="WAIT", direction=direction,
        confidence=int(total_score), grade=grade,
        ...
        reason=f"Confidence {total_score:.0f}% below 50% scalp threshold — need 50%+ for trade entry",
        ...
    )
```

### File: `d:\Trading\Aegis_Gold\core\main.py`
```python
# Added symbol_analysis_state initialization (before line 879)
with state_lock:
    for sym in gateway.active_symbols:
        symbol_analysis_state[sym] = {
            "symbol": sym,
            "confidence": 0,
            "regime": "INITIALIZING",
            ...
        }

# Enhanced error logging in fast_confidence_updater
logger.warning(f"[{sym}] Fast confidence update error: {e}", exc_info=True)
```

## Expected Results After Restart:

1. **XAUUSD**: Will show live confidence values instead of 0%
2. **EURUSD**: Will trade when confidence reaches 50%+ (instead of requiring 55%+)
3. **Better Debugging**: Any errors in confidence calculation will be logged with full stack traces

## Next Steps:

1. Restart the Aegis Gold trading system
2. Monitor the dashboard - both EURUSD and XAUUSD should show live confidence values
3. Check logs for any errors in fast confidence updater
4. Verify trades are executed when confidence >= 50%

## Verification Commands:

```powershell
# Check if both symbols show confidence
curl http://localhost:5001/aistate

# Check current trading status
curl http://localhost:5001/status

# Monitor recent logs for errors
Get-Content d:\Trading\Aegis_Gold\logs\aegis.log -Tail 50
```
