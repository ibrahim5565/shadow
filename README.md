# 🤖 GOLD TRADING BOT — COMPLETE SETUP GUIDE

## Project Structure
```
gold_trading_bot/
├── config.py          ← All settings and credentials
├── main.py            ← Entry point, main loop
├── mt5_connector.py   ← MT5 broker communication
├── claude_analyst.py  ← Claude AI signal engine
├── risk_manager.py    ← Risk/safety logic (Plan A/B/C)
├── indicators.py      ← EMA, RSI, ATR, Bollinger Bands
├── trade_logger.py    ← SQLite + CSV trade logs
├── notifier.py        ← Telegram alerts
├── requirements.txt   ← Python dependencies
└── logs/              ← Auto-created: bot.log, trades.csv, trades.db
```

---

## ⚙️ STEP 1 — Install Python & Dependencies

```bash
# Python 3.10+ required
pip install -r requirements.txt
```

> MetaTrader5 library only works on **Windows** or **Wine on Linux**.

---

## ⚙️ STEP 2 — Configure Your Credentials

Open `config.py` and fill in:

```python
MT5_LOGIN    = 123456789          # Your MT5 account number
MT5_PASSWORD = "yourpassword"
MT5_SERVER   = "ICMarkets-Live"   # Your broker server name

CLAUDE_API_KEY = "sk-ant-..."     # From console.anthropic.com

TELEGRAM_BOT_TOKEN = "..."        # From @BotFather on Telegram
TELEGRAM_CHAT_ID   = "..."        # Your Telegram user ID
```

---

## ⚙️ STEP 3 — Set Up Telegram Alerts

1. Open Telegram → search **@BotFather**
2. Send `/newbot` → follow steps → copy your **bot token**
3. Send `/start` to your new bot
4. Get your Chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates`

---

## ⚙️ STEP 4 — Get Claude API Key

1. Go to **https://console.anthropic.com**
2. Create account → API Keys → Create Key
3. Paste into `config.py`

---

## ▶️ STEP 5 — Run the Bot

```bash
# Make sure MetaTrader 5 is open and logged in first
python main.py
```

---

## 🛡️ FAILSAFE PLANS

| Plan | Trigger | Action |
|------|---------|--------|
| **Plan A** | Normal operation | Full trading |
| **Plan B** | 5 consecutive losses | 24-hour pause |
| **Plan C** | Equity drops 5% | Emergency stop, manual review |

---

## 📊 Monitoring

- **Telegram**: Real-time alerts for every trade
- **logs/bot.log**: Full detailed log with timestamps
- **logs/trades.csv**: All trades in spreadsheet format
- **logs/trades.db**: SQLite database for analysis

---

## ⚠️ IMPORTANT NOTES

1. **Test on a DEMO account first** — always verify on demo before live
2. **MetaTrader 5 must be running** on the same machine
3. **VPS recommended** for 24/5 operation (Windows VPS)
4. **Never share config.py** — it contains your credentials
5. **Keep MT5 auto-trading enabled** in the platform settings

---

## 🔧 Recommended VPS Setup (for 24/5)

- **Provider**: Contabo or Vultr Windows VPS
- **OS**: Windows Server 2019
- **RAM**: 4GB minimum
- **Auto-start**: Add `python main.py` to Windows Task Scheduler

---

## 📈 Trading Parameters (defaults)

| Parameter | Value |
|-----------|-------|
| Symbol | XAUUSD (Gold) |
| Timeframe | M5 |
| Lot Size | 0.01 |
| SL | ATR × 1.5 |
| TP | ATR × 3.0 |
| Min AI Confidence | 75% |
| Max Daily Loss | 3% |
| Max Concurrent Trades | 2 |
| Scan Interval | 60 seconds |
