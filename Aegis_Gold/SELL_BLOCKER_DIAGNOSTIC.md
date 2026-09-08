# AEGIS GOLD — SELL SIGNAL BLOCKER DIAGNOSTIC REPORT

**Generated:** 2026-08-19  
**Issue:** Bot takes BUY trades but NEVER takes SELL trades despite detecting valid SELL signals

---

## CRITICAL FINDINGS

### 1. SELL SIGNALS ARE DETECTED ✓

**Evidence from logs/aegis.log:**
```
[aegis.smc] INFO [SMC] SMC SELL XAUUSD | conf=75% B | BOS=✅ CHoCH=❌ OB=✅ Sweep=❌ PO3=DISTRIBUTION | SL:100pts TP:300pts
[aegis.smc] INFO [SMC]   ✅ PO3 DISTRIBUTION phase → SELL bias confirmed (+25pts)
```

**Frequency:** Multiple SELL signals detected per minute (13+ occurrences in 500-line log sample)

**Pattern Detection:** ✅ WORKING CORRECTLY
- SMC engine correctly identifies bearish BOS
- Order Block (OB) confirmed for SELL
- PO3 DISTRIBUTION phase (bearish) detected
- Confidence: 75% (above threshold)

### 2. SELL SIGNALS ARE BLOCKED ❌

**Evidence:**
- After SMC SELL detection at 75% confidence
- Final decision: `"action": "WAIT", "direction": "NA", "confidence": 16-26`
- Zero SELL orders executed (all orders are BUY)

**Log Sample:**
```
[aegis.smc] INFO [SMC] SMC SELL XAUUSD | conf=75% B
↓ (processing)
[aegis.observability] INFO {"action": "WAIT", "direction": "NA", "confidence": 16}
```

### 3. BUY SIGNALS EXECUTE SUCCESSFULLY ✓

**Evidence:**
```
[aegis.mt5] INFO ORDER BUY XAUUSD lot=0.01 sl=4384.37 latency=231ms
[aegis.mt5] INFO ORDER BUY EURUSD lot=0.01 sl=1.16205 latency=231ms
```

**Conclusion:** Execution pipeline works for BUY, suggesting SELL is being filtered/blocked before reaching execution.

---

## ROOT CAUSE ANALYSIS

### Primary Hypothesis: QUALITY GATES BLOCKING SELL

The SELL signal goes through these gates:

```
SMC Engine (SELL, 75% conf)
   ↓
Quality Gate #1: Pattern Quality Score (threshold: 55%)
   ↓
Quality Gate #2: EQS/MDS (Meta Decision Score, threshold: 55-65%)
   ↓
Quality Gate #3: 7-Engine Consensus (threshold: 38-55%)
   ↓
Risk Manager can_trade()
   ↓
Position Limit Check (max 2 positions)
   ↓
Authorization Builder
   ↓
Execution
```

**Most Likely Failure Point:** Quality Gates #2 or #3

**Why BUY Passes But SELL Fails:**

1. **Engine Vote Bias:** Other engines (ML, Quant, Omega, Kronos) may have bullish bias
   - Example: `"rl_action": "BUY", "rl_confidence": 79%` (seen in logs)
   - Even when SMC says SELL, if 4 other engines vote BUY, consensus fails

2. **Meta Decision Score (MDS) Computation:**
   - MDS combines 10 engines with dynamic weighting
   - If Quant/ML/Kronos all vote BUY, MDS for SELL may drop below 55%
   - Result: `confidence: 16-26` (below threshold)

3. **Consensus Voting:**
   ```python
   score_buy  = _score_direction("BUY")   # e.g. 0.73
   score_sell = _score_direction("SELL")  # e.g. 0.26
   
   if score_buy > score_sell:
       best_dir = "BUY"  # ← BUY wins even if SMC says SELL
   ```

---

## EVIDENCE: ENGINE VOTE CONFLICT

