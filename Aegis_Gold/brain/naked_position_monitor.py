"""
Naked Position Monitor & Emergency SL Attacher
==============================================
Periodically checks for any live/demo open position where sl == 0.0.
If found:
  1. Logs a CRITICAL alert.
  2. Sends an immediate Telegram alert.
  3. Attempts to attach an emergency hard SL (150pts for XAUUSD, 40pts for EURUSD) via TRADE_ACTION_SLTP.
  4. If attaching emergency SL fails, market-closes the position to eliminate naked broker risk.
"""

import logging
import MetaTrader5 as mt5
from typing import List, Dict, Any

logger = logging.getLogger("aegis.naked_position_monitor")


def check_and_protect_open_positions(gateway=None, telegram=None) -> List[Dict[str, Any]]:
    """
    Scans MT5 open positions for sl == 0.0.
    Returns list of naked positions processed.
    """
    naked_found = []
    try:
        positions = mt5.positions_get()
        if not positions:
            return []

        for pos in positions:
            if pos.sl == 0.0 or pos.sl is None:
                symbol = pos.symbol
                ticket = pos.ticket
                direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
                entry_price = pos.price_open
                volume = pos.volume

                is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
                default_floor_pts = 150 if is_gold else 40
                point = 0.01 if is_gold else 0.00001
                digits = 2 if is_gold else 5

                info = mt5.symbol_info(symbol)
                if info:
                    point = info.point
                    digits = info.digits

                # Calculate emergency SL price
                if direction == "BUY":
                    emergency_sl = round(entry_price - (default_floor_pts * point), digits)
                else:
                    emergency_sl = round(entry_price + (default_floor_pts * point), digits)

                msg = (
                    f"[ALERT] [EMERGENCY NAKED POSITION DETECTED] Ticket #{ticket} ({symbol} {direction} {volume} lot @ {entry_price}) "
                    f"has NO SL ON BROKER (sl=0.0)! Attaching emergency SL at {emergency_sl} ({default_floor_pts}pts)..."
                )
                logger.critical(msg)
                if telegram:
                    try:
                        telegram.send(f"[ALERT] <b>[EMERGENCY NAKED POSITION]</b> Ticket #{ticket} ({symbol} {direction}) sl=0.0! Attaching hard SL @ {emergency_sl}...")
                    except Exception:
                        pass

                # Attempt to attach emergency SL
                sltp_req = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": ticket,
                    "symbol": symbol,
                    "sl": emergency_sl,
                    "tp": pos.tp,
                }
                res = mt5.order_send(sltp_req)

                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    logger.info(f"[OK] [EMERGENCY SL ATTACHED] Ticket #{ticket} attached hard SL at {emergency_sl}.")
                    if telegram:
                        try:
                            telegram.send(f"✅ <b>[EMERGENCY SL ATTACHED]</b> Ticket #{ticket} hard SL attached at {emergency_sl}.")
                        except Exception:
                            pass
                else:
                    err = res.comment if res else mt5.last_error()
                    logger.error(f"[ERR] [EMERGENCY SL FAILED] Could not attach SL to #{ticket}: {err}. MARKET CLOSING NAKED POSITION FOR SAFETY...")
                    # Emergency market close
                    close_tick = mt5.symbol_info_tick(symbol)
                    close_price = close_tick.bid if direction == "BUY" else close_tick.ask
                    close_req = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": volume,
                        "type": mt5.ORDER_TYPE_SELL if direction == "BUY" else mt5.ORDER_TYPE_BUY,
                        "position": ticket,
                        "price": close_price,
                        "deviation": 20,
                        "magic": pos.magic,
                        "comment": "Emergency Naked SL Flatten",
                    }
                    res_close = mt5.order_send(close_req)
                    if res_close and res_close.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"[STOP] [EMERGENCY FLATTEN DONE] Ticket #{ticket} closed successfully.")
                    else:
                        logger.critical(f"?? [CRITICAL FAIL] Could not market close naked position #{ticket}!")

                naked_found.append({
                    "ticket": ticket,
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "emergency_sl": emergency_sl
                })

    except Exception as exc:
        logger.error(f"Error checking naked positions: {exc}")

    return naked_found
