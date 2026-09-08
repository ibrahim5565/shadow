"""
Comprehensive analysis of post-fix shadow data readiness for Aegis Gold AI training.
Fix timestamp: 2026-07-30T15:37:56+00:00 (Epoch: 1785425876)
"""
import sqlite3
import os
import csv
import json
from datetime import datetime, timezone

fix_iso_str = "2026-07-30T15:37:56"
fix_epoch = 1785425876.0

db_dir = r"d:\Trading\Aegis_Gold\data"

print("======================================================================")
print(f"AEGIS GOLD SHADOW DATA READINESS AUDIT POST-FIX ({fix_iso_str} UTC)")
print("======================================================================\n")

# --- 1. DECISION RECORDS ---
dec_db = os.path.join(db_dir, "decision_records.db")
post_decisions = []
if os.path.exists(dec_db):
    conn = sqlite3.connect(dec_db)
    cur = conn.cursor()
    rows = cur.execute("SELECT id, timestamp, action, direction, confidence FROM decision_records").fetchall()
    conn.close()
    
    for r in rows:
        ts_str = str(r[1])
        if ts_str >= fix_iso_str:
            post_decisions.append({
                "id": r[0], "timestamp": r[1], "action": r[2], "direction": r[3], "confidence": r[4]
            })

print(f"[1. DECISION RECORDS]")
print(f"Total post-fix decisions recorded: {len(post_decisions)}")

actions = {}
directions = {}
for d in post_decisions:
    act = d["action"]
    actions[act] = actions.get(act, 0) + 1
    dirn = d["direction"]
    directions[dirn] = directions.get(dirn, 0) + 1

print(f"  Actions Breakdown: {actions}")
print(f"  Directions Breakdown: {directions}")

total_dec = len(post_decisions)
hold_count = actions.get("WAIT", 0) + directions.get("NA", 0)
buy_count = directions.get("BUY", 0)
sell_count = directions.get("SELL", 0)

if total_dec > 0:
    hold_pct = (actions.get("WAIT", 0) / total_dec) * 100
    buy_pct = (buy_count / total_dec) * 100
    sell_pct = (sell_count / total_dec) * 100
    print(f"  Hold/Wait Rate: {hold_pct:.2f}% ({actions.get('WAIT', 0)} / {total_dec})")
    print(f"  Buy Rate: {buy_pct:.2f}% ({buy_count} / {total_dec})")
    print(f"  Sell Rate: {sell_pct:.2f}% ({sell_count} / {total_dec})")
else:
    print("  No decisions recorded post-fix.")

# --- 2. EXPLANATIONS DB ---
exp_db = os.path.join(db_dir, "explanations.db")
post_explanations = []
if os.path.exists(exp_db):
    conn = sqlite3.connect(exp_db)
    cur = conn.cursor()
    rows = cur.execute("SELECT id, timestamp, action, direction, confidence, outcome_pnl FROM explanations").fetchall()
    conn.close()
    
    for r in rows:
        ts_str = str(r[1])
        if ts_str >= fix_iso_str:
            post_explanations.append({
                "id": r[0], "timestamp": r[1], "action": r[2], "direction": r[3], "confidence": r[4], "pnl": r[5]
            })

print(f"\n[2. EXPLANATIONS DB]")
print(f"Total post-fix explanations recorded: {len(post_explanations)}")

exp_actions = {}
exp_directions = {}
for e in post_explanations:
    act = e["action"]
    exp_actions[act] = exp_actions.get(act, 0) + 1
    dirn = e["direction"]
    exp_directions[dirn] = exp_directions.get(dirn, 0) + 1

print(f"  Explanations Actions: {exp_actions}")
print(f"  Explanations Directions: {exp_directions}")

# --- 3. PERFORMANCE / SHADOW TRADES & REALIZED R:R ---
perf_db = os.path.join(db_dir, "performance.db")
post_trades = []
if os.path.exists(perf_db):
    conn = sqlite3.connect(perf_db)
    cur = conn.cursor()
    cols = [c[1] for c in cur.execute("PRAGMA table_info('trades')").fetchall()]
    rows = cur.execute("SELECT * FROM trades").fetchall()
    conn.close()
    
    ts_idx = cols.index("timestamp") if "timestamp" in cols else -1
    for r in rows:
        t_str = str(r[ts_idx]) if ts_idx >= 0 else ""
        if t_str >= fix_iso_str:
            post_trades.append(dict(zip(cols, r)))

print(f"\n[3. CLOSED TRADES & REALIZED R:R INTEGRITY]")
print(f"Total post-fix closed trades: {len(post_trades)}")

if post_trades:
    wins = [t for t in post_trades if float(t.get("profit_usd", 0) or 0) > 0]
    losses = [t for t in post_trades if float(t.get("profit_usd", 0) or 0) < 0]
    avg_win = (sum(float(t["profit_usd"]) for t in wins) / len(wins)) if wins else 0.0
    avg_loss = (abs(sum(float(t["profit_usd"]) for t in losses)) / len(losses)) if losses else 0.0
    rr_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0
    print(f"  Post-fix Wins: {len(wins)}, Losses: {len(losses)}")
    print(f"  Avg Win: ${avg_win:.2f}, Avg Loss: ${avg_loss:.2f}")
    print(f"  Realized R:R Ratio: {rr_ratio:.2f}")
else:
    print("  No closed shadow/live trades recorded strictly post-fix timestamp.")

# Also check trade_memory.db
tm_db = os.path.join(db_dir, "trade_memory.db")
post_tm_trades = []
if os.path.exists(tm_db):
    conn = sqlite3.connect(tm_db)
    cur = conn.cursor()
    cols = [c[1] for c in cur.execute("PRAGMA table_info('trades')").fetchall()]
    rows = cur.execute("SELECT * FROM trades").fetchall()
    conn.close()
    ts_idx = cols.index("entry_time") if "entry_time" in cols else -1
    for r in rows:
        t_str = str(r[ts_idx]) if ts_idx >= 0 else ""
        if t_str >= fix_iso_str:
            post_tm_trades.append(dict(zip(cols, r)))

print(f"\nTrade Memory post-fix trades count: {len(post_tm_trades)}")

# --- 4. BRAIN LOG (brain_log.csv) ---
bl_path = os.path.join(db_dir, "brain_log.csv")
post_bl_rows = []
if os.path.exists(bl_path):
    with open(bl_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for r in reader:
            ts = r.get("timestamp", "")
            if ts >= fix_iso_str:
                post_bl_rows.append(r)

print(f"\n[4. BRAIN LOG (brain_log.csv)]")
print(f"Post-fix brain_log entries count: {len(post_bl_rows)}")

bl_actions = {}
bl_directions = {}
for r in post_bl_rows:
    act = r.get("action", "")
    bl_actions[act] = bl_actions.get(act, 0) + 1
    dirn = r.get("direction", "")
    bl_directions[dirn] = bl_directions.get(dirn, 0) + 1

print(f"  Brain log actions post-fix: {bl_actions}")
print(f"  Brain log directions post-fix: {bl_directions}")

