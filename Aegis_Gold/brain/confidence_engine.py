"""
═══════════════════════════════════════════════════════════════════════════════
🎯 AEGIS ADVANCED CONFIDENCE SCORING ENGINE - Signal Aggregation Core
═══════════════════════════════════════════════════════════════════════════════

PURPOSE:
--------
Aggregate signals from ALL analysis engines into a single comprehensive confidence
score that represents the TRUE probability of trade success.

PHILOSOPHY:
-----------
"One indicator is an opinion. Multiple confirming indicators are evidence."

Confidence is not a single number from one analysis method. True confidence comes
from CONVERGENCE across multiple independent analysis frameworks. When SMC,
multi-timeframe, statistical models, and ML ensemble ALL agree - that's confidence.

CONFIDENCE COMPONENTS (12 SOURCES):
-----------------------------------
1. Market Structure (regime, trend, volatility)        Weight: 10%
2. Smart Money Concepts (OB, BOS, liquidity, FVG)      Weight: 12%
3. Multi-Timeframe Alignment (9 TFs)                   Weight: 15%
4. Statistical Analysis (Bayesian, Hurst, entropy)     Weight: 10%
5. Machine Learning Ensemble (4 models)                Weight: 15%
6. Liquidity Analysis                                  Weight: 8%
7. Momentum & Trend                                    Weight: 8%
8. Volatility & Risk                                   Weight: 5%
9. Spread & Execution Quality                          Weight: 3%
10. Session Timing                                     Weight: 4%
11. News Filter                                        Weight: 5%
12. Historical Performance (similar setups)            Weight: 5%

CONFIDENCE LEVELS:
------------------
90-100%: EXCEPTIONAL - Rare perfect setups. Take maximum position.
75-89%:  EXCELLENT - Strong multi-engine agreement. High confidence trade.
60-74%:  GOOD - Solid setup with decent confirmation.
50-59%:  FAIR - Marginal setup. Consider only in favorable conditions.
40-49%:  POOR - Weak setup. High probability of failure.
0-39%:   TERRIBLE - Do not trade. Clear warning signals.

VETO SIGNALS (Instant Confidence = 0):
---------------------------------------
- News event within 10 minutes (high impact)
- Spread > 2x normal
- Multi-timeframe divergence on H4
- Extreme volatility (ATR > 3%)
- Recent losing streak > 5
- Account drawdown > 10%

═══════════════════════════════════════════════════════════════════════════════
"""

import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime
import logging

logger = logging.getLogger("ConfidenceEngine")


@dataclass
class ConfidenceBreakdown:
    """Detailed breakdown of confidence components."""
    
    # Component scores (0-100)
    structure_score: int
    smc_score: int
    mtf_score: int
    statistical_score: int
    ml_score: int
    liquidity_score: int
    momentum_score: int
    volatility_score: int
    spread_score: int
    session_score: int
    news_score: int
    history_score: int
    
    # Weighted total
    total_confidence: int  # 0-100
    
    # Qualitative assessment
    confidence_level: str  # "EXCEPTIONAL", "EXCELLENT", "GOOD", "FAIR", "POOR", "TERRIBLE"
    trade_recommendation: str  # "TRADE", "CONSIDER", "AVOID"
    
    # Signal convergence
    signal_agreement: float  # 0.0-1.0 (how much all signals agree)
    conflicting_signals: List[str]  # List of conflicting indicators
    
    # Veto status
    veto_active: bool
    veto_reason: Optional[str]
    
    # Risk assessment
    risk_level: str  # "LOW", "MODERATE", "HIGH", "EXTREME"
    max_suggested_lot: float
    
    # Explanation
    primary_strengths: List[str]
    primary_weaknesses: List[str]
    summary: str


