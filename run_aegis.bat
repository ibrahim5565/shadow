@echo off
title AEGIS GOLD MASTER CONTROL
setlocal enabledelayedexpansion

echo.
echo ===================================================
echo   AEGIS-GOLD v6.0 MASTER STARTUP SEQUENCE
echo ===================================================
echo.

:: 1. Start MetaTrader 5
echo [+] Starting MetaTrader 5...
if exist "C:\Program Files\MetaTrader 5\terminal64.exe" (
    start "" "C:\Program Files\MetaTrader 5\terminal64.exe"
) else (
    echo [!] WARNING: MetaTrader 5 not found at default path.
)
ping 127.0.0.1 -n 3 >nul

:: 2. Start Dashboard Server (Background)
echo [+] Starting Dashboard Server...
cd /d "D:\Trading\aegis_dashboard"
start "AEGIS-FRONTEND" /min cmd /c "npm run dev"
ping 127.0.0.1 -n 6 >nul

:: 3. Start Python Watchdog Backend
echo [+] Starting Python Watchdog Backend...
cd /d "D:\Trading\Aegis_Gold"
start "AEGIS-WATCHDOG" .venv_cuda\Scripts\python.exe watchdog.py

echo.
echo ===================================================
echo   SYSTEMS OPERATIONAL - DASHBOARD OPENING...
echo ===================================================
echo.
echo TIP: Create a shortcut of this file on your Desktop 
     echo      for one-click trading access!
echo.
ping 127.0.0.1 -n 6 >nul
exit
