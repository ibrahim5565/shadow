import csv
import os

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for filename in ["journal.csv", "journal_backup.csv"]:
    path = os.path.join(base_dir, "data", filename)
    if not os.path.exists(path):
        continue
        
    print(f"=== File: {filename} ===")
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        
        june16_rows = []
        for r in rows:
            if r and any("2026-06-16" in field for field in r):
                june16_rows.append(r)
                
        print(f"Found {len(june16_rows)} rows for June 16")
        if june16_rows:
            print("First 3 rows:")
            for r in june16_rows[:3]:
                print(r)
            
            # If the file has a header, let's match columns. If not, let's see length of columns.
            # Standard columns: ["timestamp", "trade_id", "symbol", "mode", "session", "direction", "entry_price", "exit_price", "slippage_pts", "lot", "tp_price", "sl_price", "exit_reason", "pnl_points", "pnl_usd", "duration_sec", "spread_at_entry", "signal_score", "ai_approved", "equity_after"]
            print(f"Row length: {len(june16_rows[0])}")
            
            # Let's count wins and losses
            # If length is 20, pnl_usd is index 14
            # If length is larger/smaller, let's check
            wins, losses, others = 0, 0, 0
            for r in june16_rows:
                # Find exit timestamp (col 1) or pnl_usd (col 14)
                # Let's check if the row has exit price (col 7)
                if len(r) > 14:
                    pnl_str = r[14]
                    try:
                        pnl = float(pnl_str) if pnl_str else 0.0
                        if pnl > 0:
                            wins += 1
                        elif pnl < 0:
                            losses += 1
                        else:
                            others += 1
                    except ValueError:
                        others += 1
                else:
                    others += 1
            print(f"Wins: {wins}, Losses: {losses}, Zero/Open/Unknown: {others}")
