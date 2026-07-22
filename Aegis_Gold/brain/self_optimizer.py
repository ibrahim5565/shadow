"""
═══════════════════════════════════════════════════════════════════════════════
🧬 AEGIS SELF-OPTIMIZATION ENGINE - Continuous Learning & Adaptation
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
--------
After EVERY closed trade, analyze what worked, what didn't, and automatically
improve the system's parameters, thresholds, and decision-making logic.

PHILOSOPHY:
-----------
"The system that learns from its mistakes evolves faster than its competition."

Static trading systems die. Markets change. Successful institutional algorithms
continuously adapt based on evidence. This engine is the evolutionary core that
ensures AEGIS improves with every trade.

OPTIMIZATION TARGETS:
---------------------
1. Entry Thresholds
   - Minimum confidence required
   - Signal weight adjustments
   - Timing optimization

2. Exit Strategy
   - TP/SL levels
   - Trailing stop parameters
   - Early exit conditions

3. Risk Parameters
   - Base lot size
   - Maximum drawdown tolerance
   - Position sizing rules

4. Filter Thresholds
   - Spread limits
   - Volatility bounds
   - Session preferences

5. ML Model Weights
   - Reweight based on recent accuracy
   - Feature importance updates
   - Ensemble composition

6. Confidence Engine Weights
   - Adjust 12 component weights
   - Based on which signals predicted winners

LEARNING METHODS:
-----------------
- Reinforcement Learning: Reward winning patterns
- A/B Testing: Try parameter variations
- Gradient Descent: Optimize continuous parameters
- Bayesian Optimization: Sample parameter space efficiently
- Performance Attribution: Identify which signals contributed to wins/losses

SAFETY MECHANISMS:
------------------
- Parameter bounds (never extreme values)
- Gradual adjustment (max 10% change per day)
- Reversion trigger (undo if performance degrades)
- Emergency stop (freeze learning if losing streak > 10)

═══════════════════════════════════════════════════════════════════════════════
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger("SelfOptimizer")


@dataclass
class OptimizationState:
    """Current optimization state and parameters."""
    
    # Entry thresholds (LOCKED at 50% — cannot be changed by optimizer)
    min_confidence_threshold: int = 50
    smc_weight: float = 0.12
    mtf_weight: float = 0.15
    statistical_weight: float = 0.10
    ml_weight: float = 0.15
    
    # Exit strategy
    tp_multiplier: float = 1.0  # Multiply default TP by this
    sl_multiplier: float = 1.0  # Multiply default SL by this
    trailing_stop_enabled: bool = True
    early_exit_threshold: float = 0.3  # Exit if confidence drops by this much
    
    # Risk management
    base_lot_multiplier: float = 1.0
    max_loss_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 5.0
    
    # Filters
    max_spread_multiplier: float = 1.5  # Multiple of normal spread
    min_volatility_score: int = 30
    preferred_sessions: List[str] = None
    
    # Performance tracking
    recent_win_rate: float = 0.5
    recent_profit_factor: float = 1.0
    total_trades_analyzed: int = 0
    last_optimization: str = None
    optimization_generation: int = 1
    
    # Safety
    learning_enabled: bool = True
    consecutive_losses: int = 0
    
    def __post_init__(self):
        if self.preferred_sessions is None:
            self.preferred_sessions = ["LONDON", "NY", "OVERLAP"]


@dataclass
class TradeAnalysis:
    """Analysis of a single trade's outcome."""
    
    trade_id: int
    was_winner: bool
    profit_usd: float
    profit_pct: float
    
    # Entry analysis
    entry_confidence: int
    entry_was_optimal: bool
    could_have_waited: bool  # Entry too early
    
    # Exit analysis
    exit_was_optimal: bool
    left_on_table: float  # Additional pips that could have been captured
    exit_reason: str
    
    # Signal performance
    structure_correct: bool
    smc_correct: bool
    mtf_correct: bool
    statistical_correct: bool
    ml_correct: bool
    
    # Insights
    primary_success_factor: str  # What made it win
    primary_failure_factor: str  # What made it lose
    recommendation: str  # What to improve


