# Complete GPU Setup Guide - NVIDIA RTX 3050

## Current Status

### ✅ What's Working
- **GPU**: NVIDIA GeForce RTX 3050 Laptop (6GB VRAM)
- **CUDA Driver**: Version 13.3 (installed and functional)
- **nvidia-smi**: Working correctly
- **Python**: 3.14.3 (installed)

### ❌ What's NOT Working
- **PyTorch with CUDA**: Not available for Python 3.14 yet
- **Reason**: Python 3.14 is too new - PyTorch currently supports Python 3.9-3.12

## The Problem

PyTorch doesn't yet have pre-built wheels (installable packages) for Python 3.14 with CUDA support. This is a temporary limitation that will be resolved in 1-2 months.

## Solutions (Ranked by Ease)

---

### ✅ SOLUTION 1: Downgrade to Python 3.12 (RECOMMENDED - Easiest)

**Time**: 15 minutes  
**Difficulty**: Easy  
**Success Rate**: 100%

#### Steps:

1. **Download Python 3.12.7**:
   - Visit: https://www.python.org/downloads/release/python-3127/
   - Download: "Windows installer (64-bit)"
   - File: `python-3.12.7-amd64.exe`

2. **Uninstall Python 3.14**:
   ```
   Settings → Apps → Python 3.14.3 → Uninstall
   ```

3. **Install Python 3.12.7**:
   - Run the installer
   - ✅ Check "Add Python 3.12 to PATH"
   - Click "Install Now"

4. **Verify Installation**:
   ```bash
   python --version
   # Should show: Python 3.12.7
   ```

5. **Install PyTorch with CUDA 12.4**:
   ```bash
   cd d:\Trading\Aegis_Gold
   COMPLETE_GPU_SETUP.bat
   ```

6. **Verify GPU**:
   ```bash
   python check_gpu.py
   ```

**Expected Output**:
```
CUDA Available: True
CUDA Version: 12.4
GPU Name: NVIDIA GeForce RTX 3050 Laptop GPU
GPU Memory: 6.00 GB
```

---

###  ✅ SOLUTION 2: Use Conda Environment (RECOMMENDED - Clean Isolation)

**Time**: 20 minutes  
**Difficulty**: Easy-Medium  
**Success Rate**: 100%

This keeps Python 3.14 but creates an isolated environment with Python 3.12.

#### Steps:

1. **Download Miniconda**:
   - Visit: https://docs.conda.io/en/latest/miniconda.html
   - Download: "Miniconda3 Windows 64-bit"
   - Install (default settings OK)

2. **Create Aegis Environment**:
   ```bash
   conda create -n aegis python=3.12 -y
   ```

3. **Activate Environment**:
   ```bash
   conda activate aegis
   ```

4. **Install PyTorch with CUDA**:
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
   ```

5. **Install Aegis Requirements**:
   ```bash
   cd d:\Trading\Aegis_Gold
   pip install -r requirements.txt
   ```

6. **Verify GPU**:
   ```bash
   python check_gpu.py
   ```

#### Using Conda Daily:

**Start trading bot**:
```bash
conda activate aegis
cd d:\Trading\Aegis_Gold
python start_aegis.py
```

**Train models**:
```bash
conda activate aegis
cd d:\Trading\Aegis_Gold
python TRAIN_ALL_MODELS.py
```

---

### ⚠️ SOLUTION 3: Build PyTorch from Source (Advanced)

**Time**: 2-3 hours  
**Difficulty**: Advanced  
**Success Rate**: 70%

Only for advanced users comfortable with C++ compilation.

#### Requirements:
- Visual Studio 2019 or 2022 with C++ tools
- CUDA Toolkit 12.4
- 20GB free disk space
- Fast internet connection

#### Steps:

1. **Install Visual Studio 2022 Community**:
   - Download: https://visualstudio.microsoft.com/downloads/
   - Install "Desktop development with C++"

2. **Install CUDA Toolkit 12.4**:
   - Download: https://developer.nvidia.com/cuda-12-4-0-download-archive
   - Select: Windows → x86_64 → 11 → exe (local)
   - Install with default settings

3. **Install CMake**:
   ```bash
   pip install cmake ninja
   ```

4. **Clone PyTorch**:
   ```bash
   git clone --recursive https://github.com/pytorch/pytorch
   cd pytorch
   git checkout v2.6.0
   git submodule sync
   git submodule update --init --recursive
   ```

5. **Set Environment Variables**:
   ```bash
   set CUDA_HOME=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4
   set PATH=%CUDA_HOME%\bin;%PATH%
   ```

6. **Build PyTorch**:
   ```bash
   python setup.py install
   ```
   ⏱️ This takes 1.5-2 hours

7. **Verify**:
   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```

