import os
import sqlite3
import logging
import json
from datetime import datetime, timezone
from brain.trade_memory import get_trade_memory_db, TradeMemory

logger = logging.getLogger("aegis.performance")
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "performance.db"))


def init_db():
    """Initializes the performance SQLite database and creates the trades table if missing."""
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                sl REAL,
                tp REAL,
                lot REAL,
                profit_usd REAL,
                profit_pips REAL,
                trade_duration_min REAL,
                regime TEXT,
                pattern TEXT,
                adx_at_entry REAL,
                rsi_at_entry REAL,
                ai_confidence REAL,
                session TEXT,
                partial_tp_hit INTEGER DEFAULT 0,
                win_loss INTEGER,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()
        logger.info("Performance SQLite database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing SQLite database: {e}")


def log_trade_open(ticket, symbol, direction, entry_price, sl, tp, lot, regime, pattern, adx, rsi, confidence, session):
    """Logs the entry execution parameters of a trade into SQLite and trade_memory."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO trades (
                id, symbol, direction, entry_price, sl, tp, lot, regime, pattern,
                adx_at_entry, rsi_at_entry, ai_confidence, session, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticket, symbol, direction, entry_price, sl, tp, lot, regime, pattern,
            adx, rsi, confidence, session, datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()
        logger.info(f"Logged trade open #{ticket} for {symbol} to SQLite.")
    except Exception as e:
        logger.error(f"Error logging trade open to SQLite: {e}")

    # Mirror to trade_memory.db
    try:
        memory_db = get_trade_memory_db()
        
        # Determine classification tags based on setup parameters
        tags_list = []
        if regime == "SMC" or "SMC" in str(pattern):
            tags_list.append("Smart Money Concepts")
            pat_str = str(pattern).upper()
            if "BOS" in pat_str:
                tags_list.append("Break of Structure")
            if "CHOCH" in pat_str:
                tags_list.append("CHOCH")
            if "OB" in pat_str or "BLOCK" in pat_str:
                tags_list.append("Order Block")
            if "SWEEP" in pat_str or "LIQUIDITY" in pat_str:
                tags_list.append("Liquidity Sweep")
            if "FVG" in pat_str or "GAP" in pat_str:
                tags_list.append("Fair Value Gap")
        else:
            tags_list.append("Scalping")
            pat_str = str(pattern).upper()
            if "BOUNCE" in pat_str:
                tags_list.append("Support Bounce")
            if "REJECTION" in pat_str:
                tags_list.append("Resistance Rejection")
            if "BREAKOUT" in pat_str:
                tags_list.append("Range Breakout")
            if "TREND" in pat_str or "CONTINUATION" in pat_str:
                tags_list.append("Trend Continuation")
            if "REVERSAL" in pat_str:
                tags_list.append("Trend Reversal")
            if "PULLBACK" in pat_str:
                tags_list.append("Pullback")

        trade = TradeMemory(
            trade_id=ticket,
            symbol=symbol,
            direction=direction,
            entry_time=datetime.now().isoformat(),
            entry_price=entry_price,
            lot_size=lot,
            confidence=int(confidence or 50),
            signal_source="SMC" if (regime == "SMC" or "SMC" in str(pattern)) else "SCALP",
            sl_points=int(sl or 0),
            tp_points=int(tp or 0),
            regime=regime or "UNKNOWN",
            structure="MID_RANGE",
            rsi=rsi or 0.0,
            adx=adx or 0.0,
            session=session or "UNKNOWN",
            tags=json.dumps(tags_list),
            notes=f"Auto-classified trade for pattern: {pattern}"
        )
        memory_db.record_entry(trade)
    except Exception as e:
        logger.error(f"Error mirroring trade open to trade_memory: {e}")


def log_trade_close(ticket, exit_price, profit_usd, profit_pips, duration_sec, partial_tp_hit, win_loss):
    """Updates the database entry with exit details when a trade is closed."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        duration_min = round(duration_sec / 60.0, 2)
        cursor.execute("""
            UPDATE trades SET 
                exit_price = ?,
                profit_usd = ?,
                profit_pips = ?,
                trade_duration_min = ?,
                partial_tp_hit = ?,
                win_loss = ?
            WHERE id = ?
        """, (
            exit_price, profit_usd, profit_pips, duration_min, partial_tp_hit, win_loss, ticket
        ))
        conn.commit()
        conn.close()
        logger.info(f"Updated closed trade #{ticket} details in SQLite.")
    except Exception as e:
        logger.error(f"Error logging trade close to SQLite: {e}")

    # Mirror to trade_memory.db
    try:
        memory_db = get_trade_memory_db()
        exit_reason = "MANUAL"
        if win_loss == 1:
            exit_reason = "TP"
        elif win_loss == -1:
            exit_reason = "SL"
            
        exit_data = {
            "exit_time": datetime.now().isoformat(),
            "exit_price": exit_price,
            "profit_usd": profit_usd,
            "duration_seconds": int(duration_sec),
            "exit_reason": exit_reason,
            "profit_pct": 0.0
        }
        memory_db.update_exit(ticket, exit_data)
    except Exception as e:
        logger.error(f"Error mirroring trade close to trade_memory: {e}")

    # Performance attribution — record outcome for signal-source analysis
    try:
        from brain.performance_attribution import record_attribution
        from brain.explainability import get_explanation_for_trade, update_outcome
        outcome = "WIN" if win_loss == 1 else ("LOSS" if win_loss == -1 else "BREAKEVEN")
        duration_min = round(duration_sec / 60.0, 2)
        explanation = get_explanation_for_trade(str(ticket))
        if explanation:
            update_outcome(str(ticket), outcome, profit_usd)
            import json as _json
            ctx = _json.loads(explanation.get("context_json", "{}"))
            bd = _json.loads(explanation.get("breakdown_json", "{}"))
            sig = _json.loads(explanation.get("signal_json", "{}"))
            full_exp = {
                "trade_id": ticket,
                "final_confidence": explanation.get("confidence", 0),
                "signal_sources": sig,
                "component_breakdown": bd,
                "market_context": ctx,
            }
            record_attribution(
                trade_id=str(ticket),
                symbol=explanation.get("symbol", ""),
                direction=explanation.get("direction", ""),
                outcome=outcome,
                pnl=profit_usd,
                holding_minutes=duration_min,
                explanation=full_exp,
            )
    except Exception as e:
        logger.error(f"Attribution recording failed for #{ticket}: {e}")

    # Champion/Challenger shadow outcome recording
    try:
        from brain.champion_challenger import get_arena
        outcome_str = "WIN" if win_loss == 1 else ("LOSS" if win_loss == -1 else "BREAKEVEN")
        import json as _json2
        rr_val = 0.0
        expl2 = get_explanation_for_trade(str(ticket)) if 'get_explanation_for_trade' in dir() else None
        if expl2:
            risk_data = _json2.loads(expl2.get("risk_json", "{}"))
            rr_val = float(risk_data.get("rr_ratio", 0.0))
        arena = get_arena()
        arena.record_champion_outcome(outcome_str, profit_usd, rr_val)
        arena.record_challenger_shadow(outcome_str, profit_usd, rr_val)
    except Exception as e:
        logger.error(f"Arena shadow recording failed for #{ticket}: {e}")




