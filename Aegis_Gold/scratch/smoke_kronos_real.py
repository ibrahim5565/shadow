"""SMOKE TEST: load the REAL pretrained Kronos-small (NeoQuasar, MIT) and run inference."""
import sys, time, os
import numpy as np
import pandas as pd

VENDOR = r"D:\Trading\Aegis_Gold\quant_ai\vendor\kronos"
sys.path.insert(0, VENDOR)

t0 = time.time()
from model import Kronos, KronosTokenizer, KronosPredictor
print(f"[import vendored kronos] {time.time()-t0:.1f}s")

t0 = time.time()
tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
print(f"[tokenizer loaded] {time.time()-t0:.1f}s")
t0 = time.time()
model = Kronos.from_pretrained("NeoQuasar/Kronos-small")
print(f"[model loaded] {time.time()-t0:.1f}s")

dev = "cuda" if __import__("torch").cuda.is_available() else "cpu"
print(f"[device] {dev}")
predictor = KronosPredictor(model, tokenizer, device=dev, max_context=512)

# Synthetic OHLCV (XAUUSD-like)
rng = np.random.default_rng(42)
n = 300
base = 2400.0
rets = rng.normal(0, 1.0, n)
prices = base + np.cumsum(rets)
df = pd.DataFrame({
    "open": prices,
    "high": prices + np.abs(rng.normal(0, 0.8, n)),
    "low": prices - np.abs(rng.normal(0, 0.8, n)),
    "close": prices + rng.normal(0, 0.4, n),
    "volume": rng.uniform(100, 1000, n),
})
times = pd.date_range("2026-01-01 00:00", periods=n, freq="5min")
x_ts = pd.Series(times)
y_ts = pd.Series(pd.date_range(times[-1] + pd.Timedelta(minutes=5), periods=24, freq="5min"))

t0 = time.time()
pred = predictor.predict(df=df, x_timestamp=x_ts, y_timestamp=y_ts, pred_len=24,
                         T=1.0, top_p=0.9, sample_count=1, verbose=False)
print(f"[predict 24 steps] {time.time()-t0:.1f}s")
print("shape:", pred.shape)
print(pred.head(5))
last_close = float(df["close"].iloc[-1])
fc_close = float(pred["close"].iloc[-1])
print(f"last_close={last_close:.2f} forecast_close_h24={fc_close:.2f} delta={fc_close-last_close:+.2f}")