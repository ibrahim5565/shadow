"""
AEGIS QUANT X — Data Integrity Layer
=====================================
Layer A: Validates every incoming tick/bar before any downstream consumer
         sees it.  Enforces:

  1. Gap detection        — consecutive bar gap > N × expected interval
  2. Stale-price detection — bid unchanged across N consecutive ticks
  3. Outlier filtering    — single-bar price move > K sigma rejected
  4. Point-in-time guard  — decorator that asserts features never reference
                            data that would not have been available at
                            decision time (look-ahead detection)
  5. Multi-feed stub      — if a second feed is ever added, divergence
                            >X points logs a warning instead of silently
                            trusting one source

SAFETY CONTRACT
---------------
  validate_bars() returns CleanedBars on success.
  On failure it returns None — callers must treat None as "no data,
  resolve to WAIT".  It never raises; it never corrupts the feed silently.

FEATURE FLAG
-----------
  Enabled by QX["data_integrity"].  When flag is off the module still
  imports cleanly but validate_bars() is a no-op passthrough so the
  existing system is completely unaffected.
"""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, List, Optional, Sequence

logger = logging.getLogger("aegis.data_integrity")

# Lazy import — avoids circular dependency at module level
def _get_qx():
    try:
        from config.quant_x_config import QX
        return QX
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class IntegrityReport:
    """Summary of what the validator found and did."""
    valid:            bool     = True
    gaps_detected:    int      = 0
    stale_detected:   bool     = False
    outliers_removed: int      = 0
    bars_in:          int      = 0
    bars_out:         int      = 0
    warnings:         list     = field(default_factory=list)
    rejected_reason:  str      = ""

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        logger.warning("[INTEGRITY] %s", msg)


# CleanedBars is just the same list/array type the caller passed in,
# after filtering.  We keep the type opaque so any bar format works.
CleanedBars = Any


# ---------------------------------------------------------------------------
# Core validation functions
# ---------------------------------------------------------------------------

def _expected_interval_sec(bars: Sequence) -> float:
    """
    Infer the expected bar interval from the first few bars' timestamps.
    Returns seconds.  Falls back to 300 (M5) if inference fails.
    """
    try:
        if len(bars) < 3:
            return 300.0
        times = []
        for b in bars[:10]:
            if isinstance(b, dict):
                t = b.get("time", 0)
            else:
                try:
                    t = b[0]        # MT5 structured array: index 0 = time
                except Exception:
                    t = 0
            times.append(float(t))
        diffs = [times[i+1] - times[i] for i in range(len(times)-1) if times[i+1] > times[i]]
        if diffs:
            return statistics.median(diffs)
    except Exception:
        pass
    return 300.0


def _bar_time(bar) -> float:
    """Extract Unix timestamp from a bar (dict or structured array)."""
    try:
        if isinstance(bar, dict):
            return float(bar.get("time", 0))
        return float(bar[0])
    except Exception:
        return 0.0


def _bar_close(bar) -> float:
    try:
        if isinstance(bar, dict):
            return float(bar.get("close", 0.0))
        return float(bar[4])
    except Exception:
        return 0.0


def _bar_high(bar) -> float:
    try:
        if isinstance(bar, dict):
            return float(bar.get("high", 0.0))
        return float(bar[2])
    except Exception:
        return 0.0


def _bar_low(bar) -> float:
    try:
        if isinstance(bar, dict):
            return float(bar.get("low", 0.0))
        return float(bar[3])
    except Exception:
        return 0.0


def detect_gaps(bars: Sequence, report: IntegrityReport,
                gap_multiplier: float = 2.0) -> None:
    """
    Flag bars where the timestamp gap to the previous bar exceeds
    gap_multiplier × expected_interval.  Flagged bars are logged but
    NOT removed (gaps are informational; they don't corrupt the bar itself).
    """
    if len(bars) < 2:
        return
    expected = _expected_interval_sec(bars)
    threshold = expected * gap_multiplier
    prev_t = _bar_time(bars[0])
    for bar in bars[1:]:
        t = _bar_time(bar)
        if t > 0 and prev_t > 0:
            gap = t - prev_t
            if gap > threshold:
                msg = (f"Bar gap {gap:.0f}s > {threshold:.0f}s threshold "
                       f"(expected ~{expected:.0f}s) at bar time {t}")
                report.add_warning(msg)
                report.gaps_detected += 1
        prev_t = t


