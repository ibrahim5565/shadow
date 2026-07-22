@echo off
cd /d d:\Trading\Aegis_Gold
echo [%date% %time%] STARTING PERSISTENT SUITE > data/vps_lifecycle.log

:: 1. Force kill any old python processes
taskkill /F /IM python.exe /T >nul 2>&1

:: 2. Start Training (20 Epochs)
echo [BUILD] Starting 20-Layer Transformer Training... >> data/vps_lifecycle.log
python -u brain/train_gpt.py >> data/vps_lifecycle.log 2>&1

:: 3. Check if training finished successfully
if exist models\aegis_gpt.pt (
    echo [SYSTEM] Training complete. Launching Aegis-Gold Ultra... >> data/vps_lifecycle.log
    wscript persistence/vps_autostart.vbs
) else (
    echo [ERROR] Training failed. Bot not started. >> data/vps_lifecycle.log
)

echo [STABILITY] Suite Process Finished. >> data/vps_lifecycle.log
