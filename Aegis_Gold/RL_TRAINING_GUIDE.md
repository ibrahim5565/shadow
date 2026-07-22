# AEGIS AI REINFORCEMENT LEARNING TRAINING GUIDE

## Overview

This system trains **multiple AI models** on your June 24, 2026 trading data (first 200 trades) to improve decision-making quality and profitability.

---

## 🎯 What Gets Trained

### 1. **Reinforcement Learning (Actor-Critic PPO)**
- **Purpose**: Learn optimal entry/exit timing
- **Architecture**: 
  - Actor Network: 256→256→128 neurons, 3 actions (WAIT/BUY/SELL)
  - Critic Network: 256→256→128 neurons, value estimation
- **Training**: 50 epochs with PPO algorithm
- **Output**: `models/aegis_rl_actor.pt` and `models/aegis_rl_critic.pt`

### 2. **GPT Brain Model (Transformer)**
- **Purpose**: Pattern recognition and sequence prediction
- **Architecture**: 6 layers, 8 attention heads, 256 embedding dimensions
- **Training**: 100 epochs on historical brain_log.csv
- **Output**: `models/aegis_gpt.pt`

### 3. **Adaptive Learning System**
- **Purpose**: Dynamic threshold adjustment based on performance
- **Training**: Updates baseline from June 24 win/loss stats
- **Output**: `data/omega_performance.json`

### 4. **XGBoost Model (Optional)**
- **Purpose**: Gradient boosting for trade quality prediction
- **Training**: Only if 200+ trades available
- **Output**: `models/xgboost_model.json`

---

## 🚀 How to Run Training

### Option 1: Batch Script (Easiest)
```bash
# Double-click this file in Windows
TRAIN_MODELS.bat
```

### Option 2: Python Direct
```bash
cd d:\Trading\Aegis_Gold
python TRAIN_ALL_MODELS.py
```

### Option 3: Individual Models
```bash
# Train only RL
python brain\train_reinforcement.py

# Train only GPT
python brain\train_gpt.py

# Train only XGBoost
python models\retrain.py
```

---

## 📊 Training Data

**Source**: `data/journal.csv` (June 24, 2026 trades)

**Features Used**:
- Entry price (normalized)
- PnL (profit/loss in points)
- Lot size
- ADX (trend strength)
- RSI (momentum)
- Direction (BUY/SELL)
- Symbol (XAUUSD/EURUSD)
- Session (LONDON/NY/OVERLAP/ASIAN)
- Time features (hour sin/cos)
- Spread, volatility, momentum

**Reward Shaping**:
- Profitable trades: `+PnL/10` (positive reward)
- Loss trades: `+PnL/5` (larger negative penalty)
- Breakeven: `-0.1` (small penalty to encourage selectivity)

---

## ⚙️ Training Configuration

### Reinforcement Learning
```python
EPOCHS = 50
GAMMA = 0.99  # Discount factor
LR_ACTOR = 0.0003
LR_CRITIC = 0.001
CLIP_EPSILON = 0.2  # PPO clipping
ENTROPY_COEF = 0.01  # Exploration bonus
```

### GPT Brain
```python
EPOCHS = 100
BATCH_SIZE = 128
SEQ_LEN = 16
LEARNING_RATE = 0.0005
N_LAYERS = 6
N_HEADS = 8
N_EMBD = 256
```

---

## 📈 Expected Training Time

| Hardware | RL Training | GPT Training | Total Time |
|----------|-------------|--------------|------------|
| **CPU Only** | 10-15 min | 30-45 min | ~50-60 min |
| **GPU (CUDA)** | 2-3 min | 8-12 min | ~12-15 min |

---

## 📁 Output Files

After training, you will find:

```
models/
├── aegis_rl_actor.pt        # RL policy network (NEW)
├── aegis_rl_critic.pt       # RL value network (NEW)
├── aegis_gpt.pt             # GPT brain (UPDATED)
└── xgboost_model.json       # XGBoost model (if trained)

data/
├── rl_training_result.txt   # RL training summary (NEW)
├── training_result.txt      # GPT training summary (UPDATED)
└── omega_performance.json   # Adaptive learning baseline (UPDATED)
```

---

## 🔍 How to Verify Training Worked

### 1. Check Training Logs
Look for these messages:
```
✅ Reinforcement Learning training completed successfully
✅ GPT Brain training completed successfully
✅ Adaptive Learning updated: XXW / YYL from June 24
```

