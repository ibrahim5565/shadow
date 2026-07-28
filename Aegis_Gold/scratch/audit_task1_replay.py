"""
Task 1 — CORRECTED Phase 2 Replay Backtest (Lookahead-Bias Audit)
==================================================================
AUDIT FINDING (pre-fix):
  The previous version (replay_phase2_backtest.py) was NOT a replay of historical price paths.
  It was a pure simulation that:
    1. Applied fixed 200pt SL / 400pt TP synthetic parameters to every trade.
    2. Used `idx % 5 in (0, 1)` (a deterministic modulo on row index) to decide which losing
       trades "recover" to a win — this is not derived from any price data.
    3. Used fixed synthetic lot sizing completely independent of actual trade lot sizes.
  This is a lookahead-free fabrication, not a lookahead-biased replay — it contains no
  actual price path data at all. The reported PF of 3.746 is arithmetically derived from
  chosen constants, not from historical trade outcomes.

WHAT A VALID FORWARD REPLAY REQUIRES:
  - The actual price path (tick or OHLC bar sequence) from each trade's entry_time forward.
  - The algorithm walks each bar/tick checking if new SL or new TP is hit first in chronological order.
  - Only the exit_price/exit_time is replaced by what the new SL/TP would have produced.
  This data is NOT stored in trade_memory.db. The database has:
    - entry_price, exit_price, sl_points, tp_points (recorded at trade execution)
    - tp_was_hit / sl_was_hit columns: ALL NULL (exit reason not recorded per-trade)
    - atr: ALL ZERO (ATR not logged at execution time)
    - All XAUUSD trades were mass-closed at 2026-07-08T13:38:40 (one-time emergency exit),
      not via SL/TP triggers — there is no SL/TP hit ordering available.

WHAT THIS SCRIPT DOES INSTEAD (honest best-effort):
  Using available data:
    - entry_price, exit_price, direction, sl_points, tp_points, profit_usd
  We can determine for each closed trade whether the exit PRICE DISTANCE implies the SL or
  TP was closer (using entry→exit price move vs SL/TP distance). This is an approximation
  — it cannot determine hit ORDER when both levels were crossed in a single candle — but it
  is derived from real recorded prices, not from synthetic parameters.

  For trades where the mass-close timestamp is the exit (no clean SL/TP hit), we label them
  as "timed out" and exclude from the counterfactual SL/TP analysis.

  We then model: "if ATR-scaled SL/TP had been applied (SL=150pts, TP=350pts for XAUUSD),
  and we assume the actual exit price movement is a proxy for what the market did..."
  ...and report what FRACTION of real trade moves would have cleared the new TP vs hit the
  new SL first — using the direction-adjusted exit move as the proxy price path.

RESULT FORMAT:
  This script reports:
    1. Baseline PF from the actual historical records (unaltered).
    2. Honest statement about what forward replay requires and why it cannot be done here.
    3. Price-move proxy analysis: of XAUUSD trades, how many exit moves exceeded new TP,
       exceeded new SL, or were insufficient to determine either.
  It does NOT report a fabricated Profit Factor from synthetic parameters.
"""

import sqlite3
import numpy as np
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
TRADE_MEMORY_DB = DATA_DIR / "trade_memory.db"

MASS_CLOSE_TIMESTAMP = "2026-07-08T13:38:40"

print("=" * 70)
print("TASK 1 — PHASE 2 REPLAY AUDIT (Corrected, Lookahead-Free)")
print("=" * 70)

conn = sqlite3.connect(TRADE_MEMORY_DB)
df_all = pd.read_sql_query(
    "SELECT trade_id, symbol, direction, entry_time, exit_time, "
    "entry_price, exit_price, sl_points, tp_points, profit_usd, lot_size "
    "FROM trades WHERE profit_usd IS NOT NULL",
    conn
)
conn.close()

df_all["profit_usd"] = pd.to_numeric(df_all["profit_usd"], errors="coerce")
df_all = df_all.dropna(subset=["profit_usd"])

print(f"\nLoaded {len(df_all)} trades total (all symbols).")
print(f"Symbols present: {df_all['symbol'].value_counts().to_dict()}")

# --- BASELINE ACTUALS (real historical, no modification) ---
wins = df_all[df_all["profit_usd"] > 0]
losses = df_all[df_all["profit_usd"] < 0]
gross_win = wins["profit_usd"].sum()
gross_loss = abs(losses["profit_usd"].sum())
actual_pf = gross_win / gross_loss if gross_loss > 0 else float("nan")

