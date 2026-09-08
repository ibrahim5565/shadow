import sqlite3
import os
from datetime import datetime

EXPLAIN_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "explanations.db"))
PERF_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "performance.db"))

conn_exp = sqlite3.connect(EXPLAIN_DB)
cursor_exp = conn_exp.cursor()
cursor_exp.execute("SELECT id, timestamp, symbol, direction, confidence FROM explanations WHERE action='TRADE' ORDER BY id DESC;")
explanations = cursor_exp.fetchall()
conn_exp.close()

conn_perf = sqlite3.connect(PERF_DB)
cursor_perf = conn_perf.cursor()
cursor_perf.execute("SELECT id, timestamp, symbol, direction, win_loss, profit_usd FROM trades WHERE win_loss IS NOT NULL ORDER BY id DESC;")
perf_trades = cursor_perf.fetchall()
conn_perf.close()

print(f"Loaded {len(explanations)} explanations of type TRADE.")
print(f"Loaded {len(perf_trades)} trades with win/loss outcomes.")

# For each trade, find the closest preceding explanation
matches = []
for p_id, p_ts, p_sym, p_dir, p_win_loss, p_profit in perf_trades:
    try:
        p_dt = datetime.fromisoformat(p_ts.replace("Z", "+00:00"))
    except Exception:
        continue
        
    best_match = None
    min_diff = 999999.0
    
    for exp_id, exp_ts, exp_sym, exp_dir, exp_conf in explanations:
        if exp_sym == p_sym and exp_dir == p_dir:
            try:
                exp_dt = datetime.fromisoformat(exp_ts.replace("Z", "+00:00"))
                # Explanation must be created BEFORE or very close to order open
                diff = (p_dt - exp_dt).total_seconds()
                if 0 <= diff < 5:  # Explanation created within 5 seconds before trade open
                    if diff < min_diff:
                        min_diff = diff
                        best_match = (exp_id, p_id, p_sym, p_dir, p_win_loss, p_profit, diff)
            except Exception:
                continue
                
    if best_match:
        matches.append(best_match)

print(f"Successfully matched: {len(matches)} executed trades with explanations!")
if matches:
    print(f"Sample match: {matches[0]}")
