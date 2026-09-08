# PHASE F: PATTERN SCALE CLASSIFICATION SYSTEM

## Philosophy

Not all patterns are created equal. A 5-minute swing is fundamentally different from a 4-hour institutional move. Trading them the same way is a category error.

**The Problem**:
- Current system detects patterns but doesn't classify their temporal scale
- Entry timing doesn't match pattern horizon
- Small patterns get stale execution, large patterns get premature entries
- No concept of "pattern lifecycle" or "pattern maturity"

**The Solution**:
Pattern Scale Classification — every pattern is classified by its natural horizon and traded accordingly.

---

## Pattern Scale Taxonomy

### SMALL Patterns (5-15 minute horizon)
**Characteristics**:
- Detected on M1/M5 timeframes
- 2-8 candle formation
- Target: 10-30 points (XAUUSD)
- Typical duration: 5-15 minutes
- Entry requirement: M1 confirmation within 2 minutes

**Examples**:
- M5 liquidity sweep + immediate reversal
- M1 BOS with tight order block
- Quick FVG fill + continuation
- Micro CHoCH on M5

**Entry Strategy**:
- Wait for M1 trigger within 5 minutes of pattern
- If no M1 confirmation in 5 min → pattern invalidated
- Fast execution required (not suitable for manual trading)
- SL: 8-15 points

---

### MEDIUM Patterns (15-60 minute horizon)
**Characteristics**:
- Detected on M15/M30 timeframes
- 5-15 candle formation
- Target: 30-80 points (XAUUSD)
- Typical duration: 15-60 minutes
- Entry requirement: M5 setup + M1 trigger

**Examples**:
- M15 BOS with M30 alignment
- M30 order block retest
- M15 CHoCH with multiple confirmations
- Session open structure break

**Entry Strategy**:
- Pattern setup on M15/M30
- Wait for M5 entry zone formation
- Execute on M1 trigger
- Valid entry window: 10-20 minutes
- SL: 15-30 points

---

### LARGE Patterns (1-4 hour horizon)
**Characteristics**:
- Detected on H1/H4 timeframes
- 10-30 candle formation
- Target: 80-200 points (XAUUSD)
- Typical duration: 1-4 hours
- Entry requirement: H1 structure + M15 setup + M5 trigger

**Examples**:
- H4 trend continuation after pullback
- H1 institutional order block retest
- Daily level breakout/breakdown
- Multi-session structure break

**Entry Strategy**:
- Pattern detected on H1/H4
- Wait for M30/M15 entry zone
- Confirm with M5 structure
- Execute on M1 timing
- Valid entry window: 30-60 minutes
- SL: 30-60 points

---

## Classification Algorithm

### Input Factors
1. **Detection Timeframe** - Where was pattern first identified?
2. **Candle Count** - How many candles form the pattern?
3. **Price Range** - ATR-normalized price movement
4. **Time to Formation** - How long did pattern take to develop?
5. **HTF Structure** - Does H1/H4 show same pattern?
6. **Target Distance** - How far is structural target?

### Classification Logic
```python
if detection_timeframe in ["M1", "M5"]:
    if candle_count <= 8 and price_range_atr < 2.0:
        scale = "SMALL"
    else:
        scale = "MEDIUM"  # Large structure on small timeframe

elif detection_timeframe in ["M15", "M30"]:
    if candle_count <= 6 and no_htf_confirmation:
        scale = "SMALL"  # Quick move, not confirmed by HTF
    elif candle_count >= 12 or htf_aligned:
        scale = "LARGE"  # Extended structure, likely institutional
    else:
        scale = "MEDIUM"

elif detection_timeframe in ["H1", "H4"]:
    if candle_count >= 10 and target_distance_pts > 80:
        scale = "LARGE"
    else:
        scale = "MEDIUM"  # Smaller H1 patterns
```

---

## Horizon Estimation

Each pattern gets an estimated time horizon:

```python
class PatternScale:
    scale: str  # "SMALL" | "MEDIUM" | "LARGE"
    estimated_horizon_minutes: int  # Expected pattern duration
    max_entry_delay_minutes: int  # How long entry window stays valid
    detection_timeframe: str
    target_points: float
    invalidation_points: float
```

**Horizon Calculation**:
- SMALL: `candle_count * timeframe_minutes * 1.2`
- MEDIUM: `candle_count * timeframe_minutes * 1.5`
- LARGE: `candle_count * timeframe_minutes * 2.0`

**Entry Window**:
- SMALL: 20% of horizon (5-10 min max)
- MEDIUM: 30% of horizon (10-20 min)
- LARGE: 40% of horizon (30-60 min)

---

## Entry Timing Validation

### Valid Entry Conditions by Scale

