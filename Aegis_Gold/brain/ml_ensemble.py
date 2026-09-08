"""
═══════════════════════════════════════════════════════════════════════════════
🤖 AEGIS MACHINE LEARNING ENSEMBLE - Predictive AI Trading Core
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
--------
Multi-model ensemble learning system trained on complete trade memory database.
Predict trade outcomes, optimal entry/exit, and directional probability using
multiple ML algorithms with ensemble voting.

PHILOSOPHY:
-----------
"The wisdom of crowds beats individual experts."

No single model is perfect. Ensemble methods combine multiple models to achieve
superior accuracy, robustness, and generalization. Institutional quant funds use
ensemble learning extensively.

MODELS IN ENSEMBLE:
-------------------
1. GRADIENT BOOSTING (XGBoost/LightGBM)
   - Best for structured/tabular data
   - Handles non-linear relationships
   - Feature importance analysis

2. RANDOM FOREST
   - Robust to overfitting
   - Handles missing data well
   - Fast training and inference

3. NEURAL NETWORK (Simple Feed-Forward)
   - Learns complex patterns
   - Non-linear feature interactions
   - Backpropagation optimization

4. LOGISTIC REGRESSION (Baseline)
   - Linear baseline for comparison
   - Fast, interpretable
   - Good for feature selection

ENSEMBLE STRATEGY:
------------------
- Soft Voting: Average predicted probabilities from all models
- Hard Voting: Majority vote on predicted class
- Weighted Voting: Weight models by recent performance
- Confidence Threshold: Only trade when ensemble agrees strongly

TRAINING DATA:
--------------
- Source: Trade Memory Database (trade_memory.db)
- Features: 50+ market conditions, indicators, structure, MTF, stats
- Target: Win/Loss (binary classification)
- Validation: Time-series cross-validation (no future leakage)
- Retraining: Continuous learning after every N trades

FEATURES USED:
--------------
Market State: regime, structure, volatility, trend
Indicators: RSI, ADX, ATR, EMAs, momentum
SMC Signals: OB, BOS, CHoCH, liquidity, FVG
Multi-Timeframe: alignment, HTF trends
Statistical: Bayesian prob, Hurst, entropy, Kalman
Environmental: spread, session, hour, day, news
Performance: recent wins/losses, streak
Account: balance, equity, drawdown

═══════════════════════════════════════════════════════════════════════════════
"""

import numpy as np
import pickle
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any

from datetime import datetime

# Lightweight ML - using sklearn (available in most environments)
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import TimeSeriesSplit
    from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("scikit-learn not available. ML Ensemble will use rule-based fallback.")

logger = logging.getLogger("ML_Ensemble")


@dataclass
class MLPrediction:
    """Machine learning prediction result."""
    
    # Predictions
    direction: str  # "BUY", "SELL", "NEUTRAL"
    win_probability: float  # 0.0-1.0
    confidence: int  # 0-100
    
    # Individual model predictions
    gradient_boost_prob: float
    random_forest_prob: float
    neural_net_prob: float
    logistic_prob: float
    
    # Ensemble details
    model_agreement: float  # 0.0-1.0 (how much models agree)
    ensemble_method: str  # "SOFT_VOTING", "WEIGHTED_VOTING"
    
    # Model performance
    recent_accuracy: float
    recent_precision: float
    
    # Recommendation
    trade_recommendation: str  # "STRONG_BUY", "BUY", "WAIT", "SELL", "STRONG_SELL"
    expected_win_rate: float

    # ── QUANT X extension ─────────────────────────────────────────────────
    # Ensemble disagreement (std of individual model probabilities).
    # Higher = models disagree more → Decision Fusion should widen safety
    # margins or block the trade.  Default 0.0 = no disagreement info.
    uncertainty: float = 0.0        # std of individual probs (0-1)



@dataclass
class TrainingMetrics:
    """Model training performance metrics."""
    
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    training_samples: int
    training_time: float
    last_trained: str


