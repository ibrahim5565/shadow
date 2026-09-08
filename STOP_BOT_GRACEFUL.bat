@echo off
title STOP BOT - PROCESS TERMINATION
color 0C
cls
echo.
echo  ============================================================
echo    BOT APPLICATION — GRACEFUL STOP PROCESS TERMINATION
echo  ============================================================
echo.

set TARGET_DIR=%~dp0
cd /d "%TARGET_DIR%"

echo  [1/3] Terminating Python processes (Watchdog and Bot)...
taskkill /FI "WINDOWTITLE eq AEGIS-WATCHDOG*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AEGIS-GOLD*" /T /F >nul 2>&1
taskkill /IM python.exe /F >nul 2>&1
taskkill /IM pythonw.exe /F >nul 2>&1

echo  [2/3] Terminating Dashboard Node process...
taskkill /FI "WINDOWTITLE eq AEGIS-FRONTEND*" /T /F >nul 2>&1

echo  [3/3] Cleaning active lock files...
if exist "data\bot.lock"      del /f "data\bot.lock"      >nul 2>&1
if exist "data\watchdog.lock" del /f "data\watchdog.lock" >nul 2>&1
if exist "data\daemon.lock"   del /f "data\daemon.lock"   >nul 2>&1
if exist "Aegis_Gold\data\bot.lock"      del /f "Aegis_Gold\data\bot.lock"      >nul 2>&1
if exist "Aegis_Gold\data\watchdog.lock" del /f "Aegis_Gold\data\watchdog.lock" >nul 2>&1

echo.
echo  [SUCCESS] Bot application stopped successfully.
echo.
exit /b 0