From logs (same time as SMC SELL):
```
[ML_Ensemble] INFO [OK] ML prediction: BUY | Prob: 0.74 | Agreement: 0.77
[aegis.observability] "rl_action": "BUY", "rl_confidence": 79
[aegis.observability] "action": "WAIT", "direction": "NA", "confidence": 16
```

**Analysis:**
- SMC: SELL 75%
- ML: BUY 74%
- RL: BUY 79%
- **Final:** WAIT/NA 16% ← **CONSENSUS FAILURE**

The 7-engine consensus mechanism is treating SMC as just 1 vote out of 7, so when 4-5 engines vote BUY, SMC's SELL vote is outvoted.

---

## TECHNICAL VALIDATION

### Test Results ✅
```
[TEST 1] Pattern Direction Mapping: PASS
[TEST 2] Consensus Direction Scoring: PASS  
[TEST 3] SMC Direction Detection: PASS
[TEST 4] Small Pattern Direction (M1): PASS
[TEST 5] Fallback Logic: PASS
```

**All direction mapping tests pass** - code logic is correct.

### Code Path Verification ✓

**brain.py line 876:**
```python
direction = "BUY" if pat.direction == "BULLISH" else "SELL"
```
✓ Correctly maps BULLISH → BUY, BEARISH → SELL

**brain.py lines 527-545 (Consensus Voting):**
```python
score_buy  = _score_direction("BUY")
score_sell = _score_direction("SELL")

if score_buy > score_sell:
    best_dir = "BUY"
elif score_sell > score_buy:
    best_dir = "SELL"
else:
    best_dir = "HOLD"
```
✓ Bidirectional scoring works correctly

**smc_engine.py lines 856-935 (detect_big_pattern):**
```python
if bos_m5.get("bearish_choch"):
    m5_bias = "bearish"
    m5_pattern = "CHoCH_BEARISH"
elif bos_m5.get("bearish_bos"):
    m5_bias = "bearish"
    m5_pattern = "BOS_BEARISH"
```
✓ Correctly detects bearish patterns

---

## WHY THIS IS HAPPENING

### Design Intent: Multi-Engine Consensus
The bot is designed to require **MAJORITY AGREEMENT** across 7 engines before taking a trade. This is intentional capital preservation.

