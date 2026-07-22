import numpy as np
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger("aegis.stress_tester")

class StressTester:
    """
    QUANT X stress testing framework.
    Evaluates trading strategies against historically volatile regimes for gold
    (e.g., 2008 crash, 2013 gold selloff, 2020 covid spike, 2022 rate hike)
    and synthetic tail risk scenarios.
    """
    
    HISTORICAL_REGIMES = {
        "2008_Financial_Crisis": {"vol_mult": 2.5, "drift": -0.005},
        "2013_Gold_Selloff": {"vol_mult": 3.0, "drift": -0.012},
        "2020_Covid_Liquidity": {"vol_mult": 2.8, "drift": 0.008},
        "2022_Inflation_Rate_Hikes": {"vol_mult": 2.0, "drift": -0.003}
    }

    def __init__(self):
        pass

    def apply_historical_stress(self, returns: List[float], regime_name: str) -> List[float]:
        """
        Applies historical volatility scaling and drift adjustments to simulate a regime.
        """
        regime = self.HISTORICAL_REGIMES.get(regime_name)
        if not regime:
            logger.warning(f"Regime {regime_name} not recognized. Using identity mapping.")
            return returns
            
        vol_mult = regime["vol_mult"]
        drift = regime["drift"]
        
        stressed = [r * vol_mult + drift for r in returns]
        return stressed

    def generate_synthetic_tail_shocks(self, n_samples: int = 500, df: int = 3, scale: float = 0.02) -> List[float]:
        """
        Generates synthetic tail returns using Student's t-distribution
        (to correctly capture heavy-tailed market crash events).
        """
        # np.random.standard_t draws heavy-tailed returns
        shocks = np.random.standard_t(df, size=n_samples) * scale
        return shocks.tolist()

    def run_stress_test(self, returns: List[float]) -> Dict[str, dict]:
        """
        Evaluates returns series against multiple stress scenarios.
        Returns detailed report dictionary.
        """
        report = {}
        if not returns:
            return report

        for regime_name in self.HISTORICAL_REGIMES:
            stressed_rets = self.apply_historical_stress(returns, regime_name)
            
            # Compute Sharpe Ratio and Max Drawdown proxy
            mean = np.mean(stressed_rets)
            std = np.std(stressed_rets) if len(stressed_rets) > 1 else 1.0
            sr = mean / std if std > 0 else 0.0
            
            # Cumulative return
            cum_ret = float(np.sum(stressed_rets))
            
            report[regime_name] = {
                "stressed_expected_return": round(mean, 5),
                "stressed_volatility": round(std, 5),
                "stressed_sharpe": round(sr, 4),
                "cumulative_stressed_return": round(cum_ret, 4)
            }
            
        # Add synthetic tail test
        synthetic = self.generate_synthetic_tail_shocks(n_samples=len(returns))
        blended = [r + s for r, s in zip(returns, synthetic)]
        mean_b = np.mean(blended)
        std_b = np.std(blended)
        report["Synthetic_Tail_Shock"] = {
            "stressed_expected_return": round(mean_b, 5),
            "stressed_volatility": round(std_b, 5),
            "stressed_sharpe": round(mean_b / std_b if std_b > 0 else 0.0, 4),
            "cumulative_stressed_return": round(float(np.sum(blended)), 4)
        }

        return report
