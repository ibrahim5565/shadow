# ============================================================
# RISK MANAGER — The most critical safety layer of the bot
# ============================================================

from datetime import datetime, timedelta
from loguru import logger
from config import (
    MAX_RISK_PER_TRADE_PCT, DAILY_LOSS_LIMIT_PCT,
    MAX_CONCURRENT_TRADES, MAX_TRADE_DURATION_HOURS,
    CONFIDENCE_THRESHOLD, ATR_SL_MULTIPLIER, ATR_TP_MULTIPLIER,
    PLAN_B_CONSECUTIVE_LOSSES, PLAN_C_EMERGENCY_STOP_PCT,
    LOT_SIZE, SYMBOL
)

# ── Bot State (in-memory) ─────────────────────────────────
_state = {
    "daily_start_balance"    : 0.0,
    "consecutive_losses"     : 0,
    "trades_today"           : 0,
    "plan_b_active"          : False,
    "plan_b_until"           : None,
    "emergency_stop"         : False,
    "last_reset_date"        : None,
}


def init_day(balance: float):
    """Call this once at bot start / each new trading day."""
    today = datetime.utcnow().date()
    if _state["last_reset_date"] != today:
        _state["daily_start_balance"] = balance
        _state["trades_today"]        = 0
        _state["last_reset_date"]     = today
        _state["plan_b_active"]       = False
        _state["plan_b_until"]        = None
        logger.info(f"📅 New trading day initialized | Start balance: ${balance:.2f}")


def get_daily_pnl(current_equity: float) -> float:
    return current_equity - _state["daily_start_balance"]


def get_daily_pnl_pct(current_equity: float) -> float:
    start = _state["daily_start_balance"]
    if start == 0:
        return 0.0
    return ((current_equity - start) / start) * 100


def record_trade_result(won: bool):
    _state["trades_today"] += 1
    if won:
        _state["consecutive_losses"] = 0
    else:
        _state["consecutive_losses"] += 1
        if _state["consecutive_losses"] >= PLAN_B_CONSECUTIVE_LOSSES:
            _activate_plan_b()


def _activate_plan_b():
    _state["plan_b_active"] = True
    _state["plan_b_until"]  = datetime.utcnow() + timedelta(hours=24)
    logger.warning(f"⚠️ PLAN B ACTIVATED — {PLAN_B_CONSECUTIVE_LOSSES} consecutive losses. "
                   f"Trading paused until {_state['plan_b_until']}")


def activate_emergency_stop(reason: str):
    _state["emergency_stop"] = True
    logger.critical(f"🚨 EMERGENCY STOP: {reason}")


def calculate_sl_tp(signal: str, price: float, atr: float) -> tuple:
    """
    Calculate SL and TP prices from ATR.
    Returns (sl_price, tp_price)
    """
    sl_pips = atr * ATR_SL_MULTIPLIER
    tp_pips = atr * ATR_TP_MULTIPLIER
    if signal == "BUY":
        sl_price = round(price - sl_pips, 2)
        tp_price = round(price + tp_pips, 2)
    else:  # SELL
        sl_price = round(price + sl_pips, 2)
        tp_price = round(price - tp_pips, 2)
    return sl_price, tp_price


def calculate_lot_size(balance: float, sl_pips: float, pip_value: float = 1.0) -> float:
    """
    Calculate position size based on risk percentage.
    For XAUUSD 0.01 lot, pip value ≈ $0.10 per pip.
    We use fixed 0.01 lot for simplicity and safety.
    """
    risk_amount = balance * (MAX_RISK_PER_TRADE_PCT / 100)
    risk_per_lot = sl_pips * 10  # $10 per pip per standard lot
    calculated_lot = risk_amount / risk_per_lot
    # Clamp between 0.01 and config max
    lot = max(0.01, min(calculated_lot, LOT_SIZE))
    return round(lot, 2)


