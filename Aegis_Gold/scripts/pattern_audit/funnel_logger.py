"""
Funnel Logger

Logs each pattern's journey through decision gates.
READ-ONLY - never modifies gate behavior.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any
import logging


logger = logging.getLogger("pattern_audit.funnel")


@dataclass
class GateDecision:
    """Single gate decision record."""
    gate_name: str
    passed: bool
    reason: str  # Rejection reason if not passed
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FunnelRecord:
    """Complete funnel journey for one pattern."""
    pattern_id: str
    timestamp: float
    symbol: str
    timeframe: str
    pattern_type: str
    pattern_name: str
    direction: str  # "BUY" or "SELL"
    session: str
    session_confirmed: bool  # False if no broker offset provided
    spread_source: str  # "ACTUAL_HISTORY" or "ESTIMATED"
    gates: List[GateDecision]
    final_outcome: str  # "TRADED" | "REJECTED"
    rejection_gate: str  # Gate name that rejected, or ""


class FunnelLogger:
    """
    Logs patterns through gate sequence without modifying behavior.
    
    Gates checked (in order):
    1. Pattern Detection (already done)
    2. Risk Evaluation (evaluate_risk)
    3. SIMULATED position limits (PositionSimulator.can_trade() with
       REAL config limits; gate labelled SIMULATED, NOT real can_trade)
    4. Spread Check
    5. Session Check
    6. Direction Integrity (verify_direction_integrity)
    
    NOTE: EQS/MDS and TradeAuthorization gates omitted for simplicity
    in initial audit. Can be added if needed.
    """
    
    def __init__(self):
        self.records: List[FunnelRecord] = []
    
    def log_pattern_through_gates(
        self,
        pattern,  # PatternDetectionResult
        simulated_state,  # SimulatedState
        symbol: str,
        point: float,
        risk_mgr,  # RiskManager instance
        simulated_clock  # SimulatedClock context manager
    ) -> FunnelRecord:
        """
        Run pattern through gate sequence with simulated clock active.
        
        Args:
            pattern: PatternDetectionResult from detection
            simulated_state: SimulatedState with spread, session, etc.
            symbol: Trading symbol
            point: Point size
            risk_mgr: RiskManager instance (with simulated state)
            simulated_clock: SimulatedClock for time-dependent gates
        
        Returns:
            FunnelRecord with pass/fail for each gate
        """
        gates = []
        pattern_id = f"{symbol}_{pattern.direction}_{pattern.timestamp}"
        
        # Activate simulated clock for time-dependent gates
        with simulated_clock:
            
            # Gate 1: Pattern Detection (already passed - pattern was detected)
            gates.append(GateDecision(
                gate_name="PATTERN_DETECTION",
                passed=True,
                reason="",
                metadata={"pattern": pattern.pattern_name, "confidence": pattern.confidence}
            ))
            
            # Gate 2: Risk Evaluation
            risk_gate = self._check_risk_evaluation(
                pattern, simulated_state, symbol, point
            )
            gates.append(risk_gate)
            if not risk_gate.passed:
                return self._create_record(
                    pattern_id, pattern, simulated_state, gates, "RISK_EVALUATION"
                )
            
            # Gate 3: SIMULATED position limits (NOT real can_trade; the
            # caller passes a PositionSimulator as risk_mgr; legacy mocks
            # still work via _check_can_trade_legacy duck-typing).
            checker = getattr(self, "_check_can_trade")
            try:
                import inspect as _insp
                _names = _insp.getfullargspec(checker).args
            except Exception:
                _names = []
            if "pos_sim" in _names or "current_time" in _names:
                can_trade_gate = checker(
                    risk_mgr, simulated_state, symbol, pattern.direction,
                    current_time=getattr(
                        simulated_state, "candle_time_utc",
                        getattr(pattern, "timestamp", 0.0)),
                )
            else:  # legacy 4-arg mock-based tests
                can_trade_gate = self._check_can_trade_legacy(
                    risk_mgr, simulated_state, symbol, pattern.direction
                )
            gates.append(can_trade_gate)
            if not can_trade_gate.passed:
                return self._create_record(
                    pattern_id, pattern, simulated_state, gates, "SIMULATED_POSITION_LIMITS"
                )
            
            # Gate 4: Spread Check
            spread_gate = self._check_spread(simulated_state, symbol)
            gates.append(spread_gate)
            if not spread_gate.passed:
                return self._create_record(
                    pattern_id, pattern, simulated_state, gates, "SPREAD_CHECK"
                )
            
            # Gate 5: Session Check
            session_gate = self._check_session(simulated_state)
            gates.append(session_gate)
            if not session_gate.passed:
                return self._create_record(
                    pattern_id, pattern, simulated_state, gates, "SESSION_CHECK"
                )
            
            # Gate 6: Direction Integrity
            direction_gate = self._check_direction_integrity(pattern)
            gates.append(direction_gate)
            if not direction_gate.passed:
                return self._create_record(
                    pattern_id, pattern, simulated_state, gates, "DIRECTION_INTEGRITY"
                )
        
        # All gates passed
        return self._create_record(
            pattern_id, pattern, simulated_state, gates, ""
        )
    
    def _check_risk_evaluation(
        self, pattern, simulated_state, symbol: str, point: float
    ) -> GateDecision:
        """Gate 2: Risk Evaluation (evaluate_risk)"""
        from brain.risk_eval import evaluate_risk
        
        try:
            # Create minimal structure object for evaluate_risk
            class MockStructure:
                def __init__(self, sl_dist):
                    self.sl_distance = sl_dist
            
            sl_distance = abs(pattern.entry_price - pattern.stop_loss) / point
            structure = MockStructure(sl_distance)
            
            # Create mock account
            account = {"balance": 10000.0, "equity": 10000.0}
            
            # Create mock candles (not used by evaluate_risk but required arg)
            candles = []
            
            # Create mock risk_mgr with consecutive_losses
            class MockRiskMgr:
                def __init__(self, consec_losses):
                    self.consecutive_losses = consec_losses
            
            mock_risk = MockRiskMgr(simulated_state.consecutive_losses)
            
            # Call evaluate_risk (pure calculation, no MT5 calls)
            risk_result = evaluate_risk(
                account=account,
                structure=structure,
                candles=candles,
                risk_mgr=mock_risk,
                session=simulated_state.session,
                spread=simulated_state.spread_points
            )
            
            return GateDecision(
                gate_name="RISK_EVALUATION",
                passed=risk_result.approved,
                reason=risk_result.rejection_reason,
                metadata={"quality_score": risk_result.quality_score}
            )
            
        except Exception as e:
            logger.warning(f"Risk evaluation error: {e}")
            return GateDecision(
                gate_name="RISK_EVALUATION",
                passed=False,
                reason=f"ERROR: {str(e)}",
                metadata={}
            )
    
    def _check_can_trade(
        self, pos_sim, simulated_state, symbol: str, direction: str,
        current_time: float = 0.0,
    ) -> GateDecision:
        """Gate 3: SIMULATED position limits (NOT real RiskManager.can_trade).

        Reads limits from REAL config via PositionSimulator.limits; returns
        the EXACT reject reason (DAILY_LIMIT / MAX_OPEN / LOSS_PAUSE /
        CONSECUTIVE_LOSSES / COOLDOWN) so the funnel table counts per reason.
        Real RiskManager.can_trade() conditions needing MT5/account state
        (drawdown, 45-min refresh, CVaR, global cooldown file, TPM, direction
        filter) are NOT evaluated here - listed as UNCONFIRMED in report.
        """
        try:
            ok, reason = pos_sim.can_trade(current_time)
            code = (reason.split()[0] if reason else "")
            return GateDecision(
                gate_name="SIMULATED_POSITION_LIMITS",
                passed=ok,
                reason="" if ok else reason,
                metadata={
                    "reason_code": code,
                    "daily_trades": simulated_state.daily_trades_count,
                    "consecutive_losses": simulated_state.consecutive_losses,
                    "open_positions": len(getattr(pos_sim, "open_positions", {})),
                    "limits": {k: v.value for k, v in pos_sim.limits.items()},
                    "limit_sources": pos_sim.limit_sources(),
                },
            )
        except Exception as e:
            logger.warning(f"simulated limit check error: {e}")
            return GateDecision(
                gate_name="SIMULATED_POSITION_LIMITS",
                passed=False,
                reason=f"ERROR: {str(e)}",
                metadata={},
            )

    def _check_can_trade_legacy(
        self, risk_mgr, simulated_state, symbol: str, direction: str
    ) -> GateDecision:
        """Legacy alias (kept for old tests): delegates to simulated gate."""
        return self._check_can_trade(
            risk_mgr, simulated_state, symbol, direction,
            current_time=getattr(simulated_state, "candle_time_utc", 0.0))
    
    def _check_spread(self, simulated_state, symbol: str) -> GateDecision:
        """Gate 4: Spread Check"""
        from config import settings as cfg
        
        max_spread = cfg.SPREAD_LIMITS.get(simulated_state.session, 40)
        if symbol == "XAUUSD":
            max_spread = 35  # XAUUSD typical limit
        
        passed = simulated_state.spread_points <= max_spread
        
        return GateDecision(
            gate_name="SPREAD_CHECK",
            passed=passed,
            reason="" if passed else f"Spread {simulated_state.spread_points:.0f}pts > {max_spread}pts",
            metadata={
                "spread": simulated_state.spread_points,
                "spread_source": simulated_state.spread_source,
                "max_allowed": max_spread
            }
        )
    
    def _check_session(self, simulated_state) -> GateDecision:
        """Gate 5: Session Check"""
        # Check if session allows trading (not CLOSED)
        passed = simulated_state.session != "CLOSED"
        
        return GateDecision(
            gate_name="SESSION_CHECK",
            passed=passed,
            reason="" if passed else f"Market closed (session={simulated_state.session})",
            metadata={
                "session": simulated_state.session,
                "confirmed": simulated_state.confirmed
            }
        )
    
    def _check_direction_integrity(self, pattern) -> GateDecision:
        """Gate 6: Direction Integrity (verify_direction_integrity)"""
        # In audit, pattern.direction is the authoritative direction
        # If it's BUY or SELL, integrity passes (no ML/RL override in audit)
        passed = pattern.direction in ("BUY", "SELL")
        
        return GateDecision(
            gate_name="DIRECTION_INTEGRITY",
            passed=passed,
            reason="" if passed else f"Invalid direction: {pattern.direction}",
            metadata={"direction": pattern.direction}
        )
    
    def _create_record(
        self,
        pattern_id: str,
        pattern,
        simulated_state,
        gates: List[GateDecision],
        rejection_gate: str
    ) -> FunnelRecord:
        """Create final funnel record."""
        record = FunnelRecord(
            pattern_id=pattern_id,
            timestamp=pattern.timestamp,
            symbol="XAUUSD",  # Hardcoded for now
            timeframe=pattern.timeframe,
            pattern_type=pattern.pattern_type,
            pattern_name=pattern.pattern_name,
            direction=pattern.direction,
            session=simulated_state.session,
            session_confirmed=simulated_state.confirmed,
            spread_source=simulated_state.spread_source,
            gates=gates,
            final_outcome="TRADED" if not rejection_gate else "REJECTED",
            rejection_gate=rejection_gate
        )
        
        self.records.append(record)
        return record
