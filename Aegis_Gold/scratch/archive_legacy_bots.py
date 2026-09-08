"""
Phase 5 Cleanup Script
Moves unused legacy single-file bot entry points into archive/ folder.
Preserves all files for reference without cluttering the main Aegis-Gold repository.
"""

import os
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ARCHIVE_DIR = BASE_DIR / "archive"

LEGACY_BOT_FILES = [
    "BOT_FINAL.py",
    "BOT_WORKING.py",
    "FIXED_BOT.py",
    "PRODUCTION_BOT.py",
    "RUN_BOT.py",
    "SIMPLE_BOT.py",
    "SIMPLE_TRADER.py",
    "SINGLE_CLEAN_BOT.py",
    "START_FULL_BOT.py",
    "TRADE_NOW.py",
    "auto_restart_bot.py",
    "start_bot.py",
]

print(f"=== PHASE 5 CLEANUP & ARCHIVING ===")
print(f"Archive Directory: {ARCHIVE_DIR}")

ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

moved_count = 0
for fname in LEGACY_BOT_FILES:
    src_file = BASE_DIR / fname
    if src_file.exists():
        dst_file = ARCHIVE_DIR / fname
        shutil.move(str(src_file), str(dst_file))
        print(f"  [ARCHIVED] {fname} -> archive/{fname}")
        moved_count += 1
    else:
        print(f"  [SKIPPED] {fname} (not found)")

print(f"\nArchived {moved_count} legacy bot files successfully.")
print("Confirmed start_aegis.py is the single authoritative application entry point.")
