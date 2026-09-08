"""
===========================================================================
🎯 AEGIS GOLD — Sniper Filter v1.0 (Phase 4)
===========================================================================

PURPOSE:
  High-Precision Triple-Lock gate for Pattern-Only trading.
  Replaces probabilistic weighted-average consensus with deterministic
  structural confirmation before any TRADE decision is emitted.

TRIPLE-LOCK CONFIRMATION:
  1. SMC Structural Lock  — Price inside unmitigated OB + valid FVG gap
  2. ML Ensemble Lock     — Directional win probability ≥ 0.85
  3. HTF Alignment Lock   — H1/H4 trend aligns with M5 entry direction
  4. ATR Volatility Guard — ATR ratio ≤ 2.5 (news spike filter)
  5. Liquidity Sweep (PO3) — Required for Big Pattern mode (optional per config)

AUTO-TIGHTEN:
  If WR over last 50 sniper trades < 95%, ml_conf threshold is
  automatically tightened by SNIPER_AUTO_TIGHTEN_STEP (default: 2%)
  each evaluation cycle until WR target is met.

DESIGN PRINCIPLE:
  Signal QUALITY > Signal QUANTITY.
  1-5 high-conviction setups/day >> 100+ noisy scalps/day.
===========================================================================
"""

import logging
import os
import json
from typing import Dict, Any, Optional, List, Tuple

logger = logging.getLogger("aegis.sniper")

# ─────────────────────────────────────────────────────────────
# Defaults (overridden by config/settings.py when available)
# ─────────────────────────────────────────────────────────────
_DEFAULT_ML_CONF_MIN      = 0.85
_DEFAULT_SMC_CONF_MIN     = 0.80
_DEFAULT_HTF_CONF_MIN     = 0.80
_DEFAULT_ATR_RATIO_MAX    = 2.5
_DEFAULT_REQUIRE_SWEEP    = True
_DEFAULT_AUTO_TIGHTEN     = True
_DEFAULT_TIGHTEN_STEP     = 0.02
_DEFAULT_TIGHTEN_WR_FLOOR = 0.95
_DEFAULT_TIGHTEN_WINDOW   = 50


