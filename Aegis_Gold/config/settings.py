import os
from dotenv import load_dotenv

load_dotenv()

# ── MODE ──────────────────────────────────────────────────────
DEMO_MODE = True  # This project is restricted to DEMO accounts.
# Order execution stays disabled until a separately reviewed DEMO test is approved.
EXECUTION_ENABLED = os.environ.get("AEGIS_DEMO_EXECUTION_ENABLED", "false").strip().lower() == "true"

# ── MT5 CONNECTION CONFIGURATION ────────────────────────────────
# Credentials read from .env (never hardcode in source)
MT5_LOGIN    = int(os.environ.get("MT5_LOGIN", "0"))
MT5_PASSWORD = os.environ.get("MT5_PASSWORD", "")
MT5_SERVER   = os.environ.get("MT5_SERVER", "MetaQuotes-Demo")

# ── AI ENGINE CONFIGURATION ─────────────────────────────────
AI_ENGINE_ENABLED = False  # External AI disabled — using fully local engine
USE_AI_SUPERVISOR = True   # Local OMEGA supervisor (always on, no cloud needed)
USE_GPT_BRAIN = True      # Local GPT brain (requires trained model in models/)

# ── TELEGRAM (RE-ENABLED WITH FIXES) ──────────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ══════════════════════════════════════════════════════════════
# MULTI-SYMBOL CONFIGURATION — EURUSD + XAUUSD
# ══════════════════════════════════════════════════════════════

# Active symbols to trade (the engine iterates over these each cycle)
ACTIVE_SYMBOLS = ["XAUUSD", "EURUSD"]  # XAUUSD (GOLD) first — primary focus for bigger entries

# Per-symbol configuration — the engine reads from here for each symbol
SYMBOLS_CONFIG = {
    "EURUSD": {
        "candidates": ["EURUSD", "EURUSD.a", "EURUSDm", "EURUSDpro", "EURUSD.cash"],
        "pip_value_per_lot": 10.0,      # $10 per pip per 1.0 lot (standard)
        # ── LOT SIZING ────────────────────────────────────────────────────────
        "base_lot_demo": 0.01,          # DEMO: 0.01 lot
        "base_lot_live": 0.01,          # LIVE: 0.01 lot
        "max_lot": 0.01,                # Hard cap per trade
        "target_profit": 5.00,          # FIRST 200 MODE: $5 minimum profit (was $0.30)
        "min_tp_points": 0,             # NO TP ON ORDER - Dynamic only
        "max_tp_points": 0,             # NO TP ON ORDER - Dynamic only
        "min_sl_points": 40,            # Mandatory Hard SL Floor (15 pips)
        "max_sl_points": 120,           # Max SL points
        "spread_limits": {"ASIAN": 12, "LONDON": 8, "NY": 12, "OVERLAP": 15},
        "breakeven_trigger_pts": 2,
        "trail_trigger_pts": 3,
        "trail_distance_pts": 2,
        "time_stop_base_sec": 30,
        "mode": "MICRO_SCALP",
        "zone_threshold_pts": 5,
        "max_volatility_ratio": 2.0,
        "ema_range_threshold": 0.00010,
    },
    "XAUUSD": {
        "candidates": ["XAUUSD", "GOLD", "XAUUSD.a", "XAUUSDm", "GOLDm"],
        "pip_value_per_lot": 1.0,
        # ── LOT SIZING ────────────────────────────────────────────────────────
        "base_lot_demo": 0.01,          # DEMO: 0.01 lot
        "base_lot_live": 0.01,          # LIVE: 0.01 lot
        "max_lot": 0.01,                # Hard cap per trade
        "target_profit": 3.90,          # DAY TRADE MOVE: $3.90 target profit per 0.01 lot ($3.90 Gold move)
        "min_tp_points": 390,           # DAY TRADE TARGET: 390 points ($3.90 Gold price move)
        "max_tp_points": 600,           # Max TP points
        "min_sl_points": 150,           # Mandatory Hard SL Floor ($1.50 Gold move)
        "max_sl_points": 400,           # Max SL points
        "spread_limits": {"ASIAN": 60, "LONDON": 55, "NY": 60, "OVERLAP": 65},  # Sniper Mode: Wider limits — high-conviction setups only
        "breakeven_trigger_pts": 15,    # Move to BE at 15pts (guarantees real move before locking profit)
        "trail_trigger_pts": 15,        # Start trailing at 15pts for Gold
        "trail_distance_pts": 8,        # Wider trailing distance for Gold volatility
        "time_stop_base_sec": 180,      # Give Gold trades more time (3 min)
        "mode": "AGGRESSIVE_GOLD",      # Aggressive mode for bigger Gold entries
        "zone_threshold_pts": 10,       # Wider zone for Gold entry tolerance
        "max_volatility_ratio": 5.0,    # Allow higher Gold volatility
        "ema_range_threshold": 2.0,     # More tolerance for Gold ranging
    },
}

