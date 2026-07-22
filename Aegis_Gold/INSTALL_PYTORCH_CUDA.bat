@echo off
echo ===============================================
echo STEP 3: Installing PyTorch with CUDA 12.4
echo Downloading ~2.5GB - please wait...
echo ===============================================

call "C:\Users\mohamed ibrahim d\Miniconda3\Scripts\activate.bat" aegis

echo Active Python:
python --version
echo.

echo Installing PyTorch CUDA 12.4...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

if %errorlevel% neq 0 (
    echo.
    echo WARNING: CUDA 12.4 failed, trying CUDA 12.1...
    pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
)

echo.
echo ===============================================
echo STEP 4: Installing all Aegis requirements
echo ===============================================
pip install numpy pandas scikit-learn
pip install xgboost lightgbm
pip install gymnasium
pip install tqdm psutil
pip install flask flask-cors requests
pip install MetaTrader5
pip install matplotlib

echo.
echo ===============================================
echo STEP 5: Verifying GPU
echo ===============================================
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA Available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NOT DETECTED')"

echo.
echo ===============================================
echo ALL DONE - Environment Ready!
echo ===============================================
