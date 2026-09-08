# AEGIS GOLD — Pattern-First Architecture Specification

## 1. Executive Summary

This document specifies the **Pattern-First Architecture Transformation** for AEGIS GOLD.

AEGIS GOLD is transformed from a continuous fast-scalping / indicator-gated bot into a **Pattern-First, Local-AI Trading Architecture**. 

The system waits for verified market structure opportunities (BOS, CHoCH, Order Blocks, FVGs, Liquidity Sweeps, Retests, Breakers) and executes structural trades strictly based on pattern validity, local 7-engine alignment, structural SL/TP, and EV execution economics.

---

## 2. Main System Control Flow

```
                     MARKET DATA STREAM (MT5)
                                │
                                ▼
                     FROZEN SNAPSHOT (t <= T)
                                │
                                ▼
                     PATTERN DISCOVERY (SMC)
                     (BOS / CHoCH / OB / FVG)
                                │
                                ▼
                    SETUP STATE MACHINE
            (NO_SETUP → CONFIRMED → ARMED)
                                │
                                ▼
                    REAL-TIME M1 TRIGGER
                   (Displacement / Accel)
                                │
                                ▼
                    LOCAL 7-ENGINE ANALYSIS
               (SMC, Kronos, Quant, ML, OMEGA, RL)
                                │
                                ▼
                     STRUCTURAL SL/TP & R:R
                        (2.0R Hard Floor)
                                │
                                ▼
                     EV EXECUTION FRICTION
                       (EV >= $0.50 Edge)
                                │
                                ▼
                     PRE-ORDER ASSERTIONS
                    (Causality & Freshness)
                                │
                                ▼
                      MT5 ORDER TRANSMISSION
```

---

## 3. Removal of Confidence Trade Gates

All `CONFIDENCE >= X%` or `min_conf` checks as trade authorization gates are **100% eliminated**.

Trade decisions return a structured `PatternDecision`:

```python
@dataclass(frozen=True)
class PatternDecision:
    pattern_type: str
    action: str                       # "TRADE" or "WAIT"
    direction: str                    # "BUY", "SELL", or "WAIT"
    supporting_engines: List[str]
    conflicting_engines: List[str]
    entry_zone: float
    trigger_type: str
    stop_loss: float
    take_profit: float
    expected_value: float
    reason: str
    timestamp: datetime
```

---

## 4. Multi-Timeframe Structure

- **Higher Timeframe (H1 / M30):** Trend Context & Bias.
- **Medium Timeframe (M15 / M5):** Pattern Discovery (BOS, OB, Sweep).
- **Lower Timeframe (M1):** Trigger Execution (Displacement, Retest).
