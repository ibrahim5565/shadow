import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.adaptive_consensus_brain import SegmentedAdaptiveConsensusBrain, ENGINES

class TestAdaptiveConsensusBrain(unittest.TestCase):

    def setUp(self):
        self.test_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "test_engine_weights.json"))
        if os.path.exists(self.test_json):
            os.remove(self.test_json)
        self.brain = SegmentedAdaptiveConsensusBrain(persistence_file=self.test_json)

    def tearDown(self):
        if os.path.exists(self.test_json):
            os.remove(self.test_json)

    def test_segment_key(self):
        key1 = self.brain._get_segment_key("OVERLAP", "scalp")
        self.assertEqual(key1, "OVERLAP_scalp")

        key2 = self.brain._get_segment_key("LONDON", "pro_trend")
        self.assertEqual(key2, "LONDON_big_pattern")

    def test_default_weights(self):
        w = self.brain.get_weights("NY", "small_pattern")
        self.assertEqual(len(w), len(ENGINES))
        self.assertAlmostEqual(sum(w.values()), 1.0, places=2)

    def test_segmented_weight_update(self):
        # Create dummy trade history with high accuracy for 'neural' engine in OVERLAP scalp
        trade_history = []
        for i in range(10):
            trade_history.append({
                "session": "OVERLAP",
                "mode": "scalp",
                "direction": "buy",
                "outcome": "WIN",
                "pnl_usd": 15.0,
                "engine_votes": {
                    "neural": {"direction": "bullish"},
                    "quant": {"direction": "bearish"},
                    "ml_ensemble": {"direction": "neutral"}
                }
            })

        new_w = self.brain.update_weights(trade_history, session="OVERLAP", mode="scalp", smoothing_factor=0.95)
        self.assertAlmostEqual(sum(new_w.values()), 1.0, places=2)
        # Neural weight should increase above default weight
        self.assertGreater(new_w["neural"], 1.0 / len(ENGINES))
        print("\n[ADAPTIVE BRAIN TEST] Updated OVERLAP scalp weights:", new_w)


if __name__ == "__main__":
    unittest.main()
