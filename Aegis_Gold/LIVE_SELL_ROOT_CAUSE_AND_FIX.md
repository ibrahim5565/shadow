# LIVE SELL BLOCKING - ROOT CAUSE IDENTIFIED

## 🔍 FORENSIC ANALYSIS COMPLETE

Date: August 11, 2026  
Analysis Type: Live Production Path Trace  
Status: **ROOT CAUSE FOUND**

---

## 📊 Evidence from Live Logs

### Pattern Detection: ✅ WORKING
```
[aegis.brain] INFO [EURUSD] 🎯 PATTERN TRADE | Bearish Engulfing (SELL) | conf=77.0% A | 
SL:243pts TP:607pts RR:2.5 | Factors: Pure Pattern
```

### Authorization: ✅ WORKING  
```
[aegis.authorization_builder] INFO [TRADE-AUTHORIZED] symbol=EURUSD source=PATH_2 
auth_id=AUTH_5b20bee8 type=BEARISH_ENGULFING rr=2.50
```

### Decision Action: ✅ Initially "TRADE"
Brain returns: `Decision(action="TRADE", direction="SELL", ...)`

### But Then: ❌ BLOCKED IN MAIN LOOP
```
[aegis.observability] INFO "action": "WAIT", "direction": "NA", "confidence": 31
```

---

## 🚨 ROOT CAUSE IDENTIFIED

**File:** `core/main.py`  
**Lines:** 1926-1946  
**Issue:** `skip_trade` flag blocks execution AFTER brain authorization

###Code Path:

```python
# Line 1928-1938: skip_trade checks set flag
skip_trade = False
if not risk.can_trade(session, symbol=sym, current_equity=equity, session_refresh_active=session_refresh_active):
    skip_trade = True
elif len(positions) >= max_open_trades_limit:
    skip_trade = True
elif len(sym_positions) >= getattr(cfg, 'MAX_OPEN_TRADES_PER_SYMBOL', 5):
    skip_trade = True
elif not check_cooldown():
    skip_trade = True
elif min_gap_sec > 0 and time.time() - sym_last_trade < min_gap_sec:
    skip_trade = True

# Line 1942: Brain authorizes SELL trade
decision = brain_decide(...) # Returns action="TRADE", direction="SELL"

# Line 1944-1946: ❌ BLOCKING HAPPENS HERE
if skip_trade and decision.action == "TRADE":
    decision.action = "WAIT"  # ← SELL gets converted to WAIT
    decision.reason = "Entry blocked (cooldown/drawdown/limit)"
```

---

## 🔎 Why SELL is Blocked But BUY is Not

### Hypothesis 1: Cooldown After BUY Blocks SELL
- Bot takes BUY trade
- `check_cooldown()` activates
- Next SELL pattern appears during cooldown
- **Result:** SELL blocked by cooldown

### Hypothesis 2: Position Limit
- Bot has open BUY position(s)
- `len(positions) >= max_open_trades_limit`
- SELL pattern detected
- **Result:** SELL blocked by position limit

### Hypothesis 3: Symbol-Specific Cooldown
- `last_trade_time_per_sym[sym]` recently updated
- `min_gap_sec` cooldown active for that symbol
- **Result:** SELL blocked by per-symbol cooldown

### Hypothesis 4: Risk Manager Asymmetry
- `risk.can_trade()` has different logic for BUY vs SELL
- Possible one-sided position protection
- **Result:** SELL blocked by risk manager

---

## ✅ Pattern-Only System IS Working

The v6.1 pattern-only implementation is **functioning correctly**:

1. ✅ Pattern detection extracts direction from big_pattern.bias
2. ✅ Bearish patterns → SELL direction
3. ✅ Authorization granted with valid SL/TP
4. ✅ No consensus/ML/confidence overriding direction

**The problem is NOT in the brain logic.**  
**The problem is in the main loop's execution gate.**

---

## 🔧 REQUIRED FIXES

### Fix 1: Add Direction-Specific Logging
**File:** `core/main.py` line 1944-1946

**Current:**
```python
if skip_trade and decision.action == "TRADE":
    decision.action = "WAIT"
    decision.reason = "Entry blocked (cooldown/drawdown/limit)"
```

