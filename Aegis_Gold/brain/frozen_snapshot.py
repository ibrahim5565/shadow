"""
===========================================================================
AEGIS GOLD — Frozen Decision Snapshot
===========================================================================

FrozenDecisionSnapshot is the ONLY data container passed to engine.predict_vote().
It contains EXCLUSIVELY data with timestamp <= T (the decision time).

BUILDER CONTRACT:
  - The live (forming) candle is EXCLUDED from all candle arrays.
  - All arrays are converted to immutable tuples before wrapping.
  - The builder in core/main.py must call build_snapshot() with MT5 data
    where the last bar in each series is the most recently CLOSED bar.

TEMPORAL INTEGRITY:
  - Any engine that reads data outside this snapshot is in violation.
  - The AISupervisor (OMEGA) previously called mt5.copy_rates_from_pos()
    inside its vote path — that call is now forbidden. OMEGA must use
    snapshot.candles_m5 and snapshot.candles_m1 only.
===========================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class FrozenDecisionSnapshot:
    """
    Immutable snapshot of all market data available at decision time T.

    All candle arrays contain only CLOSED bars (bar.time < T).
    The forming (live) candle is explicitly excluded by the builder.

    Parameters
    ----------
    timestamp:          Decision time T. All bar timestamps must be < T.
    symbol:             Trading symbol (e.g. "XAUUSD", "EURUSD")
    candles_m5:         Tuple of closed M5 bars (oldest → newest)
    candles_m1:         Tuple of closed M1 bars (oldest → newest)
    candles_h1:         Optional H1 bars for higher-timeframe confirmation
    spread:             Current bid-ask spread in points
    point:              Symbol point size (e.g. 0.01 for XAUUSD)
    session:            Active session ("LONDON", "NEW_YORK", "ASIA", "OFF")
    account_equity:     Current account equity (for position sizing)
    current_price:      Last closed bar's close price (= candles_m5[-1].close equivalent)
    extra:              Engine-specific extras (news flags, macro context, etc.)
    """
    timestamp: datetime
    symbol: str
    candles_m5: tuple        # Immutable — all closed M5 bars
    candles_m1: tuple        # Immutable — all closed M1 bars
    candles_h1: tuple = ()   # Optional H1 bars
    spread: float = 0.0
    point: float = 0.01
    session: str = "LONDON"
    account_equity: float = 1000.0
    current_price: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def verify_integrity(self) -> list[str]:
        """
        Checks all candle bars in the snapshot have timestamps <= self.timestamp.
        Returns a list of violation strings (empty = clean).

        Works with both dict-style bars (MT5 numpy structured arrays or list of dicts)
        and attribute-style bar objects.
        """
        violations = []

        def check_bar(bar, tf_label: str, idx: int):
            """Extract bar timestamp and check it's before decision time."""
            bar_time = None
            if isinstance(bar, dict):
                bar_time = bar.get("time") or bar.get("timestamp")
            elif hasattr(bar, "time"):
                bar_time = bar.time
            elif hasattr(bar, "__getitem__"):
                try:
                    bar_time = bar[0]  # MT5 numpy recarray: index 0 is time
                except Exception:
                    pass

            if bar_time is None:
                return  # Cannot check — skip

            # Normalise to datetime
            if isinstance(bar_time, (int, float)):
                bar_dt = datetime.fromtimestamp(bar_time, tz=timezone.utc)
            elif isinstance(bar_time, datetime):
                bar_dt = bar_time if bar_time.tzinfo else bar_time.replace(tzinfo=timezone.utc)
            else:
                return

            snap_dt = self.timestamp if self.timestamp.tzinfo else self.timestamp.replace(tzinfo=timezone.utc)

            if bar_dt >= snap_dt:
                violations.append(
                    f"[LEAKAGE] {tf_label}[{idx}] bar_time={bar_dt.isoformat()} "
                    f">= snapshot.timestamp={snap_dt.isoformat()}"
                )

        for i, bar in enumerate(self.candles_m5):
            check_bar(bar, "M5", i)
        for i, bar in enumerate(self.candles_m1):
            check_bar(bar, "M1", i)
        for i, bar in enumerate(self.candles_h1):
            check_bar(bar, "H1", i)

        return violations

    @property
    def n_m5(self) -> int:
        return len(self.candles_m5)

    @property
    def n_m1(self) -> int:
        return len(self.candles_m1)

    @property
    def n_h1(self) -> int:
        return len(self.candles_h1)


