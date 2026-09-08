"""
===========================================================================
AEGIS GOLD — Missed Opportunities Analyzer Test Suite (Phase P)
===========================================================================

Tests for missed opportunities detection and analysis system.

CRITICAL TEST COVERAGE:
-----------------------
1. Missed signal recording and tracking
2. Outcome simulation based on price history
3. Opportunity cost calculation
4. Recommendation generation
5. Comparative analysis with actual trades
6. Statistical reporting

===========================================================================
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.missed_opportunities_analyzer import (
    MissedOpportunitiesAnalyzer,
    MissedSignal,
    SimulatedExecution,
    MissReason,
    SimulatedOutcome,
    get_missed_opportunities_analyzer
)


class TestMissedSignalRecording:
    """Test suite for missed signal recording."""
    
    def setup_method(self):
        """Setup for missed signal tests."""
        self.analyzer = MissedOpportunitiesAnalyzer()
        
        # Mock entry signal
        self.mock_signal = Mock()
        self.mock_signal.setup_completion_time = datetime.now(timezone.utc).isoformat()
        self.mock_signal.setup_quality_score = 75.0
        self.mock_signal.position_size_fraction = 0.02
        
        self.mock_trigger = Mock()
        self.mock_trigger.confidence = 0.8
        self.mock_signal.entry_trigger = self.mock_trigger
        
        # Mock entry zone
        self.mock_zone = Mock()
        self.mock_zone.optimal_price = 2010.0
        self.mock_zone.zone_width = 15.0
        self.mock_zone.direction = "BUY"
        self.mock_signal.entry_zone = self.mock_zone
        
        # Mock market snapshot
        self.mock_snapshot = Mock()
        self.mock_snapshot.current_price = 2010.0
        self.mock_snapshot.volatility_level = "NORMAL"
        self.mock_snapshot.volume = 1000
        self.mock_snapshot.momentum_score = 0.7
    
    def test_record_missed_signal_confidence_gate(self):
        """Test recording missed signal due to confidence gate."""
        missed = self.analyzer.record_missed_signal(
            pattern_id="pattern_001",
            symbol="XAUUSD",
            entry_signal=self.mock_signal,
            miss_reason=MissReason.CONFIDENCE_GATE,
            reason_details="Signal confidence 0.6 below threshold 0.75",
            market_snapshot=self.mock_snapshot,
            system_state={'positions': 1, 'max_positions': 3}
        )
        
        assert isinstance(missed, MissedSignal)
        assert missed.miss_id is not None
        assert missed.pattern_id == "pattern_001"
        assert missed.symbol == "XAUUSD"
        assert missed.miss_reason == MissReason.CONFIDENCE_GATE
        assert missed.miss_severity >= 0.0 and missed.miss_severity <= 1.0
        assert missed.signal_price == 2010.0
        
        # Should be stored
        assert missed.miss_id in self.analyzer.missed_signals
        
        # Statistics updated
        assert self.analyzer.miss_statistics['total_missed'] > 0
        
        print("✓ Missed signal recording (confidence gate) works")
    
    def test_record_missed_signal_quality_gate(self):
        """Test recording missed signal due to quality gate."""
        missed = self.analyzer.record_missed_signal(
            pattern_id="pattern_002",
            symbol="XAUUSD",
            entry_signal=self.mock_signal,
            miss_reason=MissReason.QUALITY_GATE,
            reason_details="Pattern quality 52.0 below minimum 55.0",
            market_snapshot=self.mock_snapshot,
            system_state={}
        )
        
        assert missed.miss_reason == MissReason.QUALITY_GATE
        assert missed.miss_id in self.analyzer.missed_signals
        
        print("✓ Missed signal recording (quality gate) works")
    
    def test_miss_severity_calculation(self):
        """Test severity calculation for different miss reasons."""
        # High quality signal missed due to risk gate
        severity = self.analyzer._calculate_miss_severity(
            signal_quality=85.0,
            signal_confidence=0.8,
            miss_reason=MissReason.RISK_GATE
        )
        
        assert 0 <= severity <= 1.0  # Valid range
        
        # Low quality signal missed
        severity_low = self.analyzer._calculate_miss_severity(
            signal_quality=40.0,
            signal_confidence=0.5,
            miss_reason=MissReason.QUALITY_GATE
        )
        
        assert 0 <= severity_low <= 1.0  # Valid range
        assert severity_low < severity  # Lower quality = lower severity
        
        print("✓ Miss severity calculation works")


class TestSimulatedExecution:
    """Test suite for execution simulation."""
    
    def setup_method(self):
        """Setup for simulation tests."""
        self.analyzer = MissedOpportunitiesAnalyzer()
        
        # Create missed signal
        self.missed_signal = MissedSignal(
            miss_id="miss_001",
            pattern_id="pattern_001",
            symbol="XAUUSD",
            signal_time=datetime.now(timezone.utc).isoformat(),
            signal_price=2010.0,
            entry_target=2010.0,
            signal_quality_score=75.0,
            signal_confidence=0.8,
            planned_stop_loss=2000.0,
            planned_take_profit=2030.0,
            planned_position_size=0.02,
            miss_reason=MissReason.CONFIDENCE_GATE,
            miss_reason_details="Test miss",
            miss_severity=0.5,
            market_conditions={},
            system_state={},
            detection_time=datetime.now(timezone.utc).isoformat(),
            miss_detection_time=datetime.now(timezone.utc).isoformat(),
            signal_age_minutes=5.0
        )
    
    def test_simulate_execution_win(self):
        """Test simulation of profitable execution."""
        # Price history shows TP hit
        price_history = [
            (datetime.now(timezone.utc) + timedelta(minutes=i), 2010.0 + i*2)
            for i in range(1, 11)
        ]
        
        simulation = self.analyzer.simulate_execution(
            self.missed_signal,
            price_history
        )
        
        assert isinstance(simulation, SimulatedExecution)
        assert simulation.simulated_entry_price == 2010.0
        assert simulation.simulated_exit_price is not None
        assert simulation.simulated_pnl > 0  # Should be profitable (TP hit)
        assert simulation.simulated_outcome == SimulatedOutcome.WIN_AT_TARGET
        
        print("✓ Simulated execution (profitable) works")
    
    def test_simulate_execution_loss(self):
        """Test simulation of losing execution."""
        # Price history shows SL hit
        price_history = [
            (datetime.now(timezone.utc) + timedelta(minutes=i), 2010.0 - i*1.5)
            for i in range(1, 11)
        ]
        
        simulation = self.analyzer.simulate_execution(
            self.missed_signal,
            price_history
        )
        
        assert simulation.simulated_exit_price is not None
        assert simulation.simulated_exit_reason == "STOP_LOSS"
        assert simulation.simulated_outcome == SimulatedOutcome.STOPPED_OUT
        assert simulation.simulated_pnl < 0  # Should be loss
        
        print("✓ Simulated execution (loss) works")
    
    def test_simulate_execution_no_history(self):
        """Test simulation with no price history."""
        simulation = self.analyzer.simulate_execution(
            self.missed_signal,
            []
        )
        
        assert simulation.simulated_outcome == SimulatedOutcome.UNKNOWN
        
        print("✓ Simulated execution (no history) works")


class TestOpportunityCostAnalysis:
    """Test suite for opportunity cost analysis."""
    
    def setup_method(self):
        """Setup for opportunity cost tests."""
        self.analyzer = MissedOpportunitiesAnalyzer()
        
        # Create test missed signal
        self.missed_signal = MissedSignal(
            miss_id="miss_002",
            pattern_id="pattern_002",
            symbol="XAUUSD",
            signal_time=datetime.now(timezone.utc).isoformat(),
            signal_price=2010.0,
            entry_target=2010.0,
            signal_quality_score=80.0,
            signal_confidence=0.85,
            planned_stop_loss=2000.0,
            planned_take_profit=2035.0,
            planned_position_size=0.02,
            miss_reason=MissReason.RISK_GATE,
            miss_reason_details="Risk/reward below 1.5",
            miss_severity=0.6,
            market_conditions={},
            system_state={},
            detection_time=datetime.now(timezone.utc).isoformat(),
            miss_detection_time=datetime.now(timezone.utc).isoformat(),
            signal_age_minutes=3.0
        )
        
        # Create simulated execution
        self.simulation = SimulatedExecution(
            sim_id="sim_002",
            missed_signal_id="miss_002",
            simulated_entry_price=2010.0,
            simulated_entry_time=datetime.now(timezone.utc).isoformat(),
            simulated_exit_price=2035.0,
            simulated_exit_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            simulated_exit_reason="TARGET_HIT",
            simulated_outcome=SimulatedOutcome.WIN_AT_TARGET,
            simulated_pnl=0.5,
            simulated_pnl_pct=0.00025,
            simulated_rr_ratio=1.67,
            comparison_score=0.75,
            confidence_level=0.8
        )
    
    def test_create_miss_summary(self):
        """Test creation of miss opportunity summary."""
        summary = self.analyzer.create_miss_summary(
            self.missed_signal,
            self.simulation,
            similar_actual_trades=[
                {'final_pnl': 0.4, 'entry_quality': 0.8},
                {'final_pnl': 0.6, 'entry_quality': 0.82},
                {'final_pnl': -0.2, 'entry_quality': 0.79}
            ]
        )
        
        assert summary is not None
        assert summary.miss_id == "miss_002"
        assert summary.signal_quality == 80.0
        assert summary.simulated_outcome == SimulatedOutcome.WIN_AT_TARGET
        assert summary.opportunity_cost > 0  # Profitable miss
        assert summary.similar_trades_count == 3
        assert summary.similar_win_rate > 0.5  # 2 wins out of 3
        
        print("✓ Miss opportunity summary creation works")


class TestMissAnalytics:
    """Test suite for miss analytics and reporting."""
    
    def setup_method(self):
        """Setup for analytics tests."""
        self.analyzer = MissedOpportunitiesAnalyzer()
        
        # Create multiple missed signals with simulations
        for i in range(5):
            missed = MissedSignal(
                miss_id=f"miss_{i:03d}",
                pattern_id=f"pattern_{i}",
                symbol="XAUUSD",
                signal_time=(datetime.now(timezone.utc) - timedelta(hours=i)).isoformat(),
                signal_price=2010.0 + i,
                entry_target=2010.0 + i,
                signal_quality_score=70.0 + i*3,
                signal_confidence=0.7 + i*0.05,
                planned_stop_loss=2000.0 + i,
                planned_take_profit=2030.0 + i,
                planned_position_size=0.02,
                miss_reason=MissReason.CONFIDENCE_GATE if i % 2 == 0 else MissReason.RISK_GATE,
                miss_reason_details=f"Test miss {i}",
                miss_severity=0.3 + i*0.1,
                market_conditions={},
                system_state={},
                detection_time=datetime.now(timezone.utc).isoformat(),
                miss_detection_time=datetime.now(timezone.utc).isoformat(),
                signal_age_minutes=float(i*5)
            )
            
            self.analyzer.missed_signals[missed.miss_id] = missed
            
            # Create simulation and summary
            sim = SimulatedExecution(
                sim_id=f"sim_{i:03d}",
                missed_signal_id=missed.miss_id,
                simulated_entry_price=2010.0 + i,
                simulated_entry_time=missed.signal_time,
                simulated_exit_price=2010.0 + i + (5 if i % 2 == 0 else -3),
                simulated_exit_time=(datetime.now(timezone.utc) + timedelta(hours=i)).isoformat(),
                simulated_exit_reason="TARGET_HIT" if i % 2 == 0 else "STOP_LOSS",
                simulated_outcome=SimulatedOutcome.WIN_AT_TARGET if i % 2 == 0 else SimulatedOutcome.STOPPED_OUT,
                simulated_pnl=0.1 if i % 2 == 0 else -0.05,
                simulated_pnl_pct=0.00005 if i % 2 == 0 else -0.000025,
                simulated_rr_ratio=1.67 if i % 2 == 0 else 0.75,
                comparison_score=0.7 + i*0.05,
                confidence_level=0.75 + i*0.04
            )
            
            self.analyzer.simulated_executions[sim.sim_id] = sim
            
            summary = self.analyzer.create_miss_summary(missed, sim)
            self.analyzer.missed_summaries[missed.miss_id] = summary
    
    def test_generate_report(self):
        """Test comprehensive report generation."""
        # The report needs the statistics to be populated properly
        # In a real scenario, record_missed_signal would populate statistics
        # For testing, we'll verify the analyzer has the data structures
        
        assert len(self.analyzer.missed_signals) == 5
        assert len(self.analyzer.missed_summaries) == 5
        assert len(self.analyzer.simulated_executions) == 5
        
        # Test that report can be generated (even if some fields are empty)
        report = self.analyzer.analyze_missed_opportunities()
        assert report is not None
        
        print("✓ Report generation works")
    
    def test_statistics_summary(self):
        """Test statistics summary."""
        stats = self.analyzer.get_miss_statistics()
        
        assert stats is not None
        assert stats['total_missed_signals'] == 5
        assert 'misses_by_reason' in stats
        assert 'avg_severity_by_reason' in stats
        assert stats['avg_severity'] > 0
        
        print("✓ Statistics summary works")
    
    def test_recommendations_generation(self):
        """Test recommendation generation."""
        report = self.analyzer.analyze_missed_opportunities()
        
        recommendations = report.top_improvements
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        # Check format of recommendations
        for rec in recommendations:
            assert isinstance(rec, str)
            assert len(rec) > 0
        
        print("✓ Recommendations generation works")


class TestMissedOpportunitiesAnalyzer:
    """Test suite for overall analyzer."""
    
    def test_get_singleton_analyzer(self):
        """Test singleton pattern."""
        analyzer1 = get_missed_opportunities_analyzer()
        analyzer2 = get_missed_opportunities_analyzer()
        
        assert analyzer1 is analyzer2
        assert isinstance(analyzer1, MissedOpportunitiesAnalyzer)
        
        print("✓ Singleton analyzer pattern works")
    
    def test_empty_analyzer(self):
        """Test analyzer with no missed signals."""
        analyzer = MissedOpportunitiesAnalyzer()
        
        report = analyzer.analyze_missed_opportunities()
        assert report is None  # Should return None for empty analyzer
        
        stats = analyzer.get_miss_statistics()
        assert stats is not None
        assert stats['total_missed_signals'] == 0
        
        print("✓ Empty analyzer handling works")


if __name__ == "__main__":
    try:
        # Run all tests
        test_miss = TestMissedSignalRecording()
        test_miss.setup_method()
        test_miss.test_record_missed_signal_confidence_gate()
        test_miss.test_record_missed_signal_quality_gate()
        test_miss.test_miss_severity_calculation()
        
        test_sim = TestSimulatedExecution()
        test_sim.setup_method()
        test_sim.test_simulate_execution_win()
        test_sim.test_simulate_execution_loss()
        test_sim.test_simulate_execution_no_history()
        
        test_cost = TestOpportunityCostAnalysis()
        test_cost.setup_method()
        test_cost.test_create_miss_summary()
        
        test_analytics = TestMissAnalytics()
        test_analytics.setup_method()
        test_analytics.test_generate_report()
        test_analytics.test_statistics_summary()
        test_analytics.test_recommendations_generation()
        
        test_analyzer = TestMissedOpportunitiesAnalyzer()
        test_analyzer.test_get_singleton_analyzer()
        test_analyzer.test_empty_analyzer()
        
        print("\n🎉 All Missed Opportunities Analyzer tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)