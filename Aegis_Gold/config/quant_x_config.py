"""
AEGIS QUANT X — Typed Configuration Loader
===========================================
Single source of truth for all QUANT X module parameters.
Reads quant_x_flags.json and exposes typed accessors.

Rules:
 - Import this, never import quant_x_flags.json directly.
 - Every value has a safe default so the system degrades gracefully
   if the JSON file is absent or partially populated.
 - No external dependencies — stdlib only.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("aegis.quant_x_config")

_BASE_DIR = Path(__file__).parent
_FLAGS_PATH = _BASE_DIR / "quant_x_flags.json"

# ---------------------------------------------------------------------------
# Defaults — used when the JSON key is absent
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, Any] = {
    # Feature flags
    "data_integrity":              False,
    "macro_event_context":         False,
    "extended_features":           False,
    "extended_regime":             False,
    "conformal_prediction":        False,
    "hmm_regime_model":            False,
    "ensemble_disagreement":       False,
    "autoencoder_anomaly":         False,
    "meta_labeler":                False,
    "offline_rl":                  False,
    "decision_fusion_v2":          False,
    "ai_supervisor_macro_veto":    False,
    "volatility_scaled_lot":       False,
    "cvar_risk":                   False,
    "margin_buffer_check":         False,
    "volatility_circuit_breaker":  False,
    "execution_integrity":         False,
    "champion_human_gate":         True,   # On by default for safety
    "walk_forward_validation":     False,
    "shap_explainability":         False,
    "scheduled_digest":            False,
    "digest_utc_hour":             6,
    "chaos_testing":               False,
    "heartbeat_watchdog_v2":       False,
    "secrets_audit":               True,   # On by default for safety

    # ── Module Extension Flags (Aegis-Gold v6 upgrade) ───────────────────────
    "quant_features":              False,   # FFT/wavelet/Hurst features in FeatureFactory
    "kelly_sizing":                False,   # Fractional Kelly position sizing

    # ── Data Integrity ───────────────────────────────────────────────────────
    "data_integrity_gap_multiplier":   2.0,   # Bar gap > N × expected interval → flagged
    "data_integrity_stale_ticks":      50,    # Unchanged bid for N ticks → stale
    "data_integrity_outlier_sigma":    5.0,   # Bar move > N σ → rejected

    # ── Macro Context ────────────────────────────────────────────────────────
    "calendar_source":             "forexfactory_rss",  # "forexfactory_rss" | "fmp_api"
    "calendar_refresh_minutes":    60,
    "blackout_nfp_minutes":        30,
    "blackout_fomc_minutes":       60,
    "blackout_cpi_minutes":        20,
    "blackout_default_minutes":    15,
    "reduced_size_factor":         0.5,       # Lot multiplier during near-event window

    # ── Extended Features ────────────────────────────────────────────────────
    "feature_return_windows":      [1, 5, 15, 60],
    "feature_hurst_window":        100,
    "feature_entropy_window":      50,
    "feature_wavelet_levels":      3,

    # ── Extended Regime ──────────────────────────────────────────────────────
    "regime_ambiguity_threshold":  0.55,      # Max class prob < this → TRANSITIONAL

    # ── ML / Ensemble ────────────────────────────────────────────────────────
    "ensemble_disagreement_block_threshold": 0.35,  # Std > this → block trade
    "conformal_coverage":          0.90,             # Target coverage for intervals
    "hmm_n_states":                4,

    # ── Meta-Labeler ─────────────────────────────────────────────────────────
    "meta_labeler_min_trades":     100,       # Min closed trades before training

    # ── Offline RL ───────────────────────────────────────────────────────────
    "cql_alpha":                   1.0,       # Conservative penalty coefficient
    "cql_churn_penalty":           0.05,      # Per-trade frequency penalty in reward
    "cql_max_trades_per_day":      20,        # Frequency denominator for reward shaping
    "rl_baseline_policy":          "ema_crossover",
    "rl_min_shadow_before_arena":  100,

    # ── Decision Fusion ──────────────────────────────────────────────────────
    "fusion_uncertainty_block":    0.60,      # Combined uncertainty > this → WAIT
    "fusion_disagreement_shrink":  0.30,      # Ensemble disagreement > this → halve lot

    # ── Risk Intelligence v2 ─────────────────────────────────────────────────
    "vol_scaled_target_vol":       0.01,      # 1% of equity per trade
    "cvar_alpha":                  0.05,      # 5% tail
    "margin_buffer_pct":           0.20,      # 20% above margin-call as safety floor
    "circuit_breaker_atr_multiple": 3.0,      # ATR > N × baseline → halt new entries
    "heartbeat_timeout_sec":       120,

    # ── Execution Integrity ──────────────────────────────────────────────────
    "slippage_alert_sigma":        3.0,       # Slippage > N σ of historical → alert
    "spread_anomaly_multiple":     3.0,       # Spread > N × historical → pause
    "broker_anomaly_window":       50,        # Bars of spread history for baseline

    # ── Champion / Challenger ────────────────────────────────────────────────
    "arena_min_shadow_decisions":  100,       # Overrides champion_challenger.py default
    "arena_require_human_approval": True,
    "arena_demotion_miscal_windows": 3,       # Consecutive bad calibration windows → demote

    # ── Validation Pipeline ──────────────────────────────────────────────────
    "wf_n_splits":                 5,
    "wf_embargo_bars":             5,
    "bootstrap_n_iterations":      1000,

    # ── Observability ────────────────────────────────────────────────────────
    "decision_records_db":         "data/decision_records.db",

    # ── Scheduled Digest ─────────────────────────────────────────────────────
    "digest_utc_hour":             6,
}


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class QuantXConfig:
    """
    Typed, lazy-loaded accessor for all QUANT X flags and parameters.
    Safe: missing keys fall back to _DEFAULTS; file absence falls back entirely.
    """

    def __init__(self):
        self._raw: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if _FLAGS_PATH.exists():
            try:
                self._raw = json.loads(_FLAGS_PATH.read_text(encoding="utf-8"))
                logger.debug("[QUANT-X] Flags loaded from %s", _FLAGS_PATH)
            except Exception as exc:
                logger.warning("[QUANT-X] Could not parse %s: %s — using defaults", _FLAGS_PATH, exc)
        else:
            logger.warning("[QUANT-X] %s not found — all flags default to False", _FLAGS_PATH)

    def reload(self) -> None:
        """Re-read flags file at runtime (e.g. after Telegram /reload command)."""
        self._raw = {}
        self._load()

    def get(self, key: str) -> Any:
        """Return value for key, falling back to _DEFAULTS, then None."""
        if key in self._raw:
            return self._raw[key]
        if key in _DEFAULTS:
            return _DEFAULTS[key]
        logger.warning("[QUANT-X] Unknown config key '%s' — returning None", key)
        return None

    def flag(self, key: str) -> bool:
        """Convenience bool accessor with strict fallback to False."""
        val = self.get(key)
        return bool(val) if val is not None else False

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def as_dict(self) -> dict:
        merged = dict(_DEFAULTS)
        merged.update(self._raw)
        return merged

    def dump_active_flags(self) -> dict:
        """Returns only the boolean flags that are currently True."""
        return {
            k: v for k, v in self.as_dict().items()
            if isinstance(v, bool) and v
        }


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere
# ---------------------------------------------------------------------------

_cfg: QuantXConfig | None = None


def get_quant_x_config() -> QuantXConfig:
    global _cfg
    if _cfg is None:
        _cfg = QuantXConfig()
    return _cfg


# Convenience shorthand — use `QX["flag_name"]` or `QX.flag("flag_name")`
QX = get_quant_x_config()
