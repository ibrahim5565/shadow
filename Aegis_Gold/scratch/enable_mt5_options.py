import os
import subprocess
import time

# 1. Kill MT5 if running
print("Checking for running MT5 terminal...")
try:
    subprocess.run("taskkill /F /IM terminal64.exe", shell=True, capture_output=True)
    print("MT5 terminal stopped (if it was running).")
    time.sleep(2)
except Exception as e:
    print(f"Error stopping MT5: {e}")

# 2. Modify common.ini
config_path = r"C:\Users\mohamed ibrahim d\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\config\common.ini"

if os.path.exists(config_path):
    print(f"Modifying config file: {config_path}")
    
    # Read with UTF-16
    with open(config_path, "r", encoding="utf-16") as f:
        lines = f.readlines()
        
    new_lines = []
    in_experts = False
    
    # Track which settings we have written/updated
    keys_to_set = {
        "AllowDllImport": "1",
        "Enabled": "1",
        "WebRequest": "1",
        "WebRequestUrl": "https://api.telegram.org"
    }
    written_keys = set()
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            if in_experts:
                # We are leaving [Experts] section, write any missing keys
                for k, v in keys_to_set.items():
                    if k not in written_keys:
                        new_lines.append(f"  {k}={v}\n")
                        print(f"  Added missing key: {k}={v}")
                in_experts = False
            
            if stripped.lower() == "[experts]":
                in_experts = True
                print("Found [Experts] section.")
            
            new_lines.append(line)
        elif in_experts:
            # We are inside [Experts] section
            if "=" in stripped:
                k, v = stripped.split("=", 1)
                k = k.strip()
                if k in keys_to_set:
                    new_lines.append(f"  {k}={keys_to_set[k]}\n")
                    written_keys.add(k)
                    print(f"  Updated key: {k}={keys_to_set[k]}")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    # If file ends while still in experts section
    if in_experts:
        for k, v in keys_to_set.items():
            if k not in written_keys:
                new_lines.append(f"  {k}={v}\n")
                print(f"  Added missing key: {k}={v}")
                
    # Save back to common.ini
    with open(config_path, "w", encoding="utf-16") as f:
        f.writelines(new_lines)
    print("common.ini successfully updated.")
else:
    print(f"Error: common.ini not found at {config_path}")

# 3. Restart MT5 Terminal
mt5_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
if os.path.exists(mt5_path):
    print(f"Starting MT5 terminal from {mt5_path}...")
    subprocess.Popen([mt5_path])
    time.sleep(5)
    print("MT5 terminal started.")
else:
    print(f"Error: MT5 terminal not found at {mt5_path}")
