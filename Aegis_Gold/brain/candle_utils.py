"""
brain/candle_utils.py
=====================
Shared candle-parsing utilities for the Aegis Gold brain.

All brain modules that receive a candles argument should import
`parse_candles_df` from here instead of rolling their own iteration logic.

Supported input formats
-----------------------
  1. Pandas DataFrame  (copy_rates -> pd.DataFrame)
  2. NumPy structured array (copy_rates raw return)
  3. list / tuple of dicts    e.g. [{'open':..., 'close':...}, ...]
  4. list / tuple of tuples   e.g. [(time, open, high, low, close, ...), ...]
  5. object with .open/.high/.low/.close attributes (namedtuple-like)

Returns
-------
  (opens, highs, lows, closes) -- all plain Python float lists
"""

import logging
from typing import List, Tuple

logger = logging.getLogger("aegis.candle_utils")


def parse_candles_df(candles) -> Tuple[List[float], List[float], List[float], List[float]]:
    """
    Universal candle parser. Returns (opens, highs, lows, closes).
    All values are plain Python float lists.
    """
    try:
        # 1. Pandas DataFrame
        if hasattr(candles, "iloc") and hasattr(candles, "columns"):
            cols = list(candles.columns)
            opens  = candles["open"].values.astype(float).tolist()  if "open"  in cols else [0.0] * len(candles)
            highs  = candles["high"].values.astype(float).tolist()  if "high"  in cols else [0.0] * len(candles)
            lows   = candles["low"].values.astype(float).tolist()   if "low"   in cols else [0.0] * len(candles)
            closes = candles["close"].values.astype(float).tolist() if "close" in cols else [0.0] * len(candles)
            return opens, highs, lows, closes

        # 2. NumPy structured array
        if hasattr(candles, "dtype") and hasattr(candles.dtype, "names") and candles.dtype.names:
            names = candles.dtype.names
            opens  = candles["open"].astype(float).tolist()  if "open"  in names else [0.0] * len(candles)
            highs  = candles["high"].astype(float).tolist()  if "high"  in names else [0.0] * len(candles)
            lows   = candles["low"].astype(float).tolist()   if "low"   in names else [0.0] * len(candles)
            closes = candles["close"].astype(float).tolist() if "close" in names else [0.0] * len(candles)
            return opens, highs, lows, closes

        # 3. Sequence types
        if not candles:
            return [], [], [], []

        first = candles[0]

        # 3a. list of dicts
        if isinstance(first, dict):
            opens  = [float(c.get("open",  c.get("o",  0.0))) for c in candles]
            highs  = [float(c.get("high",  c.get("h",  0.0))) for c in candles]
            lows   = [float(c.get("low",   c.get("l",  0.0))) for c in candles]
            closes = [float(c.get("close", c.get("c",  0.0))) for c in candles]
            return opens, highs, lows, closes

        # 3b. list of lists/tuples -- [time, open, high, low, close, ...]
        if isinstance(first, (list, tuple)):
            opens  = [float(c[1]) for c in candles]
            highs  = [float(c[2]) for c in candles]
            lows   = [float(c[3]) for c in candles]
            closes = [float(c[4]) for c in candles]
            return opens, highs, lows, closes

        # 3c. attribute objects (namedtuple, MT5 object)
        opens  = [float(getattr(c, "open",  0.0)) for c in candles]
        highs  = [float(getattr(c, "high",  0.0)) for c in candles]
        lows   = [float(getattr(c, "low",   0.0)) for c in candles]
        closes = [float(getattr(c, "close", 0.0)) for c in candles]
        return opens, highs, lows, closes

    except Exception as e:
        logger.warning(f"[candle_utils] parse_candles_df failed: {e} -- returning empty arrays")
        return [], [], [], []


def parse_closes(candles) -> List[float]:
    """Convenience: only extracts closes."""
    _, _, _, closes = parse_candles_df(candles)
    return closes


def parse_hlc(candles) -> Tuple[List[float], List[float], List[float]]:
    """Convenience: extracts (highs, lows, closes)."""
    _, highs, lows, closes = parse_candles_df(candles)
    return highs, lows, closes


def parse_ohlc(candles) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Convenience: extracts (opens, highs, lows, closes)."""
    return parse_candles_df(candles)
