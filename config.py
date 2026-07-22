# ============================================================
# GOLD TRADING BOT - MASTER CONFIGURATION
# ============================================================
# Fill in your credentials below before running the bot.
# Never share this file publicly.

import os

# ── BROKER / MT5 SETTINGS ───────────────────────────────────
MT5_LOGIN    = 0                        # Your MT5 account number
MT5_PASSWORD = "YOUR_MT5_PASSWORD"      # Your MT5 password
MT5_SERVER   = "YOUR_BROKER_SERVER"     # e.g. "ICMarkets-Live"

# ── CLAUDE AI SETTINGS ──────────────────────────────────────
CLAUDE_API_KEY = "YOUR_CLAUDE_API_KEY"  # From console.anthropic.com
CLAUDE_MODEL   = "claude-sonnet-4-5"   # Best speed/intelligence balance

# ── TELEGRAM ALERTS ─────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID   = "YOUR_TELEGRAM_CHAT_ID"

# ── TRADING PARAMETERS ──────────────────────────────────────
SYMBOL      = "XAUUSD"                  # Gold
TIMEFRAME   = "M5"                      # 5-minute candles
LOT_SIZE    = 0.01                      # Fixed lot size
MAGIC       = 202401                    # Unique bot identifier

# ── RISK MANAGEMENT ─────────────────────────────────────────
MAX_RISK_PER_TRADE_PCT   = 1.0          # Max 1% account risk per trade
DAILY_LOSS_LIMIT_PCT     = 3.0          # Stop trading if daily loss > 3%
MAX_CONCURRENT_TRADES    = 2            # Max open trades at once
MAX_TRADE_DURATION_HOURS = 4            # Force close after 4 hours
CONFIDENCE_THRESHOLD     = 75          # Min AI confidence to open trade (%)
ATR_SL_MULTIPLIER        = 1.5          # Stop Loss = ATR × 1.5
ATR_TP_MULTIPLIER        = 3.0          # Take Profit = ATR × 3.0
NEWS_BLACKOUT_MINUTES    = 15           # No trades X min before high-impact news
TRAILING_STOP_ENABLED    = True
TRAILING_STOP_PIPS       = 15

# ── INDICATORS SETTINGS ─────────────────────────────────────
EMA_FAST   = 9
EMA_SLOW   = 21
RSI_PERIOD = 14
ATR_PERIOD = 14
CANDLES_TO_FETCH = 100                  # History candles for analysis

# ── SCHEDULE ────────────────────────────────────────────────
SCAN_INTERVAL_SECONDS   = 60            # Check market every 60 seconds
MONITOR_INTERVAL_SECONDS = 30           # Monitor open trades every 30 seconds

# ── LOGGING ─────────────────────────────────────────────────
LOG_FILE   = "logs/bot.log"
TRADE_FILE = "logs/trades.csv"
DB_FILE    = "logs/trades.db"

# ── FAILSAFE PLANS ──────────────────────────────────────────
PLAN_B_CONSECUTIVE_LOSSES = 5           # Pause after 5 losses in a row
PLAN_C_EMERGENCY_STOP_PCT = 5.0         # Full stop if equity drops 5%