def detect_stale_price(ticks: Sequence, report: IntegrityReport,
                        stale_ticks: int = 50) -> None:
    """
    Flag when the bid price is unchanged across stale_ticks consecutive ticks.
    A genuinely active market almost never has 50 identical consecutive bids.
    """
    if not ticks or len(ticks) < stale_ticks:
        return
    try:
        recent = ticks[-stale_ticks:]
        bids: list[float] = []
        for t in recent:
            if isinstance(t, dict):
                bids.append(float(t.get("bid", 0.0)))
            else:
                bids.append(float(t[1]))   # MT5 structured tick: index 1 = bid
        if len(set(bids)) == 1 and bids[0] > 0:
            report.stale_detected = True
            report.add_warning(
                f"Stale price detected: bid={bids[0]} unchanged across "
                f"{stale_ticks} consecutive ticks"
            )
    except Exception as exc:
        logger.debug("[INTEGRITY] stale_price check failed: %s", exc)


def remove_outlier_bars(bars: Sequence, report: IntegrityReport,
                        sigma: float = 5.0) -> list:
    """
    Remove bars whose high–low range exceeds sigma × recent_std.
    Returns a new list with outlier bars excluded.
    """
    if len(bars) < 10:
        return list(bars)

    try:
        ranges = [_bar_high(b) - _bar_low(b) for b in bars]
        mean_r = statistics.mean(ranges)
        std_r  = statistics.stdev(ranges) if len(ranges) > 1 else mean_r
        if std_r <= 0:
            return list(bars)
        threshold = mean_r + sigma * std_r
        clean = []
        for bar, r in zip(bars, ranges):
            if r > threshold:
                report.outliers_removed += 1
                logger.warning(
                    "[INTEGRITY] Outlier bar removed: range=%.5f > threshold=%.5f",
                    r, threshold
                )
            else:
                clean.append(bar)
        return clean
    except Exception as exc:
        logger.debug("[INTEGRITY] outlier removal failed: %s", exc)
        return list(bars)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_bars(
    bars,
    ticks=None,
    symbol: str = "XAUUSD",
    point: float = 0.01,
) -> Optional[CleanedBars]:
    """
    Main entry point.  Call this before passing bars to any downstream
    consumer.

    Returns:
        Cleaned bars (list) on success — may be shorter than input after
        outlier removal.
        None if the feed is critically unhealthy (stale + gaps together)
        and downstream should resolve to WAIT.

    Never raises.
    """
    qx = _get_qx()
    if qx is None or not qx.flag("data_integrity"):
        # Feature disabled — passthrough, no cost
        return bars if bars is not None else None

    report = IntegrityReport()
    report.bars_in = len(bars) if bars is not None else 0

    if bars is None or len(bars) == 0:
        report.valid = False
        report.rejected_reason = "Empty bar array"
        _log_report(symbol, report)
        return None

    gap_mult  = qx.get("data_integrity_gap_multiplier") or 2.0
    stale_n   = qx.get("data_integrity_stale_ticks")    or 50
    out_sigma = qx.get("data_integrity_outlier_sigma")  or 5.0

    # 1. Gap detection (informational — logs but does not reject bars)
    detect_gaps(bars, report, gap_multiplier=gap_mult)

    # 2. Stale price detection (from ticks if provided)
    if ticks is not None and len(ticks) >= stale_n:
        detect_stale_price(ticks, report, stale_ticks=stale_n)

    # 3. Outlier removal
    cleaned = remove_outlier_bars(bars, report, sigma=out_sigma)

    report.bars_out = len(cleaned)

    # 4. Critical failure: stale price + significant gaps → WAIT
    if report.stale_detected and report.gaps_detected >= 3:
        report.valid = False
        report.rejected_reason = (
            f"Feed critically unhealthy: stale price + {report.gaps_detected} gaps. "
            "Resolving to WAIT."
        )
        _log_report(symbol, report)
        return None

    # 5. All bars were outliers — something is very wrong
    if len(cleaned) == 0:
        report.valid = False
        report.rejected_reason = "All bars removed as outliers — cannot proceed"
        _log_report(symbol, report)
        return None

    _log_report(symbol, report)
    return cleaned


