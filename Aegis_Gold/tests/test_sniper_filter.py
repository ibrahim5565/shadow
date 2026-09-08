"""
===========================================================================
🧪 AEGIS GOLD — Sniper Filter Unit Test Suite (test_sniper_filter.py)
===========================================================================
Tests all Triple-Lock conditions and auto-tighten mechanism.
Must run 6/6 PASS before deployment.
===========================================================================
"""

import os
import sys
import json
import unittest
import tempfile

# Force UTF-8 on Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from brain.sniper_filter import SniperFilter, build_sniper_setup


def _make_filter(tmp_dir, ml_conf=0.85, smc_conf=0.80, htf_conf=0.80, require_sweep=True):
    """Helper: creates a SniperFilter backed by a tmp file."""
    sf = SniperFilter(
        persistence_file=os.path.join(tmp_dir, "test_sniper_state.json")
    )
    sf.ml_conf_min  = ml_conf
    sf.smc_conf_min = smc_conf
    sf.htf_conf_min = htf_conf
    sf.require_sweep = require_sweep
    return sf


def _make_valid_setup(direction="BUY", mode="BIG_PATTERN", sweep=True,
                      smc_conf=0.85, htf_conf=0.82, atr_ratio=1.2):
    return {
        "mode":            mode,
        "direction":       direction,
        "smc_confidence":  smc_conf,
        "fvg_present":     True,
        "htf_confidence":  htf_conf,
        "htf_direction":   "bullish" if direction == "BUY" else "bearish",
        "atr_ratio":       atr_ratio,
        "sweep_confirmed": sweep,
    }


def _make_valid_votes(direction="BUY", ml_conf=0.88):
    ml_dir = "bullish" if direction == "BUY" else "bearish"
    return {
        "ml_ensemble": {"direction": ml_dir, "confidence": ml_conf},
        "quant":       {"direction": ml_dir, "confidence": 0.75},
        "neural":      {"direction": ml_dir, "confidence": 0.72},
    }


