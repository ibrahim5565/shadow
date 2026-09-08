"""
===========================================================================
AEGIS GOLD — Causal Future Move Forecaster (Phase 2)
===========================================================================

PURPOSE:
  Predicts expected future price movement (points, R-multiple, MFE, MAE, duration)
  from point-in-time snapshot at decision time T.

CAUSALITY GUARANTEE:
  All feature inputs and predictions are computed strictly using data timestamped
  t <= T. Future candle data is strictly forbidden.
===========================================================================
"""

from __future__ import annotations

import math
import logging
from typing import Optional
from brain.pattern_library import StructuralPattern, PatternScale, FutureMoveForecast
from brain.frozen_snapshot import FrozenDecisionSnapshot

logger = logging.getLogger("aegis.future_forecaster")


class FutureMoveForecaster:
    """
    Causal Point-in-Time Future Price Movement Prediction Engine.
    """

    def predict_future_move(
        self,
        pattern: StructuralPattern,
        snapshot: FrozenDecisionSnapshot,
    ) -> FutureMoveForecast:
        """
        Calculates causal FutureMoveForecast from structural pattern and snapshot data (t <= T).
        """
        direction = pattern.direction
        point = snapshot.point
        curr_price = snapshot.current_price

        # Structural Distance Calculations
        sl_dist_pts = abs(curr_price - pattern.invalidation_level) / point if point > 0 else 100.0
        tp_dist_pts = abs(pattern.target_level - curr_price) / point if point > 0 else 300.0

        sl_dist_pts = max(sl_dist_pts, 10.0)
        expected_move_R = round(tp_dist_pts / sl_dist_pts, 2)

        # Scale-dependent Horizon & Duration
        if pattern.pattern_scale == PatternScale.SMALL:
            horizon = "SHORT"
            est_duration_sec = 600  # 10 minutes
        elif pattern.pattern_scale == PatternScale.LARGE:
            horizon = "LONG"
            est_duration_sec = 7200 # 2 hours
        else:
            horizon = "MEDIUM"
            est_duration_sec = 1800 # 30 minutes

        # Estimated MFE / MAE
        expected_mfe = round(tp_dist_pts * 0.90, 1)
        expected_mae = round(sl_dist_pts * 0.35, 1)

        # Probabilities
        prob_up = 0.70 if direction == "BUY" else 0.15
        prob_down = 0.70 if direction == "SELL" else 0.15
        prob_neutral = 0.15

        forecast = FutureMoveForecast(
            direction=direction,
            expected_move_points=round(tp_dist_pts, 1),
            expected_move_R=expected_move_R,
            probability_up=prob_up,
            probability_down=prob_down,
            probability_neutral=prob_neutral,
            expected_mfe=expected_mfe,
            expected_mae=expected_mae,
            expected_time_to_target_sec=est_duration_sec,
            forecast_horizon=horizon,
            forecast_quality=round(pattern.strength_score, 1),
        )

        logger.info(
            f"🔮 [FUTURE FORECAST] Direction={direction} Scale={pattern.pattern_scale.value} "
            f"Expected Move={forecast.expected_move_points}pts ({forecast.expected_move_R}R) "
            f"Horizon={horizon} EstDuration={est_duration_sec}s"
        )

        return forecast
