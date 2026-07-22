# 🎯 FIRST 200 TRADES MODE — MAXIMUM PROFIT PURSUIT

**Active Period**: Until completing first 200 high-quality trades  
**Focus**: BIGGER PROFITS per trade — Don't close at $0.00-$3.00 anymore!

---

## 🚀 WHAT CHANGED

### 1. **MINIMUM PROFIT TARGETS INCREASED**
- **Gold (XAUUSD)**: $10 minimum (was $0.30)
- **EURUSD**: $5 minimum (was $0.30)
- **Max Loss**: $10 per trade (was $2.50)

### 2. **BIGGER POSITION SIZES**
- **Gold Max Lot**: 1.00 (was 0.50)
- **EURUSD Max Lot**: 0.30 (was 0.20)
- **Max Open Positions**: 5 total, 3 per symbol

### 3. **AGGRESSIVE TRADING FREQUENCY**
- **Daily Trade Limit**: 200 trades (was 100)
- **Minimum Daily Target**: 10+ trades per day
- **Gap Between Trades**: 0 minutes (trade continuously)
- **Loss Cooldown**: 10 seconds (was 60s)
- **Direction Switch**: 10 seconds (was 60s)

### 4. **HOLD FOR BIGGER PROFITS**
**Dynamic TP Engine v3 - FIRST 200 MODE:**
- Gold: 80pt buffer (was 40pt), 100pt extensions (was 50pt)
- EURUSD: 15pt buffer (was 8pt), 20pt extensions (was 10pt)
- Lock-in at 40% pullback (was 30%) - let profits run longer
- Minimum 30 seconds hold time before allowing exits

### 5. **EXIT LOGIC CHANGES**
**Disabled Premature Exits:**
- ❌ NO MORE $0.10 profit exits on RSI pullbacks
- ❌ NO MORE $0.30-$3.00 tiny profit closes
- ✅ Only exit if profit >= $5 (EURUSD) or $10 (Gold)
- ✅ Only exit RSI exhaustion if RSI > 75/< 25 (extreme)
- ✅ Hold through minor pullbacks for bigger moves

---

## 📊 TARGET PERFORMANCE

**Goal**: Complete 200 high-quality trades with bigger average profit per trade

**Previous Mode Issues:**
- Trades closing at $0.00, $0.01, $1.00, $2.00, $3.00
- Average profit: ~$2-3 per trade
- Too many tiny wins, not enough big moves captured

**FIRST 200 TRADES MODE:**
- Minimum profit: $5 (EURUSD), $10 (Gold)
- Target average: $8-15 per trade
- Fewer trades, bigger profits per trade
- Hold through pullbacks to capture full momentum

---

## 🛡️ RISK MANAGEMENT (STILL ACTIVE)

**These protections still work:**
- Dynamic TP pursuing price (with wider buffers)
- Spread spike exits (spread > 1.8x limit)
- Trend reversal exits (strong opposing trend)
- Volatility spike exits (extreme ATR ratios)
- Emergency drawdown protection (5%+ DD)
- Breakeven & trailing stops

**What's relaxed:**
- RSI exhaustion exits (only at extreme levels 75/25)
- Momentum weakness exits (only if score < 10 AND loss > $5)
- Minimum profit requirements (raised from $0.30 to $5/$10)

---

## 📈 HOW IT WORKS

### Entry Logic (Unchanged)
- Same confidence thresholds (40% Gold, 50% EURUSD)
- Same OMEGA supervisor vetting
- Same trend/structure/entry checks

### Exit Logic (Modified)
1. **Dynamic TP**: Pursues price with 80pt (Gold) / 15pt (EURUSD) buffer
2. **Lock-in**: Only triggers at 40% pullback from peak (was 30%)
3. **RSI Exits**: Only at extreme levels (RSI 75/25) AND profit >= $5/$10
4. **Trend Reversals**: Still active for capital protection
5. **Emergency Exits**: Only if profit >= $5/$10 secured

### Position Monitoring (Enhanced)
- Updates every 0.3s when positions open (was 1s)
- Continuously pursues bigger profits
- Won't close prematurely on tiny profits

---

## 🎯 EXPECTED RESULTS

**Before FIRST 200 MODE:**
```
Trade #1: +$0.00
Trade #2: +$1.00
Trade #3: +$2.00
Trade #4: +$3.00
Trade #5: +$5.00
Average: $2.20/trade
```

**After FIRST 200 MODE:**
```
Trade #1: +$8.00
Trade #2: +$12.00
Trade #3: +$6.00
Trade #4: +$15.00
Trade #5: +$9.00
Average: $10.00/trade
```

**Impact:**
- 4-5x higher profit per trade
- Fewer but better-quality trades
- Capture full momentum moves
- Better risk:reward execution

---

## ⚙️ CONFIGURATION CHANGES

**File: `config/settings.py`**
```python
FIRST_200_TRADES_MODE = True
FIRST_200_MIN_PROFIT_USD = 5.00
FIRST_200_MIN_HOLD_SEC = 30
FIRST_200_MAX_LOSS_USD = 10.00

MAX_DAILY_TRADES = 200
MAX_OPEN_TRADES = 5
MAX_OPEN_TRADES_PER_SYMBOL = 3
MIN_TRADES_PER_DAY = 10

COOLDOWN_AFTER_LOSS_SEC = 10
MIN_GAP_BETWEEN_TRADES_MIN = 0
NO_DUPLICATE_DIRECTION_SEC = 10
```

**File: `brain/position_supervisor.py`**
- RSI exit threshold: 75/25 (was 70/30)
- Minimum profit for RSI exit: $5/$10 (was $0.10)
- Momentum exit threshold: score < 10 AND loss > $5 (was score < 15 AND loss > $1.50)

**File: `modules/risk_manager.py`**
- Gold buffer: 80pts (was 40pts)
- Gold extensions: 100pts (was 50pts)
- Lock-in pullback: 40% (was 30%)
- EURUSD buffer: 15pts (was 8pts)

---

## 🚦 MONITORING

**Dashboard Metrics to Watch:**
- Average profit per trade (target: $8-15)
- Trade count progress toward 200
- Win rate (maintain 60%+)
- Max drawdown per trade (< $10)
- Total daily profit

**Telegram Notifications:**
- Every trade entry/exit with P&L
- Dynamic TP adjustments
- RSI exhaustion exits (rare now)
- Emergency exits

---

## ✅ RESTART REQUIRED

**After these changes, restart the bot:**
```bash
python core/main.py
```

System will load FIRST 200 TRADES MODE configuration and start pursuing bigger profits.

---

**Last Updated**: 2026-06-17  
**Mode**: FIRST 200 TRADES — MAXIMUM PROFIT PURSUIT  
**Status**: ACTIVE ✅
