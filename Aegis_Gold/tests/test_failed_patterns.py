"""
===========================================================================
AEGIS GOLD — Failed Patterns Analyzer Test Suite (Phase Q)
===========================================================================

Tests for failed pattern detection and analysis system.

CRITICAL TEST COVERAGE:
-----------------------
1. Failed pattern recording and classification
2. Root cause analysis and contributing factors
3. Pattern failure analysis and metrics
4. Correlation analysis (volatility, trend, time)
5. Health score calculation
6. Comprehensive reporting

===========================================================================
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.failed_patterns_analyzer import (
    FailedPatternsAnalyzer,
    FailedPattern,
    PatternFailureAnalysis,
    FailureType,
    FailurePhase,
    get_failed_patterns_analyzer
)


class TestFailedPatternRecording:
    """Test suite for failed pattern recording."""
    
    def setup_method(self):
        """Setup for failed pattern tests."""
        self.analyzer = FailedPatternsAnalyzer()
    
    def test_record_failed_pattern_low_win_rate(self):
        """Test recording pattern with low win rate failure."""
        failed = self.analyzer.record_failed_pattern(
            pattern_id="pattern_001",
            pattern_type="BOS_BULLISH",
            symbol="XAUUSD",
            trade_id="trade_001",
            entry_price=2010.0,
            exit_price=2005.0,
            entry_time=datetime.now(timezone.utc).isoformat(),
            exit_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
            expected_outcome="WIN",
            actual_outcome="LOSS",
            expected_pnl=0.5,
            actual_pnl=-0.2,
            market_conditions_entry={
                'volatility_level': 'NORMAL',
                'trend': 'UPTREND',
                'momentum_score': 0.6
            },
            market_conditions_exit={
                'volatility_level': 'HIGH',
                'trend': 'SIDEWAYS',
                'momentum_score': 0.3
            },
            failure_type=FailureType.LOW_WIN_RATE,
            pattern_context={
                'timeframe': 'H1',
                'age_bars': 50,
                'confluence_count': 2,
                'direction': 'BUY'
            }
        )
        
        assert failed is not None
        assert failed.failure_id is not None
        assert failed.pattern_id == "pattern_001"
        assert failed.failure_type == FailureType.LOW_WIN_RATE
        assert failed.pnl_variance > 0  # Expected > Actual
        assert failed.failure_severity >= 0.0 and failed.failure_severity <= 1.0
        assert len(failed.contributing_factors) > 0
        
        # Should be stored
        assert failed.failure_id in self.analyzer.failed_patterns
        
        print("✓ Failed pattern recording works")
    
    def test_failure_phase_detection(self):
        """Test detection of when failure occurs."""
        # Immediate failure
        entry_time = datetime.now(timezone.utc)
        exit_time = entry_time + timedelta(minutes=5)  # 5 minutes later
        
        failed_immediate = self.analyzer.record_failed_pattern(
            pattern_id="pattern_002",
            pattern_type="BOS_BULLISH",
            symbol="XAUUSD",
            trade_id="trade_002",
            entry_price=2010.0,
            exit_price=2000.0,
            entry_time=entry_time.isoformat(),
            exit_time=exit_time.isoformat(),
            expected_outcome="WIN",
            actual_outcome="LOSS",
            expected_pnl=0.5,
            actual_pnl=-0.5,
            market_conditions_entry={},
            market_conditions_exit={},
            failure_type=FailureType.EARLY_INVALIDATION,
            pattern_context={'timeframe': 'H1', 'age_bars': 50, 'confluence_count': 2, 'direction': 'BUY'}
        )
        
        assert failed_immediate.failure_phase in [FailurePhase.IMMEDIATE, FailurePhase.SHORT_TERM]
        
        print("✓ Failure phase detection works")
    
    def test_contributing_factors_analysis(self):
        """Test identification of contributing factors."""
        failed = self.analyzer.record_failed_pattern(
            pattern_id="pattern_003",
            pattern_type="BOS_BULLISH",
            symbol="XAUUSD",
            trade_id="trade_003",
            entry_price=2010.0,
            exit_price=2008.0,
            entry_time=datetime.now(timezone.utc).isoformat(),
            exit_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            expected_outcome="WIN",
            actual_outcome="SMALL_LOSS",
            expected_pnl=0.3,
            actual_pnl=-0.1,
            market_conditions_entry={
                'volatility_level': 'HIGH',
                'trend': 'DOWNTREND',
                'momentum_score': 0.2,
                'volume': 300
            },
            market_conditions_exit={'volatility_level': 'VERY_HIGH'},
            failure_type=FailureType.TREND_FAILURE,
            pattern_context={
                'timeframe': 'H1',
                'age_bars': 3,
                'confluence_count': 1,
                'direction': 'BUY'
            }
        )
        
        assert len(failed.contributing_factors) > 0
        factor_text = " ".join(failed.contributing_factors).lower()
        assert any(x in factor_text for x in ['volatility', 'trend', 'young', 'momentum', 'volume'])
        
        print("✓ Contributing factors analysis works")


class TestFailurePhaseAnalysis:
    """Test suite for failure phase classification."""
    
    def setup_method(self):
        """Setup for phase analysis tests."""
        self.analyzer = FailedPatternsAnalyzer()
    
    def test_determine_failure_phase_immediate(self):
        """Test immediate failure phase."""
        entry_time = datetime.now(timezone.utc)
        exit_time = entry_time + timedelta(minutes=30)  # 30 minutes = 0.5 bars on H1
        
        phase = self.analyzer._determine_failure_phase(
            exit_time - entry_time,
            timeframe='H1'
        )
        
        assert phase == FailurePhase.IMMEDIATE
        print("✓ Immediate failure phase detection works")
    
    def test_determine_failure_phase_short_term(self):
        """Test short-term failure phase."""
        holding_time = timedelta(hours=3)  # 3 bars on H1
        
        phase = self.analyzer._determine_failure_phase(
            holding_time,
            timeframe='H1'
        )
        
        assert phase == FailurePhase.SHORT_TERM
        print("✓ Short-term failure phase detection works")
    
    def test_determine_failure_phase_long_term(self):
        """Test long-term failure phase."""
        holding_time = timedelta(hours=72)  # Many bars
        
        phase = self.analyzer._determine_failure_phase(
            holding_time,
            timeframe='H1'
        )
        
        assert phase == FailurePhase.LONG_TERM
        print("✓ Long-term failure phase detection works")


class TestFailureSeverityCalculation:
    """Test suite for failure severity calculation."""
    
    def setup_method(self):
        """Setup for severity tests."""
        self.analyzer = FailedPatternsAnalyzer()
    
    def test_severity_high_variance(self):
        """Test severity for large variance."""
        severity = self.analyzer._calculate_failure_severity(
            pnl_variance=1.0,  # Expected 0.5, got -0.5 = 1.0 variance
            expected_pnl=0.5,
            actual_pnl=-0.5,
            failure_type=FailureType.EARLY_INVALIDATION
        )
        
        assert severity > 0.5  # Should be significant
        print("✓ High variance severity calculation works")
    
    def test_severity_low_variance(self):
        """Test severity for small variance."""
        severity = self.analyzer._calculate_failure_severity(
            pnl_variance=0.05,
            expected_pnl=0.5,
            actual_pnl=0.45,
            failure_type=FailureType.TIMING_FAILURE
        )
        
        assert 0 <= severity <= 1.0
        print("✓ Low variance severity calculation works")


class TestPatternFailureAnalysis:
    """Test suite for comprehensive pattern failure analysis."""
    
    def setup_method(self):
        """Setup for pattern analysis tests."""
        self.analyzer = FailedPatternsAnalyzer()
        
        # Create multiple failures for a pattern
        now = datetime.now(timezone.utc)
        for i in range(5):
            self.analyzer.record_failed_pattern(
                pattern_id="analyze_pattern",
                pattern_type="BOS_BULLISH",
                symbol="XAUUSD",
                trade_id=f"trade_{i:03d}",
                entry_price=2010.0 + i,
                exit_price=2010.0 + i - (2 if i % 2 == 0 else -1),
                entry_time=(now - timedelta(hours=i*2)).isoformat(),
                exit_time=(now - timedelta(hours=i*2) + timedelta(hours=1)).isoformat(),
                expected_outcome="WIN" if i % 2 == 0 else "LOSS",
                actual_outcome="LOSS" if i % 2 == 0 else "WIN",
                expected_pnl=0.3 if i % 2 == 0 else -0.2,
                actual_pnl=-0.2 if i % 2 == 0 else 0.1,
                market_conditions_entry={
                    'volatility_level': 'HIGH' if i % 2 == 0 else 'NORMAL',
                    'trend': 'UPTREND' if i % 2 == 0 else 'DOWNTREND'
                },
                market_conditions_exit={},
                failure_type=FailureType.EARLY_INVALIDATION if i % 2 == 0 else FailureType.TIMING_FAILURE,
                pattern_context={
                    'timeframe': 'H1',
                    'age_bars': 50 - i*10,
                    'confluence_count': 2,
                    'direction': 'BUY'
                }
            )
    
    def test_pattern_analysis(self):
        """Test comprehensive pattern analysis."""
        analysis = self.analyzer.analyze_pattern_failures(
            pattern_id="analyze_pattern",
            pattern_type="BOS_BULLISH",
            all_trades={
                f"trade_{i}": {'pattern_id': 'analyze_pattern'} for i in range(5)
            }
        )
        
        assert analysis is not None
        assert analysis.pattern_id == "analyze_pattern"
        assert analysis.failed_trades > 0
        assert analysis.failure_rate >= 0.0 and analysis.failure_rate <= 1.0
        assert analysis.pattern_health_score >= 0.0 and analysis.pattern_health_score <= 100.0
        assert len(analysis.failure_types) > 0
        
        print("✓ Pattern failure analysis works")
    
    def test_failure_type_distribution(self):
        """Test failure type distribution."""
        analysis = self.analyzer.analyze_pattern_failures(
            pattern_id="analyze_pattern",
            pattern_type="BOS_BULLISH",
            all_trades={'trade_0': {'pattern_id': 'analyze_pattern'}}
        )
        
        assert len(analysis.failure_types) > 0
        assert analysis.most_common_failure is not None
        
        print("✓ Failure type distribution works")
    
    def test_health_score_calculation(self):
        """Test pattern health score."""
        analysis = self.analyzer.analyze_pattern_failures(
            pattern_id="analyze_pattern",
            pattern_type="BOS_BULLISH",
            all_trades={'trade_0': {'pattern_id': 'analyze_pattern'}}
        )
        
        # Health score should be valid
        assert 0 <= analysis.pattern_health_score <= 100
        assert 0 <= analysis.trend_score <= 100
        assert 0 <= analysis.stability_score <= 100
        
        print("✓ Health score calculation works")


class TestFailureReporting:
    """Test suite for failure reporting."""
    
    def setup_method(self):
        """Setup for reporting tests."""
        self.analyzer = FailedPatternsAnalyzer()
        
        # Create some failures
        for i in range(3):
            self.analyzer.record_failed_pattern(
                pattern_id=f"pattern_{i}",
                pattern_type="BOS_BULLISH",
                symbol="XAUUSD",
                trade_id=f"trade_{i}",
                entry_price=2010.0,
                exit_price=2005.0,
                entry_time=datetime.now(timezone.utc).isoformat(),
                exit_time=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
                expected_outcome="WIN",
                actual_outcome="LOSS",
                expected_pnl=0.5,
                actual_pnl=-0.2,
                market_conditions_entry={'volatility_level': 'HIGH'},
                market_conditions_exit={},
                failure_type=FailureType.LOW_WIN_RATE,
                pattern_context={'timeframe': 'H1', 'age_bars': 50, 'confluence_count': 2, 'direction': 'BUY'}
            )
            
            # Create analysis for each
            self.analyzer.analyze_pattern_failures(
                pattern_id=f"pattern_{i}",
                pattern_type="BOS_BULLISH",
                all_trades={f"trade_{i}": {'pattern_id': f"pattern_{i}"}}
            )
    
    def test_generate_report(self):
        """Test report generation."""
        report = self.analyzer.generate_failure_report()
        
        assert report is not None
        assert report.total_patterns_analyzed >= 0
        assert report.patterns_with_failures >= 0
        assert 0 <= report.overall_failure_rate <= 1.0
        
        print("✓ Report generation works")
    
    def test_statistics_summary(self):
        """Test statistics summary."""
        stats = self.analyzer.get_failure_statistics()
        
        assert stats is not None
        assert 'total_failed_patterns' in stats
        assert 'failure_type_distribution' in stats
        assert stats['overall_failure_rate'] >= 0
        
        print("✓ Statistics summary works")


class TestFailedPatternsAnalyzer:
    """Test suite for overall analyzer."""
    
    def test_singleton_pattern(self):
        """Test singleton analyzer."""
        analyzer1 = get_failed_patterns_analyzer()
        analyzer2 = get_failed_patterns_analyzer()
        
        assert analyzer1 is analyzer2
        assert isinstance(analyzer1, FailedPatternsAnalyzer)
        
        print("✓ Singleton analyzer pattern works")
    
    def test_empty_analyzer(self):
        """Test analyzer with no failures."""
        analyzer = FailedPatternsAnalyzer()
        
        report = analyzer.generate_failure_report()
        assert report is None  # Should return None for empty analyzer
        
        stats = analyzer.get_failure_statistics()
        assert stats['total_failed_patterns'] == 0
        
        print("✓ Empty analyzer handling works")


if __name__ == "__main__":
    try:
        # Run all tests
        test_record = TestFailedPatternRecording()
        test_record.setup_method()
        test_record.test_record_failed_pattern_low_win_rate()
        test_record.test_failure_phase_detection()
        test_record.test_contributing_factors_analysis()
        
        test_phase = TestFailurePhaseAnalysis()
        test_phase.setup_method()
        test_phase.test_determine_failure_phase_immediate()
        test_phase.test_determine_failure_phase_short_term()
        test_phase.test_determine_failure_phase_long_term()
        
        test_severity = TestFailureSeverityCalculation()
        test_severity.setup_method()
        test_severity.test_severity_high_variance()
        test_severity.test_severity_low_variance()
        
        test_analysis = TestPatternFailureAnalysis()
        test_analysis.setup_method()
        test_analysis.test_pattern_analysis()
        test_analysis.test_failure_type_distribution()
        test_analysis.test_health_score_calculation()
        
        test_report = TestFailureReporting()
        test_report.setup_method()
        test_report.test_generate_report()
        test_report.test_statistics_summary()
        
        test_analyzer = TestFailedPatternsAnalyzer()
        test_analyzer.test_singleton_pattern()
        test_analyzer.test_empty_analyzer()
        
        print("\n🎉 All Failed Patterns Analyzer tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)