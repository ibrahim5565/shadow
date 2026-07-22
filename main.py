# ============================================================
# GOLD TRADING BOT — MAIN ENGINE
# ============================================================

import time
import schedule
from datetime import datetime
from loguru import logger

import mt5_connector  as broker
import claude_analyst as ai
import risk_manager   as risk
import trade_logger   as tlog
import notifier
from indicators import calculate_all
from config import (
    SCAN_INTERVAL_SECONDS, MONITOR_INTERVAL_SECONDS,
    SYMBOL, LOT_SIZE, TRAILING_STOP_ENABLED
)


# ── Open position tracker (in-memory) ────────────────────────
open_trades = {}   # ticket → {signal, open_time, sl, tp, lot}


# ─────────────────────────────────────────────────────────────
# SCAN LOOP — runs every 60 seconds
# ─────────────────────────────────────────────────────────────
def scan_market():
    logger.info("── Market scan started ──")

    # 1. Get account state
    account = broker.get_account_info()
    if not account:
        logger.error("Cannot get account info. Retrying next cycle.")
        return

    # 2. Initialize / refresh daily state
    risk.init_day(account["balance"])

    # 3. Get candles
    df = broker.get_candles()
    if df.empty:
        logger.warning("No candle data received.")
        return

    # 4. Calculate indicators
    indicators = calculate_all(df)

    # 5. Spread check
    spread = broker.get_spread()
    indicators["spread"] = spread

    # 6. Build candle summary for Claude
    candles_summary = df.tail(20).to_dict("records")
    for c in candles_summary:
        if hasattr(c.get("time"), "isoformat"):
            c["time"] = c["time"].isoformat()

    # 7. Get current session
    session = risk.get_session()

    # 8. Get recent trades for context
    recent_trades = tlog.get_recent_closed_trades(5)

    # 9. Get open positions
    open_positions = broker.get_open_positions()

    # 10. Ask Claude for signal
    signal = ai.get_signal(
        indicators=indicators,
        candles_summary=candles_summary,
        account=account,
        session=session,
        recent_trades=recent_trades
    )

    # 11. Risk check
    risk_check = risk.check_all(
        signal=signal,
        account=account,
        open_positions=open_positions,
        spread=spread
    )

    if not risk_check["allowed"]:
        logger.info(f"Trade not executed: {risk_check['reason']}")
        return

    # 12. Calculate SL / TP
    price = indicators["price"]
    atr   = indicators["atr"]
    sl_price, tp_price = risk.calculate_sl_tp(signal["signal"], price, atr)

    # 13. Execute order
    result = broker.place_order(
        signal=signal["signal"],
        sl_price=sl_price,
        tp_price=tp_price,
        lot=LOT_SIZE,
        comment=f"GoldBot|Conf{signal['confidence']}"
    )

    if not result["success"]:
        logger.error(f"Order execution failed: {result.get('error')}")
        return

    # 14. Log and notify
    ticket = result["ticket"]
    tlog.log_trade_open(
        ticket=ticket,
        signal=signal["signal"],
        price=result["price"],
        sl=sl_price,
        tp=tp_price,
        lot=LOT_SIZE,
        confidence=signal["confidence"],
        reason=signal["reason"]
    )
    open_trades[ticket] = {
        "signal"    : signal["signal"],
        "open_time" : datetime.utcnow(),
        "sl"        : sl_price,
        "tp"        : tp_price,
        "lot"       : LOT_SIZE,
        "entry"     : result["price"]
    }
    notifier.alert_trade_opened(
        signal=signal["signal"],
        price=result["price"],
        sl=sl_price,
        tp=tp_price,
        lot=LOT_SIZE,
        confidence=signal["confidence"],
        reason=signal["reason"]
    )
    logger.success(f"Trade opened: {signal['signal']} ticket={ticket}")


