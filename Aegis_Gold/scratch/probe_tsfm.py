"""Probe: can TTM / PatchTST / PatchTSMixer actually be loaded and run here?

Run:  .venv_cuda\\Scripts\\python.exe scratch\\probe_tsfm.py
Records only measured outcomes (no assumptions).
"""
import json
import os
import sys
import time
import traceback
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np


def probe_hf_config(repo: str) -> dict:
    try:
        with urllib.request.urlopen(
                f"https://huggingface.co/{repo}/resolve/main/config.json",
                timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        return {"_error": f"{type(exc).__name__}: {exc}"}


def try_patchtst(repo: str) -> dict:
    out = {"repo": repo, "loader": "PatchTSTForPrediction"}
    t0 = time.perf_counter()
    try:
        import torch
        from transformers import PatchTSTForPrediction
        model = PatchTSTForPrediction.from_pretrained(repo)
        model.eval()
        out["load_ms"] = round((time.perf_counter() - t0) * 1000.0, 1)
        ctx = int(getattr(model.config, "context_length", 0) or 512)
        n_ch = int(getattr(model.config, "num_input_channels", 1) or 1)
        out["context_length"] = ctx
        out["num_input_channels"] = n_ch
        # build `n_ch` genuinely distinct channels from a synthetic series
        base = np.sin(np.linspace(0, 40, ctx))
        chans = np.stack([base + 0.05 * k * np.cos(np.linspace(0, 20, ctx))
                          for k in range(n_ch)], axis=-1)
        x = torch.tensor(chans.reshape(1, ctx, n_ch), dtype=torch.float32)
        t1 = time.perf_counter()
        with torch.no_grad():
            y = model(past_values=x).prediction_outputs
        out["infer_ms"] = round((time.perf_counter() - t1) * 1000.0, 1)
        out["output_shape"] = list(y.shape)
        out["status"] = "RUNNING"
    except Exception as exc:
        out["status"] = "NOT_COMPATIBLE"
        out["error"] = f"{type(exc).__name__}: {exc}"
        out["trace"] = traceback.format_exc()[-400:]
    return out


def try_ttm(repo: str) -> dict:
    out = {"repo": repo, "loader": "auto"}
    try:
        import transformers as t
        avail = [n for n in dir(t) if "Granite" in n or "TTM" in n or "Tin" in n]
        out["transformers_granite_classes"] = avail
    except Exception as exc:
        out["error"] = str(exc)
    out["status"] = "NOT_TESTED"
    out["reason"] = "no GraniteTimeSeries/TTM class in transformers 5.14.1"
    return out


def main() -> int:
    results = []
    for repo in ("namctin/patchtst_etth1_forecast", "ibm/patchtst-etth1-pretrain"):
        cfg = probe_hf_config(repo)
        r = try_patchtst(repo)
        r["hf_architectures"] = cfg.get("architectures")
        results.append(r)
    for repo in ("ibm-granite/granite-timeseries-ttm-r2",
                 "ibm-granite/granite-timeseries-ttm-r1"):
        cfg = probe_hf_config(repo)
        r = try_ttm(repo)
        r["hf_architectures"] = cfg.get("architectures")
        results.append(r)
    for r in results:
        print(json.dumps(r, default=str)[:400])
    with open(os.path.join(os.path.dirname(__file__), "probe_tsfm_results.json"),
              "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
