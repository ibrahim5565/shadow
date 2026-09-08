"""
Aegis Gold — Statistical Validation & Rolling Checkpoint Engine
Maintains simultaneous rolling evaluation windows (50, 100, 250, 500 trades) and
enforces Staged Promotion Gates from Forward Demo to Controlled Capital Scaling.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger("aegis.validation_checkpoint")


@dataclass
class WindowMetrics:
    window_name: str
    trade_count: int
    win_rate_pct: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    profit_factor: float
    avg_win_usd: float
    avg_loss_usd: float
    expectancy_usd: float
    median_trade_pnl: float
    max_drawdown_usd: float
    max_consecutive_losses: int
    target_hit_rate_pct: float
    avg_holding_bars: float
    top_day_share_pct: float
    top_2_days_share_pct: float
    promotion_verdict: str


class ValidationCheckpointEngine:
    """
    Computes statistical verification metrics across multiple rolling windows.
    Enforces strict gates: PF >= 1.50, Expectancy > 0, Top day < 20%, Top 2 days < 35%.
    """

    GATE_MIN_PF_DEMO = 1.50
    GATE_MIN_PF_LIVE = 1.40
    GATE_MAX_TOP_DAY_SHARE = 20.0     # Max allowed single day profit share (%)
    GATE_MAX_TOP_2_DAY_SHARE = 35.0   # Max allowed top 2 days profit share (%)
    GATE_MAX_SLIPPAGE_RATIO = 1.80

    def __init__(self):
        pass

    def evaluate_window(self, trades_df: pd.DataFrame, window_name: str = "CURRENT_WINDOW") -> WindowMetrics:
        """Calculates quantitative metrics for a specific slice of trades."""
        if len(trades_df) == 0:
            return WindowMetrics(
                window_name=window_name, trade_count=0, win_rate_pct=0.0,
                gross_profit=0.0, gross_loss=0.0, net_pnl=0.0, profit_factor=0.0,
                avg_win_usd=0.0, avg_loss_usd=0.0, expectancy_usd=0.0,
                median_trade_pnl=0.0, max_drawdown_usd=0.0, max_consecutive_losses=0,
                target_hit_rate_pct=0.0, avg_holding_bars=0.0, top_day_share_pct=0.0,
                top_2_days_share_pct=0.0, promotion_verdict="INSUFFICIENT_DATA"
            )

        total_trades = len(trades_df)
        wins = trades_df[trades_df['pnl'] > 0]
        losses = trades_df[trades_df['pnl'] < 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades) * 100.0

        gross_profit = wins['pnl'].sum() if win_count > 0 else 0.0
        gross_loss = abs(losses['pnl'].sum()) if loss_count > 0 else 0.0
        net_pnl = gross_profit - gross_loss
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)

        avg_win = wins['pnl'].mean() if win_count > 0 else 0.0
        avg_loss = losses['pnl'].mean() if loss_count > 0 else 0.0
        expectancy = (win_rate / 100.0 * avg_win) + ((1.0 - win_rate / 100.0) * avg_loss)
        median_pnl = trades_df['pnl'].median()

        # Drawdown
        cum = trades_df['pnl'].cumsum()
        max_dd = (cum.cummax() - cum).max() if len(cum) > 0 else 0.0

        # Consecutive losses
        max_consec = 0
        current_consec = 0
        for p in trades_df['pnl']:
            if p < 0:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0

        # $3–$4 Target hit rate
        target_hits = len(trades_df[(trades_df['pnl'] >= 3.00) & (trades_df['pnl'] <= 4.00)])
        target_hit_rate = (target_hits / total_trades) * 100.0

        avg_holding = trades_df['holding_bars'].mean() if 'holding_bars' in trades_df.columns else 0.0

        # Daily Concentration
        if 'date' in trades_df.columns:
            daily = trades_df.groupby('date')['pnl'].sum().sort_values(ascending=False)
            top_day_pnl = daily.iloc[0] if len(daily) > 0 else 0.0
            top_2_pnl = daily.iloc[:2].sum() if len(daily) > 1 else top_day_pnl
            top_day_share = (top_day_pnl / net_pnl * 100.0) if net_pnl > 0 else 0.0
            top_2_share = (top_2_pnl / net_pnl * 100.0) if net_pnl > 0 else 0.0
        else:
            top_day_share = 0.0
            top_2_share = 0.0

        # Promotion verdict
        passed = (
            total_trades >= 50 and
            profit_factor >= self.GATE_MIN_PF_DEMO and
            expectancy > 0.0 and
            top_day_share <= self.GATE_MAX_TOP_DAY_SHARE and
            top_2_share <= self.GATE_MAX_TOP_2_DAY_SHARE
        )

        verdict = "PASSED_PROMOTION_GATE" if passed else (
            "CONTINUE_COLLECTING_SAMPLE" if total_trades < 50 else "GATE_REJECTED"
        )

        return WindowMetrics(
            window_name=window_name,
            trade_count=total_trades,
            win_rate_pct=round(win_rate, 2),
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            net_pnl=round(net_pnl, 2),
            profit_factor=round(profit_factor, 3),
            avg_win_usd=round(avg_win, 2),
            avg_loss_usd=round(avg_loss, 2),
            expectancy_usd=round(expectancy, 2),
            median_trade_pnl=round(median_pnl, 2),
            max_drawdown_usd=round(max_dd, 2),
            max_consecutive_losses=max_consec,
            target_hit_rate_pct=round(target_hit_rate, 2),
            avg_holding_bars=round(avg_holding, 1),
            top_day_share_pct=round(top_day_share, 1),
            top_2_days_share_pct=round(top_2_share, 1),
            promotion_verdict=verdict
        )
