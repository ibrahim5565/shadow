"""
===========================================================================
AEGIS GOLD — 7 AI Engines Unified Integration Framework (Phase K)
===========================================================================

PURPOSE:
--------
Unified integration framework for all 7 local AI engines with consensus
mechanisms, dynamic weighting, and comprehensive vote fusion.

7 ENGINES:
----------
1. SMC Engine          — Smart Money Concepts (order blocks, BOS/CHoCH, liquidity)
2. Kronos Forecaster   — Time series forecasting with foundation models
3. Quant Feature Engine — Signal processing, complexity analysis, regime detection  
4. ML Ensemble         — Multi-model ML (XGBoost, RF, NN, LogReg)
5. OMEGA Engine        — Composite AI supervisor (candle, trend, momentum)
6. Unified Brain       — Neural architecture with DQN/Actor-Critic
7. RL Agent           — Reinforcement learning meta-weighter

CONSENSUS ARCHITECTURE:
-----------------------
- Directional Voting: 6 engines (SMC, Kronos, Quant, ML, OMEGA, Unified)  
- Meta-Weighting: RL Agent adjusts conviction weights per regime
- Minimum Agreement: 5/6 engines must agree for TRADE signal
- Causality Enforcement: All engines use FrozenDecisionSnapshot
- Pattern Memory: Historical similarity influences confidence
- Quality Gates: 10-gate system validates all signals

===========================================================================
"""

import logging
import numpy as np
import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

logger = logging.getLogger("aegis.seven_engines")
@dataclass
class EngineStatus:
    """Status and health of an individual AI engine."""
    name: str
    active: bool
    last_vote_time: Optional[str] = None
    response_time_ms: float = 0.0
    success_rate: float = 1.0
    error_count: int = 0
    last_error: str = ""
    
