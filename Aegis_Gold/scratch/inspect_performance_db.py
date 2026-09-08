import sqlite3
import os

EXPLAIN_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "explanations.db"))
PERF_DB = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "performance.db"))

print("--- EXPLANATIONS.DB OUTCOMES ---")
if os.path.exists(EXPLAIN_DB):
    conn = sqlite3.connect(EXPLAIN_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT outcome, COUNT(*) FROM explanations GROUP BY outcome;")
    print(cursor.fetchall())
    conn.close()

print("\n--- PERFORMANCE.DB OUTCOMES ---")
if os.path.exists(PERF_DB):
    conn = sqlite3.connect(PERF_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT win_loss, COUNT(*) FROM trades GROUP BY win_loss;")
    print(cursor.fetchall())
    conn.close()
