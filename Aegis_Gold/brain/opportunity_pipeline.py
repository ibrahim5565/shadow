"""
Aegis Gold — Master Opportunity & Execution Pipeline
Orchestrates:
KRNOS Pattern -> SMC Structure Validation -> Trigger Detection -> News Regime ->
Quant $3–$4 Economics -> Local AI Context -> Risk Clearance -> TradeAuthorization Contract.
"""

import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from brain.canonical_types import (
    PatternCandidate, EntryOpportunity, NewsRegimeState, QuantPlan, TradeAuthorization
)
from brain.quant_economic_validator import QuantEconomicValidator
from brain.anti_duplicate_engine import AntiDuplicateEngine
from brain.news_filter import NewsFilter

logger = logging.getLogger("aegis.opportunity_pipeline")


class OpportunityPipeline:
    """
    Core execution engine for Aegis Gold v9.0.
    Builds trade authorizations from verified market patterns and quant economics.
    """

    def __init__(self):
        self.quant_validator = QuantEconomicValidator()
        self.anti_duplicate = AntiDuplicateEngine()
        self.news_filter = NewsFilter()

    def evaluate_opportunity(
        self,
        symbol: str,
        candles_m5: Any,
        candles_m1: Any,
        ticks: Any,
        account: Dict[str, Any],
        spread_pts: float,
        point: float,
        session: str,
        risk_mgr: Any
    ) -> Tuple[Optional[TradeAuthorization], str]:
        """
        Executes the deterministic 8-stage opportunity evaluation sequence.
        Returns (TradeAuthorization, reason_code).
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # -------------------------------------------------------------
        # STAGE 1: KRNOS & SMC PATTERN RECOGNITION
        # -------------------------------------------------------------
        from brain.smc_engine import detect_big_pattern, detect_small_pattern
        
        big_pattern = detect_big_pattern(symbol=symbol, candles_m5=candles_m5, point=point)
        if not big_pattern or big_pattern.bias == "neutral":
            return None, "NO_VALID_PATTERN"

        direction = "BUY" if big_pattern.bias == "bullish" else "SELL"
        pattern_id = f"KRNOS_SMC_{symbol}_{direction}_{big_pattern.pattern_type}_{int(time.time())}"

        # Current price
        current_price = 0.0
        try:
            if candles_m5 is not None and len(candles_m5) > 0:
                last_c = candles_m5.iloc[-1] if hasattr(candles_m5, 'iloc') else candles_m5[-1]
                if isinstance(last_c, dict):
                    current_price = float(last_c.get("close", last_c.get("c", 0.0)))
                elif hasattr(last_c, "close"):
                    current_price = float(last_c.close)
                elif isinstance(last_c, (list, tuple)):
                    current_price = float(last_c[4])
                else:
                    current_price = float(last_c)
        except Exception:
            current_price = 0.0

        if current_price <= 0.0:
            return None, "INVALID_MARKET_DATA"

        inval_level = big_pattern.invalidation_level or (
            current_price - (150 * point) if direction == "BUY" else current_price + (150 * point)
        )

        pattern = PatternCandidate(
            pattern_id=pattern_id,
            engine_source="KRNOS_SMC_HYBRID",
            timeframe="M5",
            direction=direction,
            pattern_type=big_pattern.pattern_type,
            structure_context=f"Session_{session}",
            invalidation_level=inval_level,
            entry_zone_low=min(current_price, inval_level),
            entry_zone_high=max(current_price, inval_level),
            metadata={"big_pattern_details": big_pattern.details}
        )

        # -------------------------------------------------------------
        # STAGE 2: SMC / STRUCTURAL VALIDATION
        # -------------------------------------------------------------
        # Invalidation distance check
        sl_dist_pts = int(abs(current_price - inval_level) / max(0.00001, point))
        is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
        min_sl_pts = 35 if is_gold else 15
        max_sl_pts = 350 if is_gold else 100

        if sl_dist_pts < min_sl_pts:
            sl_dist_pts = min_sl_pts
        elif sl_dist_pts > max_sl_pts:
            return None, "STRUCTURAL_INVALIDATION_TOO_WIDE"

        # -------------------------------------------------------------
        # STAGE 3: PRECISION ENTRY TRIGGER (M1 / M5)
        # -------------------------------------------------------------
        trigger_name = "M5_STRUCTURAL_SHIFT"
        small_pat = detect_small_pattern(
            symbol=symbol,
            candles_m1=candles_m1,
            required_bias="bullish" if direction == "BUY" else "bearish",
            point=point
        )
        if small_pat and small_pat.direction == direction:
            trigger_name = small_pat.pattern_type

        opportunity = EntryOpportunity(
            opportunity_id=f"OPP_{symbol}_{direction}_{int(time.time()*1000)}",
            pattern=pattern,
            symbol=symbol,
            direction=direction,
            entry_price=current_price,
            structural_sl_price=inval_level,
            structural_sl_points=sl_dist_pts,
            trigger_type=trigger_name,
            entry_zone_valid=True,
            reason=f"Validated {pattern.pattern_type} with trigger {trigger_name}"
        )

        # -------------------------------------------------------------
        # STAGE 4: ANTI-DUPLICATE CHECK
        # -------------------------------------------------------------
        if self.anti_duplicate.is_duplicate(opportunity, point=point):
            return None, "DUPLICATE_OPPORTUNITY"

        # -------------------------------------------------------------
        # STAGE 5: NEWS / FUNDAMENTAL REGIME FILTER
        # -------------------------------------------------------------
        is_news_clear = self.news_filter.is_news_clear(symbol=symbol)
        news_state = NewsRegimeState(
            regime="NORMAL" if is_news_clear else "NEWS_SHOCK",
            trading_allowed=is_news_clear,
            spread_multiplier_tolerance=1.5 if is_news_clear else 2.5,
            reason="Market news window clear" if is_news_clear else "High-impact news window active"
        )

        if not news_state.trading_allowed:
            return None, "NEWS_REGIME_BLOCKED"

        # -------------------------------------------------------------
        # STAGE 6: QUANT $3–$4 ECONOMIC FEASIBILITY VALIDATION
        # -------------------------------------------------------------
        # Compute ATR
        from brain.indicators import ATR
        atr_estimate = 150.0 if is_gold else 40.0
        try:
            if candles_m5 is not None and len(candles_m5) >= 14:
                hi = [c["high"] if isinstance(c, dict) else c[2] for c in candles_m5]
                lo = [c["low"] if isinstance(c, dict) else c[3] for c in candles_m5]
                cl = [c["close"] if isinstance(c, dict) else c[4] for c in candles_m5]
                atrs = ATR(hi, lo, cl, 14)
                if atrs and atrs[-1] > 0 and point > 0:
                    atr_estimate = atrs[-1] / point
        except Exception:
            pass

        account_equity = float(account.get("equity", 1000.0))
        quant_plan = self.quant_validator.validate_opportunity(
            opportunity=opportunity,
            account_equity=account_equity,
            spread_pts=spread_pts,
            point=point,
            atr_points=atr_estimate,
            news_state=news_state
        )

        if not quant_plan.target_is_economically_realistic:
            return None, f"TARGET_NOT_REALISTIC: {quant_plan.rejection_reason}"

        # -------------------------------------------------------------
        # STAGE 7: LOCAL AI CONTEXTUAL ADVISOR (METADATA ONLY)
        # -------------------------------------------------------------
        local_ai_context = {
            "regime": big_pattern.pattern_type,
            "session": session,
            "expected_value_usd": quant_plan.expected_value_usd,
            "atr_points": round(atr_estimate, 1),
            "spread_points": round(spread_pts, 1),
            "target_usd": quant_plan.target_usd
        }

        # -------------------------------------------------------------
        # STAGE 8: RISK CLEARANCE & TRADE AUTHORIZATION CONTRACT
        # -------------------------------------------------------------
        # Daily loss circuit breaker check
        if hasattr(risk_mgr, "is_daily_loss_limit_reached") and risk_mgr.is_daily_loss_limit_reached():
            return None, "DAILY_LOSS_LIMIT_REACHED"

        auth = TradeAuthorization(
            authorized=True,
            authorization_id=f"AUTH_{symbol}_{int(time.time()*1000)}",
            opportunity_id=opportunity.opportunity_id,
            pattern_id=pattern.pattern_id,
            symbol=symbol,
            direction=direction,
            lot=quant_plan.lot_size,
            entry_price=opportunity.entry_price,
            stop_loss=quant_plan.stop_loss_price,
            take_profit=quant_plan.take_profit_price,
            target_usd=quant_plan.target_usd,
            risk_usd=quant_plan.risk_usd,
            sl_points=quant_plan.sl_points,
            tp_points=quant_plan.tp_points,
            news_regime=news_state.regime,
            local_ai_context=local_ai_context,
            reason=(
                f"🎯 AUTHORIZED {direction} {symbol} | Pattern: {pattern.pattern_type} | "
                f"Target: ${quant_plan.target_usd:.2f} ({quant_plan.tp_points}pts) | "
                f"SL: ${quant_plan.risk_usd:.2f} ({quant_plan.sl_points}pts) | Lot: {quant_plan.lot_size}"
            )
        )

        # Record authorization in anti-duplicate tracker
        self.anti_duplicate.record_authorization(opportunity)

        return auth, "AUTHORIZED"
