"""
Task 2 — CORRECTED Consensus Threshold Audit (Disjoint Selection/Validation Folds)
====================================================================================
AUDIT FINDING (pre-fix):
  The previous sweep_consensus_thresholds.py had two critical flaws:

  FLAW 1 — SYNTHETIC INPUT DATA:
    The script checked for 'confidence', 'smc_score', 'regime_score' columns but fell back to
    `np.random.uniform(50, 90, len(df))` when they were missing or all-zero. These columns
    ARE present in trade_memory.db but smc_score and regime_score are ALL ZERO for most trades.
    When all three sub-scores were present but smc/regime were zero, the fallback to random data
    fired, meaning the consensus scores used for threshold selection were RANDOM NOISE.

  FLAW 2 — NO HELD-OUT VALIDATION FOLD:
    The script computed threshold selection and threshold evaluation on THE SAME SET OF FOLDS.
    In the 5-fold walk-forward CV, every fold contributed to both (a) identifying which threshold
    scored highest and (b) reporting the "held-out" PF. A proper validation protocol must:
      - Use folds [0..N-2] for selection (inner loop)
      - Use fold [N-1] (or a dedicated outer fold never seen during selection) for validation
    Without this, any PF above 1.0 is an in-sample result, not a genuine out-of-sample validation.

THIS SCRIPT FIXES BOTH:
  1. Uses ONLY real recorded 'confidence' scores from trades (which are real INTEGER values).
     Reports how many trades have non-null confidence, their distribution, and whether
     smc_score / regime_score are actually informative (non-zero) before compositing them.
  2. Uses an outer/inner cross-validation split: folds 0..3 are used for threshold selection;
     fold 4 is the held-out validation fold that is NEVER seen during selection.
"""

import sys
from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

import sqlite3
import numpy as np
import pandas as pd
from brain.walk_forward_validator import PurgedWalkForwardCV

DATA_DIR = BASE_DIR / "data"
TRADE_MEMORY_DB = DATA_DIR / "trade_memory.db"

print("=" * 70)
print("TASK 2 — CONSENSUS THRESHOLD AUDIT (Corrected, Disjoint Folds)")
print("=" * 70)

conn = sqlite3.connect(TRADE_MEMORY_DB)
df = pd.read_sql_query(
    "SELECT trade_id, confidence, smc_score, regime_score, profit_usd "
    "FROM trades WHERE profit_usd IS NOT NULL",
    conn
)
conn.close()

df["profit_usd"] = pd.to_numeric(df["profit_usd"], errors="coerce")
df = df.dropna(subset=["profit_usd"]).reset_index(drop=True)

print(f"\nLoaded {len(df)} trades with non-null profit_usd.")

# --- Audit input data BEFORE computing anything ---
print(f"\n--- INPUT DATA AUDIT ---")
print(f"  confidence  — null: {df['confidence'].isnull().sum()} | non-zero: {(df['confidence'] > 0).sum()} | range: {df['confidence'].min()}..{df['confidence'].max()}")
print(f"  smc_score   — null: {df['smc_score'].isnull().sum()} | non-zero: {(df['smc_score'] > 0).sum()} | range: {df['smc_score'].min()}..{df['smc_score'].max()}")
print(f"  regime_score— null: {df['regime_score'].isnull().sum()} | non-zero: {(df['regime_score'] > 0).sum()} | range: {df['regime_score'].min()}..{df['regime_score'].max()}")

# Determine which scores to actually use
conf_vals = pd.to_numeric(df["confidence"], errors="coerce").fillna(0.0).values
smc_vals  = pd.to_numeric(df["smc_score"],  errors="coerce").fillna(0.0).values
reg_vals  = pd.to_numeric(df["regime_score"],errors="coerce").fillna(0.0).values

smc_informative = (smc_vals > 0).sum() > len(df) * 0.05  # >5% non-zero
reg_informative = (reg_vals > 0).sum() > len(df) * 0.05

if smc_informative and reg_informative:
    consensus_scores = (conf_vals * 0.40) + (smc_vals * 0.30) + (reg_vals * 0.30)
    score_label = "Composite (confidence*0.4 + smc*0.3 + regime*0.3)"
elif smc_informative:
    consensus_scores = (conf_vals * 0.60) + (smc_vals * 0.40)
    score_label = "Partial composite (confidence*0.6 + smc*0.4) — regime_score uninformative"
else:
    consensus_scores = conf_vals.copy()
    score_label = "confidence ONLY — smc_score and regime_score are uninformative (mostly zero)"

print(f"\n  Score used: {score_label}")
print(f"  Consensus score range: min={consensus_scores.min():.2f}, max={consensus_scores.max():.2f}, mean={consensus_scores.mean():.2f}")

pnl_array  = df["profit_usd"].values
times_array = np.arange(len(df), dtype=float)

# --- CORRECTED PROTOCOL: 5 inner folds + 1 outer held-out fold ---
# We use all 5 folds from PurgedWalkForwardCV but designate the LAST fold as held-out.
# Threshold selection happens only on folds 0..3 (inner selection).
# Fold 4 is reserved as the held-out validation fold.

cv = PurgedWalkForwardCV(n_splits=5, embargo_pct=0.05)
all_splits = list(cv.split(consensus_scores, pnl_array, times_array))

