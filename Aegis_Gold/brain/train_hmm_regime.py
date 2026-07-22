"""
===========================================================================
AEGIS GOLD — HMM Regime Classifier Trainer (Quant Features - Step 2)
===========================================================================

PURPOSE:
--------
Fits a 3-State Gaussian Hidden Markov Model (HMM) on market features:
  - Feature 1: Log Returns r_t
  - Feature 2: Log Volatility ln(sigma_t)
  - Feature 3: Trend Strength (ADX)

Identifies 3 market regimes:
  - Regime 0: Low Volatility / Ranging
  - Regime 1: Moderate Volatility / Trending
  - Regime 2: High Volatility / News / Market Shock

Outputs state transition matrix, regime parameters, stationary distribution,
and saves the model artifact to models/hmm_regime_model.json.

USAGE:
    .venv_cuda\\Scripts\\python.exe -m brain.train_hmm_regime
===========================================================================
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from hmmlearn.hmm import GaussianHMM

BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from brain.train_egarch import fetch_xauusd_history, compute_log_returns

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aegis.train_hmm_regime")

MODEL_OUT_PATH = BASE_DIR / "models" / "hmm_regime_model.json"


def compute_adx_surrogate(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute surrogate ADX (trend strength 0-100) from price series."""
    n = len(prices)
    adx = np.zeros(n)
    if n <= period * 2:
        return adx

    returns = np.diff(prices, prepend=prices[0])
    abs_returns = np.abs(returns)

    # Directional movement approximation
    pos_dm = np.where(returns > 0, returns, 0.0)
    neg_dm = np.where(returns < 0, -returns, 0.0)

    for i in range(period, n):
        tr_sum = np.sum(abs_returns[i - period : i])
        if tr_sum <= 0:
            continue
        pos_di = 100.0 * np.sum(pos_dm[i - period : i]) / tr_sum
        neg_di = 100.0 * np.sum(neg_dm[i - period : i]) / tr_sum
        di_diff = abs(pos_di - neg_di)
        di_sum = pos_di + neg_di
        dx = (di_diff / di_sum * 100.0) if di_sum > 0 else 0.0
        adx[i] = dx

    # Smooth ADX
    kernel = np.ones(period) / period
    adx_smooth = np.convolve(adx, kernel, mode="same")
    return np.clip(adx_smooth, 0.0, 100.0)


def build_feature_matrix(prices: np.ndarray, vol_window: int = 14) -> np.ndarray:
    """
    Construct N x 3 feature matrix:
      X[:, 0] = returns
      X[:, 1] = log rolling volatility
      X[:, 2] = ADX trend strength
    """
    returns = compute_log_returns(prices)
    n = len(returns)

    # Rolling volatility
    vol = np.zeros(n)
    for i in range(vol_window, n):
        vol[i] = np.std(returns[i - vol_window : i])
    vol[:vol_window] = vol[vol_window] if n > vol_window else 0.01
    vol = np.maximum(1e-4, vol)
    log_vol = np.log(vol)

    adx = compute_adx_surrogate(prices[1:], period=14)

    X = np.column_stack([returns, log_vol, adx])
    return X


def train_3state_hmm(X: np.ndarray) -> tuple:
    """
    Fit 3-state Gaussian HMM and reorder state labels by increasing volatility
    so that State 0 = Ranging, State 1 = Trending, State 2 = High Vol.
    """
    logger.info("Fitting 3-state Gaussian HMM on %d bars...", len(X))
    model = GaussianHMM(n_components=3, covariance_type="full", n_iter=200, random_state=42)
    model.fit(X)

    hidden_states = model.predict(X)

    # Sort state indices by mean volatility (feature column 1)
    vol_means = [float(model.means_[i, 1]) for i in range(3)]
    order = np.argsort(vol_means)

    # Remap transition matrix and means
    transmat_reordered = model.transmat_[order][:, order]
    means_reordered = model.means_[order]
    covars_reordered = model.covars_[order]

    state_labels = {
        0: "LOW_VOL_RANGING",
        1: "MODERATE_VOL_TRENDING",
        2: "HIGH_VOL_SHOCK",
    }

    # Stationary distribution
    eigvals, eigvecs = np.linalg.eig(transmat_reordered.T)
    stat_idx = np.argmin(np.abs(eigvals - 1.0))
    stat_dist = np.real(eigvecs[:, stat_idx])
    stat_dist = stat_dist / np.sum(stat_dist)

    return transmat_reordered, means_reordered, covars_reordered, stat_dist, state_labels, hidden_states


def main():
    logger.info("=" * 60)
    logger.info("AEGIS HMM REGIME CLASSIFIER TRAINER")
    logger.info("=" * 60)

    prices = fetch_xauusd_history(count=5000)
    X = build_feature_matrix(prices)

    transmat, means, covars, stat_dist, labels, states = train_3state_hmm(X)

    print()
    print("=" * 60)
    print("  HMM REGIME TRANSITION MATRIX (Row=From, Col=To)")
    print("=" * 60)
    for i in range(3):
        row_str = " ".join([f"{transmat[i, j]:.4f}" for j in range(3)])
        print(f"  From {labels[i]:<22} -> [{row_str}]")
    print("=" * 60)
    print()

    print("=" * 60)
    print("  STATE CHARACTERISTICS & STATIONARY DISTRIBUTION")
    print("=" * 60)
    for i in range(3):
        ret_m = means[i, 0]
        logvol_m = means[i, 1]
        adx_m = means[i, 2]
        vol_pct = np.exp(logvol_m)
        freq_pct = stat_dist[i] * 100.0
        print(f"  State {i} ({labels[i]}):")
        print(f"    Stationary Share : {freq_pct:.1f}%")
        print(f"    Mean Return      : {ret_m:+.4f}%")
        print(f"    Mean Volatility  : {vol_pct:.4f}% (log_vol={logvol_m:.3f})")
        print(f"    Mean ADX         : {adx_m:.1f}")
    print("=" * 60)

    # Save model artifact
    model_dict = {
        "model_type": "3-State Gaussian HMM",
        "fitted_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(X),
        "state_labels": labels,
        "transition_matrix": transmat.tolist(),
        "stationary_distribution": stat_dist.tolist(),
        "means": means.tolist(),
        "covariances": covars.tolist(),
    }

    MODEL_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_OUT_PATH, "w") as f:
        json.dump(model_dict, f, indent=2)

    logger.info("HMM Regime Model artifact saved to %s", MODEL_OUT_PATH)


if __name__ == "__main__":
    main()
