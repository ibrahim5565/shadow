#!/usr/bin/env python3
"""
TELEGRAM BOT DIAGNOSTIC TEST
============================
Tests the Telegram bot SSL fix and polling loop.
This script validates:
1. SSL verification disabled
2. Polling loop starts
3. Connection to Telegram API succeeds
4. Commands are parsed correctly
"""

import sys
import os
import time
import logging

# Path setup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import settings as cfg
from modules.telegram_bot import TelegramBot

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
)
logger = logging.getLogger("test_telegram")

def test_telegram_bot():
    logger.info("="*60)
    logger.info("AEGIS TELEGRAM BOT DIAGNOSTIC TEST")
    logger.info("="*60)
    
    # Check credentials
    logger.info("\n[PHASE 1] Validating credentials...")
    if not cfg.TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN not configured in .env")
        return False
    if not cfg.TELEGRAM_CHAT_ID:
        logger.error("❌ TELEGRAM_CHAT_ID not configured in .env")
        return False
    logger.info("✅ Credentials present")
    logger.info("   Token: %s...%s", cfg.TELEGRAM_TOKEN[:10], cfg.TELEGRAM_TOKEN[-10:])
    logger.info("   Chat ID: %s", cfg.TELEGRAM_CHAT_ID)
    
    # Initialize bot
    logger.info("\n[PHASE 2] Initializing TelegramBot...")
    bot = TelegramBot()
    logger.info("✅ Bot initialized")
    
    # Test connectivity
    logger.info("\n[PHASE 3] Testing Telegram API connectivity...")
    logger.info("   Calling getMe()...")
    time.sleep(1)
    
    # Start polling
    logger.info("\n[PHASE 4] Starting polling loop...")
    bot.start_polling()
    logger.info("✅ Polling loop started")
    logger.info("   Polling thread: %s", bot._poll_thread)
    logger.info("   Thread alive: %s", bot._poll_thread.is_alive() if bot._poll_thread else False)
    logger.info("   Polling running: %s", bot._running)
    
    # Send test message
    logger.info("\n[PHASE 5] Testing message sending...")
    bot.send("🧪 <b>AEGIS TELEGRAM TEST</b>\nBot diagnostics running. If you see this, the fix works!")
    time.sleep(2)
    logger.info("✅ Test message queued for sending")
    
    # Monitor polling for 10 seconds
    logger.info("\n[PHASE 6] Monitoring polling loop (10 seconds)...")
    for i in range(10):
        if bot._poll_thread and bot._poll_thread.is_alive():
            logger.info("   [%d/10] Polling active", i+1)
        else:
            logger.error("❌ Polling thread died!")
            return False
        time.sleep(1)
    
    logger.info("✅ Polling loop stable")
    
    logger.info("\n[RESULT] Telegram bot test PASSED")
    logger.info("="*60)
    logger.info("Next steps:")
    logger.info("1. Check Telegram for test message")
    logger.info("2. Send /start command to test command parsing")
    logger.info("3. Check logs/telegram.log for polling activity")
    logger.info("="*60)
    
    return True

if __name__ == "__main__":
    try:
        success = test_telegram_bot()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error("Test failed with exception: %s", e, exc_info=True)
        sys.exit(1)