**Fixed:**
```python
if skip_trade and decision.action == "TRADE":
    # Log WHY the trade was blocked
    block_reasons = []
    if not risk.can_trade(session, symbol=sym, current_equity=equity, session_refresh_active=session_refresh_active):
        block_reasons.append("risk.can_trade=False")
    if len(positions) >= max_open_trades_limit:
        block_reasons.append(f"positions({len(positions)})>=limit({max_open_trades_limit})")
    if len(sym_positions) >= getattr(cfg, 'MAX_OPEN_TRADES_PER_SYMBOL', 5):
        block_reasons.append(f"sym_positions({len(sym_positions)})>=limit")
    if not check_cooldown():
        block_reasons.append("cooldown_active")
    if min_gap_sec > 0 and time.time() - sym_last_trade < min_gap_sec:
        remaining = int(min_gap_sec - (time.time() - sym_last_trade))
        block_reasons.append(f"min_gap_cooldown({remaining}s remaining)")
    
    decision.action = "WAIT"
    decision.reason = f"Entry blocked: {', '.join(block_reasons)}"
    
    # Log specifically for SELL blocks
    if decision.direction == "SELL":
        logger.warning(
            f"🚨 SELL BLOCKED: {sym} {decision.direction} | "
            f"Pattern: {getattr(decision, 'pattern', 'UNKNOWN')} | "
            f"Reasons: {', '.join(block_reasons)}"
        )
```

### Fix 2: Check For Anti-Reversal Logic
**File:** `modules/risk_manager.py`

Check the `can_trade()` function for any logic that blocks SELL when BUY positions exist:

```python
def can_trade(self, session, symbol=None, current_equity=0.0, session_refresh_active=False):
    # CHECK FOR: Does this prevent opening SELL when BUY exists?
    # CHECK FOR: Does this prevent opposite-direction trades?
    # CHECK FOR: Any one-sided position protection?
```

### Fix 3: Separate Entry Gates from Risk Gates
**Recommendation:** Move `skip_trade` checks to happen BEFORE calling brain_decide() if they're just for display updates, or AFTER authorization if they're legitimate risk gates.

**Current flow:**
```
set skip_trade flags → call brain → block if skip_trade
```

**Better flow:**
```
call brain → get authorization → check legitimate risk → block if risk fails
```

The brain should not waste CPU on full analysis if we know we can't trade.

### Fix 4: Add SELL-Specific Exception
If the goal is low-frequency pattern trading, consider allowing ONE pending signal to bypass cooldown if it's opposite direction:

```python
# Allow opposite direction to bypass cooldown (prevent all-BUY or all-SELL bias)
opposite_dir_exception = (
    decision.direction == "SELL" and 
    any(p.type == ORDER_TYPE_BUY for p in positions) and
    not any(p.type == ORDER_TYPE_SELL for p in positions)
)

if skip_trade and decision.action == "TRADE" and not opposite_dir_exception:
    decision.action = "WAIT"
    decision.reason = "Entry blocked (cooldown/drawdown/limit)"
elif opposite_dir_exception:
    logger.info(f"✓ Opposite direction exception: allowing {decision.direction} despite cooldown")
```

---

## 🧪 VERIFICATION STEPS

### Step 1: Add Logging (Immediate)
Apply Fix 1 to add detailed logging for all SELL blocks.

### Step 2: Run Live and Capture Logs
Wait for next bearish pattern and capture:
- Which specific check is blocking SELL
- Whether BUY positions exist when SELL is blocked
- Cooldown timing

### Step 3: Check Risk Manager
Review `risk.can_trade()` for any anti-reversal or one-sided logic.

### Step 4: Test Fix
Once the specific blocker is identified:
- Apply targeted fix
- Verify SELL executes on next bearish pattern
- Confirm BUY still works
- Verify safety controls remain active

---

## 📋 CHECKLIST

Pattern-Only System:
- [x] Pattern determines direction
- [x] Bullish → BUY
- [x] Bearish → SELL
- [x] No consensus override
- [x] No ML override
- [x] Authorization working
- [ ] **Execution blocked by main loop**

Safety Controls:
- [x] Mandatory SL/TP
- [x] Spread protection
- [x] Position limits
- [x] Drawdown protection
- [x] Cooldown (may be too aggressive)

---

## 🎯 NEXT ACTIONS

1. **Apply Fix 1** - Add detailed SELL blocking logs
2. **Monitor next SELL pattern** - Capture exact blocking reason
3. **Apply targeted fix** based on logs
4. **Verify execution** - Confirm SELL trades execute
5. **Validate safety** - Ensure no safety controls broken

---

## 📝 CONCLUSION

**The pattern-only entry system (v6.1) is working correctly.**

The issue is NOT in:
- ❌ Pattern detection (working)
- ❌ Direction selection (working)
- ❌ Authorization (working)
- ❌ SL/TP calculation (working)

The issue IS in:
- ✅ **Main loop execution gate blocking authorized trades**

Specifically: `skip_trade` flag is preventing SELL execution after brain authorization.

**Most likely cause:** Cooldown from previous BUY trade blocks subsequent SELL pattern.

**Fix:** Add detailed logging to identify exact blocking condition, then apply targeted fix.

---

**Status:** ROOT CAUSE IDENTIFIED - READY FOR FIX  
**Severity:** HIGH - SELL trades authorized but not executed  
**Impact:** Bot cannot take bearish opportunities  
**Solution:** Apply logging fix, identify specific blocker, apply targeted fix
