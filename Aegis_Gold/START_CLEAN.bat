@echo off
cd /d "d:\Trading\Aegis_Gold"
del /Q data\*.lock 2>nul
taskkill /F /IM python.exe 2>nul
timeout /t 2 /nobreak >nul
echo Starting bot...
python SIMPLE_BOT.py
pause
