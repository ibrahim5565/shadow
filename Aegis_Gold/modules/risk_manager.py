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
        logger.info("Daily state reset — equity=%.2f date=%s", equity, today)

    def check_daily_reset(self):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self.today_date:
            acct = self.gateway.get_account_info()
            eq   = acct["equity"] if acct else self.start_equity
            self.init_daily(eq)
            self._alert(f"New trading day started. Equity: ${eq:.2f}")

    # ── LAYER 1: Daily Drawdown Kill Switch ───────────────────

    def check_daily_loss(self, current_equity: float) -> bool:
        # User requested unlimited trading; daily drawdown limit disabled.
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

    # ── LAYER 6: Break-Even Monitor ───────────────────────────

    def check_breakeven(self, position):
        try:
            symbol     = position.symbol
            profit_pts = self._position_profit_pts(position)
            trigger_pts = cfg.get_symbol_config(symbol).get("breakeven_trigger_pts", cfg.BREAKEVEN_TRIGGER_PTS)
            guaranteed_pts = getattr(cfg, 'GUARANTEED_BREAKEVEN_PROFIT_PTS', 10)
            
            info = self.gateway.symbols_data.get(symbol, {})
            point = info.get("point", 0.00001)
            digits = info.get("digits", 5)
            if point <= 0:
                return

            if profit_pts >= trigger_pts:
                if position.type == 0:  # BUY
                    be_sl = round(position.price_open + guaranteed_pts * point, digits)
                    if position.sl < be_sl:
                        ok = self.gateway.modify_sl(position.ticket, symbol, be_sl)
                        if ok:
                            self._alert(f"Profit lock-in set (+{guaranteed_pts}pts) — {symbol} #{position.ticket}")
                else:  # SELL
                    be_sl = round(position.price_open - guaranteed_pts * point, digits)
                    if position.sl == 0 or position.sl > be_sl:
                        ok = self.gateway.modify_sl(position.ticket, symbol, be_sl)
                        if ok:
                            self._alert(f"Profit lock-in set (+{guaranteed_pts}pts) — {symbol} #{position.ticket}")
        except Exception as exc:
            logger.error("Breakeven error: %s", exc)

    # ── LAYER 7: Trailing Stop ────────────────────────────────

    def check_trailing_stop(self, position):
        try:
            symbol     = position.symbol
            profit_pts = self._position_profit_pts(position)
            if profit_pts < cfg.TRAIL_TRIGGER_PTS:
                return

            info = self.gateway.symbols_data.get(symbol)
            if not info:
                return

            point  = info["point"]
            digits = info["digits"]

            if position.type == 0:  # BUY
                new_sl = round(position.price_current - cfg.TRAIL_DISTANCE_PTS * point, digits)
                if new_sl > position.sl:
                    self.gateway.modify_sl(position.ticket, symbol, new_sl)
            else:  # SELL
                new_sl = round(position.price_current + cfg.TRAIL_DISTANCE_PTS * point, digits)
                if position.sl == 0 or new_sl < position.sl:
                    self.gateway.modify_sl(position.ticket, symbol, new_sl)
        except Exception as exc:
            logger.error("Trailing stop error: %s", exc)

    # ── LAYER 8: Time Stop ────────────────────────────────────

    def check_time_stop(self, position) -> bool:
        # Disabled to prevent closing trades at a loss per user requirements.
        return False

    # ── DYNAMIC TP ENGINE v2 — MAXIMUM PURSUIT MODE ────────────────

    def check_dynamic_tp(self, position, gateway) -> None:
        """
        FIRST 200 TRADES MODE - MAXIMUM PURSUIT Dynamic Take-Profit Engine v3.

        Three auto-selecting modes:
          RECOVERY MODE  — 1+ losses today: TP chases price at 3x speed
                           to recover losses in one big move.
          PURSUIT MODE   — In profit, price moving our way:
                           TP pushed continuously AHEAD of price.
          LOCK-IN MODE   — Price reversing after peak:
                           TP snapped tight to bank gains immediately.

        Gold:  updates every 15s, 80pt buffer, 100pt extensions, 3x recovery.
        EURUSD: updates every 20s, 15pt buffer, 20pt extensions, 2x recovery.
        
        FIRST 200 TRADES: Pursue BIGGER profits - wider buffers, longer hold times.
        """
        try:
            ticket  = position.ticket
            symbol  = position.symbol
            is_gold = ("XAU" in symbol or symbol == "XAUUSD")

            # FIRST 200 TRADES MODE: BIGGER PURSUIT PARAMETERS
            if is_gold:
                min_profit_to_pursue  = 10   # INCREASED: Wait for 10pts minimum before pursuing
                pursue_buffer_pts     = 80   # INCREASED: 80pt buffer (was 40)
                extend_trigger_pts    = 30   # INCREASED: 30pts trigger (was 15)
                extend_chunk_pts      = 100  # INCREASED: 100pt extensions (was 50)
                lock_in_pullback_pct  = 0.40 # INCREASED: Lock in only at 40% pullback (was 30%)
                lock_in_buffer_pts    = 15   # INCREASED: 15pt buffer on lock-in (was 8)
                throttle_sec          = 15   # Updates every 15s
                recovery_multiplier   = 3.0
            else:
                min_profit_to_pursue  = 3
                pursue_buffer_pts     = 15   # INCREASED: 15pt buffer (was 8)
                extend_trigger_pts    = 8
                extend_chunk_pts      = 20   # INCREASED: 20pt extensions (was 10)
                lock_in_pullback_pct  = 0.40 # INCREASED: 40% pullback tolerance
                lock_in_buffer_pts    = 5
                throttle_sec          = 20
                recovery_multiplier   = 2.0

            now      = time.time()
            last_mod = self._last_tp_modify.get(ticket, 0)
            if now - last_mod < throttle_sec:
                return

            profit_pts    = self._position_profit_pts(position)
            info          = self.gateway.symbols_data.get(symbol, {})
            point         = info.get("point", 0.00001)
            digits        = info.get("digits", 5)
            if point <= 0:
                return

            current_price = position.price_current
            is_buy        = (position.type == 0)
            current_tp    = position.tp

            prev_peak = self._peak_profit_pts.get(ticket, 0.0)
            if profit_pts > prev_peak:
                self._peak_profit_pts[ticket] = profit_pts
            peak_profit = self._peak_profit_pts.get(ticket, 0.0)

            if profit_pts < min_profit_to_pursue:
                return

            losses_today      = self.today_losses + self.consecutive_losses
            in_recovery       = losses_today > 0
            active_multiplier = recovery_multiplier if in_recovery else 1.0
            mode_label        = "RECOVERY" if in_recovery else "PURSUIT"

            effective_buffer = pursue_buffer_pts * active_multiplier
            effective_chunk  = extend_chunk_pts  * active_multiplier

            new_tp = None
            reason = ""

            pullback_now     = peak_profit - profit_pts
            pullback_pct_now = (pullback_now / peak_profit) if peak_profit > 0 else 0.0
            is_reversing     = (
                peak_profit >= min_profit_to_pursue * 3 and
                pullback_pct_now >= lock_in_pullback_pct
            )

            if is_reversing:
                if is_buy:
                    snap_tp = current_price + lock_in_buffer_pts * point
                    if current_tp == 0 or snap_tp < current_tp:
                        new_tp = snap_tp
                        reason = (f"LOCK-IN [{mode_label}] peak={peak_profit:.0f}pts "
                                  f"back={pullback_now:.0f}pts ({pullback_pct_now*100:.0f}%)")
                else:
                    snap_tp = current_price - lock_in_buffer_pts * point
                    if current_tp == 0 or snap_tp > current_tp:
                        new_tp = snap_tp
                        reason = (f"LOCK-IN [{mode_label}] peak={peak_profit:.0f}pts "
                                  f"back={pullback_now:.0f}pts ({pullback_pct_now*100:.0f}%)")
            else:
                if is_buy:
                    pursued_tp = current_price + effective_buffer * point
                    if current_tp == 0 or pursued_tp > current_tp:
                        new_tp = pursued_tp
                        reason = (f"PURSUE [{mode_label} x{active_multiplier:.0f}] "
                                  f"profit={profit_pts:.0f}pts chasing +{effective_buffer:.0f}pts ahead")
                else:
                    pursued_tp = current_price - effective_buffer * point
                    if current_tp == 0 or pursued_tp < current_tp:
                        new_tp = pursued_tp
                        reason = (f"PURSUE [{mode_label} x{active_multiplier:.0f}] "
                                  f"profit={profit_pts:.0f}pts chasing +{effective_buffer:.0f}pts ahead")

                if new_tp is None and current_tp != 0:
                    pts_to_tp = (
                        (current_tp - current_price) / point if is_buy
                        else (current_price - current_tp) / point
                    )
                    if pts_to_tp <= extend_trigger_pts:
                        if is_buy:
                            new_tp = current_tp + effective_chunk * point
                        else:
                            new_tp = current_tp - effective_chunk * point
                        reason = (f"EXTEND [{mode_label} x{active_multiplier:.0f}] "
                                  f"{pts_to_tp:.0f}pts to TP — adding {effective_chunk:.0f}pts")

            if new_tp is not None:
                new_tp_r = round(new_tp, digits)
                ok = gateway.modify_tp(ticket, symbol, new_tp_r)
                if ok:
                    self._last_tp_modify[ticket] = now
                    old_str = f"{current_tp:.5f}" if current_tp else "NONE"
                    tp_delta = abs(new_tp_r - current_tp) / point if current_tp else 0
                    logger.info(
                        f"[DynamicTP v2] {symbol} #{ticket} | {reason} | "
                        f"{old_str} → {new_tp_r:.5f} (+{tp_delta:.0f}pts) | "
                        f"profit={profit_pts:.0f}pts peak={peak_profit:.0f}pts"
                    )
                    if tp_delta >= extend_trigger_pts and self._tg_send:
                        emoji = "🔴" if "LOCK-IN" in reason else ("🚀" if in_recovery else "🟡")
                        try:
                            self._tg_send(
                                f"{emoji} <b>[DynamicTP] {symbol} #{ticket}</b>\n"
                                f"Mode: <b>{mode_label}</b>"
                                f"{' (x' + str(int(active_multiplier)) + ' boost)' if in_recovery else ''}\n"
                                f"New TP: <code>{new_tp_r:.5f}</code> (+{tp_delta:.0f}pts)\n"
                                f"Profit: {profit_pts:.0f}pts | Peak: {peak_profit:.0f}pts"
                            )
                        except Exception:
                            pass

        except Exception as exc:
            logger.error(f"check_dynamic_tp error #{getattr(position, 'ticket', '?')}: {exc}")

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


    def atr_scaled_sl_tp(self, symbol: str, atr_pts: float, confidence: int = 50) -> dict:
        """
        Returns ATR-regime-aware SL and TP distances in points (Phase 2).
        SL = clamp(ATR(14) * k, 150, 400) points.
        Scalp TP floor = 350 to 600 points to clear broker spread drag.

        Args:
            symbol:     Trading symbol (e.g. "XAUUSD")
            atr_pts:    Current ATR in points (pass 0.0 to use safe defaults)
            confidence: Brain confidence score — higher confidence extends TP slightly

        Returns:
            {"sl_pts": int, "tp_pts": int, "rr_ratio": float, "regime": str}
        """
        is_gold = ("XAU" in symbol.upper())

        if is_gold:
            sl_floor = 150  # 150 pts ($1.50 Gold move) - sits outside 1-minute noise
            sl_cap   = 400  # 400 pts ($4.00 Gold move)
            tp_floor = 350  # 350 pts ($3.50 Gold move) - clears 15-35pt spread drag
            tp_cap   = 600  # 600 pts ($6.00 Gold move max scalp target)

            k_multiplier = 1.8  # k tuned against Phase 0 MAE data
            if atr_pts > 0:
                raw_sl = atr_pts * k_multiplier
                sl = int(max(sl_floor, min(sl_cap, raw_sl)))
                
                # Scalp R:R ratio = 1.8x to 2.2x depending on confidence
                rr_target = 1.8 if confidence < 70 else 2.2
                raw_tp = sl * rr_target
                tp = int(max(tp_floor, min(tp_cap, raw_tp)))
                regime = "atr_scaled"
            else:
                regime = "default_safe"
                sl = sl_floor  # 150 pts
                tp = tp_floor  # 350 pts

            if confidence >= 70:
                tp = min(tp_cap, tp + 50)

        else:
            sl_floor = 40
            sl_cap   = 120
            tp_floor = 80
            tp_cap   = 200

            if atr_pts > 0:
                regime = "atr_scaled"
                sl = int(max(sl_floor, min(sl_cap, atr_pts * 1.5)))
                tp = int(max(tp_floor, min(tp_cap, sl * 1.8)))
            else:
                regime = "default"
                sl = sl_floor
                tp = tp_floor

        # Hard guarantees
        sl = max(sl, sl_floor)
        tp = max(tp, int(sl * 1.5))
        rr = round(tp / sl, 2) if sl > 0 else 0.0

        logger.debug(
            "[RiskMgr] atr_scaled_sl_tp %s atr=%.1fpts regime=%s sl=%dpts tp=%dpts rr=%.2f",
            symbol, atr_pts, regime, sl, tp, rr
        )
        return {"sl_pts": sl, "tp_pts": tp, "rr_ratio": rr, "regime": regime}



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
            logger.error("[KELLY] kelly_lot_compute error: %s — using base_lot", exc)
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

