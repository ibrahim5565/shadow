"""
EXIT LOGIC REPLAY v3 -- Corrected Methodology
==============================================
Data integrity fixes applied:

BLOCKER A: performance.db is the ONLY authoritative source.
  - 2,772 closed trades (XAUUSD + EURUSD)
  - Updated to 2026-07-24 (trade_memory.db is stale at 2026-07-08)
  - All metrics use performance.db exclusively

BLOCKER B: exit_reason='SL' != broker SL hit.
  Trade categories in performance.db:
    True TP exit  : profit_usd > 0  (no exit_reason in perf.db -- use win_loss=1)
    True broker SL: profit_usd < 0 AND sl > 0 (sl column stores broker SL price;
                    sl > 0 means a real stop order was placed at MT5)
    Force-close   : profit_usd < 0 AND sl = 0 (no SL order at MT5 -- mass-close
                    by recovery daemon / kill switch / manual close)

Force-closes are EXCLUDED from new-SL simulation.
  Rationale: a new per-trade SL would not prevent a force-close (which fires at
  account-equity level). Including them in the SL-cap simulation would give them
  artificially better (capped) losses, inflating PF.

Conservative MAE methodology (unchanged from v2):
  For TP exits: assumed MAE = profit_pips * MAE_FACTOR (0.3)
  If assumed MAE > sim_sl: reclassified as stop-out (conservative)
  Else: win at min(profit_pips, sim_tp)
"""

import sqlite3
import os
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = r"d:\Trading\Aegis_Gold"
PERF_DB  = os.path.join(BASE_DIR, "data", "performance.db")

# ── Simulation parameters ─────────────────────────────────────────────────────
XAUUSD_SL_NORMAL   = 60    # pts -- ATR-normal SL (exit_engine.py v2.0)
XAUUSD_TP_NORMAL   = 72    # pts -- normal TP (R:R = 1.2)
XAUUSD_SL_FLOOR    = 50    # pts -- hard minimum
XAUUSD_RR          = round(XAUUSD_TP_NORMAL / XAUUSD_SL_NORMAL, 2)
MAE_FACTOR         = 0.3   # assumed adverse excursion = 30% of gain (conservative)
SPREAD_TYPICAL_PTS = 25    # XAUUSD normal spread (pts)
SPREAD_NEWS_PTS    = 120   # XAUUSD news-time spread (pts)
PIP_VAL            = 0.01  # USD per pip per 0.01 lot (confirmed)

print("=" * 70)
print("AEGIS GOLD -- EXIT LOGIC REPLAY REPORT v3 (Corrected)")
print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("Authoritative source: performance.db only")
print("Force-close trades: EXCLUDED from new-SL simulation")
print("=" * 70)

# ── Load from performance.db ONLY ────────────────────────────────────────────
conn = sqlite3.connect(PERF_DB)
df_all = pd.read_sql_query(
    "SELECT id, symbol, direction, entry_price, exit_price, sl, tp, lot, "
    "profit_usd, profit_pips, win_loss, session, timestamp "
    "FROM trades "
    "WHERE profit_usd IS NOT NULL AND profit_usd != 0 "
    "ORDER BY timestamp",
    conn
)
conn.close()

# XAUUSD only
xau = df_all[df_all["symbol"].str.contains("XAU", na=False)].copy()

# ── Classify each trade ───────────────────────────────────────────────────────
def classify_trade(row):
    """
    Three categories using performance.db sl column (broker SL price):
      TRUE_TP        : profit_usd > 0  (won regardless of how it closed)
      BROKER_SL      : profit_usd < 0 AND sl > 0  (real stop order existed at MT5)
      FORCE_CLOSE    : profit_usd < 0 AND sl <= 0 (no stop order -- force/mass close)
    """
    if row["profit_usd"] > 0:
        return "TRUE_TP"
    elif row["sl"] > 0:
        return "BROKER_SL"
    else:
        return "FORCE_CLOSE"

xau["trade_type"] = xau.apply(classify_trade, axis=1)

tc = xau["trade_type"].value_counts()

