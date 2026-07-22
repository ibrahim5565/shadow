@echo off
echo ========================================
echo INSTALLING PyTorch with CUDA Support
echo For NVIDIA RTX 3050 GPU
echo ========================================
echo.
echo This will install PyTorch with CUDA 11.8 support
echo Training will be 10-20x faster on GPU!
echo.
pause

echo.
echo [1/2] Uninstalling CPU-only PyTorch...
pip uninstall torch torchvision torchaudio -y

echo.
echo [2/2] Installing PyTorch with CUDA 11.8...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

echo.
echo ========================================
echo Installation Complete!
echo ========================================
echo.
echo Testing CUDA availability...
python -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'Not detected')"

echo.
echo If CUDA shows as Available, you're ready for GPU training!
echo.
pause
