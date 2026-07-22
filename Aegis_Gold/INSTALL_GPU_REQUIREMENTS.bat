@echo off
REM AEGIS GOLD — GPU Training Setup
REM Installs PyTorch with CUDA 12.4 support for NVIDIA RTX 3050

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════╗
echo ║   AEGIS GOLD GPU TRAINING SETUP            ║
echo ║   Installing CUDA-Enabled PyTorch          ║
echo ╚════════════════════════════════════════════╝
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

echo [STEP 1/4] Checking GPU Status...
echo ─────────────────────────────────────────────
nvidia-smi
echo.

echo [STEP 2/4] Uninstalling CPU-only PyTorch...
echo ─────────────────────────────────────────────
pip uninstall -y torch torchvision torchaudio
echo.

echo [STEP 3/4] Installing PyTorch with CUDA 12.4 support...
echo ─────────────────────────────────────────────
echo This will download ~2.5GB of packages...
echo.
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
echo.

echo [STEP 4/4] Verifying GPU Installation...
echo ─────────────────────────────────────────────
python check_gpu.py
echo.

echo ╔════════════════════════════════════════════╗
echo ║   INSTALLATION COMPLETE                    ║
echo ╚════════════════════════════════════════════╝
echo.
echo If CUDA is available, you can now train models on GPU!
echo GPU training will be 10-20x faster than CPU.
echo.
echo Next steps:
echo 1. Run: python TRAIN_ALL_MODELS.py (for full training)
echo 2. Or:  python brain/train_gpt.py (for GPT model only)
echo.
pause
