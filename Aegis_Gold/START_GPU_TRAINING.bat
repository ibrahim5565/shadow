@echo off
echo ================================================================
echo   AEGIS GOLD - GPU TRAINING ON NVIDIA RTX 3050
echo   PyTorch 2.6.0 + CUDA 12.4
echo ================================================================
echo.

call "C:\Users\mohamed ibrahim d\Miniconda3\Scripts\activate.bat" aegis

echo GPU Status:
python -c "import torch; print('  GPU:', torch.cuda.get_device_name(0)); print('  VRAM:', round(torch.cuda.get_device_properties(0).total_memory/1024**3,1), 'GB'); print('  CUDA:', torch.version.cuda)"
echo.

echo Starting full model training pipeline...
echo ----------------------------------------------------------------
echo  Models to train:
echo   1. GPT Brain Model      (100 epochs) - ~10-15 min on GPU
echo   2. RL Agent             (50 epochs)  - ~3-5 min on GPU
echo   3. Adaptive Learning    (baseline)   - ~1 min
echo   4. XGBoost              (if data)    - ~2 min
echo ----------------------------------------------------------------
echo  Total estimated: 15-25 minutes  (was 4+ hours on CPU!)
echo ================================================================
echo.

cd /d "d:\Trading\Aegis_Gold"
python TRAIN_ALL_MODELS.py

if %errorlevel% equ 0 (
    echo.
    echo ================================================================
    echo   TRAINING COMPLETE!
    echo   All models saved to: models\
    echo ================================================================
) else (
    echo.
    echo ERROR: Training failed - check output above
)

echo.
pause
