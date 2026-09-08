# AEGIS GOLD — Local AI Pattern Engine Architecture

## 1. Executive Summary

AEGIS GOLD relies **100% on Local AI engines**. No cloud LLMs, external APIs, or remote dependencies are used for trading decisions.

---

## 2. Local 7-Engine Role Matrix

```
1. SMC ENGINE           ── Primary Structural Pattern Detector (BOS, OB, FVG, Sweep)
2. KRONOS FORECASTER    ── Evaluates price trajectory compatibility with pattern
3. QUANT ENGINE v2      ── Statistical Context (ACF, Z-Score, EWMA, GARCH, GBM, Hurst, Entropy)
4. ML ENSEMBLE          ── Pattern Success Probability & Expected Move Estimator
5. OMEGA AI SUPERVISOR  ── Candle structure, momentum & rejection evaluator
6. UNIFIED BRAIN        ── Pattern Decision Orchestrator (Returns PatternDecision)
7. RL META-WEIGHTER     ── Pattern & Regime Meta-Weighter (0.5 ... 2.0 conviction multiplier)
```

---

## 3. Consensus & Veto Logic

- Requires $\ge 5/6$ directional agreement across SMC, Kronos, Quant, ML, and OMEGA.
- RL Agent acts as meta-weighter only and is **excluded** from directional agreement count.
- If agreement $< 5/6$, Unified Brain returns `PatternDecision(action="WAIT")`.
