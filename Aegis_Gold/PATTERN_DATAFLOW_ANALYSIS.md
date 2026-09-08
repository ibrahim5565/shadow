# AEGIS GOLD — PATTERN SIGNAL DATA-FLOW ANALYSIS

**Date:** 2026-08-18  
**Analysis Type:** Production Code Trace  
**Scope:** Complete pattern detection → decision pipeline

---

## EXECUTIVE SUMMARY

**Critical Finding:** The `pattern_signal` parameter that was added to `DecisionFusionV2.fuse()` is **NEVER USED** in production because:

1. **Pattern-detected trades bypass the fusion layer** (early return at line 720)
2. **The fusion layer is only reached by non-pattern signals** (scalp/SMC fallbacks)
3. **Pattern information is passed as `scalp_signal`, not `pattern_signal`**
4. **The new `pattern_signal` parameter has no producer** in the codebase

### Status

- ✅ The fix prevents NameError (parameter exists with safe default)
- ❌ The fix does NOT prove pattern signals are actually used
- ❌ The architectural design shows patterns bypass fusion entirely

---

## COMPLETE PRODUCTION DATA-FLOW

### Decision Pipeline (brain.py, `decide()` function)

```
Entry Point: decide(ticks, candles_m5, account, risk_mgr, ...)
       ↓
  LAYER 1: LAYER 2A: PATTERN RECOGNITION (lines 658-720)
       ↓
  SMC Pattern Engine: find_smc_enhanced_patterns()
       ↓
  patterns found?
       │
       ├─ YES: Pattern meets confidence & RR threshold?
       │         ↓
       │        YES: Return Decision(
       │             action="TRADE",
       │             signal_source="PATTERN_ENGINE",  ← EARLY RETURN
       │             direction=detected_direction,
       │             confidence=pattern_confidence,
       │             pattern=pattern_name
       │        )
       │         ↓
       │     NO: Continue fallback
       │
       └─ NO: Continue fallback
              ↓
        LAYER 2B: STANDARD SMC (lines 725-850+)
              ↓
        analyze_smc(...)
              ↓
        SMC signal found?
              ↓
          YES: Return Decision(signal_source="SMC", ...)
          NO: Continue fallback
              ↓
        LAYER 3A: NEURAL/QUANT/ML/RL VOTING (lines ~850-1300)
              ↓
        Multiple engine outputs
              ↓
        Decision created with best consensus
        (signal_source defaults to "SCALP")
              ↓
        [AT THIS POINT, pattern bypass complete]
        ↓
   LAYER 3B: DECISION FUSION (line 1354)
        ↓
   DecisionFusionV2().fuse(
       smc_signal={...},
       scalp_signal={...},  ← Gets decision.direction based on signal_source
       pattern_signal=None, ← NEVER POPULATED (always None)
       ...
   )
        ↓
   Return fused Decision
```

---

## DETAILED ANALYSIS

### 1. PATTERN DETECTION PHASE (Lines 658-720)

**Source Code:**
```python
if getattr(cfg, "ENABLE_PATTERN_TRADING", True):
    try:
        from brain.smc_pattern_engine import get_smc_pattern_engine
        smc_pat_eng = get_smc_pattern_engine()
        enhanced_patterns = smc_pat_eng.find_smc_enhanced_patterns(candles_m5, point=point)
        
        if enhanced_patterns:
            best_pat_info = enhanced_patterns[0]
            pat = best_pat_info['pattern']
            final_conf = best_pat_info['final_confidence']
            min_pat_conf = getattr(cfg, "MIN_PATTERN_CONFIDENCE", 65.0)
            
            if final_conf >= min_pat_conf and pat.risk_reward >= getattr(cfg, "PATTERN_MIN_RISK_REWARD", 1.8):
                # ... calculate SL/TP/RR ...
                
                return Decision(                    # ← EARLY RETURN!
                    action="TRADE",
                    direction=direction,
                    confidence=int(final_conf),
                    signal_source="PATTERN_ENGINE",  # ← NOT "PATTERN"
                    pattern=pat.name,
                    ...
                )
```

**Critical Finding:**
- ✅ Pattern IS detected and validated
- ✅ Decision IS created with correct direction/confidence
- ✅ **BUT: Function returns immediately** (line ~720)
- ❌ Fusion layer (line 1354) is **NEVER REACHED**

---

### 2. FUSION LAYER (Lines 1354-1368)

