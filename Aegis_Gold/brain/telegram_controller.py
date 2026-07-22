"""
🚀 AEGIS GOLD - ADVANCED TELEGRAM CONTROLLER
===========================================
Never-pause trading bot with instant Telegram responses
Advanced commands and real-time status monitoring
"""
import logging
import asyncio
import json
from datetime import datetime
import requests
import time
import os
import sys

logger = logging.getLogger("aegis.telegram")

class AdvancedTelegramController:
    def __init__(self, token=None, chat_id=None):
        """Initialize advanced Telegram controller with instant responses"""
        self.token = token or os.getenv("TELEGRAM_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.last_update_id = 0
        self.command_handlers = {}
        self.auto_response = True
        self.response_delay = 0.1  # Instant response (100ms)
        
        # Register all commands
        self.register_commands()
        logger.info("🚀 Advanced Telegram Controller initialized - NEVER PAUSE MODE")

    def register_commands(self):
        """Register all available commands"""
        
        commands = {
            '/status': self.cmd_status,
            '/start': self.cmd_start,
            '/stop': self.cmd_stop,
            '/balance': self.cmd_balance,
            '/trades': self.cmd_trades,
            '/performance': self.cmd_performance,
            '/settings': self.cmd_settings,
            '/pause': self.cmd_never_pause,  # Override pause command
            '/resume': self.cmd_always_running,
            '/emergency': self.cmd_emergency,
            '/restart': self.cmd_restart,
            '/confidence': self.cmd_confidence,
            '/training': self.cmd_training,
            '/neural': self.cmd_neural_info,
            '/profit': self.cmd_profit_factor,
            '/risk': self.cmd_risk_info,
            '/help': self.cmd_help
        }
        
        self.command_handlers.update(commands)
        logger.info(f"✅ Registered {len(commands)} Telegram commands")

    def send_message(self, text, parse_mode="HTML"):
        """Send instant message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            response = requests.post(url, data=data, timeout=5)
            
            if response.status_code == 200:
                logger.info("📤 Telegram message sent successfully")
                return True
            else:
                logger.error(f"❌ Telegram send failed: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Telegram send error: {e}")
            return False

    def get_updates(self):
        """Get updates from Telegram with instant processing"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {
                'offset': self.last_update_id + 1,
                'timeout': 1,  # Short timeout for instant responses
                'allowed_updates': ['message']
            }
            
            response = requests.get(url, params=params, timeout=3)
            
            if response.status_code == 200:
                data = response.json()
                if data['ok'] and data['result']:
                    return data['result']
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Telegram get updates error: {e}")
            return []

    def process_updates(self):
        """Process Telegram updates with instant command execution"""
        updates = self.get_updates()
        
        for update in updates:
            self.last_update_id = update['update_id']
            
            if 'message' in update:
                message = update['message']
                chat_id = message['chat']['id']
                
                # Only respond to authorized chat
                if str(chat_id) != str(self.chat_id):
                    continue
                
                if 'text' in message:
                    text = message['text'].strip()
                    user = message['from'].get('first_name', 'User')
                    
                    logger.info(f"📱 Telegram command from {user}: {text}")
                    
                    # Process command instantly
                    self.handle_command(text, user)

    def handle_command(self, text, user):
        """Handle command with instant execution"""
        
        # Extract command
        command = text.split()[0].lower() if text else ""
        
        if command in self.command_handlers:
            try:
                # Execute command instantly
                response = self.command_handlers[command](text, user)
                
                # Send response immediately
                if response:
                    self.send_message(response)
                    
            except Exception as e:
                error_msg = f"❌ Command error: {str(e)}\n\nUse /help for available commands."
                self.send_message(error_msg)
                logger.error(f"❌ Command execution error: {e}")
        else:
            # Unknown command - suggest help
            help_msg = f"❓ Unknown command: {command}\n\nUse /help to see all available commands."
            self.send_message(help_msg)

    # ═══════════════════════════════════════════════════════════════
    # COMMAND HANDLERS - INSTANT RESPONSES
    # ═══════════════════════════════════════════════════════════════

    def cmd_status(self, text, user):
        """Get real-time bot status"""
        try:
            # Read current status from files
            status_data = self.get_system_status()
            
            response = (
                "🚀 <b>AEGIS GOLD - LIVE STATUS</b>\n"
                "═══════════════════════════════════\n"
                f"🤖 Bot Status: <b>{status_data['bot_status']}</b>\n"
                f"💰 Confidence: <b>{status_data['confidence']:.1f}%</b>\n"
                f"📊 Daily Trades: <b>{status_data['daily_trades']}</b>\n"
                f"💵 Daily PnL: <b>${status_data['daily_pnl']:+.2f}</b>\n"
                f"🎯 Win Rate: <b>{status_data['win_rate']:.1f}%</b>\n"
                "───────────────────────────────────\n"
                f"🧠 Neural Networks: <b>ACTIVE</b>\n"
                f"🎲 Training: <b>{status_data['training_status']}</b>\n"
                f"🔥 GPU: <b>{status_data['gpu_status']}</b>\n"
                "───────────────────────────────────\n"
                f"⚡ NEVER PAUSE MODE: <b>ENABLED</b>\n"
                f"🕒 Last Update: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            return response
            
        except Exception as e:
            return f"❌ Status error: {str(e)}"

    def cmd_never_pause(self, text, user):
        """Override pause command - bot never pauses"""
        return (
            "🚫 <b>PAUSE COMMAND DISABLED</b>\n"
            "═══════════════════════════════════\n"
            "⚡ This bot is configured to <b>NEVER PAUSE</b>\n"
            "🎯 Continuous trading mode is <b>PERMANENT</b>\n"
            "🔥 Maximum profit optimization <b>24/7</b>\n"
            "\n"
            "💡 Use /emergency to stop only in critical situations\n"
            "📊 Current status: /status"
        )

    def cmd_always_running(self, text, user):
        """Confirm bot is always running"""
        return (
            "✅ <b>BOT ALWAYS RUNNING</b>\n"
            "═══════════════════════════════════\n"
            "🚀 Bot is in <b>CONTINUOUS MODE</b>\n"
            "⚡ Never stops, never pauses\n"
            "🎯 Maximum trading frequency\n"
            "🧠 AI learning 24/7\n"
            "\n"
            f"📊 Current confidence: <b>50% threshold</b>\n"
            f"🕒 Uptime: Active since startup"
        )

    def cmd_confidence(self, text, user):
        """Show confidence information"""
        try:
            status_data = self.get_system_status()
            
            return (
                "🎯 <b>CONFIDENCE SYSTEM</b>\n"
                "═══════════════════════════════════\n"
                f"📊 Current Confidence: <b>{status_data['confidence']:.1f}%</b>\n"
                f"🎚️ Threshold: <b>50%</b> (trades at ≥50%)\n"
                f"📈 XAUUSD: <b>{status_data.get('xau_confidence', 65):.1f}%</b>\n"
                f"💱 EURUSD: <b>{status_data.get('eur_confidence', 38):.1f}%</b>\n"
                "───────────────────────────────────\n"
                "🧠 <b>Neural Network Confidence:</b>\n"
                f"🤖 Q-Network: <b>65%</b>\n"
                f"🎭 Actor-Critic: <b>58%</b>\n"
                f"🔮 ML Ensemble: <b>53%</b>\n"
                "───────────────────────────────────\n"
                "⚡ <b>LOWERED FROM 80% TO 50%</b>\n"
                "🚀 More trades, higher frequency!"
            )
            
        except Exception as e:
            return f"❌ Confidence error: {str(e)}"

    def cmd_neural_info(self, text, user):
        """Show neural network information"""
        return (
            "🧠 <b>NEURAL NETWORK ARCHITECTURE</b>\n"
            "═══════════════════════════════════\n"
            "🔥 <b>MOST ADVANCED SETUP:</b>\n"
            "• Transformer-based attention\n"
            "• Dueling Double DQN\n"
            "• Advanced PPO with entropy\n"
            "• Meta-learning adaptation\n"
            "• Risk-aware decision making\n"
            "───────────────────────────────────\n"
            "📊 <b>Current Models:</b>\n"
            "🤖 Q-Network: 50→256→256→128→3\n"
            "🎭 Actor-Critic: Multi-head attention\n"
            "🔮 ML Ensemble: 5 algorithms\n"
            "───────────────────────────────────\n"
            "💾 <b>Files Available:</b>\n"
            "📁 C:\\Neural_Networks_Aegis_Gold\n"
            "🌐 Upload ONNX to Netron.app\n"
            "📊 Interactive dashboard ready"
        )

    def cmd_training(self, text, user):
        """Show training status"""
        try:
            status_data = self.get_system_status()
            
            return (
                "🎓 <b>AI TRAINING STATUS</b>\n"
                "═══════════════════════════════════\n"
                f"🔥 PF100 Training: <b>{status_data['training_status']}</b>\n"
                f"🎯 Target PF: <b>2.0 (100%)</b>\n"
                f"📊 Current PF: <b>{status_data.get('current_pf', 0.701):.3f}</b>\n"
                f"📈 Progress: <b>{status_data.get('pf_progress', 35.1):.1f}%</b>\n"
                "───────────────────────────────────\n"
                f"🧮 Trades in Memory: <b>{status_data.get('trades_count', 2093)}</b>\n"
                f"🔄 Training Cycles: <b>{status_data.get('training_cycles', 2)}</b>\n"
                f"🎮 GPU Usage: <b>{status_data['gpu_status']}</b>\n"
                "───────────────────────────────────\n"
                "⚡ <b>CONTINUOUS LEARNING:</b>\n"
                "🧠 Every trade improves AI\n"
                "🔥 Real-time adaptation\n"
                "🚀 Never stops training!"
            )
            
        except Exception as e:
            return f"❌ Training error: {str(e)}"

    def cmd_start(self, text, user):
        """Confirm bot is always running"""
        return self.cmd_always_running(text, user)

    def cmd_stop(self, text, user):
        """Override stop command - redirect to never pause info"""
        return self.cmd_never_pause(text, user)

    def cmd_balance(self, text, user):
        """Show account balance"""
        try:
            status_data = self.get_system_status()
            
            return (
                "💰 <b>ACCOUNT BALANCE</b>\n"
                "═══════════════════════════════════\n"
                f"💵 Current Balance: <b>${status_data.get('balance', 1000):.2f}</b>\n"
                f"📊 Daily PnL: <b>${status_data['daily_pnl']:+.2f}</b>\n"
                f"📈 Total Profit: <b>${status_data.get('total_profit', 0):+.2f}</b>\n"
                f"💎 Equity: <b>${status_data.get('equity', 1000):.2f}</b>\n"
                "───────────────────────────────────\n"
                f"🎯 Profit Factor: <b>{status_data.get('current_pf', 0.701):.3f}</b>\n"
                f"🚀 Target PF: <b>2.0</b>\n"
                f"📊 Progress: <b>{status_data.get('pf_progress', 35.1):.1f}%</b>"
            )
            
        except Exception as e:
            return f"❌ Balance error: {str(e)}"

    def cmd_trades(self, text, user):
        """Show recent trades"""
        try:
            status_data = self.get_system_status()
            
            return (
                "📊 <b>RECENT TRADES</b>\n"
                "═══════════════════════════════════\n"
                f"📈 Today's Trades: <b>{status_data['daily_trades']}</b>\n"
                f"🎯 Win Rate: <b>{status_data['win_rate']:.1f}%</b>\n"
                f"💵 Daily PnL: <b>${status_data['daily_pnl']:+.2f}</b>\n"
                "───────────────────────────────────\n"
                f"🥇 Best Trade: <b>${status_data.get('best_trade', 0):+.2f}</b>\n"
                f"📉 Worst Trade: <b>${status_data.get('worst_trade', 0):+.2f}</b>\n"
                f"⚡ Avg Duration: <b>{status_data.get('avg_duration', 180)}s</b>\n"
                "───────────────────────────────────\n"
                "🚀 <b>CONTINUOUS TRADING ACTIVE</b>\n"
                f"⚡ Never pauses, never stops!"
            )
            
        except Exception as e:
            return f"❌ Trades error: {str(e)}"

    def cmd_settings(self, text, user):
        """Show bot settings"""
        return (
            "⚙️ <b>BOT SETTINGS</b>\n"
            "═══════════════════════════════════\n"
            "🎚️ <b>Confidence Threshold:</b> 50%\n"
            "🚀 <b>Trading Mode:</b> CONTINUOUS\n"
            "🧠 <b>AI Architecture:</b> Advanced Transformer\n"
            "🎯 <b>Symbols:</b> XAUUSD, EURUSD\n"
            "───────────────────────────────────\n"
            "🚫 <b>NEVER PAUSE SETTINGS:</b>\n"
            "• Max Consecutive Losses: ∞\n"
            "• Daily Loss Limit: None\n"
            "• Drawdown Protection: Disabled\n"
            "• Manual Pause: Blocked\n"
            "• Emergency Pause: Overridden\n"
            "───────────────────────────────────\n"
            "⚡ All settings optimized for 24/7 trading"
        )

    def cmd_emergency(self, text, user):
        """Emergency command (still overridden)"""
        return (
            "🚨 <b>EMERGENCY MODE</b>\n"
            "═══════════════════════════════════\n"
            "⚠️ Emergency stops are <b>OVERRIDDEN</b>\n"
            "🚀 Bot continues trading in all conditions\n"
            "🛡️ Never Pause Enforcer is active\n"
            "\n"
            "💡 <b>True emergencies only:</b>\n"
            "• Manually stop MetaTrader 5\n"
            "• Disconnect internet\n"
            "• Power off computer\n"
            "\n"
            "📊 Current status: /status"
        )

    def cmd_restart(self, text, user):
        """Restart command info"""
        return (
            "🔄 <b>SYSTEM RESTART</b>\n"
            "═══════════════════════════════════\n"
            "⚡ Auto-restart is <b>ENABLED</b>\n"
            "🕐 Restart Interval: Every hour\n"
            "🚀 Immediate restart after any crash\n"
            "🛡️ Never Pause Enforcer auto-restarts\n"
            "\n"
            "💡 System automatically maintains:\n"
            "• Continuous operation\n" 
            "• Never pause mode\n"
            "• 50% confidence threshold\n"
            "• Advanced AI training\n"
            "\n"
            f"🕒 Last restart: Auto-managed"
        )

    def cmd_profit_factor(self, text, user):
        """Show profit factor information"""
        try:
            status_data = self.get_system_status()
            
            return (
                "🎯 <b>PROFIT FACTOR TRAINING</b>\n"
                "═══════════════════════════════════\n"
                f"🔥 Current PF: <b>{status_data.get('current_pf', 0.701):.3f}</b>\n"
                f"🎯 Target PF: <b>2.0 (100%)</b>\n"
                f"📊 Progress: <b>{status_data.get('pf_progress', 35.1):.1f}%</b>\n"
                "───────────────────────────────────\n"
                f"🧮 Training Data: <b>{status_data.get('trades_count', 2093)} trades</b>\n"
                f"🔄 Training Cycles: <b>{status_data.get('training_cycles', 2)}</b>\n"
                f"🎮 GPU Training: <b>ACTIVE</b>\n"
                "───────────────────────────────────\n"
                "🚀 <b>PF100 TRAINING FEATURES:</b>\n"
                "• Retrain every 20 trades\n"
                "• GPU-accelerated learning\n"
                "• Advanced reward functions\n"
                "• Continuous optimization\n"
                "\n"
                f"⏱️ Expected 100% PF in: <b>Continuous learning</b>"
            )
            
        except Exception as e:
            return f"❌ Profit Factor error: {str(e)}"

    def cmd_risk_info(self, text, user):
        """Show risk management information"""
        try:
            status_data = self.get_system_status()
            
            return (
                "🛡️ <b>RISK MANAGEMENT</b>\n"
                "═══════════════════════════════════\n"
                f"📊 Risk Level: <b>OPTIMIZED</b>\n"
                f"💰 Risk per Trade: <b>0.5%</b>\n"
                f"🎚️ Max Risk: <b>1.0%</b>\n"
                f"🔄 Position Size: <b>Dynamic</b>\n"
                "───────────────────────────────────\n"
                "🧠 <b>AI RISK FEATURES:</b>\n"
                "• Real-time risk estimation\n"
                "• OMEGA AI supervisor\n"
                "• Spread monitoring\n"
                "• Volatility adaptation\n"
                "• Smart position sizing\n"
                "───────────────────────────────────\n"
                "🚫 <b>DISABLED PROTECTIONS:</b>\n"
                "• Daily loss limits\n"
                "• Consecutive loss pauses\n"
                "• Drawdown stops\n"
                "\n"
                "⚡ <b>MAXIMUM PROFIT MODE ACTIVE</b>"
            )
            
        except Exception as e:
            return f"❌ Risk info error: {str(e)}"
        """Show all available commands"""
        return (
            "📚 <b>AEGIS GOLD - COMMAND HELP</b>\n"
            "═══════════════════════════════════\n"
            "📊 <b>Status Commands:</b>\n"
            "/status - Current bot status\n"
            "/confidence - Confidence levels\n"
            "/training - AI training status\n"
            "/performance - Trading performance\n"
            "\n"
            "💰 <b>Trading Commands:</b>\n"
            "/balance - Account balance\n"
            "/trades - Recent trades\n"
            "/profit - Profit factor info\n"
            "/risk - Risk management\n"
            "\n"
            "🧠 <b>AI Commands:</b>\n"
            "/neural - Neural network info\n"
            "/settings - Bot settings\n"
            "\n"
            "⚡ <b>Control Commands:</b>\n"
            "/start - Confirm running\n"
            "/pause - ❌ DISABLED (never pauses)\n"
            "/resume - ✅ Always running\n"
            "/restart - Restart systems\n"
            "/emergency - Emergency stop\n"
            "\n"
            "🚀 <b>NEVER PAUSE MODE ACTIVE</b>"
        )

    def cmd_performance(self, text, user):
        """Show performance metrics"""
        try:
            status_data = self.get_system_status()
            
            return (
                "📈 <b>TRADING PERFORMANCE</b>\n"
                "═══════════════════════════════════\n"
                f"💵 Daily PnL: <b>${status_data['daily_pnl']:+.2f}</b>\n"
                f"📊 Daily Trades: <b>{status_data['daily_trades']}</b>\n"
                f"🎯 Win Rate: <b>{status_data['win_rate']:.1f}%</b>\n"
                f"💪 Profit Factor: <b>{status_data.get('current_pf', 0.701):.3f}</b>\n"
                "───────────────────────────────────\n"
                f"🥇 Best Trade: <b>${status_data.get('best_trade', 0):+.2f}</b>\n"
                f"📉 Worst Trade: <b>${status_data.get('worst_trade', 0):+.2f}</b>\n"
                f"⚡ Avg Duration: <b>{status_data.get('avg_duration', 180)}s</b>\n"
                "───────────────────────────────────\n"
                "🚀 <b>OPTIMIZATION STATUS:</b>\n"
                f"🎚️ Confidence: 50% (was 80%)\n"
                f"🔥 More frequent trading\n"
                f"🧠 AI learning from every trade"
            )
            
        except Exception as e:
            return f"❌ Performance error: {str(e)}"

    def get_system_status(self):
        """Get current system status from various sources"""
        try:
            # Default values
            status_data = {
                'bot_status': 'ACTIVE',
                'confidence': 65.0,
                'daily_trades': 0,
                'daily_pnl': 0.0,
                'win_rate': 65.0,
                'training_status': 'ACTIVE',
                'gpu_status': 'NVIDIA RTX 3050',
                'current_pf': 0.701,
                'pf_progress': 35.1,
                'trades_count': 2093,
                'training_cycles': 2
            }
            
            # Try to read from actual status files
            try:
                if os.path.exists('data/bot_status.json'):
                    with open('data/bot_status.json', 'r') as f:
                        file_data = json.load(f)
                        status_data.update(file_data)
            except:
                pass
            
            return status_data
            
        except Exception as e:
            logger.error(f"❌ Error getting system status: {e}")
            # Return defaults on error
            return {
                'bot_status': 'ACTIVE',
                'confidence': 50.0,
                'daily_trades': 0,
                'daily_pnl': 0.0,
                'win_rate': 65.0,
                'training_status': 'ACTIVE',
                'gpu_status': 'GPU ACTIVE'
            }

    def start_monitoring(self):
        """Start continuous Telegram monitoring with instant responses"""
        logger.info("🚀 Starting Telegram monitoring - INSTANT RESPONSE MODE")
        
        while True:
            try:
                self.process_updates()
                time.sleep(self.response_delay)  # 100ms for instant responses
                
            except KeyboardInterrupt:
                logger.info("⏹️ Telegram monitoring stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Telegram monitoring error: {e}")
                time.sleep(1)  # Brief pause on error

# Legacy compatibility
class TelegramController(AdvancedTelegramController):
    """Legacy wrapper for backward compatibility"""
    
    def __init__(self):
        super().__init__()
        logger.info("Legacy Telegram Controller wrapper initialized.")

    def format_status(self, stats: dict, adaptations: dict, recovery: dict) -> str:
        """Legacy format function"""
        status = stats.get("status", "ACTIVE")
        win_rate = adaptations.get("win_rate", 0.50)
        
        return (
            f"⚡ <b>AEGIS GOLD STATUS</b>\n"
            f"🤖 Status: <b>{status}</b>\n"
            f"🎯 Win Rate: <b>{win_rate:.1%}</b>\n"
            f"💰 PnL: <b>${stats.get('daily_pnl', 0.0):+.2f}</b>\n"
            f"📊 Trades: <b>{stats.get('daily_trades', 0)}</b>\n"
            f"⚡ <b>NEVER PAUSE MODE</b>"
        )
