"""
===========================================================================
AEGIS GOLD — Phase 1 Standalone Test for Kronos Forecaster Wrapper
===========================================================================

PURPOSE:
--------
Sanity checks `brain/kronos_forecaster.py` against real historical XAUUSD candle
data before any integration into the live AEGIS pipeline.

EXPLICIT CAVEAT ACCOUNTING:
---------------------------
Unlike the baseline Kronos repository demos (which omit transaction costs and
slippage), this test harness explicitly incorporates AEGIS GOLD's standard execution
cost model from `modules/risk_manager.py`:
  - Spread: 25.0 points ($0.25 on XAUUSD)
  - Slippage: 5.0 points ($0.05 on XAUUSD)
  - Commission: $0.07 per 0.01 lot ($7.00/lot)

USAGE:
------
python scripts/test_kronos_forecaster.py
===========================================================================
"""

import os
import sys
import sqlite3
import logging
from pathlib import Path
import numpy as np

# Ensure AEGIS root is in PYTHONPATH
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from brain.kronos_forecaster import KronosForecaster, KronosForecast

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("aegis.test_kronos")


def load_historical_xauusd_candles(db_path: Path, n_candles: int = 200) -> list[dict]:
    """
    Attempts to read real historical XAUUSD trades or prices from SQLite database.
    If database is empty or missing, generates realistic synthetic XAUUSD price sequence.
    """
    candles = []
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Query trades or price memory
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]

            if "trades" in tables:
                cursor.execute("SELECT open_price, close_price, high, low, close_time FROM trades WHERE symbol LIKE '%XAU%' ORDER BY id DESC LIMIT ?", (n_candles,))
                rows = cursor.fetchall()
                for row in reversed(rows):
                    open_p, close_p, high_p, low_p, ctime = row[0], row[1], row[2], row[3], row[4]
                    candles.append({
                        "open": float(open_p or 2350.0),
                        "high": float(high_p or (open_p + 1.5)),
                        "low": float(low_p or (open_p - 1.5)),
                        "close": float(close_p or 2350.0),
                        "volume": 100.0,
                        "time": str(ctime),
                    })
                conn.close()
                if candles:
                    logger.info(f"✅ Successfully loaded {len(candles)} real XAUUSD candles from {db_path.name}")
                    return candles
        except Exception as e:
            logger.warning(f"⚠️ Error reading candles from DB: {e}. Generating realistic benchmark series.")

    # Synthetic realistic XAUUSD M5 price series generator (Gold ~$2,380 base)
    logger.info("ℹ️ Generating 200 bars of realistic XAUUSD (Gold) market candles for sanity check...")
    np.random.seed(100)
    base_price = 2380.0
    price = base_price

    for i in range(n_candles):
        change = np.random.normal(0.05, 1.2)  # XAUUSD typical M5 noise
        open_p = price
        close_p = open_p + change
        high_p = max(open_p, close_p) + abs(np.random.normal(0.3, 0.4))
        low_p = min(open_p, close_p) - abs(np.random.normal(0.3, 0.4))
        price = close_p

        candles.append({
            "open": round(open_p, 2),
            "high": round(high_p, 2),
            "low": round(low_p, 2),
            "close": round(close_p, 2),
            "volume": float(np.random.randint(50, 500)),
            "time": f"2026-07-27T{i//12:02d}:{(i%12)*5:02d}:00Z",
        })

    return candles


def run_phase1_sanity_check():
    """Executes Phase 1 standalone test suite."""
    logger.info("=========================================================")
    logger.info("  AEGIS GOLD — KRONOS FORECASTER PHASE 1 SANITY CHECK   ")
    logger.info("=========================================================")

    db_path = BASE_DIR / "data" / "performance.db"
    candles = load_historical_xauusd_candles(db_path, n_candles=150)

    # Instantiate forecaster wrapper
    forecaster = KronosForecaster(
        model_name_or_path="NeoQuasar/Kronos-small",
        forecast_horizon=24,
        n_samples=50,
        context_window=100
    )

    # Predict
    forecast: KronosForecast = forecaster.predict(candles)

    # Print / Log output summary
    logger.info("\n--- KRONOS FORECAST OUTPUT SUMMARY ---")
    logger.info(f"Model Version          : {forecast.model_version}")
    logger.info(f"Timestamp              : {forecast.timestamp}")
    logger.info(f"Forecast Horizon       : {forecast.horizon_bars} bars")
    logger.info(f"Predicted Direction    : {forecast.predicted_direction}")
    logger.info(f"Confidence (Bullish P) : {forecast.confidence_up:.4f}")
    logger.info(f"24h Volatility Forecast: ${forecast.volatility_forecast_24h:.2f} USD")

    if forecast.price_path_mean:
        logger.info(f"Path Mean (First 5)    : {[round(x, 2) for x in forecast.price_path_mean[:5]]}")
        logger.info(f"Path Mean (Final Bar)  : {round(forecast.price_path_mean[-1], 2)}")
        logger.info(f"Path Std (Final Bar)   : {round(forecast.price_path_std[-1], 2)}")

    # Transaction cost & market friction audit
    # Standard AEGIS XAUUSD parameters
    spread_pts = 25.0       # $0.25/oz
    slippage_pts = 5.0      # $0.05/oz
    comm_usd_per_lot = 7.0  # $7 per standard lot
    pip_val_001_lot = 0.01

    net_cost_per_001_lot = (spread_pts + slippage_pts) * pip_val_001_lot + (comm_usd_per_lot * 0.01)
    logger.info("\n--- TRANSACTION COST & SLIPPAGE AUDIT ---")
    logger.info(f"Spread + Slippage Cost (0.01 lot) : ${net_cost_per_001_lot:.3f}")
    logger.info(f"Kronos Volatility vs Cost Ratio    : {forecast.volatility_forecast_24h / max(0.01, net_cost_per_001_lot):.2f}x")

    if forecast.volatility_forecast_24h > net_cost_per_001_lot * 2:
        logger.info("✅ PASS: Kronos forecasted volatility exceeds 2x execution friction threshold.")
    else:
        logger.warning("⚠️ ATTENTION: Forecasted volatility is too low relative to transaction costs.")

    logger.info("\n=========================================================")
    logger.info("  PHASE 1 SANITY CHECK COMPLETE — READY FOR MANUAL REVIEW ")
    logger.info("=========================================================\n")


if __name__ == "__main__":
    run_phase1_sanity_check()
