# AEGIS GOLD — Phase 5 Quant Intelligence Engine v2 Specification

## 1. Executive Summary

The **Quant Intelligence Engine v2** ([brain/quant_feature_engine.py](file:///d:/Trading/Aegis_Gold/brain/quant_feature_engine.py)) delivers a causal statistical intelligence layer to the Master Brain.

It does **NOT** issue raw standalone `BUY`/`SELL` signals. Instead, it provides a point-in-time `QuantFeatureVector` that characterizes autocorrelation, stationarity, statistical extension, volatility clustering, and Geometric Brownian Motion (GBM) distribution bounds.

---

## 2. Feature Groups A through K

| Group | Feature Name | Mathematical / Statistical Definition | Trading Interpretation |
|---|---|---|---|
| **A** | **ACF (Return Autocorrelation)** | $\rho_k = \frac{\sum (r_t - \bar{r})(r_{t+k} - \bar{r})}{\sum (r_t - \bar{r})^2}$ (lags 1–5) | $\rho > 0 \implies$ return persistence; $\rho < 0 \implies$ reversal tendency. |
| **B** | **Causal Z-Score** | $Z_t = \frac{P_t - \mu_t}{\sigma_t}$ (trailing 10/20/50 bars) | Statistically stretched price distance from trailing mean. |
| **C** | **Stationarized Log Returns** | $r_t = \ln(P_t / P_{t-1})$ | Continuous rate of return input for ACF, Hurst, and Volatility. |
| **D** | **Realized Volatility** | $RV = \sqrt{\sum_{i=1}^N r_i^2}$ (short & medium windows) | Unannualized sum of squared return volatility. |
| **E** | **EWMA Volatility** | $\sigma_t^2 = \lambda \sigma_{t-1}^2 + (1-\lambda) r_t^2$ ($\lambda = 0.94$) | Fast-reacting risk metric for sudden volatility shifts. |
| **F** | **GARCH(1,1) Baseline** | $\sigma_t^2 = \omega + \alpha r_{t-1}^2 + \beta \sigma_{t-1}^2$ | Conditional variance model capturing volatility clustering. |
| **G** | **GBM Distribution Estimation** | $dS_t = \mu S_t dt + \sigma S_t dW_t$ | Estimates expected price $E[S_{t+5}]$, 95% confidence bands, and expected range. |
| **H** | **Hurst Exponent** | Rescaled Range ($R/S$) Analysis (100-bar window) | $H > 0.55 \implies$ trending regime; $H < 0.45 \implies$ mean-reverting noise. |
| **I** | **Shannon Entropy** | $H(X) = -\sum P(x) \log_2 P(x)$ (50-bar window) | Quantifies price distribution disorder / randomness. |
| **J** | **Return Autocorrelation** | Stationarized return lag checks | Eliminates non-stationary price level artifacts. |
| **K** | **Volatility Regime** | `LOW_VOL`, `NORMAL_VOL`, `HIGH_VOL`, `VOL_EXPANSION`, `VOL_COMPRESSION` | Classifies risk state for sizing and EV adjustments. |

---

## 3. Output Dataclass: `QuantFeatureVector`

```python
@dataclass(frozen=True)
class QuantFeatureVector:
    timestamp: datetime
    symbol: str

    # Returns & Autocorrelation
    last_close: float
    log_return_1: float
    log_return_5: float
    log_return_20: float
    acf_lag_1: float
    acf_lag_2: float
    acf_lag_3: float
    acf_lag_5: float

    # Z-Scores & Volatility
    zscore_short: float
    zscore_medium: float
    zscore_long: float
    realized_vol_short: float
    realized_vol_medium: float
    ewma_volatility: float
    garch_volatility: float

    # GBM Baseline
    gbm_drift: float
    gbm_volatility: float
    gbm_expected_price: float
    gbm_lower_band: float
    gbm_upper_band: float
    gbm_expected_range: float

    # Complexity & Regimes
    hurst_exponent: float
    shannon_entropy: float
    hfd_complexity: float
    volatility_regime: str
    market_regime: str
    confidence: float
```

---

## 4. Verification & Causality Assurance

All feature calculations in `QuantFeatureEngine`:
1. Use trailing windows ending strictly at $T$.
2. Contain zero `center=True`, zero `shift(-)`, and zero future data.
3. Verified by `tests/test_quant_feature_timestamp.py` (all tests passing).
