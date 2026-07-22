@echo off
title AEGIS-GOLD v6.0 — STARTUP
color 0A
cls
echo.
echo  ============================================================
echo    AEGIS-GOLD v6.0 ULTRA ^| Local AI Trading Engine
echo  ============================================================
echo.
cd /d %~dp0

:: ── Activate Virtual Environment ──────────────────────────────
echo  [VENV] Activating CUDA virtual environment...
if not exist ".venv_cuda\Scripts\activate.bat" (
    echo  [ERROR] Virtual environment not found. Run GPU setup first.
    pause
    exit /b 1
)
call .venv_cuda\Scripts\activate.bat

:: ── Check MetaTrader 5 ────────────────────────────────────────
echo  [1/4] Checking MetaTrader 5...
tasklist /FI "IMAGENAME eq terminal64.exe" 2>nul | findstr /i "terminal64.exe" >nul
if %errorlevel% neq 0 (
    echo  [MT5] Launching MetaTrader 5...
    if exist "C:\Program Files\MetaTrader 5\terminal64.exe" (
        start "" "C:\Program Files\MetaTrader 5\terminal64.exe"
        echo  [MT5] Waiting 15 seconds for MT5 to initialize...
        timeout /t 15 /nobreak >nul
    ) else (
        echo  [WARN] MT5 not found at default path. Start MT5 manually.
    )
) else (
    echo  [MT5] MetaTrader 5 already running. OK
)

:: ── Check .env ────────────────────────────────────────────────
echo  [2/4] Checking configuration...
if not exist ".env" (
    echo  [ERROR] .env file missing! Copy .env.example to .env and fill in credentials.
    pause
    exit /b 1
)
echo  [CFG] .env loaded. OK

:: ── Clean stale locks ─────────────────────────────────────────
echo  [3/4] Cleaning stale locks...
if exist "data\bot.lock"      del /f "data\bot.lock"      >nul 2>&1
if exist "data\watchdog.lock" del /f "data\watchdog.lock" >nul 2>&1
if exist "data\daemon.lock"   del /f "data\daemon.lock"   >nul 2>&1
echo  [LOCK] Cleared. OK

:: ── Create log directories ────────────────────────────────────
if not exist "logs" mkdir logs
if not exist "data" mkdir data

:: ── Launch Watchdog (keeps bot alive 24/7) ────────────────────
echo  [4/4] Starting Aegis-Gold Watchdog + Trading Engine...
echo.
echo  ============================================================
echo    Dashboard API  : http://localhost:5001/status
echo    Heartbeat      : http://localhost:5001/heartbeat
echo    Trades         : http://localhost:5001/trades
echo  ============================================================
echo.
echo  Close this window or press Ctrl+C to stop the bot.
echo.

python watchdog.py
