@echo off
title AEGIS-GOLD — STOP
color 0C
echo.
echo  ============================================================
echo    AEGIS-GOLD — EMERGENCY STOP
echo  ============================================================
echo.
cd /d %~dp0

echo  Killing all Python processes (watchdog + bot + daemon)...
taskkill /F /IM python.exe /T >nul 2>&1
taskkill /F /IM pythonw.exe /T >nul 2>&1

echo  Removing lock files...
if exist "data\bot.lock"      del /f "data\bot.lock"
if exist "data\watchdog.lock" del /f "data\watchdog.lock"
if exist "data\daemon.lock"   del /f "data\daemon.lock"

echo.
echo  [DONE] All Aegis processes stopped and locks cleared.
echo.
pause
