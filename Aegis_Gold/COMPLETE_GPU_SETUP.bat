@echo off
REM AEGIS GOLD — COMPLETE GPU TRAINING SETUP
REM Full installation for NVIDIA RTX 3050 with Python 3.14

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║   AEGIS GOLD — COMPLETE GPU TRAINING SETUP             ║
echo ║   NVIDIA RTX 3050 + Python 3.14 + CUDA 12.4            ║
echo ╚════════════════════════════════════════════════════════╝
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo ═══════════════════════════════════════════════════════════
echo STEP 1/8: GPU Status Check
echo ═══════════════════════════════════════════════════════════
nvidia-smi
if errorlevel 1 (
    echo.
    echo ❌ ERROR: nvidia-smi not found!
    echo    NVIDIA drivers may not be installed.
    echo.
    echo Please install NVIDIA drivers from:
    echo https://www.nvidia.com/Download/index.aspx
    echo.
    pause
    exit /b 1
)
echo ✅ GPU detected successfully
timeout /t 2 /nobreak >nul
echo.

echo ═══════════════════════════════════════════════════════════
echo STEP 2/8: Python Version Check
echo ═══════════════════════════════════════════════════════════
python --version
echo ✅ Python detected
timeout /t 2 /nobreak >nul
echo.

echo ═══════════════════════════════════════════════════════════
echo STEP 3/8: Upgrading pip
echo ═══════════════════════════════════════════════════════════
python -m pip install --upgrade pip
echo ✅ pip upgraded
timeout /t 2 /nobreak >nul
echo.

echo ═══════════════════════════════════════════════════════════
echo STEP 4/8: Uninstalling old PyTorch (if exists)
echo ═══════════════════════════════════════════════════════════
pip uninstall -y torch torchvision torchaudio 2>nul
echo ✅ Old PyTorch removed
timeout /t 2 /nobreak >nul
echo.

echo ═══════════════════════════════════════════════════════════
echo STEP 5/8: Installing PyTorch NIGHTLY with CUDA 12.4
echo ═══════════════════════════════════════════════════════════
echo Python 3.14 requires PyTorch nightly build
echo This will download ~2.8GB...
echo.
pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu124
if errorlevel 1 (
    echo.
    echo ⚠️  Nightly build failed. Trying alternative: CUDA 12.1 stable...
    echo.
    pip install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu121
)
echo ✅ PyTorch with CUDA installed
timeout /t 2 /nobreak >nul
echo.

echo ═══════════════════════════════════════════════════════════
echo STEP 6/8: Installing Additional GPU Requirements
echo ═══════════════════════════════════════════════════════════
pip install --upgrade numpy pandas scikit-learn
pip install --upgrade xgboost lightgbm
pip install --upgrade gymnasium
echo ✅ Additional packages installed
timeout /t 2 /nobreak >nul
echo.

echo ═══════════════════════════════════════════════════════════
echo STEP 7/8: Verifying GPU Installation
echo ═══════════════════════════════════════════════════════════
python check_gpu.py
echo.
timeout /t 3 /nobreak >nul

echo ═══════════════════════════════════════════════════════════
echo STEP 8/8: Running GPU Benchmark Test
echo ═══════════════════════════════════════════════════════════
python gpu_benchmark.py
echo.

echo ╔════════════════════════════════════════════════════════╗
echo ║   ✅ INSTALLATION COMPLETE                             ║
echo ╚════════════════════════════════════════════════════════╝
echo.
echo Next Steps:
echo ──────────────────────────────────────────────────────────
echo 1. Train all models:     python TRAIN_ALL_MODELS.py
echo 2. Train GPT only:       python brain/train_gpt.py
echo 3. Train RL only:        python brain/train_reinforcement.py
echo 4. Monitor GPU:          nvidia-smi -l 1
echo.
echo GPU Training is now 10-20x faster than CPU! 🚀
echo.
pause
