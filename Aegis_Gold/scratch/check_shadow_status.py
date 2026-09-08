"""
Script to analyze Aegis Gold shadow-mode data readiness post-fix.
"""
import sqlite3
import os
import json
import csv
import time
from datetime import datetime, timezone

fix_cutoff_ts = 1785425876.0  # 2026-07-30T15:37:56 UTC
fix_cutoff_iso = '2026-07-30T15:37:56'

db_dir = r'd:\Trading\Aegis_Gold\data'

print(f"Fix Cutoff Timestamp: {fix_cutoff_iso} UTC (Epoch: {fix_cutoff_ts})")

print("\n=======================================================")
print("1. EXPLANATIONS DB (explanations.db)")
print("=======================================================")
exp_db = os.path.join(db_dir, 'explanations.db')
if os.path.exists(exp_db):
    conn = sqlite3.connect(exp_db)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables:", tables)
    for t in tables:
        total = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"Table '{t}' total records: {total}")
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info('{t}')").fetchall()]
        print(f"  Columns: {cols}")
        
        # Check timestamps
        ts_col = 'timestamp' if 'timestamp' in cols else ('created_at' if 'created_at' in cols else None)
        if ts_col:
            # Check latest timestamp
            latest = cur.execute(f"SELECT max({ts_col}) FROM {t}").fetchone()[0]
            print(f"  Latest timestamp: {latest}")
            
            # Query post-fix records
            post_fix = cur.execute(f"SELECT count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ?", (fix_cutoff_ts, fix_cutoff_iso)).fetchone()[0]
            print(f"  Post-fix count ({ts_col} >= {fix_cutoff_iso}): {post_fix}")
            
            if 'action' in cols:
                act_breakdown = cur.execute(f"SELECT action, count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ? GROUP BY action", (fix_cutoff_ts, fix_cutoff_iso)).fetchall()
                print(f"  Post-fix action breakdown: {act_breakdown}")
                
            if 'direction' in cols:
                dir_breakdown = cur.execute(f"SELECT direction, count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ? GROUP BY direction", (fix_cutoff_ts, fix_cutoff_iso)).fetchall()
                print(f"  Post-fix direction breakdown: {dir_breakdown}")
    conn.close()

print("\n=======================================================")
print("2. DECISION RECORDS DB (decision_records.db)")
print("=======================================================")
dec_db = os.path.join(db_dir, 'decision_records.db')
if os.path.exists(dec_db):
    conn = sqlite3.connect(dec_db)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables:", tables)
    for t in tables:
        total = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"Table '{t}' total records: {total}")
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info('{t}')").fetchall()]
        print(f"  Columns: {cols}")
        ts_col = 'timestamp' if 'timestamp' in cols else ('created_at' if 'created_at' in cols else None)
        if ts_col:
            latest = cur.execute(f"SELECT max({ts_col}) FROM {t}").fetchone()[0]
            print(f"  Latest timestamp: {latest}")
            post_fix = cur.execute(f"SELECT count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ?", (fix_cutoff_ts, fix_cutoff_iso)).fetchone()[0]
            print(f"  Post-fix count: {post_fix}")
            if 'action' in cols or 'decision' in cols:
                ac_col = 'action' if 'action' in cols else 'decision'
                print(f"  Post-fix action breakdown: {cur.execute(f'SELECT {ac_col}, count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ? GROUP BY {ac_col}', (fix_cutoff_ts, fix_cutoff_iso)).fetchall()}")
            if 'direction' in cols:
                print(f"  Post-fix direction breakdown: {cur.execute(f'SELECT direction, count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ? GROUP BY direction', (fix_cutoff_ts, fix_cutoff_iso)).fetchall()}")
    conn.close()

print("\n=======================================================")
print("3. SHADOW VALIDATION DB (shadow_validation.db)")
print("=======================================================")
sv_db = os.path.join(db_dir, 'shadow_validation.db')
if os.path.exists(sv_db):
    conn = sqlite3.connect(sv_db)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables:", tables)
    for t in tables:
        total = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"Table '{t}' total records: {total}")
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info('{t}')").fetchall()]
        print(f"  Columns: {cols}")
        ts_col = 'timestamp' if 'timestamp' in cols else ('created_at' if 'created_at' in cols else None)
        if ts_col:
            latest = cur.execute(f"SELECT max({ts_col}) FROM {t}").fetchone()[0]
            print(f"  Latest timestamp: {latest}")
            post_fix = cur.execute(f"SELECT count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ?", (fix_cutoff_ts, fix_cutoff_iso)).fetchone()[0]
            print(f"  Post-fix count: {post_fix}")
    conn.close()