class TestSniperFilter(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    # ────────────────────────────────────────────────────────────
    # TEST 1: Triple-Lock ALL PASS
    # ────────────────────────────────────────────────────────────
    def test_triple_lock_all_pass(self):
        """All 3 locks above threshold → is_sniper_setup() returns True."""
        sf = _make_filter(self.tmp)
        setup = _make_valid_setup("BUY", "BIG_PATTERN", sweep=True)
        votes = _make_valid_votes("BUY", ml_conf=0.90)

        ok, reason = sf.is_sniper_setup(setup, votes)
        self.assertTrue(ok, f"Expected PASS but got: {reason}")
        self.assertEqual(reason, "SNIPER_PASS")
        print(f"\n[TEST 1] Triple-Lock ALL PASS: {reason} ✅")

    # ────────────────────────────────────────────────────────────
    # TEST 2: Scalp Mode Rejected
    # ────────────────────────────────────────────────────────────
    def test_scalp_mode_rejected(self):
        """Any setup with mode=SCALP must always return False."""
        sf = _make_filter(self.tmp)
        setup = _make_valid_setup("BUY", mode="SCALP")
        votes = _make_valid_votes("BUY", ml_conf=0.99)

        ok, reason = sf.is_sniper_setup(setup, votes)
        self.assertFalse(ok, "Expected scalp to be rejected")
        self.assertIn("SCALP_DISABLED", reason)
        print(f"\n[TEST 2] Scalp Mode Rejected: {reason} ✅")

    # ────────────────────────────────────────────────────────────
    # TEST 3: ML Threshold Fail (0.84 < 0.85)
    # ────────────────────────────────────────────────────────────
    def test_ml_threshold_fail(self):
        """ML confidence just below threshold (0.84 < 0.85) → False."""
        sf = _make_filter(self.tmp, ml_conf=0.85)
        setup = _make_valid_setup("BUY", "BIG_PATTERN")
        votes = _make_valid_votes("BUY", ml_conf=0.84)   # Just below threshold

        ok, reason = sf.is_sniper_setup(setup, votes)
        self.assertFalse(ok, "Expected ML threshold fail")
        self.assertIn("SNIPER_ML_FAIL", reason)
        self.assertIn("ml_conf=0.84", reason)
        print(f"\n[TEST 3] ML Threshold Fail: {reason} ✅")

    # ────────────────────────────────────────────────────────────
    # TEST 4: HTF Conflict / Direction Mismatch Fail
    # ────────────────────────────────────────────────────────────
    def test_htf_conflict_fail(self):
        """HTF direction conflicts with setup direction → False."""
        sf = _make_filter(self.tmp)
        setup = _make_valid_setup("BUY", "BIG_PATTERN")
        # Force HTF to bearish while setup is BUY
        setup["htf_direction"] = "bearish"
        votes = _make_valid_votes("BUY", ml_conf=0.90)

        ok, reason = sf.is_sniper_setup(setup, votes)
        self.assertFalse(ok, "Expected HTF conflict to fail")
        self.assertIn("SNIPER_HTF_FAIL", reason)
        self.assertIn("direction_mismatch", reason)
        print(f"\n[TEST 4] HTF Conflict Fail: {reason} ✅")

    # ────────────────────────────────────────────────────────────
    # TEST 5: ATR Spike / Volatility Guard Fail
    # ────────────────────────────────────────────────────────────
    def test_atr_spike_fail(self):
        """ATR ratio 3.0 > max 2.5 (news spike) → False."""
        sf = _make_filter(self.tmp)
        setup = _make_valid_setup("SELL", "SMALL_PATTERN", sweep=False, atr_ratio=3.0)
        setup["htf_direction"] = "bearish"  # align for SELL
        votes = _make_valid_votes("SELL", ml_conf=0.91)

        ok, reason = sf.is_sniper_setup(setup, votes)
        self.assertFalse(ok, "Expected ATR spike to fail")
        self.assertIn("SNIPER_ATR_FAIL", reason)
        self.assertIn("atr_ratio=3.00", reason)
        print(f"\n[TEST 5] ATR Spike Fail (atr=3.00): {reason} ✅")

    # ────────────────────────────────────────────────────────────
    # TEST 6: Auto-Tighten Activates on Low WR
    # ────────────────────────────────────────────────────────────
    def test_auto_tighten_activates(self):
        """WR of 92% over 50 trades → ml_conf_min tightens from 0.85 → 0.87."""
        sf = _make_filter(self.tmp, ml_conf=0.85)
        sf.auto_tighten = True
        sf.tighten_step = 0.02
        sf._tighten_wr_floor = 0.95
        sf._tighten_window = 50

        # Simulate 50 trades: 46 wins, 4 losses → WR = 92%
        sf._result_history = [True] * 46 + [False] * 4

        initial_ml = sf.ml_conf_min
        sf._maybe_tighten()

        self.assertGreater(sf.ml_conf_min, initial_ml,
                           "ml_conf_min should have tightened")
        self.assertAlmostEqual(sf.ml_conf_min, 0.87, places=2)

        wr = sf.current_sniper_wr()
        print(f"\n[TEST 6] Auto-Tighten: WR={wr*100:.0f}% → ml_conf_min {initial_ml:.2f} → {sf.ml_conf_min:.2f} ✅")

    # ────────────────────────────────────────────────────────────
    # TEST 7: Big Pattern requires sweep (PO3)
    # ────────────────────────────────────────────────────────────
    def test_big_pattern_sweep_required(self):
        """BIG_PATTERN without sweep_confirmed → False when require_sweep=True."""
        sf = _make_filter(self.tmp, require_sweep=True)
        setup = _make_valid_setup("BUY", "BIG_PATTERN", sweep=False)  # No sweep
        votes = _make_valid_votes("BUY", ml_conf=0.92)

        ok, reason = sf.is_sniper_setup(setup, votes)
        self.assertFalse(ok, "Expected sweep requirement to fail for BIG_PATTERN")
        self.assertIn("SNIPER_SWEEP_FAIL", reason)
        print(f"\n[TEST 7] Big Pattern Sweep Required: {reason} ✅")

    # ────────────────────────────────────────────────────────────
    # TEST 8: Small Pattern does NOT require sweep
    # ────────────────────────────────────────────────────────────
    def test_small_pattern_no_sweep_needed(self):
        """SMALL_PATTERN does not require sweep — all other locks pass → PASS."""
        sf = _make_filter(self.tmp, require_sweep=True)
        setup = _make_valid_setup("SELL", "SMALL_PATTERN", sweep=False)
        setup["htf_direction"] = "bearish"
        votes = _make_valid_votes("SELL", ml_conf=0.89)

        ok, reason = sf.is_sniper_setup(setup, votes)
        self.assertTrue(ok, f"SMALL_PATTERN should not require sweep: {reason}")
        self.assertEqual(reason, "SNIPER_PASS")
        print(f"\n[TEST 8] Small Pattern No Sweep Needed: {reason} ✅")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  AEGIS GOLD — Sniper Filter Test Suite")
    print("=" * 60)
    unittest.main(verbosity=2)
