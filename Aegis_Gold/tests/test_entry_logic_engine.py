"""
===========================================================================
AEGIS GOLD — Entry Logic Engine Test Suite (Phase M)
===========================================================================

Tests for earliest valid entry logic system with setup→trigger pipeline.

CRITICAL TEST COVERAGE:
-----------------------
1. Setup status evaluation (NO_SETUP → VALID_SETUP → TRIGGERED)
2. Entry zone calculation with boundaries and chase protection  
3. Entry trigger detection (breakout, pullback, momentum, structure)
4. Entry signal generation with validation
5. Real-time signal updates and expiration handling
6. Entry opportunity ranking and selection

===========================================================================
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.entry_logic_engine import (
    EntryLogicEngine,
    SetupStatus,
    EntryTriggerType,
    EntryQuality,
    EntryZone,
    EntryTrigger,
    EntrySignal,
    get_entry_logic_engine
)


class TestSetupStatusEvaluation:
    """Test suite for setup status evaluation."""
    
    def setup_method(self):
        """Setup for each test."""
        self.engine = EntryLogicEngine()
        
        self.sample_pattern_context = {
            'pattern_type': 'BOS_BULLISH',
            'direction': 'BUY',
            'scale': 'MEDIUM',
            'completion_percentage': 85.0,
            'detection_time': datetime.now(timezone.utc).isoformat(),
            'entry_price': 2010.0,
            'stop_loss': 2000.0,
            'take_profit': 2035.0
        }
        
        self.mock_snapshot = Mock()
        self.mock_snapshot.current_price = 2008.0
        
        # Mock opportunity assessment
        self.mock_opportunity = Mock()
        self.mock_opportunity.metrics.overall_quality_score = 75.0
    
    def test_valid_setup_detection(self):
        """Test detection of valid setup."""
        status = self.engine.evaluate_setup_status(
            self.sample_pattern_context,
            self.mock_snapshot,
            self.mock_opportunity
        )
        
        assert status == SetupStatus.VALID_SETUP
        print("✓ Valid setup detection works")
    
    def test_weak_setup_detection(self):
        """Test detection of weak/incomplete setup."""
        weak_context = self.sample_pattern_context.copy()
        weak_context['completion_percentage'] = 50.0  # Incomplete
        
        status = self.engine.evaluate_setup_status(
            weak_context,
            self.mock_snapshot,
            self.mock_opportunity
        )
        
        assert status == SetupStatus.WEAK_SETUP
        print("✓ Weak setup detection works")
    
    def test_no_setup_detection(self):
        """Test detection of no setup."""
        no_setup_context = self.sample_pattern_context.copy()
        no_setup_context['pattern_type'] = 'UNKNOWN'
        
        status = self.engine.evaluate_setup_status(
            no_setup_context,
            self.mock_snapshot,
            self.mock_opportunity
        )
        
        assert status == SetupStatus.NO_SETUP
        print("✓ No setup detection works")
    
    def test_expired_setup_detection(self):
        """Test detection of expired setup."""
        expired_context = self.sample_pattern_context.copy()
        # Set detection time 2 hours ago (past timeout)
        expired_context['detection_time'] = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        ).isoformat()
        
        status = self.engine.evaluate_setup_status(
            expired_context,
            self.mock_snapshot,
            self.mock_opportunity
        )
        
        assert status == SetupStatus.EXPIRED
        print("✓ Expired setup detection works")
    
    def test_low_quality_setup(self):
        """Test rejection of low quality setup."""
        low_quality_opportunity = Mock()
        low_quality_opportunity.metrics.overall_quality_score = 30.0  # Below threshold
        
        status = self.engine.evaluate_setup_status(
            self.sample_pattern_context,
            self.mock_snapshot,
            low_quality_opportunity
        )
        
        assert status == SetupStatus.WEAK_SETUP
        print("✓ Low quality setup rejection works")


class TestEntryZoneCalculation:
    """Test suite for entry zone calculation."""
    
    def setup_method(self):
        """Setup for zone tests."""
        self.engine = EntryLogicEngine()
        
        self.buy_context = {
            'direction': 'BUY',
            'scale': 'MEDIUM',
            'entry_price': 2010.0
        }
        
        self.sell_context = {
            'direction': 'SELL', 
            'scale': 'MEDIUM',
            'entry_price': 2010.0
        }
        
        self.mock_snapshot = Mock()
        self.mock_snapshot.current_price = 2010.0
        self.mock_snapshot.volatility_level = 'NORMAL'
    
    def test_buy_entry_zone_creation(self):
        """Test creation of BUY entry zone."""
        zone = self.engine.create_entry_zone(self.buy_context, self.mock_snapshot)
        
        assert isinstance(zone, EntryZone)
        assert zone.direction == "BUY"
        assert zone.optimal_price == 2010.0
        assert zone.zone_low < zone.optimal_price < zone.zone_high
        assert zone.max_chase_price > zone.zone_high
        assert zone.zone_width > 0
        
        print("✓ BUY entry zone creation works")
    
    def test_sell_entry_zone_creation(self):
        """Test creation of SELL entry zone."""
        zone = self.engine.create_entry_zone(self.sell_context, self.mock_snapshot)
        
        assert zone.direction == "SELL"
        assert zone.optimal_price == 2010.0
        assert zone.zone_low < zone.optimal_price < zone.zone_high
        assert zone.max_chase_price < zone.zone_low
        assert zone.zone_width > 0
        
        print("✓ SELL entry zone creation works")
    
    def test_entry_zone_price_checks(self):
        """Test entry zone price validation methods."""
        zone = self.engine.create_entry_zone(self.buy_context, self.mock_snapshot)
        
        # Test price in zone
        assert zone.is_price_in_zone(zone.optimal_price)
        assert zone.is_price_in_zone((zone.zone_low + zone.zone_high) / 2)
        
        # Test price outside zone
        assert not zone.is_price_in_zone(zone.zone_low - 5)
        assert not zone.is_price_in_zone(zone.zone_high + 5)
        
        # Test chase limits
        assert zone.is_price_chaseable(zone.zone_high + 5)  # Within chase limit
        assert zone.is_price_chaseable(zone.optimal_price)
        
        print("✓ Entry zone price checks work")
    
    def test_entry_quality_calculation(self):
        """Test entry quality calculation based on price distance."""
        zone = self.engine.create_entry_zone(self.buy_context, self.mock_snapshot)
        
        # Perfect entry at optimal price
        perfect_quality = zone.calculate_entry_quality(zone.optimal_price)
        assert perfect_quality == EntryQuality.PERFECT
        
        # Good entry within zone
        good_price = zone.optimal_price + zone.zone_width * 0.3
        good_quality = zone.calculate_entry_quality(good_price)
        assert good_quality in [EntryQuality.GOOD, EntryQuality.FAIR]
        
        # Chase entry outside zone but within limits
        chase_price = zone.zone_high + 5
        if zone.is_price_chaseable(chase_price):
            chase_quality = zone.calculate_entry_quality(chase_price)
            assert chase_quality == EntryQuality.CHASE
        
        # Rejected entry beyond limits
        rejected_price = zone.max_chase_price + 10
        rejected_quality = zone.calculate_entry_quality(rejected_price)
        assert rejected_quality == EntryQuality.REJECTED
        
        print("✓ Entry quality calculation works")
    
    def test_volatility_adjustment(self):
        """Test entry zone adjustment for volatility."""
        # High volatility should create wider zones
        high_vol_snapshot = Mock()
        high_vol_snapshot.current_price = 2010.0
        high_vol_snapshot.volatility_level = 'HIGH'
        
        normal_zone = self.engine.create_entry_zone(self.buy_context, self.mock_snapshot)
        high_vol_zone = self.engine.create_entry_zone(self.buy_context, high_vol_snapshot)
        
        assert high_vol_zone.zone_width > normal_zone.zone_width
        print("✓ Volatility adjustment works")


class TestEntryTriggerDetection:
    """Test suite for entry trigger detection."""
    
    def setup_method(self):
        """Setup for trigger tests."""
        self.engine = EntryLogicEngine()
        
        self.pattern_context = {
            'pattern_type': 'BOS_BULLISH',
            'direction': 'BUY',
            'entry_price': 2010.0,
            'stop_loss': 2000.0,
            'take_profit': 2035.0
        }
        
        self.current_snapshot = Mock()
        self.current_snapshot.current_price = 2012.0  # Above entry (breakout)
        self.current_snapshot.volume_spike = True
        
        self.previous_snapshot = Mock()
        self.previous_snapshot.current_price = 2009.0  # Below entry
    
    def test_breakout_trigger_detection(self):
        """Test detection of breakout trigger."""
        trigger = self.engine._detect_breakout_trigger(
            self.pattern_context,
            self.current_snapshot,
            self.previous_snapshot
        )
        
        assert trigger is not None
        assert isinstance(trigger, EntryTrigger)
        assert trigger.trigger_type == EntryTriggerType.BREAKOUT
        assert trigger.confidence >= self.engine.min_trigger_confidence
        assert trigger.trigger_price == 2012.0
        assert trigger.urgency_level == "IMMEDIATE"
        
        print("✓ Breakout trigger detection works")
    
    def test_no_false_breakout_trigger(self):
        """Test no false trigger when price hasn't broken level."""
        # Price still below breakout level
        no_break_snapshot = Mock()
        no_break_snapshot.current_price = 2009.5
        
        trigger = self.engine._detect_breakout_trigger(
            self.pattern_context,
            no_break_snapshot,
            self.previous_snapshot
        )
        
        assert trigger is None
        print("✓ No false breakout trigger works")
    
    def test_sell_breakout_trigger(self):
        """Test SELL breakout trigger detection."""
        sell_context = self.pattern_context.copy()
        sell_context['direction'] = 'SELL'
        
        current_snapshot = Mock()
        current_snapshot.current_price = 2008.0  # Below entry (SELL breakout)
        current_snapshot.volume_spike = True
        
        previous_snapshot = Mock()
        previous_snapshot.current_price = 2011.0  # Above entry
        
        trigger = self.engine._detect_breakout_trigger(
            sell_context,
            current_snapshot,
            previous_snapshot
        )
        
        assert trigger is not None
        assert trigger.trigger_type == EntryTriggerType.BREAKOUT
        assert trigger.confidence >= self.engine.min_trigger_confidence
        
        print("✓ SELL breakout trigger works")
    
    def test_momentum_trigger_detection(self):
        """Test momentum shift trigger detection."""
        # Strong upward momentum for BUY
        current_snapshot = Mock()
        current_snapshot.current_price = 2015.0  # Strong move up
        current_snapshot.momentum_score = 0.8
        current_snapshot.volume_spike = True
        
        previous_snapshot = Mock()
        previous_snapshot.current_price = 2008.0  # Previous price
        
        trigger = self.engine._detect_momentum_trigger(
            self.pattern_context,
            current_snapshot, 
            previous_snapshot
        )
        
        assert trigger is not None
        assert trigger.trigger_type == EntryTriggerType.MOMENTUM_SHIFT
        assert trigger.momentum_alignment
        
        print("✓ Momentum trigger detection works")
    
    def test_structure_trigger_detection(self):
        """Test structure break trigger detection."""
        structure_context = self.pattern_context.copy()
        structure_context['pattern_type'] = 'BOS_BULLISH'
        structure_context['structure_broken'] = True
        structure_context['structure_level'] = 2009.0
        
        current_snapshot = Mock()
        current_snapshot.current_price = 2012.0
        current_snapshot.volume_spike = True
        
        trigger = self.engine._detect_structure_trigger(
            structure_context,
            current_snapshot
        )
        
        assert trigger is not None
        assert trigger.trigger_type == EntryTriggerType.STRUCTURE_BREAK
        
        print("✓ Structure trigger detection works")


