# AEGIS GOLD — Pattern Library Specification

## 1. Overview
The Pattern Library ([brain/pattern_library.py](file:///d:/Trading/Aegis_Gold/brain/pattern_library.py)) defines all formal market structure patterns recognized by AEGIS GOLD.

---

## 2. Pattern Hierarchy & Ranking

| Rank | Pattern Type | Category | Strength Score | Description |
|---|---|---|---|---|
| **10** | `CHOCH_BULLISH` / `CHOCH_BEARISH` | SMC Structure | 10.0 | Change of Character structural reversal |
| **8** | `BOS_BULLISH` / `BOS_BEARISH` | SMC Structure | 8.0 | Break of Structure trend continuation |
| **7** | `LIQUIDITY_SWEEP_BULLISH` / `BEARISH` | Liquidity | 7.0 | High/Low liquidity pool grab & rejection |
| **6** | `ORDER_BLOCK_BULLISH` / `BEARISH` | SMC Structure | 6.0 | Institutional Order Block mitigation |
| **6** | `BREAKER_BULLISH` / `BEARISH` | SMC Structure | 6.0 | Failed Order Block breaker retest |
| **5** | `FVG_CONTINUATION_BULLISH` / `BEARISH` | Liquidity | 5.0 | Fair Value Gap imbalance fill |
| **4** | `DISPLACEMENT_BULLISH` / `BEARISH` | Price Action | 4.0 | Strong impulsive body displacement |
| **4** | `RETEST_BULLISH` / `BEARISH` | Price Action | 4.0 | Retest of broken structural level |

---

## 3. Structural Pattern Dataclass

```python
@dataclass
class StructuralPattern:
    pattern_id: str
    pattern_type: PatternType
    category: PatternCategory
    direction: str
    symbol: str
    formation_time: datetime
    confirmation_time: datetime
    information_available_time: datetime
    price_level: float
    invalidation_level: float
    target_level: float
    strength_score: float
    evidence_notes: List[str]
    expiry_time: Optional[datetime]
```
