import sqlite3
import json

conn = sqlite3.connect('Aegis_Gold/data/trade_memory.db')
cursor = conn.cursor()

print("Schema of 'trades' table:")
for col in cursor.execute("PRAGMA table_info(trades)").fetchall():
    print(col)

rows = cursor.execute("SELECT * FROM trades ORDER BY rowid DESC LIMIT 20").fetchall()
print(f"\nTotal rows in trades: {len(rows)}")
for r in rows:
    print(r)
conn.close()

conn2 = sqlite3.connect('Aegis_Gold/data/decision_records.db')
cursor2 = conn2.cursor()
print("\nSchema of 'decision_records' table:")
for col in cursor2.execute("PRAGMA table_info(decision_records)").fetchall():
    print(col)

rows2 = cursor2.execute("SELECT * FROM decision_records ORDER BY rowid DESC LIMIT 20").fetchall()
print(f"\nTotal rows in decision_records: {len(rows2)}")
for r in rows2:
    print(r)
conn2.close()