# Legacy single-symbol fallback (used by modules that haven't migrated yet)
SYMBOL       = "EURUSD"
SYMBOLS      = ["EURUSD", "XAUUSD"]
MAGIC_NUMBER = 20250101

# ── TRADE PROFIT TARGETING ────────────────────────────────────
TARGET_PROFIT_PER_TRADE = 2.0   # Fast scalp target
DAILY_PROFIT_TARGET     = 64.0  # 32 trades × $2
XAUUSD_PIP_VALUE = 1.0          # Backward compat

# ── LOT SIZING ────────────────────────────────────────────────
BASE_LOT_DEMO = 0.10
BASE_LOT_LIVE = 0.10
MAX_LOT       = 0.50
RISK_PERCENT  = 0.01   # 1% max risk per trade

# ── BRAIN THRESHOLDS (PATTERN QUALITY FOCUS) ──────────────────────────
# Note: MIN_PATTERN_QUALITY is transitional - being replaced with multi-factor
# pattern quality evaluation (structure + historical edge + EV + engines)
MIN_REGIME_SCORE    = 5
MIN_STRUCTURE_SCORE = 5
MIN_ENTRY_SCORE     = 5
MIN_TOTAL_SCORE     = 10
MIN_ADX             = 5
MIN_RR_RATIO        = 0.5
ZONE_THRESHOLD_PTS  = 30
MIN_PATTERN_QUALITY = 50  # Transitional - use pattern_quality.py evaluation instead

# Pattern Quality Evaluation (replaces confidence gates)
PATTERN_QUALITY_THRESHOLD = 0.55  # Composite quality score (0.0-1.0)
REQUIRE_POSITIVE_EV = True        # Trade only if EV > 0 after costs
REQUIRE_HISTORICAL_EDGE = True    # Trade only if pattern memory shows edge
MIN_REMAINING_MOVE_PCT = 0.50     # Require 50%+ of expected move remaining

# ── ABSOLUTE NEVER PAUSE SETTINGS (STRONGEST POSSIBLE) ────────────────────────
ABSOLUTE_NEVER_PAUSE       = False   # STRONGEST NEVER PAUSE MODE
FORCE_CONTINUOUS_TRADING   = False   # FORCE CONTINUOUS - OVERRIDE ALL PAUSES
NEVER_PAUSE_MODE           = False   # NEVER PAUSE MODE ENABLED
OVERRIDE_ALL_STOPS         = False   # OVERRIDE ALL STOP CONDITIONS
IGNORE_ALL_PAUSE_CONDITIONS = False  # IGNORE ALL PAUSE CONDITIONS
BLOCK_ALL_INTERRUPTS       = False   # BLOCK ALL INTERRUPTS
MAXIMUM_TRADING_MODE       = False   # MAXIMUM TRADING MODE
EMERGENCY_OVERRIDE_ACTIVE  = False   # EMERGENCY OVERRIDE ACTIVE
NEVER_STOP_TRADING         = False   # NEVER STOP TRADING
INFINITE_TRADING_MODE      = False   # INFINITE TRADING MODE
UNSTOPPABLE_MODE           = False   # UNSTOPPABLE MODE

