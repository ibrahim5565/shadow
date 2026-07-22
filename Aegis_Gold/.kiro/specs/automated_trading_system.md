# AEGIS AUTO TRADING SYSTEM — SPECIFICATION

**Project:** Automated EURUSD & XAUUSD Trading on VPS  
**Status:** IN PROGRESS  
**Last Updated:** 2026-06-11

---

## SYSTEM OVERVIEW

A fully automated 24/7 MT5 trading system running on Windows VPS that:
- Continuously monitors EURUSD and XAUUSD markets
- Automatically executes trades when all strategy conditions are met
- Manages open positions with stops and profit targets
- Sends Telegram notifications for all events
- Auto-recovers from failures without user intervention
- Operates independently from user's laptop/internet

---

## ARCHITECTURE

```
┌─────────────────────────────────────────────────────┐
│                    VPS 24/7                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │         MASTER TRADING LOOP (main.py)        │   │
│  │  • Scan EURUSD every 120s                    │   │
│  │  • Scan XAUUSD every 120s                    │   │
│  │  • Execute trades on signal                  │   │
│  │  • Manage positions                          │   │
│  └──────────────────────────────────────────────┘   │
│                       │                             │
│        ┌──────────────┼──────────────┐              │
│        ▼              ▼              ▼              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
│  │  MT5 Gateway │ │  Brain (AI)   │ │Risk Manager  ││
│  │              │ │               │ │              ││
│  │ • Connect    │ │ • Indicators  │ │ • Daily Max  ││
│  │ • Get ticks  │ │ • Trend       │ │ • Per trade  ││
│  │ • Open/Close │ │ • Confidence  │ │ • Drawdown   ││
│  │ • Manage     │ │ • Quality     │ │ • Spread     ││
│  └──────────────┘ └──────────────┘ └──────────────┘│
│        │                               │             │
│        └───────────────┬───────────────┘             │
│                        ▼                             │
│        ┌───────────────────────────────┐            │
│        │   Telegram Bot                 │            │
│        │ • Send notifications           │            │
│        │ • Receive commands (/start)    │            │
│        │ • Remote control               │            │
│        └───────────────────────────────┘            │
│                                                     │
│        ┌───────────────────────────────┐            │
│        │   Watchdog Daemon              │            │
│        │ • Monitor process health       │            │
│        │ • Auto-restart on crash        │            │
│        │ • Detect hung threads          │            │
│        └───────────────────────────────┘            │
│                                                     │
│        ┌───────────────────────────────┐            │
│        │   Dashboard (Web API)          │            │
│        │ • Real-time status             │            │
│        │ • Trade history                │            │
│        │ • Performance metrics          │            │
│        └───────────────────────────────┘            │
│                                                     │
└─────────────────────────────────────────────────────┘
         ║
         ║ (Telegram API)
         ║
    ┌────▼────┐
    │ Telegram │
    │   Bot    │
    └──────────┘
         ║
    ┌────▼────┐
    │  Your   │
    │ Phone   │
    └────────┘
```

---

## COMPONENTS

### 1. MASTER TRADING LOOP (`core/main.py`)
**Responsibility:** Orchestrate entire trading cycle

**Loop Flow:**
```
Initialize MT5 & Telegram
↓
REPEAT every 120 seconds:
  ├─ Check if connected to MT5
  ├─ Check market hours
  ├─ SCAN EURUSD
  │  ├─ Get ticks (200 candles)
  │  ├─ Calculate indicators
  │  ├─ Evaluate entry signal
  │  ├─ Check risk limits
  │  └─ Execute trade if all pass
  │
  ├─ SCAN XAUUSD
  │  ├─ Get ticks (200 candles)
  │  ├─ Calculate indicators
  │  ├─ Evaluate entry signal
  │  ├─ Check risk limits
  │  └─ Execute trade if all pass
  │
  ├─ MANAGE OPEN POSITIONS
  │  ├─ Check each position
  │  ├─ Move stop to BE if at 50% target
  │  ├─ Check time stops
  │  ├─ Check trailing stops
  │  └─ Close if conditions met
  │
  ├─ SEND HEARTBEAT
  │  └─ Telegram: Equity, trades, status
  │
  └─ END LOOP
```

### 2. MT5 GATEWAY (`modules/mt5_gateway.py`)
**Responsibility:** All MetaTrader 5 communication

**Functions:**
- `initialize()` - Connect to MT5 terminal
- `get_ticks(symbol, count)` - Fetch price data
- `get_candles_m5(symbol, count)` - Fetch 5-min candles
- `open_position(symbol, direction, lot, sl, tp)` - Execute trade
- `close_position(ticket)` - Close trade
- `get_open_positions()` - List active trades
- `get_account_info()` - Fetch balance/equity
- `is_connected()` - Check connection status
- `reconnect()` - Force reconnection

### 3. TRADING BRAIN (`brain/brain.py`)
**Responsibility:** Trading decision logic

**Inputs:**
- Ticks (price data)
- Candles (M5 timeframe)
- Account info
- Risk manager state