print(f"\n  XAUUSD trades: {len(xau)}")
print(f"  TRUE_TP      : {tc.get('TRUE_TP', 0)} ({tc.get('TRUE_TP', 0)/len(xau)*100:.1f}%)")
print(f"  BROKER_SL    : {tc.get('BROKER_SL', 0)} ({tc.get('BROKER_SL', 0)/len(xau)*100:.1f}%)")
print(f"  FORCE_CLOSE  : {tc.get('FORCE_CLOSE', 0)} ({tc.get('FORCE_CLOSE', 0)/len(xau)*100:.1f}%) -- EXCLUDED from sim")

# ── BASELINE metrics ──────────────────────────────────────────────────────────
# True baseline: ALL trades as-is (the actual live PnL)
xau_tp   = xau[xau["trade_type"] == "TRUE_TP"]
xau_sl   = xau[xau["trade_type"] == "BROKER_SL"]
xau_fc   = xau[xau["trade_type"] == "FORCE_CLOSE"]

base_gp  = xau_tp["profit_usd"].sum()
base_gl  = abs(xau_sl["profit_usd"].sum()) + abs(xau_fc["profit_usd"].sum())
base_pf  = base_gp / base_gl if base_gl > 0 else 0.0
base_wr  = len(xau_tp) / len(xau) * 100
base_awp = xau_tp["profit_pips"].mean()
base_alp_sl = abs(xau_sl["profit_pips"].mean()) if len(xau_sl) > 0 else 0
base_alp_fc = abs(xau_fc["profit_pips"].mean()) if len(xau_fc) > 0 else 0

print()
print("=" * 70)
print("  SECTION 1: BASELINE (performance.db, all XAUUSD, no SL)")
print("=" * 70)
print(f"  Total trades      : {len(xau)}")
print(f"  Wins (TRUE_TP)    : {len(xau_tp)}")
print(f"  Losses (BROKER_SL): {len(xau_sl)} -- avg loss pips: {base_alp_sl:.1f}")
print(f"  Force-close       : {len(xau_fc)} -- avg loss pips: {base_alp_fc:.1f}")
print(f"  WIN RATE          : {base_wr:.2f}%")
print(f"  PROFIT FACTOR     : {base_pf:.3f}")
print(f"  Avg win pips      : +{base_awp:.1f}")
print(f"  Gross profit      : ${base_gp:.2f}")
print(f"  Gross loss        : ${base_gl:.2f}  (broker SL: ${abs(xau_sl['profit_usd'].sum()):.2f} + force: ${abs(xau_fc['profit_usd'].sum()):.2f})")
print(f"  NET PNL           : ${base_gp - base_gl:.2f}")

# ── SIMULATION on eligible trades ─────────────────────────────────────────────
# Eligible = TRUE_TP + BROKER_SL (force-closes excluded, kept at original loss)
eligible = xau[xau["trade_type"].isin(["TRUE_TP", "BROKER_SL"])].copy()
force_closes = xau[xau["trade_type"] == "FORCE_CLOSE"].copy()

print()
print("=" * 70)
print(f"  SECTION 2: SIMULATED -- SL={XAUUSD_SL_NORMAL}pts TP={XAUUSD_TP_NORMAL}pts R:R={XAUUSD_RR}")
print(f"  Eligible: {len(eligible)} trades (TP+BrokerSL) | Excluded (force-close): {len(force_closes)}")
print(f"  MAE factor: {MAE_FACTOR} | Spread: 0 pts (already in execution)")
print("=" * 70)

def simulate_trade(row, sim_sl, sim_tp, mae_factor):
    """
    True TP trade:
      assumed_mae = profit_pips * mae_factor
      If assumed_mae > sim_sl  -> stop-out at sim_sl (conservative)
      Else                     -> win at min(profit_pips, sim_tp)

    True broker SL trade:
      Original loss was |profit_pips| at original (likely tiny) SL or no SL.
      With new SL: loss = min(|orig_pips|, sim_sl) -- cap, never worsen.
    """
    orig_pips   = float(row["profit_pips"]) if pd.notna(row["profit_pips"]) else 0.0
    lot         = float(row["lot"]) if pd.notna(row["lot"]) and row["lot"] > 0 else 0.01
    pip_val     = PIP_VAL * (lot / 0.01)
    trade_type  = row["trade_type"]

    if trade_type == "TRUE_TP":
        assumed_mae = abs(orig_pips) * mae_factor
        if assumed_mae > sim_sl:
            sim_pips = -sim_sl
            outcome  = "STOP_OUT"
        else:
            sim_pips = min(abs(orig_pips), sim_tp)
            outcome  = "WIN"
    else:  # BROKER_SL
        if abs(orig_pips) <= sim_sl:
            sim_pips = orig_pips  # keep original (already within new SL)
        else:
            sim_pips = -sim_sl    # cap at new SL
        outcome = "LOSS_CAPPED"

    sim_usd = sim_pips * pip_val
    return sim_pips, sim_usd, outcome

