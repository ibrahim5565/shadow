import re

log_path = r"d:\Trading\Aegis_Gold\logs\aegis.log"

with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()

target_idx = -1
for idx, line in enumerate(lines):
    if "2026-06-08 17:27:07" in line:
        target_idx = idx
        break

if target_idx != -1:
    start = max(0, target_idx - 25)
    end = min(len(lines), target_idx + 25)
    print("=" * 60)
    print(f"Log Context around line {target_idx}:")
    print("=" * 60)
    for i in range(start, end):
        print(f"{i}: {lines[i].strip()}")
else:
    print("Timestamp 2026-06-08 17:27:07 not found in aegis.log")