# ── TRADE LIMITS (UNLIMITED - NO RESTRICTIONS - NEVER PAUSE) ────────────────
MIN_TRADES_PER_DAY     = 0      # No minimum
MAX_TRADES_PER_DAY     = 999999999 # UNLIMITED - Take every opportunity
MAX_DAILY_TRADES       = 999999999 # UNLIMITED
MAX_OPEN_TRADES        = 999999    # UNLIMITED open positions
MAX_OPEN_TRADES_PER_SYMBOL = 999999  # UNLIMITED positions per symbol
MAX_CONSECUTIVE_LOSSES = 999999999 # NEVER pause - keep trading through infinite losses
CONSECUTIVE_PAUSE_MIN  = 0      # NO pause ever
DAILY_LOSS_LIMIT_USD   = 999999999999  # NO daily loss limit - never stop
WEEKLY_LOSS_LIMIT_USD  = 999999999999  # NO weekly loss limit
MONTHLY_LOSS_LIMIT_USD = 999999999999  # NO monthly loss limit
YEARLY_LOSS_LIMIT_USD  = 999999999999  # NO yearly loss limit
PAUSE_ON_LOSS          = True  # NEVER pause on losses
PAUSE_ON_DRAWDOWN      = True  # NEVER pause on drawdown
ENABLE_TRADING_PAUSE   = False  # Trading pause completely disabled

# AUTO-RESTART CONFIGURATION
AUTO_RESTART_ENABLED   = True   # Enable hourly auto-restart
AUTO_RESTART_INTERVAL  = 3600   # Restart every 1 hour (3600 seconds)

# ── INSTITUTIONAL AI CONFIGURATION (ENABLE GPU TRAINING) ─────────────────────────────
INSTITUTIONAL_AI_ENABLED = True  # Enable new AI engines
INSTITUTIONAL_AI_AUTO_TRAIN = True  # Auto-train in background

# ML Ensemble
ML_RETRAIN_INTERVAL = 50  # Retrain every 50 trades
ML_MIN_TRAINING_DATA = 20  # Start training after 20 trades (reduced from 100)
ML_USE_GPU = True  # Enable GPU acceleration for training
ML_BATCH_SIZE = 32  # Batch size for GPU training

# Confidence Engine (informational/diagnostic only - not a trade gate)
MIN_CONFIDENCE_THRESHOLD = 50  # Display threshold for dashboard
CONFIDENCE_VETO_ENABLED = False  # Disabled - use pattern quality gates instead
CONFIDENCE_THRESHOLD_LOCKED = True  # Prevent self-optimizer from changing this

# Self-Optimization
SELF_OPTIMIZATION_ENABLED = True  # Enable continuous learning
OPTIMIZATION_INTERVAL = 25  # Optimize every 25 trades
OPTIMIZATION_LEARNING_RATE = 0.15  # Faster learning rate

# Multi-Timeframe
MTF_ENABLED = True  # Enable 9-timeframe analysis
MTF_MIN_ALIGNMENT = 3  # Lower alignment requirement (was 5)

# Trade Memory
TRADE_MEMORY_ENABLED = True  # Record all trades
TRADE_MEMORY_AUTO_ANALYZE = True  # Analyze in background
COOLDOWN_WIN_SEC              = 0       # NO cooldown after wins - trade immediately
COOLDOWN_BE_SEC               = 0       # NO cooldown after breakeven - trade immediately  
COOLDOWN_LOSS_SEC             = 0       # NO cooldown after losses - trade immediately
COOLDOWN_AFTER_LOSS_SEC       = 0       # NO cooldown ever - continuous trading
COOLDOWN_AFTER_CONSEC_LOSSES  = 0       # NO cooldown even after consecutive losses

VOLATILITY_LIMITS = {
    "COMPRESSED": 2,                    # Low Volatility: max 2 open trades
    "NORMAL": 3,                        # Normal Volatility: max 3 open trades
    "VOLATILE": 4,                      # High Volatility: max 4 open trades
    "EMERGENCY": 1                      # Emergency Conditions: max 1 open trade
}

