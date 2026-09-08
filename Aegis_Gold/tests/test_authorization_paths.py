"""
===========================================================================
AEGIS GOLD v6.0 — Trade Authorization Architecture Tests
===========================================================================
Covers: TradeCandidate locks | CandidateRankingEngine | AuthorizationBuilder
gates (every WAIT_* code) | MacroAnalyzer + bias helpers | LTFTriggerEngine |
GPTBrain missing-model safety | _attach_authorization TRADE/WAIT downgrade.
===========================================================================
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

# Repo convention (tests/test_decision_integrity.py)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from brain.trade_candidate import TradeCandidate, TradeClass, SIGNAL_TYPES
from brain.candidate_ranking_engine import (
    CandidateRankingEngine,
    W_MACRO, W_SETUP, W_TRIGGER, W_QUANT, W_ML, W_PATTERN,
)
import brain.authorization_builder as ab
from brain.authorization_builder import build_trade_authorization
from brain.canonical_types import TradeAuthorization
import brain.macro_analyzer as ma
from brain.macro_analyzer import (
    MacroAnalyzer, MacroContext,
    macro_bias_matches_direction, macro_bias_contradicts,
)
from brain.ltf_trigger_engine import LTFTriggerEngine

# Optional heavyweight import — brain.brain pulls pandas/numpy/config chains;
# integration tests skip cleanly if unavailable in this environment.
try:
    from brain.brain import Decision, _attach_authorization
    BRAIN_OK = True
except Exception:                                   # pragma: no cover
    BRAIN_OK = False


# ---------------------------------------------------------------------------
# Synthetic candle builders + candidate/stub factories
# ---------------------------------------------------------------------------

def make_flat_candles(n=24, price=2350.0):
    """Perfectly flat candles — deterministic no-trigger/no-bias fixture."""
    return [{"timestamp": f"T{i}", "open": price, "high": price,
             "low": price, "close": price} for i in range(n)]


def make_trend_candles(n=60, start=2300.0, drift=1.5):
    """Monotonic trend candles (drift<0 = downtrend). Bodies overlap, no gaps."""
    out, px = [], start
    for i in range(n):
        o, c = px, px + drift
        hi = max(o, c) + abs(drift) * 0.4
        lo = min(o, c) - abs(drift) * 0.4
        out.append({"timestamp": f"T{i}", "open": o, "high": hi,
                    "low": lo, "close": c})
        px = c
    return out


def make_sweep_candles():
    """
    Engineered BUY liquidity-sweep + reclaim against _detect_liquidity_sweep:
      bars 6..17 form the detector's lows[-15:-3] window (min = 2345.4);
      bar -3 pierces below it; closes[-1] reclaims above it.
    """
    out, px = [], 2340.0
    for i in range(18):                       # higher-lows uptrend
        o, c = px, px + 1.0
        out.append({"timestamp": f"T{i}", "open": o, "high": c + 0.6,
                    "low": o - 0.6, "close": c})
        px = c
    base = min(c["low"] for c in out[6:18])   # exactly the detector window
    out.append({"timestamp": "S1", "open": px, "high": px + 0.5,
                "low": base - 2.0, "close": base + 1.0})          # sweep pierce
    out.append({"timestamp": "S2", "open": base + 1.0, "high": base + 2.5,
                "low": base + 0.2, "close": base + 1.8})          # settle
    out.append({"timestamp": "S3", "open": base + 1.8, "high": base + 3.6,
                "low": base + 1.2, "close": base + 1.6})          # reclaim close
    return out


def now_iso(offset_seconds=0):
    dt = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return dt.isoformat()


def make_candidate(**overrides):
    """Fully-valid XAUUSD candidate that passes every authorization gate."""
    base = dict(
        symbol="XAUUSD", direction="BUY", signal_type="SMALL_BREAKOUT",
        source_path="PATH_1", macro_bias="BULLISH",
        macro_score=0.80, setup_score=0.70, trigger_score=0.60,
        quant_score=0.70, ml_score=0.50, pattern_score=0.60,
        expected_value=2.00, risk_reward=1.60, spread_cost=0.35,
        entry_price=2360.00, stop_loss=2344.00, take_profit=2385.60,
        sl_points=160, tp_points=256, lot=0.01, confidence=0.70,
        timestamp=now_iso(), data_timestamp=now_iso(),
        causal_valid=True, risk_valid=True,
        final_score=0.0, wait_reason="", trade_class="",
    )
    base.update(overrides)
    return TradeCandidate(**base)


class AllowRiskManager:
    def can_trade(self):
        return True


class BlockRiskManager:
    def can_trade(self):
        return False


class DailyLossRiskManager(AllowRiskManager):
    def daily_loss_limit_hit(self):
        return True


class DuplicateEngineStub:
    def __init__(self):
        self.seen = []

    def is_duplicate(self, sig_hash):
        self.seen.append(sig_hash)
        return True

# ===========================================================================
# 1. TradeCandidate locks
# ===========================================================================

class TestTradeCandidateLocks(unittest.TestCase):

    def test_all_documented_signal_types_accepted(self):
        for sig in SIGNAL_TYPES:
            self.assertEqual(make_candidate(signal_type=sig).signal_type, sig)

    def test_macro_signals_derive_macro_continuation_class(self):
        for sig in ("MACRO_CONTINUATION", "MACRO_REVERSAL"):
            c = make_candidate(signal_type=sig)
            self.assertEqual(c.trade_class, TradeClass.MACRO_CONTINUATION.value)

    def test_small_signals_derive_small_pattern_class(self):
        for sig in SIGNAL_TYPES:
            if sig.startswith("MACRO"):
                continue
            c = make_candidate(signal_type=sig)
            self.assertEqual(c.trade_class, TradeClass.SMALL_PATTERN.value)

    def test_explicit_trade_class_is_not_overridden(self):
        self.assertEqual(make_candidate(trade_class="CUSTOM").trade_class, "CUSTOM")

    def test_signal_hash_deterministic_and_sensitive(self):
        h1, h2 = make_candidate().signal_hash(), make_candidate().signal_hash()
        self.assertEqual(h1, h2)
        moved = make_candidate(entry_price=make_candidate().entry_price + 0.5)
        self.assertNotEqual(h1, moved.signal_hash())
        flipped = make_candidate(direction="SELL")
        self.assertNotEqual(h1, flipped.signal_hash())

    def test_to_dict_roundtrip_keys(self):
        d = make_candidate().to_dict()
        required = {
            "symbol", "direction", "signal_type", "source_path", "macro_bias",
            "expected_value", "risk_reward", "spread_cost", "entry_price",
            "stop_loss", "take_profit", "sl_points", "tp_points", "lot",
            "confidence", "final_score", "wait_reason", "trade_class",
        }
        missing = required - set(d.keys())
        self.assertFalse(missing, f"to_dict missing keys: {missing}")


# ===========================================================================
# 2. Candidate Ranking Engine
# ===========================================================================

class TestCandidateRankingEngine(unittest.TestCase):

    def setUp(self):
        self.engine = CandidateRankingEngine()

    def test_perfect_scores_clamp_to_one(self):
        c = make_candidate(macro_score=1.0, setup_score=1.0, trigger_score=1.0,
                           quant_score=1.0, ml_score=1.0, pattern_score=1.0,
                           spread_cost=0.0)
        s = self.engine.score(c)
        self.assertAlmostEqual(s, 1.0, places=3)
        self.assertAlmostEqual(c.final_score, s, places=3)

    def test_any_zero_component_collapses_weighted_product(self):
        s = self.engine.score(make_candidate(ml_score=0.0, spread_cost=0.0))
        self.assertAlmostEqual(s, 0.0, places=4)

    def test_spread_penalty_is_linear_ten_percent_per_dollar(self):
        clean = make_candidate(spread_cost=0.0)
        costly = make_candidate(spread_cost=1.50)
        s_clean, s_costly = self.engine.score(clean), self.engine.score(costly)
        # default profile ~= e^-0.395 = 0.674 -> penalty 0.15 stays unclamped
        self.assertAlmostEqual(s_clean - s_costly, 0.15, places=4)
        self.assertLess(s_costly, s_clean)

    def test_mid_profile_scores_in_expected_band(self):
        s = self.engine.score(make_candidate())
        self.assertGreater(s, 0.30)
        self.assertLess(s, 0.85)

    def test_rank_picks_higher_scoring_candidate(self):
        weaker = make_candidate(source_path="PATH_2", entry_price=2351.50,
                                stop_loss=2335.50, macro_score=0.40,
                                setup_score=0.40, trigger_score=0.40,
                                quant_score=0.40, ml_score=0.40,
                                pattern_score=0.40)
        stronger = make_candidate(source_path="PATH_3", entry_price=2360.90,
                                  stop_loss=2344.90, macro_score=0.95,
                                  setup_score=0.95, trigger_score=0.95,
                                  quant_score=0.95, ml_score=0.95,
                                  pattern_score=0.95)
        self.assertNotEqual(weaker.signal_hash(), stronger.signal_hash())
        best = self.engine.rank([weaker, stronger])
        self.assertIs(best, stronger)
        self.assertEqual(best.source_path, "PATH_3")

    def test_rank_returns_none_for_empty_or_invalid(self):
        self.assertIsNone(self.engine.rank([]))
        self.assertIsNone(self.engine.rank([make_candidate(causal_valid=False)]))
        self.assertIsNone(self.engine.rank([make_candidate(risk_valid=False)]))

    def test_rank_deduplicates_identical_signals_within_engine(self):
        c1 = make_candidate(source_path="PATH_0")
        c2 = make_candidate(source_path="PATH_1")   # path differs, hash does not
        self.assertEqual(c1.signal_hash(), c2.signal_hash())
        best = self.engine.rank([c1, c2])
        self.assertIsNotNone(best)
        self.assertIsNone(self.engine.rank([make_candidate()]))  # replay blocked

    def test_reset_clears_seen_hashes(self):
        self.assertIsNotNone(self.engine.rank([make_candidate()]))
        self.engine.reset()
        self.assertIsNotNone(self.engine.rank([make_candidate()]))

    def test_weight_constants_locked(self):
        self.assertEqual((W_MACRO, W_SETUP, W_TRIGGER,
                          W_QUANT, W_ML, W_PATTERN),
                         (0.25, 0.25, 0.20, 0.15, 0.10, 0.05))

# ===========================================================================
# 3. AuthorizationBuilder gates — every WAIT_* reason code
# ===========================================================================

AUTH_KW = dict(risk_mgr=None, spread_pts=20.0, point=0.01,
               anti_duplicate_engine=None)


def _auth(candidate, decision_timestamp=None, **kw):
    args = dict(AUTH_KW)
    args.update(kw)
    return build_trade_authorization(
        candidate, args["risk_mgr"], args["spread_pts"], args["point"],
        decision_timestamp or now_iso(), args["anti_duplicate_engine"])


class TestAuthorizationBuilderGates(unittest.TestCase):

    def _expect_block(self, code, **tweaks):
        c = make_candidate(**tweaks)
        self.assertIsNone(_auth(c))
        self.assertEqual(c.wait_reason, code)
        return c

    # ---- happy path + canonical field mapping -----------------------------

    def test_valid_candidate_produces_authorized_contract(self):
        c = make_candidate()
        auth = _auth(c)
        self.assertIsInstance(auth, TradeAuthorization)
        self.assertTrue(auth.authorized)
        self.assertEqual(c.wait_reason, "")
        self.assertEqual(auth.symbol, "XAUUSD")
        self.assertEqual(auth.direction, "BUY")
        self.assertEqual(auth.lot, 0.01)
        self.assertAlmostEqual(auth.entry_price, 2360.00)
        self.assertAlmostEqual(auth.stop_loss, 2344.00)
        self.assertAlmostEqual(auth.take_profit, 2385.60)
        self.assertEqual((auth.sl_points, auth.tp_points), (160, 256))
        self.assertAlmostEqual(auth.target_usd, 2.00)
        self.assertAlmostEqual(auth.risk_usd, abs(2360.00 - 2344.00) * 0.01 * 100)
        self.assertEqual(auth.source_path, "PATH_1")
        self.assertEqual((auth.pattern_id, auth.signal_type,
                          auth.macro_bias), ("SMALL_BREAKOUT",) * 2 + ("BULLISH",))
        self.assertEqual(auth.authorization_version, "v2.0")
        self.assertTrue(auth.causal_validity)
        self.assertTrue(auth.authorization_id.startswith("AUTH_"))
        ctx = auth.local_ai_context
        for key in ("source_path", "signal_type", "macro_bias", "final_score",
                    "trade_class", "risk_reward", "expected_value"):
            self.assertIn(key, ctx)

    def test_gate_order_direction_precedes_causality(self):
        c = self._expect_block(ab.WAIT_INVALID_DIRECTION,
                               direction="LONG", causal_valid=False)
        self.assertFalse(c.causal_valid)   # untouched -> proves early exit

    def test_invalid_direction_blocked(self):
        for bad in ("LONG", "SHORT", "", "buy_lower"):
            self._expect_block(ab.WAIT_INVALID_DIRECTION, direction=bad)

    def test_causality_failure_blocked(self):
        self._expect_block(ab.WAIT_CAUSALITY_FAILURE, causal_valid=False)

    def test_staleness_window(self):
        self._expect_block(ab.WAIT_STALE_SETUP, data_timestamp=now_iso(-400))
        fresh = make_candidate(data_timestamp=now_iso(-60))
        self.assertTrue(_auth(fresh).authorized)

    def test_negative_or_zero_ev_blocked(self):
        for ev in (-0.50, 0.0):
            self._expect_block(ab.WAIT_NEGATIVE_EV, expected_value=ev)

    def test_rr_thresholds_by_trade_class(self):
        # small-pattern class: >= 1.25 (strict below)
        self._expect_block(ab.WAIT_RR_TOO_LOW, risk_reward=1.00)
        self._expect_block(ab.WAIT_RR_TOO_LOW, risk_reward=1.24)
        self.assertTrue(_auth(make_candidate(risk_reward=1.25)).authorized)
        # macro class demands >= 1.50 (stricter)
        self._expect_block(ab.WAIT_RR_TOO_LOW,
                           signal_type="MACRO_CONTINUATION", risk_reward=1.45)
        cmac = make_candidate(signal_type="MACRO_CONTINUATION", risk_reward=1.50)
        self.assertTrue(_auth(cmac).authorized)          # boundary inclusive

    def test_spread_cost_cap_vs_expected_value(self):
        # cost = s * p * lot * 100 ; cap = 0.5 * max(EV, 1.0) = 1.0 USD here
        c = make_candidate(expected_value=2.00)
        self.assertIsNone(_auth(c, spread_pts=110.0))
        self.assertEqual(c.wait_reason, ab.WAIT_SPREAD_TOO_HIGH)
        ok = make_candidate(expected_value=2.00)         # exactly at cap passes
        self.assertTrue(_auth(ok, spread_pts=100.0).authorized)

    def test_sl_floors_per_symbol(self):
        self._expect_block(ab.WAIT_SL_TOO_TIGHT, sl_points=149)
        self.assertTrue(_auth(make_candidate(sl_points=150)).authorized)
        self._expect_block(ab.WAIT_SL_TOO_TIGHT, symbol="EURUSD", sl_points=39)
        self.assertTrue(_auth(make_candidate(symbol="EURUSD",
                                             sl_points=40)).authorized)

    def test_lot_bounds_enforced(self):
        # spread_pts=0 disables the earlier spread gate (lot multiplies into it)
        for bad in (0.0, 11.0, -0.05):
            c = make_candidate(lot=bad)
            self.assertIsNone(_auth(c, spread_pts=0.0))
            self.assertEqual(c.wait_reason, ab.WAIT_LOT_INVALID)
        self.assertTrue(_auth(make_candidate(lot=10.0), spread_pts=0.0).authorized)

    def test_macro_contradiction_blocks_and_neutral_passes(self):
        for bias, d in (("STRONG_BEARISH", "BUY"), ("BEARISH", "BUY"),
                        ("BULLISH", "SELL"), ("STRONG_BULLISH", "SELL")):
            self._expect_block(ab.WAIT_MACRO_CONTRADICTION,
                               macro_bias=bias, direction=d)
        neu = make_candidate(macro_bias="NEUTRAL", direction="SELL")
        self.assertTrue(_auth(neu).authorized)           # NEUTRAL never vetoes

    def test_duplicate_signal_engine_wired_with_correct_hash(self):
        dup = DuplicateEngineStub()
        c = make_candidate()
        self.assertIsNone(_auth(c, anti_duplicate_engine=dup))
        self.assertEqual(c.wait_reason, ab.WAIT_DUPLICATE_SIGNAL)
        self.assertEqual(dup.seen, [c.signal_hash()])
        passthrough = DuplicateEngineStub()
        passthrough.is_duplicate = lambda h: False
        good = make_candidate()
        self.assertTrue(_auth(good, anti_duplicate_engine=passthrough).authorized)

    def test_risk_manager_and_daily_loss_breaker(self):
        c = make_candidate()
        self.assertIsNone(_auth(c, risk_mgr=BlockRiskManager()))
        self.assertEqual(c.wait_reason, ab.WAIT_RISK_LIMIT)
        c2 = make_candidate()
        self.assertIsNone(_auth(c2, risk_mgr=DailyLossRiskManager()))
        self.assertEqual(c2.wait_reason, ab.WAIT_DAILY_LOSS_LIMIT)
        self.assertTrue(_auth(make_candidate(),
                              risk_mgr=AllowRiskManager()).authorized)

# ===========================================================================
# 4. Macro bias helpers + MacroAnalyzer
# ===========================================================================

class TestMacroBiasHelpers(unittest.TestCase):

    def test_matches_direction_semantics(self):
        self.assertTrue(macro_bias_matches_direction("STRONG_BULLISH", "BUY"))
        self.assertTrue(macro_bias_matches_direction("BULLISH", "BUY"))
        self.assertTrue(macro_bias_matches_direction("BEARISH", "SELL"))
        self.assertTrue(macro_bias_matches_direction("STRONG_BEARISH", "SELL"))
        self.assertFalse(macro_bias_matches_direction("NEUTRAL", "BUY"))
        self.assertFalse(macro_bias_matches_direction("NEUTRAL", "SELL"))
        self.assertFalse(macro_bias_matches_direction("BULLISH", "SELL"))
        self.assertFalse(macro_bias_matches_direction("ANYTHING", ""))

    def test_contradiction_semantics(self):
        self.assertTrue(macro_bias_contradicts("BEARISH", "BUY"))
        self.assertTrue(macro_bias_contradicts("STRONG_BEARISH", "BUY"))
        self.assertTrue(macro_bias_contradicts("BULLISH", "SELL"))
        self.assertTrue(macro_bias_contradicts("STRONG_BULLISH", "SELL"))
        # NEUTRAL is never a contradiction (small patterns allowed through)
        for d in ("BUY", "SELL"):
            self.assertFalse(macro_bias_contradicts("NEUTRAL", d))
            self.assertFalse(macro_bias_contradicts("", d))


class TestMacroAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = MacroAnalyzer()

    def test_flat_market_is_neutral(self):
        ctx = self.analyzer.analyze("XAUUSD", make_flat_candles(),
                                    make_flat_candles(), make_flat_candles())
        self.assertIsInstance(ctx, MacroContext)
        self.assertEqual(ctx.bias, ma.NEUTRAL)
        self.assertEqual(ctx.h4_trend, "NEUTRAL")
        self.assertAlmostEqual(ctx.h4_bias, 0.0)
        self.assertAlmostEqual(ctx.score, 0.0)

    def test_short_data_falls_back_to_neutral(self):
        ctx = self.analyzer.analyze("XAUUSD", make_flat_candles(10),
                                    make_flat_candles(12), make_flat_candles(14))
        self.assertEqual(ctx.bias, ma.NEUTRAL)

    def test_strong_uptrend_reads_bullish_family(self):
        up = make_trend_candles(n=80)
        ctx = self.analyzer.analyze("XAUUSD", up, up, up)
        self.assertIn(ctx.bias, (ma.BULLISH, ma.STRONG_BULLISH))
        self.assertGreater(ctx.score, 0.5)
        self.assertTrue(macro_bias_matches_direction(ctx.bias, "BUY"))
        self.assertFalse(macro_bias_contradicts(ctx.bias, "BUY"))

    def test_strong_downtrend_mirrors_bearish(self):
        dn = make_trend_candles(n=80, drift=-1.5)
        ctx = self.analyzer.analyze("XAUUSD", dn, dn, dn)
        self.assertIn(ctx.bias, (ma.BEARISH, ma.STRONG_BEARISH))
        self.assertLess(ctx.score, -0.5)
        self.assertTrue(macro_bias_matches_direction(ctx.bias, "SELL"))
        self.assertTrue(macro_bias_contradicts(ctx.bias, "BUY"))

    def test_timeframe_weights_dominate_hierarchy(self):
        # H4 bullish trend against M15 bearish -> H4 weight 0.45 keeps net positive
        up, dn = make_trend_candles(n=80), make_trend_candles(n=80, drift=-1.5)
        ctx = self.analyzer.analyze("XAUUSD", up, up, dn)
        self.assertIn(ctx.bias,
                      (ma.BULLISH, ma.STRONG_BULLISH, ma.NEUTRAL))
        self.assertNotIn(ctx.bias, (ma.BEARISH, ma.STRONG_BEARISH))

    def test_get_last_context_returns_latest_result(self):
        ctx = self.analyzer.analyze("XAUUSD", make_flat_candles(),
                                    make_flat_candles(), make_flat_candles())
        self.assertIs(self.analyzer.get_last_context(), ctx)

# ===========================================================================
# 5. LTF Trigger Engine
# ===========================================================================

from brain.ltf_trigger_engine import TriggerResult


class TestLTFTriggerEngine(unittest.TestCase):

    def setUp(self):
        self.engine = LTFTriggerEngine()

    def test_result_defaults_are_safe(self):
        r = TriggerResult()
        self.assertFalse(r.valid)
        self.assertEqual(r.signal_type, "NONE")
        self.assertEqual(r.trigger_score, 0.0)

    def test_insufficient_data_guard(self):
        short = make_flat_candles()[:5]
        r = self.engine.find_trigger(short, [], "BUY")
        self.assertFalse(r.valid)
        self.assertIn("INSUFFICIENT", r.reason.upper())

    def test_flat_market_fires_no_trigger(self):
        flat = make_flat_candles()
        for d in ("BUY", "SELL"):
            r = self.engine.find_trigger(flat, [], d)
            self.assertFalse(r.valid)
            self.assertEqual(r.signal_type, "NONE")
            self.assertEqual(r.trigger_score, 0.0)

    def test_engineered_sweep_reclaim_validates_buy(self):
        r = self.engine.find_trigger(make_sweep_candles(), [], "BUY")
        self.assertTrue(r.valid, f"expected trigger: {r.signal_type}/{r.reason}")
        self.assertGreater(r.trigger_score, 0.0)
        self.assertLessEqual(r.trigger_score, 1.0)
        self.assertGreater(r.entry_price, 0.0)
        self.assertGreater(r.entry_price, r.stop_loss)   # SL protective below buy

    def test_downtrend_sell_produces_low_side_trigger(self):
        dn = make_trend_candles(n=60, drift=-1.5)
        r = self.engine.find_trigger(dn, [], "SELL")
        self.assertTrue(r.valid, f"expected trigger: {r.signal_type}/{r.reason}")
        self.assertGreater(r.trigger_score, 0.0)
        self.assertLess(r.entry_price, r.stop_loss)      # SL protective above sell

# ===========================================================================
# 6. GPTBrain — missing model must never trade (v6.0 silent-weight fix)
# ===========================================================================

try:
    from brain.gpt_brain import GPTBrain
except Exception:                                   # pragma: no cover
    GPTBrain = None


@unittest.skipUnless(GPTBrain is not None, "brain.gpt_brain not importable")
class TestGPTBrainSafety(unittest.TestCase):

    def test_missing_model_file_is_unavailable_and_never_trades(self):
        missing = os.path.join(ROOT, "models", "__definitely_not_present__.pt")
        gb = GPTBrain(model_path=missing)
        self.assertNotEqual(gb.gpt_status, "READY")
        action, conf, tag = gb.decide([50, 50, 50, 150, 150, 300, 0.01])
        self.assertEqual(action, "WAIT")
        self.assertEqual(conf, 0)
        self.assertIn("UNAVAILABLE", tag)

    def test_decide_stays_wait_regardless_of_history_depth(self):
        missing = os.path.join(ROOT, "models", "__definitely_not_present__.pt")
        gb = GPTBrain(model_path=missing)
        feat = [50, 50, 50, 150, 150, 300, 0.01]
        for _ in range(30):                          # far beyond 16-bar window
            self.assertEqual(gb.decide(feat)[0], "WAIT")

# ===========================================================================
# 7. _attach_authorization integration (TRADE attach / WAIT downgrade)
# ===========================================================================

if BRAIN_OK:

    class ExplodingRiskManager:
        def can_trade(self):
            raise RuntimeError("boom")

    class TestAttachAuthorizationIntegration(unittest.TestCase):

        def _trade_decision(self, **overrides):
            d = Decision(action="TRADE", direction="BUY", lot=0.01,
                         tp_points=300, sl_points=180, confidence=70,
                         rr_ratio=0.0, structure_score=70, entry_score=60,
                         consensus_score=0.6)
            for k, v in overrides.items():
                setattr(d, k, v)
            return d

        def _attach(self, decision=None, **kw):
            args = dict(symbol="XAUUSD", candles_m5=make_flat_candles(),
                        spread=20.0, point=0.01, risk_mgr=None, lot=0.01,
                        macro_bias="BULLISH", source_path="PATH_2",
                        signal_type="SMALL_BREAKOUT")
            args.update(kw)
            return _attach_authorization(decision or self._trade_decision(),
                                         **args)

        def test_non_trade_decisions_pass_through_untouched(self):
            wait_dec = Decision(action="WAIT", reason="no setup")
            self.assertIs(self._attach(wait_dec), wait_dec)

        def test_trade_receives_canonical_authorization(self):
            dec = self._trade_decision()
            out = self._attach(dec)
            self.assertIs(out, dec)
            auth = dec.trade_authorization
            self.assertIsNotNone(auth)
            self.assertTrue(auth.authorized)
            self.assertEqual(auth.source_path, "PATH_2")
            self.assertEqual(auth.signal_type, "SMALL_BREAKOUT")
            self.assertEqual((auth.sl_points, auth.tp_points), (180, 300))
            self.assertAlmostEqual(auth.lot, 0.01)
            self.assertTrue(auth.authorization_id.startswith("AUTH_"))

        def test_invalid_direction_downgrades_to_wait_with_code(self):
            bad = self._trade_decision(direction="FROBNICATE")
            out = self._attach(bad)
            self.assertIsNot(out, bad)                   # replaced, not mutated
            self.assertEqual(out.action, "WAIT")
            self.assertTrue(out.reason.startswith("AUTHORIZATION_FAILED:"))
            self.assertIn(ab.WAIT_INVALID_DIRECTION, out.reason)
            self.assertIsNone(bad.trade_authorization)

        def test_macro_contradiction_downgrades_to_wait(self):
            out = self._attach(macro_bias="STRONG_BEARISH")
            self.assertEqual(out.action, "WAIT")
            self.assertIn(ab.WAIT_MACRO_CONTRADICTION, out.reason)

        def test_wide_spread_downgrades_to_wait(self):
            # ev=1.75 -> cap 0.875 USD ; cost @spread=100 -> 1.00 exceeds cap
            out = self._attach(spread=100.0)
            self.assertEqual(out.action, "WAIT")
            self.assertIn(ab.WAIT_SPREAD_TOO_HIGH, out.reason)

        def test_risk_limit_and_duplicate_downgrade_to_wait(self):
            out = self._attach(risk_mgr=BlockRiskManager())
            self.assertEqual(out.action, "WAIT")
            self.assertIn(ab.WAIT_RISK_LIMIT, out.reason)
            out2 = self._attach(anti_duplicate_engine=DuplicateEngineStub())
            self.assertEqual(out2.action, "WAIT")
            self.assertIn(ab.WAIT_DUPLICATE_SIGNAL, out2.reason)

        def test_risk_manager_exception_is_fail_safe_not_fatal(self):
            out = self._attach(risk_mgr=ExplodingRiskManager())
            self.assertEqual(out.action, "TRADE")        # gate swallowed error
            self.assertTrue(out.trade_authorization.authorized)


if __name__ == "__main__":
    unittest.main(verbosity=2)







