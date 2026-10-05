"""MEASURED RL research training run on REAL MT5 demo data (Sections 9-12).

Trains a PPO agent inside quant_ai.rl.environment.TradingEnv (every action
routed through the independent RiskManager) on live M5 history pulled from
the MT5 demo terminal, then compares AGAINST measured baselines on the same
environment/episode: trained agent vs random policy vs HOLD-only.

No profitability is claimed; only the actual episode numbers are reported.

Run:  .venv_cuda\\Scripts\\python.exe scripts\\train_rl_research.py
Output: printed table + scratch/rl_research_results.json
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.WARNING)

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "scratch",
                        "rl_research_results.json")
N_BARS = 3000
TIMESTEPS = 30_000
SEED = 7


def fetch_m5(symbol: str, n: int = N_BARS):
    import MetaTrader5 as mt5
    import pandas as pd
    if not mt5.initialize():
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, n)
        if rates is None or len(rates) < 500:
            raise RuntimeError(f"insufficient {symbol} history")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("time")
        return df[["open", "high", "low", "close", "tick_volume"]]
    finally:
        mt5.shutdown()


def run_random(env, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    obs, _ = env.reset()
    done, steps = False, 0
    while not done:
        obs, _, done, _, info = env.step(int(rng.integers(0, 4)))
        steps += 1
    return _summary("random_policy", env, info, steps)


def run_hold(env) -> dict:
    obs, _ = env.reset()
    done, steps = False, 0
    while not done:
        obs, _, done, _, info = env.step(0)
        steps += 1
    return _summary("hold_only", env, info, steps)


def _summary(name, env, info, steps) -> dict:
    return {"policy": name, "steps": steps,
            "final_equity": round(info["equity"], 2),
            "return_pct": round((info["equity"] - env.start_equity)
                                / env.start_equity * 100.0, 3),
            "n_closed_trades": len(env.closed_pnl),
            "final_drawdown_pct": info.get("drawdown_pct")}


def main() -> int:
    from quant_ai.config import QAIConfig, RL_RESEARCH
    from quant_ai.rl.agents import RLAgent
    from quant_ai.rl.environment import make_env

    cfg = QAIConfig()
    cfg.session_filter = False
    assert cfg.rl_mode == RL_RESEARCH, "research run requires RL_RESEARCH mode"

    print("=== fetching EURUSD M5 history from MT5 demo ===")
    df = fetch_m5("EURUSD")
    print(f"    {len(df)} bars  {df.index[0]} .. {df.index[-1]}")

    point = 0.00001              # EURUSD 5-digit
    # account currency per lot per 1 point: 100k contract * 0.00001 = $1.0
    point_value_per_lot = 1.0

    def fresh_env():
        return make_env(df, config=cfg, symbol="EURUSD", timeframe="M5",
                        equity=10_000.0, spread_pts=3.0, point=point,
                        point_value_per_lot=point_value_per_lot, warmup=120,
                        max_drawdown=0.20)

    results, t0 = [], time.time()

    print("=== baseline: HOLD-only episode ===")
    results.append(run_hold(fresh_env()))

    print("=== baseline: RANDOM policy episode ===")
    results.append(run_random(fresh_env()))

    print(f"=== training PPO ({TIMESTEPS} timesteps, seed={SEED}) ===")
    train_env = fresh_env()
    agent = RLAgent("PPO", config=cfg, seed=SEED)
    train_info = agent.train_research(train_env, timesteps=TIMESTEPS,
                                      verbose=0)
    print(f"    trained in {round(time.time() - t0, 1)}s")

    print("=== evaluating trained PPO on fresh episode ===")
    eval_env = fresh_env()
    eval_result = agent.evaluate(eval_env, deterministic=True)
    results.append({"policy": "ppo_trained", **eval_result})

    payload = {"measured": True, "symbol": "EURUSD", "timeframe": "M5",
               "bars": len(df), "data_source": "MT5 demo terminal",
               "timesteps": TIMESTEPS, "total_elapsed_s": round(time.time() - t0, 1),
               "train_info": train_info, "results": results}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(json.dumps(payload["results"], indent=2))
    print(f"saved -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