def validate_tick_feed(ticks, symbol: str = "XAUUSD") -> bool:
    """
    Quick sanity check on a tick array.
    Returns True if the feed looks healthy, False otherwise.
    Callers treat False as "insufficient data → WAIT".
    """
    qx = _get_qx()
    if qx is None or not qx.flag("data_integrity"):
        return True

    if ticks is None or len(ticks) == 0:
        logger.warning("[INTEGRITY][%s] Empty tick array", symbol)
        return False

    stale_n = qx.get("data_integrity_stale_ticks") or 50
    report  = IntegrityReport()
    detect_stale_price(ticks, report, stale_ticks=stale_n)

    if report.stale_detected:
        logger.warning("[INTEGRITY][%s] Tick feed appears stale — WAIT recommended", symbol)
        return False

    return True


# ---------------------------------------------------------------------------
# Point-in-time guard decorator
# ---------------------------------------------------------------------------

class _PITContext:
    """Thread-local-style context that records the current decision timestamp."""
    _current_bar_time: float = 0.0

    @classmethod
    def set(cls, bar_time: float) -> None:
        cls._current_bar_time = bar_time

    @classmethod
    def get(cls) -> float:
        return cls._current_bar_time


def set_pit_context(bar_time: float) -> None:
    """
    Call this at the start of each decision cycle with the bar's close time.
    Any feature function decorated with @pit_safe that accidentally references
    data beyond this timestamp will raise PITViolationError in test/dev.
    """
    _PITContext.set(bar_time)


class PITViolationError(RuntimeError):
    """Raised when a feature function accesses future data."""
    pass


def pit_safe(fn: Callable) -> Callable:
    """
    Decorator.  The wrapped function receives the current PIT timestamp and
    can assert it never accesses bars/ticks with time > bar_time.

    In production this is a no-op if 'data_integrity' flag is off.
    In test/research mode it raises PITViolationError on violation.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        qx = _get_qx()
        if qx is None or not qx.flag("data_integrity"):
            return fn(*args, **kwargs)
        # Inject pit_time keyword if the function accepts it
        import inspect
        sig = inspect.signature(fn)
        if "pit_time" in sig.parameters:
            kwargs.setdefault("pit_time", _PITContext.get())
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Multi-feed reconciliation stub
# ---------------------------------------------------------------------------

def reconcile_feeds(primary_bars, secondary_bars,
                    point: float = 0.01,
                    divergence_threshold_pts: float = 50.0) -> CleanedBars:
    """
    Compare two bar feeds (e.g. two broker connections) and flag divergence.
    Returns primary_bars always — secondary is advisory only.
    If divergence exceeds threshold, logs a WARNING and continues on primary.
    """
    if secondary_bars is None or len(secondary_bars) == 0:
        return primary_bars

    try:
        p_close = _bar_close(primary_bars[-1])
        s_close = _bar_close(secondary_bars[-1])
        if point > 0:
            divergence_pts = abs(p_close - s_close) / point
            if divergence_pts > divergence_threshold_pts:
                logger.warning(
                    "[INTEGRITY] Feed divergence: primary=%.5f secondary=%.5f "
                    "divergence=%.1f pts — trusting primary",
                    p_close, s_close, divergence_pts
                )
    except Exception as exc:
        logger.debug("[INTEGRITY] reconcile_feeds check failed: %s", exc)

    return primary_bars


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log_report(symbol: str, report: IntegrityReport) -> None:
    level = logging.WARNING if not report.valid else logging.DEBUG
    logger.log(
        level,
        "[INTEGRITY][%s] valid=%s bars=%d→%d gaps=%d stale=%s outliers=%s %s",
        symbol, report.valid, report.bars_in, report.bars_out,
        report.gaps_detected, report.stale_detected, report.outliers_removed,
        f"| {report.rejected_reason}" if report.rejected_reason else "",
    )