sim_rows = []
for _, row in eligible.iterrows():
    sp, su, tag = simulate_trade(row, XAUUSD_SL_NORMAL, XAUUSD_TP_NORMAL, MAE_FACTOR)
    sim_rows.append({"sim_pips": sp, "sim_usd": su, "outcome": tag, "orig_pips": row["profit_pips"]})

sim_df = pd.DataFrame(sim_rows)
sw = sim_df[sim_df["sim_usd"] > 0]
sl_sim = sim_df[sim_df["sim_usd"] < 0]

sim_gp  = sw["sim_usd"].sum()
sim_gl  = abs(sl_sim["sim_usd"].sum())

# Add back force-close losses unchanged
fc_gl   = abs(force_closes["profit_usd"].sum())
total_gl = sim_gl + fc_gl

sim_pf_excl_fc = sim_gp / sim_gl if sim_gl > 0 else float("inf")   # eligible only
sim_pf_incl_fc = sim_gp / total_gl if total_gl > 0 else float("inf") # all XAUUSD

sim_wr  = len(sw) / len(eligible) * 100
sim_awp = sw["sim_pips"].mean() if len(sw) > 0 else 0
sim_alp = abs(sl_sim["sim_pips"].mean()) if len(sl_sim) > 0 else 0
sim_awu = sw["sim_usd"].mean() if len(sw) > 0 else 0
sim_alu = abs(sl_sim["sim_usd"].mean()) if len(sl_sim) > 0 else 0

print(f"\n  Outcome (eligible): {sim_df['outcome'].value_counts().to_dict()}")
print()
print(f"  WIN RATE (eligible)     : {sim_wr:.2f}%  (was: {base_wr:.2f}%)")
print(f"  PF (eligible trades)    : {sim_pf_excl_fc:.3f}  (was: {base_pf:.3f})")
print(f"  PF (incl. force-closes) : {sim_pf_incl_fc:.3f}")
print(f"  Avg win pips            : +{sim_awp:.1f}  (was: +{base_awp:.1f})")
print(f"  Avg loss pips           : -{sim_alp:.1f}  (vs orig broker-SL: {base_alp_sl:.1f})")
print(f"  Avg win USD             : +${sim_awu:.4f}")
print(f"  Avg loss USD            : -${sim_alu:.4f}")
print(f"  Gross profit (eligible) : ${sim_gp:.2f}")
print(f"  Gross loss (eligible)   : ${sim_gl:.2f}")
print(f"  Force-close losses kept : ${fc_gl:.2f}")
print(f"  TOTAL gross loss        : ${total_gl:.2f}")
print(f"  NET PNL (eligible sim)  : ${sim_gp - sim_gl:.2f}")
print(f"  NET PNL (all XAUUSD)    : ${sim_gp - total_gl:.2f}")

print()
print("=" * 70)
print("  SECTION 3: SPREAD vs. SL FLOOR")
print("=" * 70)
spread_pct_normal = SPREAD_TYPICAL_PTS / XAUUSD_SL_FLOOR * 100
spread_pct_news   = SPREAD_NEWS_PTS / XAUUSD_SL_FLOOR * 100
print(f"  SL floor: {XAUUSD_SL_FLOOR} pts | Typical spread: {SPREAD_TYPICAL_PTS} pts -> {spread_pct_normal:.1f}% of floor")
print(f"  News spread: {SPREAD_NEWS_PTS} pts -> {spread_pct_news:.1f}% of floor")
if spread_pct_normal > 40:
    print(f"  WARNING: spread {spread_pct_normal:.0f}% of floor is HIGH -- spread-stop risk at low-vol sessions")
if spread_pct_news >= 100:
    print(f"  WARNING: news spread EXCEEDS floor -- no trades at news events")

