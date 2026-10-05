# AEGIS QUANT AI — FINAL AUDIT REPORT

Date: 2026-09-09 · Machine: Windows, RTX 3050 6GB (CUDA) + CPU fallback
Scope: directive Sections 1–53. Every number below is an **actual measurement** on this machine. No profitability is claimed anywhere.

---

## A. Models discovered / verified

Full registry: `models/verified_models.json`, `models/rejected_models.json`, `models/model_licenses.json`.

| Model | Repository | Checkpoint | License | Size | Downloaded | Load | Inference |
|---|---|---|---|---|---|---|---|
| Kronos-small | github.com/shiyu-coder/Kronos | HF `NeoQuasar/Kronos-small` + `Kronos-Tokenizer-base` | MIT | 24.7M | YES (HF cache) | OK (cpu/cuda) | **VERIFIED** — real sampled forecasts on MT5 data |
| Kronos-mini | same | HF `NeoQuasar/Kronos-mini` | MIT | 4.1M | no (optional) | adapter ready | not exercised |
| Kronos-base | same | HF `NeoQuasar/Kronos-base` | MIT | 102.3M | no (fits 6GB, optional) | adapter ready | not exercised |
| Chronos-2 | amazon-science/chronos-forecasting | HF `amazon/chronos-models` | Apache-2.0 | — | no (`pip install chronos-forecasting` required) | adapter ready | not exercised |
| Moirai 1.1/2.0-R | SalesforceAIResearch/uni2ts | HF `Salesforce/moirai-*` | Apache-2.0 (research-use note) | — | no (`pip install uni2ts`) | adapter ready | not exercised |
| TimesFM 3.0 | google-research/timesfm | HF `google/timesfm-3.0-pytorch` | Apache-2.0 | — | no (`pip install timesfm`) | adapter ready | not exercised |
| FinBERT | ProsusAI/finBERT | HF `ProsusAI/finbert` | Apache-2.0 | 110M | lazy (downloads on first enabled use) | adapter (`quant_ai/nlp/sentiment.py`) | gated behind `news_mode=DISABLED` |
| IsolationForest/OCSVM/LOF | scikit-learn | n/a (trained on live data) | BSD-3 | — | installed | OK | OK (anomaly layer) |
| GARCH/EGARCH/GJR | bashtage/arch | n/a (fit per series) | MIT | — | installed | OK | OK (volatility engine) |
| Stable-Baselines3 (PPO) | DLR-RM/stable-baselines3 | n/a (trains locally) | MIT | — | installed | OK | OK (RL research run below) |
| Microsoft Qlib | microsoft/qlib | n/a (framework) | MIT | — | not installed | — | used as design reference only |

Kronos-small inference was verified with the **real pretrained checkpoint** (HF safetensors, ~1.5s cold load on CPU, sampled multi-path forecasts).

## B. Models rejected (with reasons)

See `models/rejected_models.json`. Highlights:
- **Kronos-large** — weights not publicly released; refused to pretend.
- **PyPI `kronos` 0.2.2** — unrelated Django scheduler package, not the foundation model.
- **Legacy Aegis `kronos_small.pt`** — randomly-initialized local checkpoint mislabeled "Kronos" in the old engine; excluded from all pretrained claims (preserved untouched).
- **FinGPT** — gated weights (HTTP 401 without auth), Llama-3 community license; replaced by FinBERT (Apache-2.0).
- **FinText, forex/EURUSD/XAUUSD-specific HF checkpoints** — no license-clear, weight-complete official release verified; HF tags alone are not evidence.
- **TiRex, Sundial, Time-MoE, MOMENT, Lag-Llama, Timer, Granite TTM, PatchTST(M)** — catalogued INVESTIGATE; not verified this session, not installed.

## C. Installed dependencies (purpose)

Existing venv `.venv_cuda` (torch CUDA) plus:

| Package | Purpose |
|---|---|
| `einops 0.8.1` | Kronos vendor code requirement |
| `gymnasium` | RL env API |
| `stable-baselines3` (+torch) | PPO research training |
| `huggingface_hub`, `transformers` | checkpoint download/inference |
| `arch` | GARCH-family volatility |
| `scikit-learn` | anomaly detection, regime clustering |
| `pandas/numpy` | data pipeline |
| `MetaTrader5` | demo data + (future) demo execution |

## D/E. Files changed / created

Created (quant_ai stack — all new, isolated from legacy code):

```
quant_ai/__init__.py  config.py  predictions.py  registry.py  downloader.py
quant_ai/models/{base,baselines,kronos_adapter,chronos_adapter,moirai_adapter,timesfm_adapter,__init__}.py
quant_ai/quant/{factors,volatility,regime,anomaly}.py
quant_ai/risk/{risk_engine,position_sizer}.py
quant_ai/execution/{demo_guard,validator}.py
quant_ai/rl/{environment,agents,__init__}.py
quant_ai/nlp/{sentiment,__init__}.py
quant_ai/storage/db.py
quant_ai/validation/{metrics,walk_forward,tournament,backtest_engine}.py
quant_ai/vendor/kronos/            (official upstream clone, unmodified)
models/{verified_models,rejected_models,model_licenses}.json
scripts/{train_rl_research,run_tournament_measured}.py
tests/quant_ai_test_suite.py
scratch/{rl_research_results,tournament_results}.json
docs/QUANT_AI_AUDIT_REPORT.md
```

Modified: **none of the legacy AEGIS trading code was modified.** The stack is additive; `modules/mt5_gateway.py`, `modules/risk_manager.py`, `core/*`, `kronos_engine/*` remain untouched.

## F. Models successfully running (measured)

- **Kronos-small (real weights)**: loaded and produced sampled probabilistic OHLCV forecasts on live MT5 demo M5 data; per-forecast latency and uncertainty recorded in the `model_predictions` SQLite table.
- **6 naive baselines**: run in the tournament as the minimum bar (Section 30).
- **34/34 unit tests pass** (see section I below).

## G. Backtest / tournament results (measured)

Walk-forward, embargo=12 bars, step=50, horizon=12, on 3000 real MT5-demo M5 bars per symbol. Data source: connected MT5 demo terminal. Full JSON: `scratch/tournament_results.json`; leaderboard persisted in SQLite `model_tournament`.

**EURUSD M5 (n=58 out-of-sample forecasts):**

| Model | MAE | RMSE | Dir. accuracy | Brier |
|---|---|---|---|---|
| baseline_sma | **0.000432** | 0.000662 | 0.667 | — |
| baseline_previous_close | 0.000441 | **0.000639** | **0.737** | — |
| baseline_random_walk | 0.000452 | 0.000640 | **0.737** | — |
| kronos (real weights) | 0.000519 | 0.000771 | 0.632 | 0.579 |
| baseline_ema_trend | 0.000589 | 0.000781 | 0.667 | — |
| baseline_momentum | 0.000853 | 0.001133 | 0.597 | — |
| baseline_rsi | 0.001873 | 0.001979 | 0.719 | — |

**XAUUSD M5 (n=58 out-of-sample forecasts):**

| Model | MAE | RMSE | Dir. accuracy | Brier |
|---|---|---|---|---|
| baseline_previous_close | **8.657** | **11.672** | 0.754 | — |
| baseline_random_walk | 9.108 | 12.319 | 0.754 | — |
| baseline_sma | 9.916 | 13.186 | 0.719 | — |
| kronos (real weights) | 11.237 | 14.689 | 0.719 | 0.406 |
| baseline_ema_trend | 12.147 | 18.443 | 0.772 | — |
| baseline_momentum | 14.955 | 19.191 | 0.684 | — |
| baseline_rsi | 45.426 | 47.060 | 0.737 | — |