class SniperFilter:
    """
    Triple-Lock Sniper Confirmation Gate.

    Usage:
        sf = SniperFilter()
        ok, reason = sf.is_sniper_setup(setup_dict, engine_votes)
        if ok:
            # emit TRADE
    """

    def __init__(
        self,
        target_win_rate: float = 0.97,
        persistence_file: Optional[str] = None,
    ):
        self.target_win_rate = target_win_rate

        # Load thresholds from settings (with fallback to defaults)
        try:
            from config import settings as cfg
            self.ml_conf_min      = float(getattr(cfg, "SNIPER_ML_CONF_MIN",      _DEFAULT_ML_CONF_MIN))
            self.smc_conf_min     = float(getattr(cfg, "SNIPER_SMC_CONF_MIN",     _DEFAULT_SMC_CONF_MIN))
            self.htf_conf_min     = float(getattr(cfg, "SNIPER_HTF_CONF_MIN",     _DEFAULT_HTF_CONF_MIN))
            self.atr_ratio_max    = float(getattr(cfg, "SNIPER_ATR_RATIO_MAX",    _DEFAULT_ATR_RATIO_MAX))
            self.require_sweep    = bool(getattr(cfg,  "SNIPER_REQUIRE_LIQ_SWEEP", _DEFAULT_REQUIRE_SWEEP))
            self.auto_tighten     = bool(getattr(cfg,  "SNIPER_AUTO_TIGHTEN",      _DEFAULT_AUTO_TIGHTEN))
            self.tighten_step     = float(getattr(cfg, "SNIPER_AUTO_TIGHTEN_STEP", _DEFAULT_TIGHTEN_STEP))
        except Exception:
            self.ml_conf_min   = _DEFAULT_ML_CONF_MIN
            self.smc_conf_min  = _DEFAULT_SMC_CONF_MIN
            self.htf_conf_min  = _DEFAULT_HTF_CONF_MIN
            self.atr_ratio_max = _DEFAULT_ATR_RATIO_MAX
            self.require_sweep = _DEFAULT_REQUIRE_SWEEP
            self.auto_tighten  = _DEFAULT_AUTO_TIGHTEN
            self.tighten_step  = _DEFAULT_TIGHTEN_STEP

        # Sniper result history for auto-tighten mechanism
        self._result_history: List[bool]  = []   # True=WIN, False=LOSS
        self._tighten_window = _DEFAULT_TIGHTEN_WINDOW
        self._tighten_wr_floor = _DEFAULT_TIGHTEN_WR_FLOOR

        # Persistence for ml_conf_min after auto-tightens survive restarts
        if persistence_file is None:
            try:
                base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
                persistence_file = os.path.join(base, "data", "sniper_state.json")
            except Exception:
                persistence_file = "data/sniper_state.json"
        self._persistence_file = persistence_file
        self._load_state()

    # ── STATE PERSISTENCE ─────────────────────────────────────────────────

    def _load_state(self):
        """Load persisted ml_conf_min and result history from disk."""
        try:
            if os.path.exists(self._persistence_file):
                with open(self._persistence_file, "r", encoding="utf-8") as f:
                    state = json.load(f)
                saved_conf = float(state.get("ml_conf_min", self.ml_conf_min))
                # Only apply if it was tightened (never loosen below base)
                if saved_conf >= self.ml_conf_min:
                    self.ml_conf_min = saved_conf
                self._result_history = list(state.get("result_history", []))[-self._tighten_window:]
        except Exception as _e:
            logger.debug(f"[SNIPER] Could not load state: {_e}")

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self._persistence_file), exist_ok=True)
            state = {
                "ml_conf_min": self.ml_conf_min,
                "result_history": self._result_history[-self._tighten_window:],
            }
            with open(self._persistence_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as _e:
            logger.debug(f"[SNIPER] Could not save state: {_e}")

    # ── PUBLIC API ────────────────────────────────────────────────────────

    def is_sniper_setup(
        self,
        setup: Dict[str, Any],
        engine_votes: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        Evaluate whether a candidate setup passes Triple-Lock Sniper confirmation.

        Args:
            setup: Dict with keys:
                   - mode: str  ("SMALL_PATTERN" | "BIG_PATTERN" | "SCALP" | ...)
                   - direction: str  ("BUY" | "SELL")
                   - smc_confidence: float  (0.0–1.0)  OB structural confidence
                   - fvg_present: bool  Fair Value Gap in the zone
                   - htf_confidence: float  (0.0–1.0)  H1 HTF bias confidence
                   - htf_direction: str  ("bullish" | "bearish" | "neutral")
                   - atr_ratio: float  current ATR / baseline ATR (1.0 = normal)
                   - sweep_confirmed: bool  HTF liquidity sweep occurred (PO3)
            engine_votes: Dict from consensus brain containing at minimum:
                   - "ml_ensemble": { "direction": str, "confidence": float }

        Returns:
            (True, "SNIPER_PASS") if all locks pass
            (False, "<REASON>")   if any lock fails
        """
        # ── LOCK 0: Pattern-only — refuse scalp tier ─────────────────────
        mode = str(setup.get("mode", "")).upper()
        if "SCALP" in mode or mode == "":
            return False, "SNIPER_SCALP_DISABLED"

        direction = str(setup.get("direction", "")).upper()
        if direction not in ("BUY", "SELL"):
            return False, f"SNIPER_INVALID_DIRECTION:{direction}"

        # ── LOCK 1: SMC Structural Lock (OB + FVG) ───────────────────────
        smc_conf  = float(setup.get("smc_confidence", 0.0))
        fvg_present = bool(setup.get("fvg_present", False))

        if smc_conf < self.smc_conf_min:
            return False, f"SNIPER_SMC_FAIL:smc_conf={smc_conf:.2f}<{self.smc_conf_min:.2f}"
        if not fvg_present:
            return False, "SNIPER_SMC_FAIL:FVG_NOT_PRESENT"

        # ── LOCK 2: ML Ensemble Directional Probability ───────────────────
        ml_vote = engine_votes.get("ml_ensemble", engine_votes.get("ML_ENSEMBLE", {}))
        ml_conf = float(ml_vote.get("confidence", 0.0))
        ml_dir  = str(ml_vote.get("direction", "neutral")).lower()

        # Confirm ML direction matches setup direction
        expected_ml_dir = "bullish" if direction == "BUY" else "bearish"
        if ml_dir != expected_ml_dir:
            return False, f"SNIPER_ML_FAIL:direction_mismatch(ml={ml_dir},setup={expected_ml_dir})"
        if ml_conf < self.ml_conf_min:
            return False, f"SNIPER_ML_FAIL:ml_conf={ml_conf:.2f}<{self.ml_conf_min:.2f}"

        # ── LOCK 3: HTF Alignment ─────────────────────────────────────────
        htf_conf = float(setup.get("htf_confidence", 0.0))
        htf_dir  = str(setup.get("htf_direction", "neutral")).lower()
        expected_htf_dir = "bullish" if direction == "BUY" else "bearish"

        if htf_dir != expected_htf_dir:
            return False, f"SNIPER_HTF_FAIL:direction_mismatch(htf={htf_dir},setup={expected_htf_dir})"
        if htf_conf < self.htf_conf_min:
            return False, f"SNIPER_HTF_FAIL:htf_conf={htf_conf:.2f}<{self.htf_conf_min:.2f}"

        # ── LOCK 4: Volatility Guard (ATR Ratio) ─────────────────────────
        atr_ratio = float(setup.get("atr_ratio", 1.0))
        if atr_ratio > self.atr_ratio_max:
            return False, f"SNIPER_ATR_FAIL:atr_ratio={atr_ratio:.2f}>{self.atr_ratio_max:.2f}(news/spike)"

        # ── LOCK 5: Liquidity Sweep Pre-condition (Big Pattern only) ──────
        if self.require_sweep and "BIG" in mode:
            sweep_confirmed = bool(setup.get("sweep_confirmed", False))
            if not sweep_confirmed:
                return False, "SNIPER_SWEEP_FAIL:HTF_LIQ_SWEEP_REQUIRED_FOR_BIG_PATTERN"

        logger.info(
            f"[SNIPER] ✅ TRIPLE-LOCK PASS | {direction} | "
            f"SMC={smc_conf:.2f} ML={ml_conf:.2f} HTF={htf_conf:.2f} ATR={atr_ratio:.2f}"
        )
        return True, "SNIPER_PASS"

    def record_outcome(self, is_win: bool):
        """
        Record trade outcome for auto-tighten WR tracking.
        Call this after each closed sniper trade.
        """
        self._result_history.append(is_win)
        if len(self._result_history) > self._tighten_window:
            self._result_history = self._result_history[-self._tighten_window:]

        if self.auto_tighten and len(self._result_history) >= self._tighten_window:
            self._maybe_tighten()

        self._save_state()

    def get_current_thresholds(self) -> Dict[str, float]:
        """Return current active threshold values."""
        return {
            "ml_conf_min":   self.ml_conf_min,
            "smc_conf_min":  self.smc_conf_min,
            "htf_conf_min":  self.htf_conf_min,
            "atr_ratio_max": self.atr_ratio_max,
            "require_sweep": float(self.require_sweep),
        }

    def current_sniper_wr(self) -> float:
        """Returns rolling WR over last N sniper trades."""
        if not self._result_history:
            return 0.0
        return sum(self._result_history) / len(self._result_history)

    # ── PRIVATE ───────────────────────────────────────────────────────────

    def _maybe_tighten(self):
        """Auto-tighten ml_conf_min if rolling WR is below floor."""
        current_wr = self.current_sniper_wr()
        if current_wr < self._tighten_wr_floor:
            old_ml = self.ml_conf_min
            self.ml_conf_min = min(0.97, round(self.ml_conf_min + self.tighten_step, 3))
            logger.warning(
                f"[SNIPER AUTO-TIGHTEN] Rolling WR={current_wr*100:.1f}% < "
                f"{self._tighten_wr_floor*100:.0f}% target. "
                f"ml_conf_min tightened: {old_ml:.2f} → {self.ml_conf_min:.2f}"
            )


# ─────────────────────────────────────────────────────────────
# Helper: Build sniper setup dict from brain context
# ─────────────────────────────────────────────────────────────

def build_sniper_setup(
    direction: str,
    pattern_tier: str,
    big_pattern,
    ml_vote: Dict,
    atr_estimate: float,
    atr_baseline: float = 0.0,
    sweep_result: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Constructs the setup dict expected by SniperFilter.is_sniper_setup()
    from existing brain context variables.

    Args:
        direction:      "BUY" | "SELL"
        pattern_tier:   "scalp" | "pro_trend" | "small_pattern"
        big_pattern:    BigPatternResult from detect_big_pattern()
        ml_vote:        engine_votes["ml_ensemble"] dict
        atr_estimate:   current ATR in points
        atr_baseline:   20-bar mean ATR for ratio (0 → use atr_estimate as 1.0x)
        sweep_result:   result dict from detect_sweep() or None

    Returns:
        setup dict ready for SniperFilter.is_sniper_setup()
    """
    # Mode tag
    if "big" in pattern_tier.lower() or "pro_trend" in pattern_tier.lower():
        mode = "BIG_PATTERN"
    elif "small" in pattern_tier.lower():
        mode = "SMALL_PATTERN"
    else:
        mode = "SCALP"

    # SMC Confidence — use big_pattern.confidence + bonus for CHoCH vs BOS
    smc_conf = float(getattr(big_pattern, "confidence", 0.0))

    # FVG presence — detected from big_pattern details containing "FVG"
    details_str = " ".join(getattr(big_pattern, "details", []))
    fvg_present = "FVG" in details_str.upper() or "OB" in details_str.upper()

    # HTF alignment from big_pattern (tf_h1_bias vs bias)
    h1_bias   = getattr(big_pattern, "tf_h1_bias", "neutral").lower()
    m5_bias   = getattr(big_pattern, "tf_m5_bias", "neutral").lower()
    bias      = getattr(big_pattern, "bias", "neutral").lower()

    expected_dir_str = "bullish" if direction == "BUY" else "bearish"
    htf_direction = h1_bias if h1_bias != "neutral" else m5_bias

    # HTF confidence — max when H1 confirms M5
    if h1_bias == bias and h1_bias != "neutral":
        htf_conf = min(1.0, smc_conf + 0.15)  # H1 confirmation bonus
    elif h1_bias == "neutral":
        htf_conf = smc_conf * 0.70             # No H1 data — reduced confidence
    else:
        htf_conf = 0.0                         # H1 conflicts

    # ATR Ratio
    atr_ratio = (atr_estimate / atr_baseline) if atr_baseline > 0 else 1.0
    atr_ratio = round(atr_ratio, 2)

    # Sweep confirmation
    sweep_confirmed = False
    if sweep_result:
        if direction == "BUY" and sweep_result.get("bullish_sweep"):
            sweep_confirmed = True
        elif direction == "SELL" and sweep_result.get("bearish_sweep"):
            sweep_confirmed = True

    return {
        "mode":             mode,
        "direction":        direction,
        "smc_confidence":   smc_conf,
        "fvg_present":      fvg_present,
        "htf_confidence":   htf_conf,
        "htf_direction":    htf_direction,
        "atr_ratio":        atr_ratio,
        "sweep_confirmed":  sweep_confirmed,
    }
