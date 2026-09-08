# AEGIS GOLD — Structural SL/TP Architecture & EV Economics Specification

## 1. Executive Summary

This document specifies the **Structural Stop Loss (SL) / Take Profit (TP) Derivation Architecture** and **Expected Value (EV) Execution Economics** for AEGIS GOLD.

Generic fixed ATR multipliers (e.g. $\text{ATR} \times 1.5$) are **completely eliminated** from the entry path. All SL and TP levels trace back directly to observable structural levels on closed bars.

---

## 2. Structural SL Derivation Hierarchy

Stop Loss is set beyond the invalidation level of the **strongest confirming pattern** in the consensus ring:

```
CHoCH (Change of Character)    ── Strength 10
  ↓
BOS + Order Block              ── Strength 8
  ↓
Liquidity Sweep                ── Strength 7
  ↓
Order Block Alone              ── Strength 6
  ↓
Fair Value Gap (FVG)           ── Strength 5
```

### Buffer Additions:
To prevent spread noise hunting:
- **XAUUSD (Gold):** $+\text{Spread} + 15\,\text{pts}$ ($+\$0.15$)
- **EURUSD:** $+\text{Spread} + 3\,\text{pts}$ ($+\$0.00003$)

---

## 3. Structural TP Derivation Hierarchy

Take Profit targets the next structural reaction level in the predicted direction:
1. **Unmitigated Order Block** in opposite direction.
2. **Opposing Liquidity Pool** (Equal Highs/Lows, HTF swing pivot).
3. **Unfilled Fair Value Gap** edge.

---

## 4. R:R Floor & EV Execution Economics

### 2.0R Minimum Floor:
If the best structural TP yields $< 2.0\text{R}$, the trade is **REJECTED**. There is zero synthetic ATR fallback TP.

### Expected Value (EV) Formula:
$$EV = P(\text{win}) \times \text{GrossProfit} - P(\text{loss}) \times \text{GrossLoss} - \text{TotalExecutionCost}$$

Where:
- $\text{SpreadCost} = \text{spread\_pts} \times \text{point} \times \text{lot\_size} \times \text{contract\_size}$
- $\text{CommissionCost} = \$7.00 / \text{lot round-turn}$
- $\text{SlippageCost} = \text{slippage\_pts} \times \text{point} \times \text{lot\_size} \times \text{contract\_size}$

Trade is approved **ONLY IF $EV \ge \$0.50$ per trade**.