print(f"\n--- ACTUAL HISTORICAL PERFORMANCE (no modification) ---")
print(f"  Total trades:  {len(df_all)}")
print(f"  Wins:          {len(wins)}  |  Losses:  {len(losses)}")
print(f"  Gross Profit:  ${gross_win:.2f}  |  Gross Loss:  ${gross_loss:.2f}")
print(f"  Actual Profit Factor:  {actual_pf:.3f}")
print(f"  Avg Win:  ${wins['profit_usd'].mean():.4f}  |  Avg Loss:  ${abs(losses['profit_usd'].mean()):.4f}")

# --- XAUUSD specific ---
df_xau = df_all[df_all["symbol"] == "XAUUSD"].copy()
df_xau["exit_time_str"] = df_xau["exit_time"].astype(str)
df_xau["mass_closed"] = df_xau["exit_time_str"].str.startswith(MASS_CLOSE_TIMESTAMP)

n_mass = df_xau["mass_closed"].sum()
n_clean = (~df_xau["mass_closed"]).sum()

print(f"\n--- XAUUSD TRADE EXIT ANALYSIS ---")
print(f"  Total XAUUSD trades with profit_usd: {len(df_xau)}")
print(f"  Mass-closed at {MASS_CLOSE_TIMESTAMP}: {n_mass} trades (exit reason UNKNOWN — cannot determine SL/TP hit order)")
print(f"  Trades with non-mass-close exits: {n_clean}")

# --- Price-move proxy on non-mass-close XAUUSD trades ---
df_clean = df_xau[~df_xau["mass_closed"]].copy()
df_clean = df_clean[
    (df_clean["entry_price"] > 0) &
    (df_clean["exit_price"] > 0) &
    (df_clean["sl_points"] > 0)
].copy()

if len(df_clean) > 0:
    # Convert price points to price units: XAUUSD 1 point = 0.01
    # Compute directional exit move in points
    df_clean["price_move_pts"] = np.where(
        df_clean["direction"] == "BUY",
        (df_clean["exit_price"] - df_clean["entry_price"]) * 100.0,
        (df_clean["entry_price"] - df_clean["exit_price"]) * 100.0
    )

    # New ATR-scaled SL/TP floors
    NEW_SL_PTS = 150.0
    NEW_TP_PTS = 350.0  # R:R ~2.3

    reached_tp = (df_clean["price_move_pts"] >= NEW_TP_PTS).sum()
    hit_sl     = (df_clean["price_move_pts"] <= -NEW_SL_PTS).sum()
    ambiguous  = len(df_clean) - reached_tp - hit_sl

    print(f"\n--- PROXY ANALYSIS: Non-mass-close XAUUSD trades ({len(df_clean)}) ---")
    print(f"  (Using actual entry->exit price move as proxy. Cannot determine hit ORDER within candle.)")
    print(f"  NEW_SL = {NEW_SL_PTS}pts | NEW_TP = {NEW_TP_PTS}pts")
    print(f"  Exit move reached NEW_TP ({NEW_TP_PTS}pts+):    {reached_tp}")
    print(f"  Exit move hit NEW_SL ({NEW_SL_PTS}pts-):        {hit_sl}")
    print(f"  Ambiguous (move inside SL/TP range):             {ambiguous}")

    if reached_tp + hit_sl > 0:
        proxy_gross_win = reached_tp * NEW_TP_PTS
        proxy_gross_loss = hit_sl * NEW_SL_PTS
        proxy_pf = proxy_gross_win / proxy_gross_loss if proxy_gross_loss > 0 else float("nan")
        print(f"\n  PROXY Profit Factor (equal-lot assumption, {len(df_clean)} non-mass-close trades):")
        print(f"  Gross proxy win: {proxy_gross_win:.0f}pts | Gross proxy loss: {proxy_gross_loss:.0f}pts")
        print(f"  Proxy PF: {proxy_pf:.3f}")
        print(f"  WARNING: This proxy PF is for {len(df_clean)} trades only (not 3,806).")
        print(f"  The remaining {n_mass} XAUUSD trades have unknown SL/TP hit order.")
    else:
        print("  No clean TP/SL determinations possible.")
else:
    print(f"  No non-mass-close XAUUSD trades with valid entry/exit/SL data.")

print(f"""
--- CONCLUSION ---
  PREVIOUS RESULT (PF=3.746): INVALID. That script applied synthetic fixed parameters
  (200pt SL, 400pt TP) and used `idx % 5` to flip 40% of losses to wins. This is not
  a replay — it is a deterministic fabrication with no connection to historical price data.

  HONEST RESULT: A genuine forward replay requires tick or OHLC bar data from entry_time
  forward for each trade. This data is NOT stored in trade_memory.db.
  
  The actual historical PF is {actual_pf:.3f} (computed above from real profit_usd records).
  A counterfactual SL/TP replay CANNOT be reliably computed from available data.
  
  To do it properly: log per-bar OHLC data alongside each live trade and build a dedicated
  bar-by-bar replay harness that checks SL/TP hit order chronologically.
""")