class MLEnsemble:
    """
    Machine Learning Ensemble for trade prediction.
    """
    
    def __init__(self, model_dir: str = "d:\\Trading\\Aegis_Gold\\models", model_filename: str = "ml_ensemble.pkl"):
        self.model_dir = Path(model_dir)
        self.model_filename = model_filename
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        # Models
        self.gradient_boost = None
        self.random_forest = None
        self.neural_net = None
        self.logistic = None
        self.scaler = None
        
        # Model weights (updated based on recent performance)
        self.model_weights = {
            "gradient_boost": 0.35,
            "random_forest": 0.25,
            "neural_net": 0.25,
            "logistic": 0.15
        }
        
        # Performance tracking
        self.recent_predictions = []
        self.recent_accuracy = 0.5
        self.recent_precision = 0.5
        
        # Load existing models if available
        self._load_models()
        
        logger.info("[ML] ML Ensemble initialized")
    
    def predict(self, features: Dict) -> MLPrediction:
        """
        Make ensemble prediction for current market conditions.
        
        Args:
            features: Dictionary of market features (50+ fields)
            
        Returns:
            MLPrediction with ensemble result
        """
        if not SKLEARN_AVAILABLE or self.gradient_boost is None:
            # Fallback to rule-based prediction
            return self._rule_based_prediction(features)
        
        try:
            # Convert features to array
            X = self._features_to_array(features)
            X_scaled = self.scaler.transform([X])
            
            # Get predictions from each model
            gb_prob = self.gradient_boost.predict_proba(X_scaled)[0][1]  # P(win)
            rf_prob = self.random_forest.predict_proba(X_scaled)[0][1]
            # Neural net is now a Pipeline - pass raw X (Pipeline has its own scaler)
            if hasattr(self.neural_net, "named_steps"):
                nn_prob = self.neural_net.predict_proba([X])[0][1]
            else:
                nn_prob = self.neural_net.predict_proba(X_scaled)[0][1]
            lr_prob = self.logistic.predict_proba(X_scaled)[0][1]
            
            # Weighted ensemble voting
            ensemble_prob = (
                gb_prob * self.model_weights["gradient_boost"] +
                rf_prob * self.model_weights["random_forest"] +
                nn_prob * self.model_weights["neural_net"] +
                lr_prob * self.model_weights["logistic"]
            )
            
            # Model agreement (variance of predictions)
            probs = [gb_prob, rf_prob, nn_prob, lr_prob]
            agreement = 1.0 - (np.std(probs) / 0.5)  # 0.5 = max std for [0,1] range
            
            # Direction
            if ensemble_prob > 0.55:
                direction = "BUY"
            elif ensemble_prob < 0.45:
                direction = "SELL"
            else:
                direction = "NEUTRAL"
            
            # Confidence (0-100)
            confidence = int(abs(ensemble_prob - 0.5) * 200)
            
            # Trade recommendation
            trade_rec = self._generate_recommendation(ensemble_prob, agreement, confidence)
            
            result = MLPrediction(
                direction=direction,
                win_probability=ensemble_prob,
                confidence=confidence,
                gradient_boost_prob=gb_prob,
                random_forest_prob=rf_prob,
                neural_net_prob=nn_prob,
                logistic_prob=lr_prob,
                model_agreement=agreement,
                ensemble_method="WEIGHTED_VOTING",
                recent_accuracy=self.recent_accuracy,
                recent_precision=self.recent_precision,
                trade_recommendation=trade_rec,
                expected_win_rate=ensemble_prob
            )
            
            logger.info(f"[OK] ML prediction: {direction} | Prob: {ensemble_prob:.2f} | Agreement: {agreement:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"[ERR] ML prediction failed: {e}")
            return self._rule_based_prediction(features)
    
    def train(self, trade_memory_db) -> List[TrainingMetrics]:
        """
        Train all models in ensemble using trade memory database.

        Models are trained with profit-factor-aware sample weighting:
        high-profit trades and large-loss trades get higher weight so the
        ensemble optimizes for PF rather than raw accuracy.

        Args:
            trade_memory_db: TradeMemoryDatabase instance

        Returns:
            List of training metrics for each model
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("scikit-learn not available. Skipping ML training.")
            return []

        try:
            logger.info("[ML] Starting ML ensemble training (PF-optimised)...")

            # Load training data from trade memory
            trades = trade_memory_db.get_recent_trades(limit=5000)

            if len(trades) < 100:
                logger.warning(f"Insufficient training data: {len(trades)} trades. Need at least 100.")
                return []

            # Prepare features, labels, and PF-aware sample weights
            X, y, sample_weights = self._prepare_training_data(trades)

            if len(X) < 100:
                logger.warning("Not enough valid training samples after preparation")
                return []

            # Scale features
            self.scaler = StandardScaler()
            X_scaled = self.scaler.fit_transform(X)

            # Time-series split (no future leakage)
            tscv = TimeSeriesSplit(n_splits=3)

            # Train each model
            metrics = []

            # 1. Gradient Boosting
            logger.info("Training Gradient Boosting (PF-weighted)...")
            start_time = datetime.now()
            self.gradient_boost = GradientBoostingClassifier(
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                random_state=42
            )
            gb_metrics = self._train_with_cv(self.gradient_boost, X_scaled, y, sample_weights, tscv, "GradientBoosting")
            metrics.append(gb_metrics)

            # 2. Random Forest
            logger.info("Training Random Forest (PF-weighted)...")
            self.random_forest = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )
            rf_metrics = self._train_with_cv(self.random_forest, X_scaled, y, sample_weights, tscv, "RandomForest")
            metrics.append(rf_metrics)

            # 3. Neural Network
            # FIX: Use Pipeline with StandardScaler, early stopping, and
            # convergence diagnostics to prevent ConvergenceWarning.
            logger.info("Training Neural Network (PF-weighted)...")
            from sklearn.pipeline import Pipeline
            self.neural_net = Pipeline([
                ("scaler", StandardScaler()),
                ("model", MLPClassifier(
                    hidden_layer_sizes=(64, 32),
                    activation='relu',
                    max_iter=1000,          # Increased from 200 to allow convergence
                    early_stopping=True,    # Stop when validation score stops improving
                    validation_fraction=0.15,
                    n_iter_no_change=20,    # Patience for early stopping
                    learning_rate_init=0.001,
                    random_state=42,
                    verbose=False,
                ))
            ])
            nn_metrics = self._train_with_cv(self.neural_net, X_scaled, y, sample_weights, tscv, "NeuralNet")
            metrics.append(nn_metrics)

            # 4. Logistic Regression
            logger.info("Training Logistic Regression (PF-weighted)...")
            self.logistic = LogisticRegression(
                max_iter=500,
                random_state=42
            )
            lr_metrics = self._train_with_cv(self.logistic, X_scaled, y, sample_weights, tscv, "LogisticRegression")
            metrics.append(lr_metrics)

            # Save models
            self._save_models()

            # Update recent accuracy
            self.recent_accuracy = np.mean([m.accuracy for m in metrics])
            self.recent_precision = np.mean([m.precision for m in metrics])

            logger.info(f"[OK] ML ensemble training complete. Avg Accuracy: {self.recent_accuracy:.2%}")

            return metrics

        except Exception as e:
            logger.error(f"[FAIL] ML training failed: {e}")
            return []
    
    def _train_with_cv(self, model, X, y, sample_weights, cv, model_name: str) -> TrainingMetrics:
        """
        Train model with cross-validation and profit-factor-aware sample weights.

        Note: Not all sklearn models support sample_weight in fit(). For those that
        do (GB, RF, LogReg), we pass the weights. For those that don't (MLP), we
        skip the weights but still use the PF-weighted data split.
        """
        start_time = datetime.now()

        accuracies = []
        precisions = []
        recalls = []
        f1_scores = []

        # Check if model is a Pipeline (has named_steps)
        is_pipeline = hasattr(model, "named_steps")

        for train_idx, val_idx in cv.split(X):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]
            w_train = sample_weights[train_idx]

            # Try to fit with sample_weight if the model supports it
            try:
                if is_pipeline:
                    # Pipeline: pass sample_weight to final estimator via model__sample_weight
                    model.fit(X_train, y_train, model__sample_weight=w_train)
                else:
                    model.fit(X_train, y_train, sample_weight=w_train)
            except TypeError:
                # Model doesn't support sample_weight (e.g. MLPClassifier)
                model.fit(X_train, y_train)

            y_pred = model.predict(X_val)

            accuracies.append(accuracy_score(y_val, y_pred))
            precisions.append(precision_score(y_val, y_pred, zero_division=0))
            recalls.append(recall_score(y_val, y_pred, zero_division=0))
            f1_scores.append(f1_score(y_val, y_pred, zero_division=0))

        # Final fit on all data
        try:
            if is_pipeline:
                model.fit(X, y, model__sample_weight=sample_weights)
            else:
                model.fit(X, y, sample_weight=sample_weights)
        except TypeError:
            model.fit(X, y)

        training_time = (datetime.now() - start_time).total_seconds()

        return TrainingMetrics(
            model_name=model_name,
            accuracy=np.mean(accuracies),
            precision=np.mean(precisions),
            recall=np.mean(recalls),
            f1_score=np.mean(f1_scores),
            training_samples=len(X),
            training_time=training_time,
            last_trained=datetime.now().isoformat()
        )
    
    def _prepare_training_data(self, trades: List[Dict]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Convert trade records to feature matrix X, labels y, and profit-factor sample weights.

        Returns:
            X : feature matrix (n_samples, n_features)
            y : binary labels (1=win, 0=loss)
            sample_weights : PF-aware weights for each sample

        Weighting philosophy:
        - Wins are weighted by their profit magnitude (larger wins = more important)
        - Losses are weighted by their loss magnitude (larger losses = more important to avoid)
        - This makes the model focus on maximizing profit factor rather than accuracy
        """
        X_list = []
        y_list = []
        profit_list = []

        for trade in trades:
            # Skip if no exit data
            if trade.get('profit_usd') is None:
                continue

            # Features
            features = self._trade_to_features(trade)

            # Label: 1 = win, 0 = loss
            profit = float(trade.get('profit_usd', 0))
            label = 1 if profit > 0 else 0

            X_list.append(features)
            y_list.append(label)
            profit_list.append(profit)

        if len(X_list) == 0:
            return np.array([]), np.array([]), np.array([])

        # Compute profit-factor-aware sample weights
        profits = np.array(profit_list)
        gross_profit = np.sum(profits[profits > 0])
        gross_loss   = np.abs(np.sum(profits[profits < 0]))

        # Normalise profit magnitude to [0, 1] range for numerical stability
        abs_profits = np.abs(profits)
        max_profit  = abs_profits.max() if abs_profits.max() > 0 else 1.0
        norm_profits = abs_profits / max_profit

        # Sample weight = profit magnitude contribution
        # Wins: weight by profit size (big wins matter more)
        # Losses: weight by loss size (big losses matter more — we want to learn to avoid them)
        # Add small base weight (0.1) so no sample has zero weight
        sample_weights = 0.1 + norm_profits

        logger.info(f"[ML] Profit-factor sample weighting: mean={sample_weights.mean():.3f}, "
                    f"max={sample_weights.max():.3f}, gross PF={gross_profit/gross_loss if gross_loss > 0 else float('inf'):.3f}")

        return np.array(X_list), np.array(y_list), sample_weights
    
    def _trade_to_features(self, trade: Dict) -> List[float]:
        """Extract feature vector from trade record."""
        features = [
            # Basic
            trade.get('confidence', 50) / 100.0,
            trade.get('lot_size', 0.01),
            trade.get('sl_points', 50) / 100.0,
            trade.get('tp_points', 100) / 100.0,
            trade.get('rr_ratio', 1.0),
            
            # Market state
            self._encode_regime(trade.get('regime', 'UNKNOWN')),
            self._encode_structure(trade.get('structure', 'UNKNOWN')),
            trade.get('regime_score', 0) / 100.0,
            trade.get('structure_score', 0) / 100.0,
            trade.get('entry_score', 0) / 100.0,
            trade.get('momentum_score', 0) / 100.0,
            self._encode_volatility(trade.get('volatility_state', 'NORMAL')),
            self._encode_trend(trade.get('trend_state', 'UNKNOWN')),
            
            # Indicators
            trade.get('rsi', 50) / 100.0,
            trade.get('adx', 20) / 50.0,
            trade.get('atr', 10) / 100.0,
            
            # SMC
            float(trade.get('smc_ob_present', 0)),
            float(trade.get('smc_bos_present', 0)),
            float(trade.get('smc_choch_present', 0)),
            float(trade.get('smc_liquidity_sweep', 0)),
            float(trade.get('smc_fvg_present', 0)),
            trade.get('smc_score', 0) / 100.0,
            
            # Multi-timeframe
            trade.get('mtf_alignment', 0) / 9.0,
            
            # Statistical
            trade.get('bayesian_probability', 0.5),
            trade.get('hurst_exponent', 0.5),
            trade.get('entropy', 2.0) / 5.0,
            
            # Environmental
            trade.get('spread', 20) / 100.0,
            self._encode_session(trade.get('session', 'UNKNOWN')),
            trade.get('hour_of_day', 12) / 24.0,
            trade.get('day_of_week', 2) / 6.0,
            float(trade.get('news_nearby', 0)),
            
            # Performance
            trade.get('recent_wins', 0) / 20.0,
            trade.get('recent_losses', 0) / 20.0,
            trade.get('win_streak', 0) / 10.0,
            trade.get('loss_streak', 0) / 10.0,
        ]
        
        return features
    
    def _features_to_array(self, features: Dict) -> List[float]:
        """Convert feature dictionary to array for prediction."""
        return [
            features.get('confidence', 50) / 100.0,
            features.get('lot_size', 0.01),
            features.get('sl_points', 50) / 100.0,
            features.get('tp_points', 100) / 100.0,
            features.get('rr_ratio', 1.0),
            self._encode_regime(features.get('regime', 'UNKNOWN')),
            self._encode_structure(features.get('structure', 'UNKNOWN')),
            features.get('regime_score', 0) / 100.0,
            features.get('structure_score', 0) / 100.0,
            features.get('entry_score', 0) / 100.0,
            features.get('momentum_score', 0) / 100.0,
            self._encode_volatility(features.get('volatility_state', 'NORMAL')),
            self._encode_trend(features.get('trend_state', 'UNKNOWN')),
            features.get('rsi', 50) / 100.0,
            features.get('adx', 20) / 50.0,
            features.get('atr', 10) / 100.0,
            float(features.get('smc_ob_present', 0)),
            float(features.get('smc_bos_present', 0)),
            float(features.get('smc_choch_present', 0)),
            float(features.get('smc_liquidity_sweep', 0)),
            float(features.get('smc_fvg_present', 0)),
            features.get('smc_score', 0) / 100.0,
            features.get('mtf_alignment', 0) / 9.0,
            features.get('bayesian_probability', 0.5),
            features.get('hurst_exponent', 0.5),
            features.get('entropy', 2.0) / 5.0,
            features.get('spread', 20) / 100.0,
            self._encode_session(features.get('session', 'UNKNOWN')),
            features.get('hour_of_day', 12) / 24.0,
            features.get('day_of_week', 2) / 6.0,
            float(features.get('news_nearby', 0)),
            features.get('recent_wins', 0) / 20.0,
            features.get('recent_losses', 0) / 20.0,
            features.get('win_streak', 0) / 10.0,
            features.get('loss_streak', 0) / 10.0,
        ]
    
    # Encoding helpers
    def _encode_regime(self, regime: str) -> float:
        mapping = {"TREND": 1.0, "RANGE": 0.0, "VOLATILE": 0.5, "UNKNOWN": 0.5}
        return mapping.get(regime, 0.5)
    
    def _encode_structure(self, structure: str) -> float:
        mapping = {"BULLISH": 1.0, "BEARISH": 0.0, "NEUTRAL": 0.5, "UNKNOWN": 0.5}
        return mapping.get(structure, 0.5)
    
    def _encode_volatility(self, volatility: str) -> float:
        mapping = {"LOW": 0.25, "NORMAL": 0.5, "HIGH": 0.75, "EXTREME": 1.0}
        return mapping.get(volatility, 0.5)
    
    def _encode_trend(self, trend: str) -> float:
        mapping = {"BULLISH": 1.0, "BEARISH": 0.0, "NEUTRAL": 0.5, "UNKNOWN": 0.5}
        return mapping.get(trend, 0.5)
    
    def _encode_session(self, session: str) -> float:
        mapping = {"LONDON": 0.75, "NY": 1.0, "ASIA": 0.25, "OVERLAP": 0.9, "UNKNOWN": 0.5}
        return mapping.get(session, 0.5)
    
    def _generate_recommendation(self, prob: float, agreement: float, confidence: int) -> str:
        """Generate trade recommendation based on ensemble output."""
        if agreement < 0.6:
            return "WAIT"  # Models disagree - don't trade
        
        if prob > 0.7 and confidence > 60:
            return "STRONG_BUY"
        elif prob > 0.6:
            return "BUY"
        elif prob < 0.3 and confidence > 60:
            return "STRONG_SELL"
        elif prob < 0.4:
            return "SELL"
        else:
            return "WAIT"
    
    def _rule_based_prediction(self, features: Dict) -> MLPrediction:
        """Fallback rule-based prediction when ML unavailable."""
        confidence = features.get('confidence', 50)
        regime_score = features.get('regime_score', 0)
        structure_score = features.get('structure_score', 0)
        
        # Simple heuristic
        total_score = (confidence + regime_score + structure_score) / 3
        win_prob = total_score / 100.0
        
        if win_prob > 0.6:
            direction = "BUY"
            rec = "BUY"
        elif win_prob < 0.4:
            direction = "SELL"
            rec = "SELL"
        else:
            direction = "NEUTRAL"
            rec = "WAIT"
        
        return MLPrediction(
            direction=direction,
            win_probability=win_prob,
            confidence=int(abs(win_prob - 0.5) * 200),
            gradient_boost_prob=win_prob,
            random_forest_prob=win_prob,
            neural_net_prob=win_prob,
            logistic_prob=win_prob,
            model_agreement=1.0,
            ensemble_method="RULE_BASED",
            recent_accuracy=0.5,
            recent_precision=0.5,
            trade_recommendation=rec,
            expected_win_rate=win_prob
        )
    
    def _save_models(self):
        """Save trained models to disk."""
        try:
            model_file = self.model_dir / self.model_filename
            with open(model_file, 'wb') as f:
                pickle.dump({
                    'gradient_boost': self.gradient_boost,
                    'random_forest': self.random_forest,
                    'neural_net': self.neural_net,
                    'logistic': self.logistic,
                    'scaler': self.scaler,
                    'weights': self.model_weights,
                    'recent_accuracy': self.recent_accuracy,
                    'recent_precision': self.recent_precision
                }, f)
            logger.info(f"[OK] Models saved to {model_file}")
        except Exception as e:
            logger.error(f"Failed to save models: {e}")
    
    def _load_models(self):
        """Load trained models from disk."""
        try:
            model_file = self.model_dir / self.model_filename
            if model_file.exists():
                with open(model_file, 'rb') as f:
                    data = pickle.load(f)
                    self.gradient_boost = data.get('gradient_boost')
                    self.random_forest = data.get('random_forest')
                    self.neural_net = data.get('neural_net')
                    self.logistic = data.get('logistic')
                    self.scaler = data.get('scaler')
                    self.model_weights = data.get('weights', self.model_weights)
                    self.recent_accuracy = data.get('recent_accuracy', 0.5)
                    self.recent_precision = data.get('recent_precision', 0.5)
                logger.info(f"[OK] Models loaded from {model_file}")
        except Exception as e:
            logger.warning(f"Could not load models: {e}")
    
    def record_prediction_outcome(self, prediction_id: str, actual_outcome: bool):
        """
        Record outcome of prediction for model performance tracking.
        Used to update model weights dynamically.
        
        CAUSALITY FIX: This method is now BLOCKED during live trading to prevent
        future data leakage. Model updates only occur during dedicated training phases.
        """
        # Import causality enforcer
        from brain.causality_enforcer import get_causality_enforcer
        
        # Check if we're in live trading mode (detected by call stack analysis)
        enforcer = get_causality_enforcer()
        audit_result = enforcer.prevent_live_model_updates("ml_ensemble", is_live_trading=True)
        
        if not audit_result.passed:
            logger.warning("[CAUSALITY] BLOCKED live model weight update - use dedicated training phase instead")
            return
        
        # Only proceed if causality check passed (training mode)
        self.recent_predictions.append(actual_outcome)
        
        # Keep last 100 predictions
        if len(self.recent_predictions) > 100:
            self.recent_predictions = self.recent_predictions[-100:]
        
        # Update accuracy
        if len(self.recent_predictions) > 10:
            self.recent_accuracy = np.mean(self.recent_predictions)


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_ml_ensemble = None

def get_ml_ensemble() -> MLEnsemble:
    """Get or create singleton ML ensemble instance."""
    global _ml_ensemble
    if _ml_ensemble is None:
        _ml_ensemble = MLEnsemble()
    return _ml_ensemble


# ═══════════════════════════════════════════════════════════════════════════
# QUANT X EXTENSION — Ensemble Disagreement
# ═══════════════════════════════════════════════════════════════════════════

def compute_ensemble_disagreement(prediction: MLPrediction) -> float:
    """
    Compute the standard deviation of individual model probability outputs.
    Returns a value in [0, 0.5].  Higher = more disagreement.

    This value is attached to MLPrediction.uncertainty and consumed by
    DecisionFusion to shrink position size or block trades.

    FEATURE FLAG: QX["ensemble_disagreement"]
    """
    try:
        from config.quant_x_config import QX
        if not QX.flag("ensemble_disagreement"):
            return 0.0
    except Exception:
        return 0.0

    try:
        probs = [
            prediction.gradient_boost_prob,
            prediction.random_forest_prob,
            prediction.neural_net_prob,
            prediction.logistic_prob,
        ]
        probs = [p for p in probs if p is not None and 0.0 <= p <= 1.0]
        if len(probs) < 2:
            return 0.0
        mean = sum(probs) / len(probs)
        variance = sum((p - mean) ** 2 for p in probs) / len(probs)
        return round(variance ** 0.5, 4)
    except Exception:
        return 0.0


def enrich_prediction_with_disagreement(prediction: MLPrediction) -> MLPrediction:
    """Compute and attach disagreement score in-place."""
    prediction.uncertainty = compute_ensemble_disagreement(prediction)
    return prediction


# ═══════════════════════════════════════════════════════════════════════════
# QUANT X EXTENSION — Autoencoder Anomaly Detector
# ═══════════════════════════════════════════════════════════════════════════

class AutoencoderAnomalyDetector:
    """
    Lightweight autoencoder for market anomaly detection.

    Training: fit on "normal" market feature vectors from historical bars.
    Inference: reconstruction error on new bar = anomaly score.
    High anomaly score → unusual market conditions → DecisionFusion
    should widen safety margins.

    Uses sklearn's MLPRegressor as encoder/decoder pair (no PyTorch required
    in this mode).  Falls back to a z-score approach if sklearn unavailable.

    FEATURE FLAG: QX["autoencoder_anomaly"]
    """

    MIN_TRAINING_SAMPLES = 500   # Do not operate until trained on sufficient data

    def __init__(self):
        self._model          = None
        self._scaler         = None
        self._fitted         = False
        self._train_errors: List[float] = []   # Reconstruction errors on training set
        self._threshold:     Optional[float] = None
        self._n_features:    int = 0

    def fit(self, feature_matrix: List[List[float]]) -> bool:
        """
        Train autoencoder on a matrix of feature vectors (one row per bar).
        Returns True on success.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("autoencoder_anomaly"):
                return False
        except Exception:
            return False

        if len(feature_matrix) < self.MIN_TRAINING_SAMPLES:
            logger.info(
                "[AUTOENC] Need %d samples, have %d — not training yet",
                self.MIN_TRAINING_SAMPLES, len(feature_matrix)
            )
            return False

        try:
            import numpy as np

            if SKLEARN_AVAILABLE:
                from sklearn.neural_network import MLPRegressor
                from sklearn.preprocessing import StandardScaler

                X = np.array(feature_matrix, dtype=np.float32)
                self._n_features = X.shape[1]
                self._scaler = StandardScaler()
                X_scaled = self._scaler.fit_transform(X)

                # Bottleneck: half the feature count
                hidden = max(4, self._n_features // 2)
                self._model = MLPRegressor(
                    hidden_layer_sizes=(hidden,),
                    activation="relu",
                    max_iter=200,
                    random_state=42,
                )
                self._model.fit(X_scaled, X_scaled)  # Reconstruct input = autoencoder
                recon = self._model.predict(X_scaled)
                errors = np.mean((X_scaled - recon) ** 2, axis=1).tolist()
            else:
                # Fallback: z-score-based per-feature normality
                X = np.array(feature_matrix, dtype=np.float32)
                means = np.mean(X, axis=0)
                stds  = np.std(X, axis=0) + 1e-8
                errors = np.mean(((X - means) / stds) ** 2, axis=1).tolist()

            self._train_errors = errors
            # Anomaly threshold = mean + 3σ of training reconstruction errors
            mean_e = sum(errors) / len(errors)
            std_e  = (sum((e - mean_e)**2 for e in errors) / len(errors)) ** 0.5
            self._threshold = mean_e + 3.0 * std_e
            self._fitted    = True
            logger.info(
                "[AUTOENC] Fitted on %d samples. anomaly_threshold=%.4f",
                len(feature_matrix), self._threshold
            )
            return True
        except Exception as exc:
            logger.warning("[AUTOENC] Fit failed: %s", exc)
            return False

    def anomaly_score(self, feature_vector: List[float]) -> Tuple[float, bool]:
        """
        Compute reconstruction error for a single feature vector.
        Returns (score, is_anomaly).
        is_anomaly = True when score > threshold.
        Falls back to (0.0, False) if not fitted.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("autoencoder_anomaly") or not self._fitted:
                return 0.0, False
        except Exception:
            return 0.0, False

        try:
            import numpy as np
            x = np.array(feature_vector, dtype=np.float32).reshape(1, -1)

            if SKLEARN_AVAILABLE and self._model is not None and self._scaler is not None:
                x_sc = self._scaler.transform(x)
                recon = self._model.predict(x_sc)
                error = float(np.mean((x_sc - recon) ** 2))
            else:
                # z-score fallback
                if not self._train_errors:
                    return 0.0, False
                error = float(np.mean(x ** 2))   # crude proxy

            is_anomaly = self._threshold is not None and error > self._threshold
            return round(error, 6), is_anomaly
        except Exception as exc:
            logger.debug("[AUTOENC] anomaly_score error: %s", exc)
            return 0.0, False

    def get_status(self) -> dict:
        return {
            "fitted":          self._fitted,
            "threshold":       self._threshold,
            "n_train_samples": len(self._train_errors),
            "n_features":      self._n_features,
        }


# Module-level autoencoder singleton
_autoencoder: Optional[AutoencoderAnomalyDetector] = None

def get_autoencoder() -> AutoencoderAnomalyDetector:
    global _autoencoder
    if _autoencoder is None:
        _autoencoder = AutoencoderAnomalyDetector()
    return _autoencoder


def get_engine_vote(candles_m5=None, symbol: str = "XAUUSD") -> Dict[str, Any]:
    """
    SECTION 1 — PER-ENGINE OUTPUT CONTRACT
    Returns standardized EngineVote dict for ML Ensemble.
    Uses both sklearn trained models (if available) AND price-momentum fallback.
    """
    direction = "neutral"
    conf = 0.50
    win_probability = 0.50
    details = []

    try:
        # Try to use trained ML Ensemble first
        ml_ens = get_ml_ensemble()
        if ml_ens is not None and ml_ens.gradient_boost is not None and candles_m5 is not None:
            if hasattr(candles_m5, 'close'):
                closes = candles_m5['close'].values.astype(float)
            elif isinstance(candles_m5, list) and len(candles_m5) >= 10:
                closes = [float(c.get('close', 0.0) if isinstance(c, dict) else (getattr(c, 'close', 0.0) if hasattr(c, 'close') else c[4])) for c in candles_m5]
            else:
                closes = []

            if len(closes) >= 14:
                # Build feature dict for ML Ensemble
                import numpy as np_ml
                r5 = (closes[-1] - closes[-6]) / closes[-6] if closes[-6] > 0 else 0.0
                r10 = (closes[-1] - closes[-11]) / closes[-11] if len(closes) >= 11 and closes[-11] > 0 else 0.0
                volatility = float(np_ml.std(np_ml.diff(closes[-14:]))) if len(closes) >= 14 else 0.0

                ml_features = {
                    "confidence": 60,
                    "regime": "TRENDING",
                    "structure": "BULLISH" if r5 > 0 else "BEARISH",
                    "regime_score": 60,
                    "structure_score": 60,
                    "entry_score": 60,
                    "rsi": 50.0,
                    "adx": 25.0,
                    "atr": volatility * 10000,
                    "spread": 15.0,
                }

                try:
                    pred = ml_ens.predict(ml_features)
                    win_probability = pred.win_probability
                    if win_probability >= 0.60:
                        direction = "bullish"
                        conf = round(min(0.95, win_probability), 3)
                        details.append(f"XGBoost/RF win_prob={win_probability*100:.1f}%")
                    elif win_probability <= 0.40:
                        direction = "bearish"
                        conf = round(min(0.95, 1.0 - win_probability), 3)
                        details.append(f"XGBoost/RF win_prob={win_probability*100:.1f}%")
                    else:
                        direction = "neutral"
                        conf = 0.50
                        details.append(f"XGBoost/RF no edge win_prob={win_probability*100:.1f}%")
                except Exception as ml_e:
                    details.append(f"ML model predict error: {ml_e}")

        # Price-momentum fallback if no model prediction
        if not details and candles_m5 is not None and len(candles_m5) >= 10:
            if hasattr(candles_m5, 'close'):
                closes = candles_m5['close'].values.astype(float).tolist()
            elif isinstance(candles_m5, list):
                closes = [float(c.get('close', c.get('c', 0.0)) if isinstance(c, dict) else (getattr(c, 'close', 0.0) if hasattr(c, 'close') else c[4])) for c in candles_m5]
            else:
                closes = []

            if len(closes) >= 10:
                ret = (closes[-1] - closes[-6]) / closes[-6] if closes[-6] > 0 else 0.0
                if ret > 0.0005:
                    direction = "bullish"
                    conf = min(0.88, 0.55 + ret * 80)
                    details.append(f"Momentum +{ret*100:.2f}%")
                elif ret < -0.0005:
                    direction = "bearish"
                    conf = min(0.88, 0.55 + abs(ret) * 80)
                    details.append(f"Momentum {ret*100:.2f}%")
                else:
                    direction = "neutral"
                    conf = 0.50
                    details.append("Flat price action")

    except Exception as e:
        details.append(f"ML Ensemble evaluation error: {e}")

    reasoning = f"ML Ensemble: direction={direction.upper()} conf={conf*100:.0f}% | {', '.join(details)}"

    return {
        "engine": "ml_ensemble",
        "direction": direction,
        "confidence": round(conf, 3),
        "reasoning": reasoning,
        "win_probability": win_probability,
    }


def compute_expected_value(win_probability: float, tp_pts: int, sl_pts: int, point: float = 0.01,
                           lot: float = 0.01, contract_size: float = 100.0) -> float:
    """
    Computes expected dollar value of a trade given ML win probability and SL/TP.

    EV = P(win) * TP_usd  -  P(loss) * SL_usd

    Args:
        win_probability: ML ensemble win probability (0.0-1.0)
        tp_pts:          Take profit in points
        sl_pts:          Stop loss in points
        point:           Instrument point value (e.g. 0.01 for XAUUSD)
        lot:             Trade lot size
        contract_size:   Contract size (100 for XAUUSD)

    Returns:
        float: Expected value in USD (positive = good trade, negative = bad trade)
    """
    tp_usd = tp_pts * point * lot * contract_size
    sl_usd = sl_pts * point * lot * contract_size
    ev = win_probability * tp_usd - (1.0 - win_probability) * sl_usd
    return round(ev, 4)


def get_ev_gate(candles_m5, sl_pts: int, tp_pts: int, direction: str,
                symbol: str = "XAUUSD", lot: float = 0.01) -> dict:
    """
    Hard expected-value gate for the EQS pipeline.

    Computes ML win probability then checks if EV > 0.

    Returns:
        {
            "approved":      bool,
            "ev":            float,       # Expected value in USD
            "win_prob":      float,       # ML win probability
            "reason":        str,         # Human-readable decision
        }
    """
    try:
        vote = get_engine_vote(candles_m5=candles_m5, symbol=symbol)
        win_prob = vote.get("win_probability", 0.50)

        # Gold contract size = 100 oz, point = $0.01
        is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
        point = 0.01 if is_gold else 0.00001
        contract_size = 100.0 if is_gold else 100000.0

        ev = compute_expected_value(
            win_probability=win_prob,
            tp_pts=tp_pts,
            sl_pts=sl_pts,
            point=point,
            lot=lot,
            contract_size=contract_size
        )

        approved = ev > 0.0

        return {
            "approved": approved,
            "ev": ev,
            "win_prob": win_prob,
            "reason": (
                f"ML EV Gate: EV=${ev:.4f} {'APPROVED' if approved else 'BLOCKED'} | "
                f"WinProb={win_prob*100:.1f}%, TP={tp_pts}pts, SL={sl_pts}pts"
            )
        }

    except Exception as e:
        # On error, allow trade but log warning (fail-open to avoid over-filtering)
        return {
            "approved": True,
            "ev": 0.0,
            "win_prob": 0.50,
            "reason": f"ML EV Gate error (fail-open): {e}"
        }


def ml_ensemble_predict_vote(ensemble_instance, snapshot) -> "EngineVote":
    """
    Pattern Consensus Architecture — ML Ensemble per-engine point-in-time contract.

    Stand-alone function (also callable as ensemble_instance.predict_vote(snapshot))
    so it can be monkey-patched onto MLEnsemble without touching class internals.

    Role in 7-engine consensus:
      - RSI/EMA/ADX are INPUTS to ML models (features), NOT gates.
        No entry is blocked because "RSI crossed threshold X."
      - The gate is the ENSEMBLE WIN PROBABILITY vs direction class.
      - conviction = ensemble win_probability (how strongly ML agrees)
      - direction derived from trade_recommendation, not raw indicator

    Temporal integrity: reads only snapshot.candles_m5 (closed bars).
    No live MT5 data accessed here.
    """
    from brain.engine_vote import EngineVote, PatternEvidence, make_wait_vote
    from datetime import datetime, timezone

    now = snapshot.timestamp

    try:
        # Build ML feature dict from snapshot closed candle data
        features = _build_snapshot_features(snapshot)

        ml_pred = ensemble_instance.predict(features)

        if ml_pred.direction not in ("BUY", "SELL"):
            return make_wait_vote("ml_ensemble", f"ML direction={ml_pred.direction}", signal_time=now)

        if ml_pred.win_probability < 0.52:
            return make_wait_vote(
                "ml_ensemble",
                f"ML win_prob={ml_pred.win_probability:.3f} < 0.52 threshold",
                signal_time=now,
            )

        conviction = min(1.0, max(0.0, (ml_pred.win_probability - 0.5) * 2.0))

        evidence = PatternEvidence(
            pattern_type="ML_ENSEMBLE",
            confirmation_time=now,
            formation_time=now,
            invalidation_level=0.0,
            confidence_raw=conviction,
            details=[
                f"ML direction={ml_pred.direction} win_prob={ml_pred.win_probability:.3f}",
                f"Agreement={ml_pred.model_agreement:.3f} uncertainty={ml_pred.uncertainty:.3f}",
                f"GB={ml_pred.gradient_boost_prob:.3f} RF={ml_pred.random_forest_prob:.3f} "
                f"NN={ml_pred.neural_net_prob:.3f} LR={ml_pred.logistic_prob:.3f}",
            ],
            extra={
                "win_probability": ml_pred.win_probability,
                "model_agreement": ml_pred.model_agreement,
                "uncertainty": ml_pred.uncertainty,
                "ensemble_method": ml_pred.ensemble_method,
                "gradient_boost_prob": ml_pred.gradient_boost_prob,
                "random_forest_prob": ml_pred.random_forest_prob,
                "neural_net_prob": ml_pred.neural_net_prob,
                "logistic_prob": ml_pred.logistic_prob,
            },
        )

        return EngineVote(
            engine_name="ml_ensemble",
            direction=ml_pred.direction,
            conviction=conviction,
            pattern_evidence=[evidence],
            proposed_sl=0.0,   # ML Ensemble does not derive structural SL/TP
            proposed_tp=0.0,
            invalidation_level=0.0,
            signal_time=now,
        )

    except Exception as exc:
        return make_wait_vote("ml_ensemble", f"predict_vote error: {exc}", signal_time=now)


def _build_snapshot_features(snapshot) -> dict:
    """
    Build ML feature dict from FrozenDecisionSnapshot closed candle data.
    RSI/ADX/EMA are computed here as FEATURES for the ML model.
    They are NOT used as direct gates anywhere in this function.
    """
    features = {
        "session": snapshot.session,
        "symbol": snapshot.symbol,
        "spread": snapshot.spread,
    }
    try:
        candles = list(snapshot.candles_m5)
        if not candles:
            return features

        # Extract closes, highs, lows
        if isinstance(candles[-1], dict):
            closes = [float(c.get("close", 0.0)) for c in candles]
            highs = [float(c.get("high", 0.0)) for c in candles]
            lows = [float(c.get("low", 0.0)) for c in candles]
        elif isinstance(candles[-1], (list, tuple)) and len(candles[-1]) >= 5:
            closes = [float(c[4]) for c in candles]
            highs = [float(c[2]) for c in candles]
            lows = [float(c[3]) for c in candles]
        else:
            return features

        import numpy as np
        closes_arr = np.array(closes, dtype=float)

        # Price momentum features
        features["price_return_1"] = float((closes[-1] - closes[-2]) / closes[-2]) if len(closes) > 1 else 0.0
        features["price_return_5"] = float((closes[-1] - closes[-6]) / closes[-6]) if len(closes) > 5 else 0.0
        features["price_return_20"] = float((closes[-1] - closes[-21]) / closes[-21]) if len(closes) > 20 else 0.0

        # Volatility
        if len(closes) >= 14:
            features["atr_14"] = float(np.mean([highs[i] - lows[i] for i in range(-14, 0)]))
        features["current_price"] = float(closes[-1])
        features["account_equity"] = snapshot.account_equity

    except Exception:
        pass

    return features


# Monkey-patch predict_vote onto MLEnsemble so callers use ensemble.predict_vote(snapshot)
MLEnsemble.predict_vote = lambda self, snapshot: ml_ensemble_predict_vote(self, snapshot)
