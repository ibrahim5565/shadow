@echo off
title Aegis-Gold Safe Start
cd /d "%~dp0"
echo This script no longer kills all Python processes or force-restarts Aegis.
echo Starting the reviewed entry point once.
python start_aegis.py
echo Aegis stopped. Manual review is required before restarting.
pause