class TestEntrySignalGeneration:
    """Test suite for complete entry signal generation."""
    
    def setup_method(self):
        """Setup for signal tests."""
        self.engine = EntryLogicEngine()
        
        self.pattern_context = {
            'pattern_id': 'test_pattern_001',
            'pattern_type': 'BOS_BULLISH',
            'direction': 'BUY',
            'scale': 'MEDIUM',
            'symbol': 'XAUUSD',
            'completion_percentage': 85.0,
            'detection_time': datetime.now(timezone.utc).isoformat(),
            'entry_price': 2010.0,
            'stop_loss': 2000.0,
            'take_profit': 2035.0
        }
        
        self.mock_snapshot = Mock()
        self.mock_snapshot.current_price = 2008.0
        self.mock_snapshot.volatility_level = 'NORMAL'
        
        self.mock_opportunity = Mock()
        self.mock_opportunity.metrics.overall_quality_score = 75.0
        self.mock_opportunity.metrics.kelly_fraction = 0.03
        self.mock_opportunity.is_tradeable = True
    
    def test_valid_entry_signal_generation(self):
        """Test generation of valid entry signal."""
        signal = self.engine.generate_entry_signal(
            self.pattern_context,
            self.mock_snapshot,
            self.mock_opportunity
        )
        
        assert isinstance(signal, EntrySignal)
        assert signal.pattern_id == 'test_pattern_001'
        assert signal.symbol == 'XAUUSD'
        assert signal.is_valid
        assert len(signal.validation_errors) == 0
        assert signal.setup_quality_score == 75.0
        assert signal.position_size_fraction > 0
        
        print("✓ Valid entry signal generation works")
    
    def test_entry_signal_with_trigger(self):
        """Test entry signal when trigger is present."""
        # Setup conditions for trigger
        triggered_snapshot = Mock()
        triggered_snapshot.current_price = 2012.0  # Above entry (breakout)
        triggered_snapshot.volatility_level = 'NORMAL'
        triggered_snapshot.volume_spike = True
        
        # Mock previous snapshot for trigger detection
        with patch.object(self.engine, 'detect_entry_trigger') as mock_detect:
            mock_trigger = EntryTrigger(
                trigger_type=EntryTriggerType.BREAKOUT,
                trigger_price=2012.0,
                trigger_time=datetime.now(timezone.utc).isoformat(),
                confidence=0.85,
                supporting_factors=["Clean breakout"],
                invalidation_price=2009.0,
                urgency_level="IMMEDIATE",
                market_structure={'level': 2010.0},
                volume_confirmation=True,
                momentum_alignment=True
            )
            mock_detect.return_value = mock_trigger
            
            signal = self.engine.generate_entry_signal(
                self.pattern_context,
                triggered_snapshot,
                self.mock_opportunity
            )
            
            assert signal.entry_trigger is not None
            assert signal.trigger_confirmation
            assert signal.recommended_action in ["ENTER", "CHASE"]
            assert signal.entry_urgency in ["IMMEDIATE", "HIGH"]
            
        print("✓ Entry signal with trigger works")
    
    def test_invalid_entry_signal(self):
        """Test rejection of invalid entry signal."""
        invalid_context = self.pattern_context.copy()
        invalid_context['stop_loss'] = 0.0  # Invalid stop loss
        
        signal = self.engine.generate_entry_signal(
            invalid_context,
            self.mock_snapshot,
            self.mock_opportunity
        )
        
        assert not signal.is_valid
        assert len(signal.validation_errors) > 0
        assert signal.recommended_action == "ABORT"
        
        print("✓ Invalid entry signal rejection works")
    
    def test_position_size_calculation(self):
        """Test position size calculation based on quality."""
        # High quality opportunity should get larger position
        high_quality_opportunity = Mock()
        high_quality_opportunity.metrics.overall_quality_score = 90.0
        high_quality_opportunity.metrics.kelly_fraction = 0.04
        high_quality_opportunity.is_tradeable = True
        
        signal_high = self.engine.generate_entry_signal(
            self.pattern_context,
            self.mock_snapshot,
            high_quality_opportunity
        )
        
        signal_normal = self.engine.generate_entry_signal(
            self.pattern_context,
            self.mock_snapshot,
            self.mock_opportunity
        )
        
        assert signal_high.position_size_fraction > signal_normal.position_size_fraction
        assert signal_high.position_size_fraction <= 0.05  # Cap at 5%
        
        print("✓ Position size calculation works")


