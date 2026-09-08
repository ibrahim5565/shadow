"""
Acceptance Test for Task 2: Naked Position Monitoring & Emergency SL Attachment
================================================================================
Places a test order with sl=0.0 on MT5 demo, runs check_and_protect_open_positions(),
and verifies programmatically that:
  1. The naked position is detected.
  2. Emergency hard SL is attached on the broker server.
  3. The resulting position in MT5 has sl > 0.0.
  4. Flattens the test position at the end.
"""

import sys
import time
import unittest
import MetaTrader5 as mt5
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from config import settings as cfg
from brain.naked_position_monitor import check_and_protect_open_positions


class TestNakedPositionMonitor(unittest.TestCase):

    def setUp(self):
        ok = mt5.initialize(login=cfg.MT5_LOGIN, password=cfg.MT5_PASSWORD, server=cfg.MT5_SERVER)
        if not ok:
            ok = mt5.initialize()
        if not ok:
            self.skipTest("MT5 terminal not connected")
        self.symbol = "EURUSD"
        mt5.symbol_select(self.symbol, True)
        self.test_tickets = []

    def tearDown(self):
        # Clean up any remaining test positions
        for ticket in self.test_tickets:
            positions = mt5.positions_get(ticket=ticket)
            if positions:
                p = positions[0]
                tick = mt5.symbol_info_tick(p.symbol)
                price = tick.bid if p.type == mt5.ORDER_TYPE_BUY else tick.ask
                close_req = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": p.symbol,
                    "volume": p.volume,
                    "type": mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                    "position": p.ticket,
                    "price": price,
                    "deviation": 20,
                    "magic": 999999,
                    "comment": "Cleanup Naked Test Position",
                }
                res = mt5.order_send(close_req)
                if not res or res.retcode != mt5.TRADE_RETCODE_DONE:
                    close_req["type_filling"] = mt5.ORDER_FILLING_IOC
                    mt5.order_send(close_req)
        mt5.shutdown()

    def _run_naked_test_for_symbol(self, symbol: str, expected_floor_pts: int):
        mt5.symbol_select(symbol, True)
        tick = mt5.symbol_info_tick(symbol)
        self.assertIsNotNone(tick, f"Cannot get tick for {symbol}")

        info = mt5.symbol_info(symbol)
        point = info.point if info else (0.01 if "XAU" in symbol.upper() else 0.00001)

        raw_req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "sl": 0.0,
            "tp": 0.0,
            "magic": 999999,
            "deviation": 20,
            "type_filling": mt5.ORDER_FILLING_FOK,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        res = mt5.order_send(raw_req)
        self.assertIsNotNone(res, "Order send returned None")
        if res.retcode != mt5.TRADE_RETCODE_DONE:
            raw_req["type_filling"] = mt5.ORDER_FILLING_IOC
            res = mt5.order_send(raw_req)
        if res.retcode != mt5.TRADE_RETCODE_DONE:
            raw_req["type_filling"] = mt5.ORDER_FILLING_RETURN
            res = mt5.order_send(raw_req)

        self.assertEqual(res.retcode, mt5.TRADE_RETCODE_DONE, f"Failed to place test naked position on {symbol}: {res.comment}")
        ticket = res.order
        self.test_tickets.append(ticket)
        print(f"\n[TEST] Placed naked test position #{ticket} on {symbol} with sl=0.0")

        positions = mt5.positions_get(ticket=ticket)
        self.assertTrue(len(positions) > 0, f"Position #{ticket} not found in MT5")
        self.assertEqual(positions[0].sl, 0.0, "Initial position must have sl=0.0 for this test")
        entry_price = positions[0].price_open

        processed = check_and_protect_open_positions()
        print(f"[TEST] Naked monitor processed {len(processed)} naked positions.")

        detected_tickets = [p["ticket"] for p in processed]
        self.assertIn(ticket, detected_tickets, f"Ticket #{ticket} was not detected by naked position monitor")

        updated_positions = mt5.positions_get(ticket=ticket)
        if updated_positions:
            up_p = updated_positions[0]
            self.assertGreater(up_p.sl, 0.0, f"Position #{ticket} SL on broker server is still 0.0! Emergency SL failed.")
            expected_sl = round(entry_price - (expected_floor_pts * point), info.digits if info else 2)
            self.assertAlmostEqual(up_p.sl, expected_sl, places=info.digits if info else 2,
                                   msg=f"Attached SL {up_p.sl} does not match expected floor {expected_sl}")
            print(f"[TEST] SUCCESS! Position #{ticket} on {symbol} now has broker-side SL = {up_p.sl} (Entry: {entry_price}, Expected Floor SL: {expected_sl})")
        else:
            print(f"[TEST] SUCCESS! Position #{ticket} on {symbol} was market-closed for emergency safety.")

    def test_eurusd_naked_position_detected_and_protected(self):
        """Intentionally place a naked sl=0.0 test order on EURUSD and verify auto-attachment of SL."""
        self._run_naked_test_for_symbol("EURUSD", expected_floor_pts=40)

    def test_xauusd_naked_position_detected_and_protected(self):
        """Intentionally place a naked sl=0.0 test order on XAUUSD and verify auto-attachment of SL (150pt Gold floor)."""
        self._run_naked_test_for_symbol("XAUUSD", expected_floor_pts=150)


if __name__ == "__main__":
    unittest.main()

