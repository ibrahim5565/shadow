@echo off
echo ========================================
echo AEGIS AI MODEL TRAINING SUITE
echo Training on June 24, 2026 Data
echo ========================================
echo.
echo This will train:
echo   - Reinforcement Learning (Actor-Critic PPO)
echo   - GPT Brain Model (Transformer)
echo   - Adaptive Learning System
echo   - XGBoost Model
echo.
echo Training may take 30-60 minutes depending on your hardware.
echo.
pause

python TRAIN_ALL_MODELS.py

echo.
echo ========================================
echo Training completed!
echo ========================================
echo.
pause
