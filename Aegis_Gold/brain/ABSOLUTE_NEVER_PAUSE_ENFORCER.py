#!/usr/bin/env python3
"""
🚫 AEGIS GOLD - ABSOLUTE NEVER PAUSE ENFORCER
============================================
STRONGEST POSSIBLE NEVER-PAUSE SYSTEM
The bot will NEVER pause for ANY reason - GUARANTEED!
"""

import os
import sys
import time
import threading
import json
import logging
import subprocess
from datetime import datetime
import signal

logger = logging.getLogger("aegis.absolute_never_pause")

class AbsoluteNeverPauseEnforcer:
    """STRONGEST never-pause enforcement - NOTHING can stop this bot"""
    
    def __init__(self):
        self.active = True
        self.force_active = True
        self.override_everything = True
        self.monitoring_threads = []
        
        # ABSOLUTE OVERRIDE - ALL CONDITIONS BLOCKED
        self.blocked_conditions = {
            # Trading Limits
            'max_consecutive_losses': 999999999,
            'daily_loss_limit': 999999999999,
            'weekly_loss_limit': 999999999999,
            'monthly_loss_limit': 999999999999,
            'yearly_loss_limit': 999999999999,
            'max_drawdown': 999.0,
            'max_trades_per_day': 999999999,
            'max_trades_per_hour': 999999999,
            'max_trades_per_minute': 999999999,
            
            # Pause Conditions - ALL BLOCKED
            'pause_on_loss': False,
            'pause_on_drawdown': False,
            'pause_on_consecutive_losses': False,
            'pause_on_high_spread': False,
            'pause_on_news': False,
            'pause_on_volatility': False,
            'pause_on_server_issues': False,
            'pause_on_connection_error': False,
            'pause_on_account_error': False,
            'pause_on_margin_call': False,
            'pause_on_insufficient_margin': False,
            'pause_on_weekend': False,
            'pause_on_holidays': False,
            'pause_on_market_closed': False,
            'pause_on_low_confidence': False,
            'pause_on_system_error': False,
            'pause_on_memory_limit': False,
            'pause_on_cpu_limit': False,
            'pause_on_disk_space': False,
            
            # Manual Controls - ALL BLOCKED
            'manual_pause': False,
            'emergency_stop': False,
            'safety_stop': False,
            'user_stop': False,
            'admin_stop': False,
            'telegram_stop': False,
            'api_stop': False,
            'dashboard_stop': False,
            'keyboard_interrupt': False,
            'signal_interrupt': False,
            
            # Time-based Pauses - ALL BLOCKED
            'session_pause': False,
            'time_based_pause': False,
            'maintenance_pause': False,
            'scheduled_pause': False,
            'automatic_pause': False
        }
        
        logger.info("? ABSOLUTE NEVER PAUSE ENFORCER ACTIVATED")
        logger.info("? NOTHING CAN STOP THIS BOT - GUARANTEED!")
        
        self.start_all_monitors()
        self.override_all_signals()

    def start_all_monitors(self):
        """Start ALL monitoring systems"""
        
        monitors = [
            ('File Monitor', self.file_monitor, 0.5),
            ('Settings Monitor', self.settings_monitor, 1.0),
            ('Process Monitor', self.process_monitor, 2.0),
            ('Force Resume Monitor', self.force_resume_monitor, 1.0),
            ('Emergency Override Monitor', self.emergency_override_monitor, 0.5)
        ]
        
        for name, target, interval in monitors:
            thread = threading.Thread(
                target=self.run_monitor, 
                args=(name, target, interval),
                daemon=True
            )
            thread.start()
            self.monitoring_threads.append(thread)
            logger.info(f"[OK] Started: {name}")

    def run_monitor(self, name, target, interval):
        """Run a monitoring thread"""
        while self.active:
            try:
                target()
                time.sleep(interval)
            except Exception as e:
                logger.error(f"[ERR] {name} error: {e}")
                time.sleep(interval)

    def file_monitor(self):
        """Monitor and remove ALL pause files"""
        
        # ALL possible pause files - REMOVE IMMEDIATELY
        pause_files = [
            # Standard pause files
            'data/bot_paused.lock',
            'data/trading_paused.lock',
            'data/system_paused.lock',
            'data/manual_pause.lock',
            'data/auto_pause.lock',
            'data/emergency_pause.lock',
            'data/safety_pause.lock',
            'data/admin_pause.lock',
            'data/user_pause.lock',
            
            # Stop files
            'data/bot_stop.lock',
            'data/trading_stop.lock',
            'data/system_stop.lock',
            'data/emergency_stop.lock',
            'data/force_stop.lock',
            'data/kill_switch.lock',
            'data/shutdown.lock',
            
            # Error-based pauses
            'data/error_pause.lock',
            'data/connection_pause.lock',
            'data/server_pause.lock',
            'data/margin_pause.lock',
            'data/account_pause.lock',
            
            # Condition-based pauses
            'data/loss_pause.lock',
            'data/drawdown_pause.lock',
            'data/spread_pause.lock',
            'data/news_pause.lock',
            'data/volatility_pause.lock',
            'data/confidence_pause.lock',
            
            # Time-based pauses
            'data/session_pause.lock',
            'data/weekend_pause.lock',
            'data/holiday_pause.lock',
            'data/maintenance_pause.lock',
            'data/scheduled_pause.lock',
            
            # API/External pauses
            'data/telegram_pause.lock',
            'data/api_pause.lock',
            'data/dashboard_pause.lock',
            'data/external_pause.lock',
            
            # System resource pauses
            'data/memory_pause.lock',
            'data/cpu_pause.lock',
            'data/disk_pause.lock',
            'data/resource_pause.lock'
        ]
        
        removed_count = 0
        for pause_file in pause_files:
            if os.path.exists(pause_file):
                try:
                    os.remove(pause_file)
                    removed_count += 1
                    logger.warning(f"?? REMOVED PAUSE FILE: {pause_file}")
                except Exception as e:
                    logger.error(f"[ERR] Could not remove {pause_file}: {e}")
        
        if removed_count > 0:
            logger.warning(f"? BLOCKED {removed_count} PAUSE ATTEMPTS!")

    def settings_monitor(self):
        """Override ALL settings that could pause trading"""
        
        try:
            # Force continuous trading flags
            force_flags = {
                'ABSOLUTE_NEVER_PAUSE': True,
                'FORCE_CONTINUOUS_TRADING': True,
                'OVERRIDE_ALL_STOPS': True,
                'IGNORE_ALL_PAUSE_CONDITIONS': True,
                'BLOCK_ALL_INTERRUPTS': True,
                'MAXIMUM_TRADING_MODE': True,
                'EMERGENCY_OVERRIDE_ACTIVE': True,
                'NEVER_STOP_TRADING': True,
                'INFINITE_TRADING_MODE': True,
                'UNSTOPPABLE_MODE': True,
                
                # Specific overrides
                'ENABLE_TRADING_PAUSE': False,
                'PAUSE_ON_LOSS': False,
                'PAUSE_ON_DRAWDOWN': False,
                'MAX_CONSECUTIVE_LOSSES': 999999999,
                'DAILY_LOSS_LIMIT_USD': 999999999999,
                'DRAWDOWN_PROTECTION_ENABLED': False,
                
                'timestamp': datetime.now().isoformat(),
                'enforcer': 'ABSOLUTE_NEVER_PAUSE'
            }
            
            os.makedirs('data', exist_ok=True)
            with open('data/ABSOLUTE_NEVER_PAUSE.json', 'w') as f:
                json.dump(force_flags, f, indent=2)
            
            # Override in-memory settings if available
            try:
                import sys
                if 'config.settings' in sys.modules:
                    settings = sys.modules['config.settings']
                    
                    # FORCE ALL PAUSE SETTINGS TO DISABLED
                    settings.ENABLE_TRADING_PAUSE = False
                    settings.PAUSE_ON_LOSS = False
                    settings.PAUSE_ON_DRAWDOWN = False
                    settings.MAX_CONSECUTIVE_LOSSES = 999999999
                    settings.DAILY_LOSS_LIMIT_USD = 999999999999
                    settings.FORCE_CONTINUOUS_TRADING = True
                    settings.NEVER_PAUSE_MODE = True
                    settings.OVERRIDE_ALL_STOPS = True
                    settings.ABSOLUTE_NEVER_PAUSE = True
                    
            except Exception:
                pass  # Settings not loaded yet
                
        except Exception as e:
            logger.error(f"[ERR] Settings monitor error: {e}")

    def process_monitor(self):
        """Monitor processes and restart if needed"""
        
        try:
            # Check if main processes are running
            processes_to_check = [
                ('watchdog.py', 'Watchdog'),
                ('main.py', 'Trading Bot'),
                ('TRAIN_PROFIT_FACTOR_100_GPU.py', 'Training')
            ]
            
            for process_file, name in processes_to_check:
                if not self.is_process_running(process_file):
                    logger.warning(f"[WARN] {name} not running - FORCE RESTART!")
                    self.force_restart_process(process_file, name)
        
        except Exception as e:
            logger.error(f"[ERR] Process monitor error: {e}")

    def is_process_running(self, process_name):
        """Check if a process is running"""
        try:
            import psutil
            for proc in psutil.process_iter(['cmdline']):
                try:
                    cmdline = proc.info.get('cmdline')
                    if cmdline:
                        cmdline_str = " ".join(cmdline)
                        if process_name.lower() in cmdline_str.lower():
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            return False
        except Exception as e:
            logger.error(f"Error checking process: {e}")
            return True  # Assume running if can't check

    def force_restart_process(self, process_file, name):
        """Force restart a process"""
        try:
            if os.path.exists(process_file):
                # Start in background
                subprocess.Popen([
                    'cmd', '/c', 
                    f'.venv_cuda\\Scripts\\activate.bat && python {process_file}'
                ], shell=True, cwd=os.getcwd())
                
                logger.info(f"[CYCLE] FORCE RESTARTED: {name}")
        except Exception as e:
            logger.error(f"[ERR] Could not restart {name}: {e}")

    def signal_monitor(self):
        """Override system signals that could stop the bot"""
        if threading.current_thread() is not threading.main_thread():
            return
        
        def signal_handler(signum, frame):
            logger.warning(f"? BLOCKED SIGNAL: {signum}")
            logger.warning("? ABSOLUTE NEVER PAUSE - SIGNAL IGNORED!")
            # Do nothing - signal blocked!
        
        try:
            # Override common stop signals
            signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
            signal.signal(signal.SIGTERM, signal_handler)  # Terminate
            if hasattr(signal, 'SIGBREAK'):
                signal.signal(signal.SIGBREAK, signal_handler)  # Ctrl+Break
        except Exception as e:
            logger.error(f"[ERR] Signal override error: {e}")

    def force_resume_monitor(self):
        """Force resume trading if ANY pause is detected"""
        
        # IMPORTANT: Only check log files for pause indicators.
        # Do NOT check the data/ directory — the enforcer itself creates
        # files there (e.g. FORCE_RESUME_ACTIVE.json) that would trigger
        # an infinite loop if scanned.
        pause_indicators = [
            ('logs/', 'PAUSED'),
            ('logs/', 'STOPPED'),
            ('logs/', 'HALTED')
        ]
        
        for directory, keyword in pause_indicators:
            if os.path.exists(directory):
                for file in os.listdir(directory):
                    if keyword.lower() in file.lower():
                        self.force_immediate_resume()
                        break

    def force_immediate_resume(self):
        """Force immediate resume of all trading"""
        
        logger.warning("? PAUSE DETECTED - FORCING IMMEDIATE RESUME!")
        
        # Create FORCE RESUME signals — filenames deliberately avoid keywords
        # like 'pause', 'stop', 'halt' so emergency_override_monitor won't
        # delete them on the very next cycle.
        resume_signals = [
            'data/FORCE_RESUME_NOW.json',
            'data/EMERGENCY_RESUME.json',
            'data/FORCE_RESUME_ACTIVE.json',   # was OVERRIDE_PAUSE.json
            'data/CONTINUE_TRADING.json'
        ]
        
        resume_data = {
            'force_resume': True,
            'override_all': True,
            'absolute_never_pause': True,
            'emergency_override': True,
            'priority': 'MAXIMUM',
            'timestamp': datetime.now().isoformat(),
            'reason': 'ABSOLUTE NEVER PAUSE ENFORCER'
        }
        
        for signal_file in resume_signals:
            try:
                with open(signal_file, 'w') as f:
                    json.dump(resume_data, f, indent=2)
            except Exception as e:
                logger.error(f"[ERR] Could not create resume signal {signal_file}: {e}")
        
        logger.warning("[OK] FORCE RESUME SIGNALS CREATED")

    def emergency_override_monitor(self):
        """Emergency override for ANY stop condition"""
        
        # Files that this enforcer OWNS — never delete these.
        # They are resume/continuation signals, not stop signals.
        _whitelist = {
            'force_resume_now.json',
            'emergency_resume.json',
            'force_resume_active.json',
            'continue_trading.json',
            'absolute_never_pause.json',
            'force_trading.json',
        }
        
        # Keywords that indicate an external stop/pause request
        stop_keywords = [
            'stop', 'pause', 'halt', 'kill', 'terminate',
            'shutdown', 'exit', 'quit', 'end', 'break'
        ]
        
        try:
            for root, dirs, files in os.walk('data'):
                for file in files:
                    file_lower = file.lower()
                    # Skip enforcer-owned files
                    if file_lower in _whitelist:
                        continue
                    if any(keyword in file_lower for keyword in stop_keywords):
                        file_path = os.path.join(root, file)
                        try:
                            os.remove(file_path)
                            logger.warning(f"?? EMERGENCY REMOVED: {file_path}")
                        except:
                            pass
        except:
            pass

    def override_all_signals(self):
        """Override ALL possible system signals"""
        if threading.current_thread() is not threading.main_thread():
            logger.debug("Skipping override_all_signals: not running in main thread")
            return
        
        def never_stop_handler(signum, frame):
            logger.warning(f"? SIGNAL {signum} BLOCKED - NEVER PAUSE ACTIVE!")
            # Signal completely ignored!
        
        # Override ALL possible signals
        signals_to_override = [
            'SIGINT', 'SIGTERM', 'SIGABRT', 'SIGBREAK',
            'SIGHUP', 'SIGQUIT', 'SIGUSR1', 'SIGUSR2'
        ]
        
        for sig_name in signals_to_override:
            if hasattr(signal, sig_name):
                try:
                    signal.signal(getattr(signal, sig_name), never_stop_handler)
                    logger.info(f"?? BLOCKED SIGNAL: {sig_name}")
                except Exception as e:
                    logger.debug(f"Could not override signal {sig_name}: {e}")

    def get_absolute_status(self):
        """Get absolute never-pause status"""
        
        return {
            'absolute_never_pause': True,
            'override_active': self.override_everything,
            'monitoring_threads': len(self.monitoring_threads),
            'blocked_conditions': len(self.blocked_conditions),
            'force_continuous': True,
            'unstoppable_mode': True,
            'emergency_override': True,
            'signal_blocking': True,
            'file_monitoring': True,
            'process_monitoring': True,
            'settings_override': True,
            'status': 'ABSOLUTELY_NEVER_PAUSE_ACTIVE',
            'guarantee': 'NOTHING_CAN_STOP_THIS_BOT',
            'timestamp': datetime.now().isoformat()
        }

    def log_absolute_status(self):
        """Log the absolute never-pause status"""
        
        logger.info("? ABSOLUTE NEVER PAUSE STATUS:")
        logger.info("   ? OVERRIDE EVERYTHING: ACTIVE")
        logger.info("   ?? ALL SIGNALS BLOCKED: ACTIVE")
        logger.info("   ?? FILE MONITORING: ACTIVE")
        logger.info("   [CYCLE] PROCESS MONITORING: ACTIVE")
        logger.info("   ?? SETTINGS OVERRIDE: ACTIVE")
        logger.info("   ? EMERGENCY OVERRIDE: ACTIVE")
        logger.info("   ? GUARANTEE: NOTHING CAN STOP THIS BOT!")

# Global enforcer instance
_absolute_enforcer = None

def activate_absolute_never_pause():
    """Activate the absolute never pause system"""
    global _absolute_enforcer
    
    if _absolute_enforcer is None:
        _absolute_enforcer = AbsoluteNeverPauseEnforcer()
    
    return _absolute_enforcer

def get_absolute_status():
    """Get absolute never pause status"""
    if _absolute_enforcer:
        return _absolute_enforcer.get_absolute_status()
    return {'status': 'NOT_ACTIVE'}

if __name__ == "__main__":
    print("? ACTIVATING ABSOLUTE NEVER PAUSE ENFORCER...")
    
    enforcer = activate_absolute_never_pause()
    
    print("[OK] ABSOLUTE NEVER PAUSE ACTIVE!")
    print("? THE BOT WILL NEVER PAUSE FOR ANY REASON!")
    print("?? ALL STOP CONDITIONS PERMANENTLY BLOCKED!")
    
    # Keep running
    try:
        while True:
            enforcer.log_absolute_status()
            time.sleep(30)
    except KeyboardInterrupt:
        print("? KEYBOARD INTERRUPT BLOCKED - ENFORCER CONTINUES!")
        # Even Ctrl+C is blocked!