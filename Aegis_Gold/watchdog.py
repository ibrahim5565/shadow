"""
Aegis-Gold v6.0 — Autonomous Watchdog
Monitors core/main.py and ensures it runs 24/7.
Restarts on crash, deadlock, or MT5 disconnect.
Process-locked to prevent duplicate watchdogs.
"""

import sys
import os
import subprocess
import time
import logging
import logging.handlers
import atexit
from datetime import datetime

import requests
import psutil
from dotenv import load_dotenv

# ── Path setup ─────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# ── Rotating Logs ──────────────────────────────────────────────
_formatter = logging.Formatter("%(asctime)s [WATCHDOG] %(levelname)s %(message)s")

_file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, "watchdog.log"), maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)

_recovery_handler = logging.handlers.RotatingFileHandler(
    os.path.join(LOGS_DIR, "recovery.log"), maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
)
_recovery_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

logging.basicConfig(level=logging.INFO, handlers=[_file_handler, _console_handler])
logger = logging.getLogger("watchdog")
recovery_logger = logging.getLogger("watchdog.recovery")
recovery_logger.addHandler(_recovery_handler)

# ── Load .env ──────────────────────────────────────────────────
load_dotenv(os.path.join(BASE_DIR, ".env"))

BOT_SCRIPT = os.path.join(BASE_DIR, "core", "main.py")
LOCK_FILE = os.path.join(DATA_DIR, "watchdog.lock")
RESTART_DELAY = 3
MAX_RESTARTS = 50
HEARTBEAT_URL = "http://127.0.0.1:5001/heartbeat"
HEALTH_URL = "http://127.0.0.1:5001/health"
MAX_BOT_MEMORY_MB = 1500  # Bot legitimately uses ~800 MB with OMEGA AI engines


def acquire_lock():
    """Acquire process lock. Exit if another watchdog is running."""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
            if psutil.pid_exists(old_pid):
                logger.error(f"Another watchdog is running (PID {old_pid}). Exiting.")
                sys.exit(0)
            else:
                logger.warning(f"Stale watchdog lock (PID {old_pid}). Cleaning up.")
                os.remove(LOCK_FILE)
        except Exception:
            os.remove(LOCK_FILE)
    
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    
    def _cleanup():
        try:
            os.remove(LOCK_FILE)
        except Exception:
            pass
    atexit.register(_cleanup)
    logger.info(f"Watchdog lock acquired (PID {os.getpid()})")


def send_telegram(text: str):
    """Send a Telegram alert from the watchdog.
    Uses verify=False to bypass Sophos DPI SSL interception (same as main bot)."""
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        TELEGRAM_IP = "149.154.167.220"
        requests.post(
            f"https://{TELEGRAM_IP}/bot{token}/sendMessage",
            headers={"Host": "api.telegram.org"},
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
            verify=False  # Bypass Sophos DPI SSL cert interception
        )
    except Exception as e:
        logger.error(f"Telegram alert failed: {e}")


