@echo off
REM ═══════════════════════════════════════════════════════════════════════════
REM 🚀 AEGIS SCALP PRIORITY STARTUP
REM ═══════════════════════════════════════════════════════════════════════════
REM
REM This script starts AEGIS with:
REM - SCALP mode as PRIMARY (always 50%% threshold)
REM - Unlimited trade limits
REM - Auto-restart every hour
REM - GPU training in background
REM - Trade collection and analysis
REM
REM ═══════════════════════════════════════════════════════════════════════════

echo.
echo ═══════════════════════════════════════════════════════════════════════
echo 🚀 AEGIS GOLD TRADING BOT - SCALP PRIORITY MODE
echo ═══════════════════════════════════════════════════════════════════════
echo.
echo Configuration:
echo   - PRIMARY: SCALP (50%% confidence threshold)
echo   - SECONDARY: SMC (if confidence >= 70%%)
echo   - Trade Limits: UNLIMITED
echo   - Auto-Restart: Every 1 hour
echo   - AI Training: GPU-accelerated background
echo   - Mode: Take every opportunity
echo.
echo ═══════════════════════════════════════════════════════════════════════
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python not found!
    echo    Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo ✅ Python detected
echo.

REM Check if .env file exists
if not exist ".env" (
    echo ❌ ERROR: .env file not found!
    echo    Please create .env file with your credentials
    echo    See .env.example for template
    pause
    exit /b 1
)

echo ✅ .env file found
echo.

REM Create logs directory if not exists
if not exist "logs" mkdir logs

echo 📋 Starting AEGIS components...
echo.

REM Start AI Training in background (separate window)
echo 🎓 Starting AI Training Engine (GPU)...
start "AEGIS AI Training" /MIN python train_institutional_ai.py --mode continuous --gpu
timeout /t 2 /nobreak >nul
echo    ✅ AI Training started in background
echo.

REM Start Auto-Restart Manager (this will start and manage the main bot)
echo 🔄 Starting Auto-Restart Manager (1 hour intervals)...
echo    This will start the main trading bot and restart it every hour
echo.
timeout /t 2 /nobreak >nul

REM This runs in foreground so we can see logs
python auto_restart_bot.py

REM If we get here, the bot was stopped
echo.
echo ═══════════════════════════════════════════════════════════════════════
echo 🛑 AEGIS STOPPED
echo ═══════════════════════════════════════════════════════════════════════
echo.
pause
