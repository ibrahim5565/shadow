"""
Aegis-Gold Phase 0 Diagnostic Script
Extracts and analyzes full closed-trade history from trade_memory.db, performance.db, and journal.csv.
Computes exact statistics on R:R asymmetry, exit reasons, MAE/MFE distributions, and regime/engine win rates.
"""

import os
import sys
import csv
import sqlite3
import json
import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

TRADE_MEMORY_DB = DATA_DIR / "trade_memory.db"
PERFORMANCE_DB  = DATA_DIR / "performance.db"
JOURNAL_CSV     = DATA_DIR / "journal.csv"

print(f"=== AEGIS-GOLD PHASE 0 DATA EXTRACTION ===")
print(f"Base Dir: {BASE_DIR}")
print(f"Data Dir: {DATA_DIR}")

df_mem = pd.DataFrame()
df_perf = pd.DataFrame()
df_journal = pd.DataFrame()

# 1. Try trade_memory.db
if TRADE_MEMORY_DB.exists():
    try:
        conn = sqlite3.connect(TRADE_MEMORY_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM trades")
        count = cursor.fetchone()[0]
        print(f"Found {count} trades in trade_memory.db")
        df_mem = pd.read_sql_query("SELECT * FROM trades", conn)
        conn.close()
    except Exception as e:
        print(f"Error reading trade_memory.db: {e}")

# 2. Try performance.db
if PERFORMANCE_DB.exists():
    try:
        conn = sqlite3.connect(PERFORMANCE_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM trades")
        count = cursor.fetchone()[0]
        print(f"Found {count} trades in performance.db")
        df_perf = pd.read_sql_query("SELECT * FROM trades", conn)
        conn.close()
    except Exception as e:
        print(f"Error reading performance.db: {e}")

# 3. Try journal.csv
if JOURNAL_CSV.exists():
    try:
        df_journal = pd.read_csv(JOURNAL_CSV)
        print(f"Found {len(df_journal)} trades in journal.csv")
    except Exception as e:
        print(f"Error reading journal.csv: {e}")

def analyze_df(df_input, name):
    if df_input.empty:
        print(f"\n[{name}] Dataset is empty.")
        return
    
    print(f"\n==========================================")
    print(f"--- DATASET: {name} ({len(df_input)} rows) ---")
    print(f"==========================================")
    
    pnl_col = None
    for c in ['profit_usd', 'pnl', 'profit']:
        if c in df_input.columns:
            pnl_col = c
            break
            
    if not pnl_col:
        print(f"No profit column found in {name}. Columns: {list(df_input.columns)}")
        return

    df_valid = df_input.dropna(subset=[pnl_col]).copy()
    # Convert pnl to numeric
    df_valid[pnl_col] = pd.to_numeric(df_valid[pnl_col], errors='coerce')
    df_valid = df_valid.dropna(subset=[pnl_col])
    
    wins = df_valid[df_valid[pnl_col] > 0]
    losses = df_valid[df_valid[pnl_col] < 0]
    zeros = df_valid[df_valid[pnl_col] == 0]
    
    total_trades = len(df_valid)
    num_wins = len(wins)
    num_losses = len(losses)
    num_zeros = len(zeros)
    
    total_pnl = df_valid[pnl_col].sum()
    win_rate = (num_wins / total_trades) * 100 if total_trades > 0 else 0.0
    
    total_win_usd = wins[pnl_col].sum()
    total_loss_usd = abs(losses[pnl_col].sum())
    
    avg_win = wins[pnl_col].mean() if num_wins > 0 else 0.0
    avg_loss = abs(losses[pnl_col].mean()) if num_losses > 0 else 0.0
    median_win = wins[pnl_col].median() if num_wins > 0 else 0.0
    median_loss = abs(losses[pnl_col].median()) if num_losses > 0 else 0.0
    
    max_win = wins[pnl_col].max() if num_wins > 0 else 0.0
    max_loss = losses[pnl_col].min() if num_losses > 0 else 0.0
    
    profit_factor = (total_win_usd / total_loss_usd) if total_loss_usd > 0 else (999.0 if total_win_usd > 0 else 0.0)
    asymmetry_ratio = (avg_loss / avg_win) if avg_win > 0 else 0.0
    
    print(f"Total Trades Analyzed: {total_trades}")
    print(f"Total Net PnL: ${total_pnl:.2f}")
    print(f"Wins: {num_wins} ({win_rate:.2f}%) | Losses: {num_losses} ({(num_losses/total_trades)*100:.2f}%) | Zeros: {num_zeros}")
    print(f"Gross Profit: ${total_win_usd:.2f} | Gross Loss: ${total_loss_usd:.2f}")
    print(f"PROFIT FACTOR: {profit_factor:.3f}")
    print(f"Average Win: ${avg_win:.4f} (Median: ${median_win:.4f})")
    print(f"Average Loss: ${avg_loss:.4f} (Median: ${median_loss:.4f})")
    print(f"Asymmetry Ratio (Avg Loss / Avg Win): {asymmetry_ratio:.2f}x")
    print(f"Max Win: ${max_win:.2f} | Max Loss: ${max_loss:.2f}")
    
    # Exit reason breakdown
    for col in ['exit_reason', 'reason', 'close_reason', 'pattern']:
        if col in df_valid.columns:
            print(f"\n--- Exit Breakdown by [{col}] ---")
            counts = df_valid[col].value_counts()
            for k, cnt in counts.items():
                sub = df_valid[df_valid[col] == k]
                sub_pnl = sub[pnl_col].sum()
                sub_avg = sub[pnl_col].mean()
                sub_wins = len(sub[sub[pnl_col] > 0])
                sub_wr = (sub_wins / cnt) * 100 if cnt > 0 else 0
                print(f"  - {k}: {cnt} trades ({cnt/total_trades*100:.1f}%) | WR: {sub_wr:.1f}% | Net PnL: ${sub_pnl:.2f} | Avg: ${sub_avg:.4f}")
    
    # Signal source breakdown
    for col in ['signal_source', 'regime', 'mode']:
        if col in df_valid.columns:
            print(f"\n--- Signal Breakdown by [{col}] ---")
            counts = df_valid[col].value_counts()
            for k, cnt in counts.items():
                sub = df_valid[df_valid[col] == k]
                sub_pnl = sub[pnl_col].sum()
                sub_wins = len(sub[sub[pnl_col] > 0])
                sub_wr = (sub_wins / cnt) * 100 if cnt > 0 else 0
                sub_avg_w = sub[sub[pnl_col] > 0][pnl_col].mean() if sub_wins > 0 else 0
                sub_avg_l = abs(sub[sub[pnl_col] < 0][pnl_col].mean()) if (cnt - sub_wins) > 0 else 0
                print(f"  - {k}: {cnt} trades | WR: {sub_wr:.1f}% | Net PnL: ${sub_pnl:.2f} | Avg Win: ${sub_avg_w:.2f} | Avg Loss: ${sub_avg_l:.2f}")

    # MAE / MFE breakdown
    for mae_c in ['max_drawdown_pct', 'mae', 'max_dd']:
        if mae_c in df_valid.columns:
            print(f"\n--- MAE ({mae_c}) Statistics ---")
            print(f"  Overall Avg MAE: {df_valid[mae_c].mean():.4f}")
            if num_wins > 0: print(f"  Winning Trades Avg MAE: {wins[mae_c].mean():.4f}")
            if num_losses > 0: print(f"  Losing Trades Avg MAE: {losses[mae_c].mean():.4f}")
            
    for mfe_c in ['max_profit_reached', 'mfe', 'max_profit']:
        if mfe_c in df_valid.columns:
            print(f"\n--- MFE ({mfe_c}) Statistics ---")
            print(f"  Overall Avg MFE: {df_valid[mfe_c].mean():.4f}")
            if num_wins > 0: print(f"  Winning Trades Avg MFE: {wins[mfe_c].mean():.4f}")
            if num_losses > 0: print(f"  Losing Trades Avg MFE: {losses[mfe_c].mean():.4f}")

    # Save summary json
    summary = {
        "dataset_name": name,
        "total_trades": total_trades,
        "total_pnl": round(total_pnl, 2),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 3),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "asymmetry_ratio": round(asymmetry_ratio, 2),
        "num_wins": num_wins,
        "num_losses": num_losses,
        "num_zeros": num_zeros
    }
    out_file = DATA_DIR / f"phase0_{name}_summary.json"
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSaved {name} summary to {out_file}")

analyze_df(df_mem, "trade_memory")
analyze_df(df_perf, "performance")
analyze_df(df_journal, "journal")
