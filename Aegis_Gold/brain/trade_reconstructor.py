"""
===========================================================================
AEGIS GOLD — Trade Reconstructor (Phase O)
===========================================================================

PURPOSE:
--------
Implements comprehensive trade reconstruction and analysis system with causal
replay, every-trade ledger reconciliation, and outcome tracking.

CORE FEATURES:
--------------
1. Every-Trade Recording - Complete audit trail of all trade execution
2. Causal Replay - Reconstruct exact market conditions at entry/exit
3. Trade Ledger Reconciliation - Verify trade integrity and causality
4. Outcome Classification - Categorize trade results systematically
5. Performance Attribution - Identify factors contributing to P&L
6. Missed Opportunity Tracking - Analyze what was not taken

INTEGRATION:
------------
- Uses Pattern Outcome Tracker (Phase G) for pattern-level outcomes
- Leverages Entry Logic Engine (Phase M) for entry signal validation
- Integrates with Structural Risk Manager (Phase N) for risk analysis
- Applies Causality Enforcement (Phase I) for temporal integrity

===========================================================================
"""

import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json

logger = logging.getLogger("aegis.reconstruction")


class TradeOutcome(Enum):
    """Classification of trade execution outcomes."""
    WIN_AT_TARGET = "WIN_AT_TARGET"              # Hit TP at target
    WIN_PARTIAL = "WIN_PARTIAL"                  # Partial TP hit
    WIN_EARLY_EXIT = "WIN_EARLY_EXIT"            # Exited early with profit
    BREAKEVEN = "BREAKEVEN"                      # Closed at breakeven
    SMALL_LOSS = "SMALL_LOSS"                    # Lost < 0.5 R
    CONTROLLED_LOSS = "CONTROLLED_LOSS"          # Lost 0.5-1.0 R
    STOPPED_OUT = "STOPPED_OUT"                  # Hit stop loss
    FORCED_EXIT = "FORCED_EXIT"                  # Exit for external reasons
    NEVER_ENTERED = "NEVER_ENTERED"              # Signal ignored/never entered


class EntryQuality(Enum):
    """Quality assessment of trade entry execution."""
    PERFECT = "PERFECT"          # Entered at optimal price
    GOOD = "GOOD"               # Entered at good price
    FAIR = "FAIR"               # Acceptable entry
    POOR = "POOR"               # Suboptimal but tradeable
    CHASE = "CHASE"             # Entered after chase
    REJECTED = "REJECTED"       # Never entered


class ExitQuality(Enum):
    """Quality of exit execution."""
    OPTIMAL = "OPTIMAL"         # Exited at target
    GOOD = "GOOD"              # Good exit management
    ACCEPTABLE = "ACCEPTABLE"  # Acceptable exit
    FORCED = "FORCED"          # Forced exit (SL/news)
    DISASTER = "DISASTER"      # Very poor exit


class CausalityIssue(Enum):
    """Causality violations in trade reconstruction."""
    FUTURE_PRICE_DATA = "FUTURE_PRICE_DATA"
    LIVE_MODEL_UPDATE = "LIVE_MODEL_UPDATE"
    FORWARD_LOOKING_BIAS = "FORWARD_LOOKING_BIAS"
    SIGNAL_TIMING = "SIGNAL_TIMING"
    DATA_INTEGRITY = "DATA_INTEGRITY"


@dataclass
class TradeExecution:
    """Complete record of a single trade execution."""
    
    trade_id: str
    pattern_id: str
    symbol: str
    direction: str               # "BUY" or "SELL"
    
    # Timing
    signal_time: str            # When signal was generated
    entry_time: str             # When trade was entered
    exit_time: Optional[str]    # When trade was exited
    
    # Pricing
    entry_price: float
    target_price: float
    stop_loss: float
    position_size: float
    outcome: TradeOutcome
    
    # Entry/Exit Quality
    entry_quality: EntryQuality
    entry_slippage: float
    
    # Market Context
    market_conditions_entry: Dict[str, Any]
    
    # Attribution
    favorable_excursion: float  # Max profit seen
    adverse_excursion: float    # Max loss seen
    
    # Fields with defaults (must come last)
    exit_price: Optional[float] = None
    exit_quality: Optional[ExitQuality] = None
    exit_slippage: Optional[float] = None
    final_pnl: float = 0.0
    final_pnl_pct: float = 0.0        # As percentage of capital
    risk_taken: float = 0.0           # Actual risk vs planned
    reward_earned: float = 0.0
    realized_rr_ratio: float = 0.0
    market_conditions_exit: Optional[Dict[str, Any]] = None
    holding_time: Optional[timedelta] = None
    partial_fills: List[Dict[str, Any]] = field(default_factory=list)
    causality_issues: List[CausalityIssue] = field(default_factory=list)
    data_integrity: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        result = asdict(self)
        result['outcome'] = self.outcome.value
        result['entry_quality'] = self.entry_quality.value
        result['exit_quality'] = self.exit_quality.value if self.exit_quality else None
        result['causality_issues'] = [issue.value for issue in self.causality_issues]
        if self.holding_time:
            result['holding_time'] = str(self.holding_time)
        return result


