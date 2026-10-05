"""AEGIS QUANT AI — configuration (safety-first).

Central settings for the modular pretrained-model AI layer.  Defaults mirror
sensible research/demo values; everything can be overridden via environment
variables (prefix ``QAI_``) so nothing is hard-wired in code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


# ══════════════════════════════════════════════════════════════════════════
# DEMO-ONLY SAFETY POLICY (Section 35 of the integration directive)
# ══════════════════════════════════════════════════════════════════════════
TRADING_MODE: str = "DEMO"          # HARD-CODED — DEMO ONLY
ALLOW_LIVE_TRADING: bool = False    # HARD-CODED — no accidental live path

RL_DISABLED = "RL_DISABLED"
RL_RESEARCH = "RL_RESEARCH"
RL_PAPER    = "RL_PAPER"
RL_DEMO     = "RL_DEMO"


@dataclass
class QAIConfig:
    """Runtime configuration for the quant-AI stack."""

    # ── model management ────────────────────────────────────────────────
    model_enable: Dict[str, bool] = field(default_factory=lambda: {
        "kronos_mini": False,
        "kronos_small": True,      # VERIFIED; MIT; real sampled forecasts measured locally
        "kronos_base": False,
        "chronos2": True,          # VERIFIED: chronos-forecasting 2.3.2 local inference
        "moirai": False,           # set True only after `pip install uni2ts`
        "timesfm": False,          # set True only after `pip install timesfm`
        "omega_forex_v3": True,    # VERIFIED; MIT; forex-specific CNN+Transformer
        "eurusd_lgb_xgb": True,    # VERIFIED; Apache-2.0; EURUSD LGB+XGB ensemble
        "xauusd_smc_xgb": True,    # VERIFIED; MIT; XAUUSD Smart-Money-Concepts XGBoost
        "patchtst": False,         # RUNNING but domain-mismatched (ETTh1) - opt-in only
    })
    max_models_in_memory: int = field(default_factory=lambda: _env_int("QAI_MAX_MODELS_IN_MEMORY", 2))
    use_gpu: bool = field(default_factory=lambda: _env_bool("QAI_USE_GPU", True))
    model_timeout_sec: float = field(default_factory=lambda: _env_float("QAI_MODEL_TIMEOUT", 120.0))
    cache_dir: str = field(default_factory=lambda: os.environ.get(
        "QAI_CACHE_DIR", os.path.join(os.path.dirname(__file__), "..", "models", "kronos_hf")))
    vendor_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(__file__), "vendor", "kronos"))
    uncertainty_sample_runs: int = field(default_factory=lambda: _env_int("QAI_UNCERTAINTY_SAMPLES", 5))
    forecast_sample_runs: int = field(default_factory=lambda: _env_int("QAI_FORECAST_SAMPLES", 1))

    # ── market scope ────────────────────────────────────────────────────
    symbols: List[str] = field(default_factory=lambda: ["EURUSD", "XAUUSD"])
    timeframes: List[str] = field(default_factory=lambda: ["M5", "M15", "H1"])
    forecast_horizon: Dict[str, int] = field(default_factory=lambda: {
        "M1": 12, "M5": 12, "M15": 12, "M30": 12, "H1": 12, "H4": 24, "D1": 24,
    })

    # ── risk engine (independent of any model) ──────────────────────────
    risk_per_trade: float = field(default_factory=lambda: _env_float("QAI_RISK_PER_TRADE", 0.01))   # 1% equity
    max_daily_loss: float = field(default_factory=lambda: _env_float("QAI_MAX_DAILY_LOSS", 0.05))   # 5% equity/day
    max_drawdown: float = field(default_factory=lambda: _env_float("QAI_MAX_DRAWDOWN", 0.20))       # 20% hard stop
    max_consecutive_losses: int = field(default_factory=lambda: _env_int("QAI_MAX_CONSEC_LOSSES", 4))
    max_spread_mult: float = field(default_factory=lambda: _env_float("QAI_MAX_SPREAD_MULT", 3.0))
    max_exposure_pct: float = field(default_factory=lambda: _env_float("QAI_MAX_EXPOSURE_PCT", 0.05))
    session_filter: bool = field(default_factory=lambda: _env_bool("QAI_SESSION_FILTER", True))
    volatility_block_mult: float = field(default_factory=lambda: _env_float("QAI_VOL_BLOCK_MULT", 4.0))

    # ── position sizing ─────────────────────────────────────────────────
    sizing_method: str = field(default_factory=lambda: os.environ.get("QAI_SIZING_METHOD", "fractional_kelly"))
    kelly_fraction: float = field(default_factory=lambda: _env_float("QAI_KELLY_FRACTION", 0.25))

    # ── RL ──────────────────────────────────────────────────────────────
    rl_mode: str = field(default_factory=lambda: os.environ.get("QAI_RL_MODE", RL_RESEARCH))
    rl_demo_requires_validation: bool = field(default_factory=lambda: _env_bool("QAI_RL_DEMO_VALIDATION", True))

    # ── news / sentiment ────────────────────────────────────────────────
    news_mode: str = field(default_factory=lambda: os.environ.get("QAI_NEWS_MODE", "DISABLED"))

    # ── execution ───────────────────────────────────────────────────────
    demo_mode: bool = field(default_factory=lambda: _env_bool("QAI_DEMO_MODE", True))
    allow_live_trading: bool = field(default_factory=lambda: _env_bool("QAI_ALLOW_LIVE_TRADING", False))
    slippage_points: Dict[str, int] = field(default_factory=lambda: {"EURUSD": 1, "XAUUSD": 5})
    commission_per_lot_usd: Dict[str, float] = field(default_factory=lambda: {"EURUSD": 7.0, "XAUUSD": 7.0})

    def enable(self, name: str) -> "QAIConfig":
        self.model_enable[name] = True
        return self


DEFAULT_CONFIG = QAIConfig()