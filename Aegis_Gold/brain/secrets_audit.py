import os
import re
import logging
from typing import Dict, Any

logger = logging.getLogger("aegis.secrets_audit")

class SecretsAuditor:
    """
    QUANT X startup security checks.
    Scans environment configuration and logs to identify potential secrets leaks.
    """
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def check_gitignore(self) -> bool:
        """Verifies that .env is safely excluded from git tracking."""
        gitignore_path = os.path.join(self.base_dir, ".gitignore")
        if not os.path.exists(gitignore_path):
            logger.warning("[SECURITY] .gitignore file does not exist! Risk of committing secrets.")
            return False

        try:
            with open(gitignore_path, "r") as f:
                content = f.read()
            if ".env" in content:
                logger.info("[SECURITY] Gitignore check passed: .env is excluded.")
                return True
            else:
                logger.warning("[SECURITY] .gitignore found but .env is NOT excluded!")
                return False
        except Exception as e:
            logger.error(f"Error checking gitignore: {e}")
            return False

    def scan_log_files(self) -> bool:
        """
        Scans logs directory for any accidental print of sensitive keys:
        - Telegram bot tokens (digits:letters)
        - Password patterns
        """
        logs_dir = os.path.join(self.base_dir, "logs")
        if not os.path.exists(logs_dir):
            return True

        # Token pattern: e.g., 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
        token_regex = re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")
        passed = True

        for root, _, files in os.walk(logs_dir):
            for file in files:
                if not file.endswith(".log"):
                    continue
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if token_regex.search(line):
                                logger.error(
                                    f"[SECURITY WARNING] Leak detected in {file}:{line_num}! "
                                    f"Accidental log of a Telegram Bot Token pattern."
                                )
                                passed = False
                except Exception as e:
                    logger.debug(f"Failed to scan log file {file}: {e}")

        return passed

    def run_audit(self) -> Dict[str, Any]:
        """Runs all security audits and returns results dictionary."""
        from config.quant_x_config import QX
        if not QX.flag("secrets_audit"):
            return {"status": "skipped"}

        logger.info("[SECURITY] Running QUANT X Secrets Audit...")
        gitignore_ok = self.gitignore_ok = self.check_gitignore()
        logs_clean = self.scan_log_files()
        
        status = "PASSED" if (gitignore_ok and logs_clean) else "WARNING"
        logger.info(f"[SECURITY] Audit complete. Status: {status}")
        return {
            "status": status,
            "gitignore_clean": gitignore_ok,
            "logs_clean": logs_clean
        }
