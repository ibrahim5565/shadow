# BROKER CONFIGURATION - READY FOR ACTIVATION

## 📋 **CURRENT STATUS:**
✅ **DEMO MODE**: Active (0.10 lot trading)  
✅ **BROKER SETTINGS**: Prepared but NOT activated  
✅ **LIVE ACCOUNT**: Ready for activation when you say  

## 🎯 **YOUR BROKER SPECS (PRECONFIGURED):**
- **Lot Size**: 0.01 lot (1 micro lot)
- **EURUSD Spread**: 0.09 pips for 0.001 lot
- **EURUSD Pip Value**: $0.10 per pip (for 0.01 lot)
- **XAUUSD Point Value**: $0.01 per point (for 0.01 lot)

## 📂 **WHAT I'VE PREPARED:**

### 1. **settings.py** - Broker-ready configuration:
```python
"EURUSD": {
    # ... existing demo settings ...
    # === BROKER-READY CONFIGURATION (ACTIVATE LATER) ===
    "broker_pip_value_0_01_lot": 0.10,     # YOUR BROKER: $0.10 per pip for 0.01 lot
    "broker_base_lot_live": 0.01,          # YOUR BROKER LOT: 0.01 lot
    "broker_spread_cost_per_trade": 0.09,  # YOUR BROKER: 0.09 pips for 0.001 lot
    "broker_min_tp_points": 6,             # MIN TP: 6 pips = $0.60
    # ====================================================
}
```

### 2. **brain.py** - Ready for hard SL:
```python
# Current (demo):
lot = 0.01  # Current: 0.01 lot for demo
sl_points = 0  # No hard stop loss for demo

# After activation (broker):
lot = 0.01  # ✅ BROKER: Always use 0.01 lot
sl_points = int(sl_estimate)  # ✅ BROKER: Use hard SL for protection
```

### 3. **ACTIVATE_BROKER_ACCOUNT.py** - One-click activation script:
```bash
python ACTIVATE_BROKER_ACCOUNT.py
```

## 🔧 **WHAT CHANGES WHEN YOU ACTIVATE:**

| **Setting** | **DEMO Mode** | **BROKER Mode** |
|------------|---------------|-----------------|
| **Lot Size** | 0.10 lot | **0.01 lot** |
| **Pip Value** | Standard | **$0.10/pip** |
| **Min TP** | 5 pips | **6 pips** |
| **Hard SL** | Disabled | **Enabled** |
| **Spread Limits** | Normal | **Very Tight** |
| **Risk per Trade** | 0.5% | **0.3%** |

## 🚀 **HOW TO ACTIVATE (WHEN READY):**

### **Step 1: Verify broker credentials**
Check `.env` file:
```env
MT5_LOGIN=your_live_login
MT5_PASSWORD=your_live_password
MT5_SERVER=your_live_server
```

### **Step 2: Run activation script**
```bash
cd d:\Trading\Aegis_Gold
python ACTIVATE_BROKER_ACCOUNT.py
```

### **Step 3: Enable LIVE trading**
Edit `config/settings.py`:
```python
DEMO_MODE = False  # Change from True to False
```

### **Step 4: Restart bot**
Restart the trading bot for changes to take effect.

## 📊 **EXPECTED PERFORMANCE (BROKER MODE):**

**With 0.01 lot:**
- **Per Pip**: $0.10
- **Target per Trade**: $0.50 (5 pips)
- **Spread Cost**: $0.09 (0.9 pips)
- **Net Profit per Win**: $0.41
- **Max Loss per Trade**: $0.80 (8 pips SL)

**Daily (conservative):**
- 2-3 high-quality trades
- $0.80 - $1.20 net profit
- Max daily loss: ~$1.60

## ⚠️ **IMPORTANT NOTES:**

1. **DO NOT activate yet** - Wait until you're ready for live trading
2. **Test thoroughly** in demo mode first
3. **Start small** - 0.01 lot is perfect for testing
4. **Monitor spreads** - Your broker's 0.09 pips is very competitive
5. **Hard SL protection** - Will be enabled on activation

## 📞 **WHEN YOU'RE READY:**

Simply say: **"Activate broker account now"**  
I'll guide you through the final steps or run the activation script for you.

---

**STATUS**: ✅ BROKER CONFIGURATION READY (NOT ACTIVATED)  
**LOT SIZE**: 0.10 lot (DEMO) → 0.01 lot (BROKER)  
**LAST UPDATED**: June 17, 2026