print("\n=======================================================")
print("4. TRADE MEMORY DB (trade_memory.db)")
print("=======================================================")
tm_db = os.path.join(db_dir, 'trade_memory.db')
if os.path.exists(tm_db):
    conn = sqlite3.connect(tm_db)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables:", tables)
    for t in tables:
        total = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"Table '{t}' total records: {total}")
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info('{t}')").fetchall()]
        print(f"  Columns: {cols}")
        ts_col = 'timestamp' if 'timestamp' in cols else ('created_at' if 'created_at' in cols else ('entry_time' if 'entry_time' in cols else None))
        if ts_col:
            latest = cur.execute(f"SELECT max({ts_col}) FROM {t}").fetchone()[0]
            print(f"  Latest timestamp: {latest}")
            post_fix = cur.execute(f"SELECT count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ?", (fix_cutoff_ts, fix_cutoff_iso)).fetchone()[0]
            print(f"  Post-fix count: {post_fix}")
            if 'direction' in cols:
                print(f"  Post-fix direction breakdown: {cur.execute(f'SELECT direction, count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ? GROUP BY direction', (fix_cutoff_ts, fix_cutoff_iso)).fetchall()}")
    conn.close()

print("\n=======================================================")
print("5. PERFORMANCE DB (performance.db)")
print("=======================================================")
p_db = os.path.join(db_dir, 'performance.db')
if os.path.exists(p_db):
    conn = sqlite3.connect(p_db)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables:", tables)
    for t in tables:
        total = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"Table '{t}' total records: {total}")
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info('{t}')").fetchall()]
        print(f"  Columns: {cols}")
        ts_col = 'timestamp' if 'timestamp' in cols else ('close_time' if 'close_time' in cols else ('created_at' if 'created_at' in cols else None))
        if ts_col:
            latest = cur.execute(f"SELECT max({ts_col}) FROM {t}").fetchone()[0]
            print(f"  Latest timestamp: {latest}")
            post_fix = cur.execute(f"SELECT count(*) FROM {t} WHERE {ts_col} >= ? OR {ts_col} >= ?", (fix_cutoff_ts, fix_cutoff_iso)).fetchone()[0]
            print(f"  Post-fix count: {post_fix}")
    conn.close()

print("\n=======================================================")
print("6. JOURNALS (journal.csv & demo_journal.csv)")
print("=======================================================")
for j_name in ['journal.csv', 'demo_journal.csv']:
    j_path = os.path.join(db_dir, j_name)
    if os.path.exists(j_path):
        with open(j_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            print(f"{j_name} total rows: {len(rows)}")
            if rows:
                print(f"  Keys: {list(rows[0].keys())}")
                # check post fix rows
                post_fix_rows = []
                for r in rows:
                    t_str = r.get('timestamp') or r.get('open_time') or r.get('time') or ''
                    # Try parsing t_str
                    try:
                        # Check format
                        if t_str >= fix_cutoff_iso or (t_str.replace(' ', 'T') >= fix_cutoff_iso):
                            post_fix_rows.append(r)
                    except Exception:
                        pass
                print(f"  Post-fix rows count: {len(post_fix_rows)}")
                if post_fix_rows:
                    dirs = [r.get('direction') or r.get('type') for r in post_fix_rows]
                    from collections import Counter
                    print(f"  Post-fix direction counts: {Counter(dirs)}")

print("\n=======================================================")
print("7. BRAIN LOG (brain_log.csv)")
print("=======================================================")
bl_path = os.path.join(db_dir, 'brain_log.csv')
if os.path.exists(bl_path):
    # read last 2000 lines or search post-fix
    with open(bl_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        print(f"brain_log.csv total lines: {len(lines)}")
        if len(lines) > 1:
            header = lines[0]
            print("  Header:", header.strip())
            # check last 100 lines for timestamps
            last_lines = lines[-100:]
            print("  Sample last timestamp line:", last_lines[-1].strip()[:50])

