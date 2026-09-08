# AEGIS GOLD — Phase 4 Entry Architecture & Trigger Specification

## 1. Executive Summary

This document specifies the upgraded **Setup/Trigger Separation Architecture** for AEGIS GOLD. 
Prior architecture conflated pattern identification (Setup) with entry timing (Trigger), leading to either late entries or unconfirmed trade chasing. 

Under v2.0, **Setup and Trigger are strictly separated**.

---

## 2. Setup State Machine

```
   NO_SETUP
      │
      ▼
SETUP_DETECTED        (Structure identified: OB, FVG, Liquidity Sweep, BOS)
      │
      ▼
SETUP_CONFIRMED       (Confirmed on closed bar; info_available <= T)
      │
      ▼
  ENTRY_ARMED         (Waiting for real-time micro-trigger)
      │
      ▼
TRIGGER_DETECTED      (Micro-trigger fired via RealTimeEntryTriggerEngine)
      │
      ▼
ENGINE_EVALUATION     (7-Engine Consensus & Quant Feature Vector)
      │
      ▼
 MASTER_DECISION      (EV Check & Execution Economics)
      │
      ▼
   EXECUTED / REJECTED
```

### Failure & Expiry States:
- **`EXPIRED`**: Setup age $> \text{setup\_expiry\_time}$ without trigger.
- **`INVALIDATED`**: Price breached invalidation level (OB high/low).
- **`STALE`**: Trigger age $> 180\,\text{s}$ before execution fill.
- **`CHASED`**: Price moved $> 50\,\text{pts}$ past trigger price.

---

## 3. Real-Time Entry Trigger Engine

The `RealTimeEntryTriggerEngine` ([brain/trigger_engine.py](file:///d:/Trading/Aegis_Gold/brain/trigger_engine.py)) scans closed M1 bars for micro-triggers ONLY when a setup is `ENTRY_ARMED`.

### Trigger Types:
1. **`DISPLACEMENT`**: M1 closed bar beyond prior M1 high/low in setup direction.
2. **`MOMENTUM_ACCEL`**: M1 candle body $> 1.2\times$ 10-bar rolling average body.
3. **`LEVEL_REJECTION`**: M1 wick touch at `setup_level` with closed rejection.
4. **`RETEST`**: Price retested `setup_level` and resumed setup direction.

### Causality Contract:
$$\text{information\_available\_time} \le \text{trigger\_time} \le \text{decision\_time}$$

---

## 4. Entry Chase & Staleness Detector

The `EntryChaseDetector` ([brain/chase_detector.py](file:///d:/Trading/Aegis_Gold/brain/chase_detector.py)) validates trigger freshness prior to order transmission:
1. **Trigger Age Gate:** Reject if $\text{trigger\_age} > 180\,\text{s}$.
2. **Chase Distance Gate:** Reject if $|\text{current\_price} - \text{trigger\_price}| > 50\,\text{pts}$ (Gold) or $8\,\text{pts}$ (EURUSD).
3. **Remaining R:R Floor:** Reject if remaining $\text{R:R} < 1.8\text{R}$ from current entry price.

---

## 5. Hard Pre-Order Assertions

Before any order is sent to MT5, the main execution loop enforces:

```python
assert setup.information_available_time <= decision_time
assert setup.confirmation_time <= decision_time
assert trigger.trigger_time <= decision_time
assert not chase_result.is_chased
assert not chase_result.is_stale
assert not setup.is_expired(decision_time)
```

If any assertion fails, the trade is **ABORTED**.
