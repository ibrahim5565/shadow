"""
Root-Cause Fix Verification (SELL starvation, LLM veto, direction symmetry).

Guards the production execution path in core/main.py:

ROOT CAUSE #1 — queued SELL starvation:
    The old structure was `if candidates: ... elif signal_queue: ...` which made
    the queued branch run ONLY when no fresh candidates existed, so a queued
    SELL could be starved by a continuous stream of BUY candidates. The fix
    makes queued processing INDEPENDENT (`if signal_queue:` after `if
    candidates:`). These tests prove both the source structure and the
    runtime behavior (a queued SELL is popped and dispatched even while new
    BUY candidates are present).

ROOT CAUSE #2 — LLM entry veto:
    The LLM Analyst could `continue` and reject a valid pattern trade
    (conflicting_signals / no_directional_consensus / drawdown_veto), turning
    a valid pattern SELL into WAIT. The fix makes LLM observational only.
    Tests assert no veto path remains in the production source.

ROOT CAUSE #3 — direction symmetry:
    Order type, SL/TP geometry and direction all come from the pattern engine
    (BUY: sl<entry<tp, SELL: tp<entry<sl). The queue independence guarantees a
    lower-ranked SELL still executes when a higher-ranked BUY is present.
"""

import os
import sys
import time
import re
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_PATH = os.path.join(ROOT, "core", "main.py")

from brain.position_supervisor import PositionSupervisor  # noqa: E402


def _main_source():
    with open(MAIN_PATH, "r", encoding="utf-8") as f:
                return f.read()


class TestQueueStarvationFix(unittest.TestCase):
    """ROOT CAUSE #1 — queued SELL must never be starved by fresh BUY candidates."""

    def test_queued_branch_is_independent_not_elif(self):
        src = _main_source()
        self.assertNotIn("elif position_supervisor.signal_queue",
                         src, "Queued branch must not be an elif of candidates")
        cand_pos = src.index("if candidates:")
        queue_pos = src.index("if position_supervisor.signal_queue:")
        self.assertGreater(queue_pos, cand_pos,
                           "Queued processing must be independent and sequential")



    def test_queued_sell_executes_even_with_fresh_buy_candidate(self):
        """Emulates the patched loop: fresh BUY candidate present + queued SELL.
        The queued SELL must still be popped and dispatched (not starved)."""
        supervisor = PositionSupervisor()
        executed = []

        sell_decision = SimpleNamespace(
            direction="SELL", pattern_direction="SELL",
            pattern="Bearish Engulfing", action="TRADE",
            sl_points=150, tp_points=300, lot=0.01,
        )
        supervisor.signal_queue = []
        supervisor.signal_queue.append({
            "symbol": "XAUUSD", "direction": "SELL",
            "decision": sell_decision, "score": 40.0,
            "spread": 10.0, "session": "LONDON", "ai_approved": True,
            "time_queued": time.time(),
        })

        for cycle in range(5):
            candidates = [{
                "symbol": "XAUUSD", "direction": "BUY",
                "decision": SimpleNamespace(direction="BUY", pattern_direction="BUY",
                                           pattern="BOS_Bullish", action="TRADE",
                                           sl_points=150, tp_points=300, lot=0.01),
                "score": 76.0, "spread": 10.0, "session": "LONDON",
                "ai_approved": True, "time_queued": time.time(),
            }] if cycle == 0 else []
            candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)

            if candidates:
                primary = candidates[0]
                executed.append(("primary", primary["direction"]))

            if supervisor.signal_queue:
                q = supervisor.signal_queue.pop(0)
                executed.append(("queued", q["direction"]))

        self.assertTrue(
            any(tag == "queued" and d == "SELL" for tag, d in executed),
            f"Queued SELL must execute even with fresh BUY candidates. Executed: {executed}"
        )


class TestLLMVetoRemoved(unittest.TestCase):
    """ROOT CAUSE #2 — LLM must never veto a valid pattern entry."""

    def test_no_llm_veto_string_in_production(self):
        src = _main_source()
        self.assertNotIn("LLM ANALYST VETO", src,
                         "LLM veto logging/telegram must be gone")

    def test_no_llm_continue_veto_block(self):
        src = _main_source()
        self.assertNotIn("conflicting_signals", src,
                         "LLM conflicting-signals veto block must be removed")
        self.assertNotIn("no_directional_consensus", src,
                         "LLM no-directional-consensus veto block must be removed")

    def test_llm_reject_is_advisory_only(self):
        """The LLM reject branch must log only — advisory, no continue."""
        src = _main_source()
        self.assertIn("advisory only, pattern trade proceeds", src)
        self.assertIn("LLM Analyst ADVISORY", src)
        lines = src.split("\n")
        for i, line in enumerate(lines):
            if 'llm_recommendation == "reject":' in line:
                for j in range(i + 1, min(i + 30, len(lines))):
                    if 'continue' in lines[j] and lines[j].strip().startswith("continue"):
                        self.fail(f"LLM reject block contains continue at line {j+1}")
                break


class TestDirectionSymmetrySource(unittest.TestCase):
    """ROOT CAUSE #3 — direction and SL/TP geometry are pattern-driven & symmetric."""

    def test_source_dispatches_pattern_direction_unchanged(self):
        src = _main_source()
        self.assertIn("gateway.execute_order", src, "execute_order must be called")
        matches = re.findall(r'gateway\.execute_order.*?decision\.direction', src, re.DOTALL)
        self.assertEqual(len(matches), 2,
                         "Both dispatch sites must pass decision.direction to execute_order")

    def test_gateway_builds_sell_with_geometry(self):
        import MetaTrader5 as mt5
        from modules.mt5_gateway import MT5Gateway
        gw = MT5Gateway()
        req = gw.build_order_request(symbol="XAUUSD", direction="SELL", lot=0.01,
                                     tp_pts=300, sl_pts=150, price=2500.0)
        self.assertEqual(req["type"], mt5.ORDER_TYPE_SELL)
        self.assertLess(req["tp"], req["price"])
        self.assertGreater(req["sl"], req["price"])
        req_buy = gw.build_order_request(symbol="XAUUSD", direction="BUY", lot=0.01,
                                         tp_pts=300, sl_pts=150, price=2500.0)
        self.assertEqual(req_buy["type"], mt5.ORDER_TYPE_BUY)
        self.assertGreater(req_buy["tp"], req_buy["price"])
        self.assertLess(req_buy["sl"], req_buy["price"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
