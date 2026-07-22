# ============================================================
# MT5 CONNECTOR — All broker communication
# ============================================================

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from loguru import logger
from config import (
    MT5_LOGIN, MT5_PASSWORD, MT5_SERVER,
    SYMBOL, TIMEFRAME, LOT_SIZE, MAGIC,
    CANDLES_TO_FETCH
)

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "H1": mt5.TIMEFRAME_H1,
}


def connect() -> bool:
    """Initialize MT5 and login."""
    if not mt5.initialize():
        logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
        return False
    authorized = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    if not authorized:
        logger.error(f"MT5 login failed: {mt5.last_error()}")
        mt5.shutdown()
        return False
    info = mt5.account_info()
    logger.info(f"✅ MT5 Connected | Account: {info.login} | Balance: ${info.balance:.2f}")
    return True


def disconnect():
    mt5.shutdown()
    logger.info("MT5 disconnected.")


def get_account_info() -> dict:
    info = mt5.account_info()
    if info is None:
        return {}
    return {
        "balance"  : info.balance,
        "equity"   : info.equity,
        "margin"   : info.margin,
        "free_margin": info.margin_free,
        "profit"   : info.profit,
        "currency" : info.currency,
    }


def get_candles(symbol: str = SYMBOL, timeframe: str = TIMEFRAME,
                count: int = CANDLES_TO_FETCH) -> pd.DataFrame:
    """Fetch OHLCV candles from MT5."""
    tf = TIMEFRAME_MAP.get(timeframe, mt5.TIMEFRAME_M5)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        logger.warning("No candle data received.")
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"tick_volume": "volume"}, inplace=True)
    return df[["time", "open", "high", "low", "close", "volume"]]


def get_spread(symbol: str = SYMBOL) -> float:
    """Return current spread in pips."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return 999.0
    info = mt5.symbol_info(symbol)
    spread = (tick.ask - tick.bid) / info.point
    return round(spread, 1)


def get_open_positions(symbol: str = SYMBOL) -> list:
    """Return all open positions for this bot (filtered by MAGIC)."""
    positions = mt5.positions_get(symbol=symbol)
    if positions is None:
        return []
    return [p for p in positions if p.magic == MAGIC]


def place_order(signal: str, sl_price: float, tp_price: float,
                lot: float = LOT_SIZE, comment: str = "GoldBot") -> dict:
    """Place a BUY or SELL market order."""
    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.symbol_info(SYMBOL)
    if tick is None or info is None:
        return {"success": False, "error": "Symbol info unavailable"}

    order_type = mt5.ORDER_TYPE_BUY if signal == "BUY" else mt5.ORDER_TYPE_SELL
    price = tick.ask if signal == "BUY" else tick.bid
    deviation = 20  # max slippage in points

    request = {
        "action"      : mt5.TRADE_ACTION_DEAL,
        "symbol"      : SYMBOL,
        "volume"      : lot,
        "type"        : order_type,
        "price"       : price,
        "sl"          : sl_price,
        "tp"          : tp_price,
        "deviation"   : deviation,
        "magic"       : MAGIC,
        "comment"     : comment,
        "type_time"   : mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Order failed: {result.comment} (code {result.retcode})")
        return {"success": False, "error": result.comment, "retcode": result.retcode}

    logger.success(f"✅ Order placed: {signal} {lot} lot @ {result.price} | SL:{sl_price} TP:{tp_price}")
    return {
        "success"    : True,
        "ticket"     : result.order,
        "price"      : result.price,
        "sl"         : sl_price,
        "tp"         : tp_price,
        "lot"        : lot,
        "signal"     : signal,
        "time"       : datetime.now().isoformat(),
    }


def close_position(ticket: int) -> bool:
    """Force close a position by ticket."""
    position = mt5.positions_get(ticket=ticket)
    if not position:
        return False
    pos = position[0]
    tick = mt5.symbol_info_tick(SYMBOL)
    close_type  = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
    close_price = tick.bid if pos.type == 0 else tick.ask

    request = {
        "action"      : mt5.TRADE_ACTION_DEAL,
        "symbol"      : SYMBOL,
        "volume"      : pos.volume,
        "type"        : close_type,
        "position"    : ticket,
        "price"       : close_price,
        "deviation"   : 20,
        "magic"       : MAGIC,
        "comment"     : "GoldBot_Close",
        "type_time"   : mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"Close failed ticket {ticket}: {result.comment}")
        return False
    logger.info(f"Position {ticket} closed.")
    return True


def update_trailing_stop(ticket: int, new_sl: float) -> bool:
    """Update stop loss for trailing."""
    request = {
        "action"  : mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl"      : new_sl,
    }
    result = mt5.order_send(request)
    return result.retcode == mt5.TRADE_RETCODE_DONE
