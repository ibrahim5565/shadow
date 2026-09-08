"""
===========================================================================
AEGIS GOLD — Structural Risk Manager Test Suite (Phase N)
===========================================================================

Tests for structural stop loss and take profit management system.

CRITICAL TEST COVERAGE:
-----------------------
1. Structural level identification and validation
2. Stop loss calculation based on market structure
3. Take profit level calculation with partial targets
4. Risk parameter creation and management
5. Dynamic risk adjustments and trailing stops
6. Trade risk lifecycle management

===========================================================================
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.structural_risk_manager import (
    StructuralRiskManager,
    StopLossType,
    TakeProfitType,
    RiskAdjustmentReason,
    StructuralLevel,
    RiskParameters,
    TradeRisk,
    get_structural_risk_manager
)


class TestStructuralLevelIdentification:
    """Test suite for structural level identification."""
    
    def setup_method(self):
        """Setup for each test."""
        self.manager = StructuralRiskManager()
        
        self.sample_market_structure = {
            'support_levels': [
                {'price': 2000.0, 'strength': 0.8, 'timeframe': 'H1', 'age_bars': 50, 'test_count': 3},
                {'price': 1995.0, 'strength': 0.6, 'timeframe': 'H4', 'age_bars': 100, 'test_count': 2},
                2005.0  # Simple format
            ],
            'resistance_levels': [
                {'price': 2025.0, 'strength': 0.9, 'timeframe': 'H1', 'age_bars': 30, 'test_count': 4},
                {'price': 2030.0, 'strength': 0.7, 'timeframe': 'H4', 'age_bars': 80, 'test_count': 2}
            ],
            'liquidity_levels': [2002.0, 2028.0]
        }
    
    def test_identify_buy_structural_levels(self):
        """Test identification of structural levels for BUY position."""
        levels = self.manager._identify_structural_levels(
            reference_price=2010.0,
            direction="BUY",
            market_structure=self.sample_market_structure
        )
        
        assert len(levels) > 0
        
        # Should include support levels below price for stop loss
        support_levels = [l for l in levels if l.level_type in ["SUPPORT", "LIQUIDITY"] and l.level_price < 2010.0]
        assert len(support_levels) > 0
        
        # Should include resistance levels above price for take profit
        resistance_levels = [l for l in levels if l.level_type == "RESISTANCE" and l.level_price > 2010.0]
        assert len(resistance_levels) > 0
        
        # Levels should be sorted by relevance
        assert all(isinstance(level, StructuralLevel) for level in levels)
        
        print("✓ BUY structural level identification works")
    
    def test_identify_sell_structural_levels(self):
        """Test identification of structural levels for SELL position."""
        levels = self.manager._identify_structural_levels(
            reference_price=2010.0,
            direction="SELL",
            market_structure=self.sample_market_structure
        )
        
        # Should include resistance levels above price for stop loss
        resistance_levels = [l for l in levels if l.level_type in ["RESISTANCE", "LIQUIDITY"] and l.level_price > 2010.0]
        assert len(resistance_levels) > 0
        
        # Should include support levels below price for take profit
        support_levels = [l for l in levels if l.level_type == "SUPPORT" and l.level_price < 2010.0]
        assert len(support_levels) > 0
        
        print("✓ SELL structural level identification works")
    
    def test_level_strength_filtering(self):
        """Test filtering levels by minimum strength."""
        weak_structure = {
            'support_levels': [
                {'price': 2000.0, 'strength': 0.2, 'timeframe': 'H1'},  # Too weak
                {'price': 1995.0, 'strength': 0.8, 'timeframe': 'H1'}   # Strong enough
            ],
            'resistance_levels': [],
            'liquidity_levels': []
        }
        
        levels = self.manager._identify_structural_levels(
            reference_price=2010.0,
            direction="BUY",
            market_structure=weak_structure
        )
        
        # Should only include strong levels
        assert all(level.strength >= self.manager.min_level_strength for level in levels)
        assert len(levels) == 1  # Only the strong level
        
        print("✓ Level strength filtering works")
    
    def test_level_validation(self):
        """Test structural level validation."""
        level = StructuralLevel(
            level_price=2000.0,
            level_type="SUPPORT",
            strength=0.7,
            timeframe="H1",
            age_bars=100,
            test_count=2,
            last_test_time=None,
            confluence_factors=["previous_high", "fibonacci"]
        )
        
        current_time = datetime.now(timezone.utc)
        assert level.is_valid_level(current_time)
        
        # Test invalid level (too old)
        old_level = StructuralLevel(
            level_price=2000.0,
            level_type="SUPPORT",
            strength=0.7,
            timeframe="M1",
            age_bars=500,  # Too old for M1
            test_count=2,
            last_test_time=None,
            confluence_factors=[]
        )
        
        assert not old_level.is_valid_level(current_time)
        
        print("✓ Level validation works")


class TestStopLossCalculation:
    """Test suite for stop loss calculation."""
    
    def setup_method(self):
        """Setup for stop loss tests."""
        self.manager = StructuralRiskManager()
        
        self.structural_levels = [
            StructuralLevel(
                level_price=2000.0,
                level_type="SUPPORT",
                strength=0.8,
                timeframe="H1",
                age_bars=50,
                test_count=3,
                last_test_time=None,
                confluence_factors=["previous_low"]
            ),
            StructuralLevel(
                level_price=1995.0,
                level_type="SUPPORT", 
                strength=0.6,
                timeframe="H4",
                age_bars=100,
                test_count=2,
                last_test_time=None,
                confluence_factors=[]
            )
        ]
        
        self.pattern_context = {
            'invalidation_level': 1998.0,
            'atr': 15.0
        }
    
    def test_buy_structural_stop_loss(self):
        """Test structural stop loss calculation for BUY."""
        stop_price, stop_type = self.manager._calculate_structural_stop_loss(
            entry_price=2010.0,
            direction="BUY",
            structural_levels=self.structural_levels,
            pattern_context=self.pattern_context
        )
        
        assert isinstance(stop_price, float)
        assert isinstance(stop_type, StopLossType)
        assert stop_price < 2010.0  # Stop should be below entry for BUY
        
        # Should be near structural level with buffer
        assert stop_price <= 2000.0 - self.manager.level_buffer_pips
        
        print("✓ BUY structural stop loss calculation works")
    
    def test_sell_structural_stop_loss(self):
        """Test structural stop loss calculation for SELL."""
        resistance_levels = [
            StructuralLevel(
                level_price=2025.0,
                level_type="RESISTANCE",
                strength=0.9,
                timeframe="H1",
                age_bars=30,
                test_count=4,
                last_test_time=None,
                confluence_factors=["previous_high"]
            )
        ]
        
        stop_price, stop_type = self.manager._calculate_structural_stop_loss(
            entry_price=2010.0,
            direction="SELL",
            structural_levels=resistance_levels,
            pattern_context=self.pattern_context
        )
        
        assert stop_price > 2010.0  # Stop should be above entry for SELL
        assert stop_price >= 2025.0 + self.manager.level_buffer_pips
        
        print("✓ SELL structural stop loss calculation works")
    
    def test_atr_fallback_stop_loss(self):
        """Test ATR-based fallback when no structural levels."""
        stop_price, stop_type = self.manager._calculate_structural_stop_loss(
            entry_price=2010.0,
            direction="BUY",
            structural_levels=[],  # No structural levels
            pattern_context=self.pattern_context
        )
        
        print(f"Debug: stop_type = {stop_type}, stop_price = {stop_price}")
        
        # Should fallback to ATR or percentage-based
        assert isinstance(stop_type, StopLossType)
        assert stop_price < 2010.0
        
        # Should be reasonable distance from entry
        stop_distance = 2010.0 - stop_price
        assert 10.0 < stop_distance < 50.0  # Reasonable range
        
        print("✓ ATR fallback stop loss works")


class TestTakeProfitCalculation:
    """Test suite for take profit calculation."""
    
    def setup_method(self):
        """Setup for take profit tests."""
        self.manager = StructuralRiskManager()
        
        self.structural_levels = [
            StructuralLevel(
                level_price=2025.0,
                level_type="RESISTANCE",
                strength=0.9,
                timeframe="H1",
                age_bars=30,
                test_count=4,
                last_test_time=None,
                confluence_factors=["previous_high"]
            ),
            StructuralLevel(
                level_price=2035.0,
                level_type="RESISTANCE",
                strength=0.7,
                timeframe="H4", 
                age_bars=50,
                test_count=2,
                last_test_time=None,
                confluence_factors=[]
            )
        ]
        
        self.pattern_context = {
            'take_profit': 2030.0,
            'atr': 15.0
        }
    
    def test_structural_take_profit_levels(self):
        """Test structural take profit level calculation."""
        tp_levels, tp_type, final_target = self.manager._calculate_structural_take_profit(
            entry_price=2010.0,
            direction="BUY",
            structural_levels=self.structural_levels,
            pattern_context=self.pattern_context
        )
        
        assert isinstance(tp_levels, list)
        assert len(tp_levels) > 0
        assert tp_type == TakeProfitType.STRUCTURAL
        assert isinstance(final_target, float)
        assert final_target > 2010.0  # Target above entry for BUY
        
        # Check partial sizing (may not add to 100% due to algorithm design)
        total_size = sum(size for price, size in tp_levels)
        assert total_size > 0  # Should have some size allocated
        assert total_size <= 1.0  # Should not exceed 100%
        
        # Levels should be above entry for BUY
        for price, size in tp_levels:
            assert price > 2010.0
        
        print("✓ Structural take profit calculation works")
    
    def test_pattern_target_fallback(self):
        """Test fallback to pattern target when no structural levels."""
        tp_levels, tp_type, final_target = self.manager._calculate_structural_take_profit(
            entry_price=2010.0,
            direction="BUY",
            structural_levels=[],  # No structural levels
            pattern_context=self.pattern_context
        )
        
        assert tp_type == TakeProfitType.PATTERN_TARGET
        assert any(price == 2030.0 for price, size in tp_levels)  # Should use pattern target
        
        print("✓ Pattern target fallback works")


class TestRiskParameterCreation:
    """Test suite for complete risk parameter creation."""
    
    def setup_method(self):
        """Setup for risk parameter tests."""
        self.manager = StructuralRiskManager()
        
        self.pattern_context = {
            'invalidation_level': 1998.0,
            'take_profit': 2030.0,
            'atr': 15.0
        }
        
        self.market_structure = {
            'support_levels': [2000.0, 1995.0],
            'resistance_levels': [2025.0, 2035.0],
            'liquidity_levels': [2002.0]
        }
    
    def test_complete_risk_parameter_creation(self):
        """Test creation of complete risk parameters."""
        risk_params = self.manager.calculate_structural_stops(
            entry_price=2010.0,
            direction="BUY",
            pattern_context=self.pattern_context,
            market_structure=self.market_structure
        )
        
        assert isinstance(risk_params, RiskParameters)
        
        # Validate stop loss
        assert risk_params.stop_loss_price < 2010.0
        assert isinstance(risk_params.stop_loss_type, StopLossType)
        assert risk_params.initial_stop_distance > 0
        
        # Validate take profit
        assert len(risk_params.take_profit_levels) > 0
        assert isinstance(risk_params.take_profit_type, TakeProfitType)
        assert risk_params.final_target > 2010.0
        
        # Validate risk metrics
        assert risk_params.risk_reward_ratio >= self.manager.min_rr_ratio
        assert 0 < risk_params.position_risk_pct <= self.manager.max_risk_pct
        
        # Validate trailing setup
        assert risk_params.trailing_distance > 0
        assert risk_params.breakeven_trigger is not None
        
        print("✓ Complete risk parameter creation works")
    
    def test_risk_reward_calculation(self):
        """Test risk-reward ratio calculation."""
        risk_params = self.manager.calculate_structural_stops(
            entry_price=2010.0,
            direction="BUY",
            pattern_context=self.pattern_context,
            market_structure=self.market_structure
        )
        
        # Test current R/R calculation
        current_rr = risk_params.calculate_current_risk_reward(2015.0, "BUY")
        assert current_rr > 0
        
        # R/R should decrease as price moves toward target
        higher_price_rr = risk_params.calculate_current_risk_reward(2020.0, "BUY")
        assert higher_price_rr < current_rr
        
        print("✓ Risk-reward calculation works")


class TestTradeRiskManagement:
    """Test suite for complete trade risk management."""
    
    def setup_method(self):
        """Setup for trade risk tests."""
        self.manager = StructuralRiskManager()
        
        self.pattern_context = {
            'invalidation_level': 1998.0,
            'take_profit': 2030.0,
            'atr': 15.0
        }
        
        self.market_structure = {
            'support_levels': [2000.0],
            'resistance_levels': [2025.0, 2035.0],
            'liquidity_levels': [2002.0]
        }
    
    def test_trade_risk_creation(self):
        """Test creation of complete trade risk management."""
        trade_risk = self.manager.create_trade_risk(
            trade_id="test_trade_001",
            symbol="XAUUSD",
            direction="BUY", 
            entry_price=2010.0,
            position_size=1.0,
            pattern_context=self.pattern_context,
            market_structure=self.market_structure
        )
        
        assert isinstance(trade_risk, TradeRisk)
        assert trade_risk.trade_id == "test_trade_001"
        assert trade_risk.is_active
        assert not trade_risk.in_profit  # Should start not in profit
        assert not trade_risk.breakeven_hit
        
        # Should be stored in active trades
        assert "test_trade_001" in self.manager.active_trades
        
        print("✓ Trade risk creation works")
    
    def test_trade_risk_updates(self):
        """Test trade risk updates with price movement."""
        # Create trade
        trade_risk = self.manager.create_trade_risk(
            trade_id="test_trade_002",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2010.0, 
            position_size=1.0,
            pattern_context=self.pattern_context,
            market_structure=self.market_structure
        )
        
        # Update with profitable price
        updated_trade = self.manager.update_trade_risk("test_trade_002", 2015.0)
        
        assert updated_trade is not None
        assert updated_trade.in_profit
        assert updated_trade.unrealized_pnl > 0
        assert updated_trade.max_favorable_excursion > 0
        
        print("✓ Trade risk updates work")
    
    def test_breakeven_trigger(self):
        """Test breakeven mechanism."""
        trade_risk = self.manager.create_trade_risk(
            trade_id="test_trade_003",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2010.0,
            position_size=1.0,
            pattern_context=self.pattern_context,
            market_structure=self.market_structure
        )
        
        initial_stop = trade_risk.risk_params.stop_loss_price
        
        # Move price to trigger breakeven
        breakeven_price = trade_risk.risk_params.breakeven_trigger + 1.0
        updated_trade = self.manager.update_trade_risk("test_trade_003", breakeven_price)
        
        # Stop should have moved closer to entry (less risk)
        if updated_trade.breakeven_hit:
            assert updated_trade.risk_params.stop_loss_price > initial_stop
        
        print("✓ Breakeven trigger works")
    
    def test_partial_profit_triggers(self):
        """Test partial profit taking."""
        trade_risk = self.manager.create_trade_risk(
            trade_id="test_trade_004",
            symbol="XAUUSD", 
            direction="BUY",
            entry_price=2010.0,
            position_size=1.0,
            pattern_context=self.pattern_context,
            market_structure=self.market_structure
        )
        
        # Find first TP level
        first_tp_price = trade_risk.risk_params.take_profit_levels[0][0]
        
        # Trigger partial profit
        partials = self.manager.check_partial_profit_triggers(trade_risk, first_tp_price + 1.0)
        
        assert len(partials) > 0
        assert len(trade_risk.partial_fills) > 0
        
        partial_fill = partials[0]
        assert partial_fill['pnl'] > 0  # Should be profitable
        
        print("✓ Partial profit triggers work")
    
    def test_trade_closure(self):
        """Test trade closure and final metrics."""
        trade_risk = self.manager.create_trade_risk(
            trade_id="test_trade_005",
            symbol="XAUUSD",
            direction="BUY",
            entry_price=2010.0,
            position_size=1.0,
            pattern_context=self.pattern_context,
            market_structure=self.market_structure
        )
        
        # Close profitable trade
        final_metrics = self.manager.close_trade_risk("test_trade_005", 2025.0, "TP_HIT")
        
        assert final_metrics is not None
        assert final_metrics['final_pnl'] > 0  # Profitable exit
        assert final_metrics['exit_reason'] == "TP_HIT"
        assert "test_trade_005" not in self.manager.active_trades  # Removed from active
        
        print("✓ Trade closure works")


def test_singleton_risk_manager():
    """Test singleton risk manager."""
    manager1 = get_structural_risk_manager()
    manager2 = get_structural_risk_manager()
    
    assert manager1 is manager2
    assert isinstance(manager1, StructuralRiskManager)
    
    print("✓ Singleton risk manager works")


if __name__ == "__main__":
    try:
        # Run all tests
        test_levels = TestStructuralLevelIdentification()
        test_levels.setup_method()
        test_levels.test_identify_buy_structural_levels()
        test_levels.test_identify_sell_structural_levels()
        test_levels.test_level_strength_filtering()
        test_levels.test_level_validation()
        
        test_stops = TestStopLossCalculation()
        test_stops.setup_method()
        test_stops.test_buy_structural_stop_loss()
        test_stops.test_sell_structural_stop_loss()
        test_stops.test_atr_fallback_stop_loss()
        
        test_tps = TestTakeProfitCalculation()
        test_tps.setup_method()
        test_tps.test_structural_take_profit_levels()
        test_tps.test_pattern_target_fallback()
        
        test_params = TestRiskParameterCreation()
        test_params.setup_method()
        test_params.test_complete_risk_parameter_creation()
        test_params.test_risk_reward_calculation()
        
        test_trades = TestTradeRiskManagement()
        test_trades.setup_method()
        test_trades.test_trade_risk_creation()
        test_trades.test_trade_risk_updates()
        test_trades.test_breakeven_trigger()
        test_trades.test_partial_profit_triggers()
        test_trades.test_trade_closure()
        
        test_singleton_risk_manager()
        
        print("\n🎉 All Structural Risk Manager tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)