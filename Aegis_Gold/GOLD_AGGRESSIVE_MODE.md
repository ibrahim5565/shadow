# GOLD AGGRESSIVE MODE - Bigger Entry Configuration

## Date: June 18, 2026

## Configuration Changes Applied

### 🥇 **GOLD (XAUUSD) IS NOW PRIMARY FOCUS**

Changed symbol priority order:
- **BEFORE**: `["EURUSD", "XAUUSD"]` - EURUSD checked first
- **AFTER**: `["XAUUSD", "EURUSD"]` - **GOLD checked first every scan**

---

## 🚀 GOLD-SPECIFIC AGGRESSIVE SETTINGS

### 1. **Confidence Threshold - REDUCED**
- **GOLD**: 40% confidence to trade (reduced from 50%)
- **EURUSD**: Still 50% (unchanged)
- **Result**: Gold trades 10% more often with slightly lower confidence

### 2. **Spread Limits - RELAXED**
```python
"spread_limits": {
    "ASIAN": 35,    # was 25 (+10 pts tolerance)
    "LONDON": 30,   # was 20 (+10 pts tolerance)
    "NY": 35,       # was 25 (+10 pts tolerance)
    "OVERLAP": 40   # was 30 (+10 pts tolerance)
}
```
**Impact**: Gold can now trade with wider spreads during all sessions

### 3. **Lot Size - INCREASED**
- **Max Lot**: 0.20 → **0.50** (2.5× bigger positions)
- **Target Profit**: $0.50 → **$2.0** (4× bigger targets)
- **Result**: Bigger entries with bigger profit potential

### 4. **Take Profit Range - EXPANDED**
- **Max TP**: 300pts → **500pts** 
- **Result**: Can capture larger Gold swings (up to $50 per 0.10 lot)

### 5. **Stop Loss Range - EXPANDED**
- **Max SL**: 40pts → **80pts**
- **ATR Multiplier**: 0.8× → **1.2×** (wider stops for Gold volatility)
- **Result**: More room for Gold volatility, fewer stop-outs

### 6. **Volatility Tolerance - INCREASED**
- **Max Volatility Ratio**: 3.0 → **5.0**
- **Result**: Can trade Gold during high-volatility news events

### 7. **Time Management - OPTIMIZED FOR GOLD**
- **Scan Interval**: 30s → **15s** (2× faster Gold monitoring)
- **Time Stop**: 120s → **180s** (3 min - more time for Gold to run)
- **Breakeven Trigger**: 5pts → **10pts** (protect profits faster on Gold)
- **Trail Start**: 8pts → **15pts** (let Gold run further before trailing)
- **Trail Distance**: 4pts → **10pts** (wider trailing for Gold swings)

---

## 📈 TRADING RULES - MORE AGGRESSIVE

### Trade Limits - INCREASED
```python
MAX_TRADES_PER_DAY = 5              # was 3 (+2 more Gold opportunities)
MAX_OPEN_TRADES = 3                 # was 2 (can pyramid Gold)
MAX_OPEN_TRADES_PER_SYMBOL = 2      # was 1 (can scale into Gold)
MAX_CONSECUTIVE_LOSSES = 3          # was 2 (more tolerance)
```

### Cooldowns - REDUCED (Faster Recovery)
```python
MIN_GAP_BETWEEN_TRADES_MIN = 2      # was 5 (trade Gold faster)
COOLDOWN_AFTER_LOSS_SEC = 60        # was 300 (1 min vs 5 min)
COOLDOWN_AFTER_CONSEC_LOSSES = 300  # was 1800 (5 min vs 30 min)
NO_DUPLICATE_DIRECTION_SEC = 60     # was 300 (re-enter Gold trends faster)
MAX_TRADES_PER_MINUTE = 2           # was 1 (capture Gold momentum)
```

