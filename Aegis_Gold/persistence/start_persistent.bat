@echo off
cd /d d:\Trading\Aegis_Gold
echo Starting Persistent Aegis-Gold... >> data/vps_lifecycle.log
date /t >> data/vps_lifecycle.log
time /t >> data/vps_lifecycle.log

:: Ensure MetaTrader 5 is running
tasklist /FI "IMAGENAME eq terminal64.exe" | findstr /i "terminal64.exe" > nul
if %errorlevel% neq 0 (
    echo [VPS] Starting MetaTrader 5... >> data/vps_lifecycle.log
    start "" "C:\Program Files\MetaTrader 5\terminal64.exe"
    timeout /t 10
)

:: Run the watchdog (this keeps the main bot alive)
python watchdog.py >> data/watchdog_stdout.log 2>&1