def get_performance_stats(last_n=10, days=None):
    """Computes and returns detailed performance statistics for the last N closed trades or within last X days."""
    try:
        import datetime as dt
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        if days is not None:
            since_dt = datetime.now(timezone.utc) - dt.timedelta(days=days)
            since_str = since_dt.isoformat()
            cursor.execute("""
                SELECT profit_usd, win_loss, session FROM trades 
                WHERE win_loss IS NOT NULL AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (since_str,))
        else:
            cursor.execute("""
                SELECT profit_usd, win_loss, session FROM trades 
                WHERE win_loss IS NOT NULL 
                ORDER BY timestamp DESC LIMIT ?
            """, (last_n,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
            
        wins = sum(1 for r in rows if r[1] == 1)
        losses = sum(1 for r in rows if r[1] == -1)
        total = len(rows)
        win_rate = (wins / total * 100) if total > 0 else 0
        
        avg_profit = sum(r[0] for r in rows if r[0] > 0) / (sum(1 for r in rows if r[0] > 0) or 1)
        avg_loss = sum(r[0] for r in rows if r[0] < 0) / (sum(1 for r in rows if r[0] < 0) or 1)
        
        best = max([r[0] for r in rows] + [0.0])
        worst = min([r[0] for r in rows] + [0.0])
        
        gross_profit = sum(r[0] for r in rows if r[0] > 0)
        gross_loss = abs(sum(r[0] for r in rows if r[0] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
        
        # Most profitable session
        sessions = [r[2] for r in rows if r[0] > 0]
        most_prof_session = max(set(sessions), key=sessions.count) if sessions else "N/A"
        
        return {
            "win_rate": round(win_rate, 1),
            "avg_profit": round(avg_profit, 2),
            "avg_loss": round(avg_loss, 2),
            "best": round(best, 2),
            "worst": round(worst, 2),
            "profit_factor": round(profit_factor, 2),
            "most_profitable_session": most_prof_session,
            "total_trades": total
        }
    except Exception as e:
        logger.error(f"Error getting performance stats: {e}")
        return None


def get_rolling_win_rate(last_n=20):
    """Calculates the win percentage over the last N trades."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT win_loss FROM trades 
            WHERE win_loss IS NOT NULL 
            ORDER BY timestamp DESC LIMIT ?
        """, (last_n,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows or len(rows) < 10:  # Fair threshold: need at least 10 trades before enforcing drawdown winrate limit
            return 100.0
            
        wins = sum(1 for r in rows if r[0] == 1)
        total = len(rows)
        return (wins / total * 100)
    except Exception as e:
        logger.error(f"Error getting rolling win rate: {e}")
        return 100.0