**Outputs:**
- `Decision` object with:
  - `action`: "TRADE" or "WAIT"
  - `direction`: "BUY" or "SELL"
  - `confidence`: 0-100 (AI score)
  - `tp_points`: Target profit in points
  - `sl_points`: Stop loss in points
  - `lot`: Position size
  - `reason`: Why trade/no trade

**Logic:**
1. Calculate indicators (EMA, ADX, RSI, ATR, etc.)
2. Check trend (20 EMA > 50 EMA for longs)
3. Check volatility filters
4. Calculate entry score (0-100)
5. Calculate confidence (0-100)
6. Return decision

### 4. RISK MANAGER (`modules/risk_manager.py`)
**Responsibility:** Risk controls

**Checks:**
- Daily loss limit: DISABLED (user request)
- Consecutive loss pause: Max 5 losses → 30min pause
- Per-trade risk: 0.25-0.5% of equity
- Max concurrent positions: 1-2 per symbol
- Spread filter: Max spread threshold
- Time stops: Close after N seconds
- Breakeven management: Move SL at 50% target

### 5. TELEGRAM BOT (`modules/telegram_bot.py`)
**Responsibility:** User notifications & remote control

**Outbound (Bot → User):**
- Signal detected
- Trade opened
- Trade closed (profit/loss/reason)
- Error occurred
- System started/stopped
- Status updates (on-demand)
- Heartbeat (every 30min)

**Inbound (User → Bot):**
- `/start` - Welcome
- `/help` - Command list
- `/status` - Full system status
- `/stop` - Pause trading
- `/resume` - Resume trading
- `/close_all` - Close all positions
- `/profit` - Daily P&L
- `/trades` - Today's trades
- `/health` - VPS health metrics
- `/diagnose` - System diagnostic

### 6. WATCHDOG DAEMON (`persistence/watchdog.py`)
**Responsibility:** Process health & auto-recovery

**Monitors:**
- Main trading loop is running
- No hung threads
- MT5 connection status
- Memory usage
- CPU usage

**Recovery Actions:**
- Auto-restart if main process dies
- Reconnect MT5 if disconnected
- Alert via Telegram on critical issues
- Log all events

### 7. DASHBOARD (`core/main.py` - Flask endpoints)
**Responsibility:** Web API for status monitoring

**Endpoints:**
- `GET /health` - Is bot running?
- `GET /price` - Current price + spread
- `GET /status` - Full system status
- `GET /trades` - Today's trades
- `GET /positions` - Open positions
- `POST /command` - Execute command

---

## TRADE FLOW

### Entry
```
1. Scan market for signal
   ├─ EMA trend check ✓
   ├─ Volatility filter ✓
   ├─ Spread OK ✓
   └─ Risk limits OK ✓
   
2. Calculate entry
   ├─ Direction: BUY/SELL
   ├─ Stop: Risk distance
   ├─ Target: Risk:Reward ratio
   └─ Lot: % of equity
   
3. Execute
   ├─ Send order to MT5
   ├─ Wait for fill
   ├─ Confirm position
   └─ Log to journal
   
4. Notify Telegram
   └─ "TRADE OPENED: EURUSD BUY +5.0 pts target"
```

### Management
```
1. Monitor continuously
   ├─ Price movement
   ├─ Unrealized P&L
   └─ Time in trade
   
2. Breakeven at 50%
   ├─ If profit reaches 50% of target
   └─ Move SL to breakeven (eliminate risk)
   
3. Time stop
   ├─ If trade open > 120 seconds
   └─ Close trade (take loss or profit)
   
4. Trailing stop (if configured)
   ├─ If trade in profit
   └─ Raise SL by fixed distance
```

### Exit
```
1. Conditions checked every tick
   ├─ Take profit hit
   ├─ Stop loss hit
   ├─ Time stop triggered
   └─ Manual close command
   
2. Close execution
   ├─ Send close order to MT5
   ├─ Confirm close
   ├─ Calculate P&L
   └─ Log to journal
   
3. Notify Telegram
   └─ "TRADE CLOSED: +5.2 pts = +$3.40 (TP)"
```

---

## TELEGRAM NOTIFICATIONS

### Signal & Entry
```
🟢 SIGNAL DETECTED
Symbol: EURUSD
Direction: BUY
Confidence: 78/100
Time: 10:35:22 UTC

🧠 TRADE OPENED
Symbol: EURUSD
Direction: BUY
Entry: 1.0875
SL: 1.0870 (-5pts)
TP: 1.0885 (+10pts)
Lot: 0.10
R:R: 2.0:1
```

### Exit
```
✅ TRADE CLOSED (WIN)
Symbol: EURUSD
Result: +5 pts
Profit: +$2.50
Reason: Take Profit
Duration: 45 seconds
Slippage: 0.5 pts

❌ TRADE CLOSED (LOSS)
Symbol: XAUUSD
Result: -3 pts
Loss: -$0.90
Reason: Stop Loss
Duration: 22 seconds
```

