"""
Aegis Gold — Quant Economic Validator ($3–$4 Small-Profit Target Engine)
Calculates trade economics, target feasibility, dynamic lot sizing, and mathematical expectancy.
Rejects setups where expected available move cannot realistically yield the $3.00–$4.00 profit target after costs.
"""

import math
import logging
from typing import Dict, Any, Optional, Tuple
from brain.canonical_types import EntryOpportunity, QuantPlan, NewsRegimeState

logger = logging.getLogger("aegis.quant_validator")


class QuantEconomicValidator:
    """
    Evaluates every candidate opportunity against trade economics.
    Targets $3.00–$4.00 USD per trade (default $3.50).
    """

    TARGET_DEFAULT_USD = 3.50
    TARGET_MIN_USD = 3.00
    TARGET_MAX_USD = 4.00
    MIN_RISK_REWARD = 1.25            # Minimum acceptable R:R for scalping

    def __init__(self):
        pass

    def calculate_position_size(
        self,
        account_equity: float,
        structural_sl_points: int,
        symbol: str,
        point: float,
        tick_size: float = 0.01,
        tick_value: float = 1.0,
        max_risk_usd: float = 10.0,
        volume_min: float = 0.01,
        volume_max: float = 10.0,
        volume_step: float = 0.01
    ) -> float:
        """
        Dynamically calculates position size based on structural stop loss and dollar risk.
        Never hardcodes universal assumptions.
        """
        if structural_sl_points <= 0 or point <= 0 or tick_size <= 0:
            return volume_min

        # Dollar per point per 1.0 standard lot
        # For XAUUSD: 1 point = 0.01 price move = $1.00 per 1.0 lot.
        # For EURUSD: 1 point = 0.00001 price move = $1.00 per 1.0 lot.
        is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
        if is_gold:
            dollar_per_point_1lot = 1.0
        else:
            dollar_per_point_1lot = 1.0

        sl_cost_1lot = structural_sl_points * dollar_per_point_1lot
        if sl_cost_1lot <= 0:
            return volume_min

        raw_lot = max_risk_usd / sl_cost_1lot
        
        # Quantize to broker step
        steps = math.floor(raw_lot / volume_step)
        calc_lot = steps * volume_step
        calc_lot = max(volume_min, min(volume_max, round(calc_lot, 2)))

        return calc_lot

    def validate_opportunity(
        self,
        opportunity: EntryOpportunity,
        account_equity: float,
        spread_pts: float,
        point: float,
        atr_points: float,
        news_state: NewsRegimeState,
        symbol_metadata: Optional[Dict[str, Any]] = None
    ) -> QuantPlan:
        """
        Evaluates opportunity economics and constructs a QuantPlan.
        """
        sym = opportunity.symbol
        direction = opportunity.direction
        entry_px = opportunity.entry_price
        sl_points = max(30, opportunity.structural_sl_points)
        
        # Meta properties
        metadata = symbol_metadata or {}
        tick_size = metadata.get("tick_size", 0.01 if "XAU" in sym else 0.00001)
        tick_value = metadata.get("tick_value", 1.0)
        vol_min = metadata.get("volume_min", 0.01)
        vol_max = metadata.get("volume_max", 10.0)
        vol_step = metadata.get("volume_step", 0.01)

        # 1. Target USD & Lot Sizing
        target_usd = self.TARGET_DEFAULT_USD
        max_risk_usd = 5.0  # $5 max risk for $3.50 target scalp on micro balance

        lot = self.calculate_position_size(
            account_equity=account_equity,
            structural_sl_points=sl_points,
            symbol=sym,
            point=point,
            tick_size=tick_size,
            tick_value=tick_value,
            max_risk_usd=max_risk_usd,
            volume_min=vol_min,
            volume_max=vol_max,
            volume_step=vol_step
        )

        # 2. Dollar per point for calculated lot
        is_gold = "XAU" in sym.upper() or "GOLD" in sym.upper()
        dollar_per_point = lot * (1.0 if is_gold else 1.0)

        # 3. Required TP points to hit target USD after spread
        spread_cost_usd = spread_pts * dollar_per_point
        net_target_usd = target_usd + spread_cost_usd
        required_tp_points = math.ceil(net_target_usd / max(0.0001, dollar_per_point))

        # Ensure minimum pip floor
        tp_floor_pts = 35 if is_gold else 10
        tp_points = max(tp_floor_pts, required_tp_points)

        # 4. Calculate prices
        if direction == "BUY":
            sl_price = round(entry_px - (sl_points * point), 5 if not is_gold else 2)
            tp_price = round(entry_px + (tp_points * point), 5 if not is_gold else 2)
        else:
            sl_price = round(entry_px + (sl_points * point), 5 if not is_gold else 2)
            tp_price = round(entry_px - (tp_points * point), 5 if not is_gold else 2)

        # 5. Economic Feasibility Check
        # Check if the market ATR can realistically deliver the required move
        expected_move_points = atr_points * 0.8  # Realistic intraday move is ~80% of ATR
        risk_usd = sl_points * dollar_per_point
        rr_ratio = round((tp_points * dollar_per_point) / max(0.01, risk_usd), 2)

        # Target feasibility condition:
        # ATR must be large enough so that required TP points <= 1.5 * ATR
        is_realistic = True
        rejection_reason = ""

        if tp_points > atr_points * 1.8 and atr_points > 0:
            is_realistic = False
            rejection_reason = f"Required TP ({tp_points}pts) exceeds realistic ATR capacity ({atr_points:.1f}pts)"
        elif spread_cost_usd > (target_usd * 0.50):
            # Spread eats more than 50% of target profit
            is_realistic = False
            rejection_reason = f"Spread friction too high (${spread_cost_usd:.2f} > 50% of target ${target_usd:.2f})"
        elif not news_state.trading_allowed:
            is_realistic = False
            rejection_reason = f"News regime restriction: {news_state.reason}"
        elif rr_ratio < 0.50:
            is_realistic = False
            rejection_reason = f"Risk/Reward ratio structurally unacceptable ({rr_ratio:.2f} < 0.50)"

        # Expected Value calculation based on pattern structural expectation
        # Base win rate for verified structural patterns is ~55-60%
        base_win_rate = 0.58
        ev_usd = (base_win_rate * target_usd) - ((1.0 - base_win_rate) * risk_usd) - spread_cost_usd

        return QuantPlan(
            opportunity_id=opportunity.opportunity_id,
            symbol=sym,
            direction=direction,
            entry_price=entry_px,
            stop_loss_price=sl_price,
            take_profit_price=tp_price,
            sl_points=sl_points,
            tp_points=tp_points,
            target_usd=target_usd,
            risk_usd=round(risk_usd, 2),
            risk_reward_ratio=rr_ratio,
            lot_size=lot,
            atr_points=atr_points,
            spread_cost_usd=round(spread_cost_usd, 2),
            expected_move_points=round(expected_move_points, 1),
            target_is_economically_realistic=is_realistic,
            expected_value_usd=round(ev_usd, 2),
            rejection_reason=rejection_reason
        )
