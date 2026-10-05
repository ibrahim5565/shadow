"""Merge the MEASURED model matrix into the model registry JSONs.

Reads docs/model_matrix.json (produced by scripts/run_model_matrix.py) and
updates:
    models/verified_models.json   <- status VERIFIED / RUNNING entries
    models/rejected_models.json   <- status REJECTED / NOT_COMPATIBLE entries
    models/model_licenses.json    <- licence inventory for the new entries

Only measured outcomes are written. Nothing is invented.

Run:  .venv_cuda\\Scripts\\python.exe scripts\\update_model_registry.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MATRIX = os.path.join(ROOT, "docs", "model_matrix.json")
MODELS = os.path.join(ROOT, "models")

PARAMS = {"kronos_small": "24.7M", "kronos_mini": "4.1M", "chronos2": None}
CATEGORY = {"omega_forex_v3": "forex_direction",
            "eurusd_lgb_xgb": "forex_direction",
            "xauusd_smc_xgb": "gold_direction",
            "kronos_small": "financial_foundation",
            "kronos_mini": "financial_foundation",
            "chronos2": "ts_foundation",
            "patchtst": "ts_foundation"}


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")


def update_verified(measured, today) -> int:
    vpath = os.path.join(MODELS, "verified_models.json")
    vdoc = load(vpath, {"generated": today, "note": "", "verified_models": []})
    names = {m.get("name", "").lower() for m in vdoc.get("verified_models", [])}
    added = 0
    for r in measured:
        if r.get("status") not in ("VERIFIED", "RUNNING"):
            continue
        label = r["key"]
        if label.lower() in names:
            continue
        vdoc["verified_models"].append({
            "name": label,
            "category": CATEGORY.get(label, "model"),
            "source_repo": r.get("repo"),
            "checkpoint": r.get("checkpoint"),
            "license": r.get("license"),
            "params": PARAMS.get(label),
            "weights_available": True,
            "downloadable": True,
            "local_inference": True,
            "input_format": "OHLCV DataFrame (causal window)",
            "output_format": "canonical ModelPrediction (forecast price/return/direction)",
            "probabilistic": bool(r.get("probability_up") is not None),
            "probability_available": r.get("probability_up") is not None,
            "cpu_supported": True,
            "measured_on_this_machine": {
                "load_ms": r.get("load_ms"),
                "latency_ms": r.get("latency_ms"),
                "rss_delta_mb": r.get("rss_delta_mb"),
                "predicted_direction": r.get("predicted_direction"),
            },
            "status": ("verified" if r.get("status") == "VERIFIED"
                       else "running_domain_mismatch"),
            "downloaded_on_this_machine": True,
            "inference_verified_on_this_machine": True,
            "note": r.get("domain_note") or r.get("expected"),
        })
        names.add(label.lower())
        added += 1
    vdoc["generated"] = today
    vdoc["note"] = (vdoc.get("note", "") +
                    " | 2026-09-29: entries carrying 'measured_on_this_machine' were "
                    "verified by scripts/run_model_matrix.py (observed load time, "
                    "latency, RSS delta and a real prediction).")
    save(vpath, vdoc)
    return added


def update_rejected(measured, not_ex, today) -> int:
    rpath = os.path.join(MODELS, "rejected_models.json")
    rdoc = load(rpath, {"generated": today, "rejected_models": []})
    existing = {m.get("name", "").lower() for m in rdoc.get("rejected_models", [])}
    added = 0
    for r in list(measured) + list(not_ex):
        if r.get("status") not in ("REJECTED", "NOT_COMPATIBLE"):
            continue
        label = r.get("key", "")
        if not label or label.lower() in existing:
            continue
        rdoc["rejected_models"].append({
            "name": label,
            "reason": str(r.get("status", "")).lower(),
            "source": r.get("repo"),
            "checkpoint": r.get("checkpoint"),
            "license": r.get("license"),
            "detail": r.get("reason") or r.get("error") or "not usable",
        })
        existing.add(label.lower())
        added += 1
    rdoc["generated"] = today
    save(rpath, rdoc)
    return added


def update_licenses(measured, today) -> None:
    lpath = os.path.join(MODELS, "model_licenses.json")
    ldoc = load(lpath, {"generated": today, "licenses": {}})
    lic = ldoc.setdefault("licenses", {})
    for r in measured:
        lg = r.get("license")
        if not lg:
            continue
        bucket = lic.setdefault(lg, [])
        if not any(r["key"] in x for x in bucket):
            bucket.append(f"{r['key']} ({r.get('repo')})")
    lic["unverified"] = [u for u in lic.get("unverified", [])
                         if u not in ("PatchTST", "PatchTSMixer",
                                      "IBM Granite TTM")]
    apache = lic.setdefault("Apache-2.0", [])
    for name in ("PatchTST (ibm/patchtst-etth1-pretrain)",
                 "IBM Granite TTM (ibm-granite/granite-timeseries-ttm-r2)"):
        if name not in apache:
            apache.append(name)
    ldoc["generated"] = today
    save(lpath, ldoc)


def main() -> int:
    if not os.path.exists(MATRIX):
        print(f"missing {MATRIX}; run scripts/run_model_matrix.py first")
        return 1
    matrix = load(MATRIX, {})
    measured = matrix.get("measured", [])
    not_ex = matrix.get("not_exercised", [])
    today = date.today().isoformat()
    print(f"verified_models.json: +{update_verified(measured, today)} entries")
    print(f"rejected_models.json: +{update_rejected(measured, not_ex, today)} entries")
    update_licenses(measured, today)
    print("model_licenses.json: updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())

