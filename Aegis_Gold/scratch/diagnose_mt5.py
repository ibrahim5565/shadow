import os
import sys
import MetaTrader5 as mt5
from dotenv import load_dotenv

# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

from config import settings as cfg

def run_diagnostics():
    print("=" * 60)
    print("         METATRADER 5 DIAGNOSTIC AUDIT WORKSPACE")
    print("=" * 60)
    
    # 1. Initialize MT5
    login = int(os.environ.get("MT5_LOGIN", "0"))
    password = os.environ.get("MT5_PASSWORD", "")
    server = os.environ.get("MT5_SERVER", "MetaQuotes-Demo")
    
    print(f"Connecting to server: {server} using login: {login}...")
    initialized = mt5.initialize(login=login, password=password, server=server)
    if not initialized:
        print(f"[-] MT5 Initialize Failed! Error code: {mt5.last_error()}")
        return
    print("[+] MT5 Initialized Successfully.")
    
    # 2. Account Connected Check
    acct = mt5.account_info()
    if acct is None:
        print("[-] Account Info: DISCONNECTED (Failed to fetch account info)")
    else:
        print("[+] Account Info: CONNECTED")
        print(f"    - Login: {acct.login}")
        print(f"    - Name: {acct.name}")
        print(f"    - Broker/Server: {acct.server}")
        print(f"    - Balance: ${acct.balance:.2f}")
        print(f"    - Equity: ${acct.equity:.2f}")
        print(f"    - Trade Allowed on Account: {acct.trade_allowed}")
        print(f"    - Trade Expert Allowed: {acct.trade_expert}")
        
    # 3. Terminal Trade Status
    term = mt5.terminal_info()
    if term is None:
        print("[-] Terminal Info: Failed to fetch terminal info")
    else:
        print("[+] Terminal Info:")
        print(f"    - Connected: {term.connected}")
        print(f"    - Algo Trading Enabled: {term.trade_allowed}")
        print(f"    - Live Trading Allowed (License): {getattr(term, 'trade_live', False)}")
        
    # 4. Symbols Scan
    print("[+] Scanning Active Symbols...")
    for sym in cfg.ACTIVE_SYMBOLS:
        sym_config = cfg.SYMBOLS_CONFIG.get(sym, {})
        candidates = sym_config.get("candidates", [sym])
        detected = None
        for cand in candidates:
            if mt5.symbol_select(cand, True):
                info = mt5.symbol_info(cand)
                if info is not None:
                    detected = cand
                    break
        if detected:
            print(f"    - Symbol '{sym}' -> Detected as broker symbol '{detected}'")
            print(f"      * Point: {info.point}")
            print(f"      * Digits: {info.digits}")
            print(f"      * Trade Mode: {info.trade_mode}")
            print(f"      * Execution Mode: {getattr(info, 'trade_execution', 'N/A')}")
            
            # Check filling modes bitmask
            # 1 = FOK, 2 = IOC, 4 = RETURN
            fm = info.filling_mode
            print(f"      * Filling Mode Bitmask: {fm} (1=FOK, 2=IOC, 4=RETURN)")
            print(f"        IOC Supported: {bool(fm & 2)}")
            print(f"        FOK Supported: {bool(fm & 1)}")
            
            # 5. Fetch tick data
            tick = mt5.symbol_info_tick(detected)
            if tick:
                print(f"      * Tick Data Available: Bid={tick.bid}, Ask={tick.ask}, Time={tick.time}")
            else:
                print("      * Tick Data: [!] FAILED TO RETRIEVE TICK DATA")
                
            # 6. Test order_check (Dry-run order check)
            # Create a mock trade request to check order_check reachability
            lot = 0.10
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": detected,
                "volume": lot,
                "type": mt5.ORDER_TYPE_BUY,
                "price": tick.ask if tick else 1.0,
                "deviation": 5,
                "type_filling": mt5.ORDER_FILLING_IOC,
                "type_time": mt5.ORDER_TIME_GTC,
            }
            check_result = mt5.order_check(request)
            if check_result is None:
                print(f"      * order_check(): [!] Unreachable or failed. Error: {mt5.last_error()}")
            else:
                print(f"      * order_check() test with ORDER_FILLING_IOC: retcode={check_result.retcode}, comment={check_result.comment}")
                
            # Let's test with other filling modes to see what succeeds
            request["type_filling"] = mt5.ORDER_FILLING_FOK
            check_fok = mt5.order_check(request)
            print(f"      * order_check() test with ORDER_FILLING_FOK: retcode={check_fok.retcode if check_fok else 'None'}, comment={check_fok.comment if check_fok else 'None'}")
            
            request["type_filling"] = mt5.ORDER_FILLING_RETURN
            check_ret = mt5.order_check(request)
            print(f"      * order_check() test with ORDER_FILLING_RETURN: retcode={check_ret.retcode if check_ret else 'None'}, comment={check_ret.comment if check_ret else 'None'}")
        else:
            print(f"    - [!] Symbol '{sym}': Could not detect any valid broker candidate among {candidates}")
            
    mt5.shutdown()
    print("=" * 60)

if __name__ == "__main__":
    run_diagnostics()