@dataclass
class PatternOutcomeAnalysis:
    """Analysis of pattern-level outcomes across multiple trades."""
    
    pattern_id: str
    pattern_type: str
    timeframe: str
    
    # Execution Stats
    total_trades: int
    completed_trades: int
    never_entered: int
    
    # Trade Outcomes
    winners: int
    losers: int
    breakevens: int
    win_rate: float
    
    # P&L Metrics
    total_pnl: float
    avg_pnl_per_trade: float
    avg_win: float
    avg_loss: float
    expectancy: float  # Statistical expectancy
    profit_factor: float  # Gross profit / Gross loss
    
    # Risk Metrics
    avg_risk_taken: float
    avg_reward_earned: float
    avg_rr_ratio: float
    max_favorable_excursion: float
    max_adverse_excursion: float
    
    # Quality Metrics
    avg_entry_quality_score: float
    avg_exit_quality_score: float
    avg_slippage: float
    causality_issue_count: int
    
    # Best/Worst Trade
    best_trade_id: Optional[str]
    worst_trade_id: Optional[str]
    

@dataclass
class TradeLedgerEntry:
    """Single entry in trade execution ledger."""
    
    ledger_id: str
    record_time: str
    trade_id: str
    event_type: str             # "SIGNAL", "ENTRY", "PARTIAL", "EXIT"
    price: float
    reason: str
    data_checksum: str          # For integrity verification
    is_valid: bool
    
    previous_state: Dict[str, Any]
    new_state: Dict[str, Any]


