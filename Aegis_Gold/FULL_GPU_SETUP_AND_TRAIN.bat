@echo off
REM AEGIS GOLD — COMPLETE GPU SETUP AND TRAINING
REM Installs Conda, PyTorch GPU, all requirements, and starts training

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║   AEGIS GOLD — COMPLETE GPU SETUP + TRAINING                   ║
echo ║   Installing Conda + Python 3.12 + PyTorch CUDA + Training     ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Check if conda already exists
where conda >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Conda already installed
    goto :skip_conda_install
)

echo ═══════════════════════════════════════════════════════════════════
echo STEP 1/10: Downloading Miniconda
echo ═══════════════════════════════════════════════════════════════════
echo This will download ~100MB...
echo.

set CONDA_INSTALLER=Miniconda3-latest-Windows-x86_64.exe
set CONDA_URL=https://repo.anaconda.com/miniconda/%CONDA_INSTALLER%

REM Download Miniconda using PowerShell
powershell -Command "& {Invoke-WebRequest -Uri '%CONDA_URL%' -OutFile '%TEMP%\%CONDA_INSTALLER%'}"

if not exist "%TEMP%\%CONDA_INSTALLER%" (
    echo ❌ Failed to download Miniconda
    echo Please download manually from: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

echo ✅ Miniconda downloaded
echo.

echo ═══════════════════════════════════════════════════════════════════
echo STEP 2/10: Installing Miniconda
echo ═══════════════════════════════════════════════════════════════════
echo Installing to: %USERPROFILE%\Miniconda3
echo.

start /wait "" "%TEMP%\%CONDA_INSTALLER%" /InstallationType=JustMe /RegisterPython=0 /S /D=%USERPROFILE%\Miniconda3

if not exist "%USERPROFILE%\Miniconda3\Scripts\conda.exe" (
    echo ❌ Miniconda installation failed
    pause
    exit /b 1
)

echo ✅ Miniconda installed
echo.

REM Initialize conda for this session
call "%USERPROFILE%\Miniconda3\Scripts\activate.bat"

:skip_conda_install

echo ═══════════════════════════════════════════════════════════════════
echo STEP 3/10: Creating Aegis Environment (Python 3.12)
echo ═══════════════════════════════════════════════════════════════════

REM Check if environment already exists
call conda env list | findstr "aegis" >nul 2>&1
if %errorlevel% equ 0 (
    echo ⚠️  Aegis environment already exists, removing it...
    call conda env remove -n aegis -y
)

call conda create -n aegis python=3.12 -y

if %errorlevel% neq 0 (
    echo ❌ Failed to create conda environment
    pause
    exit /b 1
)

echo ✅ Aegis environment created
echo.

echo ═══════════════════════════════════════════════════════════════════
echo STEP 4/10: Activating Aegis Environment
echo ═══════════════════════════════════════════════════════════════════

call conda activate aegis

if %errorlevel% neq 0 (
    echo ❌ Failed to activate aegis environment
    pause
    exit /b 1
)

echo ✅ Aegis environment activated
echo.

echo ═══════════════════════════════════════════════════════════════════
echo STEP 5/10: Checking GPU Status
echo ═══════════════════════════════════════════════════════════════════

nvidia-smi
echo ✅ GPU detected
timeout /t 3 /nobreak >nul
echo.

echo ═══════════════════════════════════════════════════════════════════
echo STEP 6/10: Installing PyTorch with CUDA 12.4
echo ═══════════════════════════════════════════════════════════════════
echo This will download ~2.5GB (5-10 minutes)...
echo.

pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

if %errorlevel% neq 0 (
    echo ⚠️  CUDA 12.4 failed, trying CUDA 12.1...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
)

echo ✅ PyTorch with CUDA installed
echo.

echo ═══════════════════════════════════════════════════════════════════
echo STEP 7/10: Installing Aegis Requirements
echo ═══════════════════════════════════════════════════════════════════

pip install numpy pandas scikit-learn xgboost lightgbm gymnasium tqdm psutil flask flask-cors requests MetaTrader5 matplotlib seaborn

echo ✅ All requirements installed
echo.

echo ═══════════════════════════════════════════════════════════════════
echo STEP 8/10: Verifying GPU Installation
echo ═══════════════════════════════════════════════════════════════════

python check_gpu.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ GPU verification failed!
    echo PyTorch cannot detect your GPU.
    echo.
    echo Troubleshooting:
    echo 1. Restart your computer
    echo 2. Run this script again
    echo 3. Check NVIDIA drivers are up to date
    echo.
    pause
    exit /b 1
)

echo.
echo ✅ GPU verification successful!
echo.
timeout /t 3 /nobreak >nul

echo ═══════════════════════════════════════════════════════════════════
echo STEP 9/10: Running GPU Benchmark
echo ═══════════════════════════════════════════════════════════════════

python gpu_benchmark.py

echo.
timeout /t 5 /nobreak >nul

echo ═══════════════════════════════════════════════════════════════════
echo STEP 10/10: Starting GPU Training!
echo ═══════════════════════════════════════════════════════════════════
echo.
echo Training all models on GPU:
echo   • GPT Brain Model (100 epochs) - ~10-15 minutes
echo   • Reinforcement Learning Agent (50 epochs) - ~3-5 minutes
echo   • Adaptive Learning Model - ~2 minutes
echo.
echo Total estimated time: 15-22 minutes (was 4+ hours on CPU!)
echo.
echo Monitor GPU usage in another terminal: nvidia-smi -l 1
echo.
timeout /t 5 /nobreak >nul

python TRAIN_ALL_MODELS.py

if %errorlevel% equ 0 (
    echo.
    echo ╔════════════════════════════════════════════════════════════════╗
    echo ║   ✅ TRAINING COMPLETE!                                        ║
    echo ╚════════════════════════════════════════════════════════════════╝
    echo.
    echo All models trained successfully on GPU!
    echo Models saved in: d:\Trading\Aegis_Gold\models\
    echo.
    echo Next steps:
    echo 1. Start bot: conda activate aegis ^& python start_aegis.py
    echo 2. View results: Check models\ folder
    echo 3. Monitor GPU: nvidia-smi -l 1
    echo.
) else (
    echo.
    echo ❌ Training encountered an error
    echo Check the output above for details
    echo.
)

echo.
echo ═══════════════════════════════════════════════════════════════════
echo QUICK REFERENCE
echo ═══════════════════════════════════════════════════════════════════
echo.
echo Always activate environment first:
echo   conda activate aegis
echo.
echo Then run commands:
echo   python start_aegis.py          (Start trading bot)
echo   python TRAIN_ALL_MODELS.py     (Train models)
echo   python check_gpu.py            (Check GPU status)
echo   nvidia-smi                     (Monitor GPU)
echo.
pause
