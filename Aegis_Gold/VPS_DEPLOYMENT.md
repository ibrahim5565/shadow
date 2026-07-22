# 🚀 AEGIS-GOLD VPS DEPLOYMENT GUIDE

This guide provides step-by-step instructions for deploying the **Aegis-Gold Auto Trading System** to a Windows Virtual Private Server (VPS) for 24/7 stable execution.

---

## 📋 PREREQUISITES

1. **VPS Specifications:**
   - Operating System: Windows Server 2016 / 2019 / 2022 or Windows 10/11 Pro
   - Hardware: Minimum 2 Cores CPU, 4 GB RAM (8 GB recommended for GPU/CUDA acceleration)
   - Network: Low latency to your MetaTrader 5 broker (under 20ms is ideal)

2. **Required Software:**
   - **Python 3.8+** (Ensure you check "Add Python to PATH" during installation)
   - **MetaTrader 5 Terminal** (Installed and logged into your broker account)
   - **NSSM (Non-Sucking Service Manager)**:
     - Download from [nssm.cc/download](https://nssm.cc/download)
     - Extract `nssm.exe` (64-bit version) and add its directory to your system **PATH** variable.

---

## 🛠️ DEPLOYMENT STEPS

### Step 1: Copy Project Files to VPS
Transfer the entire `Aegis_Gold` folder from your local machine to the VPS (recommended location: `C:\Aegis_Gold\`).

### Step 2: Configure Environment Variables
Create a `.env` file in the project root directory (`C:\Aegis_Gold\.env`) and fill in your credentials:

```ini
MT5_LOGIN=your_mt5_account_number
MT5_PASSWORD=your_mt5_password
MT5_SERVER=your_broker_server_name

TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
TELEGRAM_VERIFY_SSL=false
```

### Step 3: Install Python Dependencies
Open command prompt or PowerShell and execute:

```cmd
cd C:\Aegis_Gold
pip install -r requirements.txt
```

*Note: If you plan to run GPU-based reinforcement learning, run the GPU batch setup script:*
```cmd
INSTALL_GPU_REQUIREMENTS.bat
```

### Step 4: Verify Local Setup
Before installing the background service, verify that everything starts up correctly in interactive mode:

```cmd
python validate_deployment.py
python start_aegis.py
```

Check your Telegram. Send `/start` and `/status` to the bot. It should respond instantly.

### Step 5: Install Windows Service (24/7 Autostart)
To ensure the bot continues running after crashes, network disconnections, or VPS reboots, install it as a Windows Service using the provided PowerShell script.

1. Open **PowerShell as Administrator**.
2. Run the installation script:
   ```powershell
   cd C:\Aegis_Gold\persistence
   .\install_service.ps1 -Action install
   ```
3. Start the service:
   ```powershell
   .\install_service.ps1 -Action start
   ```
4. Verify the status:
   ```powershell
   .\install_service.ps1 -Action status
   ```

---

## 🔍 MONITORING AND MAINTENANCE

### Viewing Logs
- Watchdog logs: `C:\Aegis_Gold\logs\watchdog.log`
- Trading bot logs: `C:\Aegis_Gold\logs\aegis.log`
- Errors only: `C:\Aegis_Gold\logs\errors.log`
- Standard output from the service: `C:\Aegis_Gold\logs\stdout.log`

### Emergency Controls
- **Stop Service**: `nssm stop AegisGoldBot`
- **Restart Service**: `nssm restart AegisGoldBot`
- **Telegram Emergency Stop**: Send `/stop` or `/close_all` via Telegram to instantly manage trades.
