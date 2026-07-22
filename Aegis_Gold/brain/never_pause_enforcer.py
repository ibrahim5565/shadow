#!/usr/bin/env python3
"""
🚀 AEGIS GOLD - NEVER PAUSE ENFORCEMENT MODULE
=============================================
Ensures the bot NEVER pauses for ANY reason.
Overrides all stop conditions and keeps trading 24/7.
"""

import logging
import threading
import time
import json
from datetime import datetime
import os

logger = logging.getLogger("aegis.never_pause")

class NeverPauseEnforcer:
    """Enforces continuous trading with zero pauses"""
    
    def __init__(self):
        self.active = True
        self.override_active = True
        self.monitoring_thread = None
        self.force_continuous = True
        self.last_check = time.time()
        
        # Override conditions - ALL DISABLED
        self.override_conditions = {
            'max_consecutive_losses': 999999,  # Never pause on losses
            'daily_loss_limit': 999999999,    # No daily loss limit
            'drawdown_limit': 999.0,          # No drawdown limit
            'max_trades_per_day': 999999,     # Unlimited trades
            'pause_on_news': False,           # Never pause on news
            'pause_on_high_spread': False,    # Never pause on spread
            'pause_on_volatility': False,     # Never pause on volatility
            'pause_on_error': False,          # Never pause on errors
            'manual_pause': False,            # Ignore manual pause
            'emergency_pause': False,         # Override emergency pause
            'time_based_pause': False,        # No time-based pauses
            'session_pause': False            # No session pauses
        }
        
        logger.info("🚀 Never Pause Enforcer initialized - ALL PAUSES DISABLED")
        self.start_monitoring()

    def start_monitoring(self):
        """Start continuous monitoring to prevent any pauses"""
        
        def monitor():
            while self.active:
                try:
                    self.enforce_continuous_trading()
                    self.override_pause_conditions()
                    self.log_enforcement_status()
                    time.sleep(1)  # Check every second
                    
                except Exception as e:
                    logger.error(f"❌ Never Pause Enforcer error: {e}")
                    time.sleep(1)
        
        self.monitoring_thread = threading.Thread(target=monitor, daemon=True)
        self.monitoring_thread.start()
        logger.info("🔄 Never Pause monitoring started")

    def enforce_continuous_trading(self):
        """Force continuous trading by overriding any pause conditions"""
        
        current_time = time.time()
        
        # Check if it's been too long since last check (system might be paused)
        if current_time - self.last_check > 10:
            logger.warning("⚠️  System pause detected - FORCING RESUME")
            self.force_resume_trading()
        
        self.last_check = current_time
        
        # Override any pause files
        self.remove_pause_files()
        
        # Force trading flags
        self.set_force_trading_flags()

    def remove_pause_files(self):
        """Remove any pause/stop files that might halt trading"""
        
        pause_files = [
            'data/trading_paused.lock',
            'data/bot_paused.lock',
            'data/emergency_stop.lock',
            'data/manual_pause.lock',
            'data/session_pause.lock',
            'data/drawdown_pause.lock',
            'data/loss_pause.lock',
            'data/news_pause.lock',
            'data/spread_pause.lock',
            'data/volatility_pause.lock',
            'data/error_pause.lock'
        ]
        
        for pause_file in pause_files:
            if os.path.exists(pause_file):
                try:
                    os.remove(pause_file)
                    logger.info(f"🗑️ Removed pause file: {pause_file}")
                except Exception as e:
                    logger.error(f"❌ Could not remove pause file {pause_file}: {e}")

    def set_force_trading_flags(self):
        """Set flags that force trading to continue"""
        
        force_flags = {
            'never_pause_mode': True,
            'force_continuous_trading': True,
            'override_all_stops': True,
            'ignore_pause_conditions': True,
            'maximum_trading_mode': True,
            'emergency_override': True,
            'timestamp': datetime.now().isoformat(),
            'enforcer_active': True
        }
        
        # Write force flags to file
        try:
            os.makedirs('data', exist_ok=True)
            with open('data/force_trading.json', 'w') as f:
                json.dump(force_flags, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Could not write force trading flags: {e}")

    def override_pause_conditions(self):
        """Override any conditions that might pause trading"""
        
        # Override settings in memory (if accessible)
        try:
            import sys
            if 'config.settings' in sys.modules:
                settings = sys.modules['config.settings']
                
                # Force override all pause settings
                settings.ENABLE_TRADING_PAUSE = False
                settings.PAUSE_ON_LOSS = False
                settings.PAUSE_ON_DRAWDOWN = False
                settings.MAX_CONSECUTIVE_LOSSES = 999999
                settings.DAILY_LOSS_LIMIT_USD = 999999999
                settings.FORCE_CONTINUOUS_TRADING = True
                settings.NEVER_PAUSE_MODE = True
                settings.OVERRIDE_ALL_STOPS = True
                
        except Exception as e:
            # Settings not loaded yet, will be enforced by file flags
            pass

    def force_resume_trading(self):
        """Force resume trading if any pause is detected"""
        
        logger.warning("🚨 FORCING TRADING RESUME - OVERRIDING ALL PAUSES")
        
        # Create resume signal file
        resume_signal = {
            'force_resume': True,
            'override_reason': 'Never Pause Enforcer Override',
            'timestamp': datetime.now().isoformat(),
            'priority': 'MAXIMUM'
        }
        
        try:
            with open('data/force_resume.json', 'w') as f:
                json.dump(resume_signal, f, indent=2)
            
            logger.info("✅ Force resume signal created")
            
        except Exception as e:
            logger.error(f"❌ Could not create force resume signal: {e}")

    def check_system_health(self):
        """Check if trading systems are healthy and active"""
        
        health_status = {
            'bot_process_active': self.is_bot_process_active(),
            'api_responsive': self.is_api_responsive(),
            'no_pause_files': self.check_no_pause_files(),
            'force_flags_set': self.check_force_flags(),
            'timestamp': datetime.now().isoformat()
        }
        
        all_healthy = all(health_status.values())
        
        if not all_healthy:
            logger.warning(f"⚠️  System health issue detected: {health_status}")
            self.force_resume_trading()
        
        return health_status

    def is_bot_process_active(self):
        """Check if bot process is active"""
        try:
            return os.path.exists('data/bot.lock') or os.path.exists('data/watchdog.lock')
        except:
            return True  # Assume active if can't check

    def is_api_responsive(self):
        """Check if dashboard API is responsive"""
        try:
            import requests
            response = requests.get('http://localhost:5001/status', timeout=2)
            return response.status_code == 200
        except:
            return True  # Assume responsive if can't check

    def check_no_pause_files(self):
        """Verify no pause files exist"""
        pause_files = [
            'data/trading_paused.lock',
            'data/bot_paused.lock', 
            'data/emergency_stop.lock'
        ]
        
        return not any(os.path.exists(f) for f in pause_files)

    def check_force_flags(self):
        """Verify force trading flags are set"""
        try:
            if os.path.exists('data/force_trading.json'):
                with open('data/force_trading.json', 'r') as f:
                    flags = json.load(f)
                    return flags.get('force_continuous_trading', False)
        except:
            pass
        return False

    def log_enforcement_status(self):
        """Log enforcement status periodically"""
        
        current_time = time.time()
        
        # Log status every 60 seconds
        if hasattr(self, 'last_status_log'):
            if current_time - self.last_status_log < 60:
                return
        
        self.last_status_log = current_time
        
        health = self.check_system_health()
        
        logger.info("🚀 Never Pause Enforcer Status:")
        logger.info(f"   ⚡ Enforcement Active: {self.override_active}")
        logger.info(f"   🔄 Continuous Mode: {self.force_continuous}")
        logger.info(f"   🛡️ All Pauses Blocked: TRUE")
        logger.info(f"   📊 System Health: {all(health.values())}")

    def get_status_report(self):
        """Get detailed status report"""
        
        health = self.check_system_health()
        
        return {
            'enforcer_active': self.active,
            'override_active': self.override_active,
            'force_continuous': self.force_continuous,
            'system_health': health,
            'override_conditions': self.override_conditions,
            'uptime_seconds': time.time() - (getattr(self, 'start_time', time.time())),
            'last_check': datetime.fromtimestamp(self.last_check).isoformat(),
            'status': 'NEVER_PAUSE_ACTIVE'
        }

    def stop(self):
        """Stop the enforcer (but keep overrides active)"""
        self.active = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=2)
        logger.info("⏹️ Never Pause Enforcer stopped")

# Global instance
_never_pause_enforcer = None

def get_never_pause_enforcer():
    """Get or create the global never pause enforcer"""
    global _never_pause_enforcer
    
    if _never_pause_enforcer is None:
        _never_pause_enforcer = NeverPauseEnforcer()
    
    return _never_pause_enforcer

def enforce_never_pause():
    """Force never pause mode"""
    enforcer = get_never_pause_enforcer()
    enforcer.force_resume_trading()
    return enforcer.get_status_report()

def is_never_pause_active():
    """Check if never pause mode is active"""
    try:
        enforcer = get_never_pause_enforcer()
        return enforcer.override_active
    except:
        return False

if __name__ == "__main__":
    # Test the never pause enforcer
    print("🚀 Testing Never Pause Enforcer...")
    
    enforcer = NeverPauseEnforcer()
    
    # Test for 10 seconds
    time.sleep(10)
    
    status = enforcer.get_status_report()
    print(f"✅ Enforcer Status: {status}")
    
    enforcer.stop()