# ---------------------------------------------------------------------------
# Builder — called by core/main.py to create a snapshot at each scan tick
# ---------------------------------------------------------------------------

def build_snapshot(
    symbol: str,
    candles_m5: Any,
    candles_m1: Any,
    candles_h1: Any = None,
    spread: float = 0.0,
    point: float = 0.01,
    session: str = "LONDON",
    account_equity: float = 1000.0,
    decision_time: Optional[datetime] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> FrozenDecisionSnapshot:
    """
    Build a FrozenDecisionSnapshot, ensuring the live (forming) candle is excluded.

    This builder removes the LAST bar of each series if its timestamp equals
    or exceeds the decision_time (i.e., it's still forming).

    Parameters
    ----------
    candles_m5/m1/h1:  Raw MT5 candle arrays (list of dicts, numpy recarray, or list of tuples)
    decision_time:     Defaults to utcnow() if not provided.
    """
    now = decision_time or datetime.now(timezone.utc)

    def to_closed_tuple(raw) -> tuple:
        """Convert raw candle array to immutable tuple, stripping any forming candle."""
        if raw is None:
            return ()
        # Convert to list for processing
        if hasattr(raw, "tolist"):
            bars = raw.tolist()
        elif hasattr(raw, "__iter__"):
            bars = list(raw)
        else:
            return ()

        if not bars:
            return ()

        # Determine last bar's time
        last = bars[-1]
        last_time = None
        if isinstance(last, dict):
            last_time = last.get("time") or last.get("timestamp")
        elif hasattr(last, "time"):
            last_time = last.time
        elif isinstance(last, (list, tuple)) and len(last) > 0:
            last_time = last[0]

        if last_time is not None:
            if isinstance(last_time, (int, float)):
                last_dt = datetime.fromtimestamp(last_time, tz=timezone.utc)
            elif isinstance(last_time, datetime):
                last_dt = last_time if last_time.tzinfo else last_time.replace(tzinfo=timezone.utc)
            else:
                last_dt = None

            now_tz = now if now.tzinfo else now.replace(tzinfo=timezone.utc)

            # Strip the forming candle: if last bar's open_time >= decision_time,
            # it hasn't closed yet
            if last_dt is not None and last_dt >= now_tz:
                bars = bars[:-1]

        return tuple(bars)

    m5_closed = to_closed_tuple(candles_m5)
    m1_closed = to_closed_tuple(candles_m1)
    h1_closed = to_closed_tuple(candles_h1)

    # Derive current_price from last closed M5 bar
    current_price = 0.0
    if m5_closed:
        last_m5 = m5_closed[-1]
        if isinstance(last_m5, dict):
            current_price = float(last_m5.get("close", last_m5.get("c", 0.0)))
        elif hasattr(last_m5, "close"):
            current_price = float(last_m5.close)
        elif isinstance(last_m5, (list, tuple)) and len(last_m5) >= 5:
            current_price = float(last_m5[4])  # MT5 format: [time, open, high, low, close, ...]

    return FrozenDecisionSnapshot(
        timestamp=now,
        symbol=symbol,
        candles_m5=m5_closed,
        candles_m1=m1_closed,
        candles_h1=h1_closed,
        spread=spread,
        point=point,
        session=session,
        account_equity=account_equity,
        current_price=current_price,
        extra=extra or {},
    )