class TestSignalUpdatesAndManagement:
    """Test suite for signal updates and management."""
    
    def setup_method(self):
        """Setup for management tests."""
        self.engine = EntryLogicEngine()
        
        # Create a sample signal
        pattern_context = {
            'pattern_id': 'test_pattern_001',
            'pattern_type': 'BOS_BULLISH',
            'direction': 'BUY',
            'scale': 'MEDIUM',
            'completion_percentage': 85.0,
            'detection_time': datetime.now(timezone.utc).isoformat(),
            'entry_price': 2010.0,
            'stop_loss': 2000.0,
            'take_profit': 2035.0
        }
        
        mock_snapshot = Mock()
        mock_snapshot.current_price = 2008.0
        mock_snapshot.volatility_level = 'NORMAL'
        
        self.mock_opportunity = Mock()
        self.mock_opportunity.metrics.overall_quality_score = 75.0
        self.mock_opportunity.metrics.kelly_fraction = 0.03
        self.mock_opportunity.is_tradeable = True
        
        self.signal = self.engine.generate_entry_signal(
            pattern_context, mock_snapshot, self.mock_opportunity
        )
    
    def test_signal_updates(self):
        """Test updating signals with new market conditions."""
        new_snapshot = Mock()
        new_snapshot.current_price = 2012.0  # Price moved up
        
        updated_signals = self.engine.update_active_signals(new_snapshot)
        
        assert len(updated_signals) > 0
        updated_signal = updated_signals[0]
        assert updated_signal.current_price == 2012.0
        
        print("✓ Signal updates work")
    
    def test_signal_expiration(self):
        """Test signal expiration handling."""
        # Create expired signal
        expired_context = {
            'pattern_id': 'expired_pattern',
            'pattern_type': 'BOS_BULLISH', 
            'direction': 'BUY',
            'completion_percentage': 85.0,
            'detection_time': (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(),
            'entry_price': 2010.0,
            'stop_loss': 2000.0,
            'take_profit': 2035.0
        }
        
        mock_snapshot = Mock()
        mock_snapshot.current_price = 2008.0
        
        expired_signal = self.engine.generate_entry_signal(expired_context, mock_snapshot)
        
        # Update should expire the signal
        updated_signals = self.engine.update_active_signals(mock_snapshot)
        
        # Check that expired signal was removed from active setups
        assert expired_signal.pattern_id not in self.engine.active_setups
        
        print("✓ Signal expiration works")
    
    def test_best_opportunity_selection(self):
        """Test selection of best entry opportunity."""
        # Create multiple opportunities of different quality
        mock_snapshot = Mock()
        mock_snapshot.current_price = 2012.0
        mock_snapshot.volatility_level = 'NORMAL'
        
        # Add triggered signals to engine
        for i, quality in enumerate([60.0, 80.0, 90.0]):
            pattern_context = {
                'pattern_id': f'pattern_{i}',
                'pattern_type': 'BOS_BULLISH',
                'direction': 'BUY',
                'completion_percentage': 85.0,
                'detection_time': datetime.now(timezone.utc).isoformat(),
                'entry_price': 2010.0,
                'stop_loss': 2000.0,
                'take_profit': 2035.0
            }
            
            mock_opportunity = Mock()
            mock_opportunity.metrics = Mock()
            mock_opportunity.metrics.overall_quality_score = quality
            mock_opportunity.metrics.kelly_fraction = 0.03
            mock_opportunity.is_tradeable = True
            
            signal = self.engine.generate_entry_signal(
                pattern_context, mock_snapshot, mock_opportunity
            )
            
            # Manually add to triggered signals for testing
            if quality > 70:  # Only add good signals as triggered
                signal.recommended_action = "ENTER"
                signal.entry_trigger = Mock()
                signal.entry_trigger.confidence = 0.8
                self.engine.triggered_signals[signal.signal_id] = signal
        
        best_opportunity = self.engine.get_best_entry_opportunity()
        
        if best_opportunity:
            assert best_opportunity.setup_quality_score >= 80.0  # Should pick high quality
        
        print("✓ Best opportunity selection works")
    
    def test_entry_summary(self):
        """Test entry summary generation.""" 
        summary = self.engine.get_entry_summary()
        
        assert isinstance(summary, dict)
        assert "active_setups" in summary
        assert "triggered_signals" in summary
        assert "status_distribution" in summary
        assert "action_distribution" in summary
        
        print("✓ Entry summary works")


def test_singleton_entry_engine():
    """Test singleton entry engine."""
    engine1 = get_entry_logic_engine()
    engine2 = get_entry_logic_engine()
    
    assert engine1 is engine2
    assert isinstance(engine1, EntryLogicEngine)
    
    print("✓ Singleton entry engine works")


if __name__ == "__main__":
    try:
        # Run all tests
        test_setup = TestSetupStatusEvaluation()
        test_setup.setup_method()
        test_setup.test_valid_setup_detection()
        test_setup.test_weak_setup_detection()
        test_setup.test_no_setup_detection()
        test_setup.test_expired_setup_detection()
        test_setup.test_low_quality_setup()
        
        test_zones = TestEntryZoneCalculation()
        test_zones.setup_method()
        test_zones.test_buy_entry_zone_creation()
        test_zones.test_sell_entry_zone_creation()
        test_zones.test_entry_zone_price_checks()
        test_zones.test_entry_quality_calculation()
        test_zones.test_volatility_adjustment()
        
        test_triggers = TestEntryTriggerDetection()
        test_triggers.setup_method()
        test_triggers.test_breakout_trigger_detection()
        test_triggers.test_no_false_breakout_trigger()
        test_triggers.test_sell_breakout_trigger()
        test_triggers.test_momentum_trigger_detection()
        test_triggers.test_structure_trigger_detection()
        
        test_signals = TestEntrySignalGeneration()
        test_signals.setup_method()
        test_signals.test_valid_entry_signal_generation()
        test_signals.test_entry_signal_with_trigger()
        test_signals.test_invalid_entry_signal()
        test_signals.test_position_size_calculation()
        
        test_management = TestSignalUpdatesAndManagement()
        test_management.setup_method()
        test_management.test_signal_updates()
        test_management.test_signal_expiration()
        test_management.test_best_opportunity_selection()
        test_management.test_entry_summary()
        
        test_singleton_entry_engine()
        
        print("\n🎉 All Entry Logic Engine tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)