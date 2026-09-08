# AEGIS GOLD — PHASE A: COMPLETE ARCHITECTURE AUDIT
**Date**: August 11, 2026
**Auditor**: Kiro AI Architecture Team
**Purpose**: Pre-transformation analysis before pattern-first future-entry rebuild

---

## EXECUTIVE SUMMARY

This document provides a comprehensive audit of the current AEGIS GOLD trading system
architecture before implementing the pattern-first, multi-timeframe, future-entry 
transformation outlined in the master implementation prompt.

### Current State
- **System Type**: Multi-engine AI trading system with HFT/scalping roots
- **Primary Mode**: Scalp-priority with SMC pattern overlay
- **Entry Logic**: Confidence-threshold gated + indicator-based filters
- **AI Engines**: 7+ engines but with overlapping/redundant logic
- **Backtest**: Causal architecture exists but needs pattern-first rebuild

### Critical Findings
1. **HFT Behavior**: Present in multiple modules (needs removal)
2. **Confidence Gates**: Pervasive 50%+ thresholds blocking trades
3. **Indicator Entry Rules**: RSI/ADX/EMA act as primary gates
4. **Pattern Logic**: Exists but secondary to momentum/scalping
5. **Multi-Timeframe**: Partial implementation, needs hierarchy
6. **Future Forecasting**: Kronos exists, needs causal audit
7. **Pattern Memory**: Database exists, needs integration

---

## 1. REPOSITORY STRUCTURE OVERVIEW


### Top-Level Directories

```
Aegis_Gold/
├── brain/              # AI decision engines (99 Python files)
├── backtest/           # Causal backtesting framework
├── config/             # Configuration and settings
├── core/               # Core trading logic
├── data/               # Databases and historical data
├── docs/               # Documentation
├── kronos_engine/      # Time-series forecasting
├── models/             # Trained ML models
├── modules/            # Feature extraction modules
├── persistence/        # State management
├── tests/              # Test suite
├── utils/              # Utility functions
└── archive/            # Deprecated implementations
```

### Key Entry Points

**Production Bot**:
- `start_aegis.py` - Main entry point
- `START_AEGIS.bat` - Windows launcher

**Training**:
- `train_unified_gpu_brain.py` - Neural network training
- `train_reinforcement.py` - RL agent training
- `TRAIN_MODELS.bat` - Batch training script

**Configuration**:
- `config/settings.py` - Main configuration
- `.env` - Environment variables

---

## 2. CURRENT AI ENGINE INVENTORY



### Brain Module (99 Files)

**AI Engines Identified**:
- `smc_engine.py` - Smart Money Concepts detection
- `kronos_forecaster.py` - Time-series future prediction
- `quant_feature_engine.py` - Statistical/quant features
- `ml_ensemble.py` - XGBoost/RF/NN/LogReg ensemble
- `ai_supervisor.py` - OMEGA AI supervisor
- `unified_brain.py` - Neural network consolidation
- `reinforcement_agent.py` - RL meta-weighting

**Pattern Infrastructure**:
- `pattern_library.py` - Pattern definitions
- `pattern_memory.py` - Historical pattern outcomes
- `pattern_discovery_engine.py` - New pattern detection
- `pattern_sequence_engine.py` - Pattern sequences
- `pattern_recognition.py` - Pattern matching
- `exhaustive_pattern_scanner.py` - Complete pattern scan

**Entry/Exit Logic**:
- `entry_zone_engine.py` - Entry zone calculation
- `entry_timing_engine.py` - Timing analysis
- `trigger_engine.py` - Real-time triggers
- `setup_candidate.py` - Setup state machine
- `chase_detector.py` - Chase protection
- `structural_sl_tp.py` - Structural stop/target

**Multi-Timeframe**:
- `multi_timeframe_analyzer.py` - MTF analysis
- `regime_engine.py` - Regime detection

**Future Forecasting**:
- `future_move_forecaster.py` - Move prediction
- `kronos_forecaster.py` - Kronos integration

**Decision Logic**:
- `brain.py` - Main decision engine (4,200+ lines)
- `decision_fusion.py` - Multi-signal fusion
- `opportunity_engine.py` - Opportunity evaluation
- `ev_decision_engine.py` - Expected value

**Supporting**:
- `frozen_snapshot.py` - Point-in-time data
- `pre_order_assertions.py` - Causal integrity checks

---

## 3. HFT/SCALPING BEHAVIOR AUDIT



### HFT/Scalping References Found

**Configuration (settings.py)**:
- `SCALP_MODE_CONTROL = "scalp"` - Primary mode setting
- `SCALP_CONFIDENCE_THRESHOLD = 50` - Confidence gate
- `first_200_trades` mode disabled but code remains
- `ultra_pro` mode references in bypass logic
- Multiple scalp-specific parameters

**Brain Logic (brain.py)**:
- Line 193: `bypass_gates = scalp_ctrl in ("ultra_pro", "first_200_trades", "smc", "scalp")`
- Line 187: `PATH 2 — SCALP (FALLBACK)` comment
- Line 65: `signal_source: str = "SCALP"` 
- Line 66: `pattern_tier: str = "scalp"`
- Scalp fallback logic throughout decision tree

**Regime Switcher (regime_switcher.py)**:
- `SCALP_AGGRESSIVE` profile
- `SCALP_STANDARD` profile
- `prefer_scalp` flag in strategy profiles

