# AEGIS GOLD — Phase 0 Repository Map

## Executive Summary
This document provides a comprehensive structural mapping of the AEGIS GOLD codebase prior to architectural upgrades. It traces the full data pipeline from MetaTrader 5 market data ingestion down to trade execution, model evaluation, and monitoring.

---

## 1. Subsystem Architecture Map

```
                     ┌────────────────────────┐
                     │ MT5 Market Data Stream │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │  modules/mt5_gateway   │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │  brain/frozen_snapshot │
                     └───────────┬────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            │                    │                    │
            ▼                    ▼                    ▼
   ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
   │ smc_engine.py  │   │ quant_feature  │   │ kronos_fore-   │
   │ (SMC / OB / FVG)│  │ _engine.py     │   │ caster.py      │
   └────────┬───────┘   └────────┬───────┘   └────────┬───────┘
            │                    │                    │
            │                    ▼                    │
            │           ┌────────────────┐            │
            │           │ ml_ensemble.py │            │
            │           └────────┬───────┘            │
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │   brain/engine_vote    │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │  brain/unified_brain   │
                     │ (7-Engine Consensus)   │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │ brain/structural_sl_tp │
                     │   (2.0R Floor Gate)    │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │ modules/risk_manager   │
                     └───────────┬────────────┘
                                 │
                                 ▼
                     ┌────────────────────────┐
                     │  MT5 Execution Fill    │
                     └────────────────────────┘
```

---

## 2. Directory & Module Catalog

### Core & Execution
- `core/main.py`: Master trading loop. Orchestrates MT5 tick/bar fetch, snapshot building, consensus calling, and order routing.
- `modules/mt5_gateway.py`: Low-level MetaTrader5 API wrapper handling rate queries, order placement, modification, and position tracking.
- `modules/risk_manager.py`: Broker-level margin, drawdown, max positions, and account risk guardrails.

### Feature & Quantitative Intelligence
- `brain/frozen_snapshot.py`: `FrozenDecisionSnapshot` container and `build_snapshot()` builder. Excludes forming (live) candles.
- `brain/quant_feature_engine.py`: Hurst exponent, Shannon entropy, Butterworth filter, log-returns, realized volatility, Z-scores, and GBM distribution estimation.
- `brain/statistical_engine.py`: Conformal prediction intervals, Kalman filtering, GARCH volatility modeling, HMM regime detection.
- `modules/feature_factory.py`: Raw technical indicator builder (EMA, ATR, RSI, ADX).

### Market Structure & Pattern Recognition
- `brain/smc_engine.py`: Smart Money Concepts engine detecting Swing Points, BOS, CHoCH, Order Blocks, Liquidity Sweeps, PO3, and FVGs.
- `brain/pattern_recognition.py`: Multi-timeframe chart pattern scanner.
- `brain/structure.py`: Higher-timeframe swing structure and trend bias classifier.

### Machine Learning & Foundation Models
- `brain/kronos_forecaster.py`: Trajectory forecaster estimating price path mean, standard deviation bands, and directional probability.
- `brain/ml_ensemble.py`: Soft-voting ensemble combining XGBoost, Random Forest, Neural Network (MLP), and Logistic Regression.
- `brain/ai_supervisor.py` (OMEGA): Local composite AI combining candle patterns, trend, momentum, and volatility.
- `brain/reinforcement_agent.py`: Deep RL Agent (Dueling-DQN / Actor-Critic) operating as meta-weighter for engine conviction.

### Master Decision & Risk Rules
- `brain/engine_vote.py`: Standardized `EngineVote` and `PatternEvidence` contracts with timestamp validation.
- `brain/unified_brain.py`: Master fusion layer implementing 7-Engine Pattern Consensus ($\ge 5/6$ directional agreement).
- `brain/structural_sl_tp.py`: Derived SL/TP from pattern levels with a mandatory $2.0\text{R}$ minimum floor.
- `brain/sniper_filter.py`: High-conviction Triple-Lock gate for precision entry filtering.

### Arena, Diagnostics & Monitoring
- `brain/champion_challenger.py`: Champion/Challenger shadow testing arena.
- `brain/shadow_auditor.py`: Out-of-sample decision auditor.
- `brain/drift_monitor.py`: Feature and distribution drift detector.

---

## 3. Systematic Keyword Scan Audit Results

A codebase-wide sweep was executed for temporal risk keywords:

| Search Term | Occurrences | Location / Finding | Status |
|---|---|---|---|
| `shift(-)` | 0 | None found in active brain code | SAFE |
| `center=True` | 0 | None found in rolling calculations | SAFE |
| `bfill` / `backfill` | 0 | None found in feature pipeline | SAFE |
| `fit(` / `scaler` | 12 | Found in `ml_ensemble.py`, `train_calibration.py`, `train_hmm_regime.py` | AUDITED: Scalers fit on historical training split only |
| `swing` / `pivot` | 84 | Found in `smc_engine.py` | AUDITED: Look-ahead fixed in Phase 1 |
