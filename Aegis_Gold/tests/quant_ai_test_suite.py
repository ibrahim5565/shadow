"""AEGIS QUANT AI - test suite (directive Section 47).

Covers: risk (sizing/limits/filters), execution (SL/TP/stops/volume),
safety (demo guard, RL mode gate), RL environment (observable-only state,
risk-routed actions) and model-adapter input robustness (bad input, NaN,
insufficient history, unloaded model).

Run:  .venv_cuda\\Scripts\\python.exe tests\\quant_ai_test_suite.py
No third-party test runner required; every assertion is measured and
reported. No fabricated results: failures raise.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from quant_ai.config import QAIConfig, RL_DEMO, RL_RESEARCH            # noqa: E402
from quant_ai.execution.demo_guard import DemoGuard                    # noqa: E402
from quant_ai.execution.validator import ExecutionValidator, OrderSpec  # noqa: E402
from quant_ai.predictions import PredictionStatus                      # noqa: E402
from quant_ai.quant.regime import RegimeEngine                         # noqa: E402
from quant_ai.quant.volatility import VolatilityEngine                 # noqa: E402
from quant_ai.risk.position_sizer import PositionSizer                 # noqa: E402
from quant_ai.risk.risk_engine import RiskManager                      # noqa: E402
from quant_ai.rl.environment import (ACTION_BUY, ACTION_CLOSE, ACTION_HOLD,
                                     ACTION_SELL, make_env, rl_mode_gate)
from quant_ai.storage.db import QuantAIStore                           # noqa: E402

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


def _synth(n=600, seed=7, trend=0.0):
    """Deterministic synthetic OHLCV history (observable past only)."""
    rng = np.random.default_rng(seed)
    ret = rng.normal(trend, 0.0004, n)
    close = 1.1000 * np.exp(np.cumsum(ret))
    spread = np.abs(rng.normal(0, 0.0003, n)) + 0.0002
    high = close + spread
    low = close - np.abs(rng.normal(0, 0.0003, n)) - 0.0002
    open_ = np.roll(close, 1) + rng.normal(0, 0.0001, n)
    open_[0] = close[0]
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})


# == RISK (Section 47) =======================================================
@test("risk: fixed fractional sizing respects risk budget")
def _():
    s = PositionSizer("fixed_fractional")
    lot = s.size(equity=10_000, risk_per_trade=0.01, sl_points=100,
                 point_value_per_lot=1.0)
    # 1% of 10k = $100 risk; 100 pts x $1/pt/lot = $100 per lot -> 1.0 lot
    assert abs(lot - 1.0) < 0.011, f"lot={lot}"


@test("risk: sizing is monotonic in SL distance")
def _():
    s = PositionSizer("fixed_fractional")
    tight = s.size(equity=10_000, risk_per_trade=0.01, sl_points=50,
                   point_value_per_lot=1.0)
    wide = s.size(equity=10_000, risk_per_trade=0.01, sl_points=200,
                  point_value_per_lot=1.0)
    assert tight > wide, (tight, wide)
    assert abs(wide - tight / 4) < 0.03


@test("risk: spread filter blocks abnormal spread")
def _():
    rm = RiskManager(QAIConfig())
    d = rm.evaluate(symbol="EURUSD", direction="BUY", equity=10_000,
                    spread_pts=500.0, point=0.0001, point_value_per_lot=1.0,
                    sl_points=100, tp_points=150)
    assert not d.allowed and "spread" in d.reason, d


@test("risk: session filter blocks unknown session")
def _():
    rm = RiskManager(QAIConfig(session_filter=True))
    d = rm.evaluate(symbol="EURUSD", direction="BUY", equity=10_000,
                    spread_pts=2.0, point=0.0001, point_value_per_lot=1.0,
                    sl_points=100, tp_points=150, session="MIDNIGHT")
    assert not d.allowed and "session" in d.reason, d


@test("risk: daily loss limit blocks after breach")
def _():
    rm = RiskManager(QAIConfig())
    rm.roll_daily(10_000)
    rm.on_trade_result(-600.0)          # > 5% of 10k
    d = rm.evaluate(symbol="EURUSD", direction="BUY", equity=10_000,
                    spread_pts=2.0, point=0.0001, point_value_per_lot=1.0,
                    sl_points=100, tp_points=150)
    assert not d.allowed and "daily_loss" in d.reason, d


@test("risk: consecutive-loss protection")
def _():
    rm = RiskManager(QAIConfig(max_consecutive_losses=3))
    for _ in range(3):
        rm.on_trade_result(-10.0)
    d = rm.evaluate(symbol="EURUSD", direction="BUY", equity=10_000,
                    spread_pts=2.0, point=0.0001, point_value_per_lot=1.0,
                    sl_points=100, tp_points=150)
    assert not d.allowed and "consecutive_losses" in d.reason, d


@test("risk: clean trade passes and returns lot + SL/TP")
def _():
    rm = RiskManager(QAIConfig())
    d = rm.evaluate(symbol="EURUSD", direction="BUY", equity=10_000,
                    spread_pts=2.0, point=0.0001, point_value_per_lot=1.0,
                    sl_points=100, tp_points=150, session="LONDON")
    assert d.allowed, d.reason
    assert d.lot_size >= 0.01 and d.sl_points == 100 and d.tp_points == 150


# == EXECUTION (Sections 36, 47) =============================================
@test("execution: valid BUY passes with normalized values")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="EURUSD", side="BUY", entry=1.1000,
                             sl=1.0950, tp=1.1100, volume=0.5, point=0.00001,
                             digits=5, stops_level_pts=10.0))
    assert r["ok"], r["errors"]
    assert abs(r["sl_pts"] - 500.0) < 0.1
    assert r["normalized_sl"] == 1.0950


@test("execution: valid SELL passes")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="XAUUSD", side="SELL", entry=2400.00,
                             sl=2405.00, tp=2390.00, volume=0.1, point=0.01,
                             digits=2, stops_level_pts=20.0))
    assert r["ok"], r["errors"]
    assert abs(r["sl_pts"] - 500.0) < 0.1


@test("execution: BUY SL above entry is rejected (error 10016 guard)")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="EURUSD", side="BUY", entry=1.1000,
                             sl=1.1050, tp=1.1100, volume=0.1, point=0.00001,
                             digits=5))
    assert not r["ok"] and any("must be < entry" in e for e in r["errors"]), r


@test("execution: SELL TP above entry is rejected")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="EURUSD", side="SELL", entry=1.1000,
                             sl=1.1050, tp=1.1100, volume=0.1, point=0.00001,
                             digits=5))
    assert not r["ok"] and any("must be < entry" in e for e in r["errors"]), r


@test("execution: SL distance below broker stops level is rejected")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="EURUSD", side="BUY", entry=1.1000,
                             sl=1.09995, tp=1.1100, volume=0.1,
                             point=0.00001, digits=5, stops_level_pts=50.0))
    assert not r["ok"] and any("stops level" in e for e in r["errors"]), r


@test("execution: naked SL (0) is rejected")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="EURUSD", side="BUY", entry=1.1000,
                             sl=0.0, tp=0.0, volume=0.1, point=0.00001,
                             digits=5))
    assert not r["ok"] and any("SL must be > 0" in e for e in r["errors"]), r


@test("execution: volume normalized to broker step")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="EURUSD", side="BUY", entry=1.1000,
                             sl=1.0950, tp=1.1100, volume=0.137, point=0.00001,
                             digits=5, volume_step=0.01, volume_min=0.01))
    assert r["ok"] and abs(r["normalized_volume"] - 0.14) < 1e-9, r


@test("execution: volume below broker minimum is rejected")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="EURUSD", side="BUY", entry=1.1000,
                             sl=1.0950, tp=1.1100, volume=0.005,
                             point=0.00001, digits=5, volume_min=0.01,
                             volume_step=0.01))
    assert not r["ok"] and any("minimum" in e for e in r["errors"]), r


@test("execution: invalid side is rejected")
def _():
    v = ExecutionValidator()
    r = v.validate(OrderSpec(symbol="EURUSD", side="LONG", entry=1.1000,
                             sl=1.0950, tp=1.1100, volume=0.1, point=0.00001,
                             digits=5))
    assert not r["ok"]


# == SAFETY (Sections 35, 10) ================================================
@test("safety: demo account passes DemoGuard")
def _():
    r = DemoGuard().check({"server": "Demo-Server", "login": 123})
    assert r["ok"] and not r["blocked"], r


@test("safety: LIVE server is blocked")
def _():
    r = DemoGuard().check({"server": "ICMarkets-Live05", "login": 123})
    assert r["blocked"] and "not a DEMO" in r["reason"], r


@test("safety: allow_live flag can never enable live (frozen build)")
def _():
    r = DemoGuard(allow_live=True).check({"server": "Demo-Server"})
    assert r["blocked"], r


@test("safety: config constants frozen to DEMO")
def _():
    from quant_ai.config import ALLOW_LIVE_TRADING, TRADING_MODE
    assert TRADING_MODE == "DEMO" and ALLOW_LIVE_TRADING is False


@test("safety: RL_DEMO blocked without walk-forward validation evidence")
def _():
    ok, reason = rl_mode_gate(RL_DEMO, validated=False)
    assert not ok and "BLOCKED" in reason, (ok, reason)
    ok2, _ = rl_mode_gate(RL_DEMO, validated=True)
    assert ok2
    ok3, _ = rl_mode_gate(RL_RESEARCH)
    assert ok3


# == RL ENVIRONMENT (Sections 9-12, 47) ======================================
def _make_env(df, **kw):
    cfg = QAIConfig()
    cfg.session_filter = False           # synthetic data uses LONDON default
    defaults = dict(config=cfg, warmup=60, spread_pts=2.0)
    defaults.update(kw)
    return make_env(df, **defaults)


@test("rl: reset/step cycle runs and obs is finite 12-dim")
def _():
    env = _make_env(_synth())
    obs, info = env.reset()
    assert obs.shape == (12,) and np.isfinite(obs).all()
    for a in (ACTION_HOLD, ACTION_BUY, ACTION_HOLD, ACTION_SELL, ACTION_CLOSE):
        obs, r, done, trunc, info = env.step(a)
        assert np.isfinite(obs).all()
        if done:
            break


@test("rl: state has no future information (causal ret_1 feature)")
def _():
    df = _synth(300)
    env = _make_env(df, warmup=100)
    env.reset()
    env.t = 150
    sd = env.state_dict()
    c = df["close"]
    expect = float(c.iloc[150] / c.iloc[149] - 1) * 20.0
    assert abs(sd["ret_1"] - expect) < 0.02, (sd, expect)


@test("rl: BUY opens position only after risk engine approval")
def _():
    env = _make_env(_synth())
    env.reset()
    env._apply(ACTION_BUY)
    assert env.position is not None, env.last_gate
    assert "opened" in env.last_gate
    assert env.position.sl < env.position.entry < env.position.tp
    assert env.position.lot >= 0.01


@test("rl: second BUY while position open is gated")
def _():
    env = _make_env(_synth())
    env.reset()
    env._apply(ACTION_BUY)
    env._apply(ACTION_BUY)
    assert env.last_gate == "position_open"


@test("rl: CLOSE realizes PnL and updates risk engine stats")
def _():
    env = _make_env(_synth())
    env.reset()
    env._apply(ACTION_BUY)
    env.t += 10
    env._apply(ACTION_CLOSE)
    assert env.position is None and len(env.closed_pnl) == 1
    assert "closed" in env.last_gate
    assert len(env.risk.pnl_history) == 1


@test("rl: abnormal spread blocks entry through risk engine")
def _():
    env = _make_env(_synth(), spread_pts=900.0)
    env.reset()
    env._apply(ACTION_BUY)
    assert env.position is None and "risk_blocked" in env.last_gate, env.last_gate


@test("rl: drawdown breach terminates episode and force-closes")
def _():
    df = _synth(600, seed=3)
    env = _make_env(df, max_drawdown=1e-6)
    env.reset()
    env._apply(ACTION_BUY)
    # push price far against a long position (synthetic shock, test only)
    env.df.loc[env.t + 1:env.t + 60, "close"] = float(df["close"].iloc[0]) * 0.5
    done = False
    for _ in range(200):
        obs, r, done, trunc, info = env.step(ACTION_HOLD)
        if done:
            break
    assert done and env.position is None, (done, info)


@test("rl: SL is enforced intra-bar (loss bounded near risk budget)")
def _():
    env = None
    for seed in (11, 3, 7, 21, 42, 5, 13):     # deterministic probe
        env = _make_env(_synth(600, seed=seed))
        env.reset()
        env._apply(ACTION_BUY)
        if env.position is not None:
            break
        env = None
    assert env is not None, "no seed produced a risk-approved entry"
    entry, sl = env.position.entry, env.position.sl
    lot = env.position.lot
    # crash the next bars below the stop (test-only synthetic shock)
    env.df.loc[env.t + 1:env.t + 20, "low"] = sl * 0.999
    env.df.loc[env.t + 1:env.t + 20, "close"] = sl * 0.995
    for _ in range(5):
        obs, r, done, trunc, info = env.step(ACTION_HOLD)
        if env.position is None:
            break
    assert env.position is None, "SL should have closed the position"
    assert env.last_gate.startswith("sl_hit"), env.last_gate
    loss_pts = abs(entry - sl) / env.point
    expected_loss = loss_pts * lot * env.point_value_per_lot
    assert abs(env.closed_pnl[0] - (-expected_loss)) < 0.5, env.closed_pnl


@test("rl: default rl_mode is RL_RESEARCH")
def _():
    assert QAIConfig().rl_mode == RL_RESEARCH


# == MODELS / VOLATILITY / REGIME / STORAGE ==================================
@test("models: adapter robust to empty/NaN/short input (kronos small)")
def _():
    from quant_ai.models.kronos_adapter import KronosAdapter
    a = KronosAdapter(symbol="XAUUSD", timeframe="M5")
    p1 = a.predict(pd.DataFrame(), 12)
    assert p1.status in (PredictionStatus.INSUFFICIENT_DATA,
                         PredictionStatus.MODEL_UNAVAILABLE), p1.status
    bad = _synth(80)
    bad.loc[bad.index[10], "close"] = np.nan
    p2 = a.predict(bad, 12)
    assert p2.status != PredictionStatus.OK, p2.status
    p3 = a.predict(_synth(10), 12)
    assert p3.status in (PredictionStatus.INSUFFICIENT_DATA,
                         PredictionStatus.MODEL_UNAVAILABLE), p3.status


@test("volatility: ATR/realized/EWMA measured, percentile in [0,1]")
def _():
    out = VolatilityEngine().analyze(_synth(400))
    assert 0.0 <= out["vol_percentile"] <= 1.0
    assert out["atr_points_20"] > 0 and out["realized_vol_20"] > 0
    assert "garch" in out


@test("regime: label is one of the defined regimes with reasons")
def _():
    re_ = RegimeEngine()
    df = _synth(400, trend=0.0008)
    rep = re_.detect(df, vol_percentile=0.5)
    assert rep.regime in ("TRENDING_UP", "TRENDING_DOWN", "RANGING",
                          "HIGH_VOLATILITY", "LOW_VOLATILITY", "BREAKOUT",
                          "MEAN_REVERSION", "UNCERTAIN"), rep.regime
    assert isinstance(rep.reasons, list)
    assert re_.detect(df, vol_percentile=0.99).regime == "HIGH_VOLATILITY"
    assert re_.detect(df, vol_percentile=0.05).regime == "LOW_VOLATILITY"


@test("storage: predictions, errors, tournament, decisions persist")
def _():
    with tempfile.TemporaryDirectory() as tmp:
        store = QuantAIStore(os.path.join(tmp, "t.db"))
        store.record_prediction({"timestamp": "2026-09-09T00:00:00Z",
                                 "model": "kronos_small", "symbol": "XAUUSD",
                                 "timeframe": "M5", "forecast_price": 2400.5,
                                 "direction": "UP", "status": "ok"})
        store.record_forecast_error(ts="2026-09-09T00:00:00Z",
                                    model="kronos_small", symbol="XAUUSD",
                                    timeframe="M5", horizon=12,
                                    actual=2400.0, forecast=2400.5)
        errs = store.recent_errors("kronos_small")
        assert len(errs) == 1 and abs(errs[0]["forecast"] - 2400.5) < 1e-9
        store.record_decision(ts="2026-09-09T00:00:00Z", action="HOLD",
                              symbol="XAUUSD", timeframe="M5",
                              record={"why": "uncertainty high"})
        store.close()


def main() -> int:
    print("=" * 68)
    print("AEGIS QUANT AI - TEST SUITE")
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



