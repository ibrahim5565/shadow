"""AEGIS QUANT AI - RL agents via Stable-Baselines3 (directive Section 9).

Every agent trains ONLY through quant_ai.rl.environment.TradingEnv, whose
actions are routed through the independent RiskManager - so no algorithm
(PPO / A2C / DQN / SAC / ...) can bypass risk, spread, session, drawdown or
SL/TP constraints (Section 12).

Promotion policy (Section 10): train_research() is only callable when the
config rl_mode is RL_RESEARCH (or RL_PAPER for evaluation); act() for
out-of-environment decisions requires RL_DEMO *plus* walk-forward
validation evidence (validated=True). Default is RL_RESEARCH.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np

from quant_ai.config import (QAIConfig, RL_DEMO, RL_DISABLED, RL_PAPER,
                             RL_RESEARCH)
from quant_ai.rl.environment import OBS_DIM, TradingEnv, rl_mode_gate

logger = logging.getLogger("quant_ai.rl.agents")

_ALGOS = ("PPO", "A2C", "DQN", "SAC", "TD3", "DDPG")   # SB3-supported subset


class RLAgent:
    """Mode-gated wrapper around an SB3 policy."""

    def __init__(self, algo: str = "PPO", config: Optional[QAIConfig] = None,
                 seed: int = 7):
        if algo.upper() not in _ALGOS:
            raise ValueError(f"unsupported algo {algo!r}; choose from {_ALGOS}")
        if algo.upper() in ("SAC", "TD3", "DDPG"):
            raise ValueError(f"{algo} is continuous-action; discrete trading "
                             "actions require PPO/A2C/DQN in this build")
        self.algo = algo.upper()
        self.cfg = config or QAIConfig()
        self.seed = seed
        self.model = None

    # -- training (Section 9) ------------------------------------------------
    def train_research(self, env: TradingEnv, timesteps: int = 50_000,
                       save_path: Optional[str] = None, verbose: int = 0) -> dict:
        allowed, reason = rl_mode_gate(self.cfg.rl_mode)
        if not allowed:
            raise PermissionError(f"RL training refused: {reason}")
        if self.cfg.rl_mode != RL_RESEARCH:
            raise PermissionError("train_research requires RL_RESEARCH mode; "
                                  f"current mode={self.cfg.rl_mode}")
        from stable_baselines3 import A2C, DQN, PPO    # lazy import

        cls = {"PPO": PPO, "A2C": A2C, "DQN": DQN}[self.algo]
        self.model = cls("MlpPolicy", env, seed=self.seed, verbose=verbose)
        self.model.learn(total_timesteps=int(timesteps))
        out = {"algo": self.algo, "timesteps": int(timesteps),
               "env_symbol": env.symbol, "env_timeframe": env.timeframe}
        if save_path:
            os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
            self.model.save(save_path)
            out["saved_to"] = save_path
        return out

    # -- evaluation ------------------------------------------------------------
    def evaluate(self, env: TradingEnv, deterministic: bool = True) -> dict:
        """Measured episode rollout; reports actual numbers only."""
        if self.model is None:
            raise RuntimeError("agent not trained/loaded")
        obs, _ = env.reset()
        done, steps = False, 0
        while not done:
            action, _ = self.model.predict(obs, deterministic=deterministic)
            obs, _, done, _, info = env.step(int(action))
            steps += 1
        return {"steps": steps, "final_equity": info["equity"],
                "return_pct": round((info["equity"] - env.start_equity)
                                    / env.start_equity * 100.0, 3),
                "n_closed_trades": len(env.closed_pnl),
                "drawdown_pct": info.get("drawdown_pct")}

    # -- out-of-environment action (Section 10) --------------------------------
    def act(self, obs: np.ndarray, validated: bool = False) -> dict:
        allowed, reason = rl_mode_gate(self.cfg.rl_mode, validated=validated)
        if not allowed or self.model is None:
            return {"action": 0, "name": "HOLD", "allowed": False,
                    "reason": reason if not allowed else "model not trained"}
        action, _ = self.model.predict(obs, deterministic=True)
        from quant_ai.rl.environment import ACTIONS
        return {"action": int(action),
                "name": ACTIONS[int(action)], "allowed": True, "reason": "ok"}

    def load(self, path: str) -> bool:
        from stable_baselines3 import A2C, DQN, PPO    # lazy import
        cls = {"PPO": PPO, "A2C": A2C, "DQN": DQN}[self.algo]
        try:
            self.model = cls.load(path)
            return True
        except Exception as exc:
            logger.error("load failed: %s", exc)
            return False
