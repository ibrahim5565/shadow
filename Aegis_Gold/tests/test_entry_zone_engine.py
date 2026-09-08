"""
tests/test_entry_zone_engine.py
================================
AEGIS GOLD — Entry Zone Engine Unit Tests

Verifies:
1. EntryZoneEngine entry zone calculation for BUY and SELL.
2. Invalidation and target price bounds.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.entry_zone_engine import EntryZoneEngine
from brain.pattern_library import PatternScale


class TestEntryZoneEngine(unittest.TestCase):

    def setUp(self):
        self.engine = EntryZoneEngine()

    def test_buy_entry_zone_spec(self):
        """EntryZoneEngine returns valid EntryZoneSpecification for BUY."""
        spec = self.engine.calculate_entry_zone("BUY", 2015.0, PatternScale.MEDIUM)
        self.assertEqual(spec.ideal_entry, 2015.0)
        self.assertLess(spec.invalidation_price, 2015.0)
        self.assertGreater(spec.target_price, 2015.0)
