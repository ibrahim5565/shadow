import os
import sys
import socket
import urllib.request
import json

print("=== STARTING DIAGNOSTICS ===")
print(f"Python Version: {sys.version}")
print(f"Python Executable: {sys.executable}")
print(f"Working Directory: {os.getcwd()}")

# 1. Check imports
print("\n--- Testing Imports ---")
modules = ["MetaTrader5", "flask", "flask_cors", "requests", "dotenv", "psutil"]
for mod in modules:
    try:
        __import__(mod)
        print(f"  [OK] {mod}")
    except ImportError as e:
        print(f"  [FAIL] {mod}: {e}")

# 2. Check .env variables
print("\n--- Testing Environment Variables ---")
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("  .env loaded successfully.")
    
    mt5_login = os.getenv("MT5_LOGIN")
    mt5_pass = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    tg_token = os.getenv("TELEGRAM_TOKEN")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID")
    anthropic_key = None  # No longer used — Anthropic removed
    
    print(f"  MT5_LOGIN: {'SET (Length: ' + str(len(mt5_login)) + ')' if mt5_login else 'MISSING'}")
    print(f"  MT5_PASSWORD: {'SET' if mt5_pass else 'MISSING'}")
    print(f"  MT5_SERVER: {mt5_server if mt5_server else 'MISSING'}")
    print(f"  TELEGRAM_TOKEN: {'SET' if tg_token else 'MISSING'}")
    print(f"  TELEGRAM_CHAT_ID: {tg_chat if tg_chat else 'MISSING'}")
    # ANTHROPIC_API_KEY removed — local AI only
except Exception as e:
    print(f"  [FAIL] Environment load: {e}")

# 3. Check Network and Telegram API connection
print("\n--- Testing Network & Telegram Bot ---")
if tg_token:
    try:
        url = f"https://api.telegram.org/bot{tg_token}/getMe"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if data.get("ok"):
                print(f"  [OK] Telegram Token is valid. Bot: @{data['result']['username']}")
            else:
                print(f"  [FAIL] Telegram returned: {data}")
    except Exception as e:
         print(f"  [FAIL] Telegram connection: {e}")
else:
    print("  [SKIP] Telegram Token is missing.")

# 4. Test MT5 Initialization and Login
print("\n--- Testing MetaTrader 5 Connection ---")
try:
    import MetaTrader5 as mt5
    if mt5_login and mt5_pass and mt5_server:
        print(f"Attempting to initialize MT5 server '{mt5_server}' with login '{mt5_login}'...")
        # Start MT5 terminal
        ok = mt5.initialize(
            login=int(mt5_login),
            password=mt5_pass,
            server=mt5_server
        )
        if ok:
            print("  [OK] MT5 Initialized and Logged In Successfully!")
            terminal_info = mt5.terminal_info()
            if terminal_info:
                print(f"  Terminal Info: connected={terminal_info.connected}, trade_allowed={terminal_info.trade_allowed}, trade_live={terminal_info.trade_live}")
            acct_info = mt5.account_info()
            if acct_info:
                print(f"  Account Info: balance={acct_info.balance}, equity={acct_info.equity}, profit={acct_info.profit}, leverage={acct_info.leverage}")
            mt5.shutdown()
        else:
            err = mt5.last_error()
            print(f"  [FAIL] MT5 login failed: {err}")
    else:
        print("  [SKIP] MT5 credentials missing in .env.")
except Exception as e:
    print(f"  [FAIL] MT5 connection test: {e}")

# 5. Check Port 5001 (Flask)
print("\n--- Testing Port 5001 Availability ---")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(("127.0.0.1", 5001))
    print("  [OK] Port 5001 is free and available.")
except socket.error as e:
    print(f"  [FAIL] Port 5001 is already in use: {e}")
finally:
    s.close()

print("\n=== DIAGNOSTICS COMPLETE ===")