# ── DRAWDOWN AND SAFETY LIMITS (ALL COMPLETELY DISABLED) ──────────────────
DD_REDUCE_FREQ_PCT            = 999999999.0   # DISABLED - Never reduce frequency
DD_BLOCK_NEW_PCT              = 999999999.0   # DISABLED - Never block trades
DD_EMERGENCY_PCT              = 999999999.0   # DISABLED - No emergency mode
DRAWDOWN_PROTECTION_ENABLED   = True   # Drawdown protection completely disabled
FORCE_NEVER_PAUSE             = False    # FORCE NEVER PAUSE - OVERRIDE ALL CONDITIONS
IGNORE_ALL_STOP_CONDITIONS    = False    # IGNORE ALL STOP CONDITIONS
MAXIMUM_TRADING_MODE          = False    # MAXIMUM TRADING MODE - NEVER STOP
SAFETY_STOPS_DISABLED         = False    # ALL SAFETY STOPS DISABLED
EMERGENCY_STOPS_DISABLED      = False    # ALL EMERGENCY STOPS DISABLED
MANUAL_STOPS_DISABLED         = False    # ALL MANUAL STOPS DISABLED
AUTOMATIC_STOPS_DISABLED      = False    # ALL AUTOMATIC STOPS DISABLED
ALL_PAUSES_BLOCKED            = False    # ALL PAUSES PERMANENTLY BLOCKED

SESSION_REFRESH_MIN           = 45      # Session refresh interval in minutes

# ── AI TRADING RULES (PATTERN-FIRST ARCHITECTURE) ──────────────────────────
# Note: "SMALL_PATTERN" = short-horizon patterns (5-15 min), not HFT/scalping
RR_RATIO              = 3.0    # Minimum 1:3 R:R for SMC trades
ATR_SL_MULTIPLIER     = 1.2    # Wider SL for Gold volatility
NEWS_BLACKOUT_MINUTES = 15     # 15-min blackout around high-impact news
PATTERN_MODE          = "small_pattern"  # PRIMARY: Pattern detection | Options: "small_pattern", "smc", "unified"
BASE_RISK_PCT         = 0.005  # 0.5% risk per trade
MAX_RISK_PCT          = 0.01   # 1% max risk
MIN_GAP_BETWEEN_TRADES_MIN = 0  # No gap — take every opportunity
NO_DUPLICATE_DIRECTION_SEC     = 0      # Allow immediate direction switches - no restrictions
TRADE_COOLDOWN_ENABLED         = True  # Disable all cooldowns completely

# ── SMC ENGINE SETTINGS ───────────────────────────────────────────────────────
SMC_SIGNAL_THRESHOLD   = 50    # Minimum SMC score to take a trade (0-100)
                               # Breakdown: BOS/CHoCH(20-30) + OB(25) + Sweep(25) + PO3(15) + FVG(10)
SMC_OB_LOOKBACK        = 30    # Candles to look back for Order Block detection
SMC_SWING_WINDOW       = 3     # Candles each side for swing high/low detection
SMC_EQUAL_LIQ_PTS      = 5.0   # Points tolerance for "equal highs/lows" liquidity
SMC_SWEEP_BUFFER_PTS   = 3.0   # Points beyond liquidity level to confirm sweep
SMC_FVG_MIN_GAP_PTS    = 5.0   # Minimum points gap to qualify as FVG
SMC_OB_BUFFER_PTS      = 5.0   # Points buffer around OB zone

# FIRST 200 TRADES SPECIAL MODE (DISABLED - CAUSING $0.00 CLOSES) ───────────────────────────────────────────────
FIRST_200_TRADES_MODE  = False  # DISABLED to prevent $0.00 closes
FIRST_200_MIN_PROFIT_USD = 5.00
FIRST_200_MIN_HOLD_SEC = 30
FIRST_200_MAX_LOSS_USD = 10.00

MAX_TRADES_PER_MINUTE  = 10    # Hard cap on trades per 60-second window

