"""
Aegis-Gold v6.0 / OMEGA — Local Offline AI Supervisor
Orchestrates local engines (Candle, Trend, Momentum, Volatility, Spread) completely offline.
No external AI APIs. No cloud services. Fully local decision engine.
"""

import logging
import time
import asyncio
from typing import Dict, Any
import MetaTrader5 as mt5

from config import settings as cfg
from brain.candle_ai import CandleAI
from brain.trend_detector import TrendDetector
from brain.momentum_engine import MomentumEngine
from brain.volatility_engine import VolatilityEngine
from brain.spread_filter import SpreadFilter
from brain.entry_engine import EntryEngine
from brain.exit_engine import ExitEngine
from brain.risk_manager import OMEGARiskManager
from brain.adaptive_learning import AdaptiveLearning
from brain.recovery_daemon import RecoveryDaemon

logger = logging.getLogger("aegis.ai")

class AISupervisor:
    def __init__(self):
        # Local AI Engines
        self.enabled = True # Always active locally
        self.candle_ai = CandleAI()
        self.trend_detector = TrendDetector()
        self.momentum_engine = MomentumEngine()
        self.volatility_engine = VolatilityEngine()
        self.spread_filter = SpreadFilter()
        self.entry_engine = EntryEngine()
        self.exit_engine = ExitEngine()
        self.adaptive_learning = AdaptiveLearning()
        self.recovery_daemon = RecoveryDaemon()

        logger.info("🟢 ANTIGRAVITY OMEGA Local Offline AI Supervisor ENABLED (100% cloud-independent)")

    async def verify_trade(self, symbol: str, direction: str, context: Dict[str, Any], candles_m1 = None, candles_m5 = None) -> Dict[str, Any]:
        """
        Runs complete quantitative evaluation of the trade setup locally.
        Returns structured approval dict compatible with main loop expectations.
        """
        logger.info(f"OMEGA vetting XAUUSD/EURUSD {direction} trade setup locally...")

        # 1. Fetch Multi-Timeframe rates directly from MT5 if not provided
        if candles_m5 is not None:
            m5_rates = candles_m5
        else:
            m5_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 100)
            
        if candles_m1 is not None:
            m1_rates = candles_m1
        else:
            m1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, 30)
            
        ticks = mt5.copy_ticks_from(symbol, int(time.time()), 200, mt5.COPY_TICKS_ALL)
        tick_obj = mt5.symbol_info_tick(symbol)

        if m5_rates is None or len(m5_rates) < 30 or m1_rates is None or len(m1_rates) < 20 or tick_obj is None:
            logger.warning("Veto trade: Insufficient market data fetched by supervisor.")
            return {
                "approved": False,
                "reason": "VETO | Insufficient broker market data sync",
                "confidence": 0
            }

        # 2. Extract price arrays
        sym_info = mt5.symbol_info(symbol)
        point = sym_info.point if sym_info else 0.00001
        current_spread = (tick_obj.ask - tick_obj.bid) / point if point > 0 else 0.0

        try:
            closes_m1 = [c[4] for c in m1_rates]
            highs_m1 = [c[2] for c in m1_rates]
            lows_m1 = [c[3] for c in m1_rates]
            opens_m1 = [c[1] for c in m1_rates]
        except Exception:
            logger.error("Failed to parse M1 candle array structures")
            return {"approved": False, "reason": "VETO | Market structure corrupt", "confidence": 0}

        # Get adaptive corrections
        adaptations = self.adaptive_learning.get_adaptations()
        selectivity_offset = adaptations.get("selectivity_offset", 0)

        # 3. RUN LOCAL ENGINES
        warnings = []

        # A. Spread Check
        session = context.get("session", "LONDON")
        session_spread_max = cfg.get_symbol_config(symbol).get("spread_limits", {}).get(session, 30)
        spread_res = self.spread_filter.analyze(current_spread, session, session_spread_max)
        if not spread_res["spread_ok"]:
            warnings.append(f"Spread is too wide ({current_spread:.0f} pts)")

        # B. Volatility / News Filter
        max_vol_ratio = cfg.get_symbol_config(symbol).get("max_volatility_ratio", 2.5)
        vol_res = self.volatility_engine.analyze(m5_rates, point, max_ratio_limit=max_vol_ratio)
        if vol_res["news_spike_detected"]:
            warnings.append("High volatility spike detected (news filter active)")

        # Macro Event Blackout Veto Check (QUANT X)
        try:
            from config.quant_x_config import QX
            from brain.macro_context import get_macro_context
            if QX.flag("ai_supervisor_macro_veto"):
                m_ctx = get_macro_context().get_event_context(symbol)
                if m_ctx.blackout:
                    warnings.append(f"Macro event blackout active ({m_ctx.blackout_reason})")
        except Exception as e:
            logger.warning(f"Failed to check macro context in AI supervisor: {e}")

        # C. Trend Detector
        trend_res = self.trend_detector.analyze(m5_rates, m1_rates)
        expected_trend = "TRENDING_UP" if direction == "BUY" else "TRENDING_DOWN"
        if trend_res["trend"] != expected_trend:
            warnings.append(f"Trend is divergent ({trend_res['reason']})")


        # D. Candle structure & pattern AI
        candle_res = self.candle_ai.analyze(m5_rates)
        # Verify no opposite rejection candle
        if direction == "BUY" and candle_res["rejection"] == "TOP":
            warnings.append("Strong upper wick rejection detected (shooting star pattern)")
        elif direction == "SELL" and candle_res["rejection"] == "BOTTOM":
            warnings.append("Strong lower wick rejection detected (hammer pattern)")

        # E. Entry timing (symbol-aware — Gold uses wider zones)
        entry_res = self.entry_engine.analyze(closes_m1, highs_m1, lows_m1, opens_m1, direction, point, symbol=symbol)
        if not entry_res["entry_approved"]:
            warnings.append(f"Entry parameters not met ({entry_res['reason']})")

        # F. Momentum check
        momentum_res = self.momentum_engine.analyze(ticks, m1_rates, point)

        # 4. Score Calculation with heavy candle weight
        candle_strength = candle_res["bullish_strength" if direction == "BUY" else "bearish_strength"]
        candle_weight = 0.40
        trend_weight = 0.20
        entry_weight = 0.20
        momentum_weight = 0.20

        confidence = int(
            candle_strength * candle_weight +
            trend_res["trend_score"] * trend_weight +
            entry_res["entry_score"] * entry_weight +
            momentum_res["momentum_score"] * momentum_weight
        )
        
        # Apply performance offset
        confidence = max(0, min(100, confidence - selectivity_offset))

        min_required_score = 20
        
        # Determine native approval
        native_approved = len(warnings) == 0 and confidence >= min_required_score
          # Advisory Override Check
        brain_confidence = context.get("brain_confidence", 0)
        
        # Self-Thinking Autonomous Mode
        # If warnings exist, but supervisor confidence is high, analyze context and decide autonomously
        autonomous_override = False
        override_reason = ""
        
        if not native_approved and confidence >= 40:
            has_spread_warning = any("Spread is too wide" in w for w in warnings)
            has_news_warning = any("volatility spike" in w for w in warnings)
            
            if not has_spread_warning and not has_news_warning:
                high_momentum = momentum_res.get("momentum_score", 0) >= 50
                strong_candle = candle_strength >= 60
                
                if high_momentum or strong_candle:
                    autonomous_override = True
                    override_reason = f"Approved via AI Autonomous Self-Thinking (momentum={momentum_res.get('momentum_score')}% candle={candle_strength}%)"

        # For XAUUSD (Gold): always use advisory mode — never hard-veto a brain-approved trade
        # The brain already has a 40% threshold for Gold; OMEGA acts as advisor not blocker
        if symbol == "XAUUSD":
            advisory_threshold = 0  # Always advisory for Gold
        else:
            advisory_threshold = 20  # EURUSD: require 20% brain confidence for advisory
        
        if autonomous_override:
            approved = True
            reason = f"OMEGA SELF-THINK OVERRIDE | {override_reason} | Score: {confidence}%"
        elif brain_confidence >= advisory_threshold:
            approved = True
            if not native_approved:
                reason = f"OMEGA ADVISORY | Warnings: {', '.join(warnings)} | Score: {confidence}%"
            else:
                reason = f"OMEGA APPROVED | Confidence: {confidence}% | {candle_res['reason']}"
        else:
            approved = native_approved
            if approved:
                reason = f"OMEGA APPROVED | Confidence: {confidence}% | {candle_res['reason']}"
            else:
                reason = f"VETO | Warnings: {', '.join(warnings)} | Score: {confidence}%"

        # Self-thinking reasoning chain log
        reasoning_chain = [
            f"🔍 OMEGA Vetting {symbol} {direction} Setup:",
            f"  • Spread Check: {'PASS' if spread_res['spread_ok'] else 'FAIL'} ({current_spread:.1f} pts / Limit {session_spread_max})",
            f"  • Volatility Check: {'PASS' if not vol_res['news_spike_detected'] else 'FAIL'} (Ratio {vol_res['volatility_ratio']:.2f} / Limit {max_vol_ratio:.1f})",
            f"  • Trend Alignment: {'PASS' if trend_res['trend'] == expected_trend else 'FAIL'} ({trend_res['reason']})",
            f"  • Candle Rejection: {'PASS' if not ((direction == 'BUY' and candle_res['rejection'] == 'TOP') or (direction == 'SELL' and candle_res['rejection'] == 'BOTTOM')) else 'FAIL'} ({candle_res['reason']})",
            f"  • Entry Timing: {'PASS' if entry_res['entry_approved'] else 'FAIL'} ({entry_res['reason']})",
            f"  • Momentum: {'PASS' if momentum_res['momentum_score'] >= 20 else 'FAIL'} (Score: {momentum_res['momentum_score']}%)",
            f"  • Final Veto Check: {len(warnings)} warning(s). Approved: {approved}. Final confidence: {confidence}%"
        ]
        if autonomous_override:
            reasoning_chain.append(f"  • Autonomous Self-Thinking Override applied: {override_reason}")
            
        thought_summary = "\n".join(reasoning_chain)
        logger.info(f"🧠 AI SUPERVISOR THOUGHT LOG:\n{thought_summary}")

        # Log reasoning chain to file for transparency
        try:
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            log_file = os.path.join(base_dir, "data", "ai_supervisor_log.txt")
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                f.write(thought_summary + "\n")
                if autonomous_override:
                    f.write(f"Decision: {reason}\n")
                f.write("="*40 + "\n")
        except Exception as e:
            logger.error(f"Failed to log reasoning chain to file: {e}")

        logger.info(f"OMEGA Decision: approved={approved} (native_approved={native_approved}) confidence={confidence}% | {reason}")
        return {
            "approved": approved,
            "reason": reason,
            "confidence": confidence,
            "lot_multiplier": adaptations.get("lot_multiplier", 1.0)
        }
