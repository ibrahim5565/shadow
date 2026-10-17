"""
Position Simulator for Historical Replay

Simulates opening/closing positions, tracking P&L, and managing daily state.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone
import pandas as pd

from scripts.pattern_audit.risk_limits import LimitValue, read_audit_limits

#: Supervisor-exit model status: replay uses CLOSED M5 bars only, no M1, no
#: ticks. Same M5-EMA/ADX shape as TrendDetector, but live ALSO requires the
#: M1 leg + forming-bar closes -> replayed exits are UNCONFIRMED.
SUPERVISOR_EXIT_MODEL = "M5_CLOSED_ONLY_NO_M1_UNCONFIRMED"


_M5_TREND_CACHE = {}


def _m5_closed_only_trend(closes, highs, lows):
    """M5 leg of TrendDetector.analyze() on CLOSED bars only.

    Mirrors brain/trend_detector.py:35-48 (EMA9/21 on closes, ADX14):
      BULLISH/BEARISH from EMA9 vs EMA21; score 60 base, +20 if ADX > 25.
    The live M1 leg (brain/trend_detector.py:55-60) and the forming bar are
    deliberately NOT replayed here: no M1 history, no invented ticks.
    """
    from brain.indicators import EMA, ADX

    if len(closes) < 30:
        return "RANGING", 0
    # Replay calls this per bar with a growing prefix; cache the
    # (trend, score) per series length so the sweep stays linear.
    _key = (len(closes), round(float(closes[-1]), 6))
    _hit = _M5_TREND_CACHE.get(_key)
    if _hit is not None:
        return _hit
    ema9 = EMA(list(closes), 9)
    ema21 = EMA(list(closes), 21)
    adx = ADX(list(highs), list(lows), list(closes), 14)
    if not ema9 or not ema21:
        return "RANGING", 0
    m5 = "BULLISH" if ema9[-1] > ema21[-1] else (
        "BEARISH" if ema9[-1] < ema21[-1] else "NONE")
    score = 60
    if adx and adx[-1] > 25:
        score += 20
    if m5 == "BULLISH":
        _out = ("TRENDING_UP", score)
    elif m5 == "BEARISH":
        _out = ("TRENDING_DOWN", score)
    else:
        _out = ("RANGING", 30)
    _M5_TREND_CACHE[_key] = _out
    return _out


def supervisor_exit_on_closed_m5(direction, closes, highs, lows,
                                 score_floor: int = 50):
    """Live supervisor trend-reversal exit, replayed on closed M5 bars.

    Live rule (brain/position_supervisor.py:141-148):
      BUY  + TRENDING_DOWN + score >= 50 -> CLOSE
      SELL + TRENDING_UP   + score >= 50 -> CLOSE
    Returns (should_close, trend, score). No M1 leg -> UNCONFIRMED.
    """
    trend, score = _m5_closed_only_trend(closes, highs, lows)
    if direction == "BUY" and trend == "TRENDING_DOWN" and score >= score_floor:
        return True, trend, score
    if direction == "SELL" and trend == "TRENDING_UP" and score >= score_floor:
        return True, trend, score
    return False, trend, score

# Real RiskManager.can_trade() conditions needing MT5/account state -
# NOT evaluated here; listed as UNCONFIRMED in the audit report.
UNCONFIRMED_REAL_GATES = (
    "DRAWDOWN_GUARD (DD_BLOCK_NEW_PCT, needs live equity curve)",
    "SESSION_REFRESH_45MIN_BLOCK (needs live refresh state)",
    "CVAR_DAILY_TAIL_LOSS_GUARD (needs live PnL tail + QX flag)",
    "GLOBAL_COOLDOWN_FILE (needs live cooldown file state)",
    "TRADES_PER_MINUTE (needs live order timestamps)",
    "DIRECTION_FILTER (needs live direction state)",
)


@dataclass
class SimulatedPosition:
    """A simulated open position."""
    ticket: int
    symbol: str
    direction: str  # "BUY" or "SELL"
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    open_time: float  # Unix timestamp
    open_bar: int = 0  # fill-bar index (next-bar open)
    max_hold_bars: int = 30
    pattern_type: str = ''
    pattern_name: str = ''


@dataclass
class ClosedPosition:
    """A closed position with outcome."""
    ticket: int
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    open_time: float
    close_time: float
    pnl: float
    exit_reason: str  # "SL", "TP", "MANUAL"
    pattern_type: str
    pattern_name: str


class PositionSimulator:
    """
    Simulates position lifecycle in historical replay.
    
    Tracks:
    - Open positions
    - Closed positions with P&L
    - Daily trade count
    - Consecutive wins/losses
    - Cooldown periods
    """
    
    #: SIMULATED gate label (NOT the real RiskManager.can_trade()).
    GATE_NAME = "SIMULATED_POSITION_LIMITS"

    def __init__(self, symbol: str, point: float,
                 limits: dict | None = None,
                 max_hold_bars: int = 30,
                 supervisor_exit: bool = False):
        self.symbol = symbol
        self.point = point
        self.next_ticket = 1
        #: {name: LimitValue} read from REAL live files (with file:line).
        self.limits = dict(limits) if limits else read_audit_limits()
        self.max_hold_bars = int(max_hold_bars)
        #: Supervisor trend-reversal exit replay (closed M5 bars only).
        #: OFF by default -> identical behaviour to the earlier audit.
        #: ON -> exits flagged SUPERVISOR_EXIT_TREND_REVERSAL (UNCONFIRMED).
        self.supervisor_exit = bool(supervisor_exit)
        
        # Position tracking
        self.open_positions: Dict[int, SimulatedPosition] = {}
        self.closed_positions: List[ClosedPosition] = []
        
        # Daily state
        self.current_day = None
        self.daily_trades = 0
        self.daily_pnl = 0.0
        
        # Streak tracking
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        
        # Cooldown tracking
        self.cooldown_until = 0  # Unix timestamp
        self.loss_pause_until = 0  # Unix timestamp
    
    def open_position(
        self,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        lot_size: float,
        open_time: float,
        open_bar: int = 0,
        max_hold_bars: int | None = None,
        pattern_type: str = '',
        pattern_name: str = ''
    ) -> int:
        """
        Open a simulated position.
        
        Returns:
            ticket: Position ticket number
        """
        ticket = self.next_ticket
        self.next_ticket += 1
        
        position = SimulatedPosition(
            ticket=ticket,
            symbol=self.symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=lot_size,
            open_time=open_time,
            open_bar=open_bar,
            max_hold_bars=(self.max_hold_bars
                           if max_hold_bars is None else max_hold_bars),
            pattern_type=pattern_type,
            pattern_name=pattern_name
        )
        
        self.open_positions[ticket] = position
        self.daily_trades += 1
        
        return ticket
    
    def update_positions(self, candle: pd.Series, current_time: float,
                         bar_index: int | None = None,
                         bar_minutes: float | None = None,
                         closes=None, highs=None, lows=None):
        """
        Update open positions - check if SL or TP hit.
        
        Args:
            candle: Current OHLC candle
            current_time: Current bar timestamp
            closes/highs/lows: Optional CLOSED-bar series THROUGH the current
                bar for the supervisor trend-reversal replay. When provided
                AND self.supervisor_exit is True, the supervisor exit is
                evaluated FIRST (before SL/TP) on those closed bars.
        """
        tickets_to_close = []
        
        for ticket, pos in self.open_positions.items():
            # Supervisor trend-reversal replay FIRST (before SL/TP), only
            # when enabled AND closed-bar series are provided. Live rule:
            # brain/position_supervisor.py:141-148. No M1 leg -> UNCONFIRMED.
            if self.supervisor_exit and closes is not None:
                _should, _trend, _score = supervisor_exit_on_closed_m5(
                    pos.direction, list(closes), list(highs or []),
                    list(lows or []))
                if _should:
                    tickets_to_close.append(
                        (ticket, float(candle["close"]),
                         "SUPERVISOR_EXIT_TREND_REVERSAL"))
                    continue
            # SL/TP off REAL bar high/low (stop-before-target convention:
            # when both are within the bar, stop loss is assumed first).
            if pos.direction == "BUY":
                if candle['low'] <= pos.stop_loss:
                    tickets_to_close.append((ticket, pos.stop_loss, "SL"))
                elif candle['high'] >= pos.take_profit:
                    tickets_to_close.append((ticket, pos.take_profit, "TP"))
            else:  # SELL
                if candle['high'] >= pos.stop_loss:
                    tickets_to_close.append((ticket, pos.stop_loss, "SL"))
                elif candle['low'] <= pos.take_profit:
                    tickets_to_close.append((ticket, pos.take_profit, "TP"))
            # Time stop: TIME_STOP_BASE_SEC from live config, else
            # max_hold_bars fallback (both simulated, both reported).
            _tstop = self.limit("TIME_STOP_BASE_SEC")
            _held_s = current_time - pos.open_time
            _held_b = ((bar_index - pos.open_bar)
                       if bar_index is not None else 10 ** 9)
            if (_tstop > 0 and _held_s >= _tstop) or \
                    (_held_b >= pos.max_hold_bars):
                if not any(t == ticket for t, _, _ in tickets_to_close):
                    tickets_to_close.append(
                        (ticket, float(candle["close"]), "TIME"))
        
        # Close positions that hit SL/TP
        for ticket, exit_price, reason in tickets_to_close:
            self.close_position(ticket, exit_price, current_time, reason)
    
    def close_position(
        self,
        ticket: int,
        exit_price: float,
        close_time: float,
        reason: str = "MANUAL",
        set_loss_cooldown: bool = True,
    ):
        """Close a position and record P&L."""
        if ticket not in self.open_positions:
            return
        
        pos = self.open_positions[ticket]
        
        # Calculate P&L
        if pos.direction == "BUY":
            pnl_points = (exit_price - pos.entry_price) / self.point
        else:  # SELL
            pnl_points = (pos.entry_price - exit_price) / self.point
        
        pnl = pnl_points * pos.lot_size * 1.0  # Simplified: $1 per point per lot
        
        # Record closed position
        closed = ClosedPosition(
            ticket=pos.ticket,
            symbol=pos.symbol,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            lot_size=pos.lot_size,
            open_time=pos.open_time,
            close_time=close_time,
            pnl=pnl,
            exit_reason=reason,
            pattern_type=pos.pattern_type,
            pattern_name=pos.pattern_name
        )
        
        self.closed_positions.append(closed)
        
        # Update streaks
        if pnl > 0:
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            
            # Set loss pause if 3 consecutive losses
            cap_l = self.limit("MAX_CONSECUTIVE_LOSSES")
            if cap_l > 0 and self.consecutive_losses >= cap_l:
                pause_h = 4.0  # documented audit convention (simulated)
                self.loss_pause_until = close_time + pause_h * 3600
                cool = self.limit("COOLDOWN_AFTER_CONSEC_LOSSES")
                if cool > 0:
                    self.cooldown_until = max(
                        self.cooldown_until, close_time + cool)
        
        # Update daily P&L
        self.daily_pnl += pnl
        
        # Loss cooldown from REAL config (COOLDOWN_AFTER_LOSS_SEC).
        if set_loss_cooldown and pnl < 0:
            _lc = self.limit("COOLDOWN_AFTER_LOSS_SEC")
            if _lc > 0:
                self.cooldown_until = max(
                    self.cooldown_until, close_time + _lc)
        # Remove from open positions
        del self.open_positions[ticket]
    
    def check_daily_reset(self, current_time: float):
        """
        Check if day boundary crossed and reset daily state.
        
        Args:
            current_time: Current bar timestamp (Unix, UTC)
        """
        current_dt = datetime.fromtimestamp(current_time, tz=timezone.utc)
        current_day = current_dt.strftime("%Y-%m-%d")
        
        if self.current_day is None:
            self.current_day = current_day
            return
        
        if current_day != self.current_day:
            # Day boundary crossed - reset daily state
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.current_day = current_day
    
    def limit(self, name: str) -> float:
        """Numeric limit value (reads REAL config; see self.limits sources)."""
        lv = self.limits.get(name)
        return float(lv.value) if lv is not None else 0.0

    def limit_sources(self) -> dict:
        return {k: v.source for k, v in self.limits.items()}

    def can_trade(self, current_time: float,
                  max_daily_trades: float | None = None) -> tuple:
        """
        Check if new trade can be opened.
        
        Args:
            current_time: Current timestamp
            max_daily_trades: Maximum trades per day
        
        Returns:
            (can_trade: bool, reason: str)
        """
        # Check daily trade limit
        if self.daily_trades >= (self.limit("MAX_DAILY_TRADES")
                if max_daily_trades is None else max_daily_trades):
            cap = (self.limit("MAX_DAILY_TRADES")
                   if max_daily_trades is None else max_daily_trades)
            return False, f"DAILY_LIMIT ({self.daily_trades}/{cap:g})"
        
        # Check open positions limit
        if len(self.open_positions) >= self.limit("MAX_OPEN_TRADES"):
            cap_o = self.limit("MAX_OPEN_TRADES")
            return False, f"MAX_OPEN ({len(self.open_positions)}/{cap_o:g})"
        
        # Check loss pause
        if current_time < self.loss_pause_until:
            hours_left = (self.loss_pause_until - current_time) / 3600
            return False, f"LOSS_PAUSE ({hours_left:.1f}h remaining)"
        
        # Check consecutive losses
        cap_c0 = self.limit("MAX_CONSECUTIVE_LOSSES")
        if cap_c0 > 0 and self.consecutive_losses >= cap_c0:
            cap_c = self.limit("MAX_CONSECUTIVE_LOSSES")
            return False, f"CONSECUTIVE_LOSSES ({self.consecutive_losses}/{cap_c:g})"
        
        # Check cooldown
        if current_time < self.cooldown_until:
            mins_left = (self.cooldown_until - current_time) / 60
            return False, f"COOLDOWN ({mins_left:.0f}min remaining)"
        
        return True, ""
    
    def get_stats(self) -> dict:
        """Get current simulator statistics."""
        total_closed = len(self.closed_positions)
        wins = sum(1 for p in self.closed_positions if p.pnl > 0)
        losses = sum(1 for p in self.closed_positions if p.pnl < 0)
        
        total_pnl = sum(p.pnl for p in self.closed_positions)
        
        return {
            'total_trades': total_closed,
            'wins': wins,
            'losses': losses,
            'win_rate': wins / total_closed if total_closed > 0 else 0,
            'total_pnl': total_pnl,
            'open_positions': len(self.open_positions),
            'daily_trades': self.daily_trades,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins
        }