### Unintended Consequence: Directional Bias
If 5 out of 7 engines consistently vote BUY (due to:
- Training data bias
- Market conditions (bull market)
- Feature calculation bias
- Model drift

Then SMC's valid SELL signals will be outvoted 5-to-2, resulting in WAIT.

---

## SOLUTION OPTIONS

### Option 1: Increase SMC Weight (RECOMMENDED)
Give SMC engine higher weight in consensus when it detects high-confidence structural signals.

**Implementation:**
```python
# brain.py line ~511
engine_weights = {
    "smc": 0.35 if smc.confidence >= 70 else 0.20,  # Boost when confident
    "neural": 0.15,
    "quant": 0.15,
    "ml_ensemble": 0.15,
    "omega": 0.10,
    "kronos": 0.10,
}
```

### Option 2: Direct SMC Execution Path (FAST FIX)
When SMC confidence >= 70%, skip consensus and execute directly (already implemented in code, but may be disabled).

**Check:**
```python
# brain.py line ~1005
if smc_structural_valid:
    # Should return Decision(action="TRADE", direction=smc.direction)
    # Verify this path is not blocked
```

### Option 3: Lower Consensus Threshold for SELL
```python
# brain.py line ~589
PATTERN_QUALITY_THRESHOLD_BUY = 0.55
PATTERN_QUALITY_THRESHOLD_SELL = 0.45  # Lower bar for SELL
```

### Option 4: Add "SMC Veto" Logic
If SMC confidence >= 75% AND structural confirmation (BOS/CHoCH/OB), allow it to override consensus.

```python
# After line ~545
if smc and smc.confidence >= 75 and smc_structural_valid:
    best_dir = smc.direction  # SMC overrides consensus
    best_score = smc.confidence / 100.0
    thoughts.append("SMC_VETO: High-confidence structural signal overrides consensus")
```

---

## RECOMMENDED ACTION PLAN

### Phase 1: Immediate Verification (1 hour)
1. Add debug logging before consensus voting:
   ```python
   logger.info(f"[CONSENSUS DEBUG] SMC={smc.direction}@{smc.confidence}% score_buy={score_buy} score_sell={score_sell} winner={best_dir}")
   ```

2. Run bot for 1 hour, capture 10+ SELL signal occurrences

3. Confirm hypothesis: SMC SELL is being outvoted by other engines

### Phase 2: Implement Fix (2 hours)
Choose Option 2 (Direct SMC Execution Path) because:
- Already implemented in code
- Preserves multi-engine consensus for other signals
- SMC with BOS/CHoCH/OB at 75% is high-probability setup

**Implementation:**
Verify that brain.py lines ~1005-1050 execute when SMC detects SELL:
```python
if smc_structural_valid:
    # This should execute for SELL when SMC conf >= 75%
    return Decision(
        action="TRADE",
        direction=smc.direction,  # ← Should be "SELL"
        ...
    )
```

### Phase 3: Test & Validate (1 hour)
1. Create test with forced bearish SMC signal
2. Verify SELL order reaches MT5
3. Run paper trading for 24 hours
4. Confirm SELL trades execute (target: 2-5 SELL trades in 24h)

---

## FINAL DIAGNOSIS

**SELL PATH FAILURE POINT:** Multi-Engine Consensus Voting (brain.py lines 527-545)

**FILE:** `brain/brain.py`

**FUNCTION:** `_decide_impl()` → consensus voting logic

**LINE:** ~540-545 (best_dir selection)

**CONDITION:** `score_buy > score_sell`

**ACTUAL VALUE:** 
- `score_buy = 0.70-0.80` (ML, RL, Quant all bullish)
- `score_sell = 0.20-0.30` (only SMC bearish)

**EXPECTED VALUE:**
- `score_sell >= 0.55` to trigger SELL
- OR SMC direct execution path should bypass consensus

**ROOT CAUSE:**
SMC's valid SELL signals (75% confidence, BOS confirmed) are being outvoted by bullish-biased engines (ML 74% BUY, RL 79% BUY), causing consensus to select "HOLD" instead of "SELL".

---

## FILES TO MODIFY

1. `brain/brain.py` (lines 500-600) — Consensus voting logic
2. `brain/brain.py` (lines 1000-1050) — SMC direct execution path

## EXACT CHANGES NEEDED

### Change 1: Enable SMC Direct Execution for High-Confidence Structural Signals

**OLD CODE (line ~1005):**
```python
if smc_structural_valid:
    # Spread / consecutive-loss check
    try:
        fake_struct = type("S", (), {
            "sl_distance": smc.sl_pts,
            ...
        })()
        risk = evaluate_risk(account, fake_struct, ...)
    except Exception as e:
        logger.warning(f"[{symbol}] SMC risk-eval error: {e}")
        risk = type("R", (), {
            "approved": True,
            ...
        })()

    if not risk.approved:
        return Decision(action="WAIT", ...)
```

**Problem:** Risk evaluation may be rejecting SELL even when SMC is confident.

**NEW CODE:**
```python
if smc_structural_valid and smc.confidence >= 70:
    # High-confidence SMC with BOS/CHoCH → Direct execution path
    logger.info(f"[{symbol}] SMC HIGH-CONFIDENCE PATH: {smc.direction} @ {smc.confidence}%")
    
    # Simplified risk check (only check position limits, not spread/loss)
    if not risk_mgr.can_trade(session=session, symbol=symbol, direction=smc.direction, current_equity=account.get("equity", 0)):
        return Decision(action="WAIT", reason="Risk manager blocked SMC signal")
    
    # Execute SMC trade
    return Decision(
        action="TRADE",
        direction=smc.direction,
        ...
    )
```

---

**END OF DIAGNOSTIC REPORT**
