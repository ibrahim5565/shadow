"""AEGIS QUANT AI - measured MODEL MATRIX runner (Task 1 + Task 19).

Attempts EVERY candidate model on THIS machine and records only what was
actually observed.  Status vocabulary (never inflated):

    VERIFIED          real weights loaded AND produced a real prediction
    RUNNING           loads + runs, but domain/asset mismatch (not signal-grade)
    NOT_COMPATIBLE    dependency or architecture/asset mismatch
    REJECTED          weights unavailable / gated / licence unclear
    NOT_TESTED        deliberately not exercised this session

Output: docs/model_matrix.json  +  printed table.

Run:  .venv_cuda\\Scripts\\python.exe scripts\\run_model_matrix.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from quant_ai.performance import probe_environment, installed_packages, rss_mb

DOCS = os.path.join(os.path.dirname(__file__), "..", "docs")
OUT = os.path.join(DOCS, "model_matrix.json")

# ── catalogue: real, publicly documented metadata ───────────────────────────
CATALOG = [
    # ---- Priority 1: forex-specific ------------------------------------
    dict(key="omega_forex_v3", module="quant_ai.models.omega_adapter",
         cls="OmegaForexAdapter", symbol="EURUSD", tier=1,
         repo="https://huggingface.co/sato2ru/omega-forex",
         checkpoint="omega_model.pt", license="MIT", size_mb=0.77,
         expected="CNN + RegimeGate + Transformer, binary up/down, 24x46 input"),
    dict(key="eurusd_lgb_xgb", module="quant_ai.models.eurusd_adapter",
         cls="EURUSDEnsembleAdapter", symbol="EURUSD", tier=1,
         repo="https://huggingface.co/lvizcaya/forex-eurusd-direction",
         checkpoint="eurusd_lgb.joblib + eurusd_xgb.joblib", license="Apache-2.0",
         size_mb=2.56,
         expected="LightGBM 0.39 + XGBoost 0.61 direction ensemble"),
    # ---- Priority 2: gold-specific -------------------------------------
    dict(key="xauusd_smc_xgb", module="quant_ai.models.xauusd_adapter",
         cls="XAUUSD_SMC_Adapter", symbol="XAUUSD", tier=2,
         repo="https://huggingface.co/JonusNattapong/xauusd-trading-ai-smc-v2",
         checkpoint="xauusd_smc_xgb.json", license="MIT", size_mb=0.73,
         expected="XGBoost on gold price action + Smart Money Concepts"),
    # ---- Priority 3: financial / time-series foundation models ----------
    dict(key="kronos_small", module="quant_ai.models.kronos_adapter",
         cls="KronosAdapter", symbol="XAUUSD", tier=3,
         repo="https://github.com/shiyu-coder/Kronos",
         checkpoint="NeoQuasar/Kronos-small", license="MIT", size_mb=98.0,
         expected="decoder-only TS foundation model, sampled multi-path forecasts",
         kwargs={"model_key": "kronos_small"}),
    dict(key="kronos_mini", module="quant_ai.models.kronos_adapter",
         cls="KronosAdapter", symbol="XAUUSD", tier=3,
         repo="https://github.com/shiyu-coder/Kronos",
         checkpoint="NeoQuasar/Kronos-mini", license="MIT", size_mb=16.0,
         expected="smaller Kronos variant",
         kwargs={"model_key": "kronos_mini"}),
    dict(key="chronos2", module="quant_ai.models.chronos_adapter",
         cls="ChronosAdapter", symbol="XAUUSD", tier=3,
         repo="https://github.com/amazon-science/chronos-forecasting",
         checkpoint="amazon/chronos-t5-* (chronos2)", license="Apache-2.0",
         size_mb=200.0, expected="Chronos-2 quantile forecaster",
         kwargs={"checkpoint": "chronos2"}),
    dict(key="patchtst", module="quant_ai.models.patchtst_adapter",
         cls="PatchTSTAdapter", symbol="XAUUSD", tier=3,
         repo="https://huggingface.co/ibm/patchtst-etth1-pretrain",
         checkpoint="ibm/patchtst-etth1-pretrain", license="Apache-2.0",
         size_mb=7.0,
         expected="PatchTST; ships a MASKED-PRETRAINING head only -> forecast "
                  "head would be randomly initialised, so it is refused"),
]

# candidates that could NOT be exercised, with the exact blocking reason
BLOCKED = [
    dict(key="moirai", repo="https://github.com/SalesforceAIResearch/uni2ts",
         checkpoint="Salesforce/moirai-1.1-R-small", license="Apache-2.0",
         status="NOT_COMPATIBLE", reason="`uni2ts` package not installed"),
    dict(key="timesfm", repo="https://github.com/google-research/timesfm",
         checkpoint="google/timesfm-2.0-200m-pytorch", license="Apache-2.0",
         status="NOT_COMPATIBLE", reason="`timesfm` package not installed"),
    dict(key="ttm_r1_r2",
         repo="https://huggingface.co/ibm-granite/granite-timeseries-ttm-r2",
         checkpoint="granite-timeseries-ttm-r1/r2", license="Apache-2.0",
         status="NOT_COMPATIBLE",
         reason="no GraniteTimeSeries/TTM class in transformers 5.14.1; needs `granite-tsfm`"),
    dict(key="patchtst_namctin",
         repo="https://huggingface.co/namctin/patchtst_etth1_forecast",
         checkpoint="namctin/patchtst_etth1_forecast", license="gated",
         status="REJECTED", reason="gated repo: HTTP 401 without authentication"),
    dict(key="kronos_large", repo="https://github.com/shiyu-coder/Kronos",
         checkpoint="Kronos-large", license="MIT (weights unreleased)",
         status="REJECTED", reason="weights not publicly released"),
    dict(key="timer_xl", repo="https://github.com/thuml/Timer-XL",
         checkpoint="Timer-XL-8M/10M", license="Apache-2.0",
         status="NOT_TESTED", reason="dedicated Timer-XL codebase not installed"),
    dict(key="timer", repo="https://github.com/thuml/Timer",
         checkpoint="Timer-base", license="Apache-2.0",
         status="NOT_TESTED", reason="dedicated Timer codebase not installed"),
    dict(key="time_moe", repo="https://github.com/Time-MoE/Time-MoE",
         checkpoint="Time-MoE-base-200M", license="Apache-2.0",
         status="NOT_TESTED", reason="Time-MoE codebase not installed"),
    dict(key="tirex", repo="https://github.com/NX-AI/tirex",
         checkpoint="NX-AI/TiRex", license="Apache-2.0",
         status="NOT_TESTED", reason="`tirex-ts` not installed"),
    dict(key="sundial", repo="https://github.com/thuml/Sundial",
         checkpoint="thuml/sundial-base-128m", license="Apache-2.0",
         status="NOT_TESTED", reason="Sundial support not present in installed transformers"),
    dict(key="moment",
         repo="https://github.com/moment-timeseries-foundation-model/moment",
         checkpoint="AutonLab/MOMENT-1-large", license="MIT",
         status="NOT_TESTED", reason="`momentfm` not installed"),
    dict(key="lag_llama",
         repo="https://github.com/time-series-foundation-models/lag-llama",
         checkpoint="lag-llama.ckpt", license="Apache-2.0",
         status="NOT_TESTED", reason="`lag-llama` + gluonts not installed"),
    dict(key="patchtsmixer",
         repo="https://huggingface.co/ibm/patchtsmixer-etth1-pretrain",
         checkpoint="ibm/patchtsmixer-etth1-pretrain", license="Apache-2.0",
         status="NOT_TESTED", reason="same ETTh1 domain mismatch as PatchTST"),
]


def synth(symbol: str, n: int = 700, seed: int = 17) -> pd.DataFrame:
    """DISABLED synthetic generator (Oct 2026 real-data-only policy)."""
    raise RuntimeError(
        "SYNTHETIC DATA DISABLED: scripts/run_model_matrix.py:synth must "
        "never be called. The audit refuses to run without real MT5 "
        "exports (12-month M5, M15, H1). All previous funnel results "
        "(48,018 patterns / 4 trades) are INVALID (synthetic data).")


def measure(entry: dict) -> dict:
    """Actually load + predict with one adapter; record observed reality."""
    import importlib
    row = {k: entry.get(k) for k in
           ("key", "repo", "checkpoint", "license", "size_mb", "symbol",
            "tier", "expected")}
    row["status"] = "NOT_TESTED"
    rss0 = rss_mb()
    try:
        mod = importlib.import_module(entry["module"])
        cls = getattr(mod, entry["cls"])
        kwargs = dict(entry.get("kwargs") or {})
        t0 = time.perf_counter()
        inst = cls(symbol=entry["symbol"], timeframe="M5", device="cpu", **kwargs)
        loaded = inst.load()
        row["load_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        row["weights_loaded"] = bool(loaded)
        if not loaded:
            row["status"] = "REJECTED"
            row["reason"] = (getattr(inst, "_refuse_reason", "")
                             or "weights could not be loaded")
            return row
        df = None
        csv_path = (entry.get("csv") or os.environ.get("QAI_REAL_CSV", ""))
        if csv_path:
            from quant_ai.data_mt5 import load_mt5_csv
            df = load_mt5_csv(csv_path, timeframe="M5")
            row["verified_on"] = {"data": f"real MT5 export {csv_path}",
                                  "n_bars": len(df), "horizon": 12,
                                  "symbol_label": entry["symbol"],
                                  "device": "cpu"}
        else:
            row["status"] = "NOT_TESTED"
            row["reason"] = ("no real MT5 export supplied (set QAI_REAL_CSV "
                             "or entry['csv']); synthetic harness DISABLED. "
                             "Previous funnel results are INVALID.")
            return row
        t1 = time.perf_counter()
        pred = inst.predict(df, 12)
        row["latency_ms"] = round((time.perf_counter() - t1) * 1000.0, 1)
        row["prediction_status"] = pred.status.value
        row["predicted_direction"] = pred.direction.value
        row["predicted_price"] = pred.forecast_price
        row["probability_up"] = pred.probability_up
        row["uncertainty"] = pred.uncertainty
        if pred.status.value == "ok" and pred.forecast_price is not None:
            row["status"] = ("RUNNING" if entry.get("domain_note") else "VERIFIED")
            row["domain_note"] = entry.get("domain_note")
            # Bound what VERIFIED means so nobody over-reads it: this run proves
            # the checkpoint loads and runs, it does NOT prove forecasting skill.
            row["evidence"] = (
                "checkpoint weights loaded and produced one finite forecast on a "
                "real MT5 export. Load-and-run check only "
                "NOT out-of-sample accuracy, NOT profitability, and NOT a live-MT5 "
                "test. Signal weight must come from ModelSelector on measured "
                "error_log evidence, never from this row.")
            row["verified_on"] = {"data": f"real MT5 export {csv_path}",
                                  "n_bars": len(df), "horizon": 12,
                                  "symbol_label": entry["symbol"],
                                  "device": "cpu"}
        else:
            row["status"] = "NOT_COMPATIBLE"
            row["reason"] = f"predict returned {pred.status.value}: {pred.detail}"
    except Exception as exc:
        row["status"] = "NOT_COMPATIBLE"
        row["error"] = f"{type(exc).__name__}: {exc}"
        row["trace"] = traceback.format_exc()[-500:]
    finally:
        row["rss_delta_mb"] = round(rss_mb() - rss0, 1)
    return row


def main() -> int:
    print("=" * 100)
    print("AEGIS QUANT AI - MEASURED MODEL MATRIX")
    print("=" * 100)
    env = probe_environment()
    pkgs = installed_packages()
    print("ENVIRONMENT")
    for k, v in env.items():
        print(f"  {k:<20} {v}")
    print("PACKAGES")
    for k, v in pkgs.items():
        print(f"  {k:<20} {v if v else 'NOT INSTALLED'}")

    rows = []
    print("\nMEASURED ADAPTERS")
    for entry in CATALOG:
        r = measure(entry)
        rows.append(r)
        print(f"  [{r['status']:<15}] {r['key']:<16} "
              f"load={r.get('load_ms')}ms lat={r.get('latency_ms')}ms "
              f"dir={r.get('predicted_direction')} "
              f"w={r.get('predicted_price')} rss+={r.get('rss_delta_mb')}MB")
        if r.get("error"):
            print(f"       error: {r['error'][:150]}")

    blocked = [{**b, "measured": False} for b in BLOCKED]
    print("\nNOT EXERCISED (with exact blocking reason)")
    for b in blocked:
        print(f"  [{b['status']:<15}] {b['key']:<18} {b['reason']}")

    verified = [r["key"] for r in rows if r["status"] == "VERIFIED"]
    running = [r["key"] for r in rows if r["status"] == "RUNNING"]
    print("\n" + "-" * 100)
    print(f"VERIFIED={len(verified)} {verified}")
    print(f"RUNNING (domain-mismatched)={len(running)} {running}")
    print(f"NOT_COMPATIBLE/REJECTED/NOT_TESTED={len(blocked)}")

    payload = {"environment": env, "packages": pkgs,
               "measured": rows, "not_exercised": blocked,
               "summary": {"verified": verified, "running": running,
                           "verified_count": len(verified),
                           "running_count": len(running),
                           "not_exercised_count": len(blocked)}}
    os.makedirs(DOCS, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"\nwritten -> {os.path.abspath(OUT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


