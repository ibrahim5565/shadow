"""
Measurement-only guard: [DECISION_TRACE] logging must not change decisions.

For identical inputs, compare the Decision produced with the trace emitter
active vs. silenced (patched to a no-op). All stable fields must be
identical in both modes, for one case per gate:
  - PATTERN_GATE   (no pattern -> WAIT)
  - RISK_GATE      (pattern + blocked risk -> WAIT, direction preserved)
  - PATTERN_ENGINE (pattern + clear risk -> TRADE)

Candles use the dict-list form so get_pattern_entry_signal() slices the
forming bar at [-1] and reads the closed bar at [-2].
"""

import copy
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import brain.brain as brain_mod
from brain.brain import _decide_impl, _emit_decision_trace


class _PermissiveRisk:
    """Risk manager stub that clears every risk gate inside _decide_impl."""

    lot_override = 0.0

    def can_trade(self, *a, **k):
        return True

    def is_daily_loss_limit_reached(self, *a, **k):
        return False

    def volatility_scaled_lot(self, *a, **k):
        return 0.01


class _BlockingRisk(_PermissiveRisk):
    def can_trade(self, *a, **k):
        return False

    def is_daily_loss_limit_reached(self, *a, **k):
        return False


def _flat_candles(n=60, base=2500.0, step=0.1):
    return [
        {"time": i, "open": base + i * step, "high": base + i * step + 0.3,
         "low": base + i * step - 0.3, "close": base + i * step}
        for i in range(n)
    ]


def _engulfing_candles(tbase=1000):
    """Bullish engulfing on closed bar [-2]; inert forming bar [-1]."""
    candles = _flat_candles(60, base=2500.0, step=0.0)
    for i, c in enumerate(candles):
        c["time"] = tbase + i
    candles[-3] = {"time": tbase + 57, "open": 2510.0, "high": 2512.0,
                   "low": 2498.0, "close": 2500.0}
    candles[-2] = {"time": tbase + 58, "open": 2496.0, "high": 2516.0,
                   "low": 2494.0, "close": 2514.0}
    candles[-1] = {"time": tbase + 59, "open": 2514.0, "high": 2515.0,
                   "low": 2513.0, "close": 2514.2}
    return candles


def _snapshot(dec):
    """Stable comparable projection of a Decision (excludes volatile ids)."""
    return {
        "action": dec.action,
        "direction": dec.direction,
        "pattern_direction": getattr(dec, "pattern_direction", "NA"),
        "reason": dec.reason,
        "pattern": dec.pattern,
        "confidence": dec.confidence,
        "signal_source": dec.signal_source,
        "mode": dec.mode,
        "grade": dec.grade,
        "lot": dec.lot,
        "sl_points": dec.sl_points,
        "tp_points": dec.tp_points,
        "rr_ratio": dec.rr_ratio,
        "regime": dec.regime,
        "atr_estimate": dec.atr_estimate,
    }


class _trace_capture:
    """Capture [DECISION_TRACE] records emitted via aegis.brain logger."""

    def __enter__(self):
        self.records = []

        class _H(logging.Handler):
            def emit(h, rec):
                if "[DECISION_TRACE]" in rec.getMessage():
                    self.records.append(rec.getMessage())

        self.handler = _H()
        logging.getLogger().addHandler(self.handler)
        self.prev = logging.getLogger("aegis.brain").level
        logging.getLogger("aegis.brain").setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        return self.records

    def __exit__(self, *exc):
        logging.getLogger().removeHandler(self.handler)
        logging.getLogger("aegis.brain").setLevel(self.prev)
        return False


_CASE_COUNTER = {"v": 0}


def _run_case(candles, risk_mgr, spread):
    if hasattr(_decide_impl, "_analyzed_candles"):
        _decide_impl._analyzed_candles.clear()
    if hasattr(_decide_impl, "_traded_candles"):
        _decide_impl._traded_candles.clear()
    account = {"equity": 10000.0, "balance": 10000.0}

    def _fresh():
        # Fresh candle epoch per run so CANDLE_DEDUPLICATION cannot fire
        # across the traced/silenced comparison runs.
        _CASE_COUNTER["v"] += 1
        base = 1_000_000 * _CASE_COUNTER["v"]
        out = copy.deepcopy(candles)
        for i, c in enumerate(out):
            if isinstance(c, dict) and "time" in c:
                c["time"] = base + i
        return out

    with _trace_capture() as records:
        traced = _decide_impl(
            [], _fresh(), account, risk_mgr,
            "LONDON", spread, 0.01, "XAUUSD")
    with patch.object(brain_mod, "_emit_decision_trace",
                       lambda *a, **k: None):
        silenced = _decide_impl(
            [], _fresh(), account, risk_mgr,
            "LONDON", spread, 0.01, "XAUUSD")
    return traced, silenced, records


def test_trace_does_not_change_pattern_gate_wait():
    traced, silenced, records = _run_case(
        _flat_candles(), _PermissiveRisk(), spread=15.0)
    assert traced.action == "WAIT"
    assert traced.signal_source == "PATTERN_GATE"
    assert _snapshot(traced) == _snapshot(silenced)
    assert len(records) == 1 and "gate=PATTERN_GATE" in records[0]


def test_trace_does_not_change_risk_gate_wait():
    traced, silenced, records = _run_case(
        _engulfing_candles(), _BlockingRisk(), spread=15.0)
    assert traced.action == "WAIT"
    assert traced.signal_source == "RISK_GATE"
    assert traced.direction == "BUY"  # Requirement 13: direction preserved
    assert _snapshot(traced) == _snapshot(silenced)
    assert len(records) == 1 and "gate=RISK_GATE" in records[0]


def test_trace_does_not_change_pattern_engine_trade():
    traced, silenced, records = _run_case(
        _engulfing_candles(), _PermissiveRisk(), spread=15.0)
    assert traced.action == "TRADE"
    assert traced.signal_source in ("PATTERN_ENGINE", "PATH_PATTERN")
    assert _snapshot(traced) == _snapshot(silenced)
    assert len(records) == 1 and "gate=PATTERN_ENGINE" in records[0]


def test_emit_never_raises_and_logs_reason_pattern_direction():
    class _Exploding:
        @property
        def action(self):
            raise RuntimeError("boom")

    _emit_decision_trace("XAUUSD", "TEST_GATE", _Exploding())  # must not raise

    fake = MagicMock()
    fake.action = "WAIT"
    fake.direction = "BUY"
    fake.pattern = "Bullish Engulfing"
    fake.reason = "RISK_BLOCKED | test"
    fake.confidence = 80
    with _trace_capture() as records:
        _emit_decision_trace("XAUUSD", "RISK_GATE", fake)
    assert len(records) == 1
    line = records[0]
    for token in ("gate=RISK_GATE", "action=WAIT", "direction=BUY",
                  "pattern=Bullish Engulfing", "reason=RISK_BLOCKED | test"):
        assert token in line, line
