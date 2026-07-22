@echo off
REM Manual PyTorch GPU Installation - Python 3.14 Workaround
REM Since Python 3.14 is too new, we'll build from source or use conda

echo.
echo ╔════════════════════════════════════════════════════════╗
echo ║   PyTorch GPU Setup - Manual Method                    ║
echo ║   For Python 3.14 + NVIDIA RTX 3050                    ║
echo ╚════════════════════════════════════════════════════════╝
echo.

echo Your Options:
echo ═══════════════════════════════════════════════════════════
echo.
echo OPTION 1: Use Python 3.12 (Recommended - Easiest)
echo ──────────────────────────────────────────────────────────
echo PyTorch officially supports Python 3.9-3.12
echo Download Python 3.12: https://www.python.org/downloads/
echo After installing Python 3.12:
echo   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
echo.
echo OPTION 2: Build PyTorch from Source (Advanced - 2-3 hours)
echo ──────────────────────────────────────────────────────────
echo Requires: Visual Studio 2019/2022, CUDA Toolkit 12.4
echo Steps:
echo   1. Install Visual Studio with C++ tools
echo   2. Install CUDA Toolkit 12.4 from NVIDIA
echo   3. Clone PyTorch: git clone https://github.com/pytorch/pytorch
echo   4. Build: python setup.py install
echo.
echo OPTION 3: Use Conda Environment (Recommended - Medium)
echo ──────────────────────────────────────────────────────────
echo Download Miniconda: https://docs.conda.io/en/latest/miniconda.html
echo Commands:
echo   conda create -n aegis python=3.12
echo   conda activate aegis
echo   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
echo   cd d:\Trading\Aegis_Gold
echo   pip install -r requirements.txt
echo.
echo OPTION 4: Wait for PyTorch 3.14 Support (1-2 months)
echo ──────────────────────────────────────────────────────────
echo PyTorch team is working on Python 3.14 support
echo Check: https://github.com/pytorch/pytorch/issues
echo.
echo ═══════════════════════════════════════════════════════════
echo.
echo ⚡ FASTEST SOLUTION: Use Python 3.12
echo.
echo I recommend uninstalling Python 3.14 and installing Python 3.12.7
echo Then run: COMPLETE_GPU_SETUP.bat
echo.
pause
