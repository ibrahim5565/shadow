"""
Aegis-Gold v4.0 — Phase 3 ML Retraining (Profit-Factor Optimised)
Weekly auto-retrain of XGBoost model from journal data.

PROFIT FACTOR OPTIMIZATION:
- Training samples are weighted by profit magnitude (larger wins/losses = higher weight)
- This makes the model optimize for PF rather than raw accuracy
- High-quality setups that contribute most to gross profit get learned preferentially

ONLY activate after 200+ trades with profitable base strategy.
"""

import os
import csv
import math
import logging
from datetime import datetime, timezone

logger = logging.getLogger("aegis.retrain")

JOURNAL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "journal.csv")
MODEL_PATH = os.path.join(os.path.dirname(__file__), "xgboost_model.json")
MIN_TRADES = 200


def load_journal_data():
    """
    Load trade journal and build feature/label arrays with PF-aware sample weights.

    Returns:
        features: list of feature vectors
        labels: list of binary labels (1=win, 0=loss)
        sample_weights: list of profit-magnitude-based weights
    """
    if not os.path.exists(JOURNAL_PATH):
        logger.warning("No journal file found at %s", JOURNAL_PATH)
        return None, None, None

    features = []
    labels = []
    profits = []

    with open(JOURNAL_PATH, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                pnl = float(row.get("pnl_points", 0) or 0)
                velocity = float(row.get("velocity_tps", 0) or 0)
                momentum = float(row.get("momentum_score", 0) or 0)
                spread = float(row.get("spread_at_entry", 0) or 0)

                # Session encoding
                session = row.get("session", "ASIAN")
                session_val = {
                    "LONDON": 1.0, "NY": 0.8, "OVERLAP": 0.9, "ASIAN": 0.5
                }.get(session, 0.5)

                # Time features
                ts = row.get("timestamp", "")
                if ts:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    hour = dt.hour + dt.minute / 60.0
                    time_sin = math.sin(2 * math.pi * hour / 24)
                    time_cos = math.cos(2 * math.pi * hour / 24)
                else:
                    time_sin = 0.0
                    time_cos = 0.0

                features.append([
                    velocity, momentum, spread,
                    session_val, time_sin, time_cos,
                ])
                labels.append(1 if pnl > 0 else 0)
                profits.append(pnl)

            except (ValueError, KeyError) as exc:
                continue

    if not features:
        return None, None, None

    # Compute profit-factor-aware sample weights
    # Same logic as ML ensemble: larger profits/losses get higher weight
    import numpy as np
    profits_arr = np.array(profits)
    abs_profits = np.abs(profits_arr)
    max_profit = abs_profits.max() if abs_profits.max() > 0 else 1.0
    norm_profits = abs_profits / max_profit
    sample_weights = 0.1 + norm_profits  # base weight + magnitude contribution

    gross_profit = sum(p for p in profits if p > 0)
    gross_loss = abs(sum(p for p in profits if p < 0))
    dataset_pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    logger.info(
        f"Loaded {len(features)} trades | Dataset PF: {dataset_pf:.3f} | "
        f"Sample weight mean: {sample_weights.mean():.3f}"
    )

    return features, labels, sample_weights.tolist()


def retrain():
    """
    Retrain XGBoost model from journal data with profit-factor optimization.

    Uses profit-magnitude-based sample weighting so the model learns to
    maximize profit factor rather than raw accuracy.
    """
    features, labels, sample_weights = load_journal_data()

    if features is None or len(features) < MIN_TRADES:
        logger.info(
            "Not enough trades for retraining (%d/%d required)",
            len(features) if features else 0, MIN_TRADES,
        )
        return False

    try:
        import xgboost as xgb
        import numpy as np

        X = np.array(features)
        y = np.array(labels)
        w = np.array(sample_weights)

        # 80/20 split
        split = int(len(X) * 0.8)
        X_train, X_test = X[:split], X[split:]
        y_train, y_test = y[:split], y[split:]
        w_train, w_test = w[:split], w[split:]

        dtrain = xgb.DMatrix(X_train, label=y_train, weight=w_train)
        dtest  = xgb.DMatrix(X_test,  label=y_test,  weight=w_test)

        params = {
            "objective": "binary:logistic",
            "eval_metric": "auc",
            "max_depth": 4,
            "eta": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 3,
            "seed": 42,
        }

        logger.info("[XGB] Training with profit-factor sample weighting...")
        model = xgb.train(
            params, dtrain,
            num_boost_round=100,
            evals=[(dtrain, "train"), (dtest, "test")],
            early_stopping_rounds=10,
            verbose_eval=False,
        )

        model.save_model(MODEL_PATH)
        logger.info("Model retrained and saved to %s", MODEL_PATH)

        # Evaluate
        preds = model.predict(dtest)
        accuracy = sum(
            (p >= 0.5) == y for p, y in zip(preds, y_test)
        ) / len(y_test)
        logger.info("Test accuracy: %.2f%%", accuracy * 100)

        return True

    except ImportError:
        logger.error("XGBoost not installed. Run: pip install xgboost")
        return False
    except Exception as exc:
        logger.error("Retrain failed: %s", exc)
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("═══ Aegis-Gold v4.0 — ML Retrain ═══")
    success = retrain()
    if success:
        print("✅ Model retrained successfully")
    else:
        print("❌ Retraining skipped or failed")
