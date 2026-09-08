# AEGIS GOLD — Immutable Validation Baseline (`AEGIS_GOLD_VALIDATION_BASELINE`)

## 1. Executive Summary
This document freezes all system parameters, feature configurations, engine settings, and software baselines prior to out-of-sample scientific edge validation.

> [!IMPORTANT]
> **FROZEN STATE:** No parameter, threshold, model weight, or trading rule may be altered during validation. All validation runs will evaluate this exact configuration.

---

## 2. Software & Test Suite Baseline

```text
Software Unit Tests:  58 Passed | 0 Failed | 0 Errors | 1 Skipped
Execution Environment: Windows | Python 3.14
Date Frozen:          2026-08-10
```

---

## 3. Engine & System Configuration Matrix

| Component | Parameter | Frozen Value | Description |
|---|---|---|---|
| **Consensus Engine** | `min_directional_agreement` | 5 of 6 | Requires $\ge 5/6$ directional agreement across SMC, Kronos, Quant, ML, OMEGA. |
| **RL Agent** | Role | Meta-Weighter | Emits per-engine conviction multipliers ($0.5 \dots 2.0$). Excluded from directional count. |
| **Setup Machine** | `setup_expiry_min` | 30 minutes | Max setup lifespan from confirmation time. |
| **Trigger Engine** | `trigger_types` | Displacement, Accel, Rejection | Scans closed M1 bars when setup is `ENTRY_ARMED`. |
| **Chase Detector** | `max_chase_pts` | 50.0 pts (Gold) / 8.0 pts (EURUSD) | Max distance price can move past trigger price. |
| **Chase Detector** | `max_trigger_age_sec` | 180 seconds | Max trigger lifespan before declaration as STALE. |
| **Chase Detector** | `min_remaining_rr` | 1.80R | Minimum remaining R:R required from current price to TP vs SL. |
| **Quant Engine v2** | `return_acf_lags` | Lags 1, 2, 3, 5 | Stationarized log return autocorrelation. |
| **Quant Engine v2** | `zscore_windows` | 10, 20, 50 bars | Causal trailing Z-scores. |
| **Quant Engine v2** | `ewma_lambda` | 0.94 | Exponentially weighted volatility decay factor. |
| **Quant Engine v2** | `gbm_horizon_bars` | 5 bars | Geometric Brownian Motion expected price & 95% bands. |
| **Quant Engine v2** | `hurst_window` | 100 bars | Rescaled Range ($R/S$) Hurst exponent calculation. |
| **EV Engine** | `required_edge` | $0.50 per trade | Minimum net EV required after spread, commission, and slippage. |
| **EV Engine** | `commission_per_lot` | $7.00 / lot round-turn | Standard broker commission. |
| **EV Engine** | `estimated_slippage` | 10 pts Gold / 2 pts EURUSD | Estimated fill slippage buffer. |
| **SL/TP Derivation** | `min_rr_ratio` | 2.00R | Hard floor: trades yielding $< 2.0\text{R}$ structural TP are REJECTED. |
| **SL/TP Derivation** | Fallback TP | None (0.0) | Zero synthetic ATR fallback TP. |

---

## 4. Frozen File Map

- **Brain Fusion:** `brain/unified_brain.py` (v2.0 Pattern Consensus)
- **Snapshot Container:** `brain/frozen_snapshot.py`
- **Setup State Machine:** `brain/setup_candidate.py`
- **Real-Time Trigger Engine:** `brain/trigger_engine.py`
- **Entry Chase Detector:** `brain/chase_detector.py`
- **Quant Intelligence Engine v2:** `brain/quant_feature_engine.py`
- **Expected Value Engine:** `brain/ev_decision_engine.py`
- **Pre-Order Assertions:** `brain/pre_order_assertions.py`
- **Structural SL/TP Engine:** `brain/structural_sl_tp.py`
- **Champion/Challenger Arena:** `brain/champion_challenger.py`
