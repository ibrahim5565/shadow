# ============================================================
# TELEGRAM NOTIFIER — Real-time trade alerts
# ============================================================

import requests
from loguru import logger
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send(message: str, parse_mode: str = "HTML") -> bool:
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.debug("Telegram not configured, skipping notification.")
        return False
    try:
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": parse_mode},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")
        return False


def alert_trade_opened(signal: str, price: float, sl: float,
                       tp: float, lot: float, confidence: int, reason: str):
    emoji = "🟢" if signal == "BUY" else "🔴"
    msg = (
        f"{emoji} <b>TRADE OPENED — {signal}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Symbol     : XAUUSD\n"
        f"📊 Signal     : {signal}\n"
        f"🎯 Entry      : {price}\n"
        f"🛑 Stop Loss  : {sl}\n"
        f"✅ Take Profit: {tp}\n"
        f"📦 Lot Size   : {lot}\n"
        f"🧠 AI Conf.   : {confidence}%\n"
        f"📝 Reason     : {reason}"
    )
    send(msg)


def alert_trade_closed(signal: str, ticket: int, profit: float,
                       pips: float, close_price: float):
    emoji = "✅" if profit > 0 else "❌"
    result = "WIN" if profit > 0 else "LOSS"
    msg = (
        f"{emoji} <b>TRADE CLOSED — {result}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎫 Ticket     : {ticket}\n"
        f"📊 Direction  : {signal}\n"
        f"💵 Close Price: {close_price}\n"
        f"💹 Pips       : {pips:+.1f}\n"
        f"💰 Profit     : ${profit:+.2f}"
    )
    send(msg)


def alert_risk_block(reason: str):
    msg = f"⚠️ <b>TRADE BLOCKED</b>\n{reason}"
    send(msg)


def alert_plan_b():
    msg = (
        "🚨 <b>PLAN B ACTIVATED</b>\n"
        "Trading paused for 24 hours due to consecutive losses.\n"
        "Bot will resume automatically."
    )
    send(msg)


def alert_emergency_stop(reason: str):
    msg = (
        f"🆘 <b>EMERGENCY STOP</b>\n"
        f"Bot has been halted.\n"
        f"Reason: {reason}\n"
        f"⚠️ MANUAL REVIEW REQUIRED"
    )
    send(msg)


def send_daily_report(stats: dict, review: str, account: dict):
    win_emoji = "🟢" if stats.get("total_profit", 0) > 0 else "🔴"
    msg = (
        f"📊 <b>DAILY PERFORMANCE REPORT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💼 Balance     : ${account.get('balance', 0):.2f}\n"
        f"📈 Total Trades: {stats.get('total_trades', 0)}\n"
        f"✅ Wins        : {stats.get('wins', 0)}\n"
        f"❌ Losses      : {stats.get('losses', 0)}\n"
        f"🎯 Win Rate    : {stats.get('win_rate_pct', 0)}%\n"
        f"{win_emoji} Total P&L  : ${stats.get('total_profit', 0):+.2f}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧠 <b>AI Review:</b>\n{review}"
    )
    send(msg)


def send_startup():
    msg = (
        "🤖 <b>GOLD TRADING BOT STARTED</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Symbol   : XAUUSD\n"
        "Timeframe: M5\n"
        "Lot Size : 0.01\n"
        "Status   : ✅ Running 24/5"
    )
    send(msg)
