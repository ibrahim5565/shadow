import sqlite3
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(base_dir, "data", "performance.db")

if os.path.exists(db_path):
    print("=== SQLite Trades Summary ===")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print(f"Tables: {tables}")
    
    for table_tuple in tables:
        table_name = table_tuple[0]
        cursor.execute(f"PRAGMA table_info({table_name});")
        info = cursor.fetchall()
        print(f"\nTable {table_name} Columns:")
        for col in info:
            print(f"  {col[1]} ({col[2]})")
            
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        print(f"Total rows in {table_name}: {count}")
        
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
        rows = cursor.fetchall()
        print(f"First 5 rows in {table_name}:")
        for r in rows:
            print(r)
            
    conn.close()
else:
    print("performance.db not found")