print()
print("=" * 70)
print("  SECTION 4: PRE-TRAINING GATE")
print("=" * 70)
gate_e = sim_pf_excl_fc > 1.0
gate_f = sim_pf_incl_fc > 1.0
print(f"\n  PF (eligible trades only) : {sim_pf_excl_fc:.3f}  -> {'PASS' if gate_e else 'FAIL'}")
print(f"  PF (all XAUUSD incl FC)   : {sim_pf_incl_fc:.3f}  -> {'PASS' if gate_f else 'FAIL'}")
print()
if gate_e and gate_f:
    print("  Both gates PASSED. Proceed to Task 2.")
elif gate_e:
    print("  Eligible-only gate PASSED. Force-close losses drag overall PF below 1.0.")
    print("  A force-close reduction mechanism (better equity protection) is needed alongside the SL fix.")
else:
    print("  GATE FAILED. Re-evaluate SL/TP parameters.")

print()
print("=" * 70)
print("  SECTION 5: SENSITIVITY ANALYSIS (MAE factor, eligible trades only)")
print("=" * 70)
print(f"\n  {'MAE':>6} {'WR%':>8} {'PF_elig':>10} {'PF_all':>10} {'Net_elig':>12} {'Gate':>6}")
print(f"  {'-'*6} {'-'*8} {'-'*10} {'-'*10} {'-'*12} {'-'*6}")
for mf in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]:
    rows = []
    for _, row in eligible.iterrows():
        sp, su, tag = simulate_trade(row, XAUUSD_SL_NORMAL, XAUUSD_TP_NORMAL, mf)
        rows.append({"sim_usd": su})
    t = pd.DataFrame(rows)
    tw = t[t["sim_usd"] > 0]
    tl = t[t["sim_usd"] < 0]
    tgp = tw["sim_usd"].sum()
    tgl = abs(tl["sim_usd"].sum())
    tpf_e = tgp / tgl if tgl > 0 else float("inf")
    tpf_a = tgp / (tgl + fc_gl) if (tgl + fc_gl) > 0 else float("inf")
    twr = len(tw) / len(t) * 100
    tnet = tgp - tgl
    flag = "[X]" if mf == MAE_FACTOR else ""
    g = "PASS" if tpf_e > 1.0 else "FAIL"
    print(f"  {mf:>6.1f} {twr:>7.1f}% {tpf_e:>10.3f} {tpf_a:>10.3f} ${tnet:>11.2f} {g:>6} {flag}")

print()
print("=" * 70)
print("  SECTION 6: SL FLOOR SENSITIVITY (MAE=0.3, eligible only)")
print("=" * 70)
print(f"\n  {'SL':>6} {'TP':>6} {'R:R':>5} {'WR%':>8} {'PF_elig':>10} {'PF_all':>10} {'Net_elig':>12}")
print(f"  {'-'*6} {'-'*6} {'-'*5} {'-'*8} {'-'*10} {'-'*10} {'-'*12}")
for test_sl in [30, 40, 50, 60, 80, 100, 120]:
    test_tp = int(test_sl * 1.2)
    rows = []
    for _, row in eligible.iterrows():
        sp, su, tag = simulate_trade(row, test_sl, test_tp, MAE_FACTOR)
        rows.append({"sim_usd": su})
    t = pd.DataFrame(rows)
    tw = t[t["sim_usd"] > 0]
    tl = t[t["sim_usd"] < 0]
    tgp = tw["sim_usd"].sum()
    tgl = abs(tl["sim_usd"].sum())
    tpf_e = tgp / tgl if tgl > 0 else float("inf")
    tpf_a = tgp / (tgl + fc_gl) if (tgl + fc_gl) > 0 else float("inf")
    twr = len(tw) / len(t) * 100
    tnet = tgp - tgl
    test_rr = round(test_tp / test_sl, 2)
    flag = " <-floor" if test_sl == XAUUSD_SL_FLOOR else ""
    g = "PASS" if tpf_e > 1.0 else "FAIL"
    print(f"  {test_sl:>6} {test_tp:>6} {test_rr:>5.2f} {twr:>7.1f}% {tpf_e:>10.3f} {tpf_a:>10.3f} ${tnet:>11.2f} {g}{flag}")
