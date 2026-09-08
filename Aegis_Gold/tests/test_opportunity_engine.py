"""
===========================================================================
AEGIS GOLD — Opportunity Engine Test Suite (Phase L)
===========================================================================

Tests for comprehensive opportunity evaluation system.

CRITICAL TEST COVERAGE:
-----------------------
1. Opportunity metrics calculation (quality, EV, risk)
2. Opportunity grading and tradeability assessment  
3. Execution parameter calculation
4. Historical edge integration
5. Real-time opportunity updates
6. Opportunity ranking and prioritization

===========================================================================
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.opportunity_engine import (
    OpportunityEngine,
    OpportunityMetrics,
    OpportunityAssessment, 
    OpportunityGrade,
    get_opportunity_engine
)


class TestOpportunityMetrics:
    """Test suite for opportunity metrics calculation."""
    
    def setup_method(self):
        """Setup for each test."""
        self.engine = OpportunityEngine()
        self.sample_pattern_context = {
            'symbol': 'XAUUSD',
            'pattern_type': 'BOS_BULLISH',
            'direction': 'BUY',
            'scale': 'MEDIUM',
            'current_price': 2010.0,
            'entry_price': 2011.0,
            'stop_loss': 2000.0,
            'take_profit': 2035.0,
            'structure_strength': 0.8,
            'mtf_alignment': 0.75,
            'regime': 'TRENDING_UP',
            'ob_present': True,
            'liquidity_swept': True
        }
        
        self.sample_market_snapshot = Mock()
        self.sample_market_snapshot.current_price = 2010.0
        self.sample_market_snapshot.session = 'LONDON'
        self.sample_market_snapshot.volatility_level = 'NORMAL'
        self.sample_market_snapshot.news_risk_level = 'LOW'
    
    def test_calculate_opportunity_metrics(self):
        """Test comprehensive opportunity metrics calculation."""
        metrics = self.engine._calculate_opportunity_metrics(
            self.sample_pattern_context,
            self.sample_market_snapshot
        )
        
        # Validate basic calculations
        assert isinstance(metrics, OpportunityMetrics)
        assert 0 <= metrics.overall_quality_score <= 100
        assert metrics.total_expected_move == 24.0  # 2035 - 2011
        assert metrics.remaining_move == 25.0       # 2035 - 2010
        assert metrics.max_risk_points == 11.0      # 2011 - 2000
        assert metrics.risk_reward_ratio == 24.0/11.0  # ~2.18
        
        # Validate quality components
        assert 0 <= metrics.structure_quality <= 100
        assert 0 <= metrics.confluence_quality <= 100
        assert 0 <= metrics.timing_quality <= 100
        assert 0 <= metrics.risk_quality <= 100
        
        # Validate probabilities
        assert 0 <= metrics.win_probability <= 1.0
        assert 0 <= metrics.kelly_fraction <= 1.0
        
        print("✓ Opportunity metrics calculation works")
    
    def test_structure_quality_assessment(self):
        """Test pattern structure quality scoring.""" 
        # High quality pattern
        high_quality_score = self.engine._assess_structure_quality(self.sample_pattern_context)
        assert high_quality_score > 70, f"High quality pattern scored {high_quality_score}"
        
        # Low quality pattern
        low_quality_context = self.sample_pattern_context.copy()
        low_quality_context.update({
            'pattern_type': 'UNKNOWN',
            'structure_strength': 0.2,
            'ob_present': False,
            'liquidity_swept': False
        })
        
        low_quality_score = self.engine._assess_structure_quality(low_quality_context)
        assert low_quality_score < high_quality_score
        assert low_quality_score >= 0
        
        print("✓ Structure quality assessment works")
    
    def test_confluence_quality_assessment(self):
        """Test multi-timeframe confluence scoring."""
        confluence_score = self.engine._assess_confluence_quality(
            self.sample_pattern_context, 
            self.sample_market_snapshot
        )
        
        assert 0 <= confluence_score <= 100
        assert confluence_score > 50  # Should be good with high MTF alignment
        
        # Test with poor confluence
        poor_confluence_context = self.sample_pattern_context.copy()
        poor_confluence_context.update({
            'mtf_alignment': 0.2,
            'htf_bias': 'NEUTRAL',
            'regime': 'RANGING'  # Doesn't match BUY direction
        })
        
        poor_score = self.engine._assess_confluence_quality(
            poor_confluence_context,
            self.sample_market_snapshot
        )
        
        assert poor_score < confluence_score
        print("✓ Confluence quality assessment works")
    
    def test_risk_quality_assessment(self):
        """Test risk/reward profile scoring."""
        # Excellent R:R
        excellent_score = self.engine._assess_risk_quality(3.0, 50.0, 1.5)
        assert excellent_score > 80
        
        # Poor R:R 
        poor_score = self.engine._assess_risk_quality(0.8, 200.0, -0.5)
        assert poor_score < 50
        
        # Medium R:R
        medium_score = self.engine._assess_risk_quality(2.0, 75.0, 0.8)
        assert poor_score < medium_score < excellent_score
        
        print("✓ Risk quality assessment works")


class TestOpportunityAssessment:
    """Test suite for complete opportunity assessment."""
    
    def setup_method(self):
        """Setup for assessment tests."""
        self.engine = OpportunityEngine()
        
        # Excellent opportunity setup
        self.excellent_context = {
            'symbol': 'XAUUSD',
            'pattern_type': 'BOS_BULLISH',
            'direction': 'BUY',
            'scale': 'MEDIUM',
            'current_price': 2010.0,
            'entry_price': 2012.0,
            'stop_loss': 2000.0,
            'take_profit': 2040.0,
            'structure_strength': 0.9,
            'mtf_alignment': 0.85,
            'regime': 'TRENDING_UP',
            'ob_present': True,
            'liquidity_swept': True,
            'detection_time': datetime.now(timezone.utc).isoformat()
        }
        
        self.mock_snapshot = Mock()
        self.mock_snapshot.current_price = 2010.0
        self.mock_snapshot.session = 'LONDON'
        self.mock_snapshot.volatility_level = 'NORMAL'
        self.mock_snapshot.news_risk_level = 'LOW'
    
    def test_excellent_opportunity_assessment(self):
        """Test assessment of high-quality opportunity."""
        assessment = self.engine.evaluate_opportunity(
            self.excellent_context,
            self.mock_snapshot
        )
        
        assert isinstance(assessment, OpportunityAssessment)
        assert assessment.grade in [OpportunityGrade.EXCELLENT, OpportunityGrade.GOOD]
        assert assessment.is_tradeable
        assert len(assessment.rejection_reasons) == 0
        assert assessment.metrics.overall_quality_score > 70
        assert assessment.metrics.risk_reward_ratio > 2.0
        
        print("✓ Excellent opportunity assessment works")
    
    def test_poor_opportunity_rejection(self):
        """Test rejection of poor quality opportunity."""
        poor_context = {
            'symbol': 'XAUUSD', 
            'pattern_type': 'UNKNOWN',
            'direction': 'BUY',
            'scale': 'SMALL',
            'current_price': 2010.0,
            'entry_price': 2011.0,
            'stop_loss': 2009.0,  # Tiny stop
            'take_profit': 2012.0,  # Tiny target, poor R:R
            'structure_strength': 0.2,
            'mtf_alignment': 0.1,
            'regime': 'RANGING',
            'ob_present': False,
            'liquidity_swept': False
        }
        
        assessment = self.engine.evaluate_opportunity(poor_context, self.mock_snapshot)
        
        assert assessment.grade in [OpportunityGrade.POOR, OpportunityGrade.REJECTED]
        assert not assessment.is_tradeable
        assert len(assessment.rejection_reasons) > 0
        
        print("✓ Poor opportunity rejection works")
    
    def test_execution_parameters(self):
        """Test calculation of execution parameters."""
        assessment = self.engine.evaluate_opportunity(
            self.excellent_context,
            self.mock_snapshot
        )
        
        assert assessment.optimal_entry_price == 2012.0
        assert assessment.stop_loss_price == 2000.0
        assert assessment.take_profit_price == 2040.0
        assert assessment.entry_window_start < assessment.optimal_entry_price
        assert assessment.entry_window_end > assessment.optimal_entry_price
        
        print("✓ Execution parameters calculation works")
    
    def test_opportunity_expiration(self):
        """Test opportunity expiration calculation."""
        assessment = self.engine.evaluate_opportunity(
            self.excellent_context,
            self.mock_snapshot
        )
        
        expiration = datetime.fromisoformat(assessment.expiration_time.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        
        assert expiration > now
        assert (expiration - now).total_seconds() > 300  # At least 5 minutes
        assert (expiration - now).total_seconds() < 7200  # Less than 2 hours
        
        print("✓ Opportunity expiration works")


class TestOpportunityUpdates:
    """Test suite for real-time opportunity updates."""
    
    def setup_method(self):
        """Setup for update tests."""
        self.engine = OpportunityEngine()
        
        # Create initial opportunity
        context = {
            'symbol': 'XAUUSD',
            'pattern_type': 'BOS_BULLISH', 
            'direction': 'BUY',
            'scale': 'MEDIUM',
            'current_price': 2010.0,
            'entry_price': 2012.0,
            'stop_loss': 2000.0,
            'take_profit': 2040.0,
            'structure_strength': 0.8,
            'mtf_alignment': 0.7,
            'regime': 'TRENDING_UP'
        }
        
        mock_snapshot = Mock()
        mock_snapshot.current_price = 2010.0
        mock_snapshot.session = 'LONDON'
        mock_snapshot.volatility_level = 'NORMAL'
        mock_snapshot.news_risk_level = 'LOW'
        
        self.assessment = self.engine.evaluate_opportunity(context, mock_snapshot)
        self.opportunity_id = self.assessment.opportunity_id
    
    def test_opportunity_update(self):
        """Test updating opportunity with price movement."""
        # Price moves toward target
        updated = self.engine.update_opportunity(self.opportunity_id, 2025.0)
        
        assert updated is not None
        assert updated.metrics.remaining_move < self.assessment.metrics.remaining_move
        assert updated.metrics.move_completion_pct > self.assessment.metrics.move_completion_pct
        
        print("✓ Opportunity update works")
    
    def test_opportunity_completion_tracking(self):
        """Test tracking as opportunity nears completion."""
        # Price near target
        updated = self.engine.update_opportunity(self.opportunity_id, 2038.0)
        
        assert updated.metrics.move_completion_pct > 90
        assert updated.metrics.remaining_move < 5.0
        
        print("✓ Opportunity completion tracking works")


class TestOpportunityRanking:
    """Test suite for opportunity ranking and comparison."""
    
    def setup_method(self):
        """Setup for ranking tests."""
        self.engine = OpportunityEngine()
    
    def test_opportunity_ranking(self):
        """Test ranking of multiple opportunities."""
        mock_snapshot = Mock()
        mock_snapshot.current_price = 2010.0
        mock_snapshot.session = 'LONDON'
        mock_snapshot.volatility_level = 'NORMAL'
        mock_snapshot.news_risk_level = 'LOW'
        
        # Create opportunities of different quality
        contexts = [
            {  # Excellent opportunity
                'symbol': 'XAUUSD', 'pattern_type': 'BOS_BULLISH', 'direction': 'BUY',
                'scale': 'MEDIUM', 'current_price': 2010.0, 'entry_price': 2012.0,
                'stop_loss': 2000.0, 'take_profit': 2040.0, 'structure_strength': 0.9,
                'mtf_alignment': 0.9, 'regime': 'TRENDING_UP', 'ob_present': True
            },
            {  # Good opportunity
                'symbol': 'XAUUSD', 'pattern_type': 'CHOCH_BULLISH', 'direction': 'BUY',
                'scale': 'MEDIUM', 'current_price': 2010.0, 'entry_price': 2013.0,
                'stop_loss': 2005.0, 'take_profit': 2030.0, 'structure_strength': 0.7,
                'mtf_alignment': 0.6, 'regime': 'TRENDING_UP', 'ob_present': False
            },
            {  # Poor opportunity  
                'symbol': 'XAUUSD', 'pattern_type': 'UNKNOWN', 'direction': 'BUY',
                'scale': 'SMALL', 'current_price': 2010.0, 'entry_price': 2011.0,
                'stop_loss': 2008.0, 'take_profit': 2014.0, 'structure_strength': 0.3,
                'mtf_alignment': 0.2, 'regime': 'RANGING', 'ob_present': False
            }
        ]
        
        opportunities = []
        for context in contexts:
            opp = self.engine.evaluate_opportunity(context, mock_snapshot)
            opportunities.append(opp)
        
        # Rank opportunities
        ranked = self.engine.rank_opportunities(opportunities)
        
        # Verify ranking order (best first)
        assert len(ranked) == 3
        assert ranked[0].metrics.overall_quality_score >= ranked[1].metrics.overall_quality_score
        assert ranked[1].metrics.overall_quality_score >= ranked[2].metrics.overall_quality_score
        
        # Best opportunity should be tradeable
        if any(opp.is_tradeable for opp in ranked):
            assert ranked[0].is_tradeable
        
        print("✓ Opportunity ranking works")
    
    def test_opportunity_summary(self):
        """Test opportunity summary generation.""" 
        # Start with empty engine
        summary = self.engine.get_opportunity_summary()
        assert summary["active_count"] == 0
        assert summary["tradeable_count"] == 0
        
        # Add some opportunities
        mock_snapshot = Mock()
        mock_snapshot.current_price = 2010.0
        mock_snapshot.session = 'LONDON'
        mock_snapshot.volatility_level = 'NORMAL'
        mock_snapshot.news_risk_level = 'LOW'
        
        context = {
            'symbol': 'XAUUSD', 'pattern_type': 'BOS_BULLISH', 'direction': 'BUY',
            'scale': 'MEDIUM', 'current_price': 2010.0, 'entry_price': 2012.0,
            'stop_loss': 2000.0, 'take_profit': 2040.0, 'structure_strength': 0.8,
            'mtf_alignment': 0.75, 'regime': 'TRENDING_UP'
        }
        
        self.engine.evaluate_opportunity(context, mock_snapshot)
        
        summary = self.engine.get_opportunity_summary()
        assert summary["active_count"] > 0
        assert "grading_distribution" in summary
        assert isinstance(summary["avg_quality"], float)
        
        print("✓ Opportunity summary works")


def test_singleton_opportunity_engine():
    """Test singleton opportunity engine."""
    engine1 = get_opportunity_engine()
    engine2 = get_opportunity_engine()
    
    assert engine1 is engine2
    assert isinstance(engine1, OpportunityEngine)
    
    print("✓ Singleton opportunity engine works")


if __name__ == "__main__":
    try:
        # Run all tests
        test_metrics = TestOpportunityMetrics()
        test_metrics.setup_method()
        test_metrics.test_calculate_opportunity_metrics()
        test_metrics.test_structure_quality_assessment()
        test_metrics.test_confluence_quality_assessment()
        test_metrics.test_risk_quality_assessment()
        
        test_assessment = TestOpportunityAssessment()
        test_assessment.setup_method()
        test_assessment.test_excellent_opportunity_assessment()
        test_assessment.test_poor_opportunity_rejection()
        test_assessment.test_execution_parameters()
        test_assessment.test_opportunity_expiration()
        
        test_updates = TestOpportunityUpdates()
        test_updates.setup_method()
        test_updates.test_opportunity_update()
        test_updates.test_opportunity_completion_tracking()
        
        test_ranking = TestOpportunityRanking()
        test_ranking.setup_method()
        test_ranking.test_opportunity_ranking()
        test_ranking.test_opportunity_summary()
        
        test_singleton_opportunity_engine()
        
        print("\n🎉 All Opportunity Engine tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)