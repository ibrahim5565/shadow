"""
Aegis Micro-Scalp AI — MT5 Gateway
Multi-symbol MetaTrader 5 communication. Supports EURUSD + XAUUSD simultaneously.
"""

import time
import logging
from collections import deque
from datetime import datetime, timezone

import MetaTrader5 as mt5

from config import settings as cfg

logger = logging.getLogger("aegis.mt5")


class MT5Gateway:
    """Single entry-point for every MT5 operation. Multi-symbol aware."""

    def __init__(self):
        # Cached symbol properties — { "SYMBOL": { "point": ..., "digits": ... } }
        self.symbols_data: dict[str, dict] = {}

        # Tick buffer kept in RAM
        self.tick_buffer: dict[str, deque] = {}  # symbol -> ticks

        # Active symbols successfully detected on broker
        self.active_symbols: list[str] = []

        # Maps detected broker name -> base symbol (e.g. "XAUUSD.a" -> "XAUUSD")
        self.symbol_base_map: dict[str, str] = {}

        # Error repeat counter for Telegram escalation
        self._error_counts: dict[str, int] = {}

        # Telegram callback (set from main.py)
        self._tg_send = None

    # ── helpers ────────────────────────────────────────────────

    def set_telegram_callback(self, fn):
        """Inject a non-blocking Telegram send function."""
        self._tg_send = fn

    def _alert(self, msg: str):
        logger.warning(msg)
        if self._tg_send:
            try:
                self._tg_send(msg)
            except Exception:
                pass

    def _track_error(self, tag: str, msg: str):
        self._error_counts[tag] = self._error_counts.get(tag, 0) + 1
        logger.error(f"[{tag}] {msg}")
        if self._error_counts[tag] >= 3:
            self._alert(f"⚠️ Repeated error ({tag}): {msg}")
            self._error_counts[tag] = 0  # reset after alert

    def _get_filling_mode(self, symbol: str) -> int:
        """Detect broker-supported filling mode for a symbol.
        Uses live order_check probe to find the truly-accepted filling mode.
        Cached per symbol after first successful detection."""
        # Use cached value if already detected
        if hasattr(self, '_filling_mode_cache') and symbol in self._filling_mode_cache:
            return self._filling_mode_cache[symbol]

        if not hasattr(self, '_filling_mode_cache'):
            self._filling_mode_cache = {}

        try:
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if info is None or tick is None:
                logger.warning(f"Cannot detect filling mode for {symbol} — using FOK")
                return mt5.ORDER_FILLING_FOK

            fm = info.filling_mode
            point = info.point
            digits = info.digits
            logger.info(f"[{symbol}] filling_mode bitmask={fm} "
                        f"FOK={bool(fm&1)} IOC={bool(fm&2)} RETURN={bool(fm&4)}")

            # Map bitmask bits → MT5 constants (bit1=FOK, bit2=IOC, bit4=RETURN)
            candidates = []
            if fm & 4:
                candidates.append(("RETURN", mt5.ORDER_FILLING_RETURN))
            if fm & 2:
                candidates.append(("IOC",    mt5.ORDER_FILLING_IOC))
            if fm & 1:
                candidates.append(("FOK",    mt5.ORDER_FILLING_FOK))

            # Always probe all three regardless of bitmask
            for name, val in [("FOK", mt5.ORDER_FILLING_FOK),
                               ("IOC", mt5.ORDER_FILLING_IOC),
                               ("RETURN", mt5.ORDER_FILLING_RETURN)]:
                probe = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": info.volume_min,
                    "type": mt5.ORDER_TYPE_BUY,
                    "price": round(tick.ask, digits),
                    "tp": round(tick.ask + 50 * point, digits),
                    "sl": 0.0,
                    "magic": 0,
                    "deviation": 5,
                    "type_filling": val,
                    "type_time": mt5.ORDER_TIME_GTC,
                }
                chk = mt5.order_check(probe)
                if chk and chk.retcode not in (10030, 10014):  # not "unsupported filling"
                    logger.info(f"[{symbol}] Filling mode confirmed: {name} (val={val}) retcode={chk.retcode}")
                    self._filling_mode_cache[symbol] = val
                    return val

            logger.warning(f"[{symbol}] No filling mode passed order_check — defaulting to FOK")
            self._filling_mode_cache[symbol] = mt5.ORDER_FILLING_FOK
            return mt5.ORDER_FILLING_FOK

        except Exception as exc:
            logger.warning(f"Filling mode detection failed for {symbol}: {exc}, using FOK")
            return mt5.ORDER_FILLING_FOK

    # ── connection ─────────────────────────────────────────────

    def initialize(self) -> bool:
        """Connect to MT5 terminal with retry."""
        for attempt in range(1, 4):
            try:
                ok = mt5.initialize(
                    login=cfg.MT5_LOGIN,
                    password=cfg.MT5_PASSWORD,
                    server=cfg.MT5_SERVER,
                )
                if ok:
                    self._detect_all_symbols()
                    self._cache_symbols_info()
                    sym_list = ", ".join(self.active_symbols)
                    self._alert(f"✅ MT5 multi-symbol gateway connected\nActive: {sym_list}")
                    logger.info("MT5 initialized (attempt %d) — symbols: %s", attempt, sym_list)
                    return True
                else:
                    err = mt5.last_error()
                    logger.warning("MT5 init attempt %d failed: %s", attempt, err)
            except Exception as exc:
                logger.exception("MT5 init exception attempt %d", attempt)
            time.sleep(2)

        self._alert("❌ MT5 failed to connect after 3 attempts")
        return False

    def _detect_all_symbols(self):
        """Scan broker for all configured symbols (EURUSD + XAUUSD variants)."""
        self.active_symbols = []
        self.symbol_base_map = {}

        for base_symbol in cfg.ACTIVE_SYMBOLS:
            sym_config = cfg.SYMBOLS_CONFIG.get(base_symbol, {})
            candidates = sym_config.get("candidates", [base_symbol])

            detected = None
            for cand in candidates:
                try:
                    if mt5.symbol_select(cand, True):
                        info = mt5.symbol_info(cand)
                        if info is not None:
                            detected = cand
                            break
                except Exception:
                    continue

            if detected:
                self.active_symbols.append(detected)
                self.symbol_base_map[detected] = base_symbol
                if detected != base_symbol:
                    logger.info(f"Auto-detected broker symbol: {base_symbol} → {detected}")
                else:
                    logger.info(f"Auto-detected standard symbol: {detected}")
            else:
                logger.warning(f"Could not detect any valid candidate for {base_symbol}. Skipping.")

        # Update legacy cfg.SYMBOLS for backward compat
        cfg.SYMBOLS = list(self.active_symbols)
        if self.active_symbols:
            cfg.SYMBOL = self.active_symbols[0]

        logger.info(f"Active symbols: {self.active_symbols}")

    def get_base_symbol(self, broker_symbol: str) -> str:
        """Get the base symbol name for a broker-specific symbol."""
        return self.symbol_base_map.get(broker_symbol, broker_symbol)

    def _cache_symbols_info(self):
        for sym in self.active_symbols:
            mt5.symbol_select(sym, True)
            info = mt5.symbol_info(sym)
            if info:
                self.symbols_data[sym] = {
                    "point": info.point,
                    "digits": info.digits,
                    "min_lot": info.volume_min,
                    "max_lot": info.volume_max,
                    "lot_step": info.volume_step
                }
                self.tick_buffer[sym] = deque(maxlen=200)
                logger.info(f"Symbol {sym} cached: point={info.point} digits={info.digits}")
            else:
                logger.error(f"Failed to cache symbol {sym}. Ensure it exists in MT5!")

    def is_connected(self) -> bool:
        try:
            ti = mt5.terminal_info()
            return ti is not None and ti.connected
        except Exception:
            return False

    def reconnect(self) -> bool:
        try:
            mt5.shutdown()
        except Exception:
            pass
        time.sleep(2)
        ok = self.initialize()
        if ok:
            self._alert("🔄 MT5 reconnected")
        return ok

    def shutdown(self):
        try:
            mt5.shutdown()
        except Exception:
            pass

    # ── market data ────────────────────────────────────────────

    def get_ticks(self, symbol: str, count: int = 200):
        """Fetch latest ticks for a specific symbol."""
        try:
            ticks = mt5.copy_ticks_from(
                symbol,
                datetime.now(timezone.utc),
                count,
                mt5.COPY_TICKS_ALL,
            )
            if ticks is not None and len(ticks) > 0:
                if symbol in self.tick_buffer:
                    for t in ticks:
                        self.tick_buffer[symbol].append(t)
                return ticks
            return None
        except Exception as exc:
            self._track_error(f"get_ticks_{symbol}", str(exc))
            return None

    def get_current_tick(self, symbol: str):
        """Fast fetch of the latest bid/ask for a symbol."""
        try:
            return mt5.symbol_info_tick(symbol)
        except Exception as exc:
            self._track_error(f"get_tick_{symbol}", str(exc))
            return None

    def get_candles_m5(self, symbol: str, count: int = 100):
        """Fetch M5 OHLC candles for a symbol."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, count)
            return rates if (rates is not None and len(rates) > 0) else []
        except Exception as exc:
            self._track_error(f"get_candles_m5_{symbol}", str(exc))
            return []

    def get_candles_m1(self, symbol: str, count: int = 20):
        """Fetch M1 OHLC candles for breakout detection."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, count)
            return rates if (rates is not None and len(rates) > 0) else []
        except Exception as exc:
            self._track_error(f"get_candles_m1_{symbol}", str(exc))
            return []

    # ── account info ───────────────────────────────────────────

    def get_account_info(self):
        """Return account equity, balance, free margin."""
        try:
            info = mt5.account_info()
            if info:
                return {
                    "equity": info.equity,
                    "balance": info.balance,
                    "margin_free": info.margin_free,
                    "profit": info.profit,
                }
            return None
        except Exception as exc:
            self._track_error("account_info", str(exc))
            return None

    # ── order execution ────────────────────────────────────────

    def execute_order(self, symbol: str, direction: str, lot: float, tp_pts: int, sl_pts: int):
        """Execute market order for a specific symbol."""
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None or symbol not in self.symbols_data:
                return None, 0, 0

            data = self.symbols_data[symbol]
            point = data["point"]
            digits = data["digits"]

            if direction == "BUY":
                price = tick.ask
                tp = price + tp_pts * point
                sl = price - sl_pts * point
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price = tick.bid
                tp = price - tp_pts * point
                sl = price + sl_pts * point
                order_type = mt5.ORDER_TYPE_SELL

            # Detect best filling mode for this symbol
            type_filling = self._get_filling_mode(symbol)

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": lot,
                "type": order_type,
                "price": round(price, digits),
                "tp": round(tp, digits) if tp_pts > 0 else 0.0,
                "sl": round(sl, digits) if sl_pts > 0 else 0.0,
                "magic": cfg.MAGIC_NUMBER,
                "deviation": 5,
                "type_filling": type_filling,
                "type_time": mt5.ORDER_TIME_GTC,
            }

            t0 = time.perf_counter()
            result = mt5.order_send(request)
            lat = (time.perf_counter() - t0) * 1000

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                slippage = abs(result.price - price) / point if point else 0
                logger.info(f"ORDER {direction} {symbol} lot={lot} latency={lat:.0f}ms")
                return result, lat, slippage
            
            err = result.comment if result else mt5.last_error()
            self._track_error(f"exec_{symbol}", f"Failed: {err}")
            return None, lat, 0
        except Exception as exc:
            self._track_error(f"exec_{symbol}_exc", str(exc))
            return None, 0, 0

    # ── position management ────────────────────────────────────

    def get_open_positions(self, symbol: str = None):
        """Return list of open positions (for specific symbol or all)."""
        try:
            if symbol:
                positions = mt5.positions_get(symbol=symbol)
            else:
                positions = mt5.positions_get()
                
            if positions is None: return []
            return [p for p in positions if p.magic == cfg.MAGIC_NUMBER]
        except Exception as exc:
            self._track_error("get_positions", str(exc))
            return []

    def get_open_positions_for_symbol(self, symbol: str) -> list:
        """Return open positions for a specific symbol only."""
        return self.get_open_positions(symbol=symbol)

    def close_position(self, position):
        """Market-close an open position with symbol awareness."""
        try:
            symbol = position.symbol
            tick = mt5.symbol_info_tick(symbol)
            if tick is None: return None
            
            data = self.symbols_data.get(symbol)
            if not data: return None
            digits = data["digits"]
            
            price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": round(price, digits),
                "magic": cfg.MAGIC_NUMBER,
                "deviation": 10,
                "type_filling": self._get_filling_mode(symbol),
            }
            result = mt5.order_send(request)
            return result if (result and result.retcode == mt5.TRADE_RETCODE_DONE) else None
        except Exception as exc:
            logger.error(f"Close error: {exc}")
            return None

    def close_partial_position(self, position, volume: float):
        """Market-close a partial volume of an open position."""
        try:
            symbol = position.symbol
            tick = mt5.symbol_info_tick(symbol)
            if tick is None: return None
            
            data = self.symbols_data.get(symbol)
            if not data: return None
            digits = data["digits"]
            
            price = tick.bid if position.type == mt5.ORDER_TYPE_BUY else tick.ask
            
            # Ensure volume is rounded to broker volume step
            vol_step = data.get("lot_step", 0.01)
            volume = round(round(volume / vol_step) * vol_step, 2)
            
            # Safeguard volume to not exceed current position volume
            if volume >= position.volume:
                volume = position.volume
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": round(price, digits),
                "magic": cfg.MAGIC_NUMBER,
                "deviation": 10,
                "type_filling": self._get_filling_mode(symbol),
            }
            result = mt5.order_send(request)
            return result if (result and result.retcode == mt5.TRADE_RETCODE_DONE) else None
        except Exception as exc:
            logger.error(f"Close partial error: {exc}")
            return None

    def modify_sl(self, ticket: int, symbol: str, new_sl: float):
        """Modify SL for a specific symbol/ticket."""
        try:
            pos = mt5.positions_get(ticket=ticket)
            if not pos: return False
            pos = pos[0]
            
            data = self.symbols_data.get(symbol)
            if not data: return False
            digits = data["digits"]
            
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": ticket,
                "sl": round(new_sl, digits),
                "tp": pos.tp,
            }
            result = mt5.order_send(request)
            return result and result.retcode == mt5.TRADE_RETCODE_DONE
        except Exception:
            return False

    def modify_tp(self, ticket: int, symbol: str, new_tp: float) -> bool:
        """Modify TP for a specific symbol/ticket. Keeps existing SL unchanged."""
        try:
            pos = mt5.positions_get(ticket=ticket)
            if not pos:
                return False
            pos = pos[0]

            data = self.symbols_data.get(symbol)
            if not data:
                return False
            digits = data["digits"]

            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "symbol": symbol,
                "position": ticket,
                "sl": pos.sl,                      # keep existing SL
                "tp": round(new_tp, digits),        # update TP only
            }
            result = mt5.order_send(request)
            ok = result and result.retcode == mt5.TRADE_RETCODE_DONE
            if ok:
                logger.info(f"[DynamicTP] TP updated → {new_tp:.5f} for #{ticket} {symbol}")
            else:
                err = result.comment if result else mt5.last_error()
                logger.debug(f"[DynamicTP] modify_tp failed for #{ticket}: {err}")
            return ok
        except Exception as exc:
            logger.error(f"modify_tp error #{ticket}: {exc}")
            return False

    def close_all_positions(self):
        """Close everything across all symbols."""
        positions = self.get_open_positions()
        for pos in positions:
            self.close_position(pos)
        if positions:
            self._alert(f"🚨 CLOSED ALL {len(positions)} POSITIONS")
