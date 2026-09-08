# AEGIS GOLD — HFT to Pattern-First Migration Specification

## 1. Migration Summary

This document specifies the migration of AEGIS GOLD from continuous fast-scalping / HFT tick-frequency gating to a **Pattern-First Local AI Architecture**.

---

## 2. Key Architecture Comparison

| Architectural Feature | Legacy HFT / Scalp Model | New Pattern-First Local AI Model |
|---|---|---|
| **Primary Driver** | Tick-level indicator thresholds | Confirmed Market Structure Patterns |
| **Trade Authorization Gate** | `CONFIDENCE >= X%` (e.g. 80%) | Structural Pattern Validity + EV economics |
| **Trade Frequency** | Continuous / forced tick-trades | Natural pattern emergence (WAIT when no pattern) |
| **Stop Loss (SL)** | Fixed ATR multipliers | Pattern invalidation level + spread buffer |
| **Take Profit (TP)** | Fixed ATR target | Structural opposing liquidity pool ($\ge 2.0\text{R}$) |
| **Execution Economics** | Net EV ignored | Hard $EV \ge \$0.50$ floor after costs |
| **AI Dependency** | Optional remote inference | 100% Offline Local AI 7-Engine consensus |

---

## 3. Deactivated HFT Constructs

1. **Indicator Threshold Gates:** RSI $> 55 / < 45$ entry gates removed. Indicators repurposed as ML feature inputs ONLY.
2. **Confidence Percentage Gates:** Min confidence thresholds removed as trade authorization gates.
3. **Continuous Scalp Loops:** Microsecond trade loops replaced by setup state machine polling on closed bars.