# ── SESSION LIMITS (no cap — market decides) ──────────────────
ASIAN_MAX_TRADES  = 999
LONDON_MAX_TRADES = 999
NY_MAX_TRADES     = 999

# ── CANDLE TIMEFRAMES ────────────────────────────────────────
CANDLE_TIMEFRAME = "M5"
CANDLE_COUNT     = 100
M1_CANDLE_COUNT  = 30     # M1 candles for breakout detection (increased for entry timing)

# ── INDICATOR PERIODS ────────────────────────────────────────
EMA_FAST_PERIOD  = 8
EMA_SLOW_PERIOD  = 21
ADX_PERIOD       = 14
RSI_PERIOD       = 14
ATR_PERIOD       = 14

# ── EXECUTION (OPTIMIZED - NO TP/SL ON ORDERS) ─────────────────────────────────────────────
LOOP_DELAY_SEC        = 1.0   # Increased from 0.3s to reduce CPU load
SCAN_INTERVAL        = 5      # Increased from 2s to 5s for CPU stability
MIN_SL_POINTS         = 0     # NO SL ON ORDER - Risk managed dynamically by position supervisor
MAX_SL_POINTS         = 0     # NO SL ON ORDER - Risk managed dynamically by position supervisor
MIN_TP_POINTS         = 0     # NO TP ON ORDER - Dynamic TP engine manages exits
MAX_TP_POINTS         = 0     # NO TP ON ORDER - Dynamic TP engine manages exits
BREAKEVEN_TRIGGER_PTS = 15    # Move to BE after +15 points ($1.50 profit on Gold)
GUARANTEED_BREAKEVEN_PROFIT_PTS = 10  # Move SL to entry + 10 points ($1.00 guaranteed profit, covers spread)
TRAIL_TRIGGER_PTS     = 15    # Still used for trailing stop
TRAIL_DISTANCE_PTS    = 10    # Wider trailing for Gold volatility
TIME_STOP_BASE_SEC    = 180   # Give Gold trades 3 minutes
MAX_VOLATILITY_RATIO  = 5.0   # High volatility tolerance for Gold

# ── PATTERN INSTANT-CLOSE PROTECTION (MINIMUM PROFIT REQUIRED) ──────────
# IMPORTANT: Don't close at $0.00 - require actual profit
PATTERN_MIN_PROFIT_USD  = 1.00   # Minimum $1.00 profit to close (prevents $0.00 closes)
# Close immediately if loss exceeds this threshold (USD) — over-loss protection
PATTERN_MAX_LOSS_USD    = 5.00   # Maximum $5 loss allowed per trade

# ── SPREAD LIMITS (RELAXED - trade through volatility) ────
SPREAD_LIMITS = {"ASIAN": 40, "LONDON": 40, "NY": 40, "OVERLAP": 40}  # RELAXED: Allow trades up to 40pt spread

# ── SESSION HOURS (UTC) ───────────────────────────────────────
ASIAN_START  = 0
ASIAN_END    = 8
LONDON_START = 7
LONDON_END   = 16
NY_START     = 12
NY_END       = 21

# ── SYSTEM ────────────────────────────────────────────────────
HEARTBEAT_SEC    = 1800
LATENCY_ALERT_MS = 20

# ── FEATURE FACTORY ───────────────────────────────────────────
DIRECTION_WINDOW    = 5
DIRECTION_MIN_AGREE = 2
VELOCITY_WINDOW_SEC = 60
VELOCITY_SPIKE_MULT = 1.2
MOMENTUM_WINDOW     = 10
MOMENTUM_MULT       = 0.8
SPREAD_DYNAMIC_MULT = 2.0
SPREAD_ROLLING_WINDOW = 20

# ── JOURNAL COLUMNS ───────────────────────────────────────────
JOURNAL_COLUMNS = [
    "timestamp", "trade_id", "symbol", "mode", "session",
    "direction", "entry_price", "exit_price", "slippage_pts",
    "lot", "tp_price", "sl_price",
    "exit_reason", "pnl_points", "pnl_usd",
    "duration_sec", "spread_at_entry",
    "signal_score", "ai_approved", "equity_after",
]

