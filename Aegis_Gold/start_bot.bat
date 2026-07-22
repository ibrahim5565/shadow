@echo off
title Aegis-Gold v6.0 Ultra
color 0A
echo ============================================
echo   AEGIS-GOLD v6.0 ULTRA -- Local AI Bot
echo ============================================
echo.
cd /d %~dp0
python watchdog.py
echo.
echo Bot stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak
start "" "%~f0"
