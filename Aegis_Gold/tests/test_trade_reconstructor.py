"""
===========================================================================
AEGIS GOLD — Trade Reconstructor Test Suite (Phase O)
===========================================================================

Tests for comprehensive trade reconstruction and analysis system.

CRITICAL TEST COVERAGE:
-----------------------
1. Trade execution recording and ledger management
2. Trade outcome classification and quality assessment
3. Pattern-level outcome analysis
4. Causality validation in trade execution
5. Performance metrics calculation
6. Complete trade lifecycle management

===========================================================================
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.trade_reconstructor import (
    TradeReconstructor,
    TradeExecution,
    TradeOutcome,
    EntryQuality,
    ExitQuality,
    PatternOutcomeAnalysis,
    get_trade_reconstructor
)


class TestTradeExecution:
    """Test suite for trade execution recording."""
    
    def setup_method(self):
        """Setup for trade execution tests."""
        self.reconstructor = TradeReconstructor()
        
        # Mock entry signal
        self.mock_entry_signal = Mock()
        self.mock_entry_signal.signal_id = "test_signal_001"
        self.mock_entry_signal.setup_completion_time = datetime.now(timezone.utc).isoformat()
        self.mock_entry_signal.signal_time = datetime.now(timezone.utc).isoformat()
        self.mock_entry_signal.position_size_fraction = 0.02
        
        # Mock entry zone
        self.mock_entry_zone = Mock()
        self.mock_entry_zone.optimal_price = 2010.0
        self.mock_entry_zone.current_quality = EntryQuality.GOOD
        self.mock_entry_zone.direction = "BUY"
        self.mock_entry_signal.entry_zone = self.mock_entry_zone
        
        # Mock market snapshot
        self.mock_snapshot_entry = Mock()
        self.mock_snapshot_entry.current_price = 2010.0
        self.mock_snapshot_entry.volatility_level = "NORMAL"
        self.mock_snapshot_entry.volume = 1000
        self.mock_snapshot_entry.momentum_score = 0.7
        
        # Pattern context
        self.pattern_context = {
            'pattern_id': 'test_pattern_001',
            'symbol': 'XAUUSD',
            'take_profit': 2030.0,
            'stop_loss': 2000.0
        }
    
    def test_record_trade_entry(self):
        """Test recording of trade entry."""
        execution = self.reconstructor.record_trade_execution(
            pattern_id='test_pattern_001',
            pattern_context=self.pattern_context,
            entry_signal=self.mock_entry_signal,
            market_snapshot_entry=self.mock_snapshot_entry
        )
        
        assert isinstance(execution, TradeExecution)
        assert execution.trade_id is not None
        assert execution.pattern_id == 'test_pattern_001'
        assert execution.symbol == 'XAUUSD'
        assert execution.direction == "BUY"
        assert execution.entry_price == 2010.0
        assert execution.stop_loss == 2000.0
        assert execution.target_price == 2030.0
        assert execution.entry_quality == EntryQuality.GOOD
        assert execution.market_conditions_entry is not None
        
        # Should be stored
        assert execution.trade_id in self.reconstructor.all_trades
        
        # Should have ledger entry
        assert len(self.reconstructor.trade_ledger) > 0
        
        print("✓ Trade entry recording works")
    
    def test_record_partial_fill(self):
        """Test recording of partial profit taking."""
        execution = self.reconstructor.record_trade_execution(
            pattern_id='test_pattern_001',
            pattern_context=self.pattern_context,
            entry_signal=self.mock_entry_signal,
            market_snapshot_entry=self.mock_snapshot_entry
        )
        
        # Record partial fill
        self.reconstructor.record_partial_fill(
            trade_id=execution.trade_id,
            exit_price=2020.0,
            size_fraction=0.5,
            exit_reason="PARTIAL_TP"
        )
        
        execution_updated = self.reconstructor.all_trades[execution.trade_id]
        assert len(execution_updated.partial_fills) > 0
        
        partial = execution_updated.partial_fills[0]
        assert partial['exit_price'] == 2020.0
        assert partial['size_fraction'] == 0.5
        assert partial['pnl'] > 0  # Should be profitable
        
        print("✓ Partial fill recording works")


class TestTradeOutcomeClassification:
    """Test suite for trade outcome classification."""
    
    def setup_method(self):
        """Setup for outcome classification tests."""
        self.reconstructor = TradeReconstructor()
    
    def test_outcome_at_target(self):
        """Test classification of winning trade at target."""
        # Create trade execution
        execution = TradeExecution(
            trade_id="test_001",
            pattern_id="pattern_001",
            symbol="XAUUSD",
            direction="BUY",
            signal_time="2026-01-01T00:00:00Z",
            entry_time="2026-01-01T01:00:00Z",
            exit_time="2026-01-01T02:00:00Z",
            entry_price=2010.0,
            target_price=2030.0,
            stop_loss=2000.0,
            position_size=0.02,
            outcome=TradeOutcome.WIN_AT_TARGET,
            entry_quality=EntryQuality.GOOD,
            entry_slippage=1.0,
            market_conditions_entry={},
            favorable_excursion=20.0,
            adverse_excursion=0.0,
            exit_price=2030.0,
            exit_quality=ExitQuality.OPTIMAL,
            exit_slippage=0.0,
            final_pnl=20.0,
            final_pnl_pct=0.02,
            risk_taken=10.0,
            reward_earned=20.0,
            realized_rr_ratio=2.0,
            market_conditions_exit={}
        )
        
        outcome = self.reconstructor._classify_outcome(execution, "TARGET_HIT")
        assert outcome == TradeOutcome.WIN_AT_TARGET
        
        print("✓ Outcome classification: Win at target works")
    
    def test_outcome_stopped_out(self):
        """Test classification of stopped out trade."""
        execution = TradeExecution(
            trade_id="test_002",
            pattern_id="pattern_001",
            symbol="XAUUSD",
            direction="BUY",
            signal_time="2026-01-01T00:00:00Z",
            entry_time="2026-01-01T01:00:00Z",
            exit_time="2026-01-01T02:00:00Z",
            entry_price=2010.0,
            target_price=2030.0,
            stop_loss=2000.0,
            position_size=0.02,
            outcome=TradeOutcome.STOPPED_OUT,
            entry_quality=EntryQuality.GOOD,
            entry_slippage=1.0,
            market_conditions_entry={},
            favorable_excursion=0.0,
            adverse_excursion=-10.0,
            exit_price=2000.0,
            exit_quality=ExitQuality.FORCED,
            exit_slippage=30.0,
            final_pnl=-10.0,
            final_pnl_pct=-0.01,
            risk_taken=10.0,
            reward_earned=0.0,
            realized_rr_ratio=0.0,
            market_conditions_exit={}
        )
        
        outcome = self.reconstructor._classify_outcome(execution, "STOP_HIT")
        assert outcome == TradeOutcome.STOPPED_OUT
        
        print("✓ Outcome classification: Stopped out works")
    
    def test_exit_quality_assessment(self):
        """Test exit quality assessment."""
        execution = TradeExecution(
            trade_id="test_003",
            pattern_id="pattern_001",
            symbol="XAUUSD",
            direction="BUY",
            signal_time="2026-01-01T00:00:00Z",
            entry_time="2026-01-01T01:00:00Z",
            exit_time="2026-01-01T02:00:00Z",
            entry_price=2010.0,
            target_price=2030.0,
            stop_loss=2000.0,
            position_size=0.02,
            outcome=TradeOutcome.WIN_AT_TARGET,
            entry_quality=EntryQuality.GOOD,
            entry_slippage=1.0,
            market_conditions_entry={},
            favorable_excursion=20.5,
            adverse_excursion=0.0,
            exit_price=2030.5,
            exit_quality=None,
            exit_slippage=0.5,
            final_pnl=20.5,
            final_pnl_pct=0.02,
            risk_taken=10.0,
            reward_earned=20.5,
            realized_rr_ratio=2.05,
            market_conditions_exit={}
        )
        
        quality = self.reconstructor._assess_exit_quality(execution)
        print(f"Debug: exit quality = {quality}")
        assert quality in [ExitQuality.OPTIMAL, ExitQuality.GOOD]  # Should be very good
        
        print("✓ Exit quality assessment works")


class TestPatternOutcomeAnalysis:
    """Test suite for pattern outcome analysis."""
    
    def setup_method(self):
        """Setup for pattern analysis tests."""
        self.reconstructor = TradeReconstructor()
        
        # Create multiple trades for a pattern
        for i in range(5):
            execution = TradeExecution(
                trade_id=f"test_{i:03d}",
                pattern_id="pattern_analysis",
                symbol="XAUUSD",
                direction="BUY",
                signal_time="2026-01-01T00:00:00Z",
                entry_time="2026-01-01T01:00:00Z",
                exit_time="2026-01-01T02:00:00Z",
                entry_price=2010.0,
                target_price=2030.0,
                stop_loss=2000.0,
                position_size=0.02,
                outcome=TradeOutcome.WIN_PARTIAL if i % 2 == 0 else TradeOutcome.SMALL_LOSS,
                entry_quality=EntryQuality.GOOD,
                entry_slippage=1.0,
                market_conditions_entry={},
                favorable_excursion=10.0 if i % 2 == 0 else 0.0,
                adverse_excursion=-5.0 if i % 2 != 0 else 0.0,
                exit_price=2010.0 + (i * 5),  # Varying exit prices
                exit_quality=ExitQuality.GOOD if i % 2 == 0 else ExitQuality.ACCEPTABLE,
                exit_slippage=5.0,
                final_pnl=10.0 if i % 2 == 0 else -5.0,
                final_pnl_pct=0.01 if i % 2 == 0 else -0.005,
                risk_taken=10.0,
                reward_earned=10.0 if i % 2 == 0 else 0.0,
                realized_rr_ratio=1.0,
                market_conditions_exit={}
            )
            self.reconstructor.all_trades[execution.trade_id] = execution
    
    def test_pattern_outcome_analysis(self):
        """Test pattern-level outcome analysis."""
        analysis = self.reconstructor.analyze_pattern_outcomes(
            pattern_id="pattern_analysis",
            pattern_type="BOS_BULLISH",
            timeframe="H1"
        )
        
        assert isinstance(analysis, PatternOutcomeAnalysis)
        assert analysis.pattern_id == "pattern_analysis"
        assert analysis.total_trades > 0
        assert analysis.win_rate >= 0.0
        assert analysis.win_rate <= 1.0
        assert analysis.profit_factor >= 0.0
        
        # Should be stored
        assert "pattern_analysis" in self.reconstructor.pattern_outcomes
        
        print("✓ Pattern outcome analysis works")
    
    def test_pattern_metrics_calculation(self):
        """Test calculation of pattern metrics."""
        analysis = self.reconstructor.analyze_pattern_outcomes(
            pattern_id="pattern_analysis",
            pattern_type="BOS_BULLISH",
            timeframe="H1"
        )
        
        # Check metrics
        assert analysis.total_trades == 5
        assert analysis.winners > 0
        assert analysis.losers > 0
        assert analysis.avg_win > 0
        assert analysis.avg_loss <= 0
        assert analysis.expectancy is not None
        assert analysis.avg_rr_ratio > 0
        
        print("✓ Pattern metrics calculation works")


class TestTradeExit:
    """Test suite for trade exit and completion."""
    
    def setup_method(self):
        """Setup for trade exit tests."""
        self.reconstructor = TradeReconstructor()
        
        # Create and record entry
        mock_signal = Mock()
        mock_signal.setup_completion_time = datetime.now(timezone.utc).isoformat()
        mock_signal.signal_time = datetime.now(timezone.utc).isoformat()
        mock_signal.position_size_fraction = 0.02
        
        mock_zone = Mock()
        mock_zone.optimal_price = 2010.0
        mock_zone.current_quality = EntryQuality.GOOD
        mock_zone.direction = "BUY"
        mock_signal.entry_zone = mock_zone
        
        mock_snapshot = Mock()
        mock_snapshot.current_price = 2010.0
        
        self.pattern_context = {
            'pattern_id': 'exit_test_pattern',
            'symbol': 'XAUUSD',
            'take_profit': 2030.0,
            'stop_loss': 2000.0
        }
        
        self.execution = self.reconstructor.record_trade_execution(
            pattern_id='exit_test_pattern',
            pattern_context=self.pattern_context,
            entry_signal=mock_signal,
            market_snapshot_entry=mock_snapshot
        )
        
        self.trade_id = self.execution.trade_id
    
    def test_record_trade_exit(self):
        """Test recording of trade exit."""
        mock_exit_snapshot = Mock()
        mock_exit_snapshot.current_price = 2025.0
        
        exit_execution = self.reconstructor.record_trade_exit(
            trade_id=self.trade_id,
            exit_price=2025.0,
            exit_reason="PARTIAL_TP",
            market_snapshot_exit=mock_exit_snapshot
        )
        
        assert exit_execution is not None
        assert exit_execution.exit_price == 2025.0
        assert exit_execution.final_pnl > 0
        assert exit_execution.exit_quality is not None
        assert exit_execution.holding_time is not None
        
        print("✓ Trade exit recording works")
    
    def test_exit_updates_performance(self):
        """Test that exit updates performance metrics."""
        initial_trades = self.reconstructor.performance_summary['total_trades']
        
        mock_exit_snapshot = Mock()
        mock_exit_snapshot.current_price = 2025.0
        
        self.reconstructor.record_trade_exit(
            trade_id=self.trade_id,
            exit_price=2025.0,
            exit_reason="PARTIAL_TP",
            market_snapshot_exit=mock_exit_snapshot
        )
        
        updated_trades = self.reconstructor.performance_summary['total_trades']
        assert updated_trades > initial_trades
        assert self.reconstructor.performance_summary['total_pnl'] > 0
        
        print("✓ Exit updates performance metrics works")


class TestTradeReconstructor:
    """Test suite for overall trade reconstructor."""
    
    def test_get_execution_summary(self):
        """Test execution summary generation."""
        reconstructor = TradeReconstructor()
        
        summary = reconstructor.get_trade_execution_summary()
        
        assert 'total_trades' in summary
        assert 'completed_trades' in summary
        assert 'open_trades' in summary
        assert 'performance' in summary
        assert 'ledger_entries' in summary
        
        print("✓ Execution summary generation works")
    
    def test_generate_report(self):
        """Test comprehensive report generation."""
        reconstructor = TradeReconstructor()
        
        report = reconstructor.generate_trade_report()
        
        assert 'summary' in report
        assert 'performance' in report
        assert 'pattern_outcomes' in report
        assert 'trades' in report
        assert 'data_quality' in report
        
        print("✓ Report generation works")


def test_singleton_reconstructor():
    """Test singleton trade reconstructor."""
    recon1 = get_trade_reconstructor()
    recon2 = get_trade_reconstructor()
    
    assert recon1 is recon2
    assert isinstance(recon1, TradeReconstructor)
    
    print("✓ Singleton reconstructor works")


if __name__ == "__main__":
    try:
        # Run all tests
        test_exec = TestTradeExecution()
        test_exec.setup_method()
        test_exec.test_record_trade_entry()
        test_exec.test_record_partial_fill()
        
        test_outcome = TestTradeOutcomeClassification()
        test_outcome.setup_method()
        test_outcome.test_outcome_at_target()
        test_outcome.test_outcome_stopped_out()
        test_outcome.test_exit_quality_assessment()
        
        test_analysis = TestPatternOutcomeAnalysis()
        test_analysis.setup_method()
        test_analysis.test_pattern_outcome_analysis()
        test_analysis.test_pattern_metrics_calculation()
        
        test_exit = TestTradeExit()
        test_exit.setup_method()
        test_exit.test_record_trade_exit()
        test_exit.test_exit_updates_performance()
        
        test_recon = TestTradeReconstructor()
        test_recon.test_get_execution_summary()
        test_recon.test_generate_report()
        
        test_singleton_reconstructor()
        
        print("\n🎉 All Trade Reconstructor tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)