"""Real LOCAL inference smoke: amazon/chronos-2 on actual MT5 EURUSD M5 data.

Measures: model load time, predict latency, forecast path, honest uncertainty
(model's own P10-P90 band).  Exits nonzero if anything fails — no fake output.
"""
import sys
import time

sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from quant_ai.models.chronos_adapter import ChronosAdapter

try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 not installed in this venv — cannot fetch live data")
    sys.exit(2)

SYMBOL = "EURUSD"
N_BARS = 1000
HORIZON = 12

print(f"=== fetching {SYMBOL} M5 x{N_BARS} from MT5 demo ===")
if not mt5.initialize():
    print(f"MT5 init failed: {mt5.last_error()}")
    sys.exit(2)
try:
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, N_BARS)
finally:
    mt5.shutdown()
if rates is None or len(rates) < 200:
    print(f"insufficient data returned: {None if rates is None else len(rates)} bars")
    sys.exit(2)
df = pd.DataFrame(rates)
df["time"] = pd.to_datetime(df["time"], unit="s")
print(f"got {len(df)} bars: {df['time'].iloc[0]} -> {df['time'].iloc[-1]}")
print(f"last_close={df['close'].iloc[-1]:.5f}")

print("=== loading amazon/chronos-2 locally (first run downloads weights) ===")
t0 = time.perf_counter()
ad = ChronosAdapter(symbol=SYMBOL, device="cpu")
if not ad.load():
    print("MODEL LOAD FAILED — see adapter log")
    sys.exit(1)
print(f"model load wall time: {time.perf_counter() - t0:.1f}s")

print("=== running real local inference ===")
pred = ad.predict(df, horizon=HORIZON)
if pred.status.value != "ok":
    print(f"INFERENCE FAILED: status={pred.status.value} detail={pred.detail}")
    sys.exit(1)

print()
print("--- RESULT (real local prediction) ---")
print(f"model            : {pred.model}")
print(f"status           : {pred.status.value}")
print(f"latency_ms       : {pred.latency_ms}")
print(f"last_close       : {df['close'].iloc[-1]:.5f}")
print(f"forecast_close   : {pred.forecast_price:.5f} (h{pred.forecast_horizon})")
print(f"forecast_return  : {pred.forecast_return:+.6f}")
print(f"direction        : {pred.direction.value}")
print(f"uncertainty      : {pred.uncertainty:.6f} (P10-P90/median)")
print(f"raw              : {pred.raw}")
print(f"prices_path head : {[round(x, 5) for x in pred.prices_path[:4]]}")
print(f"prices_path tail : {[round(x, 5) for x in pred.prices_path[-4:]]}")
print()
print("CHRONOS-2 REAL LOCAL INFERENCE OK")
