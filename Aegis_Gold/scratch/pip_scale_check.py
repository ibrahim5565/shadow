import sqlite3, os, pandas as pd

BASE_DIR = r"d:\Trading\Aegis_Gold"
PERF_DB  = os.path.join(BASE_DIR, "data", "performance.db")
conn = sqlite3.connect(PERF_DB)
df = pd.read_sql_query(
    "SELECT profit_pips, profit_usd, win_loss, lot, entry_price, exit_price "
    "FROM trades WHERE symbol LIKE '%XAU%' AND profit_usd != 0",
    conn
)
conn.close()

wins = df[df["profit_usd"] > 0]
loss = df[df["profit_usd"] < 0]

print("=== PROFIT_PIPS SCALE CHECK ===")
print(f"Total XAUUSD: {len(df)} | Wins: {len(wins)} | Losses: {len(loss)}")
print()
print("Sample rows (first 15):")
print(df.head(15)[["profit_pips","profit_usd","lot","entry_price","exit_price","win_loss"]].to_string())
print()
print("Win pips distribution:")
print(f"  p10={wins['profit_pips'].quantile(0.10):.1f}  p25={wins['profit_pips'].quantile(0.25):.1f}  p50={wins['profit_pips'].quantile(0.50):.1f}  p75={wins['profit_pips'].quantile(0.75):.1f}  p90={wins['profit_pips'].quantile(0.90):.1f}")
print(f"  min={wins['profit_pips'].min():.1f}  max={wins['profit_pips'].max():.1f}  mean={wins['profit_pips'].mean():.1f}")
print()
print(f"Wins with profit_pips < 60: {(wins['profit_pips'] < 60).sum()} of {len(wins)} ({(wins['profit_pips'] < 60).mean()*100:.1f}%)")
print(f"Wins with profit_pips >= 60: {(wins['profit_pips'] >= 60).sum()} of {len(wins)}")
print()
print("Loss pips distribution:")
print(f"  p10={loss['profit_pips'].quantile(0.10):.1f}  p25={loss['profit_pips'].quantile(0.25):.1f}  p50={loss['profit_pips'].quantile(0.50):.1f}  p75={loss['profit_pips'].quantile(0.75):.1f}  p90={loss['profit_pips'].quantile(0.90):.1f}")
print()
# Check price movement consistency
# For XAUUSD, 1 pip = 0.01, so 60pt = $0.60 per 0.01 lot
# But profit_pips 56 -> profit_usd 0.73: implies lot=0.01, pip_val~$0.13/pip?
# Check: avg pip value = avg_usd / avg_pips
if len(wins) > 0 and wins["profit_pips"].mean() != 0:
    avg_pip_usd = wins["profit_usd"].mean() / wins["profit_pips"].mean()
    print(f"Implied pip value (USD/pip): ${avg_pip_usd:.4f}")
    print(f"Implied lot (at $1/pip per 0.01 lot): {avg_pip_usd:.4f}")
    print()
    # What are the actual lot sizes?
    print(f"Lot distribution: {df['lot'].describe()}")