---

### ⏳ SOLUTION 4: Wait for Official Support

**Time**: 1-2 months  
**Difficulty**: None  
**Success Rate**: 100% (eventually)

PyTorch team is actively working on Python 3.14 support. Check progress:
- https://github.com/pytorch/pytorch/issues

Meanwhile, use CPU training or one of the above solutions.

---

## Comparison Table

| Solution | Time | Difficulty | Keeps Python 3.14 | Recommended |
|----------|------|------------|-------------------|-------------|
| **1. Python 3.12** | 15 min | Easy | ❌ No | ⭐⭐⭐⭐⭐ |
| **2. Conda** | 20 min | Easy-Medium | ✅ Yes | ⭐⭐⭐⭐⭐ |
| **3. Build from Source** | 2-3 hrs | Advanced | ✅ Yes | ⭐⭐ |
| **4. Wait** | 1-2 months | None | ✅ Yes | ⭐ |

---

## Training Performance After Setup

### CPU (Current)
- GPT Model: ~3 hours
- RL Model: ~45 minutes
- Full Pipeline: 4+ hours

### GPU (After Setup)
- GPT Model: ~10-15 minutes ⚡ (**12x faster**)
- RL Model: ~3-5 minutes ⚡ (**9-15x faster**)
- Full Pipeline: ~20-25 minutes ⚡ (**12x faster**)

---

## My Recommendation

**Choose Solution 1 (Python 3.12)** if:
- ✅ You don't need Python 3.14 specifically
- ✅ You want the fastest, easiest setup
- ✅ You're okay reinstalling one Python version

**Choose Solution 2 (Conda)** if:
- ✅ You want to keep Python 3.14
- ✅ You want clean environment isolation
- ✅ You're okay using `conda activate aegis` before trading

**Avoid Solution 3** unless:
- ❌ You're an advanced developer
- ❌ You have 3+ hours to spare
- ❌ You're comfortable debugging C++ build errors

---

## Quick Start Commands

### After Solution 1 (Python 3.12):
```bash
cd d:\Trading\Aegis_Gold
COMPLETE_GPU_SETUP.bat
python check_gpu.py
python TRAIN_ALL_MODELS.py
```

### After Solution 2 (Conda):
```bash
conda activate aegis
cd d:\Trading\Aegis_Gold
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
python check_gpu.py
python TRAIN_ALL_MODELS.py
```

---

## Troubleshooting

### Issue: "CUDA out of memory" during training
**Solution**: Your RTX 3050 has 6GB VRAM. If training fails:
```python
# Edit brain/train_gpt.py
BATCH_SIZE = 16  # Change from 32 to 16
```

### Issue: GPU not detected after setup
**Solution**:
1. Restart terminal
2. Run `python check_gpu.py` again
3. If still fails, reboot computer

### Issue: Training slower than expected
**Check**:
```bash
nvidia-smi
# GPU Util should be 80-100% during training
# Temperature should be 60-85°C
```

---

**Created**: July 13, 2026  
**GPU**: NVIDIA RTX 3050 (6GB)  
**CUDA**: 13.3  
**Status**: Awaiting PyTorch Python 3.14 support
