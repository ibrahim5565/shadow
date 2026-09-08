"""
BLOCKER B: Investigate exit_reason='SL' vs sl_points>0 gap
===========================================================
1. All code paths that can produce exit_reason='SL'
2. Gap trades: SL-labeled exits with sl_points=0
3. Sample + MT5 comment field analysis
4. Corrected breakdown
"""
import sqlite3
import os
import pandas as pd

BASE_DIR = r"d:\Trading\Aegis_Gold\data"
TM_DB    = os.path.join(BASE_DIR, "trade_memory.db")

print("=" * 70)
print("BLOCKER B: exit_reason='SL' vs sl_points>0 gap")
print("=" * 70)

conn = sqlite3.connect(TM_DB)

# ── 1. Full exit_reason breakdown ────────────────────────────────────────────
print("\n--- 1. Full exit_reason breakdown ---")
df_all = pd.read_sql_query(
    "SELECT exit_reason, sl_points, profit_usd, signal_source, "
    "entry_time, exit_time, duration_seconds, notes "
    "FROM trades WHERE profit_usd IS NOT NULL AND profit_usd != 0",
    conn
)

print(f"\nTotal closed trades: {len(df_all)}")
print("\nexit_reason counts:")
print(df_all['exit_reason'].value_counts(dropna=False).to_string())

# ── 2. Identify the gap ───────────────────────────────────────────────────────
print("\n--- 2. SL-labeled exits with sl_points=0 (the gap) ---")
sl_exits  = df_all[df_all['exit_reason'].str.upper() == 'SL']
sl_with_sl_pts    = sl_exits[sl_exits['sl_points'] > 0]
sl_without_sl_pts = sl_exits[(sl_exits['sl_points'].isna()) | (sl_exits['sl_points'] <= 0)]

print(f"\nAll exit_reason='SL' trades    : {len(sl_exits)}")
print(f"  With sl_points > 0 (clean)   : {len(sl_with_sl_pts)}")
print(f"  With sl_points = 0/null (gap): {len(sl_without_sl_pts)}")
print(f"\nGap trades summary:")
print(f"  PnL: min={sl_without_sl_pts['profit_usd'].min():.4f}  max={sl_without_sl_pts['profit_usd'].max():.4f}  mean={sl_without_sl_pts['profit_usd'].mean():.4f}")
print(f"  signal_source breakdown:")
print(sl_without_sl_pts['signal_source'].value_counts(dropna=False).to_string())

# ── 3. Duration analysis (manual closes tend to be longer) ───────────────────
print("\n--- 3. Duration comparison ---")
print(f"  Gap trades (sl=0)  avg duration_sec: {sl_without_sl_pts['duration_seconds'].mean():.0f}")
print(f"  Clean SL trades    avg duration_sec: {sl_with_sl_pts['duration_seconds'].mean():.0f}")
clean_sl_avg_loss = sl_with_sl_pts[sl_with_sl_pts['profit_usd']<0]['profit_usd'].mean()
gap_avg_loss      = sl_without_sl_pts[sl_without_sl_pts['profit_usd']<0]['profit_usd'].mean()
print(f"  Gap trades avg loss USD    : {gap_avg_loss:.4f}")
print(f"  Clean SL trades avg loss   : {clean_sl_avg_loss:.4f}")

# ── 4. Sample of gap trades with notes/duration ───────────────────────────────
print("\n--- 4. Sample of 30 gap trades ---")
sample_gap = sl_without_sl_pts.head(30)[
    ['entry_time','exit_time','duration_seconds','profit_usd','sl_points','signal_source','notes']
].copy()
print(sample_gap.to_string())

# ── 5. Notes/tags field for exit clues ────────────────────────────────────────
print("\n--- 5. Notes field values in gap trades ---")
notes_counts = sl_without_sl_pts['notes'].value_counts(dropna=False).head(20)
print(notes_counts.to_string())

# ── 6. Check if gap trades have consistent entry_score/confidence patterns ────
print("\n--- 6. Confidence/score comparison ---")
conn_ext = sqlite3.connect(TM_DB)
df_scores = pd.read_sql_query(
    "SELECT exit_reason, sl_points, confidence, entry_score, regime_score, "
    "structure_score, was_patient, followed_rules "
    "FROM trades WHERE profit_usd IS NOT NULL AND profit_usd != 0",
    conn_ext
)
conn_ext.close()

gap_scores   = df_scores[(df_scores['exit_reason'].str.upper()=='SL') & (df_scores['sl_points']<=0)]
clean_scores = df_scores[(df_scores['exit_reason'].str.upper()=='SL') & (df_scores['sl_points']>0)]
tp_scores    = df_scores[df_scores['exit_reason'].str.upper()=='TP']

print(f"\n  Avg confidence — Gap SL: {gap_scores['confidence'].mean():.1f}  | Clean SL: {clean_scores['confidence'].mean():.1f}  | TP exits: {tp_scores['confidence'].mean():.1f}")
print(f"  Avg entry_score — Gap: {gap_scores['entry_score'].mean():.2f}  | Clean: {clean_scores['entry_score'].mean():.2f}  | TP: {tp_scores['entry_score'].mean():.2f}")

# was_patient / followed_rules
print(f"\n  was_patient=1 rate — Gap: {gap_scores['was_patient'].mean():.2%}  | Clean: {clean_scores['was_patient'].mean():.2%}")
print(f"  followed_rules=1 rate — Gap: {gap_scores['followed_rules'].mean():.2%}  | Clean: {clean_scores['followed_rules'].mean():.2%}")

# ── 7. Pull performance.db to check comment/close_reason field ────────────────
print("\n--- 7. performance.db — check for close reason field ---")
PERF_DB = os.path.join(BASE_DIR, "performance.db")
conn_p = sqlite3.connect(PERF_DB)
cur = conn_p.cursor()
cur.execute("PRAGMA table_info(trades);")
perf_cols = [r[1] for r in cur.fetchall()]
print(f"performance.db columns: {perf_cols}")

# Check if win_loss field reveals anything about the gap
df_p_sl = pd.read_sql_query(
    "SELECT id, win_loss, profit_usd, profit_pips, sl, tp, lot, timestamp "
    "FROM trades WHERE profit_usd < 0 ORDER BY profit_pips",
    conn_p
)
conn_p.close()

print(f"\nperformance.db losing trades: {len(df_p_sl)}")
print(f"  sl>0 (had a stop price set): {(df_p_sl['sl']>0).sum()}")
print(f"  sl=0 (no stop price set)   : {(df_p_sl['sl']<=0).sum()}")
print(f"\n  Win_loss field values: {df_p_sl['win_loss'].value_counts().to_dict()}")

# Sample worst losses from perf.db (these are the ones that blew up)
print(f"\n  10 worst losses in performance.db:")
worst = df_p_sl.nsmallest(10, 'profit_pips')[['id','profit_pips','profit_usd','sl','tp','lot','timestamp']]
print(worst.to_string())

conn.close()
