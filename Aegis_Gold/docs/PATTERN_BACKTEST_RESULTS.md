# AEGIS GOLD — Pattern Backtest Results Specification

## 1. Backtest Summary Metrics

```text
Simulation Period:     2024-01-01 to 2026-08-10
Initial Equity:        $10,000.00
Final Equity:          $10,101.52
Net Profit:            +$101.52
Total Pattern Trades:  47
Win Rate:              89.4%
Profit Factor:         14.09
Expectancy:            +$2.16 / trade
Average R:             1.77R
Max Drawdown:          $1.85 (0.02%)
```

---

## 2. No-Trade Veto Analysis

During historical replay, candidate setups were filtered by structural gates:
- **No Setup Identified:** 124 bars
- **No M1 Micro-Trigger:** 86 setups
- **Chased / Stale Trigger:** 14 triggers
- **Engine Veto (<5/6 Agreement):** 28 setups
- **Negative EV (<$0.50 Edge):** 11 setups
- **Pre-Order Assertion Failure:** 0 trades

---

## 3. Entry Quality Distribution

- **Optimal Entries (<5 pts move):** 100% of executed trades.
- **Early / Late / Chase Entries:** 0% (All chased entries strictly rejected).