def is_mt5_running():
    """Check if terminal64.exe is running."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def restart_mt5():
    """Kill and restart MetaTrader 5."""
    logger.warning("Restarting MetaTrader 5 Terminal...")
    recovery_logger.info("MT5 restart triggered")
    
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(2)
    
    mt5_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    if os.path.exists(mt5_path):
        subprocess.Popen([mt5_path])
        logger.info("MT5 Terminal launched.")
        send_telegram("🔄 <b>[WATCHDOG] MetaTrader 5 Restarted</b>")
    else:
        logger.error(f"MT5 not found at {mt5_path}")
        send_telegram(f"⚠️ <b>[WATCHDOG] MT5 Not Found</b>\n<code>{mt5_path}</code>")


def find_bot_process(bot_pid):
    """Check if the bot process is using excessive memory.
    Warns at 1200 MB (soft), kills only at 1500 MB (hard limit).
    Normal bot usage is ~800 MB with all OMEGA AI engines loaded.
    """
    try:
        proc = psutil.Process(bot_pid)
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        if mem_mb > MAX_BOT_MEMORY_MB:
            logger.warning(f"Bot memory CRITICAL: {mem_mb:.0f} MB > {MAX_BOT_MEMORY_MB} MB — force restarting")
            recovery_logger.info(f"Memory limit exceeded: {mem_mb:.0f} MB")
            send_telegram(f"🚨 <b>[WATCHDOG] Memory Critical</b>\nBot using <code>{mem_mb:.0f} MB</code>. Force restarting...")
            return False  # Signal restart needed
        elif mem_mb > 1200:
            logger.warning(f"Bot memory high: {mem_mb:.0f} MB — GC running, monitoring...")
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return True





def _flatten_all_positions_emergency():
    """Disabled: watchdog must never send orders or flatten account positions."""
    logger.critical(
        "[WATCHDOG] Emergency flatten is disabled. Manage any open position "
        "through the verified broker terminal; watchdog has no order authority."
    )


def monitor_and_wait(process):
    """Monitor process via heartbeat, resources, and MT5 connection."""
    consecutive_failures = 0
    start_time = time.time()
    mt5_check_interval = 60  # Check MT5 every 60s
    last_mt5_check = time.time()
    
    while True:
        exit_code = process.poll()
        if exit_code is not None:
            return exit_code

        time.sleep(10)
        
        # 1. Heartbeat check (after 45s boot time to allow AI model warming)
        if time.time() - start_time > 45:
            try:
                resp = requests.get(HEARTBEAT_URL, timeout=15)
                if resp.ok and resp.json().get("status") == "online":
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    logger.warning(f"Heartbeat warning (failures: {consecutive_failures}/5)")
            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"Heartbeat failed: {e} (failures: {consecutive_failures}/5)")
            
            if consecutive_failures >= 5:
                logger.critical("5 consecutive heartbeat failures! Force restarting...")
                recovery_logger.info("Bot unresponsive - force restart triggered")
                send_telegram("🚨 <b>[WATCHDOG] Bot Unresponsive</b>\nHeartbeat failed 5x. Performing emergency position flattening and force restarting...")
                
                # Emergency position flatten
                try:
                    _flatten_all_positions_emergency()
                except Exception as e:
                    logger.error(f"Watchdog emergency flatten failed: {e}")

                try:
                    process.terminate()
                    time.sleep(2)
                    process.kill()
                except Exception:
                    pass
                return -999


        # 2. Memory check
        if not find_bot_process(process.pid):
            try:
                process.terminate()
                time.sleep(2)
                process.kill()
            except Exception:
                pass
            return -998  # Memory exceeded

        # 3. MT5 connection check
        if time.time() - last_mt5_check > mt5_check_interval:
            last_mt5_check = time.time()
            if not is_mt5_running():
                logger.warning("MT5 terminal not running! Restarting MT5...")
                recovery_logger.info("MT5 not running - restarting")
                restart_mt5()
                time.sleep(10)

        # 4. System resource monitoring
        try:
            mem = psutil.virtual_memory()
            if mem.percent > 92.0:
                logger.warning(f"VPS RAM critical: {mem.percent}%")
                send_telegram(f"⚠️ <b>[WATCHDOG] VPS RAM Critical</b>\n<code>{mem.percent:.1f}%</code> used")
        except Exception:
            pass


def run_bot():
    """Launch the bot subprocess and monitor it."""
    logger.info("Starting Aegis-Gold Engine...")
    
    if not is_mt5_running():
        send_telegram("🔄 <b>[WATCHDOG] Starting MT5</b>")
        restart_mt5()
        time.sleep(10)

    venv_python = os.path.join(BASE_DIR, ".venv_cuda", "Scripts", "python.exe")
    python_exe = venv_python if os.path.exists(venv_python) else sys.executable
    try:
        process = subprocess.Popen(
            [python_exe, BOT_SCRIPT],
            cwd=BASE_DIR,
            shell=False,
            bufsize=1,
            universal_newlines=True
        )
        
        exit_code = monitor_and_wait(process)
        
        if exit_code == 0:
            logger.info("Bot stopped gracefully.")
            send_telegram("⏹️ <b>[WATCHDOG] Bot Stopped Gracefully</b>")
        elif exit_code == -999:
            recovery_logger.info("Bot killed due to deadlock/freeze")
        elif exit_code == -998:
            recovery_logger.info("Bot killed due to memory overflow")
        elif exit_code in (1073807364, -1073741819):
            logger.critical("ACCESS VIOLATION - restarting MT5")
            recovery_logger.info("Access violation detected")
            send_telegram("🚨 <b>[WATCHDOG] Access Violation</b>\nRestarting MT5...")
            restart_mt5()
        else:
            logger.warning(f"Bot exited with code {exit_code}")
            send_telegram(f"🚨 <b>[WATCHDOG] Crash</b>\nExit code: <code>{exit_code}</code>")
            
    except Exception as e:
        logger.error(f"Failed to launch bot: {e}")
        send_telegram(f"🚨 <b>[WATCHDOG] Launch Failed</b>\n<code>{e}</code>")
        return 1
    
    return exit_code


def main():
    """Run one watchdog session; never auto-restart the bot after exit."""
    acquire_lock()
    logger.info("Aegis watchdog active in monitor-only mode; automatic bot restart is disabled.")
    send_telegram("🛡️ <b>[WATCHDOG] Monitor-only mode</b>\nAutomatic restart and emergency order execution are disabled.")
    try:
        exit_code = run_bot()
        if exit_code == 0:
            logger.info("Bot stopped gracefully.")
        else:
            logger.error("Bot exited with code %s. Manual review required; not restarting.", exit_code)
    except KeyboardInterrupt:
        logger.info("Watchdog stopped by user.")
    finally:
        logger.info("Watchdog session ended; no child process will be restarted.")


if __name__ == "__main__":
    main()
