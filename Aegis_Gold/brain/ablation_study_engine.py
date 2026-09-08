"""
===========================================================================
AEGIS GOLD — Engine Ablation Study Engine (Phase W)
===========================================================================

Systematically disable individual engines and components to measure
their contribution to overall system performance.

ABLATION STRATEGY:
------------------
1. Baseline: Run with all engines enabled
2. Disable each engine individually: Measure performance loss
3. Disable pairs: Detect interactions between engines
4. Disable systems progressively: Find minimum viable system

ENGINES ABLATED:
----------------
Phase K-L AI Consensus (7 engines):
  1. Transformer (pattern sequence analysis)
  2. LSTM (temporal dynamics)
  3. Ensemble (multi-model voting)
  4. Reinforcement (trade outcome learning)
  5. Clustering (market regime detection)
  6. Causal Graph (pattern causality)
  7. Opportunity (opportunity detection)

Plus Core Components:
  8. Risk Manager
  9. Entry Logic
  10. Quality Gates
  11. Causality Enforcer

METRICS:
--------
- Win rate change
- Sharpe ratio change
- Max drawdown change
- Precision/recall change
- Entry signal quality
- Overall system efficiency (importance score)

===========================================================================
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Tuple, Optional
import statistics
from enum import Enum


class AblationTarget(Enum):
    """Components that can be ablated."""
    TRANSFORMER = "transformer"
    LSTM = "lstm"
    ENSEMBLE = "ensemble"
    REINFORCEMENT = "reinforcement"
    CLUSTERING = "clustering"
    CAUSAL_GRAPH = "causal_graph"
    OPPORTUNITY = "opportunity"
    RISK_MANAGER = "risk_manager"
    ENTRY_LOGIC = "entry_logic"
    QUALITY_GATES = "quality_gates"
    CAUSALITY_ENFORCER = "causality_enforcer"


@dataclass
class AblationTestRun:
    """Single ablation test run."""
    
    run_id: int
    ablated_component: str
    ablated_pair: Optional[List[str]] = None  # For pair ablations
    
    # Baseline metrics (all enabled)
    baseline_win_rate: float = 0.0
    baseline_sharpe: float = 0.0
    baseline_avg_trade: float = 0.0
    baseline_max_dd: float = 0.0
    baseline_signal_quality: float = 0.0
    
    # With ablation metrics
    ablated_win_rate: float = 0.0
    ablated_sharpe: float = 0.0
    ablated_avg_trade: float = 0.0
    ablated_max_dd: float = 0.0
    ablated_signal_quality: float = 0.0
    
    # Performance deltas
    win_rate_change: float = 0.0  # % change
    sharpe_change: float = 0.0
    trade_quality_change: float = 0.0
    dd_change: float = 0.0
    signal_quality_change: float = 0.0
    
    # Importance metrics
    importance_score: float = 0.0  # Higher = more important
    can_be_disabled: bool = True  # Whether component is critical


@dataclass
class AblationSummary:
    """Aggregate ablation study results."""
    
    baseline_performance: Dict[str, float] = field(default_factory=dict)
    
    # Importance rankings
    component_importance: Dict[str, float] = field(default_factory=dict)  # sorted by score
    critical_components: List[str] = field(default_factory=list)         # non-disableable
    removable_components: List[str] = field(default_factory=list)       # can be disabled
    
    # Interaction effects
    pair_interactions: Dict[str, float] = field(default_factory=dict)  # interaction strength
    synergistic_pairs: List[Tuple[str, str]] = field(default_factory=list)
    redundant_pairs: List[Tuple[str, str]] = field(default_factory=list)
    
    # Minimum viable system
    minimum_viable_ensemble: List[str] = field(default_factory=list)
    min_viable_performance: float = 0.0


class AblationStudyEngine:
    """Engine ablation study system."""
    
    def __init__(self):
        """Initialize ablation engine."""
        self.test_runs: List[AblationTestRun] = []
        self.summary: Optional[AblationSummary] = None
        
        # Component registry
        self.components = [e.value for e in AblationTarget]
        self.critical_threshold = 0.10  # 10% drop = critical
    
    def record_baseline_run(self, metrics: Dict[str, float]) -> None:
        """Record baseline performance with all engines enabled."""
        # This is stored in the summary
        pass
    
    def record_ablation_run(self,
                           run_id: int,
                           ablated_component: str,
                           baseline_metrics: Dict[str, float],
                           ablated_metrics: Dict[str, float],
                           ablated_pair: Optional[List[str]] = None) -> AblationTestRun:
        """Record an ablation test run."""
        
        # Calculate deltas
        win_rate_delta = ((ablated_metrics.get('win_rate', 0) - baseline_metrics.get('win_rate', 0)) 
                         / baseline_metrics.get('win_rate', 1) * 100)
        sharpe_delta = ((ablated_metrics.get('sharpe', 0) - baseline_metrics.get('sharpe', 0)) 
                       / max(baseline_metrics.get('sharpe', 1), 0.01) * 100)
        trade_delta = ((ablated_metrics.get('avg_trade', 0) - baseline_metrics.get('avg_trade', 0)) 
                      / max(baseline_metrics.get('avg_trade', 0.01), 0.01) * 100)
        dd_delta = ((ablated_metrics.get('max_dd', 0) - baseline_metrics.get('max_dd', 0)) 
                   / max(baseline_metrics.get('max_dd', 0.01), 0.01) * 100)
        signal_delta = ((ablated_metrics.get('signal_quality', 0) - baseline_metrics.get('signal_quality', 0)) 
                       / max(baseline_metrics.get('signal_quality', 0.01), 0.01) * 100)
        
        # Calculate importance score (absolute % change)
        importance = (abs(win_rate_delta) + abs(sharpe_delta) + abs(trade_delta) + 
                     abs(signal_delta)) / 4.0
        
        # Determine if critical
        is_critical = abs(win_rate_delta) > 10.0 or abs(sharpe_delta) > 15.0
        
        run = AblationTestRun(
            run_id=run_id,
            ablated_component=ablated_component,
            ablated_pair=ablated_pair,
            baseline_win_rate=baseline_metrics.get('win_rate', 0),
            baseline_sharpe=baseline_metrics.get('sharpe', 0),
            baseline_avg_trade=baseline_metrics.get('avg_trade', 0),
            baseline_max_dd=baseline_metrics.get('max_dd', 0),
            baseline_signal_quality=baseline_metrics.get('signal_quality', 0),
            ablated_win_rate=ablated_metrics.get('win_rate', 0),
            ablated_sharpe=ablated_metrics.get('sharpe', 0),
            ablated_avg_trade=ablated_metrics.get('avg_trade', 0),
            ablated_max_dd=ablated_metrics.get('max_dd', 0),
            ablated_signal_quality=ablated_metrics.get('signal_quality', 0),
            win_rate_change=win_rate_delta,
            sharpe_change=sharpe_delta,
            trade_quality_change=trade_delta,
            dd_change=dd_delta,
            signal_quality_change=signal_delta,
            importance_score=importance,
            can_be_disabled=not is_critical
        )
        
        self.test_runs.append(run)
        return run
    
    def identify_critical_components(self) -> List[str]:
        """Identify components that cannot be safely disabled."""
        
        critical = []
        for run in self.test_runs:
            if not run.can_be_disabled and run.ablated_pair is None:
                critical.append(run.ablated_component)
        
        return list(set(critical))
    
    def identify_removable_components(self) -> List[str]:
        """Identify components that can be safely removed."""
        
        removable = []
        for run in self.test_runs:
            if run.can_be_disabled and run.ablated_pair is None:
                # Only truly removable if minimal impact
                if run.importance_score < 5.0:  # < 5% importance
                    removable.append(run.ablated_component)
        
        return list(set(removable))
    
    def measure_component_importance(self) -> Dict[str, float]:
        """Rank components by importance (higher = more important)."""
        
        importance_scores = {}
        
        for run in self.test_runs:
            if run.ablated_pair is None:  # Single component ablations only
                component = run.ablated_component
                if component not in importance_scores:
                    importance_scores[component] = []
                importance_scores[component].append(run.importance_score)
        
        # Average importance for each component
        avg_importance = {}
        for component, scores in importance_scores.items():
            avg_importance[component] = statistics.mean(scores) if scores else 0.0
        
        # Sort by importance (descending)
        return dict(sorted(avg_importance.items(), key=lambda x: x[1], reverse=True))
    
    def analyze_pair_interactions(self) -> Dict[str, float]:
        """Analyze interaction effects between component pairs."""
        
        interactions = {}
        
        for run in self.test_runs:
            if run.ablated_pair and len(run.ablated_pair) == 2:
                pair_key = f"{run.ablated_pair[0]}_x_{run.ablated_pair[1]}"
                
                # Interaction strength = combined ablation effect
                individual_effects = []
                for component in run.ablated_pair:
                    for other_run in self.test_runs:
                        if (other_run.ablated_component == component and 
                            other_run.ablated_pair is None):
                            individual_effects.append(other_run.importance_score)
                            break
                
                if individual_effects:
                    combined_effect = run.importance_score
                    sum_individual = sum(individual_effects)
                    interaction = combined_effect - sum_individual
                    interactions[pair_key] = interaction
        
        return interactions
    
    def find_minimum_viable_ensemble(self) -> Tuple[List[str], float]:
        """Find minimum set of components needed for acceptable performance."""
        
        # Start with all components
        candidates = set(self.components)
        
        # Remove removable components
        removable = self.identify_removable_components()
        candidates = candidates - set(removable)
        
        # Sort remaining by importance
        importance = self.measure_component_importance()
        sorted_candidates = [c for c in sorted(candidates, 
                                              key=lambda x: importance.get(x, 0), 
                                              reverse=True)]
        
        # Keep only critical components (those with >5% importance)
        min_viable = [c for c in sorted_candidates if importance.get(c, 0) >= 5.0]
        
        # Calculate min viable performance
        if self.test_runs:
            avg_importance = statistics.mean([r.importance_score for r in self.test_runs 
                                             if r.ablated_component in min_viable])
        else:
            avg_importance = 0.0
        
        return min_viable, avg_importance
    
    def generate_summary(self) -> AblationSummary:
        """Generate ablation study summary."""
        
        # Baseline performance
        baseline_metrics = {}
        if self.test_runs:
            baseline_metrics = {
                'win_rate': self.test_runs[0].baseline_win_rate,
                'sharpe': self.test_runs[0].baseline_sharpe,
                'avg_trade': self.test_runs[0].baseline_avg_trade,
                'max_dd': self.test_runs[0].baseline_max_dd,
                'signal_quality': self.test_runs[0].baseline_signal_quality
            }
        
        # Component importance
        importance = self.measure_component_importance()
        
        # Critical and removable
        critical = self.identify_critical_components()
        removable = self.identify_removable_components()
        
        # Pair interactions
        interactions = self.analyze_pair_interactions()
        synergistic = {k: v for k, v in interactions.items() if v > 5.0}
        redundant = {k: v for k, v in interactions.items() if -5.0 < v < 0}
        
        # Minimum viable
        min_viable, min_perf = self.find_minimum_viable_ensemble()
        
        summary = AblationSummary(
            baseline_performance=baseline_metrics,
            component_importance=importance,
            critical_components=critical,
            removable_components=removable,
            pair_interactions=interactions,
            synergistic_pairs=list(synergistic.keys()),
            redundant_pairs=list(redundant.keys()),
            minimum_viable_ensemble=min_viable,
            min_viable_performance=min_perf
        )
        
        self.summary = summary
        return summary
    
    def generate_ablation_report(self) -> str:
        """Generate comprehensive ablation study report."""
        
        if not self.summary:
            self.generate_summary()
        
        report = []
        report.append("=" * 70)
        report.append("ABLATION STUDY REPORT (Phase W)")
        report.append("=" * 70)
        report.append("")
        
        # Baseline performance
        report.append("BASELINE PERFORMANCE (All Engines Enabled)")
        report.append("-" * 70)
        for metric, value in self.summary.baseline_performance.items():
            report.append(f"  {metric:20s}: {value:8.4f}")
        report.append("")
        
        # Component importance
        report.append("COMPONENT IMPORTANCE RANKING")
        report.append("-" * 70)
        for component, importance in self.summary.component_importance.items():
            status = "✓ CRITICAL" if component in self.summary.critical_components else \
                    ("✗ REMOVABLE" if component in self.summary.removable_components else "")
            report.append(f"  {component:25s}: {importance:7.2f}%  {status}")
        report.append("")
        
        # Critical components
        if self.summary.critical_components:
            report.append("CRITICAL COMPONENTS (Cannot Disable)")
            report.append("-" * 70)
            for component in self.summary.critical_components:
                report.append(f"  - {component}")
            report.append("")
        
        # Removable components
        if self.summary.removable_components:
            report.append("REMOVABLE COMPONENTS (Safe to Disable)")
            report.append("-" * 70)
            for component in self.summary.removable_components:
                report.append(f"  - {component}")
            report.append("")
        
        # Synergistic pairs
        if self.summary.synergistic_pairs:
            report.append("SYNERGISTIC COMPONENT PAIRS (Work Better Together)")
            report.append("-" * 70)
            for pair in self.summary.synergistic_pairs[:5]:
                report.append(f"  - {pair}")
            report.append("")
        
        # Minimum viable ensemble
        report.append("MINIMUM VIABLE ENSEMBLE")
        report.append("-" * 70)
        report.append(f"Required Components: {len(self.summary.minimum_viable_ensemble)}")
        for component in self.summary.minimum_viable_ensemble:
            report.append(f"  - {component}")
        report.append(f"Expected Performance: {self.summary.min_viable_performance:.2f}%")
        report.append("")
        
        return "\n".join(report)
