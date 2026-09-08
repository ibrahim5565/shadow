@echo off
title AEGIS GOLD - INSTALL & SETUP KRONOS MODEL
color 0A
echo ===========================================================================
echo   AEGIS GOLD - KRONOS FOUNDATION MODEL INSTALLER & GPU SETUP
echo ===========================================================================
echo.

cd /d "%~dp0"

IF EXIST ".venv_cuda\Scripts\python.exe" (
    echo [INFO] Found CUDA virtual environment at .venv_cuda
    .venv_cuda\Scripts\python.exe scripts\download_and_setup_kronos.py
) ELSE (
    echo [INFO] Running with default Python environment...
    python scripts\download_and_setup_kronos.py
)

echo.
echo ===========================================================================
echo Kronos setup process finished. Press any key to exit.
echo ===========================================================================
pause
