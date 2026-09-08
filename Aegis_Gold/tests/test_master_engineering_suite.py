"""
Aegis Gold — Master Engineering & Validation Test Suite
Tests zero-confidence trading, $3–$4 economic validation, anti-duplicate protection,
circuit breakers, and canonical TradeAuthorization contract enforcements.
"""

import pytest
import time
from unittest.mock import MagicMock

from brain.canonical_types import (
    PatternCandidate, EntryOpportunity, NewsRegimeState, QuantPlan, TradeAuthorization
)
from brain.quant_economic_validator import QuantEconomicValidator
from brain.anti_duplicate_engine import AntiDuplicateEngine
from brain.opportunity_pipeline import OpportunityPipeline


def test_1_no_valid_pattern_returns_wait():
    """Test 1: High confidence or noise without valid pattern MUST return WAIT."""
    pipeline = OpportunityPipeline()
    risk_mock = MagicMock()
    risk_mock.is_daily_loss_limit_reached.return_value = False
    
    # Empty / neutral candle array
    candles_m5 = [{"open": 4000.0, "high": 4000.5, "low": 3999.5, "close": 4000.0} for _ in range(30)]
    
    auth, code = pipeline.evaluate_opportunity(
        symbol="XAUUSD",
        candles_m5=candles_m5,
        candles_m1=candles_m5,
        ticks=[],
        account={"equity": 5000.0},
        spread_pts=20.0,
        point=0.01,
        session="LONDON",
        risk_mgr=risk_mock
    )
    
    assert auth is None
    assert code == "NO_VALID_PATTERN"


def test_2_quant_economic_validator_target_feasibility():
    """Test 2: Validates $3.00–$4.00 profit feasibility against ATR and spread."""
    validator = QuantEconomicValidator()
    
    pattern = PatternCandidate(
        pattern_id="TEST_OB_01",
        engine_source="SMC",
        timeframe="M5",
        direction="BUY",
        pattern_type="ORDER_BLOCK",
        structure_context="TREND_CONTINUATION",
        invalidation_level=4200.0,
        entry_zone_low=4200.0,
        entry_zone_high=4205.0
    )
    
    opp = EntryOpportunity(
        opportunity_id="OPP_TEST_01",
        pattern=pattern,
        symbol="XAUUSD",
        direction="BUY",
        entry_price=4205.0,
        structural_sl_price=4200.0,
        structural_sl_points=50,
        trigger_type="M1_CHoCH"
    )
    
    news_clear = NewsRegimeState(regime="NORMAL", trading_allowed=True)
    
    # Case A: Good ATR (100 pts) -> Feasible
    plan_good = validator.validate_opportunity(
        opportunity=opp,
        account_equity=5000.0,
        spread_pts=15.0,
        point=0.01,
        atr_points=100.0,
        news_state=news_clear
    )
    assert plan_good.target_is_economically_realistic is True
    assert plan_good.target_usd == 3.50
    assert plan_good.lot_size >= 0.01
    
    # Case B: Tiny ATR (10 pts) -> Infeasible (required move > 1.8 * ATR)
    plan_bad_atr = validator.validate_opportunity(
        opportunity=opp,
        account_equity=5000.0,
        spread_pts=15.0,
        point=0.01,
        atr_points=10.0,
        news_state=news_clear
    )
    assert plan_bad_atr.target_is_economically_realistic is False
    assert "exceeds realistic ATR" in plan_bad_atr.rejection_reason


def test_3_anti_duplicate_engine_blocks_same_zone():
    """Test 3: Anti-duplicate engine blocks repetitive trades in identical zone."""
    anti_dup = AntiDuplicateEngine(zone_tolerance_points=30.0, expiry_seconds=60.0)
    
    pattern = PatternCandidate(
        pattern_id="PAT_01",
        engine_source="KRNOS",
        timeframe="M5",
        direction="BUY",
        pattern_type="EXPANSION",
        structure_context="TREND",
        invalidation_level=4200.0,
        entry_zone_low=4200.0,
        entry_zone_high=4210.0
    )
    
    opp1 = EntryOpportunity(
        opportunity_id="OPP_1",
        pattern=pattern,
        symbol="XAUUSD",
        direction="BUY",
        entry_price=4210.00,
        structural_sl_price=4200.0,
        structural_sl_points=100,
        trigger_type="M1_SWEEP"
    )
    
    # First opportunity is NOT duplicate
    assert anti_dup.is_duplicate(opp1, point=0.01) is False
    anti_dup.record_authorization(opp1)
    
    # Second opportunity in same price zone (4210.10 vs 4210.00 = 10 pts < 30 pts) is DUPLICATE
    opp2 = EntryOpportunity(
        opportunity_id="OPP_2",
        pattern=PatternCandidate(
            pattern_id="PAT_02", engine_source="KRNOS", timeframe="M5", direction="BUY",
            pattern_type="EXPANSION", structure_context="TREND", invalidation_level=4200.0,
            entry_zone_low=4200.0, entry_zone_high=4210.0
        ),
        symbol="XAUUSD",
        direction="BUY",
        entry_price=4210.10,
        structural_sl_price=4200.0,
        structural_sl_points=100,
        trigger_type="M1_SWEEP"
    )
    assert anti_dup.is_duplicate(opp2, point=0.01) is True


