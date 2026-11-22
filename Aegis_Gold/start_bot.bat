@echo off
title Aegis-Gold Safe Start
cd /d "%~dp0"
echo Starting the reviewed Aegis entry point once. No restart loop is enabled.
python start_aegis.py
echo Aegis stopped. It will not restart automatically.
pause
