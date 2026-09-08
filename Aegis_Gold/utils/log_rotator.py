"""
Aegis Gold — Automated Log & Database Archival Utility
Rotates and compresses oversized logs (>100MB) to prevent disk saturation.
"""

import os
import gzip
import shutil
import logging
from datetime import datetime, timezone

logger = logging.getLogger("aegis.log_rotator")


def rotate_oversized_files(target_dirs=None, max_bytes=100 * 1024 * 1024):
    """
    Scans data/ and logs/ folders, compresses files exceeding max_bytes into .gz archives,
    and resets the active file to keep disk footprints lean.
    """
    if target_dirs is None:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        target_dirs = [
            os.path.join(base, "data"),
            os.path.join(base, "logs")
        ]

    archive_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "archive", "rotated_logs"))
    os.makedirs(archive_dir, exist_ok=True)

    rotated_count = 0
    for d in target_dirs:
        if not os.path.exists(d):
            continue
        for fname in os.listdir(d):
            fpath = os.path.join(d, fname)
            if not os.path.isfile(fpath) or fname.endswith(".db") or fname.endswith(".gz") or fname.endswith(".lock"):
                continue
            
            try:
                sz = os.path.getsize(fpath)
                if sz >= max_bytes:
                    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    gz_name = f"{fname}_{ts}.gz"
                    gz_path = os.path.join(archive_dir, gz_name)
                    
                    # Compress
                    with open(fpath, "rb") as f_in:
                        with gzip.open(gz_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # Truncate original
                    with open(fpath, "w", encoding="utf-8") as f_zero:
                        f_zero.write(f"# Log rotated at {ts}\n")
                    
                    rotated_count += 1
                    logger.info(f"Rotated {fname} ({sz / (1024*1024):.1f} MB) -> {gz_name}")
            except Exception as e:
                logger.error(f"Error rotating {fpath}: {e}")

    return rotated_count


if __name__ == "__main__":
    count = rotate_oversized_files()
    print(f"Log rotation complete. Rotated {count} oversized files.")
