"""AEGIS QUANT AI — Reinforcement Learning research layer (directive Sections 9-12).

Modes (Section 10): RL_DISABLED / RL_RESEARCH / RL_PAPER / RL_DEMO.
Default is RL_RESEARCH.  An agent NEVER bypasses the risk engine, SL/TP
validation, demo guard or broker constraints — the environment itself routes
every action through quant_ai.risk.RiskManager before it affects state.
"""
from quant_ai.rl.environment import (  # noqa: F401
    ACTIONS, TradingEnv, make_env, rl_mode_gate,
)

__all__ = ["ACTIONS", "TradingEnv", "make_env", "rl_mode_gate"]