@dataclass  
class ConsensusResult:
    """Result of 7-engine consensus process."""
    # Decision
    action: str                        # "TRADE" or "WAIT"  
    direction: str                     # "BUY", "SELL", or "WAIT"
    final_confidence: float            # 0.0-1.0 final confidence
    
    # Vote Analysis
    total_votes: int                   # Number of engines that voted
    directional_votes: int             # Engines with BUY/SELL (not WAIT)
    agreement_count: int               # Engines agreeing on final direction
    agreement_ratio: float             # Agreement / Total votes
    
    # Engine Breakdown
    engine_votes: Dict[str, Any]       # Individual engine votes
    voting_engines: List[str]          # Engines that cast directional votes
    waiting_engines: List[str]         # Engines that voted WAIT
    failed_engines: List[str]          # Engines that failed/errored
    
    # Weighting & Quality
    rl_weights: Dict[str, float]       # RL agent conviction multipliers
    pattern_memory_boost: float       # Memory system confidence boost
    quality_gates_passed: int         # Number of quality gates passed (0-10)
    
    # Risk Assessment
    expected_r: float                  # Expected R from pattern memory
    win_probability: float             # Historical win probability
    max_drawdown_risk: float          # Expected maximum adverse excursion
    
    # Execution Details
    proposed_sl: float                 # Consensus stop loss
    proposed_tp: float                 # Consensus take profit
    entry_urgency: str                 # "IMMEDIATE", "PATIENT", "CHASE_ALLOWED"
    
    # Metadata
    timestamp: str                     # When consensus was calculated
    processing_time_ms: float          # Total time to reach consensus
    reasoning: List[str]               # Step-by-step decision reasoning
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return asdict(self)
class SevenEngineConsensus:
    """
    Unified integration framework for 7 AI engines with consensus mechanisms.
    """
    
    def __init__(self):
        # Engine configuration
        self.engines = {}
        self.engine_status = {}
        
        # Consensus parameters
        self.min_directional_agreement = 5  # Need 5/6 engines to agree
        self.directional_engines = [
            "smc", "kronos", "quant_feature_engine", 
            "ml_ensemble", "omega", "unified_brain"
        ]
        self.meta_weighting_engine = "rl_agent"
        
        # Performance tracking
        self.vote_history = []
        self.consensus_statistics = {
            "total_consensus_calls": 0,
            "trade_decisions": 0,
            "wait_decisions": 0,
            "engine_failures": defaultdict(int),
            "avg_processing_time_ms": 0.0
        }
        
        # Initialize engines
        self._initialize_engines()
        
        logger.info("[7-ENGINES] Consensus framework initialized with 7 AI engines")
    
    def _initialize_engines(self):
        """Initialize all 7 AI engines with error handling."""
        engine_configs = [
            ("smc", self._init_smc_engine),
            ("kronos", self._init_kronos_engine), 
            ("quant_feature_engine", self._init_quant_engine),
            ("ml_ensemble", self._init_ml_ensemble),
            ("omega", self._init_omega_engine),
            ("unified_brain", self._init_unified_brain),
            ("rl_agent", self._init_rl_agent)
        ]
        
        for engine_name, init_func in engine_configs:
            try:
                engine_instance = init_func()
                self.engines[engine_name] = engine_instance
                self.engine_status[engine_name] = EngineStatus(
                    name=engine_name, 
                    active=True,
                    success_rate=1.0
                )
                logger.info(f"[7-ENGINES] ✓ {engine_name} initialized")
            except Exception as e:
                logger.error(f"[7-ENGINES] ✗ {engine_name} failed to initialize: {e}")
                self.engine_status[engine_name] = EngineStatus(
                    name=engine_name,
                    active=False,
                    last_error=str(e)
                )
    
    def _init_smc_engine(self):
        """Initialize Smart Money Concepts engine."""
        from brain.smc_engine import SMCEngine
        return SMCEngine()
    
    def _init_kronos_engine(self):
        """Initialize Kronos forecasting engine."""
        from brain.kronos_forecaster import KronosForecaster
        return KronosForecaster()
    
    def _init_quant_engine(self):
        """Initialize Quantitative Feature engine."""
        from brain.quant_feature_engine import QuantFeatureEngine
        return QuantFeatureEngine()
    
    def _init_ml_ensemble(self):
        """Initialize ML Ensemble engine."""
        from brain.ml_ensemble import get_ml_ensemble
        return get_ml_ensemble()
    
    def _init_omega_engine(self):
        """Initialize OMEGA supervisor engine."""
        from brain.ai_supervisor import AISupervisor
        return AISupervisor()
    
    def _init_unified_brain(self):
        """Initialize Unified Brain engine."""
        from brain.unified_brain import UnifiedQuantAIBrain
        return UnifiedQuantAIBrain()
    
    def _init_rl_agent(self):
        """Initialize Reinforcement Learning agent."""
        from brain.reinforcement_agent import AegisRLAgent
        return AegisRLAgent()
    def run_consensus(
        self,
        snapshot,
        min_agreement: int = None,
        regime: str = "UNKNOWN",
        pattern_context: Optional[Dict[str, Any]] = None
    ) -> ConsensusResult:
        """
        Execute 7-engine consensus process with unified voting.
        
        Args:
            snapshot: FrozenDecisionSnapshot with market data
            min_agreement: Minimum engines needed for consensus (default: 5)
            regime: Current market regime for RL weighting
            pattern_context: Additional context for pattern memory
            
        Returns:
            ConsensusResult with comprehensive decision analysis
        """
        start_time = time.time()
        min_agreement = min_agreement or self.min_directional_agreement
        
        reasoning = []
        reasoning.append(f"Starting 7-engine consensus at {snapshot.timestamp}")
        
        # Step 1: Collect votes from all engines
        engine_votes = self._collect_engine_votes(snapshot, reasoning)
        
        # Step 2: Get RL meta-weights for current regime  
        rl_weights = self._get_rl_weights(regime, reasoning)
        
        # Step 3: Apply pattern memory intelligence
        memory_boost, expected_outcomes = self._apply_pattern_memory(
            pattern_context, engine_votes, reasoning
        )
        
        # Step 4: Analyze directional consensus
        consensus_analysis = self._analyze_consensus(
            engine_votes, rl_weights, min_agreement, reasoning
        )
        
        # Step 5: Validate with quality gates
        quality_result = self._validate_quality_gates(
            consensus_analysis, snapshot, reasoning
        )
        
        # Step 6: Determine final decision
        final_decision = self._make_final_decision(
            consensus_analysis, quality_result, reasoning
        )
        
        # Step 7: Calculate risk parameters
        risk_params = self._calculate_risk_parameters(
            final_decision, engine_votes, expected_outcomes, reasoning
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        # Build final consensus result
        result = ConsensusResult(
            action=final_decision["action"],
            direction=final_decision["direction"], 
            final_confidence=final_decision["confidence"],
            total_votes=len(engine_votes),
            directional_votes=len([v for v in engine_votes.values() 
                                  if v.get("direction") in ("BUY", "SELL")]),
            agreement_count=consensus_analysis["agreement_count"],
            agreement_ratio=consensus_analysis["agreement_ratio"],
            engine_votes=engine_votes,
            voting_engines=consensus_analysis["voting_engines"],
            waiting_engines=consensus_analysis["waiting_engines"], 
            failed_engines=consensus_analysis["failed_engines"],
            rl_weights=rl_weights,
            pattern_memory_boost=memory_boost,
            quality_gates_passed=quality_result["gates_passed"],
            expected_r=expected_outcomes.get("expected_r", 0.0),
            win_probability=expected_outcomes.get("win_probability", 0.5),
            max_drawdown_risk=expected_outcomes.get("max_drawdown", 0.0),
            proposed_sl=risk_params["stop_loss"],
            proposed_tp=risk_params["take_profit"],
            entry_urgency=risk_params["urgency"],
            timestamp=snapshot.timestamp.isoformat(),
            processing_time_ms=processing_time,
            reasoning=reasoning
        )
        
        # Update statistics
        self._update_statistics(result)
        
        logger.info(
            f"[7-ENGINES] Consensus: {result.action} {result.direction} "
            f"({result.agreement_count}/{result.total_votes} agree, "
            f"conf={result.final_confidence:.2f}, {processing_time:.1f}ms)"
        )
        
        return result
    def _collect_engine_votes(self, snapshot, reasoning: List[str]) -> Dict[str, Any]:
        """Collect votes from all active engines with parallel execution."""
        reasoning.append("Collecting votes from 7 engines...")
        
        engine_votes = {}
        vote_futures = {}
        
        # Use ThreadPoolExecutor for parallel engine execution
        with ThreadPoolExecutor(max_workers=7, thread_name_prefix="engine") as executor:
            # Submit all engine vote requests
            for engine_name, engine_instance in self.engines.items():
                if not self.engine_status[engine_name].active:
                    continue
                    
                future = executor.submit(self._get_single_engine_vote, 
                                       engine_name, engine_instance, snapshot)
                vote_futures[engine_name] = future
            
            # Collect results with timeout
            for engine_name, future in vote_futures.items():
                try:
                    vote_result = future.result(timeout=5.0)  # 5 second timeout per engine
                    engine_votes[engine_name] = vote_result
                    
                    # Update engine status
                    self.engine_status[engine_name].last_vote_time = datetime.now(timezone.utc).isoformat()
                    self.engine_status[engine_name].response_time_ms = vote_result.get("response_time_ms", 0)
                    
                except Exception as e:
                    logger.warning(f"[7-ENGINES] {engine_name} vote failed: {e}")
                    engine_votes[engine_name] = {
                        "engine": engine_name,
                        "direction": "WAIT",
                        "confidence": 0.0,
                        "error": str(e)
                    }
                    
                    # Update error tracking
                    self.engine_status[engine_name].error_count += 1
                    self.engine_status[engine_name].last_error = str(e)
        
        reasoning.append(f"Collected {len(engine_votes)} votes: {list(engine_votes.keys())}")
        return engine_votes
    
    def _get_single_engine_vote(self, engine_name: str, engine_instance, snapshot) -> Dict[str, Any]:
        """Get vote from single engine with timing and error handling."""
        start_time = time.time()
        
        try:
            # Check if engine has predict_vote method (new pattern consensus interface)
            if hasattr(engine_instance, 'predict_vote'):
                vote = engine_instance.predict_vote(snapshot)
                
                # Convert EngineVote to dict format
                if hasattr(vote, 'to_dict'):
                    result = vote.to_dict()
                else:
                    result = {
                        "engine": vote.engine_name,
                        "direction": vote.direction,
                        "confidence": vote.conviction,  # Map conviction to confidence
                        "proposed_sl": vote.proposed_sl,
                        "proposed_tp": vote.proposed_tp,
                        "reasoning": f"Pattern evidence: {len(vote.pattern_evidence)} patterns"
                    }
            
            # Fallback to legacy get_engine_vote method
            elif hasattr(engine_instance, 'get_engine_vote'):
                candles = list(snapshot.candles_m5)
                result = engine_instance.get_engine_vote(candles, snapshot.symbol)
            
            # Special handling for specific engines
            elif engine_name == "unified_brain":
                # Extract features and get prediction
                candles_m5 = list(snapshot.candles_m5)
                candles_m1 = list(snapshot.candles_m1) if snapshot.candles_m1 else None
                
                decision = engine_instance.predict_unified(
                    candles_m5=candles_m5,
                    candles_m1=candles_m1,
                    symbol=snapshot.symbol,
                    session=snapshot.session,
                    spread=snapshot.spread,
                    point=snapshot.point
                )
                
                result = {
                    "engine": "unified_brain",
                    "direction": decision.direction if decision.action == "TRADE" else "WAIT",
                    "confidence": decision.confidence / 100.0,
                    "reasoning": decision.reasoning,
                    "institutional_score": decision.institutional_score,
                    "model_consensus": decision.model_consensus
                }
            
            else:
                raise NotImplementedError(f"Engine {engine_name} has no supported vote method")
            
            # Add timing information
            result["response_time_ms"] = (time.time() - start_time) * 1000
            result["engine"] = engine_name  # Ensure engine name is set
            
            return result
            
        except Exception as e:
            logger.error(f"[7-ENGINES] {engine_name} vote error: {e}")
            return {
                "engine": engine_name,
                "direction": "WAIT", 
                "confidence": 0.0,
                "error": str(e),
                "response_time_ms": (time.time() - start_time) * 1000
            }
    def _get_rl_weights(self, regime: str, reasoning: List[str]) -> Dict[str, float]:
        """Get RL agent meta-weights for current regime."""
        try:
            if "rl_agent" in self.engines:
                rl_weights = self.engines["rl_agent"].get_engine_weights(regime)
                reasoning.append(f"RL weights for {regime}: {rl_weights}")
                return rl_weights
            else:
                default_weights = {engine: 1.0 for engine in self.directional_engines}
                reasoning.append("RL agent unavailable, using equal weights")
                return default_weights
        except Exception as e:
            logger.warning(f"[7-ENGINES] RL weighting failed: {e}")
            reasoning.append(f"RL weighting error: {e}, using equal weights")
            return {engine: 1.0 for engine in self.directional_engines}
    
    def _apply_pattern_memory(
        self, 
        pattern_context: Optional[Dict[str, Any]], 
        engine_votes: Dict[str, Any],
        reasoning: List[str]
    ) -> Tuple[float, Dict[str, Any]]:
        """Apply pattern memory intelligence to boost confidence."""
        memory_boost = 0.0
        expected_outcomes = {"expected_r": 0.0, "win_probability": 0.5, "max_drawdown": 0.0}
        
        if not pattern_context:
            reasoning.append("No pattern context for memory lookup")
            return memory_boost, expected_outcomes
        
        try:
            from brain.pattern_memory_system import get_pattern_memory_system
            
            memory_system = get_pattern_memory_system()
            
            # Create fingerprint from context
            fingerprint = memory_system.create_pattern_fingerprint(
                pattern_type=pattern_context.get('pattern_type', 'CONSENSUS'),
                scale=pattern_context.get('scale', 'MEDIUM'),
                direction=self._get_consensus_direction(engine_votes),
                price_levels=pattern_context.get('price_levels', []),
                candle_data=pattern_context.get('candle_data', []),
                regime=pattern_context.get('regime', 'UNKNOWN'),
                mtf_alignment=pattern_context.get('mtf_alignment', 0.5),
                volatility=pattern_context.get('volatility', 0.5),
                formation_speed=pattern_context.get('formation_speed', 0.5),
                timeframe=pattern_context.get('timeframe', 'M15'),
                rr_ratio=pattern_context.get('rr_ratio', 2.0),
                structure_strength=pattern_context.get('structure_strength', 0.5)
            )
            
            # Get prediction from similar patterns
            prediction = memory_system.predict_pattern_outcome(fingerprint)
            
            if prediction.sample_size >= 3 and prediction.confidence > 0.60:
                memory_boost = min(0.25, prediction.confidence * 0.3)  # Max 25% boost
                expected_outcomes = {
                    "expected_r": prediction.expected_r,
                    "win_probability": prediction.win_probability,
                    "max_drawdown": prediction.max_expected_drawdown
                }
                reasoning.append(
                    f"Pattern memory: {prediction.sample_size} similar patterns, "
                    f"P(win)={prediction.win_probability:.2f}, E(R)={prediction.expected_r:.2f}, "
                    f"boost=+{memory_boost:.2f}"
                )
            else:
                reasoning.append(
                    f"Pattern memory: insufficient data ({prediction.sample_size} patterns, "
                    f"conf={prediction.confidence:.2f})"
                )
        
        except ImportError:
            reasoning.append("Pattern memory system not available")
        except Exception as e:
            reasoning.append(f"Pattern memory error: {e}")
            
        return memory_boost, expected_outcomes
    
    def _get_consensus_direction(self, engine_votes: Dict[str, Any]) -> str:
        """Get preliminary consensus direction from engine votes."""
        directions = []
        for engine_name in self.directional_engines:
            if engine_name in engine_votes:
                direction = engine_votes[engine_name].get("direction", "WAIT")
                if direction in ("BUY", "SELL"):
                    directions.append(direction)
        
        if not directions:
            return "WAIT"
        
        # Return most common direction
        direction_counts = Counter(directions)
        return direction_counts.most_common(1)[0][0]