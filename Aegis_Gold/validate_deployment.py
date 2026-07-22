#!/usr/bin/env python3
"""
AEGIS AUTO TRADING — DEPLOYMENT VALIDATION
============================================

Validates all components are properly configured before deployment to VPS.

Usage:
  python validate_deployment.py
"""

import sys
import os
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger("validate")

def check(name: str, condition: bool, details: str = "") -> bool:
    """Print a check result."""
    status = "✅ PASS" if condition else "❌ FAIL"
    msg = f"{status} — {name}"
    if details:
        msg += f" ({details})"
    logger.info(msg)
    return condition

def main():
    """Run deployment validation."""
    logger.info("="*70)
    logger.info("AEGIS AUTO TRADING — DEPLOYMENT VALIDATION")
    logger.info("="*70)
    logger.info("")
    
    passed = 0
    failed = 0
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # ── Python & Dependencies ──────────────────────────────────
    logger.info("📦 PYTHON & DEPENDENCIES")
    logger.info("-" * 70)
    
    if check("Python version", sys.version_info >= (3, 8), sys.version.split()[0]):
        passed += 1
    else:
        failed += 1
    
    # Check required modules
    required_modules = ["MetaTrader5", "requests", "psutil", "flask", "flask_cors"]
    for module_name in required_modules:
        try:
            __import__(module_name)
            check(f"Module: {module_name}", True)
            passed += 1
        except ImportError:
            check(f"Module: {module_name}", False)
            failed += 1
    
    logger.info("")
    
    # ── Configuration Files ────────────────────────────────────
    logger.info("⚙️  CONFIGURATION FILES")
    logger.info("-" * 70)
    
    # Check .env file
    env_path = os.path.join(base_dir, ".env")
    env_exists = os.path.exists(env_path)
    if check(".env file exists", env_exists):
        passed += 1
        
        # Check .env content
        if env_exists:
            try:
                from dotenv import load_dotenv
                load_dotenv(env_path)
                
                mt5_login = os.getenv("MT5_LOGIN")
                mt5_pass = os.getenv("MT5_PASSWORD")
                tg_token = os.getenv("TELEGRAM_TOKEN")
                tg_chat = os.getenv("TELEGRAM_CHAT_ID")
                
                if check("  MT5_LOGIN configured", bool(mt5_login), mt5_login or "MISSING"):
                    passed += 1
                else:
                    failed += 1
                
                if check("  MT5_PASSWORD configured", bool(mt5_pass)):
                    passed += 1
                else:
                    failed += 1
                
                if check("  TELEGRAM_TOKEN configured", bool(tg_token), 
                        tg_token[:10] + "..." if tg_token else "MISSING"):
                    passed += 1
                else:
                    failed += 1
                
                if check("  TELEGRAM_CHAT_ID configured", bool(tg_chat), tg_chat or "MISSING"):
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Error reading .env: {e}")
                failed += 4
    else:
        failed += 1
        logger.warning("  Create .env file with MT5 and Telegram credentials")
    
    logger.info("")
    
    # ── Project Structure ──────────────────────────────────────
    logger.info("📁 PROJECT STRUCTURE")
    logger.info("-" * 70)
    
    required_dirs = ["logs", "data", "config", "core", "modules", "brain", "persistence"]
    for dir_name in required_dirs:
        dir_path = os.path.join(base_dir, dir_name)
        if check(f"Directory: {dir_name}", os.path.isdir(dir_path)):
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    
    # ── Main Components ────────────────────────────────────────
    logger.info("🧩 MAIN COMPONENTS")
    logger.info("-" * 70)
    
    required_files = [
        ("start_aegis.py", "Master entry point"),
        ("core/main.py", "Trading loop"),
        ("modules/mt5_gateway.py", "MT5 communication"),
        ("modules/telegram_bot.py", "Telegram bot"),
        ("modules/risk_manager.py", "Risk controls"),
        ("brain/brain.py", "Trading decisions"),
        ("config/settings.py", "Configuration"),
    ]
    
    for filename, description in required_files:
        filepath = os.path.join(base_dir, filename)
        if check(f"Component: {description}", os.path.isfile(filepath), filename):
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    
    # ── Deployment Scripts ────────────────────────────────────
    logger.info("🚀 DEPLOYMENT SCRIPTS")
    logger.info("-" * 70)
    
    deployment_files = [
        ("persistence/install_service.ps1", "Windows service installer"),
        ("persistence/start_aegis.bat", "Batch startup script"),
        ("VPS_DEPLOYMENT.md", "VPS deployment guide"),
        ("SYSTEM_READY.md", "System status documentation"),
    ]
    
    for filename, description in deployment_files:
        filepath = os.path.join(base_dir, filename)
        if check(f"Script: {description}", os.path.isfile(filepath), filename):
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    
    # ── Documentation ─────────────────────────────────────────
    logger.info("📚 DOCUMENTATION")
    logger.info("-" * 70)
    
    doc_files = [
        (".kiro/specs/automated_trading_system.md", "System specification"),
        ("TELEGRAM_FIX_SUMMARY.md", "Telegram SSL fix"),
        ("DAILY_LOSS_LIMIT_REMOVED.md", "Configuration changes"),
    ]
    
    for filename, description in doc_files:
        filepath = os.path.join(base_dir, filename)
        if check(f"Doc: {description}", os.path.isfile(filepath), filename):
            passed += 1
        else:
            failed += 1
    
    logger.info("")
    
    # ── Summary ────────────────────────────────────────────────
    logger.info("="*70)
    logger.info(f"VALIDATION RESULTS: {passed} passed, {failed} failed")
    logger.info("="*70)
    
    if failed == 0:
        logger.info("")
        logger.info("✅ ALL CHECKS PASSED — System is ready for deployment!")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Test locally: python start_aegis.py")
        logger.info("2. Deploy to VPS: See VPS_DEPLOYMENT.md")
        logger.info("3. Install service: Run persistence/install_service.ps1")
        logger.info("4. Start trading: Service auto-starts on VPS reboot")
        logger.info("")
        return 0
    else:
        logger.info("")
        logger.error("❌ VALIDATION FAILED — Fix issues above before deployment")
        logger.info("")
        logger.info("Common issues:")
        logger.info("- Missing .env file: Create it with MT5 and Telegram credentials")
        logger.info("- Missing Python modules: Run: pip install MetaTrader5 requests psutil flask flask-cors")
        logger.info("- Missing directories: Should be auto-created on first run")
        logger.info("")
        return 1

if __name__ == "__main__":
    sys.exit(main())
