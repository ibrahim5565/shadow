@echo off
REM ═══════════════════════════════════════════════════════════════════════════════
REM 🚀 START PROFIT FACTOR 100% GPU TRAINING IN BACKGROUND
REM ═══════════════════════════════════════════════════════════════════════════════

echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo    AEGIS PROFIT FACTOR 100%% GPU TRAINING
echo ═══════════════════════════════════════════════════════════════════════════════
echo.
echo Target: 100%% Profit Factor (PF ^>= 2.0)
echo Mode: Continuous background training on NVIDIA GPU
echo.
echo This will start intensive training in a separate window.
echo The training will run continuously until you close the window.
echo.
echo ═══════════════════════════════════════════════════════════════════════════════
echo.

REM Change to Aegis directory
cd /d "d:\Trading\Aegis_Gold"

REM Check if virtual environment exists
if not exist ".venv_cuda\Scripts\python.exe" (
    echo ❌ ERROR: Virtual environment not found at .venv_cuda
    echo.
    echo Please run COMPLETE_GPU_SETUP.bat first to set up the GPU environment.
    echo.
    pause
    exit /b 1
)

REM Start training in a new window (background)
echo Starting PF100 GPU training in background...
echo.

start "AEGIS PF100 GPU Training" /MIN ".venv_cuda\Scripts\python.exe" "TRAIN_PROFIT_FACTOR_100_GPU.py"

if %ERRORLEVEL% EQU 0 (
    echo ✅ Training started successfully in background!
    echo.
    echo 📊 Training is now running in a minimized window.
    echo    Check "logs/pf100_training.log" for progress.
    echo.
    echo To view training progress:
    echo    1. Look for the "AEGIS PF100 GPU Training" window in taskbar
    echo    2. Or read: logs\pf100_training.log
    echo.
    echo To stop training:
    echo    1. Open the training window
    echo    2. Press Ctrl+C
    echo.
) else (
    echo ❌ Failed to start training
    echo Check that Python and dependencies are installed correctly.
    echo.
    pause
    exit /b 1
)

echo ═══════════════════════════════════════════════════════════════════════════════
echo.
pause
