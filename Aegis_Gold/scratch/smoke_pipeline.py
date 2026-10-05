"""Smoke test: Pipeline + PaperBroker wiring (Phase-2 Tasks 13/14/18).

Run:  .venv_cuda\\Scripts\\python.exe scratch\\smoke_pipeline.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from quant_ai.config import QAIConfig
from quant_ai.paper_trading import PaperBroker, PaperBrokerConfig
from quant_ai.pipeline import QuantAIPipeline, symbol_profile


def synth(n=600, seed=11, trend=0.0, base=2400.0):
    rng = np.random.default_rng(seed)
    ret = rng.normal(trend, 0.0006, n)
    close = base * np.exp(np.cumsum(ret))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    # valid OHLC: high >= max(open, close), low <= min(open, close)
    wick = (np.abs(rng.normal(0, 0.0004, n)) + 0.0002) * base
    high = np.maximum(open_, close) + wick
    low = np.minimum(open_, close) - wick
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close})
    df.index = pd.date_range("2026-01-01", periods=n, freq="5min")
    return df


def main() -> int:
    print("=" * 72)
    print("SMOKE: pipeline + paper broker")
    print("=" * 72)
    df = synth()
    prof = symbol_profile("XAUUSD")
    print("symbol profile:", prof)

    cfg = QAIConfig()
    pipe = QuantAIPipeline(config=cfg, store=None)
    d = pipe.decide(df, symbol="XAUUSD", timeframe="M5", equity=10_000,
                    spread_pts=5.0, session="LONDON")
    print(f"[no evidence] action={d.action} reason={d.reason[:90]}")

    # seed measured evidence so the selector has something to rank
    from quant_ai.storage.db import QuantAIStore
    import tempfile
    tmp = tempfile.mkdtemp()
    store = QuantAIStore(os.path.join(tmp, "smoke.db"))
    tdf = synth(seed=5, trend=0.0004)          # trending series -> directional
    last = tdf["close"].values
    for name, err_scale in (("baseline_momentum", 0.00005),
                            ("baseline_ema_trend", 0.00008),
                            ("baseline_sma", 0.00010)):
        for i in range(120, len(tdf)):
            actual = float(last[i])
            store.record_forecast_error(
                ts=str(tdf.index[i]), model=name, symbol="XAUUSD", timeframe="M5",
                horizon=12, actual=actual,
                forecast=actual * (1.0 + np.random.default_rng(i).normal(0, err_scale)))
    pipe2 = QuantAIPipeline(config=cfg, store=store)
    d2 = pipe2.decide(tdf, symbol="XAUUSD", timeframe="M5", equity=10_000,
                      spread_pts=5.0, session="LONDON")
    print(f"[with evidence] action={d2.action} reason={d2.reason[:110]}")
    if d2.action in ("BUY", "SELL"):
        print("  position:", d2.position)
        print("  demo_guard:", d2.demo_guard)
        print("  validation ok:", d2.validation["ok"])

    # paper broker round trip
    broker = PaperBroker(PaperBrokerConfig(symbol="XAUUSD", point=0.01, digits=2,
                                           spread_points=5.0))
    px = float(df["close"].iloc[-1])
    res = broker.try_open(side="BUY", price=px, sl=px - 2.0, tp=px + 3.0,
                          lot=0.10, index=len(df) - 1, ts="2026-01-01")
    print("paper try_open:", res["ok"])
    broker.manage(index=len(df) - 1, ts="t", high=px + 4.0, low=px - 0.5,
                  close=px + 2.0)
    print("paper summary:", broker.summary())
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
