"""AEGIS QUANT AI - end-to-end decision pipeline (Task 14) with fail-safe
defaults (Task 18).

Implemented execution flow (exactly what runs, no more, no less):

    MT5 market data (caller supplies the OHLCV DataFrame)
        -> Feature engine (QuantFactorEngine)
        -> Technical indicators (inside factors)
        -> Quant models (adapters, timeout-guarded)
        -> Regime (RegimeEngine)
        -> Volatility (VolatilityEngine)
        -> Anomaly detection (AnomalyDetector)
        -> Model selection (ModelSelector - measured OOS evidence only)
        -> Ensemble (PerformanceEnsemble)
        -> Optional FREE local LLM (OllamaReasoner - advisory text only)
        -> Signal
        -> RiskManager
        -> Position sizing
        -> ExecutionValidator  (error-10016 / INVALID_VOLUME guards)
        -> DemoGuard (DEMO only)
        -> MT5 DEMO  (the caller performs order_send; this module NEVER does)

Every failure path (AI/model/DB/MT5/API/LLM/NaN/invalid risk) resolves to
HOLD.  The pipeline never raises and never returns an executable order when
any guard fails.
"""
from __future__ import annotations

import logging
import math
import traceback
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from quant_ai.config import QAIConfig
from quant_ai.ensemble.ensemble import ModelSelector, PerformanceEnsemble
from quant_ai.execution.demo_guard import DemoGuard
from quant_ai.execution.validator import ExecutionValidator, OrderSpec
from quant_ai.performance import ModelCache, PerformanceTracker, run_with_timeout, ModelTimeout
from quant_ai.predictions import Direction, ExecutionDecision, ModelPrediction, PredictionStatus
from quant_ai.quant.anomaly import AnomalyDetector
from quant_ai.quant.factors import QuantFactorEngine
from quant_ai.quant.regime import RegimeEngine
from quant_ai.quant.volatility import VolatilityEngine
from quant_ai.risk.risk_engine import RiskManager
from quant_ai.storage.db import QuantAIStore

logger = logging.getLogger("quant_ai.pipeline")

# symbol family helpers ------------------------------------------------------
FX_SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD")
GOLD_SYMBOLS = ("XAUUSD", "GOLD")


def _is_fx(symbol: str) -> bool:
    s = symbol.upper().replace("/", "")
    return any(f in s for f in FX_SYMBOLS)


def _is_gold(symbol: str) -> bool:
    s = symbol.upper().replace("/", "")
    return any(g in s for g in GOLD_SYMBOLS)


def symbol_profile(symbol: str) -> dict:
    """Broker-style contract profile used for sizing/validation defaults."""
    if _is_gold(symbol):
        return {"point": 0.01, "digits": 2, "point_value_per_lot": 1.0,
                "spread_points": 5.0, "min_sl_points": 60, "max_sl_points": 1200}
    return {"point": 0.00001, "digits": 5, "point_value_per_lot": 1.0,
            "spread_points": 1.2, "min_sl_points": 40, "max_sl_points": 800}


