"""
═══════════════════════════════════════════════════════════════════════════════
🔄 AEGIS AUTO-RESTART MANAGER
═══════════════════════════════════════════════════════════════════════════════

Automatically restarts the bot every hour to:
- Refresh connections
- Clear memory
- Reload configurations
- Prevent memory leaks
- Ensure optimal performance

Usage:
  python auto_restart_bot.py

═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import time
import subprocess
import logging
import signal
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AutoRestart] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("logs/auto_restart.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("AutoRestart")


class AutoRestartManager:
    """Manages automatic hourly bot restarts."""
    
    def __init__(self, restart_interval_seconds=3600):
        self.restart_interval = restart_interval_seconds  # Default: 1 hour
        self.bot_process = None
        self.running = True
        self.restart_count = 0
        
        logger.info("🔄 Auto-Restart Manager initialized")
        logger.info(f"   Restart Interval: {self.restart_interval / 60:.0f} minutes")
    
    def start_bot(self):
        """Start the trading bot."""
        try:
            logger.info("🚀 Starting AEGIS trading bot...")
            
            # Start bot process
            self.bot_process = subprocess.Popen(
                [sys.executable, "start_aegis.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            logger.info(f"✅ Bot started (PID: {self.bot_process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
            return False
    
    def stop_bot(self):
        """Stop the trading bot gracefully."""
        if self.bot_process is None:
            logger.warning("No bot process to stop")
            return True
        
        try:
            logger.info(f"🛑 Stopping bot (PID: {self.bot_process.pid})...")
            
            # Send SIGTERM for graceful shutdown
            self.bot_process.send_signal(signal.SIGTERM)
            
            # Wait up to 30 seconds for graceful shutdown
            try:
                self.bot_process.wait(timeout=30)
                logger.info("✅ Bot stopped gracefully")
                return True
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Bot didn't stop gracefully, forcing...")
                self.bot_process.kill()
                self.bot_process.wait()
                logger.info("✅ Bot force-stopped")
                return True
                
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")
            return False
    
    def restart_bot(self):
        """Restart the bot (stop then start)."""
        self.restart_count += 1
        logger.info("="*70)
        logger.info(f"🔄 RESTART #{self.restart_count} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*70)
        
        # Stop current instance
        if self.bot_process:
            self.stop_bot()
            time.sleep(5)  # Wait 5 seconds before restart
        
        # Start new instance
        success = self.start_bot()
        
        if success:
            logger.info(f"✅ Restart #{self.restart_count} successful")
        else:
            logger.error(f"❌ Restart #{self.restart_count} failed")
        
        return success
    
    def check_bot_health(self):
        """Check if bot is still running."""
        if self.bot_process is None:
            return False
        
        # Check if process is alive
        poll = self.bot_process.poll()
        if poll is not None:
            logger.warning(f"⚠️ Bot process died with exit code {poll}")
            return False
        
        return True
    
    def run(self):
        """Main auto-restart loop."""
        logger.info("="*70)
        logger.info("🔄 AUTO-RESTART MANAGER STARTED")
        logger.info("="*70)
        
        # Initial bot start
        if not self.start_bot():
            logger.error("Failed to start bot initially. Exiting.")
            return
        
        next_restart_time = datetime.now() + timedelta(seconds=self.restart_interval)
        logger.info(f"⏰ Next restart scheduled: {next_restart_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            while self.running:
                # Check if it's time to restart
                now = datetime.now()
                
                if now >= next_restart_time:
                    # Time to restart
                    self.restart_bot()
                    next_restart_time = datetime.now() + timedelta(seconds=self.restart_interval)
                    logger.info(f"⏰ Next restart scheduled: {next_restart_time.strftime('%Y-%m-%d %H:%M:%S')}")
                
                else:
                    # Check bot health
                    if not self.check_bot_health():
                        logger.warning("⚠️ Bot not running, restarting immediately...")
                        self.restart_bot()
                        next_restart_time = datetime.now() + timedelta(seconds=self.restart_interval)
                        logger.info(f"⏰ Next restart scheduled: {next_restart_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    else:
                        # Calculate time until next restart
                        time_remaining = (next_restart_time - now).total_seconds()
                        minutes_remaining = int(time_remaining / 60)
                        
                        if minutes_remaining % 10 == 0 and minutes_remaining > 0:  # Log every 10 minutes
                            logger.info(f"ℹ️ Bot running... {minutes_remaining} minutes until restart")
                
                # Check every 60 seconds
                time.sleep(60)
                
        except KeyboardInterrupt:
            logger.info("🛑 Auto-restart manager interrupted by user")
        except Exception as e:
            logger.error(f"❌ Error in auto-restart loop: {e}", exc_info=True)
        finally:
            # Clean shutdown
            logger.info("🛑 Shutting down auto-restart manager...")
            self.stop_bot()
            logger.info("="*70)
            logger.info("AUTO-RESTART MANAGER STOPPED")
            logger.info("="*70)


def main():
    """Entry point."""
    # Read restart interval from config
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from config import settings as cfg
        restart_interval = getattr(cfg, 'AUTO_RESTART_INTERVAL', 3600)
    except Exception:
        restart_interval = 3600  # Default: 1 hour
    
    # Create and run manager
    manager = AutoRestartManager(restart_interval_seconds=restart_interval)
    
    try:
        manager.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
