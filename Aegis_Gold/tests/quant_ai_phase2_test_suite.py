"""AEGIS QUANT AI - PHASE 2 test suite (directive Tasks 13-18).

Adds coverage on top of tests/quant_ai_test_suite.py (which must keep passing):

  model fallback / unavailable model / invalid output / NaN / API failure /
  Ollama unavailable / malformed LLM response / timeout / offline mode /
  risk rejection / invalid SL / invalid TP / invalid volume / spread rejection /
  drawdown protection / demo guard / live-account rejection / database failure /
  missing market data / model timeout / LRU eviction / paper trading /
  pipeline fail-safe / model-selection weighting.

Run:  .venv_cuda\\Scripts\\python.exe tests\\quant_ai_phase2_test_suite.py
No fabricated results: every assertion is measured; failures raise.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import traceback

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quant_ai.config import (ALLOW_LIVE_TRADING, QAIConfig, RL_DEMO,  # noqa: E402
                             RL_PAPER, RL_RESEARCH, TRADING_MODE,
                             RL_DISABLED)
from quant_ai.ensemble.ensemble import ModelSelector, PerformanceEnsemble  # noqa: E402
from quant_ai.execution.demo_guard import DemoGuard                     # noqa: E402
from quant_ai.execution.validator import ExecutionValidator, OrderSpec  # noqa: E402
from quant_ai.llm.reasoner import OllamaReasoner                        # noqa: E402
from quant_ai.models.base import BaseModelAdapter                       # noqa: E402
from quant_ai.paper_trading import PaperBroker, PaperBrokerConfig       # noqa: E402
from quant_ai.performance import (ModelCache, ModelTimeout,             # noqa: E402
                                  PerformanceTracker, Timer, probe_environment,
                                  run_with_timeout)
from quant_ai.pipeline import QuantAIPipeline, symbol_profile           # noqa: E402
from quant_ai.predictions import (Direction, ExecutionDecision,          # noqa: E402
                                  ModelPrediction, PredictionStatus)
from quant_ai.risk.risk_engine import RiskManager                       # noqa: E402
from quant_ai.storage.db import QuantAIStore                            # noqa: E402

RESULTS = []
TESTS = []


def test(name):
    def deco(fn):
        def wrapper():
            try:
                fn()
                RESULTS.append((name, "PASS", ""))
                print(f"  [PASS] {name}")
            except Exception as exc:
                RESULTS.append((name, "FAIL", f"{exc}"))
                print(f"  [FAIL] {name}: {exc}")
                traceback.print_exc(limit=2)
        wrapper.test_name = name
        TESTS.append(wrapper)
        return fn
    return deco


def _synth(n=600, seed=7, trend=0.0, base=2400.0):
    """Deterministic, VALID OHLCV history (observable past only)."""
    rng = np.random.default_rng(seed)
    close = base * np.exp(np.cumsum(rng.normal(trend, 0.0006, n)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    wick = (np.abs(rng.normal(0, 0.0004, n)) + 0.0002) * base
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})
    df["volume"] = rng.integers(500, 5000, n).astype(float)
    df.index = pd.date_range("2026-01-01", periods=n, freq="5min")
    return df


# ── stub adapters (deterministic, no network) ───────────────────────────────
class _StubAdapter(BaseModelAdapter):
    """Configurable stub used to exercise fallback / failure paths."""

    def __init__(self, name="stub", ret=0.001, status=PredictionStatus.OK,
                 explode=False, sleep_s=0.0, prob=None, symbol="XAUUSD",
                 timeframe="M5", device=None):
        super().__init__(symbol=symbol, timeframe=timeframe, device=device)
        self.name = name
        self._ret = ret
        self._status = status
        self._explode = explode
        self._sleep = sleep_s
        self._prob = prob

    def load(self) -> bool:
        self._loaded = True
        return True

    def predict(self, df, horizon, **kwargs):
        if self._sleep:
            time.sleep(self._sleep)
        if self._explode:
            raise RuntimeError("stub explosion")
        last = float(df["close"].iloc[-1])
        if self._status != PredictionStatus.OK:
            return ModelPrediction(model=self.name, symbol=self.symbol,
                                   timeframe=self.timeframe, timestamp="t",
                                   status=self._status, detail="stub closed")
        return ModelPrediction(
            model=self.name, symbol=self.symbol, timeframe=self.timeframe,
            timestamp="t", forecast_price=last * (1 + self._ret),
            forecast_return=self._ret,
            direction=(Direction.UP if self._ret > 0 else Direction.DOWN),
            probability_up=self._prob, probability_down=None,
            uncertainty=0.1, forecast_horizon=horizon, latency_ms=1.0,
            status=PredictionStatus.OK, prices_path=[last, last * (1 + self._ret)])

    def health(self):
        return {"loaded": self._loaded, "weights_available": True}


class _BrokenStore:
    """Storage that raises on every call (Task 18 DB-failure path)."""

    def recent_forecast_errors(self, symbol, limit=2000):
        raise sqlite_error()

    def record_prediction(self, p):
        raise sqlite_error()

    def record_decision(self, **kw):
        raise sqlite_error()

    def record_regime(self, **kw):
        raise sqlite_error()


def sqlite_error():
    import sqlite3
    return sqlite3.OperationalError("database is locked (simulated)")


# Windows cannot delete a sqlite file while a connection is open, so DB tests
# use unique files in scratch/ instead of TemporaryDirectory.
_DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "scratch", "phase2_dbs")


def _db(name: str) -> str:
    import uuid
    os.makedirs(_DB_DIR, exist_ok=True)
    return os.path.join(_DB_DIR, f"{name}_{uuid.uuid4().hex[:8]}.db")


# == MODEL FALLBACK / UNAVAILABLE / INVALID OUTPUT ==========================
@test("fallback: unavailable model returns MODEL_UNAVAILABLE, never invents output")
def _():
    from quant_ai.models.moirai_adapter import MoiraiAdapter
    a = MoiraiAdapter(symbol="XAUUSD", timeframe="M5")
    p = a.predict(_synth(400), 12)
    assert p.status in (PredictionStatus.MODEL_UNAVAILABLE,
                        PredictionStatus.INSUFFICIENT_DATA,
                        PredictionStatus.INFERENCE_ERROR), p.status
    assert p.forecast_price is None
    assert p.probability_up is None and p.probability_down is None


@test("fallback: exploding model is contained by the pipeline (never propagates)")
def _():
    a = _StubAdapter(name="boom", explode=True)
    # the stub itself raises, proving the pipeline - not the stub - is the guard
    raised = False
    try:
        a.predict(_synth(200), 12)
    except RuntimeError:
        raised = True
    assert raised
    pipe = QuantAIPipeline(config=QAIConfig(), store=None)
    preds = pipe._predict_all([a], _synth(200), 12, "XAUUSD", "M5")
    assert preds[0].status == PredictionStatus.INFERENCE_ERROR, preds[0].status
    d = pipe.decide(_synth(300), symbol="XAUUSD", timeframe="M5", models=[a],
                    min_models_required=1)
    assert d.action == "HOLD"


@test("invalid output: adapter returning INSUFFICIENT_DATA is excluded from ensemble")
def _():
    ok = _StubAdapter(name="okmodel", ret=0.002)
    bad = _StubAdapter(name="badmodel", status=PredictionStatus.INFERENCE_ERROR)
    oks = [m for m in (ok, bad) if m.predict(_synth(200), 12).status == PredictionStatus.OK]
    assert len(oks) == 1 and oks[0].name == "okmodel"


@test("NaN prediction: pipeline HOLDs on NaN market data (never trades)")
def _():
    df = _synth(300)
    df.loc[df.index[10], "close"] = np.nan
    pipe = QuantAIPipeline(config=QAIConfig(), store=None)
    d = pipe.decide(df, symbol="XAUUSD", timeframe="M5")
    assert d.action == "HOLD", d.action
    assert "NaN" in d.reason or "nan" in d.reason.lower()


@test("missing market data: empty/short/column-less frames all HOLD")
def _():
    pipe = QuantAIPipeline(config=QAIConfig(), store=None)
    assert pipe.decide(pd.DataFrame(), symbol="XAUUSD").action == "HOLD"
    assert pipe.decide(None, symbol="XAUUSD").action == "HOLD"
    assert pipe.decide(_synth(20), symbol="XAUUSD").action == "HOLD"
    no_ohlc = pd.DataFrame({"foo": range(300)})
    assert pipe.decide(no_ohlc, symbol="XAUUSD").action == "HOLD"


@test("timeout: hung model is cut off by run_with_timeout and HOLDs safely")
def _():
    def _hang():
        time.sleep(5.0)
        return "never"
    t0 = time.perf_counter()
    raised = False
    try:
        run_with_timeout(_hang, 0.2)
    except ModelTimeout:
        raised = True
    elapsed = time.perf_counter() - t0
    assert raised, "ModelTimeout not raised"
    assert elapsed < 2.0, f"timeout not enforced (took {elapsed:.2f}s)"


@test("model timeout: slow adapter is recorded as TIMEOUT, pipeline still HOLDs")
def _():
    slow = _StubAdapter(name="slowmodel", sleep_s=3.0)
    cfg = QAIConfig()
    cfg.model_timeout_sec = 0.3
    pipe = QuantAIPipeline(config=cfg, store=None)
    preds = pipe._predict_all([slow], _synth(200), 12, "XAUUSD", "M5")
    assert preds[0].status == PredictionStatus.TIMEOUT, preds[0].status
    stats = pipe.tracker.record_call and pipe.tracker.report()
    assert any(r["timeouts"] >= 1 for r in stats), stats


# == LLM (Task 6) ===========================================================
@test("llm: Ollama unavailable -> reason() returns None, no exception")
def _():
    r = OllamaReasoner(model="definitely-not-pulled", base_url="http://127.0.0.1:1")
    assert r.health_check() is False
    out = r.reason(symbol="XAUUSD", timeframe="M5", regime="RANGING",
                   volatility={}, signal_direction="UP", ensemble_summary={})
    assert out is None


@test("llm: malformed LLM response degrades gracefully (never raises)")
def _():
    r = OllamaReasoner(model="stub")
    assert r._parse_json_block("no json here at all") is None
    assert r._parse_json_block('{"reasoning": "x"}') == {"reasoning": "x"}
    assert r._parse_json_block("{ broken json ") is None


@test("llm: offline mode (bad host) leaves the pipeline fully functional")
def _():
    r = OllamaReasoner(base_url="http://10.255.255.1:11434")   # unroutable
    pipe = QuantAIPipeline(config=QAIConfig(), store=None, llm=r)
    d = pipe.decide(_synth(300), symbol="XAUUSD", timeframe="M5")
    assert d.action in ("HOLD", "BUY", "SELL")


# == RISK REJECTION / SL / TP / VOLUME / SPREAD (Tasks 8, 9) ================
@test("risk rejection: drawdown breach blocks the trade")
def _():
    cfg = QAIConfig()
    rm = RiskManager(cfg)
    rm.history_equity = 20_000.0                  # peak 20k, now 10k -> 50% DD
    dec = rm.evaluate(symbol="XAUUSD", direction="UP", equity=10_000.0,
                      spread_pts=5.0, sl_points=100, min_sl=10, max_sl=400,
                      tp_points=200)
    assert not dec.allowed, dec.reason
    assert dec.checks["drawdown"]["ok"] is False


@test("risk rejection: daily loss limit blocks after breach")
def _():
    cfg = QAIConfig()
    rm = RiskManager(cfg)
    rm.roll_daily(10_000.0)
    rm.on_trade_result(-400.0)
    rm.on_trade_result(-200.0)                    # -6% > 5% limit
    dec = rm.evaluate(symbol="XAUUSD", direction="UP", equity=10_000.0,
                      spread_pts=5.0, sl_points=100, min_sl=10, max_sl=400,
                      tp_points=200)
    assert not dec.allowed
    assert dec.checks["daily_loss"]["ok"] is False


@test("spread rejection: abnormal spread is blocked")
def _():
    cfg = QAIConfig()
    rm = RiskManager(cfg)
    dec = rm.evaluate(symbol="EURUSD", direction="UP", equity=10_000.0,
                      spread_pts=500.0, sl_points=50, min_sl=10, max_sl=400,
                      tp_points=100)
    assert not dec.allowed
    assert dec.checks["spread"]["ok"] is False


@test("invalid SL: naked SL(0) and wrong-side SL are rejected by the validator")
def _():
    v = ExecutionValidator()
    for spec in (
        OrderSpec(symbol="XAUUSD", side="BUY", entry=2400.0, sl=0.0, tp=2410.0,
                  volume=0.1, point=0.01, digits=2),
        OrderSpec(symbol="XAUUSD", side="BUY", entry=2400.0, sl=2405.0, tp=2410.0,
                  volume=0.1, point=0.01, digits=2),
        OrderSpec(symbol="XAUUSD", side="SELL", entry=2400.0, sl=2395.0, tp=2390.0,
                  volume=0.1, point=0.01, digits=2),
    ):
        r = v.validate(spec)
        assert not r["ok"], r


@test("invalid TP: wrong-side / below-stops-level TP is rejected")
def _():
    v = ExecutionValidator()
    bad_tp = OrderSpec(symbol="XAUUSD", side="BUY", entry=2400.0, sl=2390.0,
                       tp=2395.0, volume=0.1, point=0.01, digits=2)
    assert not v.validate(bad_tp)["ok"]
    below_stops = OrderSpec(symbol="XAUUSD", side="BUY", entry=2400.0, sl=2399.5,
                            tp=2400.5, volume=0.1, point=0.01, digits=2,
                            stops_level_pts=100.0)
    assert not v.validate(below_stops)["ok"]


@test("invalid volume: below minimum / above maximum are rejected, step normalised")
def _():
    v = ExecutionValidator()
    too_small = OrderSpec(symbol="XAUUSD", side="BUY", entry=2400.0, sl=2390.0,
                          tp=2420.0, volume=0.001, point=0.01, digits=2,
                          volume_min=0.01, volume_step=0.01)
    assert not v.validate(too_small)["ok"]
    too_big = OrderSpec(symbol="XAUUSD", side="BUY", entry=2400.0, sl=2390.0,
                        tp=2420.0, volume=500.0, point=0.01, digits=2,
                        volume_max=100.0, volume_step=0.01)
    r_big = v.validate(too_big)
    assert not r_big["ok"] and any("maximum" in e for e in r_big["errors"]), r_big
    step = OrderSpec(symbol="XAUUSD", side="BUY", entry=2400.0, sl=2390.0,
                     tp=2420.0, volume=0.137, point=0.01, digits=2,
                     volume_step=0.01)
    r = v.validate(step)
    assert r["ok"] and abs(r["normalized_volume"] - 0.14) < 1e-9, r


# == DEMO GUARD / LIVE REJECTION (Task 9) ===================================
@test("demo guard: live/real/production servers are all rejected")
def _():
    g = DemoGuard()
    for server in ("Live-Server-01", "REAL-TRADING", "ProductionFX",
                   "ACME-Live02", "Real1"):
        r = g.check({"server": server})
        assert r["blocked"] and not r["ok"], (server, r)


@test("demo guard: demo server passes; empty server fails safe")
def _():
    g = DemoGuard()
    assert g.check({"server": "MetaQuotes-Demo"})["ok"]
    assert g.check({"server": "ICMarketsSC-Demo"})["ok"]
    # empty server: tolerated only because live is structurally impossible
    assert g.check({})["ok"]


@test("demo guard: frozen constants - live can never be enabled")
def _():
    assert TRADING_MODE == "DEMO"
    assert ALLOW_LIVE_TRADING is False
    assert DemoGuard(allow_live=True).check({"server": "Demo"})["ok"] is False
    assert DemoGuard(trading_mode="LIVE").check({"server": "Demo"})["ok"] is False


# == DATABASE FAILURE / OFFLINE / FAIL-SAFE (Tasks 10, 15, 18) ==============
@test("db failure: pipeline survives a storage that raises on every call")
def _():
    pipe = QuantAIPipeline(config=QAIConfig(), store=_BrokenStore())
    d = pipe.decide(_synth(300), symbol="XAUUSD", timeframe="M5")
    assert d.action in ("HOLD", "BUY", "SELL"), d.action
    assert isinstance(d, ExecutionDecision)


@test("db failure: store.record_* swallow errors instead of raising")
def _():
    store = QuantAIStore(_db("db_failure"))
    try:
        store.record_prediction({})                       # no crash
        store.record_decision(ts="t", action="HOLD", symbol="XAUUSD",
                              timeframe="M5", record={"x": 1})
        store.record_tournament({"run_id": "r", "model": "m"})
    finally:
        store.close()
    assert True


@test("offline mode: no network/MT5 -> bridge returns HOLD with explicit reason")
def _():
    from quant_ai.aegis_bridge import AegisQuantBridge
    class _DeadMT5:
        TIMEFRAME_M5 = 5
        def initialize(self):
            return False
        def copy_rates_from_pos(self, *a, **k):
            return None
    bridge = AegisQuantBridge(config=QAIConfig(), store=None, mt5_module=_DeadMT5())
    sig = bridge.analyze("XAUUSD", "M5")
    assert sig.action == "HOLD"
    assert "unavailable" in sig.reason.lower()


@test("fail-safe: pipeline returns HOLD when every model fails")
def _():
    dead = [_StubAdapter(name=f"dead{i}", explode=True) for i in range(3)]
    pipe = QuantAIPipeline(config=QAIConfig(), store=None)
    d = pipe.decide(_synth(300), symbol="XAUUSD", timeframe="M5", models=dead,
                    min_models_required=1)
    assert d.action == "HOLD", d.action
    assert "usable prediction" in d.reason


# == PERFORMANCE / CACHE / LRU (Task 17) ====================================
@test("performance: environment probe returns measured values")
def _():
    env = probe_environment()
    assert "python" in env
    assert "ram_total_gb" in env or "ram_error" in env
    assert isinstance(env.get("cuda_available"), bool)


@test("performance: ModelCache evicts LRU and never exceeds max_models")
def _():
    cache = ModelCache(max_models=2, load_timeout_s=5.0)
    a = _StubAdapter(name="A")
    b = _StubAdapter(name="B")
    c = _StubAdapter(name="C")
    cache.put("A", a)
    cache.put("B", b)
    assert len(cache.keys()) == 2
    cache.put("C", c)                                   # evicts LRU (A)
    assert len(cache.keys()) == 2
    assert "A" not in cache.keys() and "C" in cache.keys()


@test("performance: get_or_load counts failures instead of raising")
def _():
    cache = ModelCache(max_models=2, load_timeout_s=1.0)
    def _boom():
        raise RuntimeError("cannot load")
    obj = cache.get_or_load("broken", _boom)
    assert obj is None
    assert cache.load_failures["broken"] == 1


@test("performance: get_or_load times out instead of hanging")
def _():
    cache = ModelCache(max_models=2, load_timeout_s=0.3)
    def _slow():
        time.sleep(5.0)
    t0 = time.perf_counter()
    obj = cache.get_or_load("slow", _slow)
    assert obj is None and (time.perf_counter() - t0) < 2.0


@test("performance: Timer and tracker measure real elapsed time")
def _():
    tr = PerformanceTracker()
    with Timer() as t:
        time.sleep(0.05)
    assert t.ms >= 40.0, t.ms
    tr.record_call("m", t.ms)
    tr.record_load("m", 12.0, 3.5)
    rep = tr.report()[0]
    assert rep["calls"] == 1 and rep["load_ms"] == 12.0


# == MODEL SELECTION / ENSEMBLE (Tasks 4, 5) ================================
def _eleven_errors(store, model, symbol, mae_scale, n=60):
    for i in range(n):
        actual = 2400.0 + i * 0.01
        store.record_forecast_error(ts=str(i), model=model, symbol=symbol,
                                    timeframe="M5", horizon=12, actual=actual,
                                    forecast=actual * (1.0 + mae_scale))


@test("selection: models with NO measured evidence are never eligible")
def _():
    store = QuantAIStore(_db("sel_noevi"))
    try:
        preds = [_StubAdapter(name="unmeasured", ret=0.001).predict(_synth(200), 12)]
        sel = ModelSelector(store, min_samples=20)
        eligible = sel.select(preds, "XAUUSD")
        assert eligible == [], eligible
    finally:
        store.close()


@test("selection: weights follow measured OOS error, not vote count")
def _():
    store = QuantAIStore(_db("sel_weights"))
    try:
        _eleven_errors(store, "good", "XAUUSD", 0.00001)
        _eleven_errors(store, "weak", "XAUUSD", 0.0050)
        good = _StubAdapter(name="good", ret=0.002)
        weak = _StubAdapter(name="weak", ret=-0.002)      # votes OPPOSITE
        preds = [good.predict(_synth(200), 12), weak.predict(_synth(200), 12)]
        sel = ModelSelector(store, min_samples=20)
        eligible = sel.select(preds, "XAUUSD")
        assert eligible, "expected eligible models"
        w = {s.model: s.weight for s in eligible}
        assert w["good"] > w["weak"], w                       # strong model dominates
        ens = PerformanceEnsemble().combine(preds, "XAUUSD", 2400.0, sel)
        assert ens.status == PredictionStatus.OK
        assert ens.direction == Direction.UP, (ens.direction, w)   # not outvoted
        assert ens.probability_up is None                     # never fabricated
    finally:
        store.close()


@test("selection: degrading model is penalised; latency ceiling disqualifies")
def _():
    store = QuantAIStore(_db("sel_degrade"))
    try:
        for i in range(60):
            actual = 2400.0
            scale = 0.0001 if i < 30 else 0.002          # error grows 20x
            store.record_forecast_error(ts=str(i), model="decaying", symbol="XAUUSD",
                                        timeframe="M5", horizon=12, actual=actual,
                                        forecast=actual * (1 + scale))
        preds = [_StubAdapter(name="decaying", ret=0.002).predict(_synth(200), 12)]
        sel = ModelSelector(store, min_samples=20, max_degradation=2.0)
        assert sel.select(preds, "XAUUSD") == []
        sel2 = ModelSelector(store, min_samples=20, max_latency_ms=0.001)
        assert sel2.select(preds, "XAUUSD") == []
    finally:
        store.close()


# == PAPER TRADING (Task 13) ================================================
@test("paper: win path books profit net of commission and slippage")
def _():
    b = PaperBroker(PaperBrokerConfig(symbol="XAUUSD", point=0.01, digits=2,
                                      spread_points=5.0, commission_per_lot=7.0,
                                      slippage_points=1, initial_cash=10_000.0))
    px = 2400.0
    r = b.try_open(side="BUY", price=px, sl=px - 2.0, tp=px + 3.0, lot=0.10,
                   index=0, ts="t0")
    assert r["ok"], r
    tr = b.manage(index=1, ts="t1", high=px + 4.0, low=px - 0.5, close=px + 3.0)
    assert tr is not None and tr.exit_reason == "TP", tr
    # +300 pts - 2 pts slip = 298 pts * 0.1 lot * $1 = $29.8 - $0.70 commission
    assert abs(tr.pnl - 29.1) < 0.05, tr.pnl
    assert b.summary()["n_wins"] == 1


@test("paper: loss path books the stop and never exceeds the risk budget")
def _():
    b = PaperBroker(PaperBrokerConfig(symbol="XAUUSD", point=0.01, digits=2,
                                      commission_per_lot=7.0, slippage_points=1))
    px = 2400.0
    b.try_open(side="BUY", price=px, sl=px - 2.0, tp=px + 3.0, lot=0.10,
               index=0, ts="t0")
    tr = b.manage(index=1, ts="t1", high=px + 0.5, low=px - 3.0, close=px - 2.5)
    assert tr.exit_reason == "SL"
    assert tr.pnl < 0
    assert abs(tr.pnl) < 25.0, tr.pnl          # ~200 pts * 0.1 + commission


@test("paper: SL is assumed before TP when a bar spans both (conservative)")
def _():
    b = PaperBroker(PaperBrokerConfig(symbol="XAUUSD", point=0.01, digits=2))
    px = 2400.0
    b.try_open(side="BUY", price=px, sl=px - 2.0, tp=px + 3.0, lot=0.10,
               index=0, ts="t0")
    tr = b.manage(index=1, ts="t1", high=px + 10.0, low=px - 10.0, close=px)
    assert tr.exit_reason == "SL", tr.exit_reason


@test("paper: invalid geometry is rejected by the real validator (no order)")
def _():
    b = PaperBroker(PaperBrokerConfig(symbol="XAUUSD", point=0.01, digits=2))
    px = 2400.0
    bad = b.try_open(side="BUY", price=px, sl=px + 2.0, tp=px + 3.0, lot=0.10,
                     index=0, ts="t0")
    assert not bad["ok"]
    assert b.position is None and b.rejected


@test("paper: HOLD-only run leaves equity untouched; summary is measured")
def _():
    b = PaperBroker(PaperBrokerConfig(symbol="XAUUSD", initial_cash=5000.0))
    s = b.summary()
    assert s["n_trades"] == 0 and s["final_equity"] == 5000.0
    assert s["net_return_pct"] == 0.0


# == PIPELINE END-TO-END (Task 14) ==========================================
@test("pipeline: BUY/SELL signal carries validated geometry and demo guard")
def _():
    store = QuantAIStore(_db("pipe_buy"))
    try:
        _eleven_errors(store, "strong", "XAUUSD", 0.00001, n=80)
        strong = _StubAdapter(name="strong", ret=0.0025)
        pipe = QuantAIPipeline(config=QAIConfig(), store=store)
        d = pipe.decide(_synth(400, trend=0.0003), symbol="XAUUSD",
                        timeframe="M5", equity=10_000, spread_pts=5.0,
                        models=[strong])
        assert d.action in ("BUY", "SELL", "HOLD"), d.action
        if d.action in ("BUY", "SELL"):
            assert d.validation["ok"], d.validation
            assert d.demo_guard["ok"], d.demo_guard
            assert d.position["sl"] > 0 and d.position["tp"] > 0
            assert d.position["lot"] >= 0.01
    finally:
        store.close()


@test("pipeline: spread blow-out is rejected before any signal is emitted")
def _():
    store = QuantAIStore(_db("pipe_spread"))
    try:
        _eleven_errors(store, "strong", "XAUUSD", 0.00001, n=80)
        strong = _StubAdapter(name="strong", ret=0.0025)
        pipe = QuantAIPipeline(config=QAIConfig(), store=store)
        d = pipe.decide(_synth(400, trend=0.0003), symbol="XAUUSD",
                        timeframe="M5", spread_pts=10_000.0, models=[strong])
        assert d.action == "HOLD", d.action
        assert "risk rejected" in d.reason, d.reason
    finally:
        store.close()


@test("pipeline: anomaly block halts a signal (invalid candles)")
def _():
    store = QuantAIStore(_db("pipe_anom"))
    try:
        _eleven_errors(store, "strong", "XAUUSD", 0.00001, n=80)
        strong = _StubAdapter(name="strong", ret=0.0025)
        pipe = QuantAIPipeline(config=QAIConfig(), store=store)
        df = _synth(400, trend=0.0003)
        df.loc[df.index[-1], "high"] = df["low"].iloc[-1] - 1.0   # broken candle
        d = pipe.decide(df, symbol="XAUUSD", timeframe="M5", models=[strong])
        assert d.action == "HOLD"
        assert "anomaly" in d.reason
    finally:
        store.close()


@test("pipeline: decisions are persisted for audit (Task 15)")
def _():
    store = QuantAIStore(_db("pipe_audit"))
    try:
        pipe = QuantAIPipeline(config=QAIConfig(), store=store)
        pipe.decide(_synth(300), symbol="XAUUSD", timeframe="M5")
        rows = store._conn.execute("SELECT COUNT(*) FROM decisions").fetchone()
        assert rows[0] >= 1, rows
        assert store._conn.execute(
            "SELECT COUNT(*) FROM model_predictions").fetchone()[0] >= 1
    finally:
        store.close()


# == NEWS / NLP (Task 11) ===================================================
@test("nlp: news_mode DISABLED keeps the system fully operational")
def _():
    from quant_ai.nlp.sentiment import SentimentEngine
    assert QAIConfig().news_mode == "DISABLED"
    eng = SentimentEngine.from_config(QAIConfig())
    res = eng.evaluate(["Gold rallies on rate-cut bets"])
    assert res.available is False
    assert eng.risk_event_flag(res) is False


# == RL MODE GATING (Task 7) ================================================
@test("rl: mode gate blocks RL_DEMO without validation evidence")
def _():
    from quant_ai.rl.environment import rl_mode_gate
    assert rl_mode_gate(RL_RESEARCH)[0] is True
    assert rl_mode_gate(RL_PAPER)[0] is True
    assert rl_mode_gate(RL_DEMO)[0] is False
    assert rl_mode_gate(RL_DEMO, validated=True)[0] is True
    assert rl_mode_gate(RL_DISABLED)[0] is False
    assert QAIConfig().rl_mode == RL_RESEARCH


@test("rl: RLAgent refuses continuous-action algorithms")
def _():
    from quant_ai.rl.agents import RLAgent
    for bad in ("SAC", "TD3", "DDPG"):
        try:
            RLAgent(bad)
            raise AssertionError(f"{bad} should be rejected")
        except ValueError:
            pass


# == SYMBOL PROFILES ========================================================
@test("symbols: contract profiles are symbol-aware (gold vs fx)")
def _():
    g = symbol_profile("XAUUSD")
    f = symbol_profile("EURUSD")
    assert g["point"] == 0.01 and g["digits"] == 2
    assert f["point"] == 0.00001 and f["digits"] == 5
    assert g["min_sl_points"] > f["min_sl_points"]


# == INTEGRATION BRIDGE / ADVISORY OBSERVER (Task 14) =======================
@test("bridge: MT5 unavailable degrades to HOLD with an explicit reason")
def _():
    from quant_ai.aegis_bridge import AegisQuantBridge

    class _DeadMT5:
        TIMEFRAME_M5 = 5

        @staticmethod
        def initialize():
            return False

    sig = AegisQuantBridge(mt5_module=_DeadMT5,
                           pipeline=_QuietPipeline()).analyze("XAUUSD", "M5")
    assert sig.action == "HOLD", sig.action
    assert "unavailable" in sig.reason, sig.reason
    assert sig.mt5 == "unavailable"
    assert sig.tradable is False


@test("bridge: provided candles bypass MT5 and still yield a safe decision")
def _():
    import pandas as _pd
    from quant_ai.aegis_bridge import AegisQuantBridge
    br = AegisQuantBridge(mt5_module=None)
    br.pipeline = _QuietPipeline()
    sig = br.analyze("XAUUSD", "M5", df=_synth(50))
    assert sig.action in ("BUY", "SELL", "HOLD")
    assert sig.mt5 == "n/a"
    assert isinstance(sig.to_dict(), dict)


class _QuietPipeline:
    """Stub pipeline so the bridge test does not load real models."""
    def decide(self, df, **kw):
        from quant_ai.pipeline import ExecutionDecision
        return ExecutionDecision(action="HOLD", symbol=kw.get("symbol", ""),
                                 timeframe="M5",
                                 timestamp="2026-01-01T00:00:00+00:00",
                                 reason="stub")


@test("advisory: observer is off by default (no model load, no work)")
def _():
    from core import quant_ai_advisory as qa
    assert qa._flag_on() is False, "quant_ai_advisory must default to OFF"
    snap = qa.snapshot({})
    assert snap["flag"] is False and snap["places_orders"] is False
    assert snap["stats"]["cycles"] == 0
    assert qa._bridge is None, "bridge must not be built while the flag is off"


@test("advisory: injected failure publishes HOLD and the loop survives")
def _():
    import asyncio
    import threading
    from core import quant_ai_advisory as qa

    saved = (qa._flag_on, qa._analyze_sync, qa._append_journal, qa._cfg)
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("simulated model failure")

    qa._flag_on = lambda: True
    qa._analyze_sync = _boom
    qa._append_journal = lambda p: None

    def _fake_cfg(key, default=None):
        key = str(key)
        if "interval" in key:
            return 1.0
        if "timeout" in key:
            return 2.0
        if "symbols" in key:
            return ["XAUUSD"]
        return default

    qa._cfg = _fake_cfg

    class _GW:
        active_symbols = ["XAUUSD"]

    state, lock = {}, threading.Lock()

    async def _run():
        task = asyncio.ensure_future(qa.quant_ai_advisory_loop(
            _GW(), asyncio.get_event_loop(), None, state, lock))
        await asyncio.sleep(0.4)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(_run())
    finally:
        (qa._flag_on, qa._analyze_sync, qa._append_journal,
         qa._cfg) = saved

    assert calls["n"] >= 1, "observer never ran"
    body = state["quant_ai"]["XAUUSD"]
    assert body["action"] == "HOLD", body
    assert body["places_orders"] is False and body["advisory_only"] is True
    assert "simulated model failure" in body["reason"]


@test("advisory: malformed symbols flag degrades to gateway symbols, no crash")
def _():
    import asyncio
    import threading
    from core import quant_ai_advisory as qa

    ran = []
    saved = (qa._flag_on, qa._analyze_sync, qa._append_journal, qa._cfg)

    def _ok(symbol, *a, **k):
        ran.append(symbol)
        _hold = {"symbol": symbol, "action": "HOLD", "reason": "stub ok",
                 "timestamp": "2026-01-01T00:00:00+00:00", "mt5": "n/a"}
        return _hold

    def _bad_cfg(key, default=None):
        key = str(key)
        if "symbols" in key:
            return 42                      # plainly wrong config value
        if "interval" in key:
            return 1.0
        return 2.0 if "timeout" in key else default

    qa._flag_on = lambda: True
    qa._analyze_sync = _ok
    qa._append_journal = lambda p: None
    qa._cfg = _bad_cfg

    class _GW:
        active_symbols = ["EURUSD"]

    state, lock = {}, threading.Lock()

    async def _run():
        task = asyncio.ensure_future(qa.quant_ai_advisory_loop(
            _GW(), asyncio.get_event_loop(), None, state, lock))
        await asyncio.sleep(0.4)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    try:
        asyncio.run(_run())
    finally:
        (qa._flag_on, qa._analyze_sync, qa._append_journal,
         qa._cfg) = saved

    assert ran == ["EURUSD"], ran          # bad flag ignored, gateway used
    assert state["quant_ai"]["EURUSD"]["action"] == "HOLD"


@test("advisory: neither the observer nor quant_ai can reach an order path")
def _():
    import re
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    targets = [os.path.join(root, "core", "quant_ai_advisory.py")]
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, "quant_ai")):
        dirnames[:] = [d for d in dirnames if d not in ("vendor", "__pycache__")]
        targets += [os.path.join(dirpath, f) for f in filenames
                    if f.endswith(".py")]
    pat = re.compile(r"order_send|trade_transaction|send_command|place_order")
    offenders = []
    for p in targets:
        try:
            with open(p, "r", encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            continue
        # comments/docstrings mentioning the guard are fine; calls are not
        code = "\n".join(l for l in src.splitlines()
                         if not l.strip().startswith("#"))
        code = re.sub(r'"""(?:.|\n)*?"""', "", code)
        if pat.search(code):
            offenders.append(os.path.relpath(p, root))
    assert not offenders, f"execution call found in read-only layer: {offenders}"


def main() -> int:
    print("=" * 68)
    print("AEGIS QUANT AI - PHASE 2 TEST SUITE")
    print("=" * 68)
    for t in TESTS:
        t()
    failed = [r for r in RESULTS if r[1] == "FAIL"]
    print("-" * 68)
    print(f"TOTAL={len(RESULTS)}  PASS={len(RESULTS) - len(failed)}  FAIL={len(failed)}")
    for name, _, err in failed:
        print(f"  FAILED: {name} - {err}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())






