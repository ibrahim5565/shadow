@echo off
title AEGIS TRADING BOT - WINDOWS HOME CONTROL PANEL
color 0A
cls

:MENU
cls
echo ============================================================
echo      AEGIS GOLD TRADING BOT — CONTROL PANEL (WINDOWS HOME)
echo ============================================================
echo.

:: Check current running status
tasklist /FI "WINDOWTITLE eq AEGIS-WATCHDOG*" 2>nul | findstr /i "python" >nul
if %errorlevel% equ 0 (
    echo   STATUS: [ ONLINE / RUNNING ]
) else (
    echo   STATUS: [ OFFLINE / STOPPED ]
)

echo.
echo ============================================================
echo   1. START Bot (Silent / Background Mode)
echo   2. START Bot (Visible Console Window)
echo   3. STOP  Bot (Graceful Stop & Kill Processes)
echo   4. RESTART Bot
echo   5. CHECK Status & Running Processes
echo   6. EXIT
echo ============================================================
echo.

set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" goto START_SILENT
if "%choice%"=="2" goto START_VISIBLE
if "%choice%"=="3" goto STOP_BOT
if "%choice%"=="4" goto RESTART_BOT
if "%choice%"=="5" goto CHECK_STATUS
if "%choice%"=="6" exit
goto MENU

:START_SILENT
echo.
echo [+] Starting Bot in Silent Background Mode...
wscript.exe "%~dp0START_BOT_SILENT.vbs"
echo [SUCCESS] Bot launch sequence initiated in background.
timeout /t 3 >nul
goto MENU

:START_VISIBLE
echo.
echo [+] Starting Bot in Console Mode...
call "%~dp0run_aegis.bat"
goto MENU

:STOP_BOT
echo.
echo [-] Stopping Bot & Killing Processes...
call "%~dp0STOP_BOT_GRACEFUL.bat"
goto MENU

:RESTART_BOT
echo.
echo [*] Restarting Trading Bot...
call "%~dp0STOP_BOT_GRACEFUL.bat"
timeout /t 2 >nul
wscript.exe "%~dp0START_BOT_SILENT.vbs"
echo [SUCCESS] Bot restarted successfully.
timeout /t 3 >nul
goto MENU

:CHECK_STATUS
cls
echo ============================================================
echo               ACTIVE BOT PROCESSES CHECK
echo ============================================================
echo.
echo --- Python Processes ---
tasklist /FI "IMAGENAME eq python.exe"
echo.
echo --- MetaTrader 5 ---
tasklist /FI "IMAGENAME eq terminal64.exe"
echo.
echo --- Dashboard (Node) ---
tasklist /FI "IMAGENAME eq node.exe"
echo.
echo Press any key to return to menu...
pause >nul
goto MENU
