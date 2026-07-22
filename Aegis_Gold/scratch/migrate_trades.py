import sys
import os
import sqlite3
from datetime import datetime

# Setup path to import brain modules
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from brain.trade_memory import get_trade_memory_db, TradeMemory

def migrate():
    perf_db_path = os.path.join(BASE_DIR, "data", "performance.db")
    memory_db = get_trade_memory_db()
    
    if not os.path.exists(perf_db_path):
        print(f"Error: {perf_db_path} does not exist.")
        return
        
    print(f"Reading trades from performance database: {perf_db_path}...")
    
    conn_perf = sqlite3.connect(perf_db_path)
    conn_perf.row_factory = sqlite3.Row
    cursor_perf = conn_perf.cursor()
    
    cursor_perf.execute("SELECT * FROM trades")
    rows = cursor_perf.fetchall()
    print(f"Found {len(rows)} trades to migrate.")
    
    success_count = 0
    
    for row in rows:
        ticket = row['id']
        symbol = row['symbol']
        direction = row['direction']
        entry_price = row['entry_price'] or 0.0
        lot = row['lot'] or 0.01
        confidence = int(row['ai_confidence'] or 50)
        
        # Build TradeMemory object for entry
        trade = TradeMemory(
            trade_id=ticket,
            symbol=symbol,
            direction=direction,
            entry_time=row['timestamp'] or datetime.utcnow().isoformat(),
            entry_price=entry_price,
            lot_size=lot,
            confidence=confidence,
            signal_source="SCALP",
            sl_points=int(row['sl'] or 0),
            tp_points=int(row['tp'] or 0),
            regime=row['regime'] or "UNKNOWN",
            structure="MID_RANGE",
            rsi=row['rsi_at_entry'] or 0.0,
            adx=row['adx_at_entry'] or 0.0,
            session=row['session'] or "UNKNOWN"
        )
        
        # Record entry
        if memory_db.record_entry(trade):
            # Record exit
            exit_price = row['exit_price']
            profit_usd = row['profit_usd']
            duration_min = row['trade_duration_min'] or 0.0
            win_loss = row['win_loss']
            
            exit_reason = "MANUAL"
            if win_loss == 1:
                exit_reason = "TP"
            elif win_loss == -1:
                exit_reason = "SL"
                
            exit_data = {
                "exit_time": datetime.utcnow().isoformat(),
                "exit_price": exit_price,
                "profit_usd": profit_usd,
                "duration_seconds": int(duration_min * 60),
                "exit_reason": exit_reason,
                "profit_pct": 0.0
            }
            
            if memory_db.update_exit(ticket, exit_data):
                success_count += 1
                
    conn_perf.close()
    print(f"Successfully migrated {success_count}/{len(rows)} trades.")

if __name__ == "__main__":
    migrate()