### Risk Management - MORE AGGRESSIVE
```python
BASE_RISK_PCT = 0.5%                # was 0.3% (+67% risk per trade)
MAX_RISK_PCT = 1.0%                 # was 0.5% (2× max risk)
RR_RATIO = 3.0                      # was 2.5 (bigger profit targets)
NEWS_BLACKOUT = 15 min              # was 45 min (trade Gold news)
```

---

## 🎯 EXPECTED TRADING BEHAVIOR

### GOLD (XAUUSD) Will Now:
1. ✅ **Trade at 40%+ confidence** (was 50%)
2. ✅ **Accept spreads up to 30-40pts** (was 20-30pts)
3. ✅ **Use bigger lot sizes** (up to 0.50 lot vs 0.20)
4. ✅ **Target bigger profits** ($2.0+ per trade vs $0.50)
5. ✅ **Allow 2 positions simultaneously** (scaling strategy)
6. ✅ **Scan every 15 seconds** (2× faster than before)
7. ✅ **Trade during news events** (15min blackout only)
8. ✅ **Wider stops** (up to 80pts for Gold volatility)
9. ✅ **Bigger TPs** (up to 500pts for trend rides)
10. ✅ **Faster recovery** (1min cooldown after loss)

### EURUSD Will:
- Remain at 50% confidence threshold
- Keep conservative settings
- Act as secondary pair

---

## 💰 PROFIT POTENTIAL COMPARISON

### Before (Conservative):
- Lot: 0.10-0.20
- Target: $0.50 per trade
- Max 3 trades/day
- **Daily potential**: ~$1.50

### After (Aggressive Gold):
- Lot: 0.10-0.50
- Target: $2.0+ per trade  
- Max 5 trades/day
- 2 Gold positions possible
- **Daily potential**: ~$10-20+

---

## ⚠️ IMPORTANT NOTES

### Risks Increased:
1. **Bigger Losses Possible**: 0.50 lot × 80pt SL = $40 max loss per trade
2. **More Frequent Trading**: Up to 5 trades per day
3. **Higher Volatility Exposure**: Trading Gold news events
4. **Multiple Positions**: Can have 2 Gold positions = 2× exposure

### Risk Mitigation Still Active:
1. ✅ **Max 1% risk per trade** (hard limit)
2. ✅ **Stop after 3 consecutive losses**
3. ✅ **No daily loss limit** (can trade unlimited)
4. ✅ **Breakeven protection** at 10pts profit
5. ✅ **Trailing stops** at 15pts profit

---

## 🔄 RESTART REQUIRED

These changes require a system restart to take effect:

```powershell
cd d:\Trading\Aegis_Gold

# Stop system
taskkill /F /IM python.exe /T

# Wait
timeout /t 3

# Restart
python watchdog.py
```

---

## 📊 MONITORING

### Check Gold Is Trading:
```powershell
# Monitor live logs
Get-Content d:\Trading\Aegis_Gold\logs\aegis.log -Tail 30 -Wait | Select-String "XAUUSD|TRADE"
```

### Verify Settings Loaded:
```powershell
cd d:\Trading\Aegis_Gold
python -c "from config import settings; print(f'Gold First: {settings.ACTIVE_SYMBOLS[0]}'); print(f'Max Lot: {settings.SYMBOLS_CONFIG[\"XAUUSD\"][\"max_lot\"]}')"
```

Should output:
```
Gold First: XAUUSD
Max Lot: 0.5
```

---

## 🎯 SUCCESS METRICS

After restart, you should see:
1. ✅ XAUUSD scanned before EURUSD in logs
2. ✅ Gold trades executing at 40%+ confidence
3. ✅ Bigger lot sizes (0.10-0.50 lot)
4. ✅ Wider spreads accepted (up to 30-40pts)
5. ✅ Multiple Gold positions possible
6. ✅ Faster scan interval (15s vs 30s)

The system is now optimized for **aggressive Gold trading with bigger entries**! 🥇🚀