**Source Code:**
```python
fusion_result = DecisionFusionV2().fuse(
    smc_signal={"direction": decision.direction if decision.signal_source == "SMC" else "NONE", "confidence": decision.confidence},
    scalp_signal={"direction": decision.direction if decision.signal_source == "PATTERN" else "NONE", "confidence": decision.confidence},
    ml_prediction=ml_prediction,
    rl_action=rl_action,
    rl_confidence=rl_conf,
    stat_analysis=None,
    macro_blackout=macro_blackout,
    regime_type=decision.regime,
    regime_confidence=getattr(regime_state, "regime_confidence", 0.0),
    regime_ambiguous=getattr(regime_state, "ambiguous", False),
    calibration_penalty=cal_penalty,
    drift_defensive=drift_defensive
    # NOTE: pattern_signal is NEVER passed, defaults to None
)
```

**Critical Findings:**
1. Line 1356: `scalp_signal={"direction": decision.direction if decision.signal_source == "PATTERN" else "NONE", ...}`
   - This line checks if `signal_source == "PATTERN"` but this check is DEAD CODE
   - Why? Because decisions with `signal_source="PATTERN_ENGINE"` returned at line 720!
   - Decisions that reach this line have never had `signal_source == "PATTERN"`

2. The `pattern_signal` parameter is **NEVER passed** (would be line 1367 if it existed)
   - Not in the visible parameters
   - Not passed as keyword argument
   - Defaults to `None` due to method signature: `pattern_signal: Optional[dict] = None`

---

### 3. THE MISSING DATA-FLOW

**Expected Production Chain (NOT IMPLEMENTED):**

```
Pattern Detected
    ↓
pattern_signal = {
    "direction": detected_direction,
    "confidence": pattern_confidence,
    "pattern_name": pattern_type,
    "source": "smc_pattern_engine"
}
    ↓
Decision passes through fusion layer
    ↓
DecisionFusionV2().fuse(..., pattern_signal=pattern_signal, ...)
    ↓
Fusion layer weighs pattern contribution
    ↓
Final decision = fusion result
```

**Actual Production Chain:**

```
Pattern Detected
    ↓
Decision returned immediately
    ↓
Fusion layer BYPASSED
    ↓
Decision returned to caller
```

---

## THE `pattern_signal` PARAMETER AUDIT

### Where It Exists

| File | Line | Context |
|------|------|---------|
| `brain/decision_fusion.py` | 45 | Method signature: `pattern_signal: Optional[dict] = None` |
| `brain/decision_fusion.py` | 62-72 | Safe initialization: `if not isinstance(pattern_signal, dict): ...` |
| `brain/decision_fusion.py` | 109-115 | Processing: `if pattern_signal and pattern_signal.get("direction") != "NONE": ...` |

### Where It's Passed

| File | Line | Context |
|------|------|---------|
| `tests/test_pattern_signal_fix.py` | 21 | Test only: `pattern_signal=None` |
| `tests/test_regression_pattern_signal.py` | 21 | Test only: `pattern_signal=None` |
| `scratch/audit_engines.py` | 108-114 | Audit script only (not production) |

### Where It SHOULD Be Passed

| Location | Status | Issue |
|----------|--------|-------|
| `brain/brain.py` line 1354-1368 | ❌ MISSING | No `pattern_signal=...` in fuse() call |
| Pattern detection code (lines 658-720) | ❌ N/A | Doesn't reach fusion (early return) |

---

## ROOT CAUSE ANALYSIS

### Why Pattern Signals Don't Reach Fusion

**Design Decision (Correct):**
- High-confidence patterns (≥65%) → Execute immediately
- No need for consensus with other engines
- Pattern is the signal source of truth

**Implementation Reality:**
- Patterns bypass fusion via early return
- Fusion layer designed for lower-confidence signals
- Multiple weak signals fused to make decision

**The Fix's Role:**
- ✅ Added `pattern_signal` parameter to prevent crash
- ❌ But no production code passes it
- ❌ Pattern flow designed to bypass fusion, not pass through it

---

## VALIDATION TEST RESULTS

### Trace Execution (trace_pattern_dataflow.py)

**XAUUSD Test:**
```
[PATTERN DETECTION PHASE]
  No patterns detected
  
[BRAIN DECISION PHASE]
  Calling decide() for XAUUSD...
  
[FUSION LAYER INVOKED]
  smc_signal:       {'direction': 'NONE', 'confidence': 0}
  scalp_signal:     {'direction': 'NONE', 'confidence': 0}
  pattern_signal:   None  ← EXPLICIT PARAMETER
  
[RESULT]
  Fusion result: NA WAIT (conf=0%)
```

**EURUSD Test:**
```
[PATTERN DETECTION PHASE]
  No patterns detected
  
[BRAIN DECISION PHASE]
  Calling decide() for EURUSD...
  
[FUSION LAYER INVOKED]
  smc_signal:       {'direction': 'NONE', 'confidence': 0}
  scalp_signal:     {'direction': 'NONE', 'confidence': 0}
  pattern_signal:   None  ← EXPLICIT PARAMETER (NEVER POPULATED)
  
[RESULT]
  Fusion result: SELL WAIT (conf=40%)
```

