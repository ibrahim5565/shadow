"""
═══════════════════════════════════════════════════════════════════════════════
📊 AEGIS STATISTICAL MATHEMATICS ENGINE - Quantitative Analysis Foundation
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
--------
Replace simple indicator logic with advanced probabilistic and statistical models.
Provide quantitative evidence for trading decisions rather than rule-of-thumb heuristics.

PHILOSOPHY:
-----------
"In God we trust. All others must bring data."

Markets are stochastic, not deterministic. Simple indicators give binary signals.
Statistical models give probability distributions. Institutional traders think in
probabilities, not certainties.

MATHEMATICAL MODELS:
--------------------
1. BAYESIAN INFERENCE
   - Calculate probability of direction given current evidence
   - Update priors based on recent outcomes
   - Account for model uncertainty

2. KALMAN FILTER
   - Optimal state estimation in noisy data
   - Smooth price trends from noise
   - Detect regime changes

3. HURST EXPONENT
   - Measure mean reversion vs trending behavior
   - H < 0.5: Mean reverting
   - H = 0.5: Random walk
   - H > 0.5: Trending

4. ENTROPY ANALYSIS
   - Market uncertainty quantification
   - High entropy = unpredictable (avoid)
   - Low entropy = predictable patterns

5. MONTE CARLO SIMULATION
   - Forward price projections with uncertainty bands
   - Risk assessment
   - Drawdown probability

6. FRACTAL DIMENSION
   - Market complexity measurement
   - Identify regime shifts

7. WAVELET ANALYSIS
   - Multi-scale time-frequency decomposition
   - Detect cycles at different scales

8. AUTOCORRELATION
   - Detect persistence or mean reversion
   - Optimal holding period estimation

═══════════════════════════════════════════════════════════════════════════════
"""

import numpy as np
from scipy import stats
from scipy.signal import welch
from dataclasses import dataclass
from typing import Tuple, List, Optional, Any
import logging

logger = logging.getLogger("StatisticalEngine")


@dataclass
class StatisticalAnalysis:
    """Complete statistical analysis result."""
    
    # Bayesian Analysis
    bayesian_bullish_prob: float  # 0.0-1.0
    bayesian_bearish_prob: float  # 0.0-1.0
    bayesian_neutral_prob: float  # 0.0-1.0
    bayesian_confidence: float    # 0.0-1.0
    
    # Kalman Filter
    kalman_trend: float           # Filtered price trend
    kalman_velocity: float        # Rate of change
    kalman_noise_ratio: float     # Signal/noise quality
    
    # Hurst Exponent
    hurst_exponent: float         # 0.0-1.0
    market_behavior: str          # "MEAN_REVERTING", "RANDOM_WALK", "TRENDING"
    persistence_score: int        # 0-100
    
    # Entropy
    entropy: float                # 0.0+
    predictability: str           # "HIGH", "MODERATE", "LOW", "CHAOTIC"
    entropy_score: int            # 0-100 (higher = more predictable)
    
    # Monte Carlo
    mc_expected_return: float     # Expected return over N periods
    mc_std_deviation: float       # Volatility
    mc_var_95: float              # Value at Risk (95%)
    mc_max_drawdown_prob: float   # Probability of >5% drawdown
    
    # Autocorrelation
    autocorr_lag1: float          # -1.0 to 1.0
    autocorr_optimal_hold: int    # Suggested holding period (bars)
    mean_reversion_strength: float # 0.0-1.0
    
    # Fractal Dimension
    fractal_dimension: float      # 1.0-2.0
    complexity: str               # "LOW", "MODERATE", "HIGH"
    
    # Overall Assessment
    statistical_edge: float       # 0.0-1.0 (probability of edge)
    recommended_direction: str    # "LONG", "SHORT", "NEUTRAL"
    confidence_level: int         # 0-100


