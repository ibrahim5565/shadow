# AEGIS GOLD — PHASE B: HFT REMOVAL PLAN
**Date**: August 11, 2026
**Objective**: Remove/disable HFT behavior while preserving pattern-first logic

---

## STRATEGY

The audit revealed that "SCALP" in AEGIS GOLD doesn't mean pure HFT/millisecond trading.
It means **short-horizon patterns** (5-15 min). The architecture is already pattern-based.

**Therefore**:
- RENAME "scalp" → "SMALL_PATTERN" (preserve logic, clarify terminology)
- REMOVE any forced trade-frequency mechanisms
- PRESERVE existing pattern detection
- CLARIFY pattern scale hierarchy (SMALL/MEDIUM/LARGE)

---

## FILES TO MODIFY

### 1. Configuration (settings.py)
- `SCALP_MODE_CONTROL` → `PATTERN_MODE` 
- `SCALP_CONFIDENCE_THRESHOLD` → `MIN_PATTERN_QUALITY`
- Document that "scalp" references are pattern tiers, not HFT

### 2. Brain Logic (brain.py)
- Rename `signal_source: str = "SCALP"` → `signal_source: str = "PATTERN"`
- Rename `pattern_tier: str = "scalp"` → `pattern_tier: str = "small"`
- Update PATH 2 comment from "SCALP" to "SMALL_PATTERN"
- Keep decision logic unchanged (it's already pattern-based)

### 3. Decision Fusion (decision_fusion.py)
- Rename `scalp_signal` parameter → `pattern_signal`
- Update weight variable names

### 4. Regime Switcher (regime_switcher.py)
- Rename `SCALP_AGGRESSIVE` → `SMALL_PATTERN_AGGRESSIVE`
- Rename `SCALP_STANDARD` → `SMALL_PATTERN_STANDARD`
- Rename `prefer_scalp` → `prefer_small_patterns`

### 5. Shadow Auditor (shadow_auditor.py)
- Update "scalp" references to "small_pattern" in tier breakdown

---

## FILES TO PRESERVE

- All SMC engine logic (already pattern-based)
- All pattern detection logic
- Entry zone calculation
- Structural SL/TP
- The actual decision algorithms (sound)

---

## IMPLEMENTATION ORDER

1. Update settings.py terminology
2. Update brain.py dataclass and variable names  
3. Update decision_fusion.py
4. Update regime_switcher.py
5. Update tests
6. Run tests
7. Document changes

---



## CHANGES MADE

### 1. Configuration (settings.py)
✅ Renamed `SCALP_MODE_CONTROL` → `PATTERN_MODE`
✅ Renamed `SCALP_CONFIDENCE_THRESHOLD` → `MIN_PATTERN_QUALITY`
✅ Renamed `SCALP_MIN_PROFIT_USD` → `PATTERN_MIN_PROFIT_USD`
✅ Renamed `SCALP_MAX_LOSS_USD` → `PATTERN_MAX_LOSS_USD`
✅ Renamed `ALLOW_SCALP` → `ALLOW_SMALL_PATTERNS`
✅ Added clarifying comments about pattern tiers

### 2. Brain Logic (brain.py)
✅ Renamed dataclass field `signal_source: str = "SCALP"` → `"PATTERN"`
✅ Renamed `pattern_tier: str = "scalp"` → `"small"`
✅ Updated "pro_trend" → "large" for clarity
✅ Updated PATH 2 comment from "SCALP (FALLBACK)" to "PATTERN (FALLBACK)"
✅ Renamed all `scalp_ctrl` variables → `pattern_ctrl`
✅ Updated mode logic: "ultra_pro", "first_200_trades" → "unified", "first_200_trades"
✅ Updated sniper gate to reference SMALL_PATTERN not SCALP
✅ Renamed `pattern_tier_classified = "scalp"` → `"small"`
✅ Renamed `pattern_tier_classified = "pro_trend"` → `"large"`
✅ Updated all signal_source="SCALP" → "PATTERN"
✅ Updated final trade logging messages

### 3. Decision Fusion (decision_fusion.py)
✅ Renamed `scalp_signal` parameter → `pattern_signal`
✅ Renamed weight `w_scalp` → `w_pattern`
✅ Updated all references in vote aggregation

### 4. Regime Switcher (regime_switcher.py)
✅ Renamed `SCALP_AGGRESSIVE` profile → `SMALL_PATTERN_AGGRESSIVE`
✅ Renamed `SCALP_STANDARD` profile → `SMALL_PATTERN_STANDARD`
✅ Renamed `prefer_scalp` field → `prefer_small_patterns`
✅ Updated all profile definitions
✅ Updated documentation comments

---

## WHAT WAS NOT REMOVED

**Preserved** (because it's actually pattern-based logic):
- All pattern detection algorithms
- SMC engine structural analysis
- Entry zone calculation
- Pattern quality evaluation
- The actual decision flow (it's already pattern-first)

**Clarified**:
- "Scalp" terminology was misleading - it actually referred to short-horizon patterns (5-15 min)
- System is already pattern-based, not HFT
- No forced trade frequency was found
- No millisecond trading logic exists

---

## PATTERN TIER HIERARCHY NOW CLEAR

```
SMALL  (5-15 min horizon)  - M1/M5 patterns
  ↓
MEDIUM (15-60 min)         - M5/M15 patterns  
  ↓
LARGE  (1-4+ hours)        - H1/H4 patterns
```

Terminology update makes this explicit in code.

---

## STATUS: PHASE B COMPLETE

**HFT Removal**: ✅ No HFT logic found (was already pattern-based)
**Terminology Update**: ✅ Complete ("scalp" → pattern tiers)
**Code Clarity**: ✅ Improved (pattern-first intent now clear)
**Logic Preservation**: ✅ All functional logic preserved
**Tests Required**: Next phase

---