def check_all(signal: dict, account: dict,
              open_positions: list, spread: float) -> dict:
    """
    Master risk check. Returns dict with:
      - allowed: bool
      - reason: str
    """

    # 0. Emergency stop
    if _state["emergency_stop"]:
        return _block("🚨 Emergency stop is active. Manual review required.")

    # 1. Plan B check
    if _state["plan_b_active"]:
        if datetime.utcnow() < _state["plan_b_until"]:
            remaining = _state["plan_b_until"] - datetime.utcnow()
            return _block(f"⚠️ Plan B active. Resume in {int(remaining.seconds/60)} minutes.")
        else:
            _state["plan_b_active"] = False
            _state["consecutive_losses"] = 0
            logger.info("Plan B lifted. Trading resumed.")

    # 2. Signal must be BUY or SELL
    if signal.get("signal") == "HOLD":
        return _block("Signal is HOLD — no trade needed.")

    # 3. Confidence threshold
    confidence = signal.get("confidence", 0)
    if confidence < CONFIDENCE_THRESHOLD:
        return _block(f"Confidence {confidence}% < threshold {CONFIDENCE_THRESHOLD}%")

    # 4. Daily loss limit
    equity = account.get("equity", 0)
    pnl_pct = get_daily_pnl_pct(equity)
    if pnl_pct <= -DAILY_LOSS_LIMIT_PCT:
        return _block(f"Daily loss limit hit: {pnl_pct:.2f}% (limit: -{DAILY_LOSS_LIMIT_PCT}%)")

    # 5. Emergency equity drop (Plan C)
    pnl_emergency = get_daily_pnl_pct(equity)
    if pnl_emergency <= -PLAN_C_EMERGENCY_STOP_PCT:
        activate_emergency_stop(f"Equity dropped {pnl_emergency:.2f}%")
        return _block("Plan C — Emergency equity stop triggered.")

    # 6. Max concurrent trades
    if len(open_positions) >= MAX_CONCURRENT_TRADES:
        return _block(f"Max concurrent trades ({MAX_CONCURRENT_TRADES}) reached.")

    # 7. Spread check (XAUUSD acceptable spread < 50 points)
    if spread > 50:
        return _block(f"Spread too high: {spread} points. Skipping.")

    # 8. Account has sufficient margin
    free_margin = account.get("free_margin", 0)
    if free_margin < 100:
        return _block(f"Insufficient free margin: ${free_margin:.2f}")

    logger.info("✅ All risk checks passed.")
    return {"allowed": True, "reason": "All checks passed"}


def check_time_stop(position_open_time: datetime) -> bool:
    """Return True if position has exceeded max duration and must be closed."""
    age = datetime.utcnow() - position_open_time
    return age > timedelta(hours=MAX_TRADE_DURATION_HOURS)


def get_trailing_sl(signal: str, current_price: float,
                    entry_price: float, current_sl: float,
                    atr: float, trail_pips: float = 15) -> float:
    """
    Return new SL if trailing stop should be updated, else return current SL.
    """
    trail_distance = atr * 0.5  # Trail by half ATR
    if signal == "BUY":
        new_sl = round(current_price - trail_distance, 2)
        return new_sl if new_sl > current_sl else current_sl
    else:  # SELL
        new_sl = round(current_price + trail_distance, 2)
        return new_sl if new_sl < current_sl else current_sl


def get_session() -> str:
    """Return current trading session based on UTC time."""
    hour = datetime.utcnow().hour
    if 0 <= hour < 7:
        return "ASIAN"
    elif 7 <= hour < 13:
        return "LONDON"
    elif 13 <= hour < 17:
        return "NEW_YORK"
    elif 17 <= hour < 21:
        return "OVERLAP"
    else:
        return "AFTER_HOURS"


def get_state() -> dict:
    return dict(_state)


def _block(reason: str) -> dict:
    logger.warning(f"🚫 Trade blocked: {reason}")
    return {"allowed": False, "reason": reason}
