"""
tests/test_future_move_forecast.py
===================================
AEGIS GOLD — Future Move Forecast Unit Tests

Verifies:
1. FutureMoveForecast dataclass creation and point-in-time calculation (t <= T).
2. Expected move points, MFE, MAE, duration, and horizon predictions.
"""

import sys
import os
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.pattern_library import StructuralPattern, PatternType, PatternCategory, PatternScale, FutureMoveForecast
from brain.future_move_forecaster import FutureMoveForecaster
from brain.frozen_snapshot import build_snapshot


class TestFutureMoveForecast(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.forecaster = FutureMoveForecaster()

    def test_causal_forecast_generation(self):
        """FutureMoveForecaster generates causal forecast from point-in-time snapshot."""
        pattern = StructuralPattern(
            pattern_id="p_fcst_1",
            pattern_type=PatternType.BOS_BULLISH,
            category=PatternCategory.SMC_STRUCTURE,
            direction="BUY",
            symbol="XAUUSD",
            formation_time=self.now - timedelta(minutes=10),
            confirmation_time=self.now - timedelta(minutes=5),
            information_available_time=self.now - timedelta(minutes=5),
            price_level=2015.0,
            invalidation_level=2010.0,
            target_level=2035.0,
            strength_score=8.5,
            pattern_scale=PatternScale.MEDIUM,
        )
        candles = [{"time": int(self.now.timestamp()) - i*300, "open": 2015.0, "high": 2017.0, "low": 2014.0, "close": 2016.0, "volume": 100} for i in range(20)][::-1]
        snapshot = build_snapshot("XAUUSD", candles, candles, self.now)

        forecast = self.forecaster.predict_future_move(pattern, snapshot)
        self.assertEqual(forecast.direction, "BUY")
        self.assertEqual(forecast.forecast_horizon, "MEDIUM")
        self.assertGreater(forecast.expected_move_points, 0.0)
        self.assertGreater(forecast.expected_move_R, 0.0)
        self.assertGreater(forecast.expected_mfe, 0.0)
        self.assertGreater(forecast.expected_time_to_target_sec, 0)
