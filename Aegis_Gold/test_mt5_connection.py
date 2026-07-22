#!/usr/bin/env python3
"""
Test MT5 Connection and Trading Permissions
"""
import MetaTrader5 as mt5
import sys

print('🔍 TESTING METATRADER 5 CONNECTION...')
print('=' * 50)

# Test initialization
if not mt5.initialize():
    print('❌ MT5 initialization failed')
    print('Error:', mt5.last_error())
    sys.exit(1)
else:
    print('✅ MT5 initialized successfully')

# Test account info
account = mt5.account_info()
if account:
    print(f'📊 Account: {account.login}')
    print(f'💰 Balance: ${account.balance:.2f}')
    print(f'💎 Equity: ${account.equity:.2f}')
    print(f'📈 Margin Level: {account.margin_level:.2f}%')
    print(f'🔄 Trade Mode: {"Allowed" if account.trade_allowed else "NOT ALLOWED"}')
    print(f'🤖 Algo Trading: {"Enabled" if account.trade_expert else "DISABLED"}')
else:
    print('❌ Failed to get account info')

# Test symbol info
symbol = 'XAUUSD'
symbol_info = mt5.symbol_info(symbol)
if symbol_info:
    print(f'📈 Symbol: {symbol}')
    print(f'🔄 Trading: {"Enabled" if symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL else "LIMITED"}')
    print(f'📊 Spread: {symbol_info.spread} points')
else:
    print(f'❌ Symbol {symbol} not found')

# Test tick data
tick = mt5.symbol_info_tick(symbol)
if tick:
    print(f'💰 Current Price: {tick.bid}')
    print(f'📊 Spread: {tick.ask - tick.bid:.5f}')
else:
    print('❌ Failed to get tick data')

mt5.shutdown()
print('=' * 50)
print('✅ MT5 CONNECTION TEST COMPLETE')