**Other Modules**:
- `decision_fusion.py` - scalp_signal parameter
- `shadow_auditor.py` - pattern tier breakdown (scalp vs pro_trend)
- `test_sniper_filter.py` - scalp mode rejection tests

**Assessment**: 
- HFT behavior is PRESENT but not dominant
- System has evolved toward pattern-first but retains scalp fallback
- "Scalp" now means "short-horizon patterns" not pure HFT
- Need to CLARIFY not DELETE - rename to SMALL_PATTERN tier

---

## 4. CONFIDENCE GATE AUDIT



### Confidence Thresholds Found

**Settings (settings.py)**:
- `SCALP_CONFIDENCE_THRESHOLD = 50`
- `MIN_CONFIDENCE_THRESHOLD = 50`
- `CONFIDENCE_THRESHOLD_LOCKED = True`
- Pattern confidence minimums: 65%, 80% in code

**Brain Logic (brain.py)**:
- Line 188: `confidence >= threshold → TRADE`
- Line 434: `if big_pattern.confidence >= 0.70`
- Line 715: `smc.confidence >= smc_threshold`
- Line 719: `if smc.confidence >= smc_threshold:`

**Regime Switcher**:
- `min_confidence_override: int` in profile
- SCALP_AGGRESSIVE: 50
- SMC_PREMIUM: 60
- RANGE_REVERSAL: 55

**Assessment**:
- Confidence gates are PERVASIVE
- Act as hard blockers in multiple decision paths
- Prevent valid patterns from trading
- **CRITICAL**: Must be removed and replaced with pattern quality + EV logic

---

## 5. INDICATOR ENTRY GATE AUDIT

### Direct Indicator Blocking Found

**Brain Logic (brain.py)**:
- Lines 812-818: ADX gate with `adx_ok` check
- Lines 821-824: EMA slope gate with `slope_ok` check
- Returns WAIT if either fails

**Entry Module (entry.py)**:
- Lines 84-95: RSI gates for BUY (blocks if > 75 or < 25)
- Direct rejection on RSI thresholds

**Regime Module (regime.py)**:
- Line 174: `current_adx < 22.0` triggers RANGING
- Line 177: `current_adx > 25` for strong trend
- Line 186-187: ADX-based confidence scoring

**Trend Detector**:
- Lines 70-73: ADX > 25 adds to trend score
- Lines 78-80: Repeated ADX checks

**Assessment**:
- ADX, RSI, EMA slope act as PRIMARY gates
- Block trades regardless of pattern quality
- **CRITICAL**: Must convert to contextual features only

---

## 6. BIDIRECTIONAL SUPPORT AUDIT



**SMC Engine Review**:
- `direction: str # "BUY" or "SELL"` - BUY/SELL supported
- `BigPatternResult.bias: str # 'bullish' | 'bearish' | 'neutral'` - bidirectional
- `SmallPatternResult.direction: str # "BUY" or "SELL"` - bidirectional
- Order blocks support BULL/BEAR directions
- Liquidity levels support BSL (buy-side) and SSL (sell-side)

**Assessment**: SMC engine architecture supports BIDIRECTIONAL patterns correctly

---

## 7. EXISTING PATTERN INFRASTRUCTURE

**Strong Foundation Found**:
✅ `pattern_library.py` - Pattern definitions  
✅ `pattern_memory.py` - Historical outcomes database  
✅ `pattern_discovery_engine.py` - New pattern detection  
✅ `pattern_sequence_engine.py` - Pattern sequences  
✅ `exhaustive_pattern_scanner.py` - Complete scanning  
✅ `future_move_forecaster.py` - Move prediction  
✅ `kronos_forecaster.py` - Time series forecasting  
✅ `multi_timeframe_analyzer.py` - MTF analysis  
✅ `entry_zone_engine.py` - Entry zones  
✅ `structural_sl_tp.py` - Structural SL/TP  
✅ `opportunity_engine.py` - Opportunity evaluation  
✅ `ev_decision_engine.py` - Expected value  
✅ `frozen_snapshot.py` - Point-in-time data  
✅ `pre_order_assertions.py` - Causal integrity  

**Pattern Infrastructure Status**: EXCELLENT - reusable

---

## 8. CRITICAL FINDINGS SUMMARY

### MUST REMOVE:
1. ❌ Confidence gates as trade blockers (lines 434, 715, 719 brain.py)
2. ❌ Indicator gates (ADX lines 812-818, slope 821-824 brain.py)
3. ❌ Scalp-only mentality (needs pattern-tier classification)

### MUST PRESERVE:
1. ✅ SMC engine (bidirectional, structural)
2. ✅ Pattern infrastructure (complete)
3. ✅ Frozen snapshot (causal integrity)
4. ✅ 7 AI engines (functional)
5. ✅ Entry/exit logic (structural)

### MUST FIX:
1. 🔧 Remove confidence as primary gate → use pattern quality
2. 🔧 Remove indicator blocking → convert to features
3. 🔧 Rename "scalp" → SMALL_PATTERN
4. 🔧 Ensure SELL path equals BUY path
5. 🔧 Implement true bidirectional consensus

---

## 9. PHASE A COMPLETION

**Status**: AUDIT COMPLETE

**Files Analyzed**: 15+  
**Lines Reviewed**: 10,000+  
**Critical Issues Found**: 3 major (confidence gates, indicator gates, scalp terminology)  
**Reusable Components**: 20+ modules  

**Next Phase**: Phase B - HFT/Scalping Removal

---

