# AEGIS GOLD — Causal Backtest & Champion/Challenger Validation Specification

## 1. Executive Summary

This document details the **Causal Backtesting Standard** and **Champion/Challenger Shadow Validation Protocol** for AEGIS GOLD.

The primary objective is to guarantee 100% parity between historical backtest execution and live MT5 trading by enforcing point-in-time snapshot isolation.

---

## 2. Chronological Backtest Event Loop

Backtest simulation operates on sequential closed snapshots:

```python
for T in chronological_event_timestamps:
    # 1. Build immutable point-in-time snapshot
    snapshot = build_snapshot(decision_time=T)

    # 2. Update setup state machine
    setup = setup_engine.update(snapshot)

    # 3. Detect real-time micro-triggers
    trigger = trigger_engine.detect_trigger(setup, snapshot)
    if not trigger:
        continue

    # 4. Extract Quant Feature Vector (lags 1-5 ACF, Z-score, EWMA, GARCH, GBM)
    quant_features = quant_engine.extract_quant_vector(snapshot)

    # 5. Execute 7-Engine Consensus (5/6 directional agreement rule)
    consensus = run_pattern_consensus(snapshot)
    if consensus.action != "TRADE":
        continue

    # 6. Evaluate Expected Value (EV) after full execution costs
    ev_result = ev_engine.evaluate_ev(consensus)
    if not ev_result.approved:
        continue

    # 7. Run Pre-Order Hard Assertions
    assertions = assertions_engine.verify_pre_order_invariants()
    if not assertions.passed:
        continue

    # 8. Simulate execution fill at Ask (BUY) or Bid (SELL) with realistic slippage
    execute_simulated_trade()
```

---

## 3. Champion / Challenger Shadow Validation Protocol

- **Champion (`live_baseline`):** Current live system baseline.
- **Challenger (`pattern_consensus_v2`):** New Causal Point-in-Time 7-Engine Pattern Consensus Architecture.
- **Shadow Mode:** Both systems run concurrently on live tick streams. Challenger records decisions in shadow mode without sending MT5 orders until 200 shadow decisions pass.

### Promotion Thresholds:
1. **Zero Temporal Leakage:** $0$ votes discarded for $\text{confirmation\_time} > T$.
2. **Win Rate:** $\ge 60\%$.
3. **Profit Factor:** $\ge 1.80$.
4. **Realized R:R:** $\ge 1.8\text{R}$.
5. **Drawdown Degradation:** Max Drawdown $< 10\%$.
