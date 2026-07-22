# ============================================================
# TRADE LOGGER — SQLite database + CSV + performance stats
# ============================================================

import sqlite3
import csv
import os
from datetime import datetime, date
from loguru import logger
from config import DB_FILE, TRADE_FILE, LOG_FILE


def init():
    """Create logs folder and database tables."""
    os.makedirs("logs", exist_ok=True)

    # Loguru file logger
    logger.add(LOG_FILE, rotation="1 day", retention="30 days",
               format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    conn = _conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket      INTEGER,
            signal      TEXT,
            open_price  REAL,
            close_price REAL,
            sl          REAL,
            tp          REAL,
            lot         REAL,
            open_time   TEXT,
            close_time  TEXT,
            profit      REAL,
            pips        REAL,
            confidence  INTEGER,
            reason      TEXT,
            status      TEXT DEFAULT 'OPEN'
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_events (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            time      TEXT,
            event     TEXT,
            detail    TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Trade logger initialized.")


def log_trade_open(ticket: int, signal: str, price: float,
                   sl: float, tp: float, lot: float,
                   confidence: int, reason: str) -> int:
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO trades (ticket, signal, open_price, sl, tp, lot,
                            open_time, confidence, reason, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
    """, (ticket, signal, price, sl, tp, lot,
          datetime.utcnow().isoformat(), confidence, reason))
    row_id = c.lastrowid
    conn.commit()
    conn.close()

    # Also write to CSV
    _append_csv({
        "id": row_id, "ticket": ticket, "signal": signal,
        "open_price": price, "sl": sl, "tp": tp, "lot": lot,
        "open_time": datetime.utcnow().isoformat(),
        "confidence": confidence, "reason": reason, "status": "OPEN"
    })
    return row_id


def log_trade_close(ticket: int, close_price: float, profit: float):
    pips = 0
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT signal, open_price FROM trades WHERE ticket=?", (ticket,))
    row = c.fetchone()
    if row:
        signal, open_price = row
        pips = round((close_price - open_price) * (1 if signal == "BUY" else -1) * 10, 1)
    c.execute("""
        UPDATE trades
        SET close_price=?, close_time=?, profit=?, pips=?, status=?
        WHERE ticket=?
    """, (close_price, datetime.utcnow().isoformat(),
          round(profit, 2), pips, "WIN" if profit > 0 else "LOSS", ticket))
    conn.commit()
    conn.close()
    logger.info(f"Trade {ticket} closed | Profit: ${profit:.2f} | Pips: {pips}")


def log_event(event: str, detail: str = ""):
    conn = _conn()
    c = conn.cursor()
    c.execute("INSERT INTO bot_events (time, event, detail) VALUES (?,?,?)",
              (datetime.utcnow().isoformat(), event, detail))
    conn.commit()
    conn.close()


def get_today_trades() -> list:
    today = date.today().isoformat()
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE open_time LIKE ?", (f"{today}%",))
    rows = c.fetchall()
    conn.close()
    cols = ["id","ticket","signal","open_price","close_price","sl","tp",
            "lot","open_time","close_time","profit","pips","confidence","reason","status"]
    return [dict(zip(cols, r)) for r in rows]


def get_recent_closed_trades(limit: int = 10) -> list:
    conn = _conn()
    c = conn.cursor()
    c.execute("""
        SELECT ticket, signal, open_price, close_price, profit, pips, status
        FROM trades WHERE status IN ('WIN','LOSS')
        ORDER BY close_time DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    cols = ["ticket","signal","open_price","close_price","profit","pips","status"]
    return [dict(zip(cols, r)) for r in rows]


def get_performance_stats() -> dict:
    conn = _conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM trades WHERE status IN ('WIN','LOSS')")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM trades WHERE status='WIN'")
    wins = c.fetchone()[0]
    c.execute("SELECT SUM(profit) FROM trades WHERE status IN ('WIN','LOSS')")
    total_profit = c.fetchone()[0] or 0
    c.execute("SELECT AVG(profit) FROM trades WHERE status='WIN'")
    avg_win = c.fetchone()[0] or 0
    c.execute("SELECT AVG(profit) FROM trades WHERE status='LOSS'")
    avg_loss = c.fetchone()[0] or 0
    conn.close()

    win_rate = (wins / total * 100) if total > 0 else 0
    return {
        "total_trades" : total,
        "wins"         : wins,
        "losses"       : total - wins,
        "win_rate_pct" : round(win_rate, 1),
        "total_profit" : round(total_profit, 2),
        "avg_win"      : round(avg_win, 2),
        "avg_loss"     : round(avg_loss, 2),
    }


def _conn():
    return sqlite3.connect(DB_FILE)


def _append_csv(row: dict):
    file_exists = os.path.exists(TRADE_FILE)
    with open(TRADE_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)
