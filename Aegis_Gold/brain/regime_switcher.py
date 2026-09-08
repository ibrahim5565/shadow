"""
===========================================================================
AEGIS GOLD v8.0 -- Regime-Aware Strategy Switcher
===========================================================================

PURPOSE:
--------
The market is never in a single static state. AEGIS must dynamically
shift its strategy profile based on the current market regime:

  STRONG_TREND  → Use trend-following entries, wider TP, tighter SL
  WEAK_TREND    → Use momentum pattern trading, moderate TP/SL
  RANGE         → Use mean-reversion setups, SMC OBs, tighter TP
  VOLATILE      → Reduce lot size, widen SL, raise pattern quality threshold
  TRANSITION    → Wait for clarity, avoid new entries

HOW IT WORKS:
-------------
1. Every scan cycle, the regime detector (brain/regime.py + statistical_engine)
   produces a RegimeState.
2. This switcher translates that into a StrategyProfile — a named dict of
   overrides that the brain.py decision engine respects.
3. Profile changes are logged and sent via Telegram.
4. Historical regime performance (win rate per regime) feeds back via
   performance_attribution.py to refine regime detection thresholds.

STRATEGY PROFILES:
------------------
SMALL_PATTERN_AGGRESSIVE    (STRONG_TREND + London/NY session)
SMALL_PATTERN_STANDARD      (WEAK_TREND)
RANGE_REVERSAL      (RANGE)
DEFENSIVE           (VOLATILE / TRANSITION)
SMC_PREMIUM         (HTF order block + BOS confirmed)
===========================================================================
"""

import json
import logging
import numpy as np
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger("aegis.regime_switcher")

BASE_DIR = Path(__file__).parent.parent
STATE_PATH = BASE_DIR / "data" / "regime_strategy_state.json"


# ---------------------------------------------------------------------------
# Strategy Profile dataclass
# ---------------------------------------------------------------------------

@dataclass
class StrategyProfile:
    name: str
    description: str

    # Entry threshold overrides (additive offsets applied to base thresholds)
    min_confidence_override: int    # e.g. 50 = require at least 50%
    confidence_bonus: int           # extra pts added to computed confidence

    # Position sizing
    lot_multiplier: float           # 1.0 = normal, 0.5 = half, 1.2 = scaled up

    # Exit strategy
    tp_multiplier: float            # 1.0 = config TP, 1.5 = 50% wider
    sl_multiplier: float            # 1.0 = config SL, 0.8 = 20% tighter

    # Signal preference
    prefer_smc: bool                # True = SMC signals weighted higher
    prefer_small_patterns: bool     # True = small-pattern signals weighted higher
    prefer_reversal: bool           # True = Counter-trend setups preferred

    # Additional guard
    skip_if_news: bool              # Always skip near news
    max_spread_multiplier: float    # Max spread as multiple of config spread limit

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------

