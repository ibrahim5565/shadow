#!/usr/bin/env python3
"""
MetaTrader 5 RSI Trading Bot
Description: Executes a fixed 0.1 lot trade on XAUUSD (H4 timeframe) based on RSI triggers.
             - RSI(14) < 30 -> BUY
             - RSI(14) > 70 -> SELL
             - Limits trade executions to one trade every 120 seconds.
             - Uses simple console logs and plain-text file logging.
             - Clean class-based OOP structure with zero AI or external dependencies.
"""

import os
import sys
import time
import datetime
import pandas as pd
import numpy as np
import MetaTrader5 as mt5

# ==============================================================================
#                      CONFIGURATION VARIABLES
# ==============================================================================
SYMBOL = "XAUUSD"
TIMEFRAME = mt5.TIMEFRAME_H4
POSITION_SIZE = 0.1
STOP_LOSS_PIPS = 0
TAKE_PROFIT_PIPS = 30
TRADE_INTERVAL_SECONDS = 120
RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
MAGIC_NUMBER = 20240604


class Logger:
    """Writes clean and readable plain-text logs for trades and error events."""
    def __init__(self, trades_file="bot_trades.txt", errors_file="bot_errors.txt"):
        self.trades_file = trades_file
        self.errors_file = errors_file

    def log_trade(self, timestamp, symbol, action, price, size, sl, tp, result):
        log_line = f"{timestamp} | {symbol} | {action} | {price:.2f} | {size:.2f} | {sl:.2f} | {tp:.2f} | {result}\n"
        try:
            with open(self.trades_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"[{timestamp}] Error writing trade log: {e}")

    def log_error(self, timestamp, error_code, description):
        log_line = f"{timestamp} | {error_code} | {description}\n"
        try:
            with open(self.errors_file, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as e:
            print(f"[{timestamp}] Error writing error log: {e}")


class MT5Connection:
    """Controls initialization, authentication, status validation, and reconnects."""
    def __init__(self, logger):
        self.logger = logger
        self.account = None
        self.password = None
        self.server = None

    def connect(self, account, password, server) -> bool:
        self.account = account
        self.password = password
        self.server = server
        
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Attempting connection to account {account} on server {server}...")
        try:
            if not mt5.initialize():
                err = mt5.last_error()
                raise ConnectionError(f"MT5 terminal initialization failed. Error details: {err}")
            
            authorized = mt5.login(login=self.account, password=self.password, server=self.server)
            if not authorized:
                err = mt5.last_error()
                raise ConnectionError(f"MT5 authorization login failed. Error details: {err}")
                
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Connected to MT5 Terminal successfully.")
            return True
        except Exception as e:
            ts_err = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.log_error(ts_err, "CONNECTION_FAILED", str(e))
            print(f"[{ts_err}] Connection Exception: {e}")
            return False

    def disconnect(self):
        try:
            mt5.shutdown()
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] MetaTrader 5 terminal shut down.")
        except Exception as e:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.log_error(ts, "DISCONNECT_FAILED", str(e))

    def is_connected(self) -> bool:
        try:
            terminal_info = mt5.terminal_info()
            if terminal_info is None or not terminal_info.connected:
                return False
            return True
        except Exception:
            return False

    def handle_disconnect(self) -> bool:
        if self.is_connected():
            return True
            
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.logger.log_error(ts, "CONNECTION_LOST", "Connection with MT5 lost. Auto-reconnecting...")
        print(f"[{ts}] Connection lost! Initiating auto-reconnect routine...")
        
        for attempt in range(1, 4):
            print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Reconnection attempt {attempt}/3...")
            if mt5.initialize():
                if mt5.login(login=self.account, password=self.password, server=self.server):
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Reconnected successfully.")
                    return True
            time.sleep(5)
            
        print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Reconnection attempts failed.")
        return False


class RSISignalGenerator:
    """Computes technical analysis signals based on standard Wilder's RSI formula."""
    def __init__(self, logger):
        self.logger = logger

    def calculate_rsi(self, prices, period=14) -> float:
        if len(prices) < period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        # Simple Moving Average for first period
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        # Wilder's Smoothing method
        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def get_signal(self, symbol, timeframe) -> tuple:
        try:
            # Copy rates history
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, RSI_PERIOD * 10)
            if rates is None or len(rates) < RSI_PERIOD + 1:
                err = mt5.last_error()
                raise RuntimeError(f"Unable to copy rates for {symbol}. Error details: {err}")
            
            close_prices = np.array([rate['close'] for rate in rates])
            rsi = self.calculate_rsi(close_prices, RSI_PERIOD)
            
            if rsi < RSI_OVERSOLD:
                return "BUY", rsi
            elif rsi > RSI_OVERBOUGHT:
                return "SELL", rsi
            return "HOLD", rsi
        except Exception as e:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.log_error(ts, "SIGNAL_CALCUTION_ERROR", str(e))
            print(f"[{ts}] Signal Engine Exception: {e}")
            raise


