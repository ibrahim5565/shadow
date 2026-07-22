import MetaTrader5 as mt5
from dotenv import load_dotenv
import os

load_dotenv()

if mt5.initialize(
    login=int(os.getenv("MT5_LOGIN")),
    password=os.getenv("MT5_PASSWORD"),
    server=os.getenv("MT5_SERVER")
):
    ti = mt5.terminal_info()
    ai = mt5.account_info()
    if ti:
        print("\nTerminalInfo fields:")
        for attr in dir(ti):
            if not attr.startswith("_"):
                print(f"  {attr}: {getattr(ti, attr)}")
    if ai:
        print("\nAccountInfo fields:")
        for attr in dir(ai):
            if not attr.startswith("_"):
                print(f"  {attr}: {getattr(ai, attr)}")
    mt5.shutdown()
else:
    print("MT5 Init Failed")