class StatisticalEngine:
    """
    Advanced statistical and probabilistic analysis engine.
    """
    
    def __init__(self):
        # Bayesian priors (updated from historical data)
        self.prior_bullish = 0.33
        self.prior_bearish = 0.33
        self.prior_neutral = 0.34
        
        # Kalman filter state
        self.kalman_state = None
        self.kalman_covariance = None
        
        logger.info("[STAT] Statistical Engine initialized")
    
    def analyze(self, prices: Any, volumes: Optional[np.ndarray] = None) -> StatisticalAnalysis:
        """
        Perform comprehensive statistical analysis on price data.
        
        Args:
            prices: Array or DataFrame of prices (at least 50 points recommended)
            volumes: Optional volume data
            
        Returns:
            StatisticalAnalysis object with all metrics
        """
        if hasattr(prices, 'close'):
            prices_arr = prices['close'].values
        elif hasattr(prices, 'values'):
            prices_arr = prices.values.flatten()
        else:
            prices_arr = np.asarray(prices, dtype=float)

        if len(prices_arr) < 50:
            logger.warning("Insufficient data for statistical analysis")
            return self._default_analysis()
        
        try:
            # 1. Bayesian Analysis
            bayes_bull, bayes_bear, bayes_neut, bayes_conf = self._bayesian_inference(prices_arr)
            
            # 2. Kalman Filter
            kalman_trend, kalman_vel, kalman_noise = self._kalman_filter(prices_arr)
            
            # 3. Hurst Exponent
            hurst, behavior, persistence = self._hurst_exponent(prices_arr)
            
            # 4. Entropy
            entropy, predictability, entropy_score = self._entropy_analysis(prices_arr)
            
            # 5. Monte Carlo
            mc_return, mc_std, mc_var, mc_dd_prob = self._monte_carlo_simulation(prices_arr)
            
            # 6. Autocorrelation
            autocorr, optimal_hold, mean_rev = self._autocorrelation_analysis(prices_arr)
            
            # 7. Fractal Dimension
            fractal_dim, complexity = self._fractal_dimension(prices_arr)
            
            # 8. Overall Assessment
            stat_edge, direction, confidence = self._calculate_edge(
                bayes_bull, bayes_bear, hurst, entropy_score, kalman_noise, persistence
            )
            
            result = StatisticalAnalysis(
                bayesian_bullish_prob=bayes_bull,
                bayesian_bearish_prob=bayes_bear,
                bayesian_neutral_prob=bayes_neut,
                bayesian_confidence=bayes_conf,
                kalman_trend=kalman_trend,
                kalman_velocity=kalman_vel,
                kalman_noise_ratio=kalman_noise,
                hurst_exponent=hurst,
                market_behavior=behavior,
                persistence_score=persistence,
                entropy=entropy,
                predictability=predictability,
                entropy_score=entropy_score,
                mc_expected_return=mc_return,
                mc_std_deviation=mc_std,
                mc_var_95=mc_var,
                mc_max_drawdown_prob=mc_dd_prob,
                autocorr_lag1=autocorr,
                autocorr_optimal_hold=optimal_hold,
                mean_reversion_strength=mean_rev,
                fractal_dimension=fractal_dim,
                complexity=complexity,
                statistical_edge=stat_edge,
                recommended_direction=direction,
                confidence_level=confidence
            )
            
            logger.info(f"[OK] Statistical analysis complete | Edge: {stat_edge:.2f} | Direction: {direction}")
            return result
            
        except Exception as e:
            logger.error(f"[FAIL] Statistical analysis failed: {e}")
            return self._default_analysis()

    def calculate_features(self, prices: Any, volumes: Optional[np.ndarray] = None) -> StatisticalAnalysis:
        return self.analyze(prices, volumes=volumes)

    def calculate_all_features(self, prices: Any, volumes: Optional[np.ndarray] = None) -> StatisticalAnalysis:
        return self.analyze(prices, volumes=volumes)

    def extract_features(self, prices: Any, volumes: Optional[np.ndarray] = None) -> StatisticalAnalysis:
        return self.analyze(prices, volumes=volumes)

    def compute_features(self, prices: Any, volumes: Optional[np.ndarray] = None) -> StatisticalAnalysis:
        return self.analyze(prices, volumes=volumes)

    
    def _bayesian_inference(self, prices: np.ndarray) -> Tuple[float, float, float, float]:
        """
        Bayesian inference for directional probability.
        
        P(Direction|Evidence) = P(Evidence|Direction) * P(Direction) / P(Evidence)
        """
        # Calculate returns
        returns = np.diff(prices) / prices[:-1]
        
        # Recent evidence (last 20 bars)
        recent_returns = returns[-20:]
        
        # Likelihood functions
        # P(Evidence | Bullish): probability of seeing this data if market is bullish
        mean_return = np.mean(recent_returns)
        std_return = np.std(recent_returns)
        
        # Bullish likelihood: positive returns with low volatility
        if std_return > 0:
            z_score = mean_return / std_return
            likelihood_bull = stats.norm.cdf(z_score)  # 0.5 to 1.0 for positive momentum
            likelihood_bear = 1 - likelihood_bull
        else:
            likelihood_bull = 0.5
            likelihood_bear = 0.5
        
        # Neutral likelihood: high volatility or no clear direction
        volatility_factor = min(std_return * 1000, 1.0)  # Normalize
        likelihood_neutral = volatility_factor
        
        # Apply Bayes' theorem
        posterior_bull = likelihood_bull * self.prior_bullish
        posterior_bear = likelihood_bear * self.prior_bearish
        posterior_neut = likelihood_neutral * self.prior_neutral
        
        # Normalize
        total = posterior_bull + posterior_bear + posterior_neut
        if total > 0:
            prob_bull = posterior_bull / total
            prob_bear = posterior_bear / total
            prob_neut = posterior_neut / total
        else:
            prob_bull = prob_bear = prob_neut = 0.33
        
        # Confidence = how decisive the probabilities are
        max_prob = max(prob_bull, prob_bear, prob_neut)
        confidence = (max_prob - 0.33) / 0.67  # 0 = uniform, 1 = certain
        
        return prob_bull, prob_bear, prob_neut, confidence
    
    def _kalman_filter(self, prices: np.ndarray) -> Tuple[float, float, float]:
        """
        Kalman filter for optimal price trend estimation.
        
        State: [price, velocity]
        Observation: noisy price
        """
        # Initialize if first run
        if self.kalman_state is None:
            self.kalman_state = np.array([prices[0], 0.0])
            self.kalman_covariance = np.eye(2) * 1.0
        
        # Kalman filter parameters
        dt = 1.0  # Time step
        F = np.array([[1, dt], [0, 1]])  # State transition matrix
        H = np.array([[1, 0]])           # Observation matrix
        Q = np.eye(2) * 0.01             # Process noise
        R = np.array([[0.1]])            # Measurement noise
        
        # Filter through all prices
        filtered_prices = []
        velocities = []
        
        for price in prices:
            # Prediction
            state_pred = F @ self.kalman_state
            cov_pred = F @ self.kalman_covariance @ F.T + Q
            
            # Update
            y = price - H @ state_pred  # Innovation
            S = H @ cov_pred @ H.T + R  # Innovation covariance
            K = cov_pred @ H.T @ np.linalg.inv(S)  # Kalman gain
            
            self.kalman_state = state_pred + K @ y
            self.kalman_covariance = (np.eye(2) - K @ H) @ cov_pred
            
            filtered_prices.append(self.kalman_state[0])
            velocities.append(self.kalman_state[1])
        
        # Current trend and velocity
        current_trend = filtered_prices[-1]
        current_velocity = velocities[-1]
        
        # Noise ratio (signal quality)
        raw_std = np.std(prices[-50:])
        filtered_std = np.std(filtered_prices[-50:])
        noise_ratio = filtered_std / raw_std if raw_std > 0 else 0.0
        
        return current_trend, current_velocity, noise_ratio
    
    def _hurst_exponent(self, prices: np.ndarray) -> Tuple[float, str, int]:
        """
        Calculate Hurst exponent using Rescaled Range (R/S) analysis.
        
        H < 0.5: Mean reverting (anti-persistent)
        H = 0.5: Random walk (no memory)
        H > 0.5: Trending (persistent)
        """
        if len(prices) < 100:
            return 0.5, "RANDOM_WALK", 50
        
        try:
            # Use log returns
            log_returns = np.diff(np.log(prices))
            
            # Different lag windows
            lags = [10, 20, 50, 100]
            rs_values = []
            
            for lag in lags:
                if lag > len(log_returns):
                    continue
                
                # Split into chunks
                n_chunks = len(log_returns) // lag
                rs_list = []
                
                for i in range(n_chunks):
                    chunk = log_returns[i*lag:(i+1)*lag]
                    
                    # Mean-adjusted series
                    mean = np.mean(chunk)
                    Y = np.cumsum(chunk - mean)
                    
                    # Range
                    R = np.max(Y) - np.min(Y)
                    
                    # Standard deviation
                    S = np.std(chunk)
                    
                    if S > 0:
                        rs_list.append(R / S)
                
                if len(rs_list) > 0:
                    rs_values.append(np.mean(rs_list))
            
            if len(rs_values) >= 2:
                # Fit log(R/S) vs log(lag)
                log_lags = np.log([l for l in lags[:len(rs_values)]])
                log_rs = np.log(rs_values)
                
                # Hurst = slope
                hurst = np.polyfit(log_lags, log_rs, 1)[0]
                hurst = max(0.0, min(1.0, hurst))  # Clamp to [0, 1]
            else:
                hurst = 0.5
            
            # Classify behavior
            if hurst < 0.4:
                behavior = "MEAN_REVERTING"
            elif hurst < 0.6:
                behavior = "RANDOM_WALK"
            else:
                behavior = "TRENDING"
            
            # Persistence score (0-100)
            if hurst > 0.5:
                persistence = int((hurst - 0.5) * 200)
            else:
                persistence = int((0.5 - hurst) * 200)
            
            return hurst, behavior, persistence
            
        except Exception as e:
            logger.error(f"Hurst calculation error: {e}")
            return 0.5, "RANDOM_WALK", 50
    
    def _entropy_analysis(self, prices: np.ndarray) -> Tuple[float, str, int]:
        """
        Shannon entropy analysis for market predictability.
        
        High entropy = high uncertainty (chaotic, avoid)
        Low entropy = low uncertainty (predictable patterns)
        """
        try:
            # Calculate returns
            returns = np.diff(prices) / prices[:-1]
            
            # Discretize returns into bins
            hist, _ = np.histogram(returns, bins=20, density=True)
            hist = hist[hist > 0]  # Remove zero bins
            
            # Shannon entropy
            entropy = -np.sum(hist * np.log2(hist))
            
            # Normalize (max entropy for 20 bins is log2(20) = 4.32)
            normalized_entropy = entropy / 4.32
            
            # Classify predictability
            if normalized_entropy < 0.3:
                predictability = "HIGH"
                entropy_score = 90
            elif normalized_entropy < 0.5:
                predictability = "MODERATE"
                entropy_score = 70
            elif normalized_entropy < 0.8:
                predictability = "LOW"
                entropy_score = 40
            else:
                predictability = "CHAOTIC"
                entropy_score = 10
            
            return entropy, predictability, entropy_score
            
        except Exception as e:
            logger.error(f"Entropy calculation error: {e}")
            return 2.0, "MODERATE", 50
    
    def _monte_carlo_simulation(self, prices: np.ndarray, n_simulations: int = 1000, periods: int = 20) -> Tuple[float, float, float, float]:
        """
        Monte Carlo simulation for forward price projection and risk assessment.
        """
        try:
            # Calculate historical returns statistics
            returns = np.diff(prices) / prices[:-1]
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            # Run simulations
            current_price = prices[-1]
            final_prices = []
            max_drawdowns = []
            
            for _ in range(n_simulations):
                # Simulate price path
                simulated_returns = np.random.normal(mean_return, std_return, periods)
                simulated_prices = current_price * np.cumprod(1 + simulated_returns)
                
                # Final price
                final_prices.append(simulated_prices[-1])
                
                # Max drawdown in this path
                peak = np.maximum.accumulate(simulated_prices)
                drawdown = (simulated_prices - peak) / peak
                max_drawdowns.append(np.min(drawdown))
            
            # Statistics
            final_prices = np.array(final_prices)
            expected_return = (np.mean(final_prices) - current_price) / current_price
            std_deviation = np.std(final_prices) / current_price
            
            # Value at Risk (95% confidence)
            var_95 = np.percentile(final_prices - current_price, 5) / current_price
            
            # Probability of >5% drawdown
            max_drawdowns = np.array(max_drawdowns)
            dd_prob = np.sum(max_drawdowns < -0.05) / n_simulations
            
            return expected_return, std_deviation, var_95, dd_prob
            
        except Exception as e:
            logger.error(f"Monte Carlo error: {e}")
            return 0.0, 0.0, 0.0, 0.5
    
    def _autocorrelation_analysis(self, prices: np.ndarray) -> Tuple[float, int, float]:
        """
        Autocorrelation analysis for persistence and optimal holding period.
        """
        try:
            # Calculate returns
            returns = np.diff(prices) / prices[:-1]
            
            # Lag-1 autocorrelation
            if len(returns) > 1:
                autocorr_lag1 = np.corrcoef(returns[:-1], returns[1:])[0, 1]
            else:
                autocorr_lag1 = 0.0
            
            # Find optimal holding period (where autocorrelation drops below threshold)
            optimal_hold = 1
            for lag in range(1, min(50, len(returns) // 2)):
                if lag >= len(returns):
                    break
                autocorr = np.corrcoef(returns[:-lag], returns[lag:])[0, 1]
                if abs(autocorr) < 0.1:
                    optimal_hold = lag
                    break
            
            # Mean reversion strength (negative autocorrelation)
            mean_reversion = max(0.0, -autocorr_lag1)  # 0 to 1
            
            return autocorr_lag1, optimal_hold, mean_reversion
            
        except Exception as e:
            logger.error(f"Autocorrelation error: {e}")
            return 0.0, 10, 0.0
    
    def _fractal_dimension(self, prices: np.ndarray) -> Tuple[float, str]:
        """
        Calculate fractal dimension using box-counting method.
        
        FD ≈ 1: Simple, smooth (strong trend)
        FD ≈ 2: Complex, rough (choppy, range-bound)
        """
        try:
            # Normalize prices
            prices_norm = (prices - np.min(prices)) / (np.max(prices) - np.min(prices))
            
            # Box sizes
            box_sizes = [2, 4, 8, 16, 32]
            counts = []
            
            for box_size in box_sizes:
                if box_size > len(prices_norm):
                    continue
                
                # Count boxes needed to cover the curve
                n_boxes = 0
                for i in range(0, len(prices_norm), box_size):
                    chunk = prices_norm[i:i+box_size]
                    if len(chunk) > 1:
                        box_range = np.max(chunk) - np.min(chunk)
                        n_boxes += int(np.ceil(box_range * box_size)) + 1
                
                counts.append(n_boxes)
            
            # Fractal dimension = -slope of log(count) vs log(box_size)
            if len(counts) >= 2:
                log_boxes = np.log([s for s in box_sizes[:len(counts)]])
                log_counts = np.log(counts)
                fractal_dim = -np.polyfit(log_boxes, log_counts, 1)[0]
                fractal_dim = max(1.0, min(2.0, fractal_dim))
            else:
                fractal_dim = 1.5
            
            # Classify complexity
            if fractal_dim < 1.3:
                complexity = "LOW"
            elif fractal_dim < 1.7:
                complexity = "MODERATE"
            else:
                complexity = "HIGH"
            
            return fractal_dim, complexity
            
        except Exception as e:
            logger.error(f"Fractal dimension error: {e}")
            return 1.5, "MODERATE"
    
    def _calculate_edge(self, bayes_bull: float, bayes_bear: float, hurst: float, 
                       entropy_score: int, kalman_noise: float, persistence: int) -> Tuple[float, str, int]:
        """
        Calculate overall statistical edge and recommendation.
        """
        # Edge components
        directional_edge = max(bayes_bull, bayes_bear) - 0.5  # 0 to 0.5
        trend_edge = abs(hurst - 0.5) * 2  # 0 to 1
        predictability_edge = entropy_score / 100  # 0 to 1
        signal_quality_edge = kalman_noise  # 0 to 1
        
        # Weighted combination
        edge = (
            directional_edge * 0.4 +
            trend_edge * 0.2 +
            predictability_edge * 0.2 +
            signal_quality_edge * 0.2
        )
        
        # Direction
        if bayes_bull > bayes_bear and bayes_bull > 0.5:
            direction = "LONG"
        elif bayes_bear > bayes_bull and bayes_bear > 0.5:
            direction = "SHORT"
        else:
            direction = "NEUTRAL"
        
        # Confidence (0-100)
        confidence = int(edge * 100)
        
        return edge, direction, confidence
    
    def _default_analysis(self) -> StatisticalAnalysis:
        """Return default analysis when calculation fails."""
        return StatisticalAnalysis(
            bayesian_bullish_prob=0.33,
            bayesian_bearish_prob=0.33,
            bayesian_neutral_prob=0.34,
            bayesian_confidence=0.0,
            kalman_trend=0.0,
            kalman_velocity=0.0,
            kalman_noise_ratio=0.0,
            hurst_exponent=0.5,
            market_behavior="RANDOM_WALK",
            persistence_score=50,
            entropy=2.0,
            predictability="MODERATE",
            entropy_score=50,
            mc_expected_return=0.0,
            mc_std_deviation=0.0,
            mc_var_95=0.0,
            mc_max_drawdown_prob=0.5,
            autocorr_lag1=0.0,
            autocorr_optimal_hold=10,
            mean_reversion_strength=0.0,
            fractal_dimension=1.5,
            complexity="MODERATE",
            statistical_edge=0.0,
            recommended_direction="NEUTRAL",
            confidence_level=0
        )
    
    def update_priors(self, outcome: str):
        """
        Update Bayesian priors based on trade outcome.
        
        Args:
            outcome: "BULLISH_WIN", "BULLISH_LOSS", "BEARISH_WIN", "BEARISH_LOSS"
        """
        # Simple Bayesian update (can be made more sophisticated)
        learning_rate = 0.1
        
        if "BULLISH" in outcome:
            if "WIN" in outcome:
                self.prior_bullish += learning_rate * (1 - self.prior_bullish)
            else:
                self.prior_bullish -= learning_rate * self.prior_bullish
        
        elif "BEARISH" in outcome:
            if "WIN" in outcome:
                self.prior_bearish += learning_rate * (1 - self.prior_bearish)
            else:
                self.prior_bearish -= learning_rate * self.prior_bearish
        
        # Normalize
        total = self.prior_bullish + self.prior_bearish + self.prior_neutral
        self.prior_bullish /= total
        self.prior_bearish /= total
        self.prior_neutral /= total


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_statistical_engine = None

def get_statistical_engine() -> StatisticalEngine:
    """Get or create singleton statistical engine instance."""
    global _statistical_engine
    if _statistical_engine is None:
        _statistical_engine = StatisticalEngine()
    return _statistical_engine


# ═══════════════════════════════════════════════════════════════════════════
# QUANT X EXTENSION — Conformal Predictor
# ═══════════════════════════════════════════════════════════════════════════

class ConformalPredictor:
    """
    Split-conformal prediction wrapper.

    Provides distribution-free, statistically valid prediction intervals
    for any point-prediction model.  Preferred over ad-hoc confidence
    heuristics because the coverage guarantee is exact for finite samples
    (given exchangeability — a weaker assumption than i.i.d.).

    Usage:
        cp = ConformalPredictor(target_coverage=0.90)
        cp.calibrate(cal_predictions, cal_actuals)   # once, on held-out set
        pred, lo, hi, achieved = cp.predict(new_prediction)

    FEATURE FLAG: QX["conformal_prediction"]
    """

    def __init__(self, target_coverage: float = 0.90):
        self.target_coverage   = target_coverage
        self._nonconf_scores:  List[float] = []   # calibration nonconformity scores
        self._quantile:        Optional[float] = None
        self._n_cal:           int = 0

    def calibrate(self, predictions: List[float], actuals: List[float]) -> None:
        """
        Build the conformal calibration set from held-out predictions and outcomes.
        predictions: model output (0-1 probability)
        actuals:     observed binary outcomes (0/1) or continuous targets
        """
        if not predictions or not actuals or len(predictions) != len(actuals):
            return
        self._nonconf_scores = [abs(a - p) for a, p in zip(actuals, predictions)]
        self._n_cal = len(self._nonconf_scores)
        alpha = 1.0 - self.target_coverage
        n = self._n_cal
        # Conformal quantile: ceil((n+1)(1-alpha)) / n -th order statistic
        k = int(np.ceil((n + 1) * (1 - alpha)))
        k = min(k, n)
        self._quantile = sorted(self._nonconf_scores)[k - 1]
        logger.info(
            "[CONFORMAL] Calibrated on %d samples. q=%.4f (coverage=%.0f%%)",
            n, self._quantile, self.target_coverage * 100
        )

    @property
    def is_calibrated(self) -> bool:
        return self._quantile is not None

    def predict(self, point_prediction: float) -> Tuple[float, float, float, float]:
        """
        Return (prediction, lower_bound, upper_bound, achieved_coverage).
        Falls back to (prediction, 0, 1, 0) if not yet calibrated.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("conformal_prediction"):
                return point_prediction, 0.0, 1.0, 0.0
        except Exception:
            return point_prediction, 0.0, 1.0, 0.0

        if not self.is_calibrated:
            return point_prediction, 0.0, 1.0, 0.0

        q = self._quantile
        lo = max(0.0, point_prediction - q)
        hi = min(1.0, point_prediction + q)
        coverage = self.target_coverage
        return round(point_prediction, 4), round(lo, 4), round(hi, 4), coverage

    def interval_width(self) -> Optional[float]:
        """Current interval width (2q).  Narrower = more certain."""
        if self._quantile is None:
            return None
        return round(2 * self._quantile, 4)

    def get_status(self) -> dict:
        return {
            "calibrated":        self.is_calibrated,
            "n_calibration":     self._n_cal,
            "quantile":          self._quantile,
            "target_coverage":   self.target_coverage,
            "interval_width":    self.interval_width(),
        }


# ═══════════════════════════════════════════════════════════════════════════
# QUANT X EXTENSION — HMM Regime Model
# ═══════════════════════════════════════════════════════════════════════════

class HMMRegimeModel:
    """
    Hidden Markov Model for regime detection.
    Uses hmmlearn if available; falls back to a pure-Python Viterbi stub
    for environments without hmmlearn.

    States map to: TRENDING, RANGING, VOLATILE, MEAN_REVERTING
    (n_states configurable via QX["hmm_n_states"])

    FEATURE FLAG: QX["hmm_regime_model"]
    """

    STATE_LABELS = {0: "RANGING", 1: "TRENDING", 2: "VOLATILE", 3: "MEAN_REVERTING"}

    def __init__(self):
        self._model    = None
        self._fitted   = False
        self._n_states = 4

    def fit(self, returns_series: List[float]) -> bool:
        """
        Fit the HMM on a series of log returns.
        Returns True on success.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("hmm_regime_model"):
                return False
            self._n_states = int(QX.get("hmm_n_states") or 4)
        except Exception:
            return False

        try:
            from hmmlearn.hmm import GaussianHMM
            import numpy as np
            X = np.array(returns_series).reshape(-1, 1)
            self._model = GaussianHMM(
                n_components=self._n_states,
                covariance_type="full",
                n_iter=100,
                random_state=42,
            )
            self._model.fit(X)
            self._fitted = True
            logger.info("[HMM] Fitted GaussianHMM on %d observations", len(returns_series))
            return True
        except ImportError:
            logger.warning("[HMM] hmmlearn not installed ? using stub decoder")
            self._fitted = True   # Stub mode
            return True
        except Exception as exc:
            logger.warning("[HMM] Fit failed: %s", exc)
            return False

    def predict_state(self, recent_returns: List[float]) -> Tuple[str, float]:
        """
        Predict the current regime state from recent returns.
        Returns (state_label, confidence_0_to_1).
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("hmm_regime_model") or not self._fitted:
                return "UNKNOWN", 0.0
        except Exception:
            return "UNKNOWN", 0.0

        try:
            if self._model is not None:
                import numpy as np
                X = np.array(recent_returns[-20:]).reshape(-1, 1)
                states = self._model.predict(X)
                last_state = int(states[-1])
                probs = self._model.predict_proba(X)
                conf = float(probs[-1][last_state])
                label = self.STATE_LABELS.get(last_state % self._n_states, "UNKNOWN")
                return label, round(conf, 4)
            else:
                # Stub: classify by volatility of recent returns
                import statistics as _stats
                if len(recent_returns) < 3:
                    return "UNKNOWN", 0.0
                std = _stats.stdev(recent_returns[-10:]) if len(recent_returns) >= 10 else 0.0
                mean_abs = sum(abs(r) for r in recent_returns[-10:]) / max(len(recent_returns[-10:]), 1)
                if std > mean_abs * 1.5:
                    return "VOLATILE", 0.5
                elif mean_abs > 0.001:
                    return "TRENDING", 0.5
                else:
                    return "RANGING", 0.5
        except Exception as exc:
            logger.debug("[HMM] predict_state error: %s", exc)
            return "UNKNOWN", 0.0


# Module-level HMM singleton
_hmm_model: Optional[HMMRegimeModel] = None

def get_hmm_model() -> HMMRegimeModel:
    global _hmm_model
    if _hmm_model is None:
        _hmm_model = HMMRegimeModel()
    return _hmm_model


# Module-level ConformalPredictor singleton (shared across callers)
_conformal_predictor: Optional[ConformalPredictor] = None

def get_conformal_predictor() -> ConformalPredictor:
    global _conformal_predictor
    if _conformal_predictor is None:
        try:
            from config.quant_x_config import QX
            cov = float(QX.get("conformal_coverage") or 0.90)
        except Exception:
            cov = 0.90
        _conformal_predictor = ConformalPredictor(target_coverage=cov)
    return _conformal_predictor