PROFILES: Dict[str, StrategyProfile] = {
    "SCALP_AGGRESSIVE": StrategyProfile(
        name="SCALP_AGGRESSIVE",
        description="Strong trend active session — follow the trend, wide TP",
        min_confidence_override=50,
        confidence_bonus=5,
        lot_multiplier=1.0,
        tp_multiplier=1.5,
        sl_multiplier=1.0,
        prefer_smc=False,
        prefer_small_patterns=True,
        prefer_reversal=False,
        skip_if_news=True,
        max_spread_multiplier=1.0,
    ),
    "SCALP_STANDARD": StrategyProfile(
        name="SCALP_STANDARD",
        description="Moderate trend — standard small-pattern parameters",
        min_confidence_override=50,
        confidence_bonus=0,
        lot_multiplier=1.0,
        tp_multiplier=1.0,
        sl_multiplier=1.0,
        prefer_smc=False,
        prefer_small_patterns=True,
        prefer_reversal=False,
        skip_if_news=True,
        max_spread_multiplier=1.0,
    ),
    "SMALL_PATTERN_AGGRESSIVE": StrategyProfile(
        name="SMALL_PATTERN_AGGRESSIVE",
        description="Strong trend active session — follow the trend, wide TP",
        min_confidence_override=50,
        confidence_bonus=5,
        lot_multiplier=1.0,
        tp_multiplier=1.5,
        sl_multiplier=1.0,
        prefer_smc=False,
        prefer_small_patterns=True,
        prefer_reversal=False,
        skip_if_news=True,
        max_spread_multiplier=1.0,
    ),
    "SMALL_PATTERN_STANDARD": StrategyProfile(
        name="SMALL_PATTERN_STANDARD",
        description="Moderate trend — standard small-pattern parameters",
        min_confidence_override=50,
        confidence_bonus=0,
        lot_multiplier=1.0,
        tp_multiplier=1.0,
        sl_multiplier=1.0,
        prefer_smc=False,
        prefer_small_patterns=True,
        prefer_reversal=False,
        skip_if_news=True,
        max_spread_multiplier=1.0,
    ),
    "SMC_PREMIUM": StrategyProfile(
        name="SMC_PREMIUM",
        description="Strong SMC setup confirmed — elevated position sizing",
        min_confidence_override=60,
        confidence_bonus=8,
        lot_multiplier=1.0,
        tp_multiplier=2.0,
        sl_multiplier=1.0,
        prefer_smc=True,
        prefer_small_patterns=False,
        prefer_reversal=False,
        skip_if_news=True,
        max_spread_multiplier=1.2,
    ),
    "RANGE_REVERSAL": StrategyProfile(
        name="RANGE_REVERSAL",
        description="Range-bound market — mean reversion from OB/liquidity zones",
        min_confidence_override=55,
        confidence_bonus=0,
        lot_multiplier=0.8,
        tp_multiplier=0.8,
        sl_multiplier=0.9,
        prefer_smc=True,
        prefer_small_patterns=False,
        prefer_reversal=True,
        skip_if_news=True,
        max_spread_multiplier=0.9,
    ),
    "DEFENSIVE": StrategyProfile(
        name="DEFENSIVE",
        description="Volatile/transitional regime — reduced risk, high selectivity",
        min_confidence_override=65,
        confidence_bonus=-5,
        lot_multiplier=0.5,
        tp_multiplier=0.8,
        sl_multiplier=1.2,
        prefer_smc=False,
        prefer_small_patterns=False,
        prefer_reversal=False,
        skip_if_news=True,
        max_spread_multiplier=0.8,
    ),
}


# ---------------------------------------------------------------------------
# Regime → Profile mapping
# ---------------------------------------------------------------------------

def _select_profile(
    regime_type: str,
    adx: float,
    session: str,
    recent_win_rate: float = 0.5
) -> str:
    """
    Map current market conditions to a strategy profile name.

    regime_type: one of STRONG_TREND, WEAK_TREND, RANGE, VOLATILE, TRANSITION, RANGING, TRENDING
    adx:         ADX value (higher = stronger trend)
    session:     ASIAN | LONDON | NY | OVERLAP
    recent_win_rate: last 20-trade win rate (from attribution stats)
    """
    regime_upper = regime_type.upper()

    # Defensive mode if losing streak
    if recent_win_rate < 0.40:
        return "DEFENSIVE"

    if "VOLATILE" in regime_upper or "TRANSITION" in regime_upper:
        return "DEFENSIVE"

    if "STRONG" in regime_upper or (adx > 25 and "TREND" in regime_upper):
        if session in ("LONDON", "NY", "OVERLAP"):
            return "SCALP_AGGRESSIVE"
        return "SCALP_STANDARD"

    if "RANGE" in regime_upper or "RANGING" in regime_upper:
        return "RANGE_REVERSAL"

    if "WEAK" in regime_upper or "TREND" in regime_upper:
        return "SCALP_STANDARD"

    return "SCALP_STANDARD"


# ---------------------------------------------------------------------------
# StrategyState — persistent current active profile
# ---------------------------------------------------------------------------

