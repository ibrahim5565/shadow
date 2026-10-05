"""Measured walk-forward MODEL TOURNAMENT on REAL MT5 demo data.

Fetches live M5 history from the connected MT5 demo terminal for EURUSD and
XAUUSD, then evaluates every verified model + naive baselines chronologically
(walk-forward, embargoed - Sections 27/28/30/33).  All numbers reported are
actual measurements; kronos predictions use the real pretrained checkpoint.

Run:  .venv_cuda\\Scripts\\python.exe scripts\\run_tournament_measured.py
Output: printed leaderboard + scratch/tournament_results.json
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd                       # noqa: E402

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logging.getLogger("matplotlib").setLevel(logging.WARNING)

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "scratch",
                        "tournament_results.json")
N_BARS = 3000
STEP = 50            # one scored forecast every 50 bars -> ~57 scored points


def fetch_m5(symbol: str, n: int = N_BARS) -> pd.DataFrame:
    import MetaTrader5 as mt5
    if not mt5.initialize():
        raise RuntimeError(f"MT5 init failed: {mt5.last_error()}")
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, n)
        if rates is None or len(rates) < 500:
            raise RuntimeError(f"insufficient {symbol} history: "
                               f"{0 if rates is None else len(rates)} bars")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("time")
        return df[["open", "high", "low", "close", "tick_volume"]]
    finally:
        mt5.shutdown()


def main() -> int:
    from quant_ai.models.baselines import all_baselines
    from quant_ai.models.chronos_adapter import ChronosAdapter
    from quant_ai.models.kronos_adapter import KronosAdapter
    from quant_ai.storage.db import QuantAIStore
    from quant_ai.validation.tournament import ModelTournament

    store = QuantAIStore()
    tournament = ModelTournament(store=store, embargo=12, min_samples=120)
    all_rows, t0 = [], time.time()

    for symbol in ("EURUSD", "XAUUSD"):
        print(f"\n=== fetching {symbol} M5 x{N_BARS} from MT5 demo ===")
        df = fetch_m5(symbol)
        print(f"    range {df.index[0]} .. {df.index[-1]}  ({len(df)} bars)")

        models = all_baselines(symbol=symbol, timeframe="M5")
        kronos = KronosAdapter(model_key="kronos_small", symbol=symbol,
                               timeframe="M5", uncertainty_runs=3)
        if kronos.load():
            print("    kronos_small loaded (real pretrained weights)")
            models.append(kronos)
        else:
            print("    kronos_small NOT loaded - excluded (no fabricated rows)")

        chronos = ChronosAdapter(symbol=symbol, timeframe="M5")
        if chronos.load():
            print("    chronos2 loaded (amazon/chronos-2, Apache-2.0)")
            models.append(chronos)
        else:
            print("    chronos2 NOT loaded - excluded (no fabricated rows)")

        leaderboard = tournament.run(models, df, horizon=12, symbol=symbol,
                                     timeframe="M5", step=STEP)
        print(ModelTournament.print_leaderboard(leaderboard))
        for row in leaderboard:
            all_rows.append(row)

    payload = {"measured": True, "data_source": "MT5 demo terminal (live M5)",
               "step": STEP, "horizon": 12, "embargo": 12,
               "elapsed_s": round(time.time() - t0, 1), "results": all_rows}
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\nsaved -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