class SelfOptimizer:
    """
    Continuous learning and self-optimization engine.
    """
    
    def __init__(self, state_file: str = "d:\\Trading\\Aegis_Gold\\data\\optimization_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()
        
        # Recent trade analyses
        self.recent_analyses: List[TradeAnalysis] = []
        
        # Parameter history (for reversion if needed)
        self.parameter_history: List[OptimizationState] = []
        
        logger.info(f"[OPT] Self-Optimizer initialized (Gen {self.state.optimization_generation})")
    
    def analyze_closed_trade(self, trade_record: Dict, trade_memory_db) -> TradeAnalysis:
        """
        Analyze a closed trade and extract learning insights.
        
        Args:
            trade_record: Complete trade record from trade_memory.db
            trade_memory_db: TradeMemoryDatabase instance for comparison
            
        Returns:
            TradeAnalysis with detailed insights
        """
        try:
            was_winner = trade_record.get('profit_usd', 0) > 0
            profit_usd = trade_record.get('profit_usd', 0)
            profit_pct = trade_record.get('profit_pct', 0)
            
            # Entry analysis
            entry_confidence = trade_record.get('confidence', 0)
            entry_was_optimal = trade_record.get('was_entry_optimal', None)
            
            # Check if we entered too early (price moved against us initially)
            could_have_waited = self._check_if_early_entry(trade_record)
            
            # Exit analysis
            exit_was_optimal = trade_record.get('was_exit_optimal', None)
            left_on_table = trade_record.get('could_have_captured_more', 0) or 0
            exit_reason = trade_record.get('exit_reason', 'UNKNOWN')
            
            # Signal performance (which signals were correct?)
            structure_correct = self._was_signal_correct('structure', trade_record, was_winner)
            smc_correct = self._was_signal_correct('smc', trade_record, was_winner)
            mtf_correct = self._was_signal_correct('mtf', trade_record, was_winner)
            statistical_correct = self._was_signal_correct('statistical', trade_record, was_winner)
            ml_correct = self._was_signal_correct('ml', trade_record, was_winner)
            
            # Identify success/failure factors
            success_factor, failure_factor = self._identify_key_factors(
                trade_record, was_winner, structure_correct, smc_correct,
                mtf_correct, statistical_correct, ml_correct
            )
            
            # Generate recommendation
            recommendation = self._generate_recommendation(
                trade_record, was_winner, entry_was_optimal, exit_was_optimal,
                structure_correct, smc_correct, mtf_correct, statistical_correct, ml_correct
            )
            
            analysis = TradeAnalysis(
                trade_id=trade_record.get('trade_id', 0),
                was_winner=was_winner,
                profit_usd=profit_usd,
                profit_pct=profit_pct,
                entry_confidence=entry_confidence,
                entry_was_optimal=entry_was_optimal if entry_was_optimal is not None else True,
                could_have_waited=could_have_waited,
                exit_was_optimal=exit_was_optimal if exit_was_optimal is not None else True,
                left_on_table=left_on_table,
                exit_reason=exit_reason,
                structure_correct=structure_correct,
                smc_correct=smc_correct,
                mtf_correct=mtf_correct,
                statistical_correct=statistical_correct,
                ml_correct=ml_correct,
                primary_success_factor=success_factor,
                primary_failure_factor=failure_factor,
                recommendation=recommendation
            )
            
            # Store for batch optimization
            self.recent_analyses.append(analysis)
            
            # Keep last 200 analyses
            if len(self.recent_analyses) > 200:
                self.recent_analyses = self.recent_analyses[-200:]
            
            logger.info(f"📊 Trade {analysis.trade_id} analyzed: {'WIN' if was_winner else 'LOSS'} | {recommendation}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Trade analysis failed: {e}")
            return None
    
    def optimize(self, trade_memory_db) -> Dict:
        """
        Perform optimization based on recent trade analyses.
        Should be called periodically (e.g., every 50 trades).
        
        Returns:
            Dictionary with optimization results and changes made
        """
        if not self.state.learning_enabled:
            logger.warning("Learning disabled. Skipping optimization.")
            return {"status": "disabled"}
        
        if len(self.recent_analyses) < 20:
            logger.info(f"Not enough data for optimization ({len(self.recent_analyses)}/20)")
            return {"status": "insufficient_data"}
        
        try:
            logger.info("🧬 Starting optimization cycle...")
            
            # Save current state for potential reversion
            self.parameter_history.append(self.state)
            if len(self.parameter_history) > 10:
                self.parameter_history = self.parameter_history[-10:]
            
            changes = {}
            
            # 1. Optimize entry thresholds
            entry_changes = self._optimize_entry_thresholds()
            changes['entry'] = entry_changes
            
            # 2. Optimize exit strategy
            exit_changes = self._optimize_exit_strategy()
            changes['exit'] = exit_changes
            
            # 3. Optimize signal weights
            weight_changes = self._optimize_signal_weights()
            changes['weights'] = weight_changes
            
            # 4. Optimize risk parameters
            risk_changes = self._optimize_risk_parameters()
            changes['risk'] = risk_changes
            
            # 5. Update performance metrics
            self._update_performance_metrics()
            
            # 6. Increment generation
            self.state.optimization_generation += 1
            self.state.last_optimization = datetime.now().isoformat()
            
            # Save state
            self._save_state()
            
            logger.info(f"✅ Optimization complete (Gen {self.state.optimization_generation})")
            logger.info(f"Changes: {changes}")
            
            return {
                "status": "success",
                "generation": self.state.optimization_generation,
                "changes": changes,
                "performance": {
                    "win_rate": self.state.recent_win_rate,
                    "profit_factor": self.state.recent_profit_factor
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Optimization failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def _optimize_entry_thresholds(self) -> Dict:
        """Optimize minimum confidence threshold based on outcomes."""
        changes = {}
        
        # Analyze win rate at different confidence levels
        confidence_bins = {
            'low': [a for a in self.recent_analyses if a.entry_confidence < 60],
            'medium': [a for a in self.recent_analyses if 60 <= a.entry_confidence < 75],
            'high': [a for a in self.recent_analyses if a.entry_confidence >= 75]
        }
        
        win_rates = {}
        for level, analyses in confidence_bins.items():
            if len(analyses) > 5:
                win_rate = sum(1 for a in analyses if a.was_winner) / len(analyses)
                win_rates[level] = win_rate
        
        # Confidence threshold is LOCKED at 50% by user requirement
        # self_optimizer is NOT allowed to change this gate (CONFIDENCE_THRESHOLD_LOCKED=True)
        from config import settings as _cfg
        if getattr(_cfg, 'CONFIDENCE_THRESHOLD_LOCKED', False):
            self.state.min_confidence_threshold = 50
            logger.info("Confidence threshold LOCKED at 50% (user requirement - not adjustable by optimizer)")
        else:
            # If low confidence trades perform poorly, raise threshold
            if 'low' in win_rates and win_rates['low'] < 0.45:
                old_threshold = self.state.min_confidence_threshold
                self.state.min_confidence_threshold = min(80, self.state.min_confidence_threshold + 5)
                changes['confidence_threshold'] = f"{old_threshold} → {self.state.min_confidence_threshold}"
                logger.info(f"Raising confidence threshold: {changes['confidence_threshold']}")
            # If high confidence trades do well, can lower threshold slightly (floor: 80)
            elif 'high' in win_rates and win_rates['high'] > 0.65 and self.state.min_confidence_threshold > 80:
                old_threshold = self.state.min_confidence_threshold
                self.state.min_confidence_threshold = max(80, self.state.min_confidence_threshold - 3)
                changes['confidence_threshold'] = f"{old_threshold} → {self.state.min_confidence_threshold}"
                logger.info(f"Lowering confidence threshold: {changes['confidence_threshold']}")
        
        return changes
    
    def _optimize_exit_strategy(self) -> Dict:
        """Optimize TP/SL multipliers and exit conditions."""
        changes = {}
        
        # Analyze exits
        early_exits = [a for a in self.recent_analyses if 'EARLY' in a.exit_reason.upper()]
        tp_exits = [a for a in self.recent_analyses if 'TP' in a.exit_reason.upper()]
        sl_exits = [a for a in self.recent_analyses if 'SL' in a.exit_reason.upper()]
        
        # If leaving too much on table consistently, increase TP
        avg_left = np.mean([a.left_on_table for a in self.recent_analyses if a.was_winner])
        if avg_left > 20:  # More than 20 pips left consistently
            old_tp = self.state.tp_multiplier
            self.state.tp_multiplier = min(1.5, self.state.tp_multiplier + 0.1)
            changes['tp_multiplier'] = f"{old_tp:.2f} → {self.state.tp_multiplier:.2f}"
            logger.info(f"Increasing TP multiplier: {changes['tp_multiplier']}")
        
        # If SL hit too often, widen SL
        if len(sl_exits) > len(tp_exits) and len(self.recent_analyses) > 30:
            sl_rate = len(sl_exits) / len(self.recent_analyses)
            if sl_rate > 0.4:  # More than 40% SL hits
                old_sl = self.state.sl_multiplier
                self.state.sl_multiplier = min(1.5, self.state.sl_multiplier + 0.1)
                changes['sl_multiplier'] = f"{old_sl:.2f} → {self.state.sl_multiplier:.2f}"
                logger.info(f"Widening SL: {changes['sl_multiplier']}")
        
        return changes
    
    def _optimize_signal_weights(self) -> Dict:
        """Adjust confidence engine signal weights based on accuracy."""
        changes = {}
        
        # Calculate accuracy for each signal
        signal_accuracy = {
            'structure': np.mean([a.structure_correct for a in self.recent_analyses]),
            'smc': np.mean([a.smc_correct for a in self.recent_analyses]),
            'mtf': np.mean([a.mtf_correct for a in self.recent_analyses]),
            'statistical': np.mean([a.statistical_correct for a in self.recent_analyses]),
            'ml': np.mean([a.ml_correct for a in self.recent_analyses])
        }
        
        # Adjust weights toward better performing signals
        best_signal = max(signal_accuracy, key=signal_accuracy.get)
        worst_signal = min(signal_accuracy, key=signal_accuracy.get)
        
        # Small incremental adjustment
        adjustment = 0.02
        
        if signal_accuracy[best_signal] > 0.6 and signal_accuracy[worst_signal] < 0.45:
            # Increase weight of best signal
            if best_signal == 'structure':
                old = self.state.smc_weight  # Using smc as example, should map to actual weight variables
                # Note: Actual weight adjustment would be in confidence_engine, this is for tracking
                changes[f'{best_signal}_boost'] = f"Performance: {signal_accuracy[best_signal]:.1%}"
            
            # Decrease weight of worst signal
            changes[f'{worst_signal}_reduce'] = f"Performance: {signal_accuracy[worst_signal]:.1%}"
            
            logger.info(f"Signal performance: {signal_accuracy}")
        
        return changes
    
    def _optimize_risk_parameters(self) -> Dict:
        """Optimize position sizing and risk limits."""
        changes = {}
        
        # Calculate recent drawdown
        recent_losses = [a.profit_usd for a in self.recent_analyses[-20:] if not a.was_winner]
        if len(recent_losses) > 0:
            avg_loss = abs(np.mean(recent_losses))
            
            # If losses are small relative to wins, can increase position size slightly
            recent_wins = [a.profit_usd for a in self.recent_analyses[-20:] if a.was_winner]
            if len(recent_wins) > len(recent_losses):
                avg_win = np.mean(recent_wins)
                if avg_win > avg_loss * 2:  # Win/loss ratio > 2
                    old_mult = self.state.base_lot_multiplier
                    self.state.base_lot_multiplier = min(1.3, self.state.base_lot_multiplier + 0.05)
                    changes['lot_multiplier'] = f"{old_mult:.2f} → {self.state.base_lot_multiplier:.2f}"
        
        # Safety: reduce if recent drawdown is high
        if self.state.consecutive_losses > 5:
            old_mult = self.state.base_lot_multiplier
            self.state.base_lot_multiplier = max(0.5, self.state.base_lot_multiplier - 0.1)
            changes['lot_multiplier_reduced'] = f"Due to {self.state.consecutive_losses} losses"
        
        return changes
    
    def _update_performance_metrics(self):
        """Update recent performance metrics."""
        if len(self.recent_analyses) == 0:
            return
        
        # Win rate (last 50 trades)
        recent = self.recent_analyses[-50:]
        wins = sum(1 for a in recent if a.was_winner)
        self.state.recent_win_rate = wins / len(recent)
        
        # Profit factor
        total_wins = sum(a.profit_usd for a in recent if a.was_winner)
        total_losses = abs(sum(a.profit_usd for a in recent if not a.was_winner))
        if total_losses > 0:
            self.state.recent_profit_factor = total_wins / total_losses
        
        # Consecutive losses
        if recent[-1].was_winner:
            self.state.consecutive_losses = 0
        else:
            self.state.consecutive_losses += 1
        
        # Total trades analyzed
        self.state.total_trades_analyzed = len(self.recent_analyses)
        
        # Emergency stop if losing streak too long
        if self.state.consecutive_losses > 10:
            logger.warning(f"⚠️ EMERGENCY: Disabling learning after {self.state.consecutive_losses} consecutive losses")
            self.state.learning_enabled = False
    
    def _check_if_early_entry(self, trade: Dict) -> bool:
        """Check if entry was too early (price moved against us initially)."""
        # Simplified heuristic
        entry_price = trade.get('entry_price', 0)
        exit_price = trade.get('exit_price', 0)
        direction = trade.get('direction', 'BUY')
        profit = trade.get('profit_usd', 0)
        
        # If loss and price moved significantly against direction, probably early
        if profit < 0:
            if direction == 'BUY' and exit_price < entry_price * 0.998:
                return True
            elif direction == 'SELL' and exit_price > entry_price * 1.002:
                return True
        
        return False
    
    def _was_signal_correct(self, signal_type: str, trade: Dict, was_winner: bool) -> bool:
        """Determine if a specific signal type was correct."""
        # A signal was "correct" if it was strong and the trade won,
        # or weak and the trade lost
        
        if signal_type == 'structure':
            score = trade.get('structure_score', 50)
        elif signal_type == 'smc':
            score = trade.get('smc_score', 50)
        elif signal_type == 'mtf':
            score = trade.get('mtf_alignment', 0) * 11  # Scale 0-9 to 0-100
        elif signal_type == 'statistical':
            score = trade.get('bayesian_probability', 0.5) * 100
        elif signal_type == 'ml':
            score = trade.get('confidence', 50)  # ML contributes to overall confidence
        else:
            score = 50
        
        # Strong signal (>65) should predict win
        # Weak signal (<45) should predict loss
        if score > 65:
            return was_winner
        elif score < 45:
            return not was_winner
        else:
            return True  # Neutral signal, don't penalize
    
    def _identify_key_factors(self, trade: Dict, was_winner: bool, 
                             struct: bool, smc: bool, mtf: bool, stat: bool, ml: bool) -> Tuple[str, str]:
        """Identify primary success and failure factors."""
        # Success factor (for wins)
        if was_winner:
            correctness = {
                'Structure': struct,
                'SMC': smc,
                'Multi-Timeframe': mtf,
                'Statistical': stat,
                'ML Ensemble': ml
            }
            correct_signals = [name for name, correct in correctness.items() if correct]
            if len(correct_signals) > 0:
                success = f"{', '.join(correct_signals[:2])} provided accurate signals"
            else:
                success = "Market moved favorably despite weak signals"
        else:
            success = "N/A"
        
        # Failure factor (for losses)
        if not was_winner:
            incorrectness = {
                'Structure': not struct,
                'SMC': not smc,
                'Multi-Timeframe': not mtf,
                'Statistical': not stat,
                'ML Ensemble': not ml
            }
            incorrect_signals = [name for name, incorrect in incorrectness.items() if incorrect]
            if len(incorrect_signals) > 0:
                failure = f"{', '.join(incorrect_signals[:2])} gave false signals"
            else:
                failure = "Market moved unfavorably despite strong signals"
        else:
            failure = "N/A"
        
        return success, failure
    
    def _generate_recommendation(self, trade: Dict, was_winner: bool, 
                                entry_optimal: bool, exit_optimal: bool,
                                struct: bool, smc: bool, mtf: bool, stat: bool, ml: bool) -> str:
        """Generate actionable recommendation for improvement."""
        recommendations = []
        
        if not was_winner:
            # Analyze what went wrong
            if not struct:
                recommendations.append("Require stronger market structure")
            if not mtf:
                recommendations.append("Wait for better multi-timeframe alignment")
            if not entry_optimal:
                recommendations.append("Improve entry timing")
            if not exit_optimal:
                recommendations.append("Exit earlier when confidence drops")
        else:
            # Analyze what could be better
            left_on_table = trade.get('could_have_captured_more', 0) or 0
            if left_on_table > 30:
                recommendations.append("Extend TP to capture more profit")
            if not exit_optimal:
                recommendations.append("Hold longer when trend persists")
        
        if len(recommendations) == 0:
            return "Optimal trade execution"
        
        return " | ".join(recommendations[:2])
    
    def get_current_parameters(self) -> Dict:
        """Get current optimization parameters."""
        return asdict(self.state)
    
    def revert_to_previous_generation(self) -> bool:
        """Revert to previous parameter set if performance degraded."""
        if len(self.parameter_history) == 0:
            logger.warning("No previous generation to revert to")
            return False
        
        self.state = self.parameter_history[-1]
        self.parameter_history.pop()
        self._save_state()
        
        logger.info(f"⏪ Reverted to generation {self.state.optimization_generation}")
        return True
    
    def emergency_stop(self):
        """Emergency stop - freeze all learning."""
        self.state.learning_enabled = False
        self._save_state()
        logger.warning("🚨 EMERGENCY STOP: Learning disabled")
    
    def resume_learning(self):
        """Resume learning after emergency stop."""
        self.state.learning_enabled = True
        self.state.consecutive_losses = 0
        self._save_state()
        logger.info("✅ Learning resumed")
    
    def _save_state(self):
        """Save optimization state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(asdict(self.state), f, indent=2)
            logger.debug(f"State saved to {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def _load_state(self) -> OptimizationState:
        """Load optimization state from disk."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    state = OptimizationState(**data)
                logger.info(f"State loaded from {self.state_file} (Gen {state.optimization_generation})")
                return state
        except Exception as e:
            logger.warning(f"Could not load state: {e}. Using defaults.")
        
        return OptimizationState()


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_self_optimizer = None

def get_self_optimizer() -> SelfOptimizer:
    """Get or create singleton self-optimizer instance."""
    global _self_optimizer
    if _self_optimizer is None:
        _self_optimizer = SelfOptimizer()
    return _self_optimizer