class OrderManager:
    """Manages order sending, position closures, parameters scaling, and filters."""
    def __init__(self, magic_number, logger):
        self.magic_number = magic_number
        self.logger = logger

    def get_pip_multiplier(self, symbol_info) -> float:
        digits = symbol_info.digits
        point = symbol_info.point
        if digits in [3, 5]:
            return point * 10.0
        elif digits == 2:
            return 0.1
        else:
            return point

    def _get_filling_mode(self, symbol_info) -> int:
        filling = symbol_info.filling_mode
        if filling & mt5.SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        elif filling & mt5.SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        else:
            return mt5.ORDER_FILLING_RETURN

    def place_buy_order(self, symbol, volume, sl_pips, tp_pips) -> bool:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise RuntimeError(f"Unable to fetch ticks for {symbol}")
                
            symbol_info = mt5.symbol_info(symbol)
            pip_mult = self.get_pip_multiplier(symbol_info)
            digits = symbol_info.digits
            
            price = tick.ask
            sl = round(price - (sl_pips * pip_mult), digits)
            tp = round(price + (tp_pips * pip_mult), digits)
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": self.magic_number,
                "comment": "RSI Bot Entry",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_mode(symbol_info),
            }
            
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise RuntimeError(f"Order placement failed. Return Code: {result.retcode} ({result.comment})")
                
            print(f"[{ts}] BUY execution completed. Ticket ID: {result.order}. Entry Price: {result.price}")
            self.logger.log_trade(ts, symbol, "BUY", result.price, volume, sl, tp, f"SUCCESS ticket: {result.order}")
            return True
        except Exception as e:
            self.logger.log_error(ts, "BUY_ORDER_FAILED", str(e))
            print(f"[{ts}] Place Buy Order Exception: {e}")
            raise

    def place_sell_order(self, symbol, volume, sl_pips, tp_pips) -> bool:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise RuntimeError(f"Unable to fetch ticks for {symbol}")
                
            symbol_info = mt5.symbol_info(symbol)
            pip_mult = self.get_pip_multiplier(symbol_info)
            digits = symbol_info.digits
            
            price = tick.bid
            sl = round(price + (sl_pips * pip_mult), digits)
            tp = round(price - (tp_pips * pip_mult), digits)
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": self.magic_number,
                "comment": "RSI Bot Entry",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._get_filling_mode(symbol_info),
            }
            
            result = mt5.order_send(request)
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                raise RuntimeError(f"Order placement failed. Return Code: {result.retcode} ({result.comment})")
                
            print(f"[{ts}] SELL execution completed. Ticket ID: {result.order}. Entry Price: {result.price}")
            self.logger.log_trade(ts, symbol, "SELL", result.price, volume, sl, tp, f"SUCCESS ticket: {result.order}")
            return True
        except Exception as e:
            self.logger.log_error(ts, "SELL_ORDER_FAILED", str(e))
            print(f"[{ts}] Place Sell Order Exception: {e}")
            raise

    def close_position(self, symbol) -> bool:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            positions = self.get_open_positions()
            if not positions:
                return True
                
            for pos in positions:
                if pos.symbol == symbol:
                    ticket = pos.ticket
                    volume = pos.volume
                    pos_type = pos.type
                    
                    close_type = mt5.ORDER_TYPE_SELL if pos_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
                    tick = mt5.symbol_info_tick(symbol)
                    if tick is None:
                        raise RuntimeError(f"Unable to fetch prices to close ticket {ticket}")
                        
                    price = tick.bid if pos_type == mt5.ORDER_TYPE_BUY else tick.ask
                    symbol_info = mt5.symbol_info(symbol)
                    
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": volume,
                        "type": close_type,
                        "position": ticket,
                        "price": price,
                        "deviation": 20,
                        "magic": self.magic_number,
                        "comment": "RSI Bot Close",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": self._get_filling_mode(symbol_info),
                    }
                    
                    result = mt5.order_send(request)
                    if result.retcode != mt5.TRADE_RETCODE_DONE:
                        raise RuntimeError(f"Close order failed for ticket {ticket}. Retcode: {result.retcode}")
                        
                    print(f"[{ts}] Position ticket {ticket} closed at price {price}")
                    self.logger.log_trade(ts, symbol, "CLOSE", price, volume, 0.0, 0.0, f"CLOSED ticket: {ticket}")
            return True
        except Exception as e:
            self.logger.log_error(ts, "CLOSE_POSITION_FAILED", str(e))
            print(f"[{ts}] Close Position Exception: {e}")
            raise

    def get_open_positions(self):
        positions = mt5.positions_get(symbol=SYMBOL, magic=self.magic_number)
        if positions is None:
            return []
        return list(positions)


