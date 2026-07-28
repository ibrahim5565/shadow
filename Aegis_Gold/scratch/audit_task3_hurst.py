"""
Task 3 — CORRECTED Hurst Exponent Audit
=========================================
AUDIT FINDING (pre-fix):
  test_hurst_htf.py had TWO bugs that guaranteed the output would always be 0.5000:

  BUG 1 — Wrong dictionary key:
    The script called `q_res.get('hurst', 0.50)`.
    QuantFeatureEngine.analyze() returns the key 'hurst_100', NOT 'hurst'.
    Because 'hurst' is never in the result dict, get() silently returned the default 0.50.
    This is not a real calculation — it is the hardcoded default value.

  BUG 2 — Non-XAUUSD input / synthetic fallback:
    The script read `entry_price` from trade_memory.db via:
      SELECT entry_price FROM trades ORDER BY trade_id ASC
    This returns a MIX of EURUSD prices (~1.14xxx) and XAUUSD prices (~4100-4200).
    Feeding a mixed multi-asset price series into an R/S Hurst calculation is meaningless.
    Additionally, the script fell back to synthetic Gaussian random walk if fewer than 50 rows
    were returned — which would by construction produce H ≈ 0.5.

  BUG 3 — No H1/H4 OHLC bars:
    The test claims to test "H1/H4" data but reads tick-frequency entry prices from trade
    records (which arrive at M1 or sub-minute intervals). These are NOT H1/H4 OHLC closes.
    No H1/H4 bar data is stored in trade_memory.db.

THIS SCRIPT FIXES ALL THREE:
  1. Uses the correct key 'hurst_100'.
  2. Separates XAUUSD and EURUSD entry prices and runs Hurst on each independently.
  3. Logs the actual input array (length, first/last 5 values) BEFORE calling Hurst.
  4. Calls calculate_hurst() directly (not via analyze()) to bypass any silent fallbacks.
  5. Reports the actual computed H alongside the input summary so it can be sanity-checked.
  6. Explicitly documents that these are NOT H1/H4 OHLC closes and what the numbers mean.

NOTE ON H1/H4 DATA AVAILABILITY:
  No H1/H4 OHLC bar data is stored in any database in this codebase. Generating a proper
  H1/H4 Hurst estimate requires either:
    (a) Running MT5 with the bot active and requesting H1/H4 bars via copy_rates_from_pos(), or
    (b) Loading an offline historical OHLCV file for XAUUSD.
  This script reports H on available entry-price sequences as the best available proxy,
  and clearly labels them as such.
"""

import sys
import numpy as np
import pandas as pd
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from brain.quant_feature_engine import QuantFeatureEngine

DATA_DIR = BASE_DIR / "data"
TRADE_MEMORY_DB = DATA_DIR / "trade_memory.db"

print("=" * 70)
print("TASK 3 — HURST EXPONENT AUDIT (Corrected)")
print("=" * 70)

# Load ALL trade entry prices, separate by symbol
conn = sqlite3.connect(TRADE_MEMORY_DB)
df = pd.read_sql_query(
    "SELECT symbol, entry_price, entry_time FROM trades "
    "WHERE entry_price IS NOT NULL AND entry_price > 0 "
    "ORDER BY entry_time ASC",
    conn
)
conn.close()

print(f"\nTotal rows loaded: {len(df)}")
print(f"Symbol breakdown: {df['symbol'].value_counts().to_dict()}")

qfe = QuantFeatureEngine()

for symbol in ["XAUUSD", "EURUSD"]:
    prices_raw = df[df["symbol"] == symbol]["entry_price"].values
    prices = prices_raw.astype(float)

    print(f"\n{'='*60}")
    print(f"SYMBOL: {symbol}")
    print(f"  Input array length:  {len(prices)}")
    if len(prices) > 0:
        print(f"  First 5 values:      {prices[:5]}")
        print(f"  Last 5 values:       {prices[-5:]}")
        print(f"  Min: {prices.min():.4f}  Max: {prices.max():.4f}  StdDev: {prices.std():.4f}")
    else:
        print("  ERROR: No data for this symbol.")
        continue

    if len(prices) < 20:
        print(f"  WARNING: Only {len(prices)} samples — Hurst requires >= 20. Reporting N/A.")
        continue

    # Call calculate_hurst directly — bypass analyze() to avoid any silent fallbacks
    try:
        hurst_val = QuantFeatureEngine.calculate_hurst(prices)
        print(f"\n  Hurst Exponent (R/S on entry-price sequence): H = {hurst_val:.4f}")
        if abs(hurst_val - 0.5) < 1e-6:
            print(f"  WARNING: H is exactly 0.5000 — inspecting R/S computation manually...")
            # Manual spot-check on lag=8
            n = len(prices)
            lag = 8
            num_chunks = n // lag
            if num_chunks >= 1:
                chunks = prices[:num_chunks * lag].reshape((num_chunks, lag))
                means = np.mean(chunks, axis=1, keepdims=True)
                devs = chunks - means
                cumsum = np.cumsum(devs, axis=1)
                rng = np.max(cumsum, axis=1) - np.min(cumsum, axis=1)
                stds = np.std(chunks, axis=1, ddof=1)
                valid = stds > 0
                if valid.any():
                    rs = rng[valid] / stds[valid]
                    print(f"  Spot-check lag=8: R/S mean = {np.mean(rs):.4f}, n_chunks={num_chunks}, n_valid={valid.sum()}")
                else:
                    print(f"  Spot-check lag=8: ALL STD=0 (constant series!) — this would force H=0.5")
    except Exception as e:
        print(f"  ERROR in calculate_hurst: {e}")
        hurst_val = None

    if hurst_val is not None:
        if hurst_val > 0.55:
            regime = "PERSISTENT TRENDING (H > 0.55)"
        elif hurst_val < 0.45:
            regime = "MEAN-REVERTING (H < 0.45)"
        else:
            regime = "RANDOM WALK / MIXED (0.45 <= H <= 0.55)"
        print(f"  Regime interpretation: {regime}")

    print(f"\n  DATA QUALITY CAVEAT:")
    print(f"  These are trade ENTRY PRICES sampled at M1-ish frequency, not H1/H4 OHLC closes.")
    print(f"  A proper H1 Hurst requires 100+ consecutive H1 bars from MT5 copy_rates_from_pos().")
    print(f"  Entry-price Hurst gives directional information about trade-frequency market state,")
    print(f"  NOT the HTF structural persistence needed for Pro Trend mode decisions.")

print(f"""
--- CONCLUSION ---
  PREVIOUS RESULT (H=0.5000 "to four decimal places"): INVALID.
  Root cause: `q_res.get('hurst', 0.50)` used wrong key ('hurst' vs 'hurst_100').
  The value was the hardcoded Python default, not a computed number.

  HONEST RESULT: See per-symbol results above.
  
  For genuine H1/H4 Hurst analysis:
    - Connect MT5 and run: mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 200)
    - Pass the resulting close[] array to QuantFeatureEngine.calculate_hurst()
    - A minimum of 100 H1 bars (4+ trading days) is needed for a stable R/S estimate.
  This cannot be done offline without live MT5 connection or an external OHLCV data source.
""")
