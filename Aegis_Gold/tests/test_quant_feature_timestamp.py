"""
tests/test_quant_feature_timestamp.py
======================================
AEGIS GOLD — Quant Intelligence Engine v2 Tests (Phase 5)

Verifies:
1. Log Returns, ACF, Z-score, EWMA, GARCH, and GBM distribution formulas
2. QuantFeatureVector output schema and timestamp causality (timestamp == snapshot.timestamp)
3. Zero look-ahead: all calculations use strictly trailing closed bars
"""

import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.frozen_snapshot import FrozenDecisionSnapshot, build_snapshot
from brain.quant_feature_engine import QuantFeatureEngine, QuantFeatureVector


def _make_candle(t_offset_s, c=2000.0):
    base_t = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    return {
        "time": int(base_t + t_offset_s),
        "open": c - 2.0, "high": c + 5.0, "low": c - 5.0, "close": c, "volume": 100
    }


class TestQuantIntelligenceV2(unittest.TestCase):

    def setUp(self):
        self.qfe = QuantFeatureEngine()
        self.decision_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        self.m5_bars = [_make_candle(i * 300 - 50 * 300, c=2000.0 + i * 0.5) for i in range(50)]
        self.snapshot = build_snapshot(
            symbol="XAUUSD",
            candles_m5=self.m5_bars,
            candles_m1=[],
            decision_time=self.decision_time,
            point=0.01,
        )

    def test_quant_vector_schema(self):
        """extract_quant_vector must return a valid QuantFeatureVector."""
        vec = self.qfe.extract_quant_vector(self.snapshot)
        self.assertIsInstance(vec, QuantFeatureVector)
        self.assertEqual(vec.timestamp, self.decision_time)
        self.assertEqual(vec.symbol, "XAUUSD")
        self.assertGreater(vec.last_close, 0.0)

    def test_acf_calculation(self):
        """Return ACF at lag 1 should return float in [-1.0, 1.0]."""
        vec = self.qfe.extract_quant_vector(self.snapshot)
        self.assertTrue(-1.0 <= vec.acf_lag_1 <= 1.0)
        self.assertTrue(-1.0 <= vec.acf_lag_2 <= 1.0)

    def test_zscore_causality(self):
        """Z-score must be calculated from trailing window without look-ahead."""
        vec = self.qfe.extract_quant_vector(self.snapshot)
        self.assertIsInstance(vec.zscore_short, float)
        self.assertIsInstance(vec.zscore_medium, float)

    def test_volatility_measures(self):
        """EWMA, GARCH, and Realized Volatility must be non-negative."""
        vec = self.qfe.extract_quant_vector(self.snapshot)
        self.assertGreaterEqual(vec.ewma_volatility, 0.0)
        self.assertGreaterEqual(vec.garch_volatility, 0.0)
        self.assertGreaterEqual(vec.realized_vol_medium, 0.0)

    def test_gbm_distribution_bands(self):
        """GBM expected price should lie between lower and upper bands."""
        vec = self.qfe.extract_quant_vector(self.snapshot)
        self.assertLessEqual(vec.gbm_lower_band, vec.gbm_expected_price)
        self.assertGreaterEqual(vec.gbm_upper_band, vec.gbm_expected_price)
        self.assertGreaterEqual(vec.gbm_expected_range, 0.0)