class MainBot:
    """Orchestrates connection flow, logic cycles, intervals checking, and safety checks."""
    def __init__(self, account, password, server):
        self.account = account
        self.password = password
        self.server = server
        self.logger = Logger()
        self.conn = MT5Connection(self.logger)
        self.sig_gen = RSISignalGenerator(self.logger)
        self.order_mgr = OrderManager(MAGIC_NUMBER, self.logger)
        self.last_trade_time = 0.0
        self.is_running = False

    def connect(self):
        if not self.conn.connect(self.account, self.password, self.server):
            print("Failed to authenticate MT5 terminal connection. Exiting bot.")
            sys.exit(1)
            
        symbol_info = mt5.symbol_info(SYMBOL)
        if symbol_info is None:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.log_error(ts, "SYMBOL_ERROR", f"Symbol {SYMBOL} not found on server.")
            print(f"[{ts}] Symbol validation failed: {SYMBOL} is not found on server.")
            self.conn.disconnect()
            sys.exit(1)
            
        if not symbol_info.visible:
            mt5.symbol_select(SYMBOL, True)

    def fetch_ohlc(self, symbol, timeframe, bars):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) < bars:
            err = mt5.last_error()
            raise RuntimeError(f"Rates fetch failed. MT5 Error: {err}")
        return pd.DataFrame(rates)

    def check_margin_safety(self):
        info = mt5.account_info()
        if info is None:
            err = mt5.last_error()
            raise RuntimeError(f"Unable to fetch account stats. MT5 Error: {err}")
            
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        margin_level_val = info.margin_level if info.margin else 0.0
        print(f"[{ts}] Balance: {info.balance:.2f} | Margin Free: {info.margin_free:.2f} | Margin Level: {margin_level_val:.2f}%")
        
        # Buffer margin safety filter
        if info.margin_free < 150.0:
            raise PermissionError("Safety Check Blocked: Insufficient free margin to trade.")
        return True

    def execute_trade_logic(self):
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 1. Fetch signal from indicator
        signal, rsi_val = self.sig_gen.get_signal(SYMBOL, TIMEFRAME)
        print(f"[{ts}] Current RSI: {rsi_val:.2f}% | Calculated Signal: {signal}")
        
        # 2. Check time elapsed threshold
        current_time = time.time()
        elapsed = current_time - self.last_trade_time
        
        if elapsed >= TRADE_INTERVAL_SECONDS:
            if signal in ["BUY", "SELL"]:
                print(f"[{ts}] Trade eligibility criteria met. Processing order...")
                
                # Check financial safety metrics
                self.check_margin_safety()
                
                # Retrieve active positions
                positions = self.order_mgr.get_open_positions()
                
                # Ensure 1 position limit rule (close any existing open position)
                if len(positions) > 0:
                    print(f"[{ts}] Active position found. Close request sent to reverse order...")
                    self.order_mgr.close_position(SYMBOL)
                
                # Place live order
                if signal == "BUY":
                    success = self.order_mgr.place_buy_order(SYMBOL, POSITION_SIZE, STOP_LOSS_PIPS, TAKE_PROFIT_PIPS)
                else:  # SELL
                    success = self.order_mgr.place_sell_order(SYMBOL, POSITION_SIZE, STOP_LOSS_PIPS, TAKE_PROFIT_PIPS)
                    
                if success:
                    self.last_trade_time = time.time()
                    print(f"[{ts}] Trade completed. Interval timer reset.")
        else:
            time_left = max(0, int(TRADE_INTERVAL_SECONDS - elapsed))
            print(f"[{ts}] Trade interval locked. Cooldown remaining: {time_left} seconds.")

    def run(self):
        self.is_running = True
        self.last_trade_time = 0.0  # Force immediate check eligibility on boot
        print("MetaTrader 5 RSI Trading Bot is running...")
        
        while self.is_running:
            try:
                # Ensure connection integrity
                if not self.conn.handle_disconnect():
                    print("Terminal disconnection loop failure. Aborting operations.")
                    break
                
                self.execute_trade_logic()
                
                # Scan every 5 seconds to manage status prints and time updates
                time.sleep(5)
            except KeyboardInterrupt:
                print("Shutdown signal detected. Gracefully closing connection...")
                self.is_running = False
            except Exception as e:
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.logger.log_error(ts, "MAIN_CYCLE_ERROR", str(e))
                print(f"[{ts}] Runtime Exception: {e}")
                time.sleep(5)  # Cooldown sleep to prevent terminal loop spamming
                
        self.conn.disconnect()
        print("Bot is stopped.")


# -------------------------------------------------
# Auto‑load MT5 credentials from .env (or system env)
# -------------------------------------------------
if __name__ == "__main__":
    print("=" * 80)
    print("                 METATRADER 5 TECHNICAL RSI TRADING BOT")
    print("=" * 80)

    # Load environment variables from the .env file located in the Aegis_Gold folder
    from dotenv import load_dotenv
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "Aegis_Gold", ".env"))
    load_dotenv(dotenv_path=env_path)

    try:
        account_num = int(os.getenv("MT5_LOGIN"))
        password_str = os.getenv("MT5_PASSWORD")
        server_str = os.getenv("MT5_SERVER", "MetaQuotes-Demo")

        if not all([account_num, password_str, server_str]):
            raise ValueError("Missing MT5 credentials in .env")

        bot = MainBot(account_num, password_str, server_str)
        bot.connect()
        bot.run()
    except Exception as e:
        print(f"\nConfiguration/Runtime Exception: {e}")
        sys.exit(1)
