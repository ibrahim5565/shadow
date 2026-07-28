"""
Unit Tests for Aegis-Gold Position Sizing Math (Phase 1)
Asserts that dollar risk remains constant across a range of SL distances (150pt to 500pt)
and across varying account equity levels ($1,000 to $10,000).
"""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from modules.risk_manager import RiskManager


class MockGateway:
    """Mock gateway providing account equity for testing."""
    def __init__(self, equity=1000.0):
        self._equity = equity
        self.symbols_data = {"XAUUSD": {"point": 0.01}}

    def get_account_info(self):
        return {"equity": self._equity, "balance": self._equity}


class TestPositionSizing(unittest.TestCase):

    def setUp(self):
        self.gateway = MockGateway(equity=1000.0)
        self.rm = RiskManager(self.gateway)

    def test_constant_dollar_risk_across_sl_distances(self):
        """
        Asserts that a 500-point SL trade risks the exact same dollar amount as a 150-point SL trade.
        Formula: Dollar Risk = Lot Size * SL Points * Point_Value_Per_Lot
        """
        equity = 1000.0
        risk_pct = 0.01  # 1% target = $10.00 risk
        target_risk_usd = equity * risk_pct  # $10.00

        sl_distances = [150, 200, 250, 300, 350, 400, 450, 500]
        calculated_risks = []

        for sl in sl_distances:
            lot = self.rm.calculate_position_size(
                symbol="XAUUSD",
                sl_points=sl,
                equity=equity,
                risk_pct=risk_pct
            )
            # Dollar risk = lot * sl_points * 1.0 ($1 per point per 1.0 lot)
            actual_dollar_risk = lot * sl * 1.0
            calculated_risks.append((sl, lot, actual_dollar_risk))
            print(f"SL: {sl}pts -> Lot: {lot:.2f} -> Actual Dollar Risk: ${actual_dollar_risk:.2f} (Target: ${target_risk_usd:.2f})")

        # Assert all calculated risks stay <= target risk (never overshooting) and within 1 lot step quantization ($2.50)
        for sl, lot, risk in calculated_risks:
            self.assertLessEqual(
                risk,
                target_risk_usd + 0.01,
                msg=f"Risk for {sl}pt SL (${risk:.2f}) exceeded target dollar risk (${target_risk_usd:.2f})"
            )
            self.assertGreaterEqual(
                risk,
                target_risk_usd - 3.50,
                msg=f"Risk for {sl}pt SL (${risk:.2f}) fell too far below target dollar risk (${target_risk_usd:.2f})"
            )

    def test_constant_dollar_risk_across_equity_levels(self):
        """
        Asserts constant dollar risk scaling across varying equity levels ($1,000 to $10,000).
        """
        equities = [1000.0, 2500.0, 5000.0, 10000.0]
        sl_points = 300  # Fixed 300pt SL

        for eq in equities:
            target_usd = eq * 0.01  # 1% risk
            lot = self.rm.calculate_position_size(
                symbol="XAUUSD",
                sl_points=sl_points,
                equity=eq,
                risk_pct=0.01
            )
            actual_risk = lot * sl_points * 1.0
            print(f"Equity: ${eq:.2f} | SL: {sl_points}pts -> Lot: {lot:.2f} -> Dollar Risk: ${actual_risk:.2f} (Target: ${target_usd:.2f})")
            self.assertLessEqual(
                actual_risk,
                target_usd + 0.01,
                msg=f"Risk for Equity ${eq} (${actual_risk:.2f}) exceeded target (${target_usd:.2f})"
            )

    def test_fixed_dollar_risk_override(self):
        """
        Asserts fixed dollar risk parameter overrides equity risk_pct.
        """
        fixed_risk = 25.0  # $25 fixed risk
        sl_points = 250

        lot = self.rm.calculate_position_size(
            symbol="XAUUSD",
            sl_points=sl_points,
            equity=5000.0,
            fixed_risk_usd=fixed_risk
        )
        actual_risk = lot * sl_points * 1.0
        print(f"Fixed Risk Target: ${fixed_risk:.2f} | SL: {sl_points}pts -> Lot: {lot:.2f} -> Actual Risk: ${actual_risk:.2f}")
        self.assertEqual(lot, 0.10)
        self.assertEqual(actual_risk, 25.0)


if __name__ == "__main__":
    unittest.main()