**Key Finding:**
- ✅ No crashes (fix is working)
- ✅ Fusion receives smc_signal and scalp_signal
- ❌ **Fusion NEVER receives pattern_signal** (always None)
- ❌ Test did not detect actual patterns (market data was synthetic)

---

## PROOF REQUIREMENTS NOT MET

### Requirement 1: Pattern Actually Detected ✅

```python
# Pattern WOULD be detected IF market had the pattern
# But test data had no patterns
# → Proof requires real market data with actual Bullish Engulfing
```

### Requirement 2: Pattern Reaches Fusion Layer ❌

```python
# Pattern early-returns at line 720
# → Never reaches line 1354 fusion layer
# → proof requirement: FAILED
```

### Requirement 3: Fusion Consumes Pattern Signal ❌

```python
# Fusion layer receives: pattern_signal=None (always)
# Fusion receives: scalp_signal={...} for non-pattern trades
# → pattern_signal parameter never used
# → Proof requirement: FAILED
```

### Requirement 4: Pattern Affects Final Decision ❌

```python
# Pattern trades return at line 720
# → Never fused, never weighted against other signals
# → Patterns are accepted or rejected based on pattern engine only
# → Proof requirement: FAILED
```

---

## ARCHITECTURAL OBSERVATIONS

### Current Design (Correct by Design)

```
Pattern Engine → High Confidence? → Execute Immediately
                                ↓
                              No → Fall through to other signals
                                     ↓
                                  Fuse multiple weak signals
```

**Rationale:** Why waste computation fusing a high-probability pattern with weak scalp signals?

### But This Means...

1. **Pattern information does NOT flow through fusion layer**
2. **The `pattern_signal` parameter has no production use case**
3. **Adding `pattern_signal` to fusion is architectural mismatch**
4. **Proof of "pattern propagation through fusion" is impossible**

---

## CORRECTNESS OF THE FIX

| Aspect | Status | Evidence |
|--------|--------|----------|
| Prevents NameError | ✅ YES | Parameter exists with safe default |
| Allows pattern_signal=None | ✅ YES | No crash on None input |
| Integrates with fusion | ❌ NO | No production call passes it |
| Proves pattern consumption | ❌ NO | Patterns bypass fusion entirely |
| Proves pattern propagation | ❌ NO | Early return prevents propagation |

---

## MISSING EVIDENCE

To claim "pattern signals propagate through fusion," you would need:

1. **A pattern detection with conf ≥ 65% AND RR ≥ 1.8**
   - Test requirement: Real Bullish/Bearish Engulfing detected live
   - Status: NOT MET (synthetic test data had no patterns)

2. **That pattern reaching the fusion layer (line 1354)**
   - Current code: Impossible (early return at line 720)
   - Fix required: Remove early return, let patterns continue to fusion

3. **Fusion layer receiving the pattern_signal**
   - Current code: Never happens
   - Fix required: Add `pattern_signal=...` to fuse() call

4. **Pattern contributing to fusion result**
   - Current code: N/A (pattern_signal=None always)
   - Fix required: Verify pattern weights affect outcome

---

## SUMMARY

| Claim | Proven? | Evidence |
|-------|---------|----------|
| Parameter exists | ✅ | `pattern_signal: Optional[dict] = None` at line 45 |
| Parameter safe | ✅ | Safe default initialization + type check |
| No NameError | ✅ | Parameter has default value |
| Pattern detected | ❌ | No real patterns in test data |
| Pattern reaches fusion | ❌ | Early return at line 720 prevents it |
| Fusion receives pattern | ❌ | Never passed as argument |
| Pattern affects decision | ❌ | Patterns bypass fusion (design by architecture) |
| Production integration complete | ❌ | Data-flow broken at multiple points |

---

## CONCLUSION

**The fix applied is correct for its scope (preventing NameError), but it proves insufficient for the actual requirement.**

The user's concern was valid:

> "The current validation proves that the variable can safely exist, but we now need to prove that real detected patterns are actually propagated through the production decision pipeline."

**Proof Status:** ❌ NOT PROVEN

**Why:**
1. Patterns detected successfully → Return early (line 720)
2. Fusion layer reached only by non-pattern signals
3. `pattern_signal` parameter never populated in production code
4. Early return architecture prevents fusion-layer integration

**To fully prove production integration, would require:**
1. Real pattern detection test (actual Bullish/Bearish Engulfing)
2. Architecture change to allow patterns through fusion layer
3. Production code passing `pattern_signal=...` to fuse()
4. Regression test showing pattern affects final decision

---

**Final Status:** ✅ NameError Fixed | ❌ Data-Flow NOT Proven
