import csv
import os
import sqlite3

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

print("=== Checking journal.csv for June 23 ===")
journal_path = os.path.join(base_dir, "data", "journal.csv")
if os.path.exists(journal_path):
    with open(journal_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        june23_count = 0
        for r in reader:
            if r and any("2026-06-23" in field for field in r):
                june23_count += 1
                if june23_count <= 10:
                    print(dict(zip(header, r)))
        print(f"Total June 23 trades in journal: {june23_count}")
else:
    print("journal.csv not found")

print("\n=== Checking performance.db for June 23 ===")
db_path = os.path.join(base_dir, "data", "performance.db")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trades WHERE timestamp LIKE '%2026-06-23%';")
    count = cursor.fetchone()[0]
    print(f"Total June 23 trades in database: {count}")
    
    cursor.execute("SELECT * FROM trades WHERE timestamp LIKE '%2026-06-23%' ORDER BY timestamp DESC LIMIT 10;")
    rows = cursor.fetchall()
    for r in rows:
        print(r)
    conn.close()
else:
    print("performance.db not found")