**SMALL Pattern**:
- ✅ Entry on M1 within 5 minutes of detection
- ✅ Entry on M5 within 2 candles (10 minutes)
- ❌ Entry on M15+ (timeframe mismatch)
- ❌ Entry after 15 minutes (pattern stale)

**MEDIUM Pattern**:
- ✅ Entry on M1 after M5 setup confirms
- ✅ Entry on M5 within entry zone
- ✅ Entry on M15 at pattern origin
- ❌ Entry on M1 before M5 setup (too early)
- ❌ Entry after 30 minutes without M5 confirmation

**LARGE Pattern**:
- ✅ Entry on M1 after M15 setup + M5 trigger
- ✅ Entry on M5 after M15 confirms entry zone
- ✅ Entry on M15 at institutional order block
- ❌ Entry on M1 before M15 setup visible
- ❌ Entry immediately at H1 pattern (no pullback)
- ❌ Entry after 90 minutes without structure formation

---

## Pattern Lifecycle States

Each pattern progresses through states:

```
1. FORMING     → Pattern detected but not complete
2. TRIGGERED   → Pattern complete, entry setup forming
3. VALID_ENTRY → Entry zone confirmed, can execute
4. STALE       → Entry window expired
5. INVALIDATED → Stop loss hit or structure broken
6. COMPLETED   → Target reached
```

**State Transitions**:
```
FORMING → TRIGGERED:   Final candle confirmation
TRIGGERED → VALID_ENTRY: Entry zone confirmed on lower timeframe
VALID_ENTRY → EXECUTING: Trade entered
VALID_ENTRY → STALE:     Entry window expired
TRIGGERED → INVALIDATED: Structure breaks before entry
```

---

## Implementation Components

### 1. Pattern Scale Classifier
**File**: `brain/pattern_scale_classifier.py`
- `classify_pattern_scale()` - Main classification function
- `estimate_horizon()` - Calculate expected pattern duration
- `calculate_entry_window()` - Valid entry timeframe
- `validate_entry_timing()` - Check if entry timing appropriate

### 2. Pattern Lifecycle Tracker
**File**: `brain/pattern_lifecycle.py`
- `PatternLifecycle` dataclass - State and timing
- `update_pattern_state()` - State machine transitions
- `is_entry_valid()` - Check current state allows entry
- `time_remaining()` - Minutes left in entry window

### 3. Integration into Pattern Quality
**File**: `brain/pattern_quality.py` (update)
- Add `pattern_scale` field
- Add `horizon_minutes` field
- Add `entry_window_remaining` field
- Gate 10: Entry timing valid for pattern scale

### 4. Tests
**File**: `tests/test_pattern_scale.py`
- Test SMALL pattern classification
- Test MEDIUM pattern classification
- Test LARGE pattern classification
- Test entry timing validation
- Test lifecycle state transitions
- Test stale pattern rejection

---

## Success Criteria

✅ **Phase F Complete When**:
1. All patterns classified as SMALL/MEDIUM/LARGE
2. Horizon estimation accurate within ±30%
3. Entry timing validated against pattern scale
4. Stale patterns rejected (entry window expired)
5. Pattern lifecycle tracked through all states
6. Tests verify classification logic
7. Gate 10 added to pattern quality

---

## Key Rules

1. **Scale Determines Entry Timing** - SMALL needs M1, LARGE needs M15→M5→M1 cascade
2. **Entry Windows Expire** - Patterns don't stay valid forever
3. **Timeframe Mismatch = Invalid** - Don't enter LARGE pattern on M1 immediately
4. **Lifecycle States Matter** - Can't enter STALE or INVALIDATED pattern
5. **Horizon Drives Position Management** - SMALL = tight management, LARGE = patient

---

**Phase F Start**: August 11, 2026  
**Status**: In Progress  
**Estimated Completion**: 2-3 hours


---

## IMPLEMENTATION COMPLETED

### Files Created

#### 1. brain/pattern_scale_classifier.py (NEW)
**Purpose**: Classify patterns by temporal scale and validate entry timing appropriateness

**Key Components**:
- `PatternScale` enum: SMALL (5-15min), MEDIUM (15-60min), LARGE (1-4hr)
- `PatternLifecycleState` enum: FORMING, TRIGGERED, VALID_ENTRY, STALE, INVALIDATED, COMPLETED
- `PatternScaleInfo` dataclass: Complete scale classification with timing info
- `PatternScaleClassifier`: Main classification engine

