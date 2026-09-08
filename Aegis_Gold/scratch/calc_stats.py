import os
import glob
import sqlite3
import pandas as pd

base_dir = r"d:\Trading"
db_files = glob.glob(os.path.join(base_dir, "**", "*.db"), recursive=True)
print(f"Found {len(db_files)} DB files: {db_files}")

for db_path in db_files:
    print(f"\n==========================================")
    print(f"Analyzing Database: {db_path}")
    print(f"==========================================")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cur.fetchall()]
        print(f"Tables: {tables}")
        
        for tname in tables:
            print(f"\n--- Table: {tname} ---")
            df = pd.read_sql_query(f"SELECT * FROM {tname}", conn)
            print(f"Total Rows: {len(df)}")
            print(f"Columns: {list(df.columns)}")
            
            # Check if profit or profit_usd column exists
            profit_col = None
            for c in ['profit_usd', 'profit', 'pnl', 'profit_pips', 'realized_pnl']:
                if c in df.columns:
                    profit_col = c
                    break
            
            if profit_col:
                valid_trades = df[df[profit_col].notnull() & (df[profit_col] != 0)]
                print(f"Trades with non-zero profit ('{profit_col}'): {len(valid_trades)}")
                if len(valid_trades) > 0:
                    wins = valid_trades[valid_trades[profit_col] > 0]
                    losses = valid_trades[valid_trades[profit_col] < 0]
                    
                    gross_profit = wins[profit_col].sum()
                    gross_loss = abs(losses[profit_col].sum())
                    
                    win_rate = (len(wins) / len(valid_trades)) * 100 if len(valid_trades) > 0 else 0.0
                    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)
                    
                    print(f"  Total Closed Trades: {len(valid_trades)}")
                    print(f"  Winning Trades: {len(wins)}")
                    print(f"  Losing Trades: {len(losses)}")
                    print(f"  Gross Profit: ${gross_profit:,.2f}")
                    print(f"  Gross Loss: ${gross_loss:,.2f}")
                    print(f"  Net Profit: ${gross_profit - gross_loss:,.2f}")
                    print(f"  WIN RATE: {win_rate:.2f}%")
                    print(f"  PROFIT FACTOR: {profit_factor:.2f}")
            else:
                print("No obvious profit column found.")
                if 'win_loss' in df.columns:
                    wl_valid = df[df['win_loss'].notnull()]
                    if len(wl_valid) > 0:
                        wins = wl_valid[wl_valid['win_loss'] == 1]
                        win_rate = (len(wins) / len(wl_valid)) * 100
                        print(f"  Based on 'win_loss' column:")
                        print(f"  Total Valid: {len(wl_valid)}, Wins: {len(wins)}, Win Rate: {win_rate:.2f}%")
                        
        conn.close()
    except Exception as e:
        print(f"Error processing {db_path}: {e}")
