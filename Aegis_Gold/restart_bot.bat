@echo off
REM AEGIS AUTO TRADING — BOT RESTART SCRIPT
REM Restarts the bot with all fixes applied

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0

echo.
echo ╔════════════════════════════════════════════╗
echo ║   AEGIS AUTO TRADING BOT — RESTART        ║
echo ╚════════════════════════════════════════════╝
echo.
echo Time: %date% %time%
echo Directory: %SCRIPT_DIR%
echo.

REM Kill any existing Python processes
echo Stopping existing bot instances...
taskkill /IM python.exe /F 2>nul
timeout /t 2 /nobreak >nul

REM Clear old logs
echo Clearing old logs...
del /Q "%SCRIPT_DIR%\logs\telegram.log" 2>nul

REM Start bot with new fixes
echo.
echo Starting AEGIS Bot with SCALPING MODE:
echo ✓ Trade execution at 60%% confidence ONLY
echo ✓ Small profits: $0.50-$1 per trade
echo ✓ NO STOP LOSS - Never close on loss
echo ✓ EURUSD + XAUUSD simultaneous trading
echo ✓ Telegram instant responses
echo.

cd /d "%SCRIPT_DIR%"
python start_aegis.py

REM If we reach here, bot crashed
echo.
echo ERROR: Bot process ended unexpectedly
echo Check logs\aegis.log and logs\errors.log for details
pause