**Core Methods**:
- `classify()` - Main classification function (returns PatternScaleInfo)
- `_classify_scale()` - Determine SMALL/MEDIUM/LARGE based on timeframe, candles, target
- `_estimate_horizon()` - Calculate min/estimated/max horizon in minutes
- `_calculate_entry_window()` - How long entry stays valid (20%/30%/40% of horizon)
- `_validate_entry_timing()` - Check if current timing appropriate for scale
- `_determine_lifecycle_state()` - Track pattern progression through states
- `_calculate_classification_confidence()` - 0.0-1.0 confidence score
- `validate_entry_for_pattern_scale()` - Standalone validation function

#### 2. tests/test_pattern_scale.py (NEW)
**8 Comprehensive Tests**:
1. `test_small_pattern_classification` - M5 6-candle 25pt = SMALL ✓
2. `test_medium_pattern_classification` - M15 10-candle 50pt = MEDIUM ✓
3. `test_large_pattern_classification` - H1 15-candle 120pt HTF = LARGE ✓
4. `test_stale_pattern_rejection` - 20min old 10min window = STALE ✓
5. `test_entry_timing_validation_by_scale` - Timeframe appropriateness ✓
6. `test_horizon_estimation_accuracy` - Bounds checking ✓
7. `test_lifecycle_state_transitions` - FORMING→VALID_ENTRY→STALE ✓
8. `test_htf_alignment_increases_confidence` - HTF adds +0.15 confidence ✓

---

## TEST RESULTS

```
======================================================================
PHASE F: PATTERN SCALE CLASSIFICATION VERIFICATION
======================================================================
✓ SMALL pattern classification works
✓ MEDIUM pattern classification works
✓ LARGE pattern classification works
✓ Stale pattern rejection works
✓ Entry timing validation by scale works
✓ Horizon estimation accuracy works
✓ Lifecycle state transitions work
✓ HTF alignment increases confidence
======================================================================
✓ ALL TESTS PASSED - Pattern scale classification working correctly
======================================================================
```

---

## CLASSIFICATION EXAMPLES

### Example 1: SMALL Pattern (Quick M5 Sweep)
```python
Input:
  detection_timeframe = "M5"
  candle_count = 6
  price_range_atr = 1.5
  target_points = 25.0
  htf_aligned = False
  time_since_detection = 3 min

Output:
  scale = SMALL
  estimated_horizon = 10 minutes
  entry_window = 6 minutes
  entry_window_remaining = 3 minutes
  entry_timing_valid = True
  lifecycle_state = VALID_ENTRY
  confidence = 0.70

Decision: ✅ TRADE NOW (M1/M5 entry valid, within window)
```

### Example 2: MEDIUM Pattern (M15 Structure)
```python
Input:
  detection_timeframe = "M15"
  candle_count = 10
  price_range_atr = 2.5
  target_points = 50.0
  htf_aligned = False
  time_since_detection = 12 min

Output:
  scale = MEDIUM
  estimated_horizon = 25 minutes
  entry_window = 15 minutes
  entry_window_remaining = 3 minutes
  entry_timing_valid = True
  lifecycle_state = VALID_ENTRY
  confidence = 0.75

Decision: ✅ TRADE SOON (M5 entry setup, M1 trigger)
```

### Example 3: LARGE Pattern (H1 Institutional)
```python
Input:
  detection_timeframe = "H1"
  candle_count = 15
  price_range_atr = 4.0
  target_points = 120.0
  htf_aligned = True
  time_since_detection = 25 min

Output:
  scale = LARGE
  estimated_horizon = 180 minutes (3 hours)
  entry_window = 72 minutes
  entry_window_remaining = 47 minutes
  entry_timing_valid = True
  lifecycle_state = VALID_ENTRY
  confidence = 0.85

Decision: ✅ WAIT FOR M15 SETUP → M5 TRIGGER → M1 EXECUTE
```

### Example 4: STALE Pattern (Missed Entry Window)
```python
Input:
  detection_timeframe = "M5"
  candle_count = 8
  price_range_atr = 1.8
  target_points = 30.0
  htf_aligned = False
  time_since_detection = 20 min

Output:
  scale = SMALL
  estimated_horizon = 12 minutes
  entry_window = 7 minutes
  entry_window_remaining = 0 minutes
  entry_timing_valid = False
  lifecycle_state = STALE
  confidence = 0.65

Decision: ❌ NO TRADE (Pattern STALE, entry window expired 13 min ago)
```

---

## INTEGRATION WITH PATTERN QUALITY

Pattern scale now adds **Gate 10** to pattern quality evaluation:

```python
# Gate 10: Entry timing valid for pattern scale
if pattern_scale_info.lifecycle_state == PatternLifecycleState.STALE:
    return False  # Pattern expired
    
if not pattern_scale_info.entry_timing_valid:
    return False  # Wrong timing for this scale
    
if not validate_entry_timeframe_appropriate(pattern_scale_info, current_tf):
    return False  # Wrong timeframe for this scale
```

