"""
===========================================================================
AEGIS GOLD — Walk-Forward Analysis Engine (Phase U)
===========================================================================

Historical backtesting with expanding window and anchored window methods.
Validates system performance across different market regimes.

METHODOLOGY:
-----------
1. Divide historical data into train/test periods
2. Train pattern memory on initial data
3. Test on subsequent out-of-sample period
4. Expand window (walk-forward) and repeat
5. Accumulate performance metrics across all folds

WINDOWS SUPPORTED:
------------------
- Expanding: Each test period uses all previous data for training
- Anchored: Fixed training window slides forward in time
- Rolling: Fixed window both training and testing
- Custom: User-defined window sizes

METRICS TRACKED:
----------------
- Win rate per regime
- Average trade metrics (RR, duration, profit)
- Drawdown analysis (max DD, recovery time)
- Sharpe ratio, Sortino ratio
- Pattern success rates by type
- Performance degradation over time

===========================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Tuple, Optional
from enum import Enum
import statistics


class WindowMethod(Enum):
    """Walk-forward window methods."""
    EXPANDING = "expanding"      # Expanding window (all previous data)
    ANCHORED = "anchored"         # Fixed start, expanding end
    ROLLING = "rolling"           # Fixed window sliding forward
    CUSTOM = "custom"             # Custom sizes


@dataclass
class WFTestPeriod:
    """Single walk-forward test period."""
    
    fold_number: int
    train_start: str  # ISO timestamp
    train_end: str
    test_start: str
    test_end: str
    train_sample_size: int
    test_sample_size: int
    
    # Performance metrics
    win_count: int = 0
    loss_count: int = 0
    break_even_count: int = 0
    avg_profit_per_trade: float = 0.0
    avg_loss_per_trade: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    
    # Pattern-specific metrics
    patterns_tested: int = 0
    pattern_success_rates: Dict[str, float] = field(default_factory=dict)
    
    # Regime metrics
    market_regime: str = "UNKNOWN"
    regime_consistency: float = 0.0


@dataclass
class WFPerformanceSummary:
    """Aggregate walk-forward performance."""
    
    total_folds: int
    total_trades: int
    overall_win_rate: float
    overall_avg_trade_size: float
    overall_max_dd: float
    
    # Performance by regime
    regime_performance: Dict[str, float] = field(default_factory=dict)
    
    # Performance stability
    fold_win_rates: List[float] = field(default_factory=list)
    fold_sharpe_ratios: List[float] = field(default_factory=list)
    performance_consistency: float = 0.0
    
    # Pattern performance
    pattern_performance_by_fold: Dict[str, List[float]] = field(default_factory=dict)
    
    # Degradation analysis
    performance_degradation: float = 0.0  # % decline over time
    

class WalkForwardAnalyzer:
    """Walk-forward backtesting engine."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.test_periods: List[WFTestPeriod] = []
        self.summary: Optional[WFPerformanceSummary] = None
        
        # Configuration
        self.window_method = WindowMethod.EXPANDING
        self.train_window_bars = 5000
        self.test_window_bars = 1000
        self.step_size_bars = 500
        
        self.is_configured = False
    
    def configure_expanding_window(self, train_bars: int, test_bars: int):
        """Configure expanding window (all previous data for training)."""
        self.window_method = WindowMethod.EXPANDING
        self.train_window_bars = train_bars
        self.test_window_bars = test_bars
        self.is_configured = True
        return self
    
    def configure_anchored_window(self, anchor_bars: int, test_bars: int):
        """Configure anchored window (fixed start point)."""
        self.window_method = WindowMethod.ANCHORED
        self.train_window_bars = anchor_bars
        self.test_window_bars = test_bars
        self.is_configured = True
        return self
    
    def configure_rolling_window(self, train_bars: int, test_bars: int, step_bars: int):
        """Configure rolling window."""
        self.window_method = WindowMethod.ROLLING
        self.train_window_bars = train_bars
        self.test_window_bars = test_bars
        self.step_size_bars = step_bars
        self.is_configured = True
        return self
    
    def create_test_period(self,
                          fold_number: int,
                          train_start: str,
                          train_end: str,
                          test_start: str,
                          test_end: str,
                          train_sample_size: int,
                          test_sample_size: int) -> WFTestPeriod:
        """Create a test period."""
        
        period = WFTestPeriod(
            fold_number=fold_number,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            train_sample_size=train_sample_size,
            test_sample_size=test_sample_size
        )
        
        return period
    
    def calculate_fold_metrics(self,
                              trades: List[Dict],
                              market_data: List[Dict]) -> Tuple[int, int, int, float, float]:
        """Calculate metrics for a fold."""
        
        if not trades:
            return 0, 0, 0, 0.0, 0.0
        
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losses = sum(1 for t in trades if t.get('pnl', 0) < 0)
        breakevens = sum(1 for t in trades if t.get('pnl', 0) == 0)
        
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        avg_per_trade = total_pnl / len(trades) if trades else 0.0
        
        # Calculate max drawdown
        cumulative_pnl = []
        running_total = 0
        for trade in trades:
            running_total += trade.get('pnl', 0)
            cumulative_pnl.append(running_total)
        
        max_dd = 0.0
        peak = 0
        for val in cumulative_pnl:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        
        return wins, losses, breakevens, avg_per_trade, max_dd
    
    def record_fold_performance(self,
                               fold_number: int,
                               trades: List[Dict],
                               market_data: List[Dict],
                               market_regime: str) -> WFTestPeriod:
        """Record performance metrics for a fold."""
        
        if fold_number < 1 or fold_number > 20:
            raise ValueError(f"Invalid fold number: {fold_number}")
        
        wins, losses, breakevens, avg_trade, max_dd = self.calculate_fold_metrics(
            trades, market_data
        )
        
        # Find or create period
        period = None
        for p in self.test_periods:
            if p.fold_number == fold_number:
                period = p
                break
        
        if period is None:
            base_time = datetime.now(timezone.utc)
            period = WFTestPeriod(
                fold_number=fold_number,
                train_start=base_time.isoformat(),
                train_end=(base_time + timedelta(days=fold_number)).isoformat(),
                test_start=(base_time + timedelta(days=fold_number)).isoformat(),
                test_end=(base_time + timedelta(days=fold_number+1)).isoformat(),
                train_sample_size=5000 * fold_number,
                test_sample_size=1000
            )
            self.test_periods.append(period)
        
        # Update metrics
        period.win_count = wins
        period.loss_count = losses
        period.break_even_count = breakevens
        period.avg_profit_per_trade = avg_trade
        period.max_drawdown = max_dd
        period.market_regime = market_regime
        period.patterns_tested = len(trades)
        
        # Calculate Sharpe ratio (simplified)
        if trades:
            pnls = [t.get('pnl', 0) for t in trades]
            if len(pnls) > 1:
                mean_pnl = statistics.mean(pnls)
                std_dev = statistics.stdev(pnls) if len(pnls) > 1 else 1.0
                period.sharpe_ratio = (mean_pnl / std_dev) if std_dev > 0 else 0.0
                
                # Sortino ratio (only downside volatility)
                downside_pnls = [p for p in pnls if p < 0]
                downside_std = statistics.stdev(downside_pnls) if len(downside_pnls) > 1 else 1.0
                period.sortino_ratio = (mean_pnl / downside_std) if downside_std > 0 else 0.0
        
        return period
    
    def generate_aggregate_summary(self) -> WFPerformanceSummary:
        """Generate aggregate performance summary across all folds."""
        
        if not self.test_periods:
            return WFPerformanceSummary(
                total_folds=0,
                total_trades=0,
                overall_win_rate=0.0,
                overall_avg_trade_size=0.0,
                overall_max_dd=0.0
            )
        
        total_trades = sum(p.patterns_tested for p in self.test_periods)
        total_wins = sum(p.win_count for p in self.test_periods)
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
        
        avg_trade_size = statistics.mean(
            [p.avg_profit_per_trade for p in self.test_periods if p.patterns_tested > 0]
        ) if self.test_periods else 0.0
        
        max_dd = max([p.max_drawdown for p in self.test_periods], default=0.0)
        
        # Performance by regime
        regime_performance = {}
        for period in self.test_periods:
            regime = period.market_regime
            if regime not in regime_performance:
                regime_performance[regime] = []
            win_rate = (period.win_count / period.patterns_tested * 100) if period.patterns_tested > 0 else 0.0
            regime_performance[regime].append(win_rate)
        
        regime_avg = {k: statistics.mean(v) for k, v in regime_performance.items()}
        
        # Performance consistency
        fold_win_rates = [
            (p.win_count / p.patterns_tested * 100) if p.patterns_tested > 0 else 0.0
            for p in self.test_periods
        ]
        consistency = 100 - (statistics.stdev(fold_win_rates) if len(fold_win_rates) > 1 else 0)
        
        # Performance degradation
        if len(fold_win_rates) > 1:
            degradation = ((fold_win_rates[0] - fold_win_rates[-1]) / fold_win_rates[0] * 100) \
                         if fold_win_rates[0] > 0 else 0.0
        else:
            degradation = 0.0
        
        summary = WFPerformanceSummary(
            total_folds=len(self.test_periods),
            total_trades=total_trades,
            overall_win_rate=overall_win_rate,
            overall_avg_trade_size=avg_trade_size,
            overall_max_dd=max_dd,
            regime_performance=regime_avg,
            fold_win_rates=fold_win_rates,
            fold_sharpe_ratios=[p.sharpe_ratio for p in self.test_periods],
            performance_consistency=consistency,
            performance_degradation=degradation
        )
        
        self.summary = summary
        return summary
    
    def get_fold_details(self, fold_number: int) -> Optional[WFTestPeriod]:
        """Get details for a specific fold."""
        for period in self.test_periods:
            if period.fold_number == fold_number:
                return period
        return None
    
    def get_regime_robustness(self) -> Dict[str, float]:
        """Get robustness metrics by market regime."""
        regime_metrics = {}
        
        for regime in set(p.market_regime for p in self.test_periods):
            regime_periods = [p for p in self.test_periods if p.market_regime == regime]
            
            win_rates = [
                (p.win_count / p.patterns_tested * 100) if p.patterns_tested > 0 else 0.0
                for p in regime_periods
            ]
            
            avg_wr = statistics.mean(win_rates) if win_rates else 0.0
            consistency = 100 - (statistics.stdev(win_rates) if len(win_rates) > 1 else 0)
            
            regime_metrics[regime] = {
                'avg_win_rate': avg_wr,
                'consistency': consistency,
                'fold_count': len(regime_periods)
            }
        
        return regime_metrics
    
    def validate_strategy_robustness(self) -> Tuple[bool, str]:
        """Validate if strategy is robust across regimes."""
        
        if not self.summary:
            return False, "No performance summary generated"
        
        # Check minimum performance standards
        if self.summary.overall_win_rate < 50.0:
            return False, f"Win rate below 50%: {self.summary.overall_win_rate:.1f}%"
        
        if self.summary.performance_degradation > 20.0:
            return False, f"Performance degradation too high: {self.summary.performance_degradation:.1f}%"
        
        # Check regime consistency
        regime_robustness = self.get_regime_robustness()
        for regime, metrics in regime_robustness.items():
            if metrics['consistency'] < 60.0:
                return False, f"Low consistency in {regime}: {metrics['consistency']:.1f}%"
        
        return True, "Strategy is robust across regimes"
    
    def generate_wf_report(self) -> str:
        """Generate comprehensive walk-forward analysis report."""
        
        if not self.summary:
            self.generate_aggregate_summary()
        
        report = []
        report.append("=" * 70)
        report.append("WALK-FORWARD ANALYSIS REPORT (Phase U)")
        report.append("=" * 70)
        report.append("")
        
        # Summary statistics
        report.append("PERFORMANCE SUMMARY")
        report.append("-" * 70)
        report.append(f"Total Folds:              {self.summary.total_folds}")
        report.append(f"Total Trades:             {self.summary.total_trades}")
        report.append(f"Overall Win Rate:         {self.summary.overall_win_rate:.1f}%")
        report.append(f"Avg Trade Size:           {self.summary.overall_avg_trade_size:.4f}")
        report.append(f"Max Drawdown:             {self.summary.overall_max_dd:.4f}")
        report.append("")
        
        # Performance by regime
        if self.summary.regime_performance:
            report.append("PERFORMANCE BY REGIME")
            report.append("-" * 70)
            for regime, wr in self.summary.regime_performance.items():
                report.append(f"  {regime:20s}: {wr:6.1f}%")
            report.append("")
        
        # Consistency metrics
        report.append("CONSISTENCY METRICS")
        report.append("-" * 70)
        report.append(f"Consistency Score:       {self.summary.performance_consistency:.1f}%")
        report.append(f"Performance Degradation: {self.summary.performance_degradation:.1f}%")
        report.append("")
        
        # Fold-by-fold breakdown
        report.append("FOLD-BY-FOLD BREAKDOWN")
        report.append("-" * 70)
        report.append(f"{'Fold':<6} {'Trades':<8} {'WinRate':<10} {'AvgTrade':<12} {'MaxDD':<10} {'Regime':<15}")
        report.append("-" * 70)
        
        for period in self.test_periods:
            win_rate = (period.win_count / period.patterns_tested * 100) if period.patterns_tested > 0 else 0.0
            report.append(
                f"{period.fold_number:<6} {period.patterns_tested:<8} "
                f"{win_rate:<10.1f} {period.avg_profit_per_trade:<12.4f} "
                f"{period.max_drawdown:<10.4f} {period.market_regime:<15}"
            )
        
        report.append("")
        
        # Robustness validation
        is_robust, reason = self.validate_strategy_robustness()
        report.append("ROBUSTNESS VALIDATION")
        report.append("-" * 70)
        report.append(f"Status: {'✓ ROBUST' if is_robust else '✗ NOT ROBUST'}")
        report.append(f"Reason: {reason}")
        report.append("")
        
        return "\n".join(report)