class StrategyState:
    """
    Maintains the current active strategy profile and handles transitions.
    Persisted to JSON for cross-process visibility.
    """

    def __init__(self):
        self._current_name: str = "SCALP_STANDARD"
        self._last_changed: Optional[str] = None
        self._switch_count: int = 0
        self._load()

    def _load(self):
        try:
            if STATE_PATH.exists():
                data = json.loads(STATE_PATH.read_text())
                self._current_name = data.get("profile", "SCALP_STANDARD")
                self._last_changed = data.get("last_changed")
                self._switch_count = data.get("switch_count", 0)
        except Exception as e:
            logger.warning(f"[SWITCHER] Could not load state: {e}")

    def _save(self):
        try:
            STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            STATE_PATH.write_text(json.dumps({
                "profile": self._current_name,
                "last_changed": self._last_changed,
                "switch_count": self._switch_count,
            }, indent=2))
        except Exception as e:
            logger.warning(f"[SWITCHER] Could not save state: {e}")

    @property
    def current_profile(self) -> StrategyProfile:
        return PROFILES.get(self._current_name, PROFILES["SCALP_STANDARD"])

    @property
    def current_name(self) -> str:
        return self._current_name

    def evaluate_and_switch(
        self,
        regime_type: str,
        adx: float,
        session: str,
        recent_win_rate: float = 0.5
    ) -> Optional[str]:
        """
        Re-evaluate the active profile given current market conditions.
        Returns the new profile name if a switch occurred, else None.

        VALIDATION: If regime or required features are invalid, the current
        strategy is KEPT and the reason is logged.
        """
        # ── REGIME VALIDATION ─────────────────────────────────────────
        # Do not switch strategies based on invalid placeholder data.
        invalid_reason = None

        # Check regime_type is valid
        if not regime_type or str(regime_type).strip().upper() in ("NA", "NONE", "UNKNOWN", ""):
            invalid_reason = f"INVALID_REGIME_FEATURES | regime={regime_type}"

        # Check ADX is valid (not 0.0 placeholder, not NaN, not inf)
        try:
            adx_f = float(adx)
            if not np.isfinite(adx_f) or adx_f <= 0.0:
                invalid_reason = f"INVALID_REGIME_FEATURES | ADX={adx}"
        except (TypeError, ValueError):
            invalid_reason = f"INVALID_REGIME_FEATURES | ADX={adx}"

        # Check session is valid
        if not session or str(session).strip().upper() in ("NA", "NONE", "UNKNOWN", ""):
            invalid_reason = f"INVALID_REGIME_FEATURES | session={session}"

        if invalid_reason:
            logger.warning(
                "[SWITCHER] KEEP CURRENT STRATEGY | %s | current=%s",
                invalid_reason, self._current_name
            )
            return None

        new_name = _select_profile(regime_type, adx, session, recent_win_rate)

        if new_name != self._current_name:
            old = self._current_name
            self._current_name = new_name
            self._last_changed = datetime.now(timezone.utc).isoformat()
            self._switch_count += 1
            self._save()

            logger.info(
                f"[SWITCHER] Strategy switched: {old} -> {new_name} "
                f"(regime={regime_type}, ADX={adx:.1f}, session={session}, "
                f"win_rate={recent_win_rate:.1%})"
            )
            return new_name

        return None

    def get_status(self) -> dict:
        return {
            "current_profile": self._current_name,
            "profile_config": self.current_profile.to_dict(),
            "last_changed": self._last_changed,
            "total_switches": self._switch_count,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_strategy_state: Optional[StrategyState] = None


def get_strategy_state() -> StrategyState:
    global _strategy_state
    if _strategy_state is None:
        _strategy_state = StrategyState()
    return _strategy_state


def get_active_profile() -> StrategyProfile:
    return get_strategy_state().current_profile


class RegimeSwitcher:
    """
    Class wrapper for regime evaluation and strategy profile switching.
    """
    def __init__(self):
        self.state = get_strategy_state()

    def update_regime(self, df_or_regime: Any, adx: float = 25.0, session: str = "LONDON", win_rate: float = 0.5) -> StrategyProfile:
        regime_type = "RANGE"
        if isinstance(df_or_regime, str):
            regime_type = df_or_regime
        elif hasattr(df_or_regime, "close"):
            # Compute basic ADX / trend proxy from df
            prices = df_or_regime["close"].values
            if len(prices) > 20:
                diff = np.diff(prices[-20:])
                if np.sum(diff > 0) > 13:
                    regime_type = "STRONG_TREND"
                elif np.sum(diff < 0) > 13:
                    regime_type = "STRONG_TREND"

        self.state.evaluate_and_switch(regime_type, adx, session, win_rate)
        return self.state.current_profile

    def detect_regime(self, df_or_regime: Any) -> str:
        prof = self.update_regime(df_or_regime)
        return prof.name