# ── HELPER: Get symbol config with fallback ───────────────────
def get_symbol_config(symbol: str) -> dict:
    """Return per-symbol config dict, falling back to EURUSD defaults."""
    # Check exact match first
    if symbol in SYMBOLS_CONFIG:
        return SYMBOLS_CONFIG[symbol]
    # Check if symbol is a variant (e.g. EURUSD.a → EURUSD config)
    for base_sym, conf in SYMBOLS_CONFIG.items():
        if symbol in conf.get("candidates", []):
            return conf
    # Fallback to EURUSD
    return SYMBOLS_CONFIG["EURUSD"]


# ── QUANT X: Startup Security assertions ───────────────────────
# Check that sensitive keys are loaded from env, not hardcoded.
# If environment variables are empty, raise EnvironmentError.
if not DEMO_MODE:
    if not os.environ.get("MT5_PASSWORD"):
        raise EnvironmentError("[SECURITY ERROR] MT5_PASSWORD is not set in environment variables! Trading halted.")
    if not os.environ.get("TELEGRAM_TOKEN"):
        raise EnvironmentError("[SECURITY ERROR] TELEGRAM_TOKEN is not set in environment variables! Trading halted.")

# ── MODULE 4: Risk Engine Parameters ────────────────────────────
# CVaR daily limit — entries blocked when tail loss exceeds this value.
# Set CVAR_DAILY_LIMIT_USD=0.01 in .env to test the guard fires correctly.
CVAR_DAILY_LIMIT_USD = float(os.environ.get("CVAR_DAILY_LIMIT_USD", "50"))

# Fractional Kelly sizing parameters.
# kelly_sizing flag must be true in quant_x_flags.json AND backtest gate must pass.
KELLY_FRACTION      = float(os.environ.get("KELLY_FRACTION",      "0.25"))  # 25% of full Kelly
KELLY_MAX_RISK_PCT  = float(os.environ.get("KELLY_MAX_RISK_PCT",  "0.02"))  # 2% hard equity cap
KELLY_ROLLING_N     = int(os.environ.get(  "KELLY_ROLLING_N",    "100"))   # rolling window trades
KELLY_PRIOR_WEIGHT  = int(os.environ.get(  "KELLY_PRIOR_WEIGHT", "100"))   # Bayesian prior weight


# ── SNIPER MODE (Phase 4 — High-Precision Pattern-Only Trading) ──────────────
# Enables Triple-Lock Confirmation gate. When active, only SMALL_PATTERN and
# BIG_PATTERN tier setups that pass all 3 locks can generate TRADE decisions.
# Small-pattern mode is disabled when SNIPER_MODE_ENABLED = True.
SNIPER_MODE_ENABLED       = True    # Master switch for Sniper gating
ALLOW_SMALL_PATTERNS      = False   # Small pattern tier disabled in sniper mode
SNIPER_ML_CONF_MIN        = 0.85    # ML directional win probability floor (was 0.68)
SNIPER_SMC_CONF_MIN       = 0.80    # SMC OB+FVG structural confidence floor
SNIPER_HTF_CONF_MIN       = 0.80    # H1 HTF alignment confidence floor
SNIPER_ATR_RATIO_MAX      = 2.5     # Max ATR ratio vs 20-bar baseline (news spike guard)
SNIPER_REQUIRE_LIQ_SWEEP  = True    # Big Pattern requires prior HTF liquidity sweep (PO3)
SNIPER_AUTO_TIGHTEN       = True    # Auto-tighten ml_conf if WR < 95% over last 50 trades
SNIPER_AUTO_TIGHTEN_STEP  = 0.02    # Tighten ml_conf by 2% each auto-tighten cycle
SNIPER_RISK_PCT           = 0.005   # 0.5% equity risk per sniper trade (ultra-conservative)
SNIPER_MIN_RR             = 2.5     # Minimum R:R ratio for sniper setups (TP/SL)