if len(all_splits) < 2:
    print("\nERROR: Not enough folds to separate selection from validation. Need >= 2 folds.")
    exit(1)

# Held-out = last fold; selection = all preceding folds
held_out_split = all_splits[-1]
selection_splits = all_splits[:-1]

thresholds = [50, 55, 60, 65, 70, 75, 80]

# --- INNER LOOP: Select threshold on folds 0..N-2 ---
print(f"\n--- INNER LOOP: Threshold selection on {len(selection_splits)} inner fold(s) ---")
selection_results = {}

for th in thresholds:
    total_gwin, total_gloss = 0.0, 0.0
    total_passed = 0
    for train_idx, test_idx in selection_splits:
        test_scores = consensus_scores[test_idx]
        test_pnl = pnl_array[test_idx]
        mask = test_scores >= th
        passed_pnl = test_pnl[mask]
        if len(passed_pnl) > 0:
            wins_s   = passed_pnl[passed_pnl > 0]
            losses_s = passed_pnl[passed_pnl < 0]
            total_gwin  += wins_s.sum()
            total_gloss += abs(losses_s.sum())
            total_passed += len(passed_pnl)
    pf_inner = total_gwin / total_gloss if total_gloss > 0 else (99.0 if total_gwin > 0 else 0.0)
    selection_results[th] = {"passed": total_passed, "pf": round(pf_inner, 3)}

print(f"  {'Threshold':<12} | {'Passed Trades':<15} | {'Inner PF':<12}")
print(f"  {'-'*45}")
for th, res in selection_results.items():
    print(f"  {th:<12}% | {res['passed']:<15} | {res['pf']:<12.3f}")

best_th = max(selection_results.keys(), key=lambda k: selection_results[k]["pf"])
print(f"\n  => Selected threshold from inner folds: {best_th}%  (inner PF={selection_results[best_th]['pf']:.3f})")

# --- OUTER VALIDATION: Evaluate selected threshold on held-out fold 4 ---
print(f"\n--- OUTER VALIDATION: Evaluating {best_th}% threshold on held-out fold 4 (NEVER SEEN DURING SELECTION) ---")
_, held_test_idx = held_out_split
held_scores = consensus_scores[held_test_idx]
held_pnl    = pnl_array[held_test_idx]

held_mask   = held_scores >= best_th
held_passed = held_pnl[held_mask]

print(f"  Held-out fold size: {len(held_test_idx)} trades")
print(f"  Trades passing {best_th}% threshold: {held_mask.sum()}")

if len(held_passed) > 0:
    held_wins   = held_passed[held_passed > 0]
    held_losses = held_passed[held_passed < 0]
    held_gwin   = held_wins.sum()
    held_gloss  = abs(held_losses.sum())
    held_pf     = held_gwin / held_gloss if held_gloss > 0 else (99.0 if held_gwin > 0 else 0.0)
    held_wr     = (len(held_wins) / len(held_passed)) * 100.0
    print(f"  Held-out Gross Win: ${held_gwin:.2f} | Held-out Gross Loss: ${held_gloss:.2f}")
    print(f"  Held-out Win Rate:  {held_wr:.1f}%")
    print(f"  HELD-OUT PROFIT FACTOR: {held_pf:.3f}")
else:
    held_pf = 0.0
    print("  No trades passed the threshold in the held-out fold.")

# --- Report all thresholds on held-out fold for transparency ---
print(f"\n--- ALL THRESHOLDS ON HELD-OUT FOLD (for transparency) ---")
print(f"  {'Threshold':<12} | {'Passed':<10} | {'Win Rate':<12} | {'Held-Out PF':<12}")
print(f"  {'-'*50}")
for th in thresholds:
    m = held_scores >= th
    p = held_pnl[m]
    if len(p) > 0:
        w = p[p > 0]; l = p[p < 0]
        pf_h = w.sum() / abs(l.sum()) if abs(l.sum()) > 0 else (99.0 if w.sum() > 0 else 0.0)
        wr_h = (len(w) / len(p)) * 100.0
    else:
        pf_h, wr_h = 0.0, 0.0
    print(f"  {th:<12}% | {m.sum():<10} | {wr_h:<12.1f}% | {pf_h:<12.3f}")

print(f"""
--- CONCLUSION ---
  PREVIOUS RESULT ("55% optimal, data-backed"): INVALID.
    - Scores were composite of real confidence + UNINFORMATIVE smc/regime (all zero).
    - Same 5 folds used for both selection and "validation" — no genuine held-out fold.
    - A PF of 0.963 reported as positive result without noting it is < 1.0.

  HONEST RESULT:
    Score input:     {score_label}
    Best threshold (inner folds): {best_th}%  (inner PF = {selection_results[best_th]['pf']:.3f})
    Held-out fold PF at {best_th}%:  {held_pf:.3f}
    
    {'CONSENSUS GATE PASSES PF > 1.0 ON HELD-OUT FOLD. Review whether margin is robust enough for live use.' if held_pf > 1.0 else 'CONSENSUS GATE DOES NOT CLEAR PF > 1.0 ON HELD-OUT FOLD. This is a negative result.'}
    {'Do NOT present consensus gating as validated — the held-out result must clear PF > 1.0 before this is considered an edge.' if held_pf <= 1.0 else ''}
""")
