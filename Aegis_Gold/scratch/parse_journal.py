import csv
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for filename in ["journal.csv", "demo_journal.csv", "journal_backup.csv"]:
    path = os.path.join(base_dir, "data", filename)
    if not os.path.exists(path):
        continue
    
    print(f"=== File: {filename} ===")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        # Find date column index
        date_idx = header.index("timestamp") if "timestamp" in header else 0
        
        count = 0
        for row in reader:
            if not row:
                continue
            date_str = row[date_idx]
            if "2026-06-16" in date_str or "-06-16" in date_str:
                count += 1
                if count <= 15:
                    print(dict(zip(header, row)))
        
        print(f"Total June 16 trades in {filename}: {count}\n")
