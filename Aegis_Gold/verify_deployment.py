"""
Aegis-Gold v6.0 — Deployment Verification Script
Runs 6 checks: MT5 connection, Telegram connection, Trading engine, Watchdog daemon, Dashboard API, Command routing.
On success, enables Live VPS Control Mode and alerts Telegram.
"""

import os
import sys
import time
import requests
import psutil
import socket
import subprocess

# Encoding fix for Windows terminals
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Path setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

from config import settings as cfg

def print_step(name, status, details=""):
    status_icon = "✅" if status else "❌"
    print(f"{status_icon} [{name}] {details}")

def run_checks():
    print("=" * 60)
    print("   AEGIS VPS CONTROL SYSTEM — DEPLOYMENT VERIFICATION")
    print("=" * 60)
    
    all_passed = True
    
    # ── Check 1: Telegram Connection ─────────────────────────────────
    tg_passed = False
    tg_details = ""
    try:
        TELEGRAM_IP = "149.154.167.220"
        url = f"https://{TELEGRAM_IP}/bot{cfg.TELEGRAM_TOKEN}/getMe"
        headers = {"Host": "api.telegram.org"}
        resp = requests.get(url, headers=headers, timeout=10, verify=False)
        if resp.ok:
            data = resp.json()
            username = data.get("result", {}).get("username", "unknown")
            tg_passed = True
            tg_details = f"Connected to @{username}"
        else:
            tg_details = f"API error: {resp.status_code} - {resp.text}"
    except Exception as e:
        tg_details = f"Connection error: {e}"
        
    print_step("1/6 Telegram Connection", tg_passed, tg_details)
    if not tg_passed:
        all_passed = False

    # ── Check 2: MT5 Connection ──────────────────────────────────────
    mt5_passed = False
    mt5_details = ""
    try:
        import MetaTrader5 as mt5
        ok = mt5.initialize(
            login=cfg.MT5_LOGIN,
            password=cfg.MT5_PASSWORD,
            server=cfg.MT5_SERVER,
        )
        if ok:
            ti = mt5.terminal_info()
            ai = mt5.account_info()
            if ti and ai:
                mt5_passed = True
                mt5_details = f"Logged in: {cfg.MT5_LOGIN} (Broker: {ti.company}, Equity: ${ai.equity:.2f})"
            else:
                mt5_details = "Connected to terminal, but failed to retrieve account details."
            # NOTE: Do NOT call mt5.shutdown() here — it would kill the running bot's shared MT5 connection
        else:
            mt5_details = f"Initialize failed: {mt5.last_error()}"
    except Exception as e:
        mt5_details = f"Exception: {e}"
        
    print_step("2/6 MetaTrader 5 Connection", mt5_passed, mt5_details)
    if not mt5_passed:
        all_passed = False

    # ── Verify process lifecycle status for 3 and 4 ──────────────────
    # Check if services are started, if not, attempt to start them
    def check_script_running(script_name):
        normalized_name = script_name.replace("/", os.sep).replace("\\", os.sep)
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmdline = proc.info.get('cmdline') or []
                for arg in cmdline:
                    normalized_arg = arg.replace("/", os.sep).replace("\\", os.sep)
                    if normalized_name.lower() in normalized_arg.lower():
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    watchdog_active = check_script_running("watchdog.py")
    bot_active = check_script_running("core/main.py")
    
    if not watchdog_active or not bot_active:
        print("ℹ️ Starting Aegis background services to perform lifecycle checks...")
        # Start watchdog.py directly (which will start the bot)
        python_exe = sys.executable
        watchdog_script = os.path.join(BASE_DIR, "watchdog.py")
        subprocess.Popen(
            [python_exe, watchdog_script],
            cwd=BASE_DIR,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        
        # Give services up to 15 seconds to spin up and bind ports
        print("🕒 Waiting 15 seconds for processes and endpoints to initialize...")
        time.sleep(15)
        watchdog_active = check_script_running("watchdog.py")
        bot_active = check_script_running("core/main.py")

    # ── Check 3: Trading Engine ──────────────────────────────────────
    engine_details = f"Process running: {bot_active}"
    if bot_active:
        lock_path = os.path.join(BASE_DIR, "data", "bot.lock")
        if os.path.exists(lock_path):
            engine_details += " (data/bot.lock exists)"
        else:
            engine_details += " (⚠️ data/bot.lock missing)"
    print_step("3/6 Trading Engine Status", bot_active, engine_details)
    if not bot_active:
        all_passed = False

    # ── Check 4: Watchdog Status ─────────────────────────────────────
    wd_details = f"Process running: {watchdog_active}"
    if watchdog_active:
        lock_path = os.path.join(BASE_DIR, "data", "watchdog.lock")
        if os.path.exists(lock_path):
            wd_details += " (data/watchdog.lock exists)"
        else:
            wd_details += " (⚠️ data/watchdog.lock missing)"
    print_step("4/6 Watchdog Status Check", watchdog_active, wd_details)
    if not watchdog_active:
        all_passed = False

    # ── Check 5: Dashboard API ───────────────────────────────────────
    api_passed = False
    api_details = ""
    try:
        resp = requests.get("http://127.0.0.1:5001/health", timeout=5)
        if resp.ok and resp.json().get("status") == "online":
            api_passed = True
            api_details = f"Dashboard online (Response: {resp.json()})"
        else:
            api_details = f"Dashboard responded with status: {resp.status_code}"
    except Exception as e:
        api_details = f"Connection failed to http://127.0.0.1:5001/health: {e}"
        
    print_step("5/6 Dashboard API Status", api_passed, api_details)
    if not api_passed:
        all_passed = False

    # ── Check 6: Command Routing ─────────────────────────────────────
    route_passed = False
    route_details = ""
    try:
        # Verify post command to API works
        resp = requests.post("http://127.0.0.1:5001/command", json={"cmd": "PING_ROUTE"}, timeout=5)
        if resp.ok and resp.json().get("success") is True:
            route_passed = True
            route_details = "Command router endpoint reachable and validated."
        else:
            route_details = f"Endpoint error: {resp.status_code}"
    except Exception as e:
        route_details = f"Routing failed: {e}"
        
    print_step("6/6 Command Routing Check", route_passed, route_details)
    if not route_passed:
        all_passed = False

    print("=" * 60)
    if all_passed:
        print("🏆 ALL DEPLOYMENT CHECKS COMPLETED SUCCESSFULLY!")
        print("Enabling Live VPS Control Mode and notifying Telegram chat...")
        
        TELEGRAM_IP = "149.154.167.220"
        tg_url = f"https://{TELEGRAM_IP}/bot{cfg.TELEGRAM_TOKEN}/sendMessage"
        headers = {"Host": "api.telegram.org"}
        message_text = "<b>AEGIS VPS CONTROL ONLINE — All Systems Operational — Mobile Control Enabled.</b>"
        
        try:
            requests.post(
                tg_url,
                headers=headers,
                json={"chat_id": str(cfg.TELEGRAM_CHAT_ID), "text": message_text, "parse_mode": "HTML"},
                verify=False,
                timeout=10
            )
            print("✉️ Notification sent to Telegram successfully.")
        except Exception as e:
            print(f"⚠️ Failed to send Telegram notification: {e}")
            
        return True
    else:
        print("❌ DEPLOYMENT VERIFICATION FAILED. Please check details above.")
        return False

if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