### System Events
```
✅ BOT STARTED
Mode: LIVE
Symbol: EURUSD, XAUUSD
Uptime: 0h 0m 0s

🔄 MT5 RECONNECTED
Status: ✅ CONNECTED
Account: 10010503332 (Live)
Balance: $5,000.00

⚠️ VPS CPU SPIKE
Current: 92%
Throttling engine temporarily...

❌ CRITICAL ERROR
Component: MT5 Gateway
Error: Connection lost + reconnect failed
Action: Restarting watchdog...
```

### Heartbeat (every 30 min)
```
💓 HEARTBEAT
Time: 10:30 UTC
Equity: $5,234.50
Daily P&L: +$234.50
Trades: 8 (6W/2L) = 75% WR
Status: ✅ ACTIVE
Spread: 2pts (LONDON)
```

---

## CONFIGURATION

### Required (.env)
```
MT5_LOGIN=10010503332
MT5_PASSWORD=your_password
MT5_SERVER=MetaQuotes-Demo
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### Trading Parameters (config/settings.py)
```
SYMBOLS = ["EURUSD", "XAUUSD"]
SCAN_INTERVAL = 120  # seconds

# Per-Symbol Config
EURUSD:
  - Min TP: 5 pips
  - Max TP: 15 pips
  - Min SL: 5 pips
  - Max SL: 10 pips
  - Spread Limit: 20 pips

XAUUSD:
  - Min TP: 0.5 USD
  - Max TP: 2.0 USD
  - Min SL: 0.5 USD
  - Max SL: 1.5 USD
  - Spread Limit: 30 pips
```

### Risk Parameters
```
RISK_PER_TRADE = 0.25-0.5% of equity
MAX_POSITIONS = 2 (global)
MAX_POSITIONS_PER_SYMBOL = 1
MAX_CONSECUTIVE_LOSSES = 5
CONSECUTIVE_PAUSE_MIN = 30
BREAKEVEN_TRIGGER = 50% of target
TRAIL_TRIGGER = TP reached
TIME_STOP_SEC = 120
```

---

## ERROR HANDLING & RECOVERY

### Failure Scenarios

| Scenario | Detection | Action |
|----------|-----------|--------|
| MT5 disconnected | `is_connected()` returns False | Retry connection up to 5x, wait 10s between |
| MT5 frozen | No price updates for 10 min | Send alert, restart MT5 via watchdog |
| Telegram unreachable | Send fails | Queue message, retry every 60s |
| VPS resource spike | CPU > 85% or RAM > 400MB | Throttle loop, send alert |
| Trade execution failed | Order rejected by MT5 | Log error, skip trade, continue |
| Position tracking lost | Can't find open position | Resync positions from MT5 |
| Process crashed | Watchdog detects no heartbeat | Auto-restart main.py |

### Logging

**Log Files:**
- `logs/aegis.log` - Main trading activity
- `logs/errors.log` - All errors
- `logs/trades.log` - Every trade entry/exit
- `logs/telegram.log` - Bot communications
- `logs/watchdog.log` - Watchdog events

**Journal:**
- `data/journal.csv` - Full trade history

---

## VPS OPERATION

### Auto-Start After Reboot
```
Windows Task Scheduler
├─ Task: "Aegis Trading Bot"
├─ Trigger: At startup
├─ Action: Run batch file → Python main.py
├─ Run with highest privileges
└─ Retry on failure
```

**Or via NSSM (Non-Sucking Service Manager):**
```
nssm install AegisBot "C:\Python\python.exe" "C:\Aegis_Gold\core\main.py"
nssm set AegisBot AppStdout "C:\Aegis_Gold\logs\stdout.log"
nssm set AegisBot AppStderr "C:\Aegis_Gold\logs\stderr.log"
nssm set AegisBot AppExit Default Restart
```

### 24/7 Operation
- ✅ Runs even when user's laptop is OFF
- ✅ Continues trading if user's internet disconnects
- ✅ Auto-recovers from crashes
- ✅ Sends status via Telegram
- ✅ Can be controlled remotely via Telegram commands

---

## TESTING CHECKLIST

- [ ] MT5 connection stable
- [ ] Telegram token valid
- [ ] Can open positions on EURUSD
- [ ] Can open positions on XAUUSD
- [ ] Stops and targets placed correctly
- [ ] Positions close at TP/SL
- [ ] Breakeven moves at 50%
- [ ] Telegram notifications arrive
- [ ] Commands respond (/start, /status, /stop, /resume)
- [ ] Daily P&L calculated correctly
- [ ] Consecutive loss limit pauses trading
- [ ] Spread filter works
- [ ] Time stops close positions
- [ ] Watchdog restarts process if killed
- [ ] VPS reboot auto-starts bot
- [ ] Logs capture all events

---

## SUCCESS METRICS

✅ **System is ready when:**
1. Bot runs 24/7 on VPS without user intervention
2. Trades execute automatically on valid signals
3. All Telegram notifications arrive in real-time
4. Bot recovers from all failure scenarios
5. P&L calculated accurately
6. Remote commands work instantly
7. Watchdog keeps system alive
8. Logs show no errors or warnings

---

**Status:** Ready for implementation  
**Next Step:** Deploy to VPS and test live

