"""
Aegis-Gold v4.0 — Feature Factory
Tick-based feature extraction: direction, velocity, momentum, spread, session.
Returns a FeatureSet every loop iteration.
"""

import time
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from config import settings as cfg

logger = logging.getLogger("aegis.features")


@dataclass
class FeatureSet:
    """Snapshot of all features for the current loop."""
    direction: str = "NONE"            # BUY / SELL / NONE
    velocity_spike: bool = False
    strong_momentum: bool = False
    spread_ok: bool = False
    current_spread: float = 0.0        # in points
    ticks_per_sec: float = 0.0
    momentum_score: float = 0.0
    signal_confirmed: bool = False     # all 3 true + spread ok
    session: str = "ASIAN"             # ASIAN / LONDON / NY / OVERLAP
    session_tp: int = 20
    session_sl: int = 15
    session_lot_mult: float = 0.5
    session_spread_max: int = 25
    # Module 3: quant features (populated by extract_quant(), empty dict when flag off)
    quant_features: dict = field(default_factory=dict)


class FeatureFactory:
    """Extracts tick-level features every loop cycle."""

    def __init__(self, point: float):
        self.point = point

        # Rolling buffers
        self._tps_history: deque[float] = deque(maxlen=cfg.VELOCITY_WINDOW_SEC)
        self._range_history: deque[float] = deque(maxlen=50)
        self._spread_history: deque[float] = deque(maxlen=cfg.SPREAD_ROLLING_WINDOW)

        # Tick timestamps for velocity calc
        self._tick_times: deque[float] = deque(maxlen=500)

    # ── public API ─────────────────────────────────────────────

    def extract(self, ticks, tick_obj=None) -> FeatureSet:
        """
        Build a complete FeatureSet from raw ticks.
        ticks  : numpy array from mt5.copy_ticks_from
        tick_obj : single mt5.symbol_info_tick result (for spread)
        """
        fs = FeatureSet()

        if ticks is None or len(ticks) < cfg.DIRECTION_WINDOW:
            return fs

        # Record tick arrival times for velocity - obsolete, handled by MT5 time_msc


        # Session detection (must be first — sets TP/SL/lot)
        self._detect_session(fs)

        # 1. Direction
        self._calc_direction(ticks, fs)

        # 2. Velocity spike
        self._calc_velocity(ticks, fs)

        # 3. Momentum strength
        self._calc_momentum(ticks, fs)

        # 4. Spread check
        self._calc_spread(tick_obj, fs)

        # 5. Signal confirmation
        fs.signal_confirmed = (
            fs.direction != "NONE"
            and fs.velocity_spike
            and fs.strong_momentum
            and fs.spread_ok
        )

        return fs

    # ── session detection ──────────────────────────────────────

    def _detect_session(self, fs: FeatureSet):
        hour = datetime.now(timezone.utc).hour

        # Check overlap first (London + NY crossover)
        if cfg.NY_START <= hour < cfg.LONDON_END:
            fs.session = "OVERLAP"
            fs.session_tp = 20
            fs.session_sl = 15
            fs.session_lot_mult = 1.0
            fs.session_spread_max = 30
        elif cfg.LONDON_START <= hour < cfg.LONDON_END:
            fs.session = "LONDON"
            fs.session_tp = 20
            fs.session_sl = 15
            fs.session_lot_mult = 1.0
            fs.session_spread_max = 30
        elif cfg.NY_START <= hour < cfg.NY_END:
            fs.session = "NY"
            fs.session_tp = 20
            fs.session_sl = 15
            fs.session_lot_mult = 1.0
            fs.session_spread_max = 30
        else:
            fs.session = "ASIAN"
            fs.session_tp = 20
            fs.session_sl = 15
            fs.session_lot_mult = 0.5
            fs.session_spread_max = 30

    # ── 1. direction (5-tick window) ───────────────────────────

    def _calc_direction(self, ticks, fs: FeatureSet):
        prices = [t["bid"] for t in ticks[-cfg.DIRECTION_WINDOW:]]
        if len(prices) < cfg.DIRECTION_WINDOW:
            return

        ups = sum(
            1 for i in range(1, len(prices)) if prices[i] > prices[i - 1]
        )
        downs = sum(
            1 for i in range(1, len(prices)) if prices[i] < prices[i - 1]
        )

        if ups >= cfg.DIRECTION_MIN_AGREE:
            fs.direction = "BUY"
        elif downs >= cfg.DIRECTION_MIN_AGREE:
            fs.direction = "SELL"
        else:
            fs.direction = "NONE"

    # ── 2. velocity spike ─────────────────────────────────────

    def _calc_velocity(self, ticks, fs: FeatureSet):
        if len(ticks) == 0:
            fs.ticks_per_sec = 0
            fs.velocity_spike = False
            return
            
        # Count ticks in the last 1000ms natively using MT5 timestamps
        last_msc = ticks[-1]["time_msc"]
        tps_now = sum(1 for t in ticks if last_msc - t["time_msc"] <= 1000)
        self._tps_history.append(tps_now)

        fs.ticks_per_sec = tps_now

        if len(self._tps_history) < 3:
            # Not enough history — allow trading
            fs.velocity_spike = True
            return

        tps_avg = sum(self._tps_history) / len(self._tps_history)

        if tps_avg > 0:
            fs.velocity_spike = tps_now >= tps_avg * cfg.VELOCITY_SPIKE_MULT
        else:
            fs.velocity_spike = True  # no data = allow

    # ── 3. momentum strength ──────────────────────────────────

    def _calc_momentum(self, ticks, fs: FeatureSet):
        window = cfg.MOMENTUM_WINDOW
        if len(ticks) < window:
            return

        prices = [t["bid"] for t in ticks[-window:]]
        range_now = max(prices) - min(prices)
        self._range_history.append(range_now)

        if len(self._range_history) < 5:
            fs.strong_momentum = range_now > 0
            fs.momentum_score = range_now / self.point if self.point else 0
            return

        range_avg = sum(self._range_history) / len(self._range_history)

        if range_avg > 0:
            fs.strong_momentum = range_now > range_avg * cfg.MOMENTUM_MULT
            fs.momentum_score = range_now / range_avg
        else:
            fs.strong_momentum = range_now > 0
            fs.momentum_score = 0.0

    # ── 4. spread check ───────────────────────────────────────

    def _calc_spread(self, tick_obj, fs: FeatureSet):
        if tick_obj is None:
            fs.spread_ok = False
            return

        try:
            spread = (tick_obj.ask - tick_obj.bid) / self.point if self.point else 0
        except Exception:
            fs.spread_ok = False
            return

        fs.current_spread = spread
        self._spread_history.append(spread)

        # Dynamic spread cap
        if len(self._spread_history) >= 3:
            roll_avg = sum(self._spread_history) / len(self._spread_history)
            dynamic_limit = roll_avg * cfg.SPREAD_DYNAMIC_MULT
        else:
            dynamic_limit = float("inf")

        hard_limit = fs.session_spread_max

        fs.spread_ok = spread < min(dynamic_limit, hard_limit)

    # ── MODULE 3: Quant Feature Extraction (flag-gated) ──────────────────────

    # Singleton QuantFeatureEngine — only instantiated if flag is on
    _quant_engine = None

    def extract_quant(self, prices_array) -> dict:
        """
        Extract FFT, Hurst, wavelet, entropy features from a price array.
        Returns an empty dict immediately when QX.flag('quant_features') is False
        — zero cost, zero impact on the legacy path.

        Parameters
        ----------
        prices_array : array-like of floats (close prices, oldest-first)

        Returns
        -------
        dict with keys: hurst, dominant_cycle, entropy_shannon, fft_energy,
                        wavelet_trend, butterworth_denoised_last
        """
        try:
            from config.quant_x_config import QX
            if not QX.flag("quant_features"):
                return {}
        except Exception:
            return {}

        try:
            import numpy as np
            if FeatureFactory._quant_engine is None:
                from brain.quant_feature_engine import QuantFeatureEngine
                FeatureFactory._quant_engine = QuantFeatureEngine()

            arr = np.asarray(prices_array, dtype=float)
            if len(arr) < 20:
                return {}

            result = FeatureFactory._quant_engine.analyze(arr)

            # Flatten to the subset the brain layer actually reads
            return {
                "hurst":                   result.get("hurst_exponent", 0.5),
                "dominant_cycle":          result.get("dominant_cycle", 0.0),
                "entropy_shannon":         result.get("entropy_shannon", 1.0),
                "fft_energy":              result.get("fft_spectral_energy", 0.0),
                "wavelet_trend":           result.get("wavelet_trend", 0.0),
                "butterworth_denoised_last": result.get("butterworth_denoised_last", 0.0),
            }
        except Exception as exc:
            logger.debug("[QUANT] extract_quant error: %s", exc)
            return {}
