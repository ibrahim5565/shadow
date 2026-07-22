#!/usr/bin/env python3
"""
AEGIS AUTO TRADING SYSTEM — MASTER ENTRY POINT
===============================================

Fully automated 24/7 MT5 trading for EURUSD & XAUUSD
- Continuous market monitoring
- Automatic trade execution
- Telegram notifications
- VPS 24/7 operation
- Auto-recovery from failures

Usage:
  python start_aegis.py              # Start in foreground
  nssm install AegisBot "python start_aegis.py"  # Install as service

"""

import sys
import os
import logging
import logging.handlers
import asyncio
import threading
import time
import signal
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings as cfg
from core.main import main_loop, main as core_main
from brain.recovery_daemon import RecoveryDaemon

# ══════════════════════════════════════════════════════════════
# LOGGING SETUP
# ══════════════════════════════════════════════════════════════

log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)

# Console + File logging
formatter = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")

# Root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

# File handler — delay=True prevents rotation lock on Windows
file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(log_dir, "aegis.log"),
    maxBytes=10*1024*1024,
    backupCount=3,
    encoding="utf-8",
    delay=True
)
file_handler.setFormatter(formatter)
root_logger.addHandler(file_handler)

logger = logging.getLogger("aegis.master")

# ══════════════════════════════════════════════════════════════
# SIGNAL HANDLERS
# ══════════════════════════════════════════════════════════════

_shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """Handle SIGTERM and SIGINT gracefully."""
    logger.warning("Received signal %d. Graceful shutdown initiated...", signum)
    _shutdown_event.set()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# ══════════════════════════════════════════════════════════════
# STARTUP CHECKS
# ══════════════════════════════════════════════════════════════

def check_environment():
    """Verify all required configuration and dependencies."""
    logger.info("="*70)
    logger.info("AEGIS AUTO TRADING SYSTEM — STARTUP")
    logger.info("="*70)
    
    checks_passed = True
    
    # Check Python version
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8+ required (current: %s)", sys.version)
        checks_passed = False
    else:
        logger.info("✅ Python version: %s", sys.version.split()[0])
    
    # Check Telegram credentials (OPTIONAL - not required for bot operation)
    if not cfg.TELEGRAM_TOKEN:
        logger.warning("⚠️  TELEGRAM_TOKEN not configured - Telegram notifications disabled")
    else:
        logger.info("✅ Telegram token configured")
    
    if not cfg.TELEGRAM_CHAT_ID:
        logger.warning("⚠️  TELEGRAM_CHAT_ID not configured - Telegram notifications disabled")
    else:
        logger.info("✅ Telegram chat ID configured")
    
    # Check MT5 credentials
    if not cfg.MT5_LOGIN or not cfg.MT5_PASSWORD:
        logger.error("❌ MT5 credentials not configured in .env")
        checks_passed = False
    else:
        logger.info("✅ MT5 credentials configured (Account: %s)", cfg.MT5_LOGIN)
    
    # Check required directories
    required_dirs = ["logs", "data", "config"]
    for dir_name in required_dirs:
        dir_path = os.path.join(os.path.dirname(__file__), dir_name)
        if not os.path.exists(dir_path):
            logger.error("❌ Missing directory: %s", dir_name)
            checks_passed = False
        else:
            logger.info("✅ Directory exists: %s", dir_name)
    
    # Check required modules
    try:
        import MetaTrader5 as mt5
        logger.info("✅ MetaTrader5 module available")
    except ImportError:
        logger.error("❌ MetaTrader5 module not found. Install: pip install MetaTrader5")
        checks_passed = False
    
    try:
        import requests
        logger.info("✅ requests module available")
    except ImportError:
        logger.error("❌ requests module not found. Install: pip install requests")
        checks_passed = False
    
    try:
        import psutil
        logger.info("✅ psutil module available")
    except ImportError:
        logger.error("❌ psutil module not found. Install: pip install psutil")
        checks_passed = False
    
    logger.info("="*70)
    
    if not checks_passed:
        logger.critical("STARTUP CHECKS FAILED - System cannot start")
        return False
    
    logger.info("✅ ALL STARTUP CHECKS PASSED")
    return True

# ══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

async def run_with_recovery():
    """Run trading loop with recovery daemon monitoring."""
    recovery = RecoveryDaemon(
        ram_threshold_mb=400.0,
        cpu_threshold_pct=85.0
    )
    
    logger.info("🚀 Starting AEGIS trading engine...")
    logger.info("   Symbols: %s", ", ".join(cfg.SYMBOLS))
    logger.info("   Scan Interval: %d seconds", cfg.SCAN_INTERVAL)
    logger.info("   Demo Mode: %s", "YES" if cfg.DEMO_MODE else "NO (LIVE)")
    logger.info("   Risk per Trade: %.2f%%", cfg.RISK_PERCENT * 100)
    
    # Health check thread
    def health_check_loop():
        """Monitor system health every 60 seconds."""
        while not _shutdown_event.is_set():
            try:
                health = recovery.check_health()
                if health["status"] == "DEGRADED":
                    logger.warning("⚠️ System degraded: %s", health)
                    if "GARBAGE_COLLECTION" in health["actions_taken"]:
                        logger.info("   Garbage collection completed. Memory now: %.1f MB", health["ram_mb"])
                time.sleep(60)
            except Exception as e:
                logger.error("Health check error: %s", e)
                time.sleep(60)
    
    health_thread = threading.Thread(target=health_check_loop, daemon=True)
    health_thread.start()
    logger.info("✅ Health monitoring thread started")
    
    # Run main loop
    try:
        await main_loop()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.critical("Unhandled exception in main loop: %s", e, exc_info=True)
        raise

def main():
    """Entry point."""
    import logging.handlers
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Log system info
    logger.info("VPS Info:")
    logger.info("  OS: %s", sys.platform)
    logger.info("  Hostname: %s", os.environ.get("COMPUTERNAME", "unknown"))
    logger.info("  Start Time: %s UTC", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    
    # Run async event loop — calls core_main() which starts Flask API + main_loop
    try:
        logger.info("Entering main event loop...")
        core_main()
    except KeyboardInterrupt:
        logger.info("Shutdown by user")
    except Exception as e:
        logger.critical("Fatal error: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        logger.info("AEGIS trading system stopped")
        logger.info("="*70)

if __name__ == "__main__":
    main()
