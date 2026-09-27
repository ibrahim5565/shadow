"""
Aegis-Gold v6.0 — Risk Manager
9-layer protection. Fully symbol-aware.
"""

import os
import time
import json
import math
import logging
from collections import deque
from datetime import datetime, timezone

from typing import Optional, Dict, Any, List, Set, Tuple
from config import settings as cfg

logger = logging.getLogger("aegis.risk")
LOCKFILE = os.path.join(os.path.dirname(__file__), "..", "data", "lockfile.json")


class RiskManager:
    """9-layer risk protection system."""

    def __init__(self, gateway):
        self.gateway       = gateway
        self._tg_send      = None

        # Daily state
        self.start_equity        : float = 0.0
        self.daily_trades        : int   = 0
        self.session_trades      : dict  = {"ASIAN": 0, "LONDON": 0, "NY": 0, "OVERLAP": 0}
        self.today_date          : str   = ""
        self.today_wins          : int   = 0
        self.today_losses        : int   = 0

        # Consecutive loss tracking
        self.consecutive_losses  : int   = 0
        self.is_paused           : bool  = False
        self.pause_until         : float = 0.0

        # Equity curve
        self.recent_pnls         : deque = deque(maxlen=20)

        # Manual overrides
        self.stop_today          : bool  = False
        self.manual_pause        : bool  = False

        # Open trade times {ticket: open_time}
        self.open_trade_times    : dict  = {}

        # Trades-per-minute tracking
        self.trade_timestamps: list = []
        
        # Loss cooldown tracking
        self.last_loss_time: float = 0.0
        
        # Duplicate direction tracking {symbol: {"direction": str, "time": float}}
        self.last_trade_info: dict = {}
        
        # Global lot size override
        self.lot_override: float = 0.0

        # Dynamic TP: track peak profit (pts) per ticket {ticket: peak_pts}
        self._peak_profit_pts: dict = {}
        # Track last TP modification time per ticket {ticket: timestamp}
        self._last_tp_modify: dict = {}

        # Module 4: Kelly sizer state
        self._kelly_lot_last: float = 0.0        # last computed Kelly lot
        self._kelly_hard_cap_active: bool = False # was 2% hard cap the binding constraint?
        self._cvar_alert_sent: bool = False       # prevent duplicate Telegram alerts per session
        self._partial_taken_tickets: set = set()   # set of ticket IDs where partial TP was taken

    # ── Telegram ──────────────────────────────────────────────

    def set_telegram_callback(self, fn):
        self._tg_send = fn

    def _alert(self, msg: str):
        logger.warning(msg)
        if self._tg_send:
            try:
                self._tg_send(msg)
            except Exception:
                pass

    # ── Daily Init ────────────────────────────────────────────

    def init_daily(self, equity: float):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.start_equity       = equity
        self.daily_trades       = 0
        self.today_wins         = 0
        self.today_losses       = 0
        self.consecutive_losses = 0
        self.session_trades     = {k: 0 for k in self.session_trades}
        self.today_date         = today
        self.stop_today         = False
        self.is_paused          = False
        self.manual_pause       = False
        logger.info("Daily state reset ? equity=%.2f date=%s", equity, today)

    def check_daily_reset(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.today_date:
            acct = self.gateway.get_account_info()
            eq   = acct["equity"] if acct else self.start_equity
            self.init_daily(eq)
            self._alert(f"New trading day started. Equity: ${eq:.2f}")

    # ── LAYER 1: Daily Drawdown Kill Switch ───────────────────

    DAILY_MAX_LOSS_USD: float = 500.0  # Hard dollar loss limit per trading day

    def is_daily_loss_limit_reached(self, current_equity: Optional[float] = None) -> bool:
        """Checks if daily loss circuit breaker has triggered."""
        if self.stop_today:
            return True
        if self.start_equity <= 0:
            return False
        
        eq = current_equity
        if eq is None and self.gateway:
            acct = self.gateway.get_account_info()
            if acct:
                eq = acct.get("equity", self.start_equity)
        
        if eq is not None:
            loss_usd = self.start_equity - eq
            if loss_usd >= self.DAILY_MAX_LOSS_USD:
                self.stop_today = True
                self._alert(
                    f"🚨 [CIRCUIT BREAKER] Daily loss limit reached: -${loss_usd:.2f} >= ${self.DAILY_MAX_LOSS_USD:.2f}. "
                    f"Trading halted for remainder of the day."
                )
                return True
        return False

    def check_daily_loss(self, current_equity: float) -> bool:
        """Active daily drawdown protection."""
        if self.is_daily_loss_limit_reached(current_equity):
            return False
        return True

    # ── LAYER 2: Daily Profit Target ──────────────────────────

    def check_profit_target(self, current_equity: float) -> bool:
        """Stop trading if daily profit target reached."""
        # User requested unlimited trading; profit target stop disabled.
        return True

    # ── LAYER 3: Lockfile ──────────────────────────────────────

    def _create_lockfile(self):
        data = {"locked_at": time.time(), "reason": "kill_switch"}
        try:
            os.makedirs(os.path.dirname(LOCKFILE), exist_ok=True)
            with open(LOCKFILE, "w") as f:
                json.dump(data, f)
        except Exception as exc:
            logger.error("Failed to create lockfile: %s", exc)

    def is_locked(self) -> bool:
        if not os.path.exists(LOCKFILE):
            return False
        try:
            with open(LOCKFILE, "r") as f:
                data = json.load(f)
            if time.time() - data.get("locked_at", 0) > 86400:
                os.remove(LOCKFILE)
                self._alert("Lockfile expired — auto-unlocked")
                return False
            return True
        except Exception:
            return False

    def force_unlock(self):
        if os.path.exists(LOCKFILE):
            os.remove(LOCKFILE)
            self._alert("Lockfile manually removed")

    def manual_resume(self):
        self.is_paused          = False
        self.manual_pause       = False
        self.stop_today         = False
        self.consecutive_losses = 0
        self.force_unlock()
        self._alert("SYSTEM RESUMED — all stops cleared")

    # ── LAYER 4: Consecutive Loss Pause ───────────────────────

    def on_trade_close(self, pnl_points: float):
        self.recent_pnls.append(pnl_points)
        if pnl_points >= 0:
            self.consecutive_losses = 0
            self.today_wins        += 1
        else:
            self.consecutive_losses += 1
            self.today_losses       += 1
            self.last_loss_time     = time.time()  # Track loss time for cooldown
            if self.consecutive_losses >= cfg.MAX_CONSECUTIVE_LOSSES:
                is_demo = True
                if self.gateway and hasattr(self.gateway, "get_account_info"):
                    acct = self.gateway.get_account_info()
                    if acct and (str(acct.get("trade_mode", "")).upper() in ("REAL", "LIVE")):
                        is_demo = False

                from config.quant_x_config import QX
                unrestricted_demo = (QX.get("demo_unrestricted_mode", False) and is_demo) or getattr(cfg, "FORCE_NEVER_PAUSE", False) or getattr(cfg, "MAXIMUM_TRADING_MODE", False)

                if unrestricted_demo:
                    logger.warning(
                        "[TESTING MODE] %d consecutive losses — auto-pause BYPASSED for continuous testing data collection.",
                        self.consecutive_losses
                    )
                    self._alert(
                        f"ℹ️ <b>[TESTING MODE]</b> {self.consecutive_losses} consecutive losses.\n"
                        f"Auto-pause PERMANENTLY BYPASSED for testing mode. Bot remains 100% active."
                    )
                else:
                    self.is_paused = True
                    self.pause_until = time.time() + cfg.COOLDOWN_AFTER_CONSEC_LOSSES
                    self._alert(
                        f"⏸ PAUSE — {self.consecutive_losses} consecutive losses.\n"
                        f"Cooling down for {cfg.COOLDOWN_AFTER_CONSEC_LOSSES}s.\n"
                        f"Send /resume to override."
                    )

    def check_auto_resume(self):
        if self.stop_today or self.manual_pause:
            return
        if self.is_paused and self.pause_until > 0 and time.time() >= self.pause_until:
            self.is_paused          = False
            self.consecutive_losses = 0
            self.pause_until        = 0.0
            self._alert("Auto-resumed after consecutive loss pause")

    # ── LAYER 5: Session Trade Limits ─────────────────────────

    def session_trades_ok(self, session: str) -> bool:
        limits = {
            "ASIAN":   cfg.ASIAN_MAX_TRADES,
            "LONDON":  cfg.LONDON_MAX_TRADES,
            "NY":      cfg.NY_MAX_TRADES,
            "OVERLAP": cfg.LONDON_MAX_TRADES,
        }
        return self.session_trades.get(session, 0) < limits.get(session, 10)

    def daily_trades_ok(self) -> bool:
        return self.daily_trades < cfg.MAX_DAILY_TRADES

    # ── LAYER 6: Structural Break-Even & Partial TP Monitor ──────

    def check_breakeven(self, position, pattern_tier: str = "scalp"):
        """
        LAYER 6: DISABLED - HFT PER-TICK MODIFICATION REMOVED
        
        STEP 5 FIX: Breakeven and SL modifications are removed.
        Entries now use COMPLETED candles only with initial SL/TP set at entry.
        No per-tick SL/TP modifications allowed.
        """
        return

    # ── LAYER 7: Trailing Stop ────────────────────────────────

    def check_trailing_stop(self, position, pattern_tier: str = "scalp"):
        """
        LAYER 7: DISABLED - HFT PER-TICK MODIFICATION REMOVED
        
        STEP 5 FIX: Trailing stop modifications are removed.
        Entries now use COMPLETED candles only with initial SL/TP set at entry.
        No per-tick SL/TP modifications allowed.
        """
        return


    # ── LAYER 8: Time Stop ────────────────────────────────────

    def check_time_stop(self, position) -> bool:
        # Disabled to prevent closing trades at a loss per user requirements.
        return False

    # ── DYNAMIC TP ENGINE v2 — MAXIMUM PURSUIT MODE ────────────────

    def check_dynamic_tp(self, position, gateway) -> None:
        """
        DISABLED - HFT PER-TICK MODIFICATION REMOVED
        
        STEP 5 FIX: Dynamic TP modifications are removed.
        Entries now use COMPLETED candles only with initial SL/TP set at entry.
        No per-tick SL/TP modifications allowed.
        """
        return
        try:
            pass
        except Exception as exc:
            pass

    def clear_dynamic_tp_state(self, ticket: int):
        """Call this when a trade closes to free memory."""
        self._peak_profit_pts.pop(ticket, None)
        self._last_tp_modify.pop(ticket, None)

    # ── LAYER 9: Equity Curve Filter ──────────────────────────

    def equity_curve_ok(self) -> bool:
        # User requested unlimited trading; equity curve filter disabled.
        return True

    # ── LAYER 10: Trades Per Minute Cap ────────────────────────

    def trades_per_minute_ok(self) -> bool:
        """Check if we haven't exceeded the trades-per-minute cap."""
        now = time.time()
        # Clean old timestamps (older than 60s)
        self.trade_timestamps = [t for t in self.trade_timestamps if now - t < 60]
        max_tpm = getattr(cfg, 'MAX_TRADES_PER_MINUTE', 30)
        return len(self.trade_timestamps) < max_tpm

    # ── LAYER 11: Loss Cooldown ───────────────────────────────

    def loss_cooldown_ok(self) -> bool:
        """Check if enough time has passed since the last loss."""
        if self.last_loss_time <= 0:
            return True
        cooldown = getattr(cfg, 'COOLDOWN_AFTER_LOSS_SEC', 30)
        return (time.time() - self.last_loss_time) >= cooldown

    # ── LAYER 12: Duplicate Direction Prevention ──────────────

    def direction_ok(self, symbol: str = "", direction: str = "") -> bool:
        """Prevent same-direction re-entry within a short window."""
        if not symbol or not direction:
            return True
        last = self.last_trade_info.get(symbol)
        if not last:
            return True
        window = getattr(cfg, 'NO_DUPLICATE_DIRECTION_SEC', 60)
        if last["direction"] == direction and (time.time() - last["time"]) < window:
            return False
        return True

    # ── Master Gate ───────────────────────────────────────────

    def calculate_current_drawdown(self, current_equity: float) -> float:
        """Calculate drawdown percentage relative to starting equity."""
        if self.start_equity <= 0:
            return 0.0
        if current_equity >= self.start_equity:
            return 0.0
        return ((self.start_equity - current_equity) / self.start_equity) * 100.0

    def get_cooldown_left(self) -> float:
        """Retrieve remaining time in seconds for global cooldown."""
        try:
            # Dynamically import to avoid circular dependencies
            import json
            STREAK_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "streak_state.json"))
            if os.path.exists(STREAK_FILE):
                with open(STREAK_FILE, "r") as f:
                    state = json.load(f)
                cooldown_until = state.get("cooldown_until")
                if cooldown_until:
                    return max(0.0, cooldown_until - time.time())
        except Exception:
            pass
        return 0.0

    def can_trade(self, session: str = "LONDON", symbol: str = "", direction: str = "", 
                  current_equity: float = 0.0, session_refresh_active: bool = False) -> bool:
        if getattr(cfg, "FORCE_NEVER_PAUSE", False) or getattr(cfg, "MAXIMUM_TRADING_MODE", False):
            self.is_paused = False
            self.manual_pause = False
            self.stop_today = False
            self.consecutive_losses = 0
            return True

        self.check_auto_resume()  # Check if we should auto-resume from pause
        if self.is_locked() or self.stop_today or self.manual_pause:
            return False
        
        # Enforce 45-minute session refresh block
        if session_refresh_active:
            return False

        # Enforce Drawdown Protection blocks (drawdown > 4% blocks entries)
        if current_equity > 0.0:
            dd = self.calculate_current_drawdown(current_equity)
            if dd >= cfg.DD_BLOCK_NEW_PCT:
                return False

        # Enforce global trade cooldown
        if self.get_cooldown_left() > 0:
            return False

        # Re-enable trades-per-minute and loss cooldown checks
        if not self.trades_per_minute_ok():
            return False
        if not self.loss_cooldown_ok():
            return False
        if symbol and direction and not self.direction_ok(symbol, direction):
            return False

        # ── MODULE 4: Layer 13 — CVaR Daily Tail-Loss Guard ─────────────
        # Blocks new entries when rolling tail loss exceeds CVAR_DAILY_LIMIT_USD.
        # Alert fires once per session to avoid flooding Telegram.
        try:
            from config.quant_x_config import QX
            if QX.flag("cvar_risk"):
                _cvar_limit = getattr(cfg, "CVAR_DAILY_LIMIT_USD", 50.0)
                _cvar_val   = self.cvar_estimate()
                if _cvar_val < 0 and abs(_cvar_val) > _cvar_limit:
                    if not self._cvar_alert_sent:
                        self._alert(
                            f"🛑 <b>[CVAR GUARD]</b> Daily tail loss CVaR={_cvar_val:.2f} "
                            f"exceeds limit ${_cvar_limit:.2f}. New entries blocked."
                        )
                        self._cvar_alert_sent = True
                    logger.warning(
                        "[CVAR GUARD] CVaR=%.2f > limit %.2f — blocking entry",
                        _cvar_val, _cvar_limit
                    )
                    return False
                elif _cvar_val >= 0 or abs(_cvar_val) <= _cvar_limit:
                    self._cvar_alert_sent = False  # Reset alert when guard clears
        except Exception as _cvar_ex:
            logger.debug("[CVAR GUARD] Check failed (non-fatal): %s", _cvar_ex)

        return True

    def on_trade_open(self, session: str, ticket: int, direction: str = "", symbol: str = ""):
        self.daily_trades += 1
        self.session_trades[session] = self.session_trades.get(session, 0) + 1
        self.open_trade_times[ticket] = time.time()
        self.trade_timestamps.append(time.time())
        # Track last trade direction per symbol
        if symbol and direction:
            self.last_trade_info[symbol] = {"direction": direction, "time": time.time()}

    def override_lot(self, lot: float):
        self.lot_override = lot
        logger.info(f"Lot size override set to {lot}")

    # ── QUANT X Extensions (non-destructive) ────────────────────

    def calculate_position_size(
        self,
        symbol: str,
        sl_points: float,
        equity: float = 0.0,
        risk_pct: float = 0.01,
        fixed_risk_usd: float = 0.0
    ) -> float:
        """
        Computes lot size to target a CONSTANT dollar-risk per trade.
        Formula: Lot = Target_Dollar_Risk / (SL_points * Point_Value_Per_Lot)

        INVARIANT: A trade with a 500-point SL risks the exact same dollar amount as a trade with a 150-point SL.

        Args:
            symbol: Trading symbol (e.g. "XAUUSD")
            sl_points: Stop Loss distance in points (e.g. 150 to 500)
            equity: Account equity (if 0.0, fetches from gateway or start_equity)
            risk_pct: Target risk fraction of equity (default 0.01 = 1%)
            fixed_risk_usd: If > 0, overrides risk_pct to use a fixed dollar risk

        Returns:
            Lot size rounded to 2 decimal places, clamped between min_lot and max_lot.
        """
        if getattr(self, "lot_override", 0.0) > 0.0:
            return self.lot_override

        sym_cfg = cfg.get_symbol_config(symbol)
        min_lot = sym_cfg.get("min_lot", 0.01)
        max_lot = getattr(cfg, "MAX_LOT", 1.0)

        if equity <= 0.0:
            if self.gateway:
                try:
                    acct = self.gateway.get_account_info()
                    equity = acct.get("equity", 0.0) if acct else 0.0
                except Exception:
                    equity = 0.0
            if equity <= 0.0:
                equity = getattr(self, "start_equity", 1000.0)
            if equity <= 0.0:
                equity = 1000.0

        target_usd = fixed_risk_usd if fixed_risk_usd > 0.0 else (equity * risk_pct)
        
        # Point value per 1.0 lot ($ per point for 1.0 lot)
        # XAUUSD: 1 point ($0.01 price move) = $1.00 per 1.0 lot ($0.01 per 0.01 lot)
        point_val = 1.0

        if sl_points <= 0 or point_val <= 0:
            return min_lot

        raw_lot = target_usd / (sl_points * point_val)
        # Floor round to 2 decimal places to ensure actual risk never exceeds target_usd due to rounding
        floored_lot = math.floor(raw_lot * 100.0) / 100.0
        clamped_lot = round(max(min_lot, min(max_lot, floored_lot)), 2)
        return clamped_lot

    def volatility_scaled_lot(self, symbol: str, current_atr: float, base_lot: float, sl_points: float = 0.0) -> float:
        """
        Computes volatility-scaled position sizing targeting constant $-risk.
        If sl_points > 0, uses SL points directly; otherwise uses ATR-derived points.
        """
        try:
            from config.quant_x_config import QX
            if sl_points > 0.0:
                return self.calculate_position_size(symbol=symbol, sl_points=sl_points)

            if not QX.flag("volatility_scaled_lot") or current_atr <= 0:
                return base_lot

            acct = self.gateway.get_account_info() if self.gateway else None
            equity = acct.get("equity", 0.0) if (acct and "equity" in acct) else getattr(self, "start_equity", 1000.0)

            point = 0.01 if "XAU" in symbol.upper() else 0.00001
            atr_pts = current_atr / point if point > 0 else current_atr

            return self.calculate_position_size(symbol=symbol, sl_points=atr_pts, equity=equity)
        except Exception as e:
            logger.warning(f"Failed to calculate volatility scaled lot: {e}")
            return base_lot


    def check_cost_adjusted_edge(self, symbol: str, tp_pts: int, sl_pts: int, spread_pts: float, win_prob: float = None) -> dict:
        """
        Issue 3 Fix: Cost & Spread-Adjusted Expected Value (EV) Gate.
        
        Calculates round-trip transaction cost (spread + commission) and checks:
        1. TP distance >= 3.0 * round_trip_cost (clears cost by 3x margin)
        2. Expected Value (EV) after round-trip cost is strictly > 0.0

        Args:
            symbol: Trading symbol ("XAUUSD", "EURUSD", etc.)
            tp_pts: Planned TP distance in points
            sl_pts: Planned SL distance in points
            spread_pts: Current market spread in points
            win_prob: Win probability (if None, dynamically fetches rolling win rate from DB)

        Returns:
            {"approved": bool, "ev_usd": float, "cost_pts": float, "min_tp_required": int, "rejection_reason": str}
        """
        if win_prob is None or win_prob <= 0.0:
            try:
                from modules.performance import get_rolling_win_rate
                win_prob = get_rolling_win_rate(last_n=20, default=0.55)
            except Exception:
                win_prob = 0.55

        is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
        # Estimated commission in points (Exness/RoboForex cent/standard: ~$0.05-$0.10 per 0.01 lot on Gold = 5-10 points)
        commission_pts = 10.0 if is_gold else 4.0
        round_trip_cost_pts = max(1.0, spread_pts + commission_pts)

        # Mandatory TP floor: TP must be at least 3x round-trip cost
        min_tp_required = int(math.ceil(round_trip_cost_pts * 3.0))

        # EV Calculation (in points):
        # EV = (Win_Prob * (TP - Cost)) - ((1 - Win_Prob) * (SL + Cost))
        net_win_pts  = tp_pts - round_trip_cost_pts
        net_loss_pts = sl_pts + round_trip_cost_pts
        ev_pts       = (win_prob * net_win_pts) - ((1.0 - win_prob) * net_loss_pts)

        # Dollar EV conversion for 0.01 lot
        point_val = 0.01 if is_gold else 0.0001
        ev_usd    = ev_pts * point_val

        approved = True
        rejection_reason = ""

        if tp_pts < min_tp_required:
            approved = False
            rejection_reason = (
                f"TP distance ({tp_pts}pts) < 3.0x round-trip cost ({round_trip_cost_pts:.1f}pts -> min TP {min_tp_required}pts required). "
                f"Risk of $0.00 close on TP hit."
            )
        elif ev_pts <= 0.0:
            approved = False
            rejection_reason = (
                f"Negative cost-adjusted EV ({ev_pts:.1f}pts / ${ev_usd:.2f}). "
                f"Spread ({spread_pts:.0f}pts) + Commission ({commission_pts:.0f}pts) eats edge."
            )

        logger.info(
            f"[COST CHECK] {symbol} TP:{tp_pts}pts SL:{sl_pts}pts Spread:{spread_pts:.0f}pts "
            f"Cost:{round_trip_cost_pts:.1f}pts minTP:{min_tp_required}pts EV:{ev_pts:.1f}pts (${ev_usd:.2f}) "
            f"Approved:{approved} {rejection_reason}"
        )

        return {
            "approved": approved,
            "ev_pts": round(ev_pts, 2),
            "ev_usd": round(ev_usd, 3),
            "cost_pts": round(round_trip_cost_pts, 1),
            "min_tp_required": min_tp_required,
            "rejection_reason": rejection_reason
        }

    def atr_scaled_sl_tp(self, symbol: str, atr_pts: float, confidence: int = 50, spread_pts: float = 20.0) -> dict:
        """
        Returns ATR-regime-aware SL and TP distances in points (Phase 2).
        SL = clamp(ATR(14) * k, 150, 400) points.
        Scalp TP floor = 350 to 600 points to clear broker spread drag (Issue 3 Fix).

        Args:
            symbol:     Trading symbol (e.g. "XAUUSD")
            atr_pts:    Current ATR in points (pass 0.0 to use safe defaults)
            confidence: Brain confidence score — higher confidence extends TP slightly
            spread_pts: Current spread in points to enforce cost clearance

        Returns:
            {"sl_pts": int, "tp_pts": int, "rr_ratio": float, "regime": str}
        """
        is_gold = ("XAU" in symbol.upper())
        commission_pts = 10.0 if is_gold else 4.0
        round_trip_cost = max(1.0, spread_pts + commission_pts)

        if is_gold:
            sl_floor = 150  # 150 pts ($1.50 Gold move) - sits outside 1-minute noise
            sl_cap   = 400  # 400 pts ($4.00 Gold move)
            # Ensure TP floor clears round-trip cost by at least 3x
            tp_floor = max(390, int(math.ceil(round_trip_cost * 3.0)))
            tp_cap   = 600  # 600 pts ($6.00 Gold move max scalp target)

            k_multiplier = 1.8  # k tuned against Phase 0 MAE data
            if atr_pts > 0:
                raw_sl = atr_pts * k_multiplier
                sl = int(max(sl_floor, min(sl_cap, raw_sl)))
                
                # Scalp R:R ratio = 2.0x to 2.5x depending on confidence
                rr_target = 2.0 if confidence < 70 else 2.5
                raw_tp = sl * rr_target
                tp = int(max(tp_floor, min(tp_cap, raw_tp)))
                regime = "atr_scaled"
            else:
                regime = "default_safe"
                sl = sl_floor  # 150 pts
                tp = max(tp_floor, sl_floor * 2)  # 390 pts (>= 2.6R)

            if confidence >= 70:
                tp = min(tp_cap, tp + 50)

        else:
            sl_floor = 40
            sl_cap   = 120
            tp_floor = max(80, int(math.ceil(round_trip_cost * 3.0)))
            tp_cap   = 200

            if atr_pts > 0:
                regime = "atr_scaled"
                sl = int(max(sl_floor, min(sl_cap, atr_pts * 1.5)))
                tp = int(max(tp_floor, min(tp_cap, sl * 2.0)))
            else:
                regime = "default"
                sl = sl_floor
                tp = max(tp_floor, sl_floor * 2)

        # Hard guarantees: TP must clear 2.0x SL and 3x cost
        sl = max(sl, sl_floor)
        tp = max(tp, max(int(sl * 2.0), int(math.ceil(round_trip_cost * 3.0))))
        rr = round(tp / sl, 2) if sl > 0 else 0.0

        logger.debug(
            "[RiskMgr] atr_scaled_sl_tp %s atr=%.1fpts regime=%s sl=%dpts tp=%dpts rr=%.2f spread=%.0fpts",
            symbol, atr_pts, regime, sl, tp, rr, spread_pts
        )
        return {"sl_pts": sl, "tp_pts": tp, "rr_ratio": rr, "regime": regime}

    def dual_tier_sl_tp(
        self,
        symbol: str,
        tier: str,                  # "scalp" or "pro_trend"
        direction: str,             # "BUY" or "SELL"
        entry_price: float,
        invalidation_level: float,
        atr_pts: float = 0.0,
        point: float = 0.01
    ) -> dict:
        """
        SECTION 3 — DUAL-TIER SL/TP ENGINE (extends ATR-scaled plan)
        
        Tier Scalp (small pattern):
          - SL: 150-200 pts, or beyond invalidation_level (whichever wider)
          - TP: 350-600 pts
          - Min R:R: >= 2.0
          
        Tier Pro Trend (big pattern continuation):
          - SL: 300-500 pts, or beyond invalidation_level (whichever wider)
          - TP: 1000-2500 pts
          - Min R:R: >= 3.0
          
        Rules:
          - SL is never tighter than structural invalidation level.
          - If computed R:R < min_rr, reject the trade (approved=False). Do NOT shrink SL to force R:R.
        """
        is_gold = ("XAU" in symbol.upper())
        pt = point if point > 0 else (0.01 if is_gold else 0.00001)

        # Calculate structural SL in points
        structural_sl_pts = 0
        if invalidation_level > 0 and entry_price > 0:
            if direction.upper() in ("BUY", "BULLISH"):
                structural_sl_pts = int(math.ceil((entry_price - invalidation_level) / pt))
            elif direction.upper() in ("SELL", "BEARISH"):
                structural_sl_pts = int(math.ceil((invalidation_level - entry_price) / pt))

        structural_sl_pts = max(0, structural_sl_pts)

        if tier.lower() == "scalp":
            sl_floor, sl_cap = 150, 200
            tp_floor, tp_cap = 390, 600
            min_rr = 2.0
        else:  # pro_trend
            sl_floor, sl_cap = 300, 500
            tp_floor, tp_cap = 1000, 2500
            min_rr = 3.0

        if not is_gold:
            sl_floor = int(sl_floor * 0.2)
            sl_cap   = int(sl_cap * 0.2)
            tp_floor = int(tp_floor * 0.2)
            tp_cap   = int(tp_cap * 0.2)

        # SL determination: wider of floor or structural SL
        raw_sl = max(sl_floor, structural_sl_pts)
        if atr_pts > 0:
            raw_sl = max(raw_sl, int(atr_pts * 1.5))
            
        sl_pts = max(structural_sl_pts, min(sl_cap, raw_sl)) if structural_sl_pts <= sl_cap else structural_sl_pts

        # TP determination: target based on min_rr with room up to tp_cap
        target_tp = int(sl_pts * min_rr)
        tp_pts = max(tp_floor, min(tp_cap, target_tp))

        computed_rr = round(tp_pts / sl_pts, 2) if sl_pts > 0 else 0.0

        approved = True
        rejection_reason = ""

        if computed_rr < min_rr:
            approved = False
            rejection_reason = f"Computed R:R ({computed_rr:.2f}) is below tier '{tier}' minimum ({min_rr:.1f})"

        logger.info(
            f"[RiskMgr] Dual-Tier SL/TP ({tier}): {symbol} {direction} entry={entry_price:.2f} "
            f"inval={invalidation_level:.2f} -> SL:{sl_pts}pts TP:{tp_pts}pts RR:{computed_rr} "
            f"approved={approved} {rejection_reason}"
        )

        return {
            "approved": approved,
            "sl_pts": sl_pts,
            "tp_pts": tp_pts,
            "rr_ratio": computed_rr,
            "tier": tier,
            "rejection_reason": rejection_reason,
            "min_rr": min_rr
        }

    def validate_directional_sl_tp(self, symbol: str, direction: str, entry_price: float, sl_price: float, tp_price: float) -> dict:
        """
        Directional SL/TP Validation Guard:
        Ensures BUY orders strictly have SL < entry_price and TP > entry_price.
        Ensures SELL orders strictly have SL > entry_price and TP < entry_price.
        """
        if not direction or entry_price <= 0.0:
            return {"approved": True, "rejection_reason": ""}
        
        dir_norm = direction.upper().strip()
        is_buy = dir_norm in ("BUY", "BULLISH")
        is_sell = dir_norm in ("SELL", "BEARISH")
        
        if is_buy:
            if sl_price > 0.0 and sl_price >= entry_price:
                return {
                    "approved": False,
                    "rejection_reason": f"BUY SL Violation: SL ({sl_price:.5f}) >= Entry ({entry_price:.5f})"
                }
            if tp_price > 0.0 and tp_price <= entry_price:
                return {
                    "approved": False,
                    "rejection_reason": f"BUY TP Violation: TP ({tp_price:.5f}) <= Entry ({entry_price:.5f})"
                }
        elif is_sell:
            if sl_price > 0.0 and sl_price <= entry_price:
                return {
                    "approved": False,
                    "rejection_reason": f"SELL SL Violation: SL ({sl_price:.5f}) <= Entry ({entry_price:.5f})"
                }
            if tp_price > 0.0 and tp_price >= entry_price:
                return {
                    "approved": False,
                    "rejection_reason": f"SELL TP Violation: TP ({tp_price:.5f}) >= Entry ({entry_price:.5f})"
                }
                
        return {"approved": True, "rejection_reason": ""}




    def cvar_estimate(self, alpha: float = 0.05) -> float:
        """
        Calculates Conditional Value at Risk (Expected Shortfall) at alpha level
        over the rolling recent P&L history.
        """
        if len(self.recent_pnls) < 5:
            return 0.0
        try:
            pnls = sorted(list(self.recent_pnls))
            cutoff = int(len(pnls) * alpha)
            cutoff = max(1, cutoff)
            tail_pnls = pnls[:cutoff]
            return round(sum(tail_pnls) / len(tail_pnls), 2)
        except Exception:
            return 0.0

    def margin_buffer_check(self, account: dict) -> bool:
        """
        Verifies if current margin level is above the safety margin threshold.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("margin_buffer_check"):
                return True
            
            margin_level = account.get("margin_level", 0.0)
            # Standard MT5 margin level is in percentage (e.g. 500 = 500%)
            # If margin level goes below margin_buffer_pct (e.g. 200%), block trades
            buffer_pct = float(QX.get("margin_buffer_pct") or 0.20) * 1000.0  # 200% default
            
            if 0.0 < margin_level < buffer_pct:
                logger.warning(f"[RISK] Margin level {margin_level:.1f}% below buffer limit {buffer_pct:.1f}%")
                return False
        except Exception as e:
            logger.warning(f"Margin buffer check error: {e}")
        return True

    def volatility_circuit_breaker(self, symbol: str, current_atr: float, baseline_atr: float) -> bool:
        """
        Auto-pauses entries if volatility exceeds the historical average by a set multiplier.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("volatility_circuit_breaker"):
                return False
            
            mult = float(QX.get("circuit_breaker_atr_multiple") or 3.0)
            if baseline_atr > 0 and current_atr > baseline_atr * mult:
                logger.warning(f"[CIRCUIT BREAKER] {symbol} ATR ({current_atr:.5f}) exceeded baseline x{mult} ({baseline_atr:.5f})")
                return True
        except Exception as e:
            logger.warning(f"Circuit breaker check error: {e}")
        return False

    def correlation_exposure_check(self, symbol: str, direction: str) -> bool:
        """
        Detects and blocks stacked same-direction exposure across concurrent positions.
        """
        try:
            # Check active open positions in gateway
            positions = self.gateway.get_open_positions()
            if not positions:
                return True
            
            same_dir_count = 0
            for pos in positions:
                pos_dir = "BUY" if pos.type == 0 else "SELL"
                if pos.symbol == symbol and pos_dir == direction:
                    same_dir_count += 1
            
            # If we already have 2 positions in same direction, block additional
            if same_dir_count >= 2:
                logger.warning(f"[RISK] Correlation limit hit: {same_dir_count} positions of {symbol} in direction {direction}")
                return False
        except Exception as e:
            logger.warning(f"Correlation exposure check error: {e}")
        return True

    # ── Helpers ───────────────────────────────────────────────

    def _position_profit_pts(self, position) -> float:
        info = self.gateway.symbols_data.get(position.symbol)
        if not info or info["point"] <= 0:
            return 0.0
        if position.type == 0:  # BUY
            return (position.price_current - position.price_open) / info["point"]
        return (position.price_open - position.price_current) / info["point"]

    def get_status_report(self, current_equity: float) -> str:
        profit = current_equity - self.start_equity
        sign   = "+" if profit >= 0 else ""
        status = "ACTIVE"
        if self.is_locked():   status = "LOCKED"
        elif self.stop_today:  status = "STOPPED"
        elif self.is_paused:   status = "PAUSED"

        cvar = self.cvar_estimate()

        return (
            f"SYSTEM STATUS\n"
            f"Status    : {status}\n"
            f"Equity    : ${current_equity:.2f}\n"
            f"PnL Today : {sign}${profit:.2f} / target ${cfg.DAILY_PROFIT_TARGET}\n"
            f"Trades    : {self.daily_trades} ({self.today_wins}W/{self.today_losses}L)\n"
            f"Consec L  : {self.consecutive_losses}/{cfg.MAX_CONSECUTIVE_LOSSES}\n"
            f"CVaR (5%) : ${cvar:.2f}\n"
        )

    def kelly_lot_compute(
        self,
        symbol: str,
        sl_pts: float,
        base_lot: float,
    ) -> float:
        """
        Compute position size via fractional Kelly if the flag is on.
        Returns base_lot unchanged if:
          - kelly_sizing flag is off
          - kelly_sizer returns 0.0 (negative edge / insufficient data)
          - any exception occurs

        Updates self._kelly_lot_last and self._kelly_hard_cap_active.
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("kelly_sizing"):
                return base_lot

            acct = self.gateway.get_account_info()
            equity = acct["equity"] if acct else self.start_equity
            if equity <= 0:
                return base_lot

            sym_cfg   = cfg.get_symbol_config(symbol)
            pip_value = sym_cfg.get("pip_value_per_lot", 1.0)

            # Dollar risk per 1.0 lot at the current SL distance
            risk_per_lot = sl_pts * pip_value
            if risk_per_lot <= 0:
                return base_lot

            from brain.kelly_sizer import compute_kelly_lot
            kelly_lot, meta = compute_kelly_lot(
                equity=equity,
                risk_per_lot=risk_per_lot,
                rolling_n=getattr(cfg, "KELLY_ROLLING_N", 100),
                kelly_fraction=getattr(cfg, "KELLY_FRACTION", 0.25),
                max_lot_cap=sym_cfg.get("max_lot", base_lot),
                max_risk_pct=getattr(cfg, "KELLY_MAX_RISK_PCT", 0.02),
            )

            if kelly_lot <= 0:
                logger.debug(
                    "[KELLY] Negative edge or insufficient data — using base_lot=%.2f",
                    base_lot
                )
                return base_lot

            self._kelly_lot_last        = kelly_lot
            self._kelly_hard_cap_active = meta.get("hard_cap_active", False)
            logger.info(
                "[KELLY] %s sl=%.0fpts risk_per_lot=$%.2f blended_wr=%.1f%% "
                "→ kelly=%.2f (hard_cap=%s)",
                symbol, sl_pts, risk_per_lot,
                (meta.get("blended_win_rate") or 0) * 100,
                kelly_lot,
                "ACTIVE" if self._kelly_hard_cap_active else "inactive",
            )
            return kelly_lot

        except Exception as exc:
            logger.error("[KELLY] kelly_lot_compute error: %s ? using base_lot", exc)
            return base_lot

    def get_status_dict(self) -> dict:
        return {
            "daily_trades":         self.daily_trades,
            "session_trades":       dict(self.session_trades),
            "consecutive_losses":   self.consecutive_losses,
            "is_paused":            self.is_paused,
            "manual_pause":         self.manual_pause,
            "is_locked":            self.is_locked(),
            "stop_today":           self.stop_today,
            "today_wins":           self.today_wins,
            "today_losses":         self.today_losses,
            "start_equity":         self.start_equity,
            "cvar":                 self.cvar_estimate(),
            # Module 4 additions
            "kelly_lot":            self._kelly_lot_last,
            "kelly_hard_cap_active": self._kelly_hard_cap_active,
        }

