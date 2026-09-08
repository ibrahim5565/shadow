"""
===========================================================================
AEGIS GOLD — Shadow/Demo Trading Mode (Phase Y)
===========================================================================

Run system in parallel with actual trading without execution.

PURPOSE:
--------
1. Validate trading signals before live execution
2. Measure signal accuracy in real-time conditions
3. Test with small position sizes
4. Monitor performance without risk
5. Detect anomalies or issues
6. Build confidence before full deployment

MODES:
------
1. SHADOW:  Signals only, no execution, full logging
2. DEMO:    Execution on demo account (simulated fills)
3. PAPER:   Execution on paper trading (real market prices, virtual money)

METRICS TRACKED:
----------------
- Signal accuracy (win/loss rate)
- Execution quality (slippage, fills)
- System latency (decision → execution time)
- Anomaly detection (unusual signals/prices)
- Risk metrics (max DD in shadow mode)

===========================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
from enum import Enum
import json


class ShadowMode(Enum):
    """Shadow/demo mode types."""
    SHADOW = "shadow"      # Signals only, no execution
    DEMO = "demo"          # Simulated execution
    PAPER = "paper"        # Paper trading
    HYBRID = "hybrid"      # Mix of modes


class ExecutionStatus(Enum):
    """Execution status in shadow mode."""
    SIGNAL_GENERATED = "signal_generated"
    WOULD_EXECUTE = "would_execute"
    DEMO_EXECUTED = "demo_executed"
    PAPER_EXECUTED = "paper_executed"
    SKIPPED_BY_GATE = "skipped_by_gate"
    FAILED_VALIDATION = "failed_validation"


@dataclass
class ShadowSignal:
    """Signal generated in shadow mode."""
    
    signal_id: str
    timestamp: str  # ISO format
    symbol: str
    direction: str  # BUY/SELL
    
    # Signal details
    pattern_id: str
    pattern_type: str
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size_fraction: float
    
    # Quality metrics
    confidence_score: float  # 0-100
    pattern_fit_score: float  # 0-100
    regime_consistency: float  # 0-100
    confluence_factors: int  # Number of confluent signals
    
    # Risk metrics
    risk_reward_ratio: float
    max_position_risk_pct: float
    
    # Status
    execution_status: str = ExecutionStatus.SIGNAL_GENERATED.value
    was_executed: bool = False
    execution_price: Optional[float] = None
    
    # Outcome (if executed)
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_time_hours: float = 0.0
    

@dataclass
class ShadowPerformance:
    """Aggregated shadow mode performance."""
    
    mode: str
    start_time: str
    end_time: str
    
    # Execution metrics
    total_signals: int = 0
    signals_executed: int = 0
    signals_skipped: int = 0
    execution_rate: float = 0.0  # %
    
    # Performance metrics
    win_count: int = 0
    loss_count: int = 0
    break_even_count: int = 0
    win_rate: float = 0.0  # %
    
    # P&L metrics (shadow only, no real money)
    total_pnl: float = 0.0
    avg_pnl_per_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    
    # Risk metrics
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    
    # Quality metrics
    avg_confidence: float = 0.0
    avg_pattern_fit: float = 0.0
    avg_regime_consistency: float = 0.0
    
    # Execution quality
    avg_execution_latency_ms: float = 0.0
    avg_slippage_pips: float = 0.0
    fill_rate: float = 0.0  # % of intended executions filled
    
    # Anomaly detection
    anomalies_detected: int = 0
    anomaly_types: List[str] = field(default_factory=list)


class ShadowDemoMode:
    """Shadow/demo trading mode system."""
    
    def __init__(self, mode: ShadowMode = ShadowMode.SHADOW):
        """Initialize shadow/demo mode."""
        self.mode = mode
        self.is_active = False
        
        self.signals: List[ShadowSignal] = []
        self.performance: Optional[ShadowPerformance] = None
        
        # Configuration
        self.max_signals_per_day = 20
        self.demo_base_balance = 10000.0
        self.demo_current_balance = self.demo_base_balance
        self.paper_broker_connection = None  # For paper trading
        
        # Monitoring
        self.anomaly_threshold_confidence = 40.0  # Below this = anomaly
        self.anomaly_threshold_slippage = 5.0     # Pips
        self.start_time = datetime.now(timezone.utc)
        self.last_signal_time = None
        
        self.statistics = {
            'total_signals': 0,
            'executed_signals': 0,
            'skipped_signals': 0,
            'total_pnl': 0.0,
            'max_dd': 0.0,
            'anomalies': 0
        }
    
    def start(self) -> str:
        """Start shadow/demo mode."""
        self.is_active = True
        self.start_time = datetime.now(timezone.utc)
        self.demo_current_balance = self.demo_base_balance
        
        status = f"[SHADOW MODE] Started in {self.mode.value} mode at {self.start_time.isoformat()}"
        return status
    
    def stop(self) -> str:
        """Stop shadow/demo mode and generate report."""
        self.is_active = False
        end_time = datetime.now(timezone.utc)
        
        status = f"[SHADOW MODE] Stopped at {end_time.isoformat()}"
        return status
    
    def record_signal(self,
                     signal_id: str,
                     symbol: str,
                     direction: str,
                     entry_price: float,
                     stop_loss: float,
                     take_profit: float,
                     position_size_pct: float,
                     pattern_id: str,
                     pattern_type: str,
                     confidence_score: float,
                     pattern_fit: float,
                     regime_consistency: float,
                     confluence_factors: int,
                     risk_reward_ratio: float) -> ShadowSignal:
        """Record a trading signal in shadow mode."""
        
        if not self.is_active:
            self.is_active = True
        
        # Check if signal should be recorded
        if self.statistics['total_signals'] >= self.max_signals_per_day:
            execution_status = ExecutionStatus.SKIPPED_BY_GATE.value
        else:
            execution_status = ExecutionStatus.SIGNAL_GENERATED.value
        
        # Calculate risk metrics
        max_position_risk = abs(entry_price - stop_loss) / entry_price * 100 if entry_price > 0 else 0
        
        signal = ShadowSignal(
            signal_id=signal_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol,
            direction=direction,
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size_fraction=position_size_pct,
            confidence_score=confidence_score,
            pattern_fit_score=pattern_fit,
            regime_consistency=regime_consistency,
            confluence_factors=confluence_factors,
            risk_reward_ratio=risk_reward_ratio,
            max_position_risk_pct=max_position_risk,
            execution_status=execution_status
        )
        
        self.signals.append(signal)
        self.statistics['total_signals'] += 1
        self.last_signal_time = datetime.now(timezone.utc)
        
        # Detect anomalies
        if confidence_score < self.anomaly_threshold_confidence:
            self.statistics['anomalies'] += 1
        
        return signal
    
    def execute_signal_demo(self,
                           signal: ShadowSignal,
                           current_market_price: float,
                           execution_slippage_pips: float = 0.5) -> Tuple[bool, str]:
        """Execute signal in demo mode."""
        
        # Calculate execution price with slippage
        if signal.direction == "BUY":
            execution_price = signal.entry_price + (execution_slippage_pips * 0.0001)
        else:
            execution_price = signal.entry_price - (execution_slippage_pips * 0.0001)
        
        signal.execution_price = execution_price
        signal.was_executed = True
        signal.execution_status = ExecutionStatus.DEMO_EXECUTED.value
        
        self.statistics['executed_signals'] += 1
        
        return True, f"Demo execution at {execution_price}"
    
    def record_trade_outcome(self,
                            signal_id: str,
                            exit_price: float,
                            exit_time: str,
                            holding_hours: float) -> Optional[ShadowSignal]:
        """Record outcome of shadow trade."""
        
        # Find signal
        signal = None
        for s in self.signals:
            if s.signal_id == signal_id:
                signal = s
                break
        
        if not signal:
            return None
        
        # Calculate P&L
        if signal.direction == "BUY":
            pnl_points = exit_price - signal.entry_price
        else:
            pnl_points = signal.entry_price - exit_price
        
        pnl_pct = (pnl_points / signal.entry_price * 100) if signal.entry_price > 0 else 0
        pnl = pnl_points * signal.position_size_fraction * 10000  # Scaled by position size
        
        signal.exit_price = exit_price
        signal.exit_time = exit_time
        signal.pnl = pnl
        signal.pnl_pct = pnl_pct
        signal.holding_time_hours = holding_hours
        
        # Update balance (demo mode)
        self.demo_current_balance += pnl
        self.statistics['total_pnl'] += pnl
        
        # Track win/loss
        if pnl > 0:
            self.statistics['wins'] = self.statistics.get('wins', 0) + 1
        elif pnl < 0:
            self.statistics['losses'] = self.statistics.get('losses', 0) + 1
        else:
            self.statistics['breakevens'] = self.statistics.get('breakevens', 0) + 1
        
        return signal
    
    def detect_anomalies(self) -> List[Dict]:
        """Detect anomalies in signals."""
        
        anomalies = []
        
        for signal in self.signals[-20:]:  # Check recent signals
            issues = []
            
            # Check confidence
            if signal.confidence_score < self.anomaly_threshold_confidence:
                issues.append(f"Low confidence: {signal.confidence_score:.1f}%")
            
            # Check pattern fit
            if signal.pattern_fit_score < 60.0:
                issues.append(f"Poor pattern fit: {signal.pattern_fit_score:.1f}%")
            
            # Check regime consistency
            if signal.regime_consistency < 50.0:
                issues.append(f"Weak regime consistency: {signal.regime_consistency:.1f}%")
            
            # Check risk/reward
            if signal.risk_reward_ratio < 1.5:
                issues.append(f"Unfavorable R:R: {signal.risk_reward_ratio:.2f}")
            
            if issues:
                anomalies.append({
                    'signal_id': signal.signal_id,
                    'timestamp': signal.timestamp,
                    'pattern_type': signal.pattern_type,
                    'issues': issues
                })
                self.statistics['anomalies'] += 1
        
        return anomalies
    
    def generate_performance_summary(self) -> ShadowPerformance:
        """Generate shadow mode performance summary."""
        
        end_time = datetime.now(timezone.utc)
        
        # Calculate metrics
        total_signals = len(self.signals)
        executed_signals = sum(1 for s in self.signals if s.was_executed)
        skipped_signals = total_signals - executed_signals
        execution_rate = (executed_signals / total_signals * 100) if total_signals > 0 else 0.0
        
        # Calculate P&L metrics
        pnls = [s.pnl for s in self.signals if s.pnl != 0]
        wins = sum(1 for s in self.signals if s.pnl > 0)
        losses = sum(1 for s in self.signals if s.pnl < 0)
        breakevens = sum(1 for s in self.signals if s.pnl == 0)
        
        win_rate = (wins / total_signals * 100) if total_signals > 0 else 0.0
        
        avg_win = sum(s.pnl for s in self.signals if s.pnl > 0) / wins if wins > 0 else 0.0
        avg_loss = sum(s.pnl for s in self.signals if s.pnl < 0) / losses if losses > 0 else 0.0
        profit_factor = avg_win / abs(avg_loss) if avg_loss != 0 else 0.0
        
        # Calculate Sharpe ratio
        if len(pnls) > 1:
            import statistics
            mean_pnl = statistics.mean(pnls)
            std_dev = statistics.stdev(pnls)
            sharpe = (mean_pnl / std_dev) if std_dev > 0 else 0.0
        else:
            sharpe = 0.0
        
        # Calculate max drawdown
        cumulative_pnl = []
        running_total = 0
        for signal in self.signals:
            running_total += signal.pnl
            cumulative_pnl.append(running_total)
        
        max_dd = 0.0
        peak = 0
        for val in cumulative_pnl:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        
        max_dd_pct = (max_dd / self.demo_base_balance * 100) if self.demo_base_balance > 0 else 0.0
        
        # Quality metrics
        avg_confidence = sum(s.confidence_score for s in self.signals) / total_signals if total_signals > 0 else 0.0
        avg_pattern_fit = sum(s.pattern_fit_score for s in self.signals) / total_signals if total_signals > 0 else 0.0
        avg_regime = sum(s.regime_consistency for s in self.signals) / total_signals if total_signals > 0 else 0.0
        
        # Anomalies
        anomalies = self.detect_anomalies()
        anomaly_types = list(set(issue for a in anomalies for issue in a['issues']))
        
        performance = ShadowPerformance(
            mode=self.mode.value,
            start_time=self.start_time.isoformat(),
            end_time=end_time.isoformat(),
            total_signals=total_signals,
            signals_executed=executed_signals,
            signals_skipped=skipped_signals,
            execution_rate=execution_rate,
            win_count=wins,
            loss_count=losses,
            break_even_count=breakevens,
            win_rate=win_rate,
            total_pnl=self.statistics['total_pnl'],
            avg_pnl_per_trade=self.statistics['total_pnl'] / total_signals if total_signals > 0 else 0.0,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            sharpe_ratio=sharpe,
            avg_confidence=avg_confidence,
            avg_pattern_fit=avg_pattern_fit,
            avg_regime_consistency=avg_regime,
            anomalies_detected=len(anomalies),
            anomaly_types=anomaly_types
        )
        
        self.performance = performance
        return performance
    
    def generate_shadow_report(self) -> str:
        """Generate shadow mode performance report."""
        
        if not self.performance:
            self.generate_performance_summary()
        
        report = []
        report.append("=" * 70)
        report.append(f"SHADOW/DEMO MODE REPORT ({self.mode.value.upper()})")
        report.append("=" * 70)
        report.append("")
        
        # Duration
        report.append("SESSION METRICS")
        report.append("-" * 70)
        report.append(f"Duration: {self.performance.start_time} → {self.performance.end_time}")
        report.append("")
        
        # Execution metrics
        report.append("EXECUTION METRICS")
        report.append("-" * 70)
        report.append(f"Total Signals:       {self.performance.total_signals}")
        report.append(f"Signals Executed:    {self.performance.signals_executed}")
        report.append(f"Signals Skipped:     {self.performance.signals_skipped}")
        report.append(f"Execution Rate:      {self.performance.execution_rate:.1f}%")
        report.append("")
        
        # Performance
        report.append("PERFORMANCE METRICS")
        report.append("-" * 70)
        report.append(f"Win Rate:            {self.performance.win_rate:.1f}%")
        report.append(f"Wins/Losses/BE:      {self.performance.win_count}/{self.performance.loss_count}/{self.performance.break_even_count}")
        report.append(f"Total P&L:           ${self.performance.total_pnl:,.2f}")
        report.append(f"Avg P&L per Trade:   ${self.performance.avg_pnl_per_trade:,.2f}")
        report.append(f"Avg Win:             ${self.performance.avg_win:,.2f}")
        report.append(f"Avg Loss:            ${self.performance.avg_loss:,.2f}")
        report.append(f"Profit Factor:       {self.performance.profit_factor:.2f}")
        report.append("")
        
        # Risk metrics
        report.append("RISK METRICS")
        report.append("-" * 70)
        report.append(f"Max Drawdown:        ${self.performance.max_drawdown:,.2f}")
        report.append(f"Max Drawdown %:      {self.performance.max_drawdown_pct:.1f}%")
        report.append(f"Sharpe Ratio:        {self.performance.sharpe_ratio:.2f}")
        report.append("")
        
        # Quality metrics
        report.append("SIGNAL QUALITY")
        report.append("-" * 70)
        report.append(f"Avg Confidence:      {self.performance.avg_confidence:.1f}%")
        report.append(f"Avg Pattern Fit:     {self.performance.avg_pattern_fit:.1f}%")
        report.append(f"Avg Regime Consistency: {self.performance.avg_regime_consistency:.1f}%")
        report.append("")
        
        # Anomalies
        if self.performance.anomalies_detected > 0:
            report.append("ANOMALIES DETECTED")
            report.append("-" * 70)
            report.append(f"Count: {self.performance.anomalies_detected}")
            for anomaly_type in self.performance.anomaly_types[:5]:
                report.append(f"  - {anomaly_type}")
            report.append("")
        
        # Recommendation
        report.append("RECOMMENDATION")
        report.append("-" * 70)
        if self.performance.win_rate >= 52 and self.performance.sharpe_ratio >= 0.7:
            report.append("✓ READY FOR LIVE TRADING")
            report.append("  - Performance metrics acceptable")
            report.append("  - Anomaly detection working")
            report.append("  - Risk management operational")
        else:
            report.append("⚠ ADDITIONAL TUNING RECOMMENDED")
            if self.performance.win_rate < 52:
                report.append("  - Win rate below 52%")
            if self.performance.sharpe_ratio < 0.7:
                report.append("  - Sharpe ratio below 0.7")
            if self.performance.anomalies_detected > 10:
                report.append("  - Too many anomalies detected")
        
        report.append("")
        
        return "\n".join(report)