class QuantAIPipeline:
    """Deterministic, fail-safe orchestration of the quant-AI stack."""

    def __init__(self, config: Optional[QAIConfig] = None,
                 store: Optional[QuantAIStore] = None,
                 cache: Optional[ModelCache] = None,
                 llm=None, tracker: Optional[PerformanceTracker] = None,
                 device: Optional[str] = None):
        self.cfg = config or QAIConfig()
        self.store = store
        self.tracker = tracker or PerformanceTracker()
        self.cache = cache or ModelCache(max_models=self.cfg.max_models_in_memory,
                                         tracker=self.tracker)
        self.device = device
        self.llm = llm
        # independent engines (one per pipeline; all stateless per call)
        self.factors = QuantFactorEngine()
        self.vol_engine = VolatilityEngine()
        self.regime_engine = RegimeEngine()
        self.anomaly = AnomalyDetector()
        self.ensemble = PerformanceEnsemble()
        self.validator = ExecutionValidator()
        self.demo_guard = DemoGuard()

    # ── storage (lazy: DB failure must not break trading) ──────────────
    def _store(self) -> Optional[QuantAIStore]:
        if self.store is None:
            try:
                self.store = QuantAIStore()
            except Exception as exc:
                logger.error("storage init failed (continuing without DB): %s", exc)
                self.store = None
        return self.store

    # ── model construction ─────────────────────────────────────────────
    def build_models(self, symbol: str, timeframe: str) -> List:
        """Instantiate the configured adapters valid for `symbol`.

        Symbol-incompatible models are skipped (a gold model is never asked
        to forecast EURUSD).
        """
        from quant_ai.models.baselines import all_baselines
        models: List = list(all_baselines(symbol=symbol, timeframe=timeframe))
        en = self.cfg.model_enable
        gold, fx = _is_gold(symbol), _is_fx(symbol)

        if en.get("kronos_small") or en.get("kronos_mini") or en.get("kronos_base"):
            from quant_ai.models.kronos_adapter import KronosAdapter
            for key in ("kronos_small", "kronos_mini", "kronos_base"):
                if en.get(key):
                    models.append(KronosAdapter(model_key=key, symbol=symbol,
                                                timeframe=timeframe, device=self.device))
        if en.get("chronos2"):
            from quant_ai.models.chronos_adapter import ChronosAdapter
            models.append(ChronosAdapter(checkpoint="chronos2", symbol=symbol,
                                         timeframe=timeframe, device=self.device))
        if en.get("moirai"):
            from quant_ai.models.moirai_adapter import MoiraiAdapter
            models.append(MoiraiAdapter(symbol=symbol, timeframe=timeframe,
                                        device=self.device))
        if en.get("timesfm"):
            from quant_ai.models.timesfm_adapter import TimesFMAdapter
            models.append(TimesFMAdapter(symbol=symbol, timeframe=timeframe,
                                         device=self.device))
        if en.get("omega_forex_v3") and fx:
            from quant_ai.models.omega_adapter import OmegaForexAdapter
            models.append(OmegaForexAdapter(symbol=symbol, timeframe=timeframe,
                                            device=self.device))
        if en.get("eurusd_lgb_xgb") and "EURUSD" in symbol.upper():
            from quant_ai.models.eurusd_adapter import EURUSDEnsembleAdapter
            models.append(EURUSDEnsembleAdapter(symbol=symbol, timeframe=timeframe,
                                                device=self.device))
        if en.get("xauusd_smc_xgb") and gold:
            from quant_ai.models.xauusd_adapter import XAUUSD_SMC_Adapter
            models.append(XAUUSD_SMC_Adapter(symbol=symbol, timeframe=timeframe,
                                             device=self.device))
        if en.get("patchtst"):
            from quant_ai.models.patchtst_adapter import PatchTSTAdapter
            models.append(PatchTSTAdapter(symbol=symbol, timeframe=timeframe,
                                          device=self.device))
        return models

    # ── per-model timed prediction ─────────────────────────────────────
    def _predict_all(self, models: List, df: pd.DataFrame, horizon: int,
                     symbol: str, timeframe: str) -> List[ModelPrediction]:
        preds: List[ModelPrediction] = []
        timeout = float(self.cfg.model_timeout_sec)
        for m in models:
            name = getattr(m, "name", type(m).__name__)
            try:
                if not getattr(m, "is_loaded", False):
                    m.load()
            except Exception as exc:
                logger.warning("[pipeline] %s load failed: %s", name, exc)
            try:
                p = run_with_timeout(m.predict, timeout, df, horizon)
                self.tracker.record_call(name, getattr(p, "latency_ms", 0.0) or 0.0)
            except ModelTimeout:
                self.tracker.record_call(name, timeout * 1000.0, timeout=True)
                p = ModelPrediction(model=name, symbol=symbol, timeframe=timeframe,
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    status=PredictionStatus.TIMEOUT,
                                    detail=f"exceeded {timeout:.0f}s")
            except Exception as exc:
                self.tracker.record_call(name, 0.0, error=True)
                logger.warning("[pipeline] %s predict failed: %s", name, exc)
                p = ModelPrediction(model=name, symbol=symbol, timeframe=timeframe,
                                    timestamp=datetime.now(timezone.utc).isoformat(),
                                    status=PredictionStatus.INFERENCE_ERROR,
                                    detail=str(exc))
            preds.append(p)
        return preds

    # ── fail-safe HOLD factory ─────────────────────────────────────────
    def _hold(self, symbol: str, timeframe: str, reason: str,
              **extra) -> ExecutionDecision:
        now = datetime.now(timezone.utc).isoformat()
        d = ExecutionDecision(action="HOLD", symbol=symbol, timeframe=timeframe,
                              timestamp=now, reason=reason)
        for k, v in extra.items():
            setattr(d, k, v)
        return d

    # ── main entry point ───────────────────────────────────────────────
    def decide(self, df: pd.DataFrame, symbol: str = "XAUUSD",
               timeframe: str = "M5", horizon: Optional[int] = None,
               *, equity: float = 10_000.0, spread_pts: float = 0.0,
               session: str = "LONDON", headlines: Optional[List[str]] = None,
               models: Optional[List] = None,
               min_models_required: int = 0) -> ExecutionDecision:
        """Produce an auditable decision. NEVER raises; never returns a signal
        that has not passed every guard.  Returns HOLD on any failure."""
        horizon = int(horizon or self.cfg.forecast_horizon.get(timeframe, 12))
        try:
            d = self._decide_inner(
                df, symbol, timeframe, horizon, equity=equity,
                spread_pts=spread_pts, session=session, headlines=headlines,
                models=models, min_models_required=min_models_required)
        except Exception as exc:                     # Task 18: absolute fail-safe
            logger.error("pipeline exception -> HOLD: %s\n%s", exc,
                         traceback.format_exc())
            d = self._hold(symbol, timeframe, f"pipeline exception: {exc}")
        # Task 15: EVERY decision is persisted, including early HOLDs.
        self._store_decision(d)
        return d

    def _decide_inner(self, df, symbol, timeframe, horizon, *, equity,
                      spread_pts, session, headlines, models,
                      min_models_required) -> ExecutionDecision:
        now = datetime.now(timezone.utc).isoformat()
        prof = symbol_profile(symbol)

        # ── 0. input guard ─────────────────────────────────────────────
        if df is None or len(df) < 60:
            return self._hold(symbol, timeframe, "missing/insufficient market data")
        need = ["open", "high", "low", "close"]
        if any(c not in df.columns for c in need):
            return self._hold(symbol, timeframe, "market data missing OHLC columns")
        if not np.isfinite(df[need].astype(float).values).all():
            return self._hold(symbol, timeframe, "market data contains NaN/Inf")

        # ── 1. features / volatility / regime ──────────────────────────
        features = {}
        try:
            features = self.factors.latest(df, spread_pts=spread_pts,
                                           point=prof["point"])
        except Exception as exc:
            logger.warning("factor engine failed: %s", exc)

        vol = {}
        try:
            vol = self.vol_engine.analyze(df, horizon=horizon)
        except Exception as exc:
            logger.warning("volatility engine failed: %s", exc)

        vol_pct = float(vol.get("vol_percentile", 0.5) or 0.5)
        regime_rep = None
        regime = "UNCERTAIN"
        try:
            regime_rep = self.regime_engine.detect(df, vol_percentile=vol_pct)
            regime = regime_rep.regime
        except Exception as exc:
            logger.warning("regime engine failed: %s", exc)

        # ── 2. anomaly detection (can only BLOCK) ──────────────────────
        anomaly = {}
        try:
            anomaly = self.anomaly.detect(df, spread_pts=spread_pts,
                                          vol_percentile=vol_pct)
        except Exception as exc:
            logger.warning("anomaly engine failed: %s", exc)
            anomaly = {"block": False, "checks": {"engine": {"ok": True}}}

        store = self._store()
        if store is not None and regime_rep is not None:
            try:
                store.record_regime(
                    ts=now, symbol=symbol, timeframe=timeframe, regime=regime,
                    trend_strength=float(getattr(regime_rep, "trend_strength", 0.0) or 0.0),
                    vol_percentile=vol_pct,
                    autocorr=float(getattr(regime_rep, "autocorr", 0.0) or 0.0),
                    reasons=list(getattr(regime_rep, "reasons", []) or []))
            except Exception as exc:
                logger.warning("store.record_regime failed: %s", exc)

        if anomaly.get("block"):
            bad = [k for k, v in anomaly.get("checks", {}).items()
                   if not v.get("ok")]
            return self._hold(symbol, timeframe, f"anomaly block: {bad}",
                              regime=regime, volatility=vol, anomaly=anomaly)

        # ── 3. models (timeout-guarded, never fatal) ───────────────────
        model_list = models if models is not None else self.build_models(symbol, timeframe)
        preds = self._predict_all(model_list, df, horizon, symbol, timeframe)
        ok_preds = [p for p in preds if p.status == PredictionStatus.OK]
        preds_map = {p.model: p.to_dict() for p in preds}

        store = self._store()
        if store is not None:
            for p in preds:
                try:
                    store.record_prediction(p.to_dict())
                except Exception:
                    pass

        if len(ok_preds) < min_models_required:
            return self._hold(
                symbol, timeframe,
                f"only {len(ok_preds)} usable prediction(s) "
                f"(< required {min_models_required})",
                predictions=preds_map, regime=regime, volatility=vol,
                anomaly=anomaly)

        # ── 4. model selection + ensemble (measured evidence only) ─────
        last_price = float(df["close"].iloc[-1])
        ens = self.ensemble.combine(ok_preds, symbol, last_price,
                                    selector=ModelSelector(store) if store else
                                    ModelSelector(_NullStore()),
                                    volatility_percentile=vol_pct)
        members = ens.raw.get("members", []) if isinstance(ens.raw, dict) else []

        if ens.status != PredictionStatus.OK or ens.direction == Direction.UNKNOWN:
            return self._hold(symbol, timeframe,
                              f"ensemble abstained ({ens.status.value}: {ens.detail})",
                              predictions=preds_map, regime=regime,
                              volatility=vol, anomaly=anomaly)

        direction = ens.direction.value          # UP | DOWN | FLAT
        if direction == "FLAT":
            return self._hold(symbol, timeframe, "ensemble flat (edge below band)",
                              predictions=preds_map, regime=regime,
                              volatility=vol, anomaly=anomaly)

        # ── 5. optional FREE local LLM (advisory text ONLY) ────────────
        llm_reason = None
        if self.llm is not None:
            try:
                llm_reason = self.llm.reason(
                    symbol=symbol, timeframe=timeframe, regime=regime,
                    volatility=vol, signal_direction=direction,
                    ensemble_summary={"members": members,
                                      "forecast_return": ens.forecast_return},
                    risk_summary="pre-risk (advisory text cannot alter the signal)")
            except Exception as exc:
                logger.info("LLM advisory skipped (fail-safe): %s", exc)
                llm_reason = None

        # ── 6. risk engine (independent, always authoritative) ─────────
        risk = RiskManager(self.cfg)
        risk.roll_daily(equity)
        atr_pts = float(vol.get("atr_points_20", 0.0) or 0.0)
        sl_pts = int(max(prof["min_sl_points"],
                         min(prof["max_sl_points"], atr_pts * 1.5
                             if atr_pts else prof["min_sl_points"] * 2)))
        tp_pts = int(sl_pts * 1.5)
        risk_decision = risk.evaluate(
            symbol=symbol, direction=direction, equity=equity,
            spread_pts=spread_pts, point=prof["point"],
            point_value_per_lot=prof["point_value_per_lot"],
            atr_points=atr_pts, vol_ratio=float(vol.get("vol_ratio", 1.0) or 1.0),
            vol_percentile=vol_pct, session=session,
            sl_points=sl_pts, min_sl=prof["min_sl_points"],
            max_sl=prof["max_sl_points"], tp_points=tp_pts)

        if not risk_decision.allowed:
            d = self._hold(symbol, timeframe, f"risk rejected: {risk_decision.reason}",
                           predictions=preds_map, regime=regime, volatility=vol,
                           anomaly=anomaly, risk=risk_decision.to_dict())
            d.ensemble_direction = direction
            return d

        # ── 7. position sizing + order spec ────────────────────────────
        side = "BUY" if direction == "UP" else "SELL"
        lot = float(risk_decision.lot_size or 0.0)
        if not math.isfinite(lot) or lot <= 0:
            d = self._hold(symbol, timeframe, "non-positive/invalid lot size",
                           predictions=preds_map, regime=regime, volatility=vol,
                           anomaly=anomaly, risk=risk_decision.to_dict())
            d.ensemble_direction = direction
            return d

        entry = float(df["close"].iloc[-1])
        sl = risk_decision.sl_points
        tp = risk_decision.tp_points
        if side == "BUY":
            sl_price = entry - sl * prof["point"]
            tp_price = entry + tp * prof["point"]
        else:
            sl_price = entry + sl * prof["point"]
            tp_price = entry - tp * prof["point"]

        spec = OrderSpec(
            symbol=symbol, side=side, entry=round(entry, prof["digits"]),
            sl=round(sl_price, prof["digits"]), tp=round(tp_price, prof["digits"]),
            volume=lot, point=prof["point"], digits=prof["digits"],
            volume_min=0.01, volume_max=100.0, volume_step=0.01)
        validation = self.validator.validate(spec)
        if not validation["ok"]:
            d = self._hold(symbol, timeframe,
                           "execution validation failed: " +
                           "; ".join(validation["errors"]),
                           predictions=preds_map, regime=regime, volatility=vol,
                           anomaly=anomaly, risk=risk_decision.to_dict(),
                           validation=validation)
            d.ensemble_direction = direction
            return d

        # ── 8. demo guard (absolute, cannot be bypassed) ───────────────
        guard = self.demo_guard.check()
        if not guard["ok"]:
            d = self._hold(symbol, timeframe, f"demo guard blocked: {guard['reason']}",
                           predictions=preds_map, regime=regime, volatility=vol,
                           anomaly=anomaly, risk=risk_decision.to_dict(),
                           validation=validation, demo_guard=guard)
            d.ensemble_direction = direction
            return d

        # ── 9. final auditable decision (signal is generated, NOT sent) ─
        d = ExecutionDecision(
            action=side, symbol=symbol, timeframe=timeframe, timestamp=now,
            reason=(f"ensemble {direction} (w={ens.forecast_return:.6f}, "
                    f"unc={ens.uncertainty}, regime={regime}, vol_pct={vol_pct:.2f})"),
            predictions=preds_map, regime=regime, volatility=vol, anomaly=anomaly,
            risk=risk_decision.to_dict(),
            position={"lot": validation["normalized_volume"],
                      "entry": round(entry, prof["digits"]),
                      "sl": validation["normalized_sl"],
                      "tp": validation["normalized_tp"],
                      "sl_points": validation["sl_pts"],
                      "tp_points": validation["tp_pts"]},
            validation=validation, demo_guard=guard)
        if llm_reason is not None:
            d.reason_llm = {"model": llm_reason.model,
                            "reasoning": llm_reason.reasoning,
                            "risk_notes": llm_reason.risk_notes}
        d.ensemble_direction = direction
        return d

    # ── decision persistence (Task 15) ─────────────────────────────────
    def _store_decision(self, d: ExecutionDecision,
                        direction_hint: Optional[str] = None) -> None:
        store = self._store()
        if store is None:
            return
        try:
            rec = d.to_dict()
            hint = direction_hint or getattr(d, "ensemble_direction", "") or ""
            rec["ensemble_direction"] = hint
            if self.llm is not None:
                rec["llm_reasoning"] = getattr(d, "reason_llm", None)
            store.record_decision(ts=d.timestamp, action=d.action,
                                  symbol=d.symbol, timeframe=d.timeframe,
                                  record=rec)
        except Exception as exc:
            logger.warning("decision persistence failed (non-fatal): %s", exc)

    # ── introspection ──────────────────────────────────────────────────
    def health(self) -> dict:
        return {
            "models_in_memory": self.cache.memory_report(),
            "timings": self.tracker.report(),
            "llm_enabled": self.llm is not None,
            "demo_guard": self.demo_guard.check(),
        }


class _NullStore:
    """Stand-in when storage is unavailable: selector finds no evidence, so
    the ensemble abstains rather than trusting an unmeasured model."""

    def recent_forecast_errors(self, symbol: str, limit: int = 2000) -> list:
        return []





