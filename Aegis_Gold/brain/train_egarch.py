"""
===========================================================================
AEGIS GOLD — EGARCH Volatility Model Trainer (Quant Features - Step 1)
===========================================================================

PURPOSE:
--------
Fits an asymmetric EGARCH(1,1) model on XAUUSD M5 return series.
Evaluates forecast accuracy against realized volatility using rolling
walk-forward re-fitting, reporting MAE, RMSE, and QLIKE loss.
Saves model parameters to models/egarch_model.json.

USAGE:
    .venv_cuda\\Scripts\\python.exe -m brain.train_egarch
===========================================================================
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import warnings
from arch.utility.exceptions import DataScaleWarning
warnings.simplefilter("ignore", DataScaleWarning)
warnings.simplefilter("ignore", UserWarning)

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aegis.train_egarch")

MODEL_OUT_PATH = BASE_DIR / "models" / "egarch_model.json"


def fetch_xauusd_history(count: int = 5000) -> np.ndarray:
    """
    Fetch XAUUSD M5 close prices from MT5.
    If MT5 is not available or returns insufficient data, generate a
    synthetic geometric Brownian motion series with volatility regime shifts
    so the pipeline is fully testable offline.
    """
    try:
        import MetaTrader5 as mt5
        from config import settings as cfg

        if mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER):
            rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_M5, 0, count)
            if rates is not None and len(rates) >= 500:
                closes = np.array([r['close'] for r in rates], dtype=float)
                logger.info("Loaded %d M5 close prices from MT5", len(closes))
                return closes
    except Exception as exc:
        logger.warning("Could not fetch rates from MT5: %s", exc)

    logger.info("Generating synthetic XAUUSD price series with vol regimes for training...")
    np.random.seed(42)
    n = count
    dt = 1.0 / (288 * 252) # M5 bars per year approx
    mu = 0.05
    # Simulating 3 volatility regimes
    vol_regimes = [0.12, 0.28, 0.16]
    price = 2400.0
    prices = [price]
    regime_lengths = [int(n * 0.4), int(n * 0.3), int(n * 0.3)]
    
    for vol in vol_regimes:
        length = int(n / len(vol_regimes))
        for _ in range(length):
            ret = (mu - 0.5 * vol**2) * dt + vol * np.sqrt(dt) * np.random.normal()
            price *= np.exp(ret)
            prices.append(price)
            
    return np.array(prices[:count], dtype=float)


def compute_log_returns(prices: np.ndarray) -> np.ndarray:
    """Compute log returns r_t = ln(P_t / P_{t-1}) * 100 for numerical stability."""
    returns = np.diff(np.log(prices)) * 100.0
    return returns


def evaluate_walk_forward_egarch(returns: np.ndarray, train_window: int = 1500, step: int = 50) -> dict:
    """
    Perform rolling walk-forward evaluation of EGARCH(1,1).
    For each window, fits model on trailing `train_window` returns,
    forecasts 1-step conditional variance sigma^2, and compares to
    realized 5-bar volatility.
    """
    from arch import arch_model

    forecast_sigmas = []
    realized_sigmas = []

    n = len(returns)
    eval_indices = range(train_window, n - 5, step)

    logger.info("Starting rolling walk-forward evaluation (%d windows)...", len(eval_indices))

    for idx in eval_indices:
        train_slice = returns[idx - train_window : idx]
        # Realized vol: std of next 5 bars
        realized_vol = float(np.std(returns[idx : idx + 5]))

        try:
            am = arch_model(train_slice, mean="Constant", vol="EGARCH", p=1, o=1, q=1, dist="normal")
            res = am.fit(disp="off", show_warning=False)
            forecast = res.forecast(horizon=1)
            var_pred = forecast.variance.values[-1, 0]
            vol_pred = np.sqrt(max(1e-6, var_pred))

            forecast_sigmas.append(vol_pred)
            realized_sigmas.append(realized_vol)
        except Exception:
            continue

    f_arr = np.array(forecast_sigmas)
    r_arr = np.array(realized_sigmas)

    if len(f_arr) == 0:
        return {"mae": 0.0, "rmse": 0.0, "qlike": 0.0, "n_evals": 0}

    # Loss metrics
    mae = float(np.mean(np.abs(f_arr - r_arr)))
    rmse = float(np.sqrt(np.mean((f_arr - r_arr) ** 2)))
    # QLIKE: ln(f_var) + r_var / f_var
    f_var = np.maximum(1e-6, f_arr ** 2)
    r_var = r_arr ** 2
    qlike = float(np.mean(np.log(f_var) + r_var / f_var))

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "qlike": round(qlike, 4),
        "n_evals": len(f_arr),
        "mean_forecast_vol": round(float(np.mean(f_arr)), 4),
        "mean_realized_vol": round(float(np.mean(r_arr)), 4),
    }


def fit_final_egarch_model(returns: np.ndarray) -> dict:
    """Fit EGARCH(1,1) on full dataset and return parameter dictionary."""
    from arch import arch_model

    am = arch_model(returns, mean="Constant", vol="EGARCH", p=1, o=1, q=1, dist="normal")
    res = am.fit(disp="off")

    params = {k: float(v) for k, v in res.params.items()}

    model_dict = {
        "model_type": "EGARCH(1,1)",
        "fitted_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(returns),
        "parameters": params,
        "log_likelihood": round(float(res.loglikelihood), 2),
        "aic": round(float(res.aic), 2),
        "bic": round(float(res.bic), 2),
    }

    return model_dict


def main():
    logger.info("=" * 60)
    logger.info("AEGIS EGARCH VOLATILITY MODEL TRAINER")
    logger.info("=" * 60)

    prices = fetch_xauusd_history(count=5000)
    returns = compute_log_returns(prices)
    logger.info("Computed %d log returns. Mean: %.4f%%, Std: %.4f%%", len(returns), np.mean(returns), np.std(returns))

    # 1. Walk-forward validation
    eval_metrics = evaluate_walk_forward_egarch(returns, train_window=1500, step=50)

    print()
    print("=" * 60)
    print("  EGARCH WALK-FORWARD EVALUATION METRICS")
    print("=" * 60)
    print(f"  Evaluation Windows : {eval_metrics['n_evals']}")
    print(f"  Mean Forecast Vol  : {eval_metrics['mean_forecast_vol']:.4f}%")
    print(f"  Mean Realized Vol  : {eval_metrics['mean_realized_vol']:.4f}%")
    print(f"  MAE (Volatility)   : {eval_metrics['mae']:.4f}")
    print(f"  RMSE (Volatility)  : {eval_metrics['rmse']:.4f}")
    print(f"  QLIKE Loss         : {eval_metrics['qlike']:.4f}")
    print("=" * 60)
    print()

    # 2. Fit final model
    logger.info("Fitting final EGARCH(1,1) model on full dataset...")
    final_model = fit_final_egarch_model(returns)
    final_model["walk_forward_metrics"] = eval_metrics

    # Save artifact
    MODEL_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_OUT_PATH, "w") as f:
        json.dump(final_model, f, indent=2)

    logger.info("EGARCH model artifact saved to %s", MODEL_OUT_PATH)
    print(f"Model parameters saved: {json.dumps(final_model['parameters'], indent=2)}")


if __name__ == "__main__":
    main()
