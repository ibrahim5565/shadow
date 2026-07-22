import MetaTrader5 as mt5
import sys

LOGIN = 10010503332
PASS = "FjJ@Rc6d"
SERVER = "MetaQuotes-Demo"

if not mt5.initialize(login=LOGIN, password=PASS, server=SERVER):
    print(f"FAILED to initialize MT5: {mt5.last_error()}")
    mt5.shutdown()
    sys.exit(1)

info = mt5.terminal_info()
if info:
    print(f"MT5 Terminal Info: Connected={info.connected}, DLLsAllowed={info.dlls_allowed}, TradeAllowed={info.trade_allowed}")
else:
    print("FAILED to get terminal info")

acct = mt5.account_info()
if acct:
    print(f"Account Info: Login={acct.login}, Server={acct.server}, Balance={acct.balance}, Equity={acct.equity}")
else:
    print(f"FAILED to get account info: {mt5.last_error()}")

mt5.shutdown()