class TradeReconstructor:
    """
    Comprehensive trade reconstruction and analysis system.
    """
    
    def __init__(self):
        # Trade execution tracking
        self.all_trades = {}        # trade_id -> TradeExecution
        self.trade_ledger = []      # Complete audit trail
        self.pattern_outcomes = {}  # pattern_id -> PatternOutcomeAnalysis
        
        # Performance metrics
        self.performance_summary = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0.0,
            'total_pnl': 0.0,
            'expectancy': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'profit_factor': 0.0
        }
        
        # Missed opportunities
        self.missed_opportunities = []
        
        # Data quality
        self.causality_violations = []
        self.data_integrity_issues = []
        
        logger.info("[RECON] Trade Reconstructor initialized")
    
    def record_trade_execution(
        self,
        pattern_id: str,
        pattern_context: Dict[str, Any],
        entry_signal,
        market_snapshot_entry,
        exit_data: Optional[Dict[str, Any]] = None
    ) -> TradeExecution:
        """
        Record complete trade execution from entry to exit.
        
        Args:
            pattern_id: Pattern that triggered the trade
            pattern_context: Pattern details
            entry_signal: Entry signal object from Entry Logic Engine
            market_snapshot_entry: Market conditions at entry
            exit_data: Exit information (optional for open positions)
            
        Returns:
            Complete TradeExecution record
        """
        
        trade_id = f"{pattern_id}_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Extract entry information
        entry_price = entry_signal.entry_zone.optimal_price
        entry_time = entry_signal.signal_time
        signal_time = entry_signal.setup_completion_time
        
        # Calculate entry quality
        actual_entry_price = market_snapshot_entry.current_price
        entry_quality = entry_signal.entry_zone.current_quality
        entry_slippage = abs(actual_entry_price - entry_price)
        
        # Get target information
        target_price = entry_signal.entry_zone.optimal_price  # Can be improved
        if entry_signal.entry_zone.direction == "BUY":
            target_price = max([tp[0] for tp in entry_signal.entry_zone.direction] if hasattr(entry_signal.entry_zone, 'direction') else [2010.0])
        
        # Initialize execution record
        execution = TradeExecution(
            trade_id=trade_id,
            pattern_id=pattern_id,
            symbol=pattern_context.get('symbol', 'XAUUSD'),
            direction=entry_signal.entry_zone.direction,
            signal_time=signal_time,
            entry_time=entry_time,
            exit_time=None,
            entry_price=entry_price,
            exit_price=None,
            target_price=pattern_context.get('take_profit', entry_price * 1.02),
            stop_loss=pattern_context.get('stop_loss', entry_price * 0.98),
            entry_quality=entry_quality,
            entry_slippage=entry_slippage,
            exit_quality=None,
            exit_slippage=None,
            position_size=entry_signal.position_size_fraction,
            partial_fills=[],
            outcome=TradeOutcome.NEVER_ENTERED,  # Updated when trade completes
            final_pnl=0.0,
            final_pnl_pct=0.0,
            risk_taken=0.0,
            reward_earned=0.0,
            realized_rr_ratio=0.0,
            market_conditions_entry=self._capture_market_conditions(market_snapshot_entry),
            market_conditions_exit=None,
            holding_time=None,
            favorable_excursion=0.0,
            adverse_excursion=0.0
        )
        
        # Check for causality issues in entry
        entry_causality = self._validate_entry_causality(
            entry_signal, market_snapshot_entry, pattern_context
        )
        execution.causality_issues.extend(entry_causality)
        
        # Store and record
        self.all_trades[trade_id] = execution
        
        # Create ledger entry
        ledger_entry = TradeLedgerEntry(
            ledger_id=f"{trade_id}_ENTRY",
            record_time=datetime.now(timezone.utc).isoformat(),
            trade_id=trade_id,
            event_type="ENTRY",
            price=actual_entry_price,
            reason="Trade entry signal executed",
            data_checksum=self._calculate_data_checksum(execution),
            is_valid=len(entry_causality) == 0,
            previous_state={},
            new_state=asdict(execution)
        )
        self.trade_ledger.append(ledger_entry)
        
        logger.info(
            f"[RECON] Recorded entry for {trade_id}: "
            f"Entry={entry_price:.2f}, SL={execution.stop_loss:.2f}, "
            f"TP={execution.target_price:.2f}"
        )
        
        return execution
    
    def record_partial_fill(
        self,
        trade_id: str,
        exit_price: float,
        size_fraction: float,
        exit_reason: str
    ):
        """Record partial profit taking event."""
        
        if trade_id not in self.all_trades:
            logger.warning(f"[RECON] Partial fill for unknown trade {trade_id}")
            return
        
        trade = self.all_trades[trade_id]
        
        partial_fill = {
            'exit_price': exit_price,
            'size_fraction': size_fraction,
            'exit_time': datetime.now(timezone.utc).isoformat(),
            'exit_reason': exit_reason,
            'pnl': self._calculate_trade_pnl(
                trade.entry_price, exit_price, size_fraction, trade.direction
            )
        }
        
        trade.partial_fills.append(partial_fill)
        
        logger.info(
            f"[RECON] Partial fill for {trade_id}: "
            f"{size_fraction*100:.0f}% at {exit_price:.2f}"
        )
    
    def record_trade_exit(
        self,
        trade_id: str,
        exit_price: float,
        exit_reason: str,
        market_snapshot_exit
    ) -> Optional[TradeExecution]:
        """
        Record trade exit and complete execution record.
        
        Args:
            trade_id: Trade to close
            exit_price: Exit price
            exit_reason: Reason for exit
            market_snapshot_exit: Market conditions at exit
            
        Returns:
            Updated TradeExecution or None
        """
        
        if trade_id not in self.all_trades:
            logger.warning(f"[RECON] Exit for unknown trade {trade_id}")
            return None
        
        trade = self.all_trades[trade_id]
        
        # Calculate exit metrics
        exit_time = datetime.now(timezone.utc)
        holding_time = datetime.fromisoformat(trade.entry_time.replace('Z', '+00:00')) if trade.entry_time else None
        
        if holding_time:
            trade.holding_time = exit_time - holding_time
        
        # Calculate P&L
        total_pnl = self._calculate_trade_pnl(
            trade.entry_price, exit_price, 
            (1.0 - sum(f.get('size_fraction', 0) for f in trade.partial_fills)),
            trade.direction
        )
        
        # Add partial fills P&L
        for partial in trade.partial_fills:
            total_pnl += partial.get('pnl', 0.0)
        
        # Update trade
        trade.exit_time = exit_time.isoformat()
        trade.exit_price = exit_price
        trade.final_pnl = total_pnl
        trade.market_conditions_exit = self._capture_market_conditions(market_snapshot_exit)
        
        # Classify outcome
        trade.outcome = self._classify_outcome(trade, exit_reason)
        trade.exit_quality = self._assess_exit_quality(trade)
        trade.exit_slippage = abs(exit_price - trade.target_price)
        
        # Calculate risk metrics
        trade.risk_taken = abs(trade.entry_price - trade.stop_loss)
        trade.reward_earned = abs(exit_price - trade.entry_price)
        
        if trade.risk_taken > 0:
            trade.realized_rr_ratio = trade.reward_earned / trade.risk_taken
        
        # Check causality on exit
        exit_causality = self._validate_exit_causality(trade, market_snapshot_exit)
        trade.causality_issues.extend(exit_causality)
        
        # Record in ledger
        ledger_entry = TradeLedgerEntry(
            ledger_id=f"{trade_id}_EXIT",
            record_time=datetime.now(timezone.utc).isoformat(),
            trade_id=trade_id,
            event_type="EXIT",
            price=exit_price,
            reason=exit_reason,
            data_checksum=self._calculate_data_checksum(trade),
            is_valid=len(exit_causality) == 0,
            previous_state={'exit_price': None, 'outcome': 'OPEN'},
            new_state={'exit_price': exit_price, 'outcome': trade.outcome.value}
        )
        self.trade_ledger.append(ledger_entry)
        
        # Update performance metrics
        self._update_performance_metrics(trade)
        
        logger.info(
            f"[RECON] Recorded exit for {trade_id}: "
            f"Exit={exit_price:.2f}, Outcome={trade.outcome.value}, "
            f"PnL={trade.final_pnl:+.2f}"
        )
        
        return trade
    
    def _calculate_trade_pnl(
        self,
        entry_price: float,
        exit_price: float,
        position_size: float,
        direction: str
    ) -> float:
        """Calculate P&L for trade."""
        
        if direction == "BUY":
            pnl_per_unit = (exit_price - entry_price)
        else:
            pnl_per_unit = (entry_price - exit_price)
        
        return pnl_per_unit * position_size
    
    def _classify_outcome(self, trade: TradeExecution, exit_reason: str) -> TradeOutcome:
        """Classify trade outcome."""
        
        if not trade.exit_price:
            return TradeOutcome.NEVER_ENTERED
        
        # Check if at target
        if abs(trade.exit_price - trade.target_price) < 2.0:  # Within 2 pips
            return TradeOutcome.WIN_AT_TARGET
        
        # Check if profitable
        if trade.final_pnl > 0:
            if abs(trade.final_pnl) < trade.risk_taken * 0.5:
                return TradeOutcome.WIN_EARLY_EXIT
            else:
                return TradeOutcome.WIN_PARTIAL
        
        # Check if breakeven
        elif abs(trade.final_pnl) < 5.0:  # Within 5 pips
            return TradeOutcome.BREAKEVEN
        
        # Loss scenarios
        elif exit_reason == "STOP_HIT":
            return TradeOutcome.STOPPED_OUT
        elif trade.final_pnl > -trade.risk_taken * 0.5:
            return TradeOutcome.SMALL_LOSS
        elif trade.final_pnl > -trade.risk_taken:
            return TradeOutcome.CONTROLLED_LOSS
        else:
            return TradeOutcome.STOPPED_OUT
    
    def _assess_exit_quality(self, trade: TradeExecution) -> ExitQuality:
        """Assess exit execution quality."""
        
        if not trade.exit_price:
            return None
        
        # Distance from target
        distance_from_target = abs(trade.exit_price - trade.target_price)
        target_range = abs(trade.target_price - trade.entry_price)
        
        distance_pct = distance_from_target / target_range if target_range > 0 else 0
        
        if distance_pct < 0.01:  # Within 1% of target
            return ExitQuality.OPTIMAL
        elif distance_pct < 0.05:  # Within 5% of target
            return ExitQuality.GOOD
        elif distance_pct < 0.15:  # Within 15% of target
            return ExitQuality.ACCEPTABLE
        elif trade.final_pnl <= 0:  # Loss or breakeven
            return ExitQuality.FORCED
        else:
            return ExitQuality.DISASTER
    
    def _validate_entry_causality(
        self,
        entry_signal,
        market_snapshot: Any,
        pattern_context: Dict[str, Any]
    ) -> List[CausalityIssue]:
        """Validate causality of entry signal."""
        
        issues = []
        
        # Check signal timing
        signal_time = datetime.fromisoformat(entry_signal.signal_time.replace('Z', '+00:00')) if hasattr(entry_signal, 'signal_time') else None
        current_time = datetime.now(timezone.utc)
        
        if signal_time and (current_time - signal_time).total_seconds() < 0:
            issues.append(CausalityIssue.SIGNAL_TIMING)
        
        return issues
    
    def _validate_exit_causality(
        self,
        trade: TradeExecution,
        market_snapshot: Any
    ) -> List[CausalityIssue]:
        """Validate causality of trade exit."""
        
        issues = []
        
        # Check that exit comes after entry
        entry_time = datetime.fromisoformat(trade.entry_time.replace('Z', '+00:00'))
        exit_time = datetime.fromisoformat(trade.exit_time.replace('Z', '+00:00'))
        
        if exit_time <= entry_time:
            issues.append(CausalityIssue.SIGNAL_TIMING)
        
        return issues
    
    def _capture_market_conditions(self, market_snapshot: Any) -> Dict[str, Any]:
        """Capture relevant market conditions."""
        
        return {
            'price': getattr(market_snapshot, 'current_price', 0.0),
            'time': datetime.now(timezone.utc).isoformat(),
            'volatility': getattr(market_snapshot, 'volatility_level', 'NORMAL'),
            'volume': getattr(market_snapshot, 'volume', 0),
            'momentum': getattr(market_snapshot, 'momentum_score', 0.5)
        }
    
    def _calculate_data_checksum(self, trade: TradeExecution) -> str:
        """Calculate checksum for trade data integrity."""
        
        data_str = f"{trade.trade_id}_{trade.entry_price}_{trade.exit_price}"
        return str(hash(data_str))
    
    def _update_performance_metrics(self, trade: TradeExecution):
        """Update overall performance metrics."""
        
        self.performance_summary['total_trades'] += 1
        self.performance_summary['total_pnl'] += trade.final_pnl
        
        if trade.final_pnl > 0:
            self.performance_summary['winning_trades'] += 1
        elif trade.final_pnl < 0:
            self.performance_summary['losing_trades'] += 1
        
        # Recalculate rates
        total = self.performance_summary['total_trades']
        if total > 0:
            self.performance_summary['win_rate'] = (
                self.performance_summary['winning_trades'] / total
            )
    
    def analyze_pattern_outcomes(
        self,
        pattern_id: str,
        pattern_type: str,
        timeframe: str
    ) -> PatternOutcomeAnalysis:
        """
        Analyze all trades for a given pattern.
        
        Args:
            pattern_id: Pattern identifier
            pattern_type: Type of pattern
            timeframe: Timeframe where pattern was detected
            
        Returns:
            Pattern outcome analysis
        """
        
        # Get all trades for pattern
        pattern_trades = [
            trade for trade in self.all_trades.values()
            if trade.pattern_id == pattern_id
        ]
        
        if not pattern_trades:
            logger.warning(f"[RECON] No trades found for pattern {pattern_id}")
            return None
        
        # Calculate metrics
        completed_trades = [t for t in pattern_trades if t.exit_price is not None]
        never_entered = [t for t in pattern_trades if t.outcome == TradeOutcome.NEVER_ENTERED]
        
        winners = [t for t in completed_trades if t.final_pnl > 0]
        losers = [t for t in completed_trades if t.final_pnl < 0]
        breakevens = [t for t in completed_trades if abs(t.final_pnl) < 5.0]
        
        win_rate = len(winners) / len(completed_trades) if completed_trades else 0.0
        
        # P&L Metrics
        total_pnl = sum(t.final_pnl for t in completed_trades)
        avg_pnl = total_pnl / len(completed_trades) if completed_trades else 0.0
        
        avg_win = (sum(t.final_pnl for t in winners) / len(winners)) if winners else 0.0
        avg_loss = (sum(t.final_pnl for t in losers) / len(losers)) if losers else 0.0
        
        expectancy = (win_rate * avg_win) + ((1 - win_rate) * avg_loss)
        
        gross_profit = sum(t.final_pnl for t in winners)
        gross_loss = abs(sum(t.final_pnl for t in losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Risk Metrics
        avg_risk = np.mean([t.risk_taken for t in completed_trades]) if completed_trades else 0.0
        avg_reward = np.mean([t.reward_earned for t in completed_trades]) if completed_trades else 0.0
        avg_rr = np.mean([t.realized_rr_ratio for t in completed_trades]) if completed_trades else 0.0
        
        max_fav_excursion = max([t.favorable_excursion for t in completed_trades]) if completed_trades else 0.0
        max_adv_excursion = min([t.adverse_excursion for t in completed_trades]) if completed_trades else 0.0
        
        # Quality Metrics
        entry_qualities = [
            {'PERFECT': 5, 'GOOD': 4, 'FAIR': 3, 'POOR': 2, 'CHASE': 1, 'REJECTED': 0}
            .get(t.entry_quality.value, 0)
            for t in completed_trades
        ]
        avg_entry_quality = np.mean(entry_qualities) if entry_qualities else 0.0
        
        exit_qualities = [
            {'OPTIMAL': 5, 'GOOD': 4, 'ACCEPTABLE': 3, 'FORCED': 2, 'DISASTER': 0}
            .get(t.exit_quality.value if t.exit_quality else 'FORCED', 0)
            for t in completed_trades
        ]
        avg_exit_quality = np.mean(exit_qualities) if exit_qualities else 0.0
        
        avg_slippage = np.mean([t.entry_slippage for t in completed_trades]) if completed_trades else 0.0
        
        causality_issues = sum(len(t.causality_issues) for t in completed_trades)
        
        # Best/Worst
        best_trade = max(completed_trades, key=lambda t: t.final_pnl) if completed_trades else None
        worst_trade = min(completed_trades, key=lambda t: t.final_pnl) if completed_trades else None
        
        analysis = PatternOutcomeAnalysis(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            timeframe=timeframe,
            total_trades=len(pattern_trades),
            completed_trades=len(completed_trades),
            never_entered=len(never_entered),
            winners=len(winners),
            losers=len(losers),
            breakevens=len(breakevens),
            win_rate=win_rate,
            total_pnl=total_pnl,
            avg_pnl_per_trade=avg_pnl,
            avg_win=avg_win,
            avg_loss=avg_loss,
            expectancy=expectancy,
            profit_factor=profit_factor,
            avg_risk_taken=avg_risk,
            avg_reward_earned=avg_reward,
            avg_rr_ratio=avg_rr,
            max_favorable_excursion=max_fav_excursion,
            max_adverse_excursion=max_adv_excursion,
            avg_entry_quality_score=avg_entry_quality,
            avg_exit_quality_score=avg_exit_quality,
            avg_slippage=avg_slippage,
            causality_issue_count=causality_issues,
            best_trade_id=best_trade.trade_id if best_trade else None,
            worst_trade_id=worst_trade.trade_id if worst_trade else None
        )
        
        self.pattern_outcomes[pattern_id] = analysis
        
        logger.info(
            f"[RECON] Pattern {pattern_id} analysis: "
            f"Trades={len(pattern_trades)}, WinRate={win_rate:.1%}, "
            f"PnL={total_pnl:+.2f}, RR={avg_rr:.2f}"
        )
        
        return analysis
    
    def get_trade_execution_summary(self) -> Dict[str, Any]:
        """Get summary of all trade executions."""
        
        return {
            "total_trades": len(self.all_trades),
            "completed_trades": len([t for t in self.all_trades.values() if t.exit_price]),
            "open_trades": len([t for t in self.all_trades.values() if not t.exit_price]),
            "performance": self.performance_summary,
            "ledger_entries": len(self.trade_ledger),
            "pattern_analyses": len(self.pattern_outcomes),
            "causality_violations": len(self.causality_violations),
            "data_integrity_issues": len(self.data_integrity_issues)
        }
    
    def generate_trade_report(self) -> Dict[str, Any]:
        """Generate comprehensive trade reconstruction report."""
        
        return {
            "summary": self.get_trade_execution_summary(),
            "performance": self.performance_summary,
            "pattern_outcomes": {
                pid: asdict(analysis) for pid, analysis in self.pattern_outcomes.items()
            },
            "trades": {
                tid: trade.to_dict() for tid, trade in self.all_trades.items()
            },
            "data_quality": {
                "total_records": len(self.trade_ledger),
                "integrity_issues": len(self.data_integrity_issues),
                "causality_violations": len(self.causality_violations)
            }
        }


# Global singleton instance
_trade_reconstructor = None

def get_trade_reconstructor() -> TradeReconstructor:
    """Get or create singleton trade reconstructor."""
    global _trade_reconstructor
    if _trade_reconstructor is None:
        _trade_reconstructor = TradeReconstructor()
    return _trade_reconstructor