class ConfidenceEngine:
    """
    Advanced confidence scoring engine that aggregates all analysis sources.
    """
    
    # Component weights (must sum to 1.0)
    WEIGHTS = {
        'structure': 0.10,
        'smc': 0.12,
        'mtf': 0.15,
        'statistical': 0.10,
        'ml': 0.15,
        'liquidity': 0.08,
        'momentum': 0.08,
        'volatility': 0.05,
        'spread': 0.03,
        'session': 0.04,
        'news': 0.05,
        'history': 0.05
    }
    
    def __init__(self):
        logger.info("[CONF] Confidence Engine initialized")
    
    def calculate_confidence(
        self,
        symbol: str,
        structure_data: Dict,
        smc_data: Optional[Dict] = None,
        mtf_data: Optional[Dict] = None,
        statistical_data: Optional[Dict] = None,
        ml_data: Optional[Dict] = None,
        market_data: Optional[Dict] = None,
        account_data: Optional[Dict] = None,
        historical_data: Optional[Dict] = None
    ) -> ConfidenceBreakdown:
        """
        Calculate comprehensive confidence score from all available data sources.
        
        Args:
            symbol: Trading symbol (XAUUSD, EURUSD)
            structure_data: Market structure analysis (regime, trend, etc.)
            smc_data: Smart Money Concepts analysis
            mtf_data: Multi-timeframe analysis result
            statistical_data: Statistical engine result
            ml_data: ML ensemble prediction
            market_data: Current market conditions (spread, volatility, session)
            account_data: Account state (balance, drawdown, recent performance)
            historical_data: Similar historical trade outcomes
            
        Returns:
            ConfidenceBreakdown with detailed scoring and recommendation
        """
        try:
            # Check for veto conditions FIRST
            veto_active, veto_reason = self._check_veto_conditions(
                market_data, account_data, mtf_data
            )
            
            if veto_active:
                return self._create_veto_result(veto_reason)
            
            # Calculate individual component scores
            structure_score = self._score_structure(structure_data)
            smc_score = self._score_smc(smc_data)
            mtf_score = self._score_mtf(mtf_data)
            statistical_score = self._score_statistical(statistical_data)
            ml_score = self._score_ml(ml_data)
            liquidity_score = self._score_liquidity(market_data, smc_data)
            momentum_score = self._score_momentum(structure_data, mtf_data)
            volatility_score = self._score_volatility(market_data, statistical_data)
            spread_score = self._score_spread(market_data, symbol)
            session_score = self._score_session(market_data)
            news_score = self._score_news(market_data)
            history_score = self._score_history(historical_data)
            
            # Weighted total confidence
            total_confidence = int(
                structure_score * self.WEIGHTS['structure'] +
                smc_score * self.WEIGHTS['smc'] +
                mtf_score * self.WEIGHTS['mtf'] +
                statistical_score * self.WEIGHTS['statistical'] +
                ml_score * self.WEIGHTS['ml'] +
                liquidity_score * self.WEIGHTS['liquidity'] +
                momentum_score * self.WEIGHTS['momentum'] +
                volatility_score * self.WEIGHTS['volatility'] +
                spread_score * self.WEIGHTS['spread'] +
                session_score * self.WEIGHTS['session'] +
                news_score * self.WEIGHTS['news'] +
                history_score * self.WEIGHTS['history']
            )
            
            # Signal agreement (variance of scores)
            scores = [structure_score, smc_score, mtf_score, statistical_score, ml_score,
                     liquidity_score, momentum_score, volatility_score]
            signal_agreement = 1.0 - (np.std(scores) / 50.0)  # Normalize to 0-1
            signal_agreement = max(0.0, min(1.0, signal_agreement))
            
            # Detect conflicting signals
            conflicting = self._detect_conflicts(
                structure_score, smc_score, mtf_score, statistical_score, ml_score
            )
            
            # Qualitative assessment
            confidence_level = self._assess_confidence_level(total_confidence)
            trade_recommendation = self._generate_recommendation(total_confidence, signal_agreement, conflicting)
            
            # Risk assessment
            risk_level = self._assess_risk(volatility_score, spread_score, mtf_data)
            max_suggested_lot = self._calculate_max_lot(total_confidence, risk_level, account_data)
            
            # Strengths and weaknesses
            strengths = self._identify_strengths(
                structure_score, smc_score, mtf_score, statistical_score, ml_score
            )
            weaknesses = self._identify_weaknesses(
                structure_score, smc_score, mtf_score, statistical_score, ml_score
            )
            
            # Summary
            summary = self._generate_summary(
                total_confidence, confidence_level, signal_agreement, strengths, weaknesses
            )
            
            result = ConfidenceBreakdown(
                structure_score=structure_score,
                smc_score=smc_score,
                mtf_score=mtf_score,
                statistical_score=statistical_score,
                ml_score=ml_score,
                liquidity_score=liquidity_score,
                momentum_score=momentum_score,
                volatility_score=volatility_score,
                spread_score=spread_score,
                session_score=session_score,
                news_score=news_score,
                history_score=history_score,
                total_confidence=total_confidence,
                confidence_level=confidence_level,
                trade_recommendation=trade_recommendation,
                signal_agreement=signal_agreement,
                conflicting_signals=conflicting,
                veto_active=False,
                veto_reason=None,
                risk_level=risk_level,
                max_suggested_lot=max_suggested_lot,
                primary_strengths=strengths,
                primary_weaknesses=weaknesses,
                summary=summary
            )
            
            logger.info(f"✅ Confidence: {total_confidence}% ({confidence_level}) | Agreement: {signal_agreement:.2f}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Confidence calculation failed: {e}")
            return self._create_default_result()
    
    def _check_veto_conditions(self, market_data: Optional[Dict], 
                               account_data: Optional[Dict],
                               mtf_data: Optional[Dict]) -> tuple:
        """Check for conditions that automatically veto trading."""
        if not market_data:
            return False, None
        
        # 1. News event nearby
        if market_data.get('news_nearby', False) and market_data.get('news_impact') in ['HIGH', 'MEDIUM']:
            return True, "High-impact news event within 10 minutes"
        
        # 2. Excessive spread
        normal_spread = 20 if market_data.get('symbol') == 'XAUUSD' else 2
        if market_data.get('spread', 0) > normal_spread * 2:
            return True, f"Spread too wide: {market_data.get('spread')} (normal: {normal_spread})"
        
        # 3. Extreme volatility
        if market_data.get('volatility_state') == 'EXTREME':
            return True, "Extreme market volatility detected"
        
        # 4. Account drawdown
        if account_data:
            drawdown_pct = account_data.get('drawdown_pct', 0)
            if drawdown_pct > 10:
                return True, f"Account drawdown too high: {drawdown_pct:.1f}%"
            
            # Recent losing streak
            loss_streak = account_data.get('loss_streak', 0)
            if loss_streak > 5:
                return True, f"Losing streak: {loss_streak} trades"
        
        # 5. Multi-timeframe divergence
        if mtf_data:
            if mtf_data.get('divergence_detected', False):
                return True, "Multi-timeframe divergence detected"
            
            if mtf_data.get('regime_shift_imminent', False):
                return True, "Regime shift imminent - wait for clarity"
        
        return False, None
    
    def _score_structure(self, data: Optional[Dict]) -> int:
        """Score market structure analysis (0-100)."""
        if not data:
            return 50
        
        score = 0
        
        # Regime score (0-40 points)
        regime_score = data.get('regime_score', 0)
        score += min(40, regime_score * 0.4)
        
        # Structure score (0-40 points)
        structure_score = data.get('structure_score', 0)
        score += min(40, structure_score * 0.4)
        
        # Trend clarity (0-20 points)
        if data.get('trend_state') in ['BULLISH', 'BEARISH']:
            score += 20
        elif data.get('trend_state') == 'NEUTRAL':
            score += 10
        
        return int(score)
    
    def _score_smc(self, data: Optional[Dict]) -> int:
        """Score Smart Money Concepts analysis (0-100)."""
        if not data:
            return 50
        
        # SMC provides its own total_score (0-100)
        return min(100, data.get('total_score', 50))
    
    def _score_mtf(self, data: Optional[Dict]) -> int:
        """Score Multi-Timeframe analysis (0-100)."""
        if not data:
            return 50
        
        # Alignment score (0-9) → scale to 0-70
        alignment = data.get('alignment_score', 0)
        score = (alignment / 9) * 70
        
        # Trend confidence bonus (0-30 points)
        trend_confidence = data.get('trend_confidence', 0)
        score += (trend_confidence / 100) * 30
        
        return int(score)
    
    def _score_statistical(self, data: Optional[Dict]) -> int:
        """Score statistical analysis (0-100)."""
        if not data:
            return 50
        
        # Statistical edge (0-1) → scale to 0-60
        edge = data.get('statistical_edge', 0.0)
        score = edge * 60
        
        # Bayesian confidence (0-1) → 0-40 points
        bayes_conf = data.get('bayesian_confidence', 0.0)
        score += bayes_conf * 40
        
        return int(score)
    
    def _score_ml(self, data: Optional[Dict]) -> int:
        """Score ML ensemble prediction (0-100)."""
        if not data:
            return 50
        
        # Win probability (0-1) → scale to 0-70
        win_prob = data.get('win_probability', 0.5)
        score = abs(win_prob - 0.5) * 140  # 0.5 = neutral, 0 or 1 = confident
        
        # Model agreement (0-1) → 0-30 points
        agreement = data.get('model_agreement', 0.5)
        score += agreement * 30
        
        return int(min(100, score))
    
    def _score_liquidity(self, market_data: Optional[Dict], smc_data: Optional[Dict]) -> int:
        """Score liquidity conditions (0-100)."""
        score = 50  # Base
        
        if smc_data:
            # Liquidity sweep = good entry
            if smc_data.get('liquidity_sweep', False):
                score += 30
            
            # FVG = liquidity imbalance
            if smc_data.get('fvg_present', False):
                score += 20
        
        return min(100, score)
    
    def _score_momentum(self, structure_data: Optional[Dict], mtf_data: Optional[Dict]) -> int:
        """Score momentum strength (0-100)."""
        if not structure_data:
            return 50
        
        momentum_score = structure_data.get('momentum_score', 0)
        score = momentum_score
        
        # MTF momentum bonus
        if mtf_data:
            regime = mtf_data.get('overall_regime', 'UNKNOWN')
            if 'STRONG' in str(regime):
                score += 20
            elif 'TREND' in str(regime):
                score += 10
        
        return min(100, score)
    
    def _score_volatility(self, market_data: Optional[Dict], statistical_data: Optional[Dict]) -> int:
        """Score volatility favorability (0-100)."""
        if not market_data:
            return 50
        
        volatility_state = market_data.get('volatility_state', 'NORMAL')
        
        # Optimal volatility = NORMAL or slightly HIGH
        mapping = {
            'LOW': 40,
            'NORMAL': 90,
            'HIGH': 70,
            'EXTREME': 10
        }
        
        score = mapping.get(volatility_state, 50)
        
        # Predictability bonus from statistical engine
        if statistical_data:
            predictability = statistical_data.get('predictability', 'MODERATE')
            if predictability == 'HIGH':
                score += 10
            elif predictability == 'CHAOTIC':
                score -= 30
        
        return max(0, min(100, score))
    
    def _score_spread(self, market_data: Optional[Dict], symbol: str) -> int:
        """Score spread favorability (0-100)."""
        if not market_data:
            return 80
        
        spread = market_data.get('spread', 0)
        
        # Normal spreads
        normal_spread = 20 if symbol == 'XAUUSD' else 2
        
        if spread <= normal_spread * 0.8:
            return 100  # Excellent spread
        elif spread <= normal_spread:
            return 90
        elif spread <= normal_spread * 1.2:
            return 70
        elif spread <= normal_spread * 1.5:
            return 50
        else:
            return 20  # Poor spread
    
    def _score_session(self, market_data: Optional[Dict]) -> int:
        """Score trading session favorability (0-100)."""
        if not market_data:
            return 70
        
        session = market_data.get('session', 'UNKNOWN')
        hour = market_data.get('hour_of_day', 12)
        
        # Session quality
        session_scores = {
            'LONDON': 90,
            'NY': 95,
            'OVERLAP': 100,  # London/NY overlap = best
            'ASIA': 60,
            'UNKNOWN': 50
        }
        
        score = session_scores.get(session, 70)
        
        # Avoid dead hours (0-4 UTC)
        if 0 <= hour < 4:
            score -= 30
        
        return max(0, score)
    
    def _score_news(self, market_data: Optional[Dict]) -> int:
        """Score news environment (0-100)."""
        if not market_data:
            return 80
        
        if not market_data.get('news_nearby', False):
            return 100  # No news = safe
        
        impact = market_data.get('news_impact', 'NONE')
        
        mapping = {
            'NONE': 100,
            'LOW': 90,
            'MEDIUM': 50,
            'HIGH': 10
        }
        
        return mapping.get(impact, 80)
    
    def _score_history(self, historical_data: Optional[Dict]) -> int:
        """Score based on similar historical setups (0-100)."""
        if not historical_data:
            return 50
        
        similar_trades = historical_data.get('similar_trades', [])
        
        if len(similar_trades) < 5:
            return 50  # Not enough history
        
        # Calculate win rate of similar setups
        wins = sum(1 for t in similar_trades if t.get('profit_usd', 0) > 0)
        win_rate = wins / len(similar_trades)
        
        # Scale to 0-100
        return int(win_rate * 100)
    
    def _detect_conflicts(self, structure: int, smc: int, mtf: int, 
                         statistical: int, ml: int) -> List[str]:
        """Detect conflicting signals between analysis methods."""
        conflicts = []
        
        # Major conflict = one signal very high, another very low
        scores = {
            'Structure': structure,
            'SMC': smc,
            'MTF': mtf,
            'Statistical': statistical,
            'ML': ml
        }
        
        for name1, score1 in scores.items():
            for name2, score2 in scores.items():
                if name1 < name2:  # Avoid duplicates
                    if score1 > 70 and score2 < 40:
                        conflicts.append(f"{name1} bullish but {name2} bearish")
                    elif score1 < 40 and score2 > 70:
                        conflicts.append(f"{name1} bearish but {name2} bullish")
        
        return conflicts
    
    def _assess_confidence_level(self, confidence: int) -> str:
        """Classify confidence into qualitative levels."""
        if confidence >= 90:
            return "EXCEPTIONAL"
        elif confidence >= 75:
            return "EXCELLENT"
        elif confidence >= 60:
            return "GOOD"
        elif confidence >= 50:
            return "FAIR"
        elif confidence >= 40:
            return "POOR"
        else:
            return "TERRIBLE"
    
    def _generate_recommendation(self, confidence: int, agreement: float, 
                                 conflicts: List[str]) -> str:
        """Generate final trade recommendation."""
        if len(conflicts) > 2:
            return "AVOID"  # Too many conflicts
        
        if agreement < 0.5:
            return "AVOID"  # Low agreement
        
        if confidence >= 60:
            return "TRADE"
        elif confidence >= 50:
            return "CONSIDER"
        else:
            return "AVOID"
    
    def _assess_risk(self, volatility_score: int, spread_score: int, 
                    mtf_data: Optional[Dict]) -> str:
        """Assess overall risk level."""
        risk_points = 0
        
        if volatility_score < 30:
            risk_points += 2
        elif volatility_score < 50:
            risk_points += 1
        
        if spread_score < 50:
            risk_points += 1
        
        if mtf_data and mtf_data.get('divergence_detected', False):
            risk_points += 2
        
        if risk_points >= 4:
            return "EXTREME"
        elif risk_points >= 3:
            return "HIGH"
        elif risk_points >= 1:
            return "MODERATE"
        else:
            return "LOW"
    
    def _calculate_max_lot(self, confidence: int, risk_level: str, 
                          account_data: Optional[Dict]) -> float:
        """Calculate maximum suggested lot size."""
        base_lot = 0.01
        
        if not account_data:
            return base_lot
        
        # Scale by confidence
        if confidence >= 80:
            multiplier = 1.5
        elif confidence >= 70:
            multiplier = 1.2
        elif confidence >= 60:
            multiplier = 1.0
        else:
            multiplier = 0.8
        
        # Reduce for risk
        risk_factors = {
            'LOW': 1.0,
            'MODERATE': 0.8,
            'HIGH': 0.6,
            'EXTREME': 0.4
        }
        
        multiplier *= risk_factors.get(risk_level, 0.8)
        
        suggested_lot = base_lot * multiplier
        
        # Cap at account limits
        max_lot = account_data.get('max_lot', 0.01)
        return min(suggested_lot, max_lot)
    
    def _identify_strengths(self, structure: int, smc: int, mtf: int, 
                           statistical: int, ml: int) -> List[str]:
        """Identify primary strengths of the setup."""
        strengths = []
        
        if structure >= 70:
            strengths.append("Strong market structure")
        if smc >= 70:
            strengths.append("Clear SMC signals")
        if mtf >= 75:
            strengths.append("Excellent multi-timeframe alignment")
        if statistical >= 70:
            strengths.append("Statistical edge present")
        if ml >= 70:
            strengths.append("ML models agree")
        
        return strengths[:3]  # Top 3
    
    def _identify_weaknesses(self, structure: int, smc: int, mtf: int, 
                            statistical: int, ml: int) -> List[str]:
        """Identify primary weaknesses of the setup."""
        weaknesses = []
        
        if structure < 40:
            weaknesses.append("Weak market structure")
        if smc < 40:
            weaknesses.append("Poor SMC signals")
        if mtf < 50:
            weaknesses.append("Low timeframe alignment")
        if statistical < 40:
            weaknesses.append("No statistical edge")
        if ml < 40:
            weaknesses.append("ML models uncertain")
        
        return weaknesses[:3]  # Top 3
    
    def _generate_summary(self, confidence: int, level: str, agreement: float,
                         strengths: List[str], weaknesses: List[str]) -> str:
        """Generate human-readable summary."""
        summary = f"{level} setup with {confidence}% confidence. "
        
        if agreement > 0.8:
            summary += "Strong signal convergence. "
        elif agreement < 0.5:
            summary += "Poor signal agreement. "
        
        if len(strengths) > 0:
            summary += f"Strengths: {', '.join(strengths)}. "
        
        if len(weaknesses) > 0:
            summary += f"Weaknesses: {', '.join(weaknesses)}."
        
        return summary
    
    def _create_veto_result(self, reason: str) -> ConfidenceBreakdown:
        """Create confidence breakdown when veto is active."""
        return ConfidenceBreakdown(
            structure_score=0,
            smc_score=0,
            mtf_score=0,
            statistical_score=0,
            ml_score=0,
            liquidity_score=0,
            momentum_score=0,
            volatility_score=0,
            spread_score=0,
            session_score=0,
            news_score=0,
            history_score=0,
            total_confidence=0,
            confidence_level="TERRIBLE",
            trade_recommendation="AVOID",
            signal_agreement=0.0,
            conflicting_signals=[],
            veto_active=True,
            veto_reason=reason,
            risk_level="EXTREME",
            max_suggested_lot=0.0,
            primary_strengths=[],
            primary_weaknesses=[reason],
            summary=f"VETO ACTIVE: {reason}"
        )
    
    def _create_default_result(self) -> ConfidenceBreakdown:
        """Create default result when calculation fails."""
        return ConfidenceBreakdown(
            structure_score=50,
            smc_score=50,
            mtf_score=50,
            statistical_score=50,
            ml_score=50,
            liquidity_score=50,
            momentum_score=50,
            volatility_score=50,
            spread_score=50,
            session_score=50,
            news_score=50,
            history_score=50,
            total_confidence=50,
            confidence_level="FAIR",
            trade_recommendation="CONSIDER",
            signal_agreement=0.5,
            conflicting_signals=[],
            veto_active=False,
            veto_reason=None,
            risk_level="MODERATE",
            max_suggested_lot=0.01,
            primary_strengths=[],
            primary_weaknesses=["Insufficient data"],
            summary="Default confidence due to incomplete analysis"
        )


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════

_confidence_engine = None

def get_confidence_engine() -> ConfidenceEngine:
    """Get or create singleton confidence engine instance."""
    global _confidence_engine
    if _confidence_engine is None:
        _confidence_engine = ConfidenceEngine()
    return _confidence_engine
