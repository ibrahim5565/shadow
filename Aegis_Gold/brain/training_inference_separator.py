"""
Aegis Gold — Training / Inference Isolation Manager
Ensures GPU-intensive model training, RL replay updates, and feature mining
execute in separate asynchronous background worker processes without competing
with live execution inference loops.
"""

import os
import sys
import time
import logging
import subprocess
from datetime import datetime, timezone
from typing import Optional, Dict, Any

logger = logging.getLogger("aegis.training_separator")


class TrainingInferenceSeparator:
    """
    Manages offline batch training schedules and enforces GPU memory isolation.
    """

    def __init__(self):
        self.base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.training_script = os.path.join(self.base_dir, "TRAIN_ALL_MODELS.py")
        self.flag_file = os.path.join(self.base_dir, "data", "training_in_progress.flag")
        self._last_training_time: float = 0.0

    def is_training_active(self) -> bool:
        """Checks if a background training process is currently active."""
        if os.path.exists(self.flag_file):
            try:
                # Check for stale flags (> 4 hours)
                mtime = os.path.getmtime(self.flag_file)
                if (time.time() - mtime) > (4 * 3600):
                    os.remove(self.flag_file)
                    return False
                return True
            except Exception:
                return False
        return False

    def schedule_background_training(self, force: bool = False) -> bool:
        """
        Launches offline retraining in a low-priority background process.
        Runs only during quiet market hours (e.g. weekend or late post-NY session).
        """
        if self.is_training_active() and not force:
            logger.info("Background training already in progress. Skipping duplicate launch.")
            return False

        now = datetime.now(timezone.utc)
        # Quiet window: Saturday/Sunday or 22:00-23:00 UTC
        is_weekend = now.weekday() in (5, 6)
        is_quiet_hour = (now.hour == 22)
        
        if not (is_weekend or is_quiet_hour or force):
            logger.debug("Active trading hours — postponing background retraining to quiet window.")
            return False

        try:
            # Set flag
            os.makedirs(os.path.dirname(self.flag_file), exist_ok=True)
            with open(self.flag_file, "w", encoding="utf-8") as f:
                f.write(f"Started at {now.isoformat()}\n")

            cmd = [sys.executable, self.training_script, "--offline-mode"]
            
            # Spawn detached low-priority process on Windows
            creation_flags = 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS
            subprocess.Popen(
                cmd,
                cwd=self.base_dir,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self._last_training_time = time.time()
            logger.info("Spawned offline GPU model retraining worker in isolated low-priority process.")
            return True
        except Exception as e:
            logger.error(f"Failed to spawn background training worker: {e}")
            if os.path.exists(self.flag_file):
                try:
                    os.remove(self.flag_file)
                except Exception:
                    pass
            return False
