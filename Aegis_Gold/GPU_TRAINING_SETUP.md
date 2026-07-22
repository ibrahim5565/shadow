# GPU Training Setup Guide - NVIDIA RTX 3050

## System Status
- ✅ GPU: NVIDIA GeForce RTX 3050 Laptop (6GB VRAM)
- ✅ CUDA Driver: Version 13.3 (installed and working)
- ✅ nvidia-smi: Working correctly
- ❌ PyTorch: CPU-only version (needs GPU version)

## What We're Installing

### PyTorch with CUDA 12.4
- **Official PyTorch**: 2.6+ with CUDA 12.4 support
- **Compatible with**: Your CUDA 13.3 driver (forward compatible)
- **Download Size**: ~2.5GB
- **Speed Improvement**: 10-20x faster training than CPU

### Installation Command
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

## Installation Steps

### Option 1: Automatic (Recommended)
```batch
INSTALL_GPU_REQUIREMENTS.bat
```

### Option 2: Manual
1. Uninstall CPU PyTorch:
   ```bash
   pip uninstall -y torch torchvision torchaudio
   ```

2. Install GPU PyTorch:
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
   ```

3. Verify installation:
   ```bash
   python check_gpu.py
   ```

## Expected Results After Installation

### Successful Installation
```
CUDA GPU STATUS CHECK
============================================================
PyTorch Version: 2.6.0+cu124
CUDA Available: True
CUDA Version (PyTorch): 12.4
cuDNN Version: 90100
GPU Count: 1
GPU Name: NVIDIA GeForce RTX 3050 Laptop GPU
GPU Memory: 6.00 GB
```

## Training Performance

### CPU Training (Current)
- GPT Model (100 epochs): ~3 hours
- RL Model (50 epochs): ~45 minutes
- Memory Usage: ~2GB RAM

### GPU Training (After Setup)
- GPT Model (100 epochs): ~10-15 minutes ⚡
- RL Model (50 epochs): ~3-5 minutes ⚡
- Memory Usage: ~3GB VRAM

## Important Notes

### VRAM Management (6GB GPU)
Your RTX 3050 has 6GB VRAM. Our training scripts are optimized for this:
- **Batch size**: 32 (fits in 6GB)
- **Model size**: Optimized (won't exceed VRAM)
- **Automatic fallback**: If VRAM full, falls back to CPU

### Training Commands

#### Train All Models (GPU)
```bash
python TRAIN_ALL_MODELS.py
```

#### Train GPT Only (GPU)
```bash
python brain/train_gpt.py
```

#### Train RL Only (GPU)
```bash
python brain/train_reinforcement.py
```

### Monitor GPU Usage During Training
```bash
nvidia-smi -l 1
```
This shows GPU utilization, memory usage, and temperature in real-time.

## Troubleshooting

### Issue: "CUDA out of memory"
**Solution**: Reduce batch size in training script:
```python
BATCH_SIZE = 16  # Change from 32 to 16
```

### Issue: GPU not detected after installation
**Solution**: 
1. Restart Python/Terminal
2. Run `python check_gpu.py` again
3. If still fails, reboot computer

### Issue: Training slower than expected
**Check**:
1. GPU utilization: `nvidia-smi` should show 80-100% usage
2. Temperature: Should be 60-85°C (normal for training)
3. Power mode: Laptop should be plugged in (not battery)

## CUDA Compatibility

Your CUDA 13.3 driver supports these PyTorch CUDA versions:
- ✅ CUDA 12.4 (recommended - latest PyTorch)
- ✅ CUDA 12.1
- ✅ CUDA 11.8

**Recommendation**: CUDA 12.4 (best performance, latest features)

## Post-Installation

After successful installation:
1. ✅ Verify GPU detection: `python check_gpu.py`
2. ✅ Run training: `python TRAIN_ALL_MODELS.py`
3. ✅ Monitor progress: Watch console for epoch updates
4. ✅ Check GPU load: `nvidia-smi` in another terminal

## Training Time Comparison

| Model | CPU (Current) | GPU (After Setup) | Speedup |
|-------|---------------|-------------------|---------|
| GPT Brain (100 epochs) | 3 hours | 10-15 min | 12-18x |
| RL Agent (50 epochs) | 45 min | 3-5 min | 9-15x |
| Adaptive Learning | 20 min | 2 min | 10x |
| Full Pipeline | 4+ hours | 20-25 min | 12x |

## Safety Notes

### Temperature
- Normal: 60-85°C during training
- Warning: 85-95°C (reduce batch size)
- Critical: >95°C (stop training, clean fans)

### Power
- Always use AC power when training
- Battery mode will throttle GPU (much slower)

### Laptop Cooling
- Use on hard, flat surface (good airflow)
- Consider laptop cooling pad for long training sessions
- Monitor with: `nvidia-smi dmon -s pucvmet -c 60`

---
**Installation Date**: July 13, 2026
**GPU Model**: NVIDIA RTX 3050 Laptop (6GB)
**CUDA Driver**: 13.3
**Target PyTorch**: 2.6+ with CUDA 12.4