# ─────────────────────────────────────────────────────────────
# MONITOR LOOP — runs every 30 seconds
# ─────────────────────────────────────────────────────────────
def monitor_positions():
    if not open_trades:
        return

    positions = broker.get_open_positions()
    live_tickets = {p.ticket for p in positions}

    for ticket, trade in list(open_trades.items()):

        # Trade was closed by SL/TP
        if ticket not in live_tickets:
            _handle_closed_trade(ticket, trade)
            continue

        # Time stop
        if risk.check_time_stop(trade["open_time"]):
            logger.warning(f"Time stop triggered for ticket {ticket}")
            if broker.close_position(ticket):
                _handle_closed_trade(ticket, trade, forced=True)
            continue

        # Trailing stop
        if TRAILING_STOP_ENABLED:
            indicators = calculate_all(broker.get_candles())
            current_price = indicators["price"]
            atr = indicators["atr"]
            new_sl = risk.get_trailing_sl(
                signal=trade["signal"],
                current_price=current_price,
                entry_price=trade["entry"],
                current_sl=trade["sl"],
                atr=atr
            )
            if new_sl != trade["sl"]:
                if broker.update_trailing_stop(ticket, new_sl):
                    open_trades[ticket]["sl"] = new_sl
                    logger.info(f"Trailing SL updated: {ticket} → {new_sl}")


def _handle_closed_trade(ticket: int, trade: dict, forced: bool = False):
    """Handle a trade that has been closed."""
    import MetaTrader5 as mt5
    history = mt5.history_deals_get(position=ticket)
    profit = 0.0
    close_price = trade.get("entry", 0)
    if history:
        for deal in history:
            if deal.entry == 1:  # exit deal
                profit = deal.profit
                close_price = deal.price
                break

    won = profit > 0
    risk.record_trade_result(won)
    tlog.log_trade_close(ticket, close_price, profit)

    pips = abs(close_price - trade["entry"]) * 10
    pips = pips if won else -pips
    notifier.alert_trade_closed(
        signal=trade["signal"],
        ticket=ticket,
        profit=profit,
        pips=pips,
        close_price=close_price
    )

    if forced:
        tlog.log_event("TIME_STOP_CLOSE", f"Ticket {ticket} force closed")

    del open_trades[ticket]
    logger.info(f"Trade {ticket} removed from tracker | P&L: ${profit:.2f}")


# ─────────────────────────────────────────────────────────────
# DAILY REPORT — runs at 23:59 UTC
# ─────────────────────────────────────────────────────────────
def daily_report():
    logger.info("Generating daily report...")
    stats   = tlog.get_performance_stats()
    account = broker.get_account_info()
    trades  = tlog.get_today_trades()
    review  = ai.get_daily_review(trades, account)
    notifier.send_daily_report(stats, review, account)
    tlog.log_event("DAILY_REPORT", f"Win rate: {stats.get('win_rate_pct')}%")


# ─────────────────────────────────────────────────────────────
# MAIN — Entry point
# ─────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 50)
    logger.info("  GOLD TRADING BOT — STARTING UP")
    logger.info("=" * 50)

    # Initialize systems
    tlog.init()

    # Connect to MT5
    if not broker.connect():
        logger.critical("MT5 connection failed. Exiting.")
        return

    # Send startup notification
    notifier.send_startup()

    # Schedule tasks
    schedule.every(SCAN_INTERVAL_SECONDS).seconds.do(scan_market)
    schedule.every(MONITOR_INTERVAL_SECONDS).seconds.do(monitor_positions)
    schedule.every().day.at("23:59").do(daily_report)

    logger.info(f"Bot running | Scan: {SCAN_INTERVAL_SECONDS}s | Monitor: {MONITOR_INTERVAL_SECONDS}s")

    # Initial scan immediately
    scan_market()

    # Main loop
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        broker.disconnect()
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
        notifier.alert_emergency_stop(str(e))
        broker.disconnect()
        raise


if __name__ == "__main__":
    main()