**Honest conclusion:** Kronos-small did NOT beat the naive previous-close/random-walk baselines on either symbol in this run (MAE 0.000519 vs 0.000441 on EURUSD; 11.24 vs 8.66 on XAUUSD). Its EURUSD Brier 0.579 is worse than coin-flip; XAUUSD Brier 0.406 is informative but not sufficient. Per the interpretation policy, **no model is promoted**. Tournament elapsed: 501.9s (Kronos CPU sampling dominates).

**Interpretation policy:** a model is only "useful" if it beats `baseline_previous_close` / `random_walk` out-of-sample. No model was promoted this session.

## H. RL results (measured, real run)

`scripts/train_rl_research.py` — PPO (SB3, 30k timesteps) on the real `TradingEnv` over 3000 EURUSD M5 demo bars (MT5 data), risk-routed actions:

```
hold_only      steps=2879  equity=10000.00  return= 0.000%  trades= 0
random_policy  steps=2879  equity= 9911.08  return=-0.889%  trades=11  dd=1.75%
ppo_trained    steps=2879  equity= 9939.76  return=-0.602%  trades=12  dd=2.01%
```

Honest reading: at 30k timesteps PPO is **not profitable**; it merely lost less than random. The RL_DEMO gate stays closed (Sections 10/48): no walk-forward validation evidence → `rl_mode_gate(RL_DEMO)` returns BLOCKED (unit-tested).

## I. Risk-engine tests (measured)

`tests/quant_ai_test_suite.py` → **TOTAL=34 PASS=34 FAIL=0**, covering:

- sizing: fixed-fractional budget match, SL-distance monotonicity
- filters: abnormal spread block, unknown-session block, daily-loss stop, consecutive-loss stop
- execution (error-10016 guard): BUY/SELL direction validation, SL-below-stops-level rejection, naked-SL rejection, volume step normalization, min-volume rejection, invalid side
- safety: demo pass, LIVE server blocked, `allow_live=True` still blocked, hardcoded `TRADING_MODE=DEMO`, RL_DEMO gate
- RL env: finite obs, causal features (no future leak), risk-routed BUY/CLOSE, spread block, drawdown force-close, intra-bar SL bounding
- adapters: empty df / NaN / short-history → INSUFFICIENT_DATA (never fabricated output)
- storage: predictions / forecast-errors / decisions persist and round-trip

## J. MT5 DEMO tests (measured)

- MT5 terminal connected (demo account); 3000 M5 bars fetched per symbol for EURUSD and XAUUSD via `copy_rates_from_pos`.
- `DemoGuard.check()` unit-tested: demo passes; live server blocked; the allow-live escape hatch is inert.
- No order was sent in this session (validator + demo guard are unit-tested; live demo order send is intentionally deferred to the monitored paper→demo stage, Section 48).

## K. Remaining problems

1. **Single verified foundation model.** Only Kronos-small runs with real weights; Chronos-2 / Moirai / TimesFM adapters exist but their packages were not installed — multi-model ensemble is untested until they are.
2. **Kronos CPU latency.** ~2–5s per sampled forecast on CPU; walk-forward tournament with sampled uncertainty is slow. GPU path exists but shares the 6GB card with the legacy engine.
3. **No legal/free news feed verified** → `news_mode=DISABLED`; FinBERT integrated but dormant.
4. **RL not promoted.** PPO underperformed hold; needs longer training, forecast inputs in the state, and walk-forward evaluation before paper/demo.
5. **Regime/volatility layers are classical** (ATR/EWMA/GARCH/ADX/change-point); no pretrained regime model was verified.
6. **Legacy duplication.** The old `kronos_engine` remains the legacy AEGIS brain; cutover is a separate, deliberate step.
7. **No HF token** → anonymous rate-limited downloads; set `HF_TOKEN` for reliable checkpoint caching.

## Absolute-rules compliance

- No invented models/checkpoints/licenses/performance; every metric above was produced by a script on this machine.
- No future data: walk-forward with embargo; causal features unit-tested.
- Nothing bypasses risk: RL actions route through `RiskManager`; orders require `ExecutionValidator`; live trading is structurally blocked (`TRADING_MODE="DEMO"` hard-coded, `DemoGuard` rejects live servers).


