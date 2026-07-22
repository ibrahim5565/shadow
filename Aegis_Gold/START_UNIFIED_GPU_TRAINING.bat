@echo off
title AEGIS INSTITUTIONAL QUANT AI — GPU NEURAL TRAINING
color 0A

echo =======================================================================
echo 🚀 AEGIS INSTITUTIONAL QUANT AI — RTX 3050 GPU TRAINING
echo =======================================================================
echo Target: Profit Factor >= 2.0 (100% PF)
echo Elimination of $0.00 / -$0.01 trade closes
echo Hardware: NVIDIA RTX 3050 GPU (PyTorch CUDA Acceleration)
echo =======================================================================
echo.

if exist .venv_cuda\Scripts\python.exe (
    .venv_cuda\Scripts\python.exe train_unified_gpu_brain.py --epochs 100
) else (
    python train_unified_gpu_brain.py --epochs 100
)

echo.
echo =======================================================================
echo ✅ TRAINING PROCESS COMPLETED
echo =======================================================================
pause
