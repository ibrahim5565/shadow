"""AEGIS QUANT AI - dynamic model selection + ensemble (Phase-2 Tasks 4-5).

NO blind majority voting.  Selection/weighting is driven only by MEASURED,
chronologically available evidence:

  - out-of-sample forecast errors recorded in QuantAIStore (walk-forward runs)
  - recent degradation (second-half error vs first-half error)
  - the model's own prediction uncertainty (never fabricated)
  - measured inference latency
  - current regime / volatility gate supplied by the caller

A model with no measured history gets weight 0 until it earns evidence.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from quant_ai.predictions import Direction, ModelPrediction, PredictionStatus
from quant_ai.storage.db import QuantAIStore

logger = logging.getLogger("quant_ai.ensemble")


@dataclass
class ModelScore:
    model: str
    mae: float                      # rolling OOS MAE (price units)
    samples: int
    degradation: float              # >0 means error growing over time
    latency_ms: float
    weight: float = 0.0
    eligible: bool = False
    reason: str = ""


class ModelSelector:
    """Ranks models by measured OOS performance; no voting."""

    def __init__(self, store: QuantAIStore, min_samples: int = 20,
                 max_mae: Optional[float] = None, max_degradation: float = 2.0,
                 max_latency_ms: float = 30_000.0):
        self.store = store
        self.min_samples = min_samples
        self.max_mae = max_mae          # price-unit ceiling; None = auto (median)
        self.max_degradation = max_degradation
        self.max_latency_ms = max_latency_ms

    def score_models(self, symbol: str, limit: int = 300) -> Dict[str, ModelScore]:
        scores: Dict[str, ModelScore] = {}
        rows = self.store.recent_forecast_errors(symbol=symbol, limit=limit * 8)
        by_model: Dict[str, List[dict]] = {}
        for r in rows:
            by_model.setdefault(r["model"], []).append(r)
        for model, errs in by_model.items():
            # recent_forecast_errors returns NEWEST first: keep the most recent
            # `limit` records, then restore chronological order so that the
            # first/second halves below really mean older/recent.
            errs = errs[:limit][::-1]
            n = len(errs)
            abs_err = [abs(e["forecast"] - e["actual"]) for e in errs]
            mae = float(np.mean(abs_err)) if n else math.nan
            half = max(n // 2, 1)
            older = float(np.mean(abs_err[:-half])) if n > half else mae
            recent = float(np.mean(abs_err[-half:])) if n > half else mae
            degradation = (recent / older) if older and older > 0 else 1.0
            scores[model] = ModelScore(model=model, mae=mae, samples=n,
                                       degradation=round(degradation, 3),
                                       latency_ms=0.0)
        return scores

    def select(self, predictions: List[ModelPrediction], symbol: str,
               volatility_percentile: float = 0.5,
               max_models: int = 3) -> List[ModelScore]:
        """Return eligible models (best first) with normalized weights."""
        scores = self.score_models(symbol)
        ok_preds = [p for p in predictions if p.status == PredictionStatus.OK]
        by_name = {p.model: p for p in ok_preds}
        maes = [s.mae for s in scores.values()
                if s.samples > 0 and math.isfinite(s.mae)]
        auto_mae = float(np.median(maes)) * 2.0 if maes else None
        ceiling = self.max_mae or auto_mae

        for name, s in scores.items():
            if name not in by_name:
                s.reason = "no OK prediction this cycle"
                continue
            if s.samples < self.min_samples:
                s.reason = f"insufficient OOS evidence ({s.samples}<{self.min_samples})"
                continue
            if ceiling is not None and s.mae > ceiling:
                s.reason = f"MAE {s.mae:.6f} above ceiling {ceiling:.6f}"
                continue
            if s.degradation > self.max_degradation:
                s.reason = f"degrading (x{s.degradation})"
                continue
            s.eligible = True
            s.reason = "eligible"

        # latency from this cycle's predictions
        for name, s in scores.items():
            if name in by_name and by_name[name].latency_ms:
                s.latency_ms = by_name[name].latency_ms
            if s.latency_ms > self.max_latency_ms:
                s.eligible = False
                s.reason = f"latency {s.latency_ms:.0f}ms"

        eligible = [s for s in scores.values() if s.eligible]
        eligible.sort(key=lambda s: s.mae)            # lower OOS error first
        eligible = eligible[:max_models]

        # inverse-MAE weighting, shrunk by the model's own uncertainty
        raw: Dict[str, float] = {}
        for s in eligible:
            pred = by_name[s.model]
            w = 1.0 / max(s.mae, 1e-12)
            unc = pred.uncertainty
            if unc is not None and math.isfinite(unc) and unc > 0:
                w /= (1.0 + unc)                      # uncertainty shrinkage
            # high-volatility regime: penalize models with growing error
            if volatility_percentile > 0.8:
                w /= max(s.degradation, 0.5)
            raw[s.model] = w
        total = sum(raw.values())
        for s in eligible:
            s.weight = raw.get(s.model, 0.0) / total if total > 0 else 0.0
        return eligible


class PerformanceEnsemble:
    """Weighted ensemble over selector-approved models.

    Weights come exclusively from ModelSelector (measured OOS evidence +
    the models' own uncertainty).  If nothing is eligible the ensemble
    abstains (status NOT_AVAILABLE) - fail-safe default.
    """

    def combine(self, predictions: List[ModelPrediction], symbol: str,
                last_price: float, selector: ModelSelector,
                volatility_percentile: float = 0.5) -> ModelPrediction:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        tf = predictions[0].timeframe if predictions else "M5"
        base = ModelPrediction(model="ensemble", symbol=symbol,
                               timeframe=tf, timestamp=now)
        eligible = selector.select(predictions, symbol,
                                   volatility_percentile=volatility_percentile)
        if not eligible:
            base.status = PredictionStatus.MODEL_UNAVAILABLE
            base.detail = "no eligible models (insufficient measured evidence)"
            return base

        by_name = {p.model: p for p in predictions}
        wsum = ret_acc = unc_acc = 0.0
        members: List[dict] = []
        for s in eligible:
            p = by_name[s.model]
            ret_acc += s.weight * (p.forecast_return or 0.0)
            if p.uncertainty is not None and math.isfinite(p.uncertainty):
                unc_acc += s.weight * p.uncertainty
            wsum += s.weight
            members.append({"model": s.model, "weight": round(s.weight, 4),
                            "forecast_return": p.forecast_return,
                            "uncertainty": p.uncertainty,
                            "mae": round(s.mae, 6), "samples": s.samples})
        ens_ret = ret_acc / wsum if wsum > 0 else 0.0
        band = 0.00025
        base.forecast_return = ens_ret
        base.forecast_price = last_price * (1.0 + ens_ret)
        base.direction = (Direction.UP if ens_ret > band
                          else Direction.DOWN if ens_ret < -band else Direction.FLAT)
        base.uncertainty = unc_acc / wsum if wsum > 0 else None
        base.probability_up = None      # never fabricated
        base.probability_down = None
        base.status = PredictionStatus.OK
        base.raw = {"members": members,
                    "method": "inverse-MAE weighted, uncertainty-shrunk",
                    "n_eligible": len(eligible)}
        return base

