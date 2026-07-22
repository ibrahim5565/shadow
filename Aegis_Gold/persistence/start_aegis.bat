@echo off
REM AEGIS AUTO TRADING — START SCRIPT
REM Run this to start the bot on Windows VPS

setlocal enabledelayedexpansion

REM Get script directory
set SCRIPT_DIR=%~dp0..
set PYTHON_EXE=python.exe

REM Check if Python is available
where %PYTHON_EXE% >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Please install Python 3.8+ and add to PATH
    pause
    exit /b 1
)

echo.
echo ========================================
echo AEGIS AUTO TRADING SYSTEM
echo ========================================
echo.
echo Starting trading bot...
echo Directory: %SCRIPT_DIR%
echo Time: %date% %time%
echo.

REM Create logs directory if it doesn't exist
if not exist "%SCRIPT_DIR%\logs" (
    mkdir "%SCRIPT_DIR%\logs"
)

REM Start Python process
cd /d "%SCRIPT_DIR%"
%PYTHON_EXE% start_aegis.py

echo.
echo Bot process ended. Check logs\aegis.log for details.
pause