### 2. Check Model Files
```bash
dir models\aegis_rl_*.pt    # Should show 2 files
dir models\aegis_gpt.pt     # Should show updated timestamp
```

### 3. Check Training Results
```bash
type data\rl_training_result.txt
type data\training_result.txt
```

### 4. Test in Bot
```bash
python start_aegis.py
```
- Look for: `✅ RL Actor model loaded successfully`
- Dashboard should show improved confidence scores
- Telegram notifications should show better trade quality

---

## 🧠 How RL Enhances Decisions

The trained RL model is automatically integrated into the brain decision system:

1. **State Extraction**: Current market conditions → 15-dimensional state vector
2. **Policy Query**: Actor network → probabilities for WAIT/BUY/SELL
3. **Confidence Boost**: 
   - If RL agrees with decision → **+10% confidence boost**
   - If RL disagrees → **-5% confidence penalty**
   - If RL says WAIT → no change

Example:
```
Brain Decision: BUY at 65% confidence
RL Policy: BUY with 85% confidence
Final Confidence: 65% + (0.85 * 10%) = 73.5%
```

---

## ⚠️ Important Notes

1. **Training Overwrites Models**
   - Old models are replaced
   - Backup `models/` folder before training if needed

2. **GPU Recommended**
   - Install CUDA for 4x faster training
   - CPU training works but takes longer

3. **Data Quality Matters**
   - Training quality depends on June 24 trade quality
   - More profitable trades = better RL rewards
   - 200 trades is minimum for meaningful learning

4. **Continuous Improvement**
   - Re-train weekly with new data for best results
   - Add more trades to journal.csv for better generalization
   - Monitor `omega_performance.json` for adaptation trends

---

## 🔧 Troubleshooting

### "No trades found for June 24, 2026"
**Solution**: Check `data/journal.csv` has trades with that date. Adjust date filter in `train_reinforcement.py` if needed.

### "CUDA out of memory"
**Solution**: Reduce BATCH_SIZE in training scripts or use CPU:
```python
device = torch.device("cpu")
```

### "RL model not found" in logs
**Solution**: Training failed or models not saved. Re-run training and check for errors.

### Models not loading in bot
**Solution**: 
1. Check file paths in config
2. Verify .pt files exist in `models/`
3. Check Python/PyTorch version compatibility

---

## 📚 Next Steps After Training

1. **Restart Bot**
   ```bash
   python start_aegis.py
   ```

2. **Monitor Performance**
   - Check Telegram for RL-enhanced trade notifications
   - Watch dashboard confidence scores
   - Review `logs/aegis.log` for RL inference messages

3. **Compare Results**
   - Track win rate before/after RL training
   - Monitor average PnL per trade
   - Check if confidence scores correlate with winners

4. **Iterate**
   - Collect more trades
   - Re-train weekly
   - Adjust reward shaping if needed

---

## 📞 Support

For issues or questions:
1. Check `logs/aegis.log` for error details
2. Verify all dependencies installed: `pip install torch numpy pandas`
3. Ensure journal.csv has June 24 data
4. Review training output files for diagnostic info

---

## 🎓 Technical Details

### RL Architecture

**Actor Network** (Policy):
```
Input (15 features)
  ↓
Dense(256) + ReLU + Dropout(0.2)
  ↓
Dense(256) + ReLU + Dropout(0.2)
  ↓
Dense(128) + ReLU
  ↓
Dense(3) + Softmax
  ↓
Output (WAIT/BUY/SELL probabilities)
```

**Critic Network** (Value):
```
Input (15 features)
  ↓
Dense(256) + ReLU + Dropout(0.2)
  ↓
Dense(256) + ReLU + Dropout(0.2)
  ↓
Dense(128) + ReLU
  ↓
Dense(1)
  ↓
Output (Expected return)
```

### PPO Algorithm
- Proximal Policy Optimization
- Clipped objective prevents large policy updates
- Entropy bonus encourages exploration
- Advantage estimation for variance reduction

### Training Loop
```
For each epoch:
  1. Collect old policy probabilities
  2. Compute discounted returns
  3. Estimate advantages (returns - values)
  4. Update actor with clipped surrogate loss
  5. Update critic with MSE loss
  6. Save best model based on total reward
```

---

**Last Updated**: June 17, 2026  
**Version**: 4.0  
**Status**: Production Ready ✅