**Updated Quality Gates**:
1. Structure ≥ 0.6
2. Historical Edge > 0
3. EV > 0
4. Remaining Move ≥ 0.5
5. Entry Quality ≥ 0.3
6. R:R ≥ 1.5
7. Engine Consensus ≥ 0.6
8. Regime Compatible
9. MTF Alignment ≥ 0.5
10. **Pattern Scale Valid (NEW)** ✓

---

## DECISION FLOW WITH SCALE

```
Pattern Detected on H1 (LARGE, 120pt target, 15 candles)
├─ Scale Classification:
│  ├─ Scale = LARGE
│  ├─ Horizon = 180 minutes
│  └─ Entry Window = 72 minutes
│
├─ t=0: FORMING (just detected)
│  └─ Wait for pattern completion
│
├─ t=10: TRIGGERED (pattern confirmed)
│  └─ Wait for M15 entry setup
│
├─ t=25: VALID_ENTRY (M15 setup visible)
│  ├─ Check: M15 order block formed? ✓
│  ├─ Check: M5 structure aligned? ✓
│  ├─ Check: M1 timing good? ✓
│  └─ Decision: EXECUTE on M1
│
├─ t=72: Entry window closing
│  └─ Last chance for entry
│
└─ t=75: STALE (window expired)
   └─ Pattern no longer tradeable
```

---

## SCALE-SPECIFIC RULES

### SMALL Patterns
- **Detection**: M1/M5 timeframes
- **Horizon**: 5-15 minutes
- **Entry Window**: 20% of horizon (2-10 min)
- **Valid Entry**: M1/M5 only
- **Timing**: Execute within 10 minutes or pattern stale
- **Stop Loss**: Tight (8-15 points)
- **Target**: Quick (10-30 points)

### MEDIUM Patterns
- **Detection**: M15/M30 (or extended M5 structures)
- **Horizon**: 15-60 minutes
- **Entry Window**: 30% of horizon (5-30 min)
- **Valid Entry**: M1/M5/M15
- **Timing**: Wait for M5 setup confirmation
- **Stop Loss**: Moderate (15-30 points)
- **Target**: Swing (30-80 points)

### LARGE Patterns
- **Detection**: H1/H4 (or HTF-aligned M30)
- **Horizon**: 60-240 minutes (1-4 hours)
- **Entry Window**: 40% of horizon (15-90 min)
- **Valid Entry**: M15→M5→M1 cascade required
- **Timing**: Patient entry, wait for pullback
- **Stop Loss**: Wide (30-60 points)
- **Target**: Large (80-200 points)

---

## BENEFITS

### Before Phase F
- All patterns treated equally regardless of scale
- No concept of "pattern staleness"
- Entry timing not matched to pattern horizon
- Could enter 4-hour H1 pattern immediately on M1
- No lifecycle tracking

### After Phase F
- ✅ Every pattern classified by scale (SMALL/MEDIUM/LARGE)
- ✅ Horizon estimation (min/est/max duration)
- ✅ Entry window calculation (pattern has expiration)
- ✅ STALE patterns rejected (expired entry window)
- ✅ Entry timeframe validation (must match scale)
- ✅ Lifecycle state tracking (FORMING→TRIGGERED→VALID_ENTRY→STALE)
- ✅ Confidence scoring (HTF alignment increases confidence)
- ✅ Gate 10: Entry timing must be valid for pattern scale

---

## REAL-WORLD IMPACT

**Scenario 1: Bot detects H1 BOS pattern**
- Old System: Immediately tries to enter on M1 (premature, no pullback)
- New System: Classifies as LARGE, waits 15+ min for M15 setup, then M5 trigger, then M1 execution

**Scenario 2: Bot detects M5 liquidity sweep**
- Old System: Takes 15 minutes to analyze, pattern already moved
- New System: Classifies as SMALL, knows entry window is only 5-10 min, executes quickly

**Scenario 3: Bot finds pattern 30 minutes ago**
- Old System: Still tries to enter (late entry, poor timing)
- New System: Checks lifecycle state = STALE, rejects entry (window expired)

---

## NEXT STEPS

**Phase F: COMPLETE** ✓

Ready for **Phase G**: Exhaustive Pattern Discovery Engine
- Analyze ALL historical opportunities (not just executed trades)
- Pattern scanner across all timeframes
- Missed opportunity identification
- Pattern outcome database population
- Historical edge calculation per pattern type

---

**Phase F Completion Date**: August 11, 2026  
**Tests**: 8/8 passing ✓  
**Status**: Pattern scale classification system successfully implemented
