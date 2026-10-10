"""
Position Simulator for Historical Replay

Simulates opening/closing positions, tracking P&L, and managing daily state.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timezone
import pandas as pd


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
    pattern_type: str
    pattern_name: str


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
    
    def __init__(self, symbol: str, point: float):
        self.symbol = symbol
        self.point = point
        self.next_ticket = 1
        
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
        pattern_type: str,
        pattern_name: str
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
            pattern_type=pattern_type,
            pattern_name=pattern_name
        )
        
        self.open_positions[ticket] = position
        self.daily_trades += 1
        
        return ticket
    
    def update_positions(self, candle: pd.Series, current_time: float):
        """
        Update open positions - check if SL or TP hit.
        
        Args:
            candle: Current OHLC candle
            current_time: Current bar timestamp
        """
        tickets_to_close = []
        
        for ticket, pos in self.open_positions.items():
            # Check if SL or TP hit during this candle
            if pos.direction == "BUY":
                # BUY position: SL below entry, TP above
                if candle['low'] <= pos.stop_loss:
                    # Stop loss hit
                    tickets_to_close.append((ticket, pos.stop_loss, "SL"))
                elif candle['high'] >= pos.take_profit:
                    # Take profit hit
                    tickets_to_close.append((ticket, pos.take_profit, "TP"))
            
            elif pos.direction == "SELL":
                # SELL position: SL above entry, TP below
                if candle['high'] >= pos.stop_loss:
                    # Stop loss hit
                    tickets_to_close.append((ticket, pos.stop_loss, "SL"))
                elif candle['low'] <= pos.take_profit:
                    # Take profit hit
                    tickets_to_close.append((ticket, pos.take_profit, "TP"))
        
        # Close positions that hit SL/TP
        for ticket, exit_price, reason in tickets_to_close:
            self.close_position(ticket, exit_price, current_time, reason)
    
    def close_position(
        self,
        ticket: int,
        exit_price: float,
        close_time: float,
        reason: str = "MANUAL"
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
            if self.consecutive_losses >= 3:
                self.loss_pause_until = close_time + (3600 * 4)  # 4 hour pause
        
        # Update daily P&L
        self.daily_pnl += pnl
        
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
    
    def can_trade(self, current_time: float, max_daily_trades: int = 5) -> tuple:
        """
        Check if new trade can be opened.
        
        Args:
            current_time: Current timestamp
            max_daily_trades: Maximum trades per day
        
        Returns:
            (can_trade: bool, reason: str)
        """
        # Check daily trade limit
        if self.daily_trades >= max_daily_trades:
            return False, f"DAILY_LIMIT ({self.daily_trades}/{max_daily_trades})"
        
        # Check open positions limit
        if len(self.open_positions) >= 3:
            return False, f"MAX_OPEN_POSITIONS ({len(self.open_positions)}/3)"
        
        # Check loss pause
        if current_time < self.loss_pause_until:
            hours_left = (self.loss_pause_until - current_time) / 3600
            return False, f"LOSS_PAUSE ({hours_left:.1f}h remaining)"
        
        # Check consecutive losses
        if self.consecutive_losses >= 3:
            return False, f"CONSECUTIVE_LOSSES ({self.consecutive_losses})"
        
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
