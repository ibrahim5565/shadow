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
from quant_ai.execution.demo_guard import DemoGuard

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

    def _demo_account_verified(self) -> bool:
        """Fail closed unless MT5 confirms the connected account is DEMO."""
        try:
            account = mt5.account_info()
            demo_mode = getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", None)
            if account is None or demo_mode is None:
                logger.critical("[DEMO GUARD] Account or DEMO trade-mode constant unavailable")
                return False
            if getattr(cfg, "DEMO_MODE", None) is not True:
                logger.critical("[DEMO GUARD] config/settings.py must keep DEMO_MODE=True")
                return False
            # Use DemoGuard's central TRADING_MODE and ALLOW_LIVE_TRADING policy.
            # Do not derive or override those values from the UI/application mode flag.
            guard = DemoGuard(demo_trade_mode=demo_mode)
            verdict = guard.check(account)
            if not verdict.get("ok"):
                logger.critical("[DEMO GUARD] BLOCKED: %s", verdict.get("reason"))
                return False
            return True
        except Exception as exc:
            logger.critical("[DEMO GUARD] Verification error; blocking: %s", exc)
            return False

    def _broker_request_check(self, request: dict, operation: str) -> bool:
        """Ask the broker to validate the exact request before sending it."""
        try:
            checked = mt5.order_check(request)
            if checked is None:
                logger.error("[ORDER CHECK] %s rejected: broker returned no check result (%s)", operation, mt5.last_error())
                return False
            retcode = getattr(checked, "retcode", None)
            accepted = {0, getattr(mt5, "TRADE_RETCODE_DONE", 10009)}
            if retcode not in accepted:
                logger.error("[ORDER CHECK] %s rejected: retcode=%s comment=%s", operation, retcode, getattr(checked, "comment", ""))
                return False
            return True
        except Exception as exc:
            logger.error("[ORDER CHECK] %s failed; blocking request: %s", operation, exc)
            return False

    def _execution_permitted(self, operation: str) -> bool:
        """Require explicit opt-in plus a freshly verified DEMO account."""
        if not bool(getattr(cfg, "EXECUTION_ENABLED", False)):
            logger.warning("[EXECUTION DISABLED] %s blocked: AEGIS_DEMO_EXECUTION_ENABLED is not true", operation)
            return False
        return self._demo_account_verified()

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
                logger.warning(f"Cannot detect filling mode for {symbol} ? using FOK")
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

            logger.warning(f"[{symbol}] No filling mode passed order_check ? defaulting to FOK")
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
                    if not self._demo_account_verified():
                        logger.critical("Connected MT5 account is not verifiably DEMO; shutting down")
                        mt5.shutdown()
                        return False
                    self._detect_all_symbols()
                    self._cache_symbols_info()
                    sym_list = ", ".join(self.active_symbols)
                    self._alert(f"✅ MT5 multi-symbol gateway connected\nActive: {sym_list}")
                    logger.info("MT5 initialized (attempt %d) ? symbols: %s", attempt, sym_list)
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
                    logger.info(f"Auto-detected broker symbol: {base_symbol} ? {detected}")
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
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 1, count)
            return rates if (rates is not None and len(rates) > 0) else []
        except Exception as exc:
            self._track_error(f"get_candles_m5_{symbol}", str(exc))
            return []

    def get_candles_m1(self, symbol: str, count: int = 20):
        """Fetch M1 OHLC candles for breakout detection."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 1, count)
            return rates if (rates is not None and len(rates) > 0) else []
        except Exception as exc:
            self._track_error(f"get_candles_m1_{symbol}", str(exc))
            return []
    
    def get_candles_m15(self, symbol: str, count: int = 50):
        """Fetch M15 OHLC candles for pattern context analysis."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 1, count)
            return rates if (rates is not None and len(rates) > 0) else []
        except Exception as exc:
            self._track_error(f"get_candles_m15_{symbol}", str(exc))
            return []
    
    def get_candles_m30(self, symbol: str, count: int = 40):
        """Fetch M30 OHLC candles for swing structure analysis."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M30, 1, count)
            return rates if (rates is not None and len(rates) > 0) else []
        except Exception as exc:
            self._track_error(f"get_candles_m30_{symbol}", str(exc))
            return []
    
    def get_candles_h1(self, symbol: str, count: int = 30):
        """Fetch H1 OHLC candles for session trend analysis."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 1, count)
            return rates if (rates is not None and len(rates) > 0) else []
        except Exception as exc:
            self._track_error(f"get_candles_h1_{symbol}", str(exc))
            return []
    
    def get_candles_h4(self, symbol: str, count: int = 24):
        """Fetch H4 OHLC candles for institutional bias analysis."""
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 1, count)
            return rates if (rates is not None and len(rates) > 0) else []
        except Exception as exc:
            self._track_error(f"get_candles_h4_{symbol}", str(exc))
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
                    "margin": info.margin,
                    "margin_level": info.margin_level,
                    "profit": info.profit,
                    "login": info.login,
                    "server": info.server,
                    "trade_mode": info.trade_mode,
                }
            return None
        except Exception as exc:
            self._track_error("account_info", str(exc))
            return None

    def normalize_volume(self, symbol: str, volume: float) -> float:
        """
        Clamps and rounds volume based on MT5 symbol_info specifications:
        volume_min, volume_max, volume_step.
        Guarantees that sent volume will never fail with 'Invalid volume'.
        Always refreshes from live MT5 symbol_info if cached data is incomplete.
        """
        data = self.symbols_data.get(symbol, {})
        min_lot  = data.get("min_lot")
        max_lot  = data.get("max_lot")
        lot_step = data.get("lot_step")

        # Always refresh from live MT5 symbol_info for precision
        try:
            info = mt5.symbol_info(symbol)
            if info:
                if info.volume_min > 0:
                    min_lot = info.volume_min
                if info.volume_max > 0:
                    max_lot = info.volume_max
                if info.volume_step > 0:
                    lot_step = info.volume_step
                # Cache back to symbols_data
                if symbol in self.symbols_data:
                    self.symbols_data[symbol]["min_lot"]  = min_lot
                    self.symbols_data[symbol]["max_lot"]  = max_lot
                    self.symbols_data[symbol]["lot_step"] = lot_step
        except Exception:
            pass

        if not min_lot or min_lot <= 0:
            min_lot = 0.01
        if not max_lot or max_lot <= 0:
            max_lot = 100.0
        if not lot_step or lot_step <= 0:
            lot_step = 0.01

        # Apply both global and per-symbol strategy caps. Never round upward
        # beyond the configured risk cap or silently exceed broker minimums.
        symbol_cfg = cfg.get_symbol_config(symbol)
        configured_cap = min(
            float(getattr(cfg, "MAX_LOT", 0.01)),
            float(symbol_cfg.get("max_lot", getattr(cfg, "MAX_LOT", 0.01))),
        )
        effective_max = min(float(max_lot), configured_cap)
        if configured_cap <= 0 or float(min_lot) > effective_max:
            raise ValueError(
                f"Broker minimum lot {min_lot} exceeds configured risk cap "
                f"{configured_cap} for {symbol}; refusing order"
            )

        requested = float(volume)
        if requested <= 0:
            raise ValueError(f"Requested lot must be positive, got {requested}")
        volume = min(effective_max, max(float(min_lot), requested))

        # Floor to the broker's volume step to avoid rounding above the cap.
        steps = int((volume + 1e-12) / float(lot_step))
        volume = steps * float(lot_step)
        step_str = f"{float(lot_step):.8f}".rstrip("0")
        decimals = min(len(step_str.split(".")[1]) if "." in step_str else 2, 8)
        norm_vol = round(volume, decimals)
        if norm_vol < float(min_lot) or norm_vol > effective_max + 1e-12:
            raise ValueError(
                f"Normalized lot {norm_vol} violates [{min_lot}, {effective_max}] for {symbol}"
            )
        return norm_vol

    # ── order execution ────────────────────────────────────────

    def build_order_request(self, symbol: str, direction: str, lot: float, tp_pts: int, sl_pts: int, price: float = None, type_filling: int = None) -> dict:
        """
        Constructs order request payload with MANDATORY broker-side hard SL enforcement.
        Under NO circumstance will sl_pts <= 0 produce a request with sl = 0.0.
        """
        lot = self.normalize_volume(symbol, lot)
        data = self.symbols_data.get(symbol, {
            "point": 0.01 if "XAU" in symbol.upper() else 0.00001,
            "digits": 2 if "XAU" in symbol.upper() else 5
        })
        point = data["point"]
        digits = data["digits"]
        
        # Enforce Hard SL Floor if sl_pts is missing or below mandatory floor
        is_gold = "XAU" in symbol.upper() or "GOLD" in symbol.upper()
        default_floor_pts = 150 if is_gold else 40
        
        if sl_pts is None or sl_pts < default_floor_pts:
            logger.warning(
                f"[ALERT] [HARD SL FLOOR ENFORCED] Order for {symbol} requested with sl_pts={sl_pts}. "
                f"Floored to {default_floor_pts}pts to prevent dangerously tight or naked broker position."
            )
            self._alert(f"<b>[HARD SL FLOOR FIRED]</b> Order for {symbol} sl_pts={sl_pts} floored to {default_floor_pts}pts.")
            sl_pts = default_floor_pts

        if price is None:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise ValueError(f"Cannot get tick for symbol {symbol}")
            price = tick.ask if direction == "BUY" else tick.bid

        if direction == "BUY":
            tp = price + tp_pts * point if tp_pts > 0 else 0.0
            sl = price - sl_pts * point
            order_type = mt5.ORDER_TYPE_BUY
            # Validate BUY: SL must be below entry, TP must be above entry
            if sl >= price:
                raise ValueError(f"INVALID BUY ORDER: SL ({sl:.5f}) must be < entry ({price:.5f})")
            if tp_pts > 0 and tp <= price:
                raise ValueError(f"INVALID BUY ORDER: TP ({tp:.5f}) must be > entry ({price:.5f})")
        else:
            tp = price - tp_pts * point if tp_pts > 0 else 0.0
            sl = price + sl_pts * point
            order_type = mt5.ORDER_TYPE_SELL
            # Validate SELL: SL must be above entry, TP must be below entry
            if sl <= price:
                raise ValueError(f"INVALID SELL ORDER: SL ({sl:.5f}) must be > entry ({price:.5f})")
            if tp_pts > 0 and tp >= price:
                raise ValueError(f"INVALID SELL ORDER: TP ({tp:.5f}) must be < entry ({price:.5f})")

        sl_rounded = round(sl, digits)
        if sl_rounded <= 0.0:
            raise ValueError(f"CRITICAL SAFETY VIOLATION: Calculated SL price {sl_rounded} is invalid for {symbol}")

        if type_filling is None:
            type_filling = self._get_filling_mode(symbol)

        return {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": round(price, digits),
            "tp": round(tp, digits) if tp_pts > 0 else 0.0,
            "sl": sl_rounded,  # GUARANTEED NON-ZERO
            "magic": cfg.MAGIC_NUMBER,
            "deviation": 5,
            "type_filling": type_filling,
            "type_time": mt5.ORDER_TIME_GTC,
        }

    def verify_sl_enforcement(self) -> bool:
        """
        Startup/pre-trade self-check: Verifies that any order built with sl_pts <= 0
        is floored to a non-zero SL price and never produces sl=0.0.
        """
        for test_sym in ["XAUUSD", "EURUSD"]:
            req = self.build_order_request(
                symbol=test_sym, direction="BUY", lot=0.01, tp_pts=100, sl_pts=0, price=2000.0 if "XAU" in test_sym else 1.1000, type_filling=mt5.ORDER_FILLING_FOK
            )
            if req.get("sl", 0.0) == 0.0:
                logger.critical(f"[ERR] [SL SAFETY VERIFICATION FAILED] Symbol {test_sym} generated sl=0.0 payload!")
                return False
        logger.info("[OK] [SL SAFETY VERIFICATION PASSED] Mandatory broker-side SL floor active for all symbols.")
        return True

    def execute_order(self, symbol: str, direction: str, lot: float, tp_pts: int, sl_pts: int, session: str = "LONDON"):
        """Execute market order for a specific symbol with mandatory hard SL enforcement."""
        try:
            if not self._execution_permitted("open order"):
                return None, 0, 0
            precheck = self.pre_execution_check(symbol, direction, session=session, lot=lot)
            if not precheck.get("ok"):
                logger.warning("[PRE-EXECUTION BLOCK] %s %s: %s", direction, symbol, precheck.get("reason"))
                return None, float(precheck.get("latency_ms", 0.0)), 0
            tick = mt5.symbol_info_tick(symbol)
            if tick is None or symbol not in self.symbols_data:
                return None, 0, 0

            data = self.symbols_data[symbol]
            point = data["point"]
            price = tick.ask if direction == "BUY" else tick.bid

            request = self.build_order_request(
                symbol=symbol, direction=direction, lot=lot, tp_pts=tp_pts, sl_pts=sl_pts, price=price
            )

            # ── STRICT SYMMETRICAL VALIDATION (Requirements 10, 11, 12) ──────────
            if direction == "SELL":
                if request["type"] != mt5.ORDER_TYPE_SELL:
                    logger.error(f"[ORDER REJECTED] SELL assertion failed: order type {request['type']} != ORDER_TYPE_SELL")
                    return None, 0, 0
                if request["sl"] <= price:
                    logger.error(f"[ORDER REJECTED] SELL assertion failed: SL {request['sl']} <= entry {price}")
                    return None, 0, 0
                if tp_pts > 0 and request["tp"] >= price:
                    logger.error(f"[ORDER REJECTED] SELL assertion failed: TP {request['tp']} >= entry {price}")
                    return None, 0, 0
            elif direction == "BUY":
                if request["type"] != mt5.ORDER_TYPE_BUY:
                    logger.error(f"[ORDER REJECTED] BUY assertion failed: order type {request['type']} != ORDER_TYPE_BUY")
                    return None, 0, 0
                if request["sl"] >= price:
                    logger.error(f"[ORDER REJECTED] BUY assertion failed: SL {request['sl']} >= entry {price}")
                    return None, 0, 0
                if tp_pts > 0 and request["tp"] <= price:
                    logger.error(f"[ORDER REJECTED] BUY assertion failed: TP {request['tp']} <= entry {price}")
                    return None, 0, 0
            else:
                logger.error(f"[ORDER REJECTED] Invalid direction: {direction}")
                return None, 0, 0

            # Broker-side stop-distance validation uses the current symbol contract.
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logger.error("[ORDER REJECTED] Symbol contract unavailable for %s", symbol)
                return None, 0, 0
            min_stop_distance = float(getattr(symbol_info, "trade_stops_level", 0) or 0) * point
            if direction == "BUY":
                if price - request["sl"] < min_stop_distance:
                    logger.error("[ORDER REJECTED] BUY SL violates broker stop level for %s", symbol)
                    return None, 0, 0
                if tp_pts > 0 and request["tp"] - price < min_stop_distance:
                    logger.error("[ORDER REJECTED] BUY TP violates broker stop level for %s", symbol)
                    return None, 0, 0
            else:
                if request["sl"] - price < min_stop_distance:
                    logger.error("[ORDER REJECTED] SELL SL violates broker stop level for %s", symbol)
                    return None, 0, 0
                if tp_pts > 0 and price - request["tp"] < min_stop_distance:
                    logger.error("[ORDER REJECTED] SELL TP violates broker stop level for %s", symbol)
                    return None, 0, 0
            if not self._broker_request_check(request, f"{direction} {symbol}"):
                return None, 0, 0

            t0 = time.perf_counter()
            result = mt5.order_send(request)
            lat = (time.perf_counter() - t0) * 1000

            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                slippage = abs(result.price - price) / point if point else 0
                logger.info(f"ORDER {direction} {symbol} lot={lot} sl={request['sl']} latency={lat:.0f}ms")
                return result, lat, slippage
            
            retcode = result.retcode if result else "N/A"
            comment = result.comment if result else mt5.last_error()
            err_msg = f"retcode={retcode} ({comment})"
            logger.error(f"[ORDER REJECTED] {direction} {symbol} lot={request.get('volume')} payload={request} -> {err_msg}")
            self._track_error(f"exec_{symbol}", f"Failed: {err_msg}")
            return None, lat, 0
        except Exception as exc:
            self._track_error(f"exec_{symbol}_exc", str(exc))
            return None, 0, 0

    def pre_execution_check(
        self,
        symbol: str,
        direction: str,
        session: str = "LONDON",
        latency_abort_ms: float = 100.0,
        lot: float = 0.01,
    ) -> dict:
        """
        Zero-Bypass pre-execution safety check (Phase 4 — Sniper Mode).
        Must pass ALL checks within 10ms of signal before order dispatch.

        Checks:
          1. MT5 connection alive
          2. Free margin >= required margin for 0.01 lot
          3. Current spread <= session spread limit
          4. Tick fetch latency <= latency_abort_ms (default: 100ms)

        Returns:
            { "ok": bool, "reason": str, "latency_ms": float, "spread": float }
        """
        import time as _time

        t_start = _time.perf_counter()

        # 1. MT5 Connection Check
        try:
            acct = mt5.account_info()
            if acct is None:
                return {"ok": False, "reason": "MT5_DISCONNECTED", "latency_ms": 0.0, "spread": 0.0}
        except Exception as _ce:
            return {"ok": False, "reason": f"MT5_CONNECTION_ERROR:{_ce}", "latency_ms": 0.0, "spread": 0.0}

        # 2. Tick fetch + Latency check
        try:
            tick = mt5.symbol_info_tick(symbol)
            lat_ms = (_time.perf_counter() - t_start) * 1000
            if tick is None:
                return {"ok": False, "reason": f"TICK_UNAVAILABLE:{symbol}", "latency_ms": lat_ms, "spread": 0.0}
            if lat_ms > latency_abort_ms:
                logger.warning(f"[SNIPER LATENCY GUARD] {symbol} tick fetch took {lat_ms:.0f}ms > {latency_abort_ms:.0f}ms — aborting")
                return {"ok": False, "reason": f"LATENCY_GUARD_ABORT:{lat_ms:.0f}ms>{latency_abort_ms:.0f}ms", "latency_ms": lat_ms, "spread": 0.0}
        except Exception as _te:
            return {"ok": False, "reason": f"TICK_FETCH_ERROR:{_te}", "latency_ms": 0.0, "spread": 0.0}

        # 3. Spread Check
        try:
            sym_info = mt5.symbol_info(symbol)
            if sym_info is None:
                return {"ok": False, "reason": f"SYMBOL_INFO_UNAVAILABLE:{symbol}", "latency_ms": lat_ms, "spread": 0.0}
            spread_pts = sym_info.spread
            global_spread_limit = float(cfg.SPREAD_LIMITS.get(session, 40))
            symbol_spread_limits = cfg.get_symbol_config(symbol).get("spread_limits", {})
            symbol_spread_limit = float(symbol_spread_limits.get(session, global_spread_limit))
            # Apply the stricter of the global and symbol-specific limits.
            spread_limit = min(global_spread_limit, symbol_spread_limit)
            if spread_pts > spread_limit:
                    return {
                        "ok": False,
                        "reason": f"SPREAD_TOO_WIDE:{spread_pts}pts>{spread_limit}pts({session})",
                        "latency_ms": lat_ms,
                        "spread": float(spread_pts),
                    }
        except Exception as _sp:
            return {"ok": False, "reason": f"SPREAD_CHECK_ERROR:{_sp}", "latency_ms": lat_ms, "spread": 0.0}

        # 4. Margin Check (0.01 lot minimum)
        try:
            price = tick.ask if direction == "BUY" else tick.bid
            margin_req = mt5.order_calc_margin(
                mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
                symbol, lot, price
            )
            if margin_req is None:
                return {"ok": False, "reason": "MARGIN_CALCULATION_UNAVAILABLE", "latency_ms": lat_ms, "spread": float(spread_pts)}
            if acct.margin_free < margin_req:
                return {
                    "ok": False,
                    "reason": f"INSUFFICIENT_MARGIN:free={acct.margin_free:.2f}<required={margin_req:.2f}",
                    "latency_ms": lat_ms,
                    "spread": float(spread_pts),
                }
        except Exception as _me:
            return {"ok": False, "reason": f"MARGIN_CHECK_ERROR:{_me}", "latency_ms": lat_ms, "spread": float(spread_pts)}

        lat_ms = (_time.perf_counter() - t_start) * 1000
        return {"ok": True, "reason": "PRE_CHECK_PASS", "latency_ms": lat_ms, "spread": float(spread_pts)}

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
            if not self._execution_permitted("close position") or not self._broker_request_check(request, "close position"):
                return None
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
            if not self._execution_permitted("close position") or not self._broker_request_check(request, "close position"):
                return None
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
            if not self._execution_permitted("modify stop loss") or not self._broker_request_check(request, "modify stop loss"):
                return False
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
            if not self._execution_permitted("modify take profit") or not self._broker_request_check(request, "modify take profit"):
                return False
            result = mt5.order_send(request)
            ok = result and result.retcode == mt5.TRADE_RETCODE_DONE
            if ok:
                logger.info(f"[DynamicTP] TP updated ? {new_tp:.5f} for #{ticket} {symbol}")
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
