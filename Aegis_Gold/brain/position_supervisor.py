"""
Aegis-Gold v10.0 — Position Supervisor Engine
Monitors open positions, manages signal scoring/queues, and checks volatility-adjusted limits.
"""

import logging
import time
from typing import Dict, Any, List, Tuple
from config import settings as cfg
from brain.indicators import RSI

logger = logging.getLogger("aegis.position_supervisor")

class PositionSupervisor:
    def __init__(self, gateway=None, risk_mgr=None):
        self.gateway = gateway
        self.risk_mgr = risk_mgr
        self._bound = gateway is not None and risk_mgr is not None
        self._limit_warning_logged = False
        self.signal_queue: List[Dict[str, Any]] = []
        logger.info("?? Position Supervisor Engine Initialized")

    def bind(self, gateway, risk_mgr):
        self.gateway = gateway
        self.risk_mgr = risk_mgr
        self._bound = True
        self._limit_warning_logged = False
        logger.info("?? PositionSupervisor.bind() called ? gateway and risk_mgr now live.")

    def get_dynamic_trade_limit(self, volatility_state: str, is_emergency: bool = False) -> int:
        """
        Dynamic Trade Limits:
        Unlimited mode: returns cfg.MAX_OPEN_TRADES (999999 by design — intentional config, not a placeholder)
        Emergency: returns 1

        GUARD: If called before .bind() is invoked, logs a one-time critical warning.
        The returned value is still valid (derived from config), but evaluate_position()
        MUST NOT be called before .bind() or it will AttributeError on self.risk_mgr.
        """
        if not self._bound and not self._limit_warning_logged:
            logger.critical(
                "[PositionSupervisor] get_dynamic_trade_limit() called BEFORE .bind() — "
                "gateway and risk_mgr are None. Trade limit is from config (intentional), "
                "but DO NOT call evaluate_position() until .bind() is invoked."
            )
            self._limit_warning_logged = True

        # Emergency always restricts
        if is_emergency:
            return cfg.VOLATILITY_LIMITS.get("EMERGENCY", 1)

        # If MAX_OPEN_TRADES is set to unlimited (>= 100), respect that directly.
        # NOTE: cfg.MAX_OPEN_TRADES = 999999 is INTENTIONAL "unlimited" configuration.
        # This is not a sentinel or placeholder — it is the explicit operator setting.
        max_from_cfg = getattr(cfg, 'MAX_OPEN_TRADES', 10)
        if max_from_cfg >= 100:
            return max_from_cfg  # UNLIMITED mode — intentional operator config

        # Otherwise use per-volatility limits
        limit = cfg.VOLATILITY_LIMITS.get(volatility_state, 3)
        return limit

    def score_signal(self, symbol: str, direction: str, confidence: float, 
                     trend_score: float, volatility_score: float, 
                     spread: float, momentum_score: float) -> float:
        """
        Scoring signal for execution priority.
        Higher score = better rank.
        Formula:
          Score = (confidence * 0.3) + (trend_score * 0.2) + (momentum_score * 0.2)
                  - (spread * 0.2) - (volatility_score * 0.1)
        """
        score = (confidence * 0.3) + (trend_score * 0.2) + (momentum_score * 0.2) - (spread * 0.2) - (volatility_score * 0.1)
        # Gold boost slightly to capture momentum
        if "XAU" in symbol or symbol == "XAUUSD":
            score += 5.0
        return round(score, 2)

    def evaluate_position(self, pos, ticks: List[Dict[str, Any]], 
                          candles_m1: List[Dict[str, Any]], 
                          candles_m5: List[Dict[str, Any]], 
                          current_spread: float, 
                          trend_res: Dict[str, Any], 
                          volatility_res: Dict[str, Any], 
                          momentum_res: Dict[str, Any],
                          session: str,
                          is_emergency_drawdown: bool = False) -> Dict[str, Any]:
        """
        Evaluates an open position against exit conditions:
        - Reversal detection (trend exhaustion, opposite alignment)
        - Momentum weakening (M1 RSI overbought/oversold pullback)
        - Volatility spike (extreme ATR ratio)
        - Spread spike (current spread exceeds limit significantly)
        - Liquidity change (TPS drop / spread increase)
        - Profit protection (breakeven, trailing, dynamic TP)
        """
        # ── UNBOUND GUARD ─────────────────────────────────────────────────────
        # If .bind() was never called, self.risk_mgr and self.gateway are None.
        # Proceeding would raise AttributeError on self.risk_mgr.check_breakeven().
        if not self._bound:
            logger.critical(
                f"[PositionSupervisor] evaluate_position() called BEFORE .bind() — "
                f"self.risk_mgr is None. Returning HOLD to prevent AttributeError. "
                f"Call .bind(gateway, risk_mgr) before using evaluate_position()."
            )
            return {"action": "HOLD", "reason": "PositionSupervisor not bound — call .bind() first"}

        symbol = pos.symbol
        ticket = pos.ticket
        pos_dir = "BUY" if pos.type == 0 else "SELL"
        live_profit = pos.profit
        sym_info = self.gateway.symbols_data.get(symbol, {})
        point = sym_info.get("point", 0.00001)

        # Retrieve settings
        sym_cfg = cfg.get_symbol_config(symbol)
        spread_max = sym_cfg.get("spread_limits", {}).get(session, 40)
        vol_max_ratio = sym_cfg.get("max_volatility_ratio", 5.0)

        # ── 1. SPREAD SPIKE DETECTION ──────────────────────────────────────
        # Exit if spread is extremely wide (>1.8x limit) and trade is underperforming
        if current_spread > spread_max * 1.8:
            if live_profit < 0:
                logger.warning(f"Ticket #{ticket} exit triggered: Spread spike detected ({current_spread:.0f} pts vs max {spread_max})")
                return {"action": "CLOSE", "reason": f"Spread spike ({current_spread:.0f} pts)"}

        # ── 2. VOLATILITY SPIKE / ABNORMAL VOLATILITY ─────────────────────
        # Extreme volatility ratio indicates abnormal condition
        vol_ratio = volatility_res.get("volatility_ratio", 1.0)
        if vol_ratio > vol_max_ratio * 1.5 or volatility_res.get("news_spike_detected", False):
            # If trade has negative floating profit, close to prevent damage
            if live_profit < -1.0:
                logger.warning(f"Ticket #{ticket} exit triggered: Abnormal volatility ratio {vol_ratio:.2f}")
                return {"action": "CLOSE", "reason": f"Volatility ratio spike ({vol_ratio:.2f})"}

        # ── 3. TREND REVERSAL DETECTION ──────────────────────────────────
        trend_dir = trend_res.get("trend")
        trend_score = trend_res.get("trend_score", 0)
        
        # BUY position, but trend has flipped strongly bearish
        if pos_dir == "BUY" and trend_dir == "TRENDING_DOWN" and trend_score >= 50:
            logger.warning(f"Ticket #{ticket} exit triggered: Strong trend reversal to bearish")
            return {"action": "CLOSE", "reason": f"Trend reversal to BEARISH (Score: {trend_score}%)"}
            
        # SELL position, but trend has flipped strongly bullish
        if pos_dir == "SELL" and trend_dir == "TRENDING_UP" and trend_score >= 50:
            logger.warning(f"Ticket #{ticket} exit triggered: Strong trend reversal to bullish")
            return {"action": "CLOSE", "reason": f"Trend reversal to BULLISH (Score: {trend_score}%)"}

        # ── 4. MOMENTUM WEAKENING DETECTION (DISABLED FOR FIRST 200 TRADES) ───
        # FIRST 200 TRADES MODE: Don't exit on small RSI pullbacks - hold for bigger profits
        # Only exit if BOTH momentum is dead AND we're in a loss
        from brain.candle_utils import parse_closes
        closes_m1 = parse_closes(candles_m1)

        if len(closes_m1) >= 14:
            rsi_list = RSI(closes_m1, 14)
            if rsi_list:
                curr_rsi = rsi_list[-1]
                prev_rsi = rsi_list[-2]
                
                # INSTITUTIONAL MODE: Only exit RSI exhaustion if profit >= SCALP_MIN_PROFIT_USD ($1.00+)
                min_profit_rsi_exit = getattr(cfg, 'SCALP_MIN_PROFIT_USD', 1.00)
                
                # BUY: RSI was overbought (>75) and is now falling hard
                if pos_dir == "BUY" and prev_rsi > 75.0 and curr_rsi < 70.0:
                    if live_profit >= min_profit_rsi_exit:
                        logger.warning(f"Ticket #{ticket} exit triggered: M1 RSI exhaustion {prev_rsi:.1f} -> {curr_rsi:.1f} @ ${live_profit:.2f}")
                        return {"action": "CLOSE", "reason": f"M1 Bullish RSI exhaustion @ ${live_profit:.2f}"}
                        
                # SELL: RSI was oversold (<25) and is now rising hard
                if pos_dir == "SELL" and prev_rsi < 25.0 and curr_rsi > 30.0:
                    if live_profit >= min_profit_rsi_exit:
                        logger.warning(f"Ticket #{ticket} exit triggered: M1 RSI exhaustion {prev_rsi:.1f} -> {curr_rsi:.1f} @ ${live_profit:.2f}")
                        return {"action": "CLOSE", "reason": f"M1 Bearish RSI exhaustion @ ${live_profit:.2f}"}

        # Momentum score drop - only exit if SEVERE drop AND negative
        mom_score = momentum_res.get("momentum_score", 50)
        if mom_score < 10 and live_profit < -5.00:  # Only exit on severe momentum loss AND big loss
            logger.warning(f"Ticket #{ticket} exit triggered: Dead momentum (Score: {mom_score})")
            return {"action": "CLOSE", "reason": "Momentum exhaustion"}

        # ── 5. LIQUIDITY DECAY DETECTION ─────────────────────────────────
        tps = momentum_res.get("tps", 2.0)
        # Exceptionally low tick rate (TPS < 0.2) + wide spread indicates illiquid market
        if tps < 0.2 and current_spread > spread_max * 1.3:
            if live_profit < -1.00:
                logger.warning(f"Ticket #{ticket} exit triggered: Low liquidity (TPS: {tps:.1f}, Spread: {current_spread:.0f})")
                return {"action": "CLOSE", "reason": "Low liquidity & spread expansion"}

        # ── 6. DRAWDOWN EMERGENCY EXITS ──────
        if is_emergency_drawdown:
            min_emergency_profit = getattr(cfg, 'SCALP_MIN_PROFIT_USD', 1.00)
            if live_profit >= min_emergency_profit:
                logger.warning(f"Ticket #{ticket} closed with ${live_profit:.2f} profit under Emergency Drawdown Mode.")
                return {"action": "CLOSE", "reason": f"Emergency DD Capital Protection @ ${live_profit:.2f}"}

        # ── 7. PROFIT PROTECTION FALLBACK (Breakeven & Trailing Stops) ──────
        tier = getattr(pos, 'pattern_tier', 'scalp')
        self.risk_mgr.check_breakeven(pos, pattern_tier=tier)
        self.risk_mgr.check_trailing_stop(pos, pattern_tier=tier)
        self.risk_mgr.check_dynamic_tp(pos, self.gateway)

        return {"action": "HOLD", "reason": "Conditions stable"}

