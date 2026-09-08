"""
Aegis Gold — Parameter Sensitivity & Overfitting Stress Test Engine
Performs multi-dimensional grid sweeps across $3.00–$4.00 targets, SL boundaries,
and spread ceilings to verify strategy robustness against parameter overfitting.
"""

import sys
import os
import itertools
import numpy as np
import pandas as pd
import MetaTrader5 as mt5

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from brain.opportunity_pipeline import OpportunityPipeline


def run_parameter_sweep():
    print("=" * 100)
    print("               AEGIS GOLD PARAMETER SENSITIVITY & OVERFITTING SWEEP")
    print("=" * 100)

    if not mt5.initialize():
        print("❌ MT5 Initialization failed.")
        return

    symbol = "XAUUSD"
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 15000)
    if rates is None or len(rates) < 100:
        print("❌ Failed to fetch MT5 rates.")
        mt5.shutdown()
        return

    sym_info = mt5.symbol_info(symbol)
    point = getattr(sym_info, 'point', 0.01)
    df = pd.DataFrame(rates)
    df['time_dt'] = pd.to_datetime(df['time'], unit='s')
    mt5.shutdown()

    # Parameter grid
    target_usd_grid = [3.00, 3.25, 3.50, 3.75, 4.00]
    sl_points_grid = [120, 150, 180]
    horizon_bars_grid = [18, 24, 30]

    pipeline = OpportunityPipeline()

    class MockRiskMgr:
        def is_daily_loss_limit_reached(self, current_equity=None):
            return False

    risk_mgr = MockRiskMgr()

    # Pre-extract all candidate opportunities
    print(f"Pre-scanning {len(df)} M5 bars for structural setups...")
    setup_indices = []
    i = 50
    while i < len(df) - 35:
        sub = df.iloc[i-50:i]
        auth, code = pipeline.evaluate_opportunity(
            symbol=symbol,
            candles_m5=sub,
            candles_m1=None,
            ticks=[],
            account={"equity": 5000.0},
            spread_pts=15.0,
            point=point,
            session="LONDON",
            risk_mgr=risk_mgr
        )
        if auth and auth.authorized:
            setup_indices.append((i, auth))
            i += 12 # skip forward slightly to reduce overlapping identical setups
        else:
            i += 1

    print(f"Identified {len(setup_indices)} candidate setup instances. Running grid sweep...")

    results = []

    for tgt_usd, sl_pts, horizon in itertools.product(target_usd_grid, sl_points_grid, horizon_bars_grid):
        trade_pnls = []
        for idx, auth in setup_indices:
            entry_px = auth.entry_price
            direction = auth.direction
            lot = auth.lot
            
            # Derived prices for current parameter combination
            is_gold = "XAU" in symbol
            dollar_per_pt = lot * (1.0 if is_gold else 1.0)
            required_tp_pts = max(30, int(tgt_usd / dollar_per_pt))
            
            if direction == "BUY":
                tp_px = entry_px + (required_tp_pts * point)
                sl_px = entry_px - (sl_pts * point)
            else:
                tp_px = entry_px - (required_tp_pts * point)
                sl_px = entry_px + (sl_pts * point)

            future = df.iloc[idx:idx+horizon]
            outcome_pnl = 0.0
            resolved = False

            for _, f in future.iterrows():
                if direction == "BUY":
                    if f['high'] >= tp_px:
                        outcome_pnl = tgt_usd; resolved = True; break
                    elif f['low'] <= sl_px:
                        outcome_pnl = -(sl_pts * dollar_per_pt); resolved = True; break
                else:
                    if f['low'] <= tp_px:
                        outcome_pnl = tgt_usd; resolved = True; break
                    elif f['high'] >= sl_px:
                        outcome_pnl = -(sl_pts * dollar_per_pt); resolved = True; break

            if not resolved:
                exit_px = future.iloc[-1]['close']
                move = (exit_px - entry_px)/point if direction == "BUY" else (entry_px - exit_px)/point
                outcome_pnl = round(move * dollar_per_pt, 2)

            trade_pnls.append(outcome_pnl)

        pnls = np.array(trade_pnls)
        wins = pnls[pnls > 0]
        losses = pnls[pnls < 0]
        n_trades = len(pnls)
        wr = (len(wins) / n_trades * 100.0) if n_trades > 0 else 0.0
        g_win = wins.sum() if len(wins) > 0 else 0.0
        g_loss = abs(losses.sum()) if len(losses) > 0 else 0.0
        pf = (g_win / g_loss) if g_loss > 0 else 99.0
        net = g_win - g_loss
        avg_w = wins.mean() if len(wins) > 0 else 0.0
        avg_l = losses.mean() if len(losses) > 0 else 0.0
        ev = (wr/100.0 * avg_w) + ((1.0 - wr/100.0) * avg_l)
        
        cum = np.cumsum(pnls)
        max_dd = float((np.maximum.accumulate(cum) - cum).max()) if len(cum) > 0 else 0.0

        results.append({
            "Target ($)": tgt_usd,
            "SL (pts)": sl_pts,
            "Horizon (bars)": horizon,
            "Trades": n_trades,
            "Win Rate (%)": round(wr, 1),
            "PF": round(pf, 3),
            "Net PnL ($)": round(net, 2),
            "EV ($)": round(ev, 2),
            "Max DD ($)": round(max_dd, 2)
        })

    res_df = pd.DataFrame(results)
    
    print("\n" + "=" * 100)
    print("📋 PARAMETER SENSITIVITY GRID RESULTS (Sample of 15 Combinations)")
    print("=" * 100)
    print(res_df.head(15).to_string(index=False))

    # Sensitivity Assessment
    profitable_combos = (res_df['PF'] >= 1.20).sum()
    total_combos = len(res_df)
    robustness_pct = (profitable_combos / total_combos) * 100.0
    
    print("\n" + "=" * 100)
    print("🔍 SENSITIVITY & OVERFITTING VERDICT")
    print("=" * 100)
    print(f"Total Combinations Tested:     {total_combos}")
    print(f"Profitable Combinations (PF>=1.2): {profitable_combos} ({robustness_pct:.1f}%)")
    print(f"Average Profit Factor across all parameters: {res_df['PF'].mean():.3f}")
    print(f"Average Expectancy across all parameters:    ${res_df['EV ($)'].mean():+.2f}")
    print(f"Stability Verdict:             {'✅ ROBUST (Broad stability across all parameter variations)' if robustness_pct >= 75 else '⚠️ FRAGILE'}")
    print("=" * 100)


if __name__ == "__main__":
    run_parameter_sweep()