def test_4_daily_loss_circuit_breaker():
    """Test 4: Circuit breaker blocks authorization when daily loss limit is hit."""
    pipeline = OpportunityPipeline()
    risk_mock = MagicMock()
    risk_mock.is_daily_loss_limit_reached.return_value = True
    
    from brain.smc_engine import BigPatternResult
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "brain.smc_engine.detect_big_pattern",
            lambda **kwargs: BigPatternResult(
                bias="bullish",
                pattern_type="BOS_BULLISH",
                confidence=0.80,
                invalidation_level=4206.50
            )
        )
        mp.setattr("brain.news_filter.NewsFilter.is_news_clear", lambda self, **kwargs: True)
        
        candles = [{"open": 4205.0, "high": 4210.0, "low": 4204.0, "close": 4208.0} for _ in range(30)]
        
        auth, code = pipeline.evaluate_opportunity(
            symbol="XAUUSD",
            candles_m5=candles,
            candles_m1=candles,
            ticks=[],
            account={"equity": 4500.0},
            spread_pts=15.0,
            point=0.01,
            session="LONDON",
            risk_mgr=risk_mock
        )
        
        assert auth is None
        assert code == "DAILY_LOSS_LIMIT_REACHED"


def test_5_full_opportunity_authorization_contract():
    """Test 5: Full valid setup passes all gates and produces TradeAuthorization contract."""
    pipeline = OpportunityPipeline()
    risk_mock = MagicMock()
    risk_mock.is_daily_loss_limit_reached.return_value = False
    
    from brain.smc_engine import BigPatternResult, SmallPatternResult
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "brain.smc_engine.detect_big_pattern",
            lambda **kwargs: BigPatternResult(
                bias="bullish",
                pattern_type="BOS_BULLISH",
                confidence=0.85,
                invalidation_level=4303.50
            )
        )
        mp.setattr(
            "brain.smc_engine.detect_small_pattern",
            lambda **kwargs: SmallPatternResult(
                pattern_type="LIQUIDITY_SWEEP_REVERSAL",
                confidence=0.80,
                invalidation_level=4303.50,
                entry_price=4305.0,
                direction="BUY"
            )
        )
        mp.setattr("brain.news_filter.NewsFilter.is_news_clear", lambda self, **kwargs: True)
        
        candles = [{"open": 4304.0, "high": 4307.0, "low": 4303.0, "close": 4305.0} for _ in range(30)]
        
        auth, code = pipeline.evaluate_opportunity(
            symbol="XAUUSD",
            candles_m5=candles,
            candles_m1=candles,
            ticks=[],
            account={"equity": 5000.0},
            spread_pts=15.0,
            point=0.01,
            session="LONDON",
            risk_mgr=risk_mock
        )
        
        assert auth is not None
        assert code == "AUTHORIZED"
        assert auth.authorized is True
        assert auth.direction == "BUY"
        assert auth.target_usd == 3.50
        assert auth.lot >= 0.01
        assert auth.tp_points > 0
        assert auth.sl_points > 0
        assert auth.stop_loss < auth.entry_price < auth.take_profit


def test_6_dynamic_broker_aware_position_sizing():
    """Test 6: Verifies dynamic calculation of lot sizes based on broker tick specs."""
    validator = QuantEconomicValidator()
    
    # Account 1: $10,000 equity, 150 pt SL, $10 max risk -> 10 / (150 * 1.0) = 0.066 -> 0.06 lot
    lot1 = validator.calculate_position_size(
        account_equity=10000.0,
        structural_sl_points=150,
        symbol="XAUUSD",
        point=0.01,
        max_risk_usd=10.0,
        volume_min=0.01,
        volume_max=5.0,
        volume_step=0.01
    )
    assert lot1 == 0.06

    # Account 2: Strict volume step 0.05
    lot2 = validator.calculate_position_size(
        account_equity=10000.0,
        structural_sl_points=100,
        symbol="XAUUSD",
        point=0.01,
        max_risk_usd=10.0,
        volume_min=0.05,
        volume_max=5.0,
        volume_step=0.05
    )
    assert lot2 == 0.10


def test_7_watchdog_cannot_override_risk_halt():
    """Test 7: Proves that process watchdog resets cannot override a daily risk shutdown."""
    from modules.risk_manager import RiskManager
    
    class MockGateway:
        symbols_data = {"XAUUSD": {"point": 0.01}}
        def get_account_info(self):
            return {"equity": 4400.0, "balance": 5000.0} # $600 loss (> $500 limit)

    gw = MockGateway()
    risk = RiskManager(gateway=gw)
    risk.init_daily(equity=5000.0) # Started day at $5000

    # Risk manager evaluates daily loss limit
    is_halted = risk.is_daily_loss_limit_reached(current_equity=4400.0)
    assert is_halted is True
    assert risk.stop_today is True

    # Even if watchdog restarts or calls check_daily_loss, it remains blocked
    assert risk.check_daily_loss(current_equity=4400.0) is False


if __name__ == "__main__":
    pytest.main(["-v", __file__])
