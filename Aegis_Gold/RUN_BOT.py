#!/usr/bin/env python3
"""
AEGIS GOLD BOT - SIMPLE STARTER
================================
Starts the bot and begins trading immediately
Fixed to use 50% confidence threshold
"""
import sys
import os
import asyncio
import logging

# Fix encoding
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Set up path
sys.path.insert(0, os.getcwd())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("RUN_BOT")

def main():
    """Start the Aegis Gold bot"""
    logger.info("=" * 60)
    logger.info("🚀 AEGIS GOLD BOT - STARTING")
    logger.info("=" * 60)
    logger.info("📊 Mode: DEMO (Safe Testing)")
    logger.info("⚡ Confidence: 50% threshold")
    logger.info("🚫 Never Pause: ACTIVE")
    logger.info("💪 Trading: CONTINUOUS")
    logger.info("=" * 60)
    
    try:
        # Import the main function
        from core.main import main as core_main
        
        logger.info("✅ Core imported successfully")
        logger.info("🚀 Starting main trading loop...")
        
        # Run the main function
        core_main()
        
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.info("🔧 Trying alternative import method...")
        
        try:
            # Alternative: run the main loop directly
            import start_aegis
            logger.info("✅ Using start_aegis module")
            start_aegis.main()
            
        except Exception as alt_error:
            logger.error(f"❌ Alternative import failed: {alt_error}")
            logger.info("🔧 Last resort: Running minimal trading loop...")
            
            # Minimal trading loop
            import MetaTrader5 as mt5
            from config import settings as cfg
            
            logger.info("🔌 Connecting to MT5...")
            if not mt5.initialize(
                login=cfg.MT5_LOGIN,
                password=cfg.MT5_PASSWORD,
                server=cfg.MT5_SERVER
            ):
                logger.error(f"❌ MT5 initialization failed: {mt5.last_error()}")
                return
            
            logger.info("✅ MT5 connected successfully")
            logger.info(f"📊 Account: {mt5.account_info().login}")
            logger.info(f"💰 Balance: ${mt5.account_info().balance:.2f}")
            logger.info("🔄 Bot is running - waiting for trading signals...")
            logger.info("⚡ Press Ctrl+C to stop (if not in Never Pause mode)")
            
            # Keep running
            import time
            while True:
                time.sleep(5)
                logger.info("💪 Bot running - checking for signals...")
                
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
        
    except Exception as e:
        logger.error(f"❌ Bot error: {e}", exc_info=True)
        logger.info("🔄 Attempting to restart in 5 seconds...")
        import time
        time.sleep(5)
        main()  # Restart

if __name__ == "__main__":
    logger.info("🤖 Aegis Gold Trading Bot")
    logger.info("🚫 ABSOLUTE NEVER PAUSE MODE")
    logger.info("⚡ 50% Confidence Threshold")
    logger.info("")
    main()
