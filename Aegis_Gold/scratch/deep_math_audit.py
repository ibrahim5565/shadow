import sqlite3, pandas as pd

BASE_DIR = r"d:\Trading\Aegis_Gold\data"
conn = sqlite3.connect(f"{BASE_DIR}/performance.db")
df = pd.read_sql_query("SELECT * FROM trades WHERE symbol LIKE '%XAU%' AND profit_usd != 0", conn)
conn.close()

xau_tp = df[df["profit_usd"] > 0]
xau_sl = df[(df["profit_usd"] < 0) & (df["sl"] > 0)]
xau_fc = df[(df["profit_usd"] < 0) & (df["sl"] <= 0)]

print("=== DEEP AUDIT OF REPLAY MATH & TP CAPPING ===")
print(f"Total XAUUSD TP Trades: {len(xau_tp)}")
print(f"Original Gross Profit from TP Trades: ${xau_tp['profit_usd'].sum():.2f}")
print(f"Max single win USD: ${xau_tp['profit_usd'].max():.2f}")
print(f"Wins > 72 pts ($0.72): {(xau_tp['profit_usd'] > 0.72).sum()} trades totaling ${xau_tp[xau_tp['profit_usd'] > 0.72]['profit_usd'].sum():.2f}")

# Calculate exact sum when wins > 72 pts are capped at 72 pts ($0.72)
capped_tp_sum = 0.0
reclassified_count = 0
reclassified_loss = 0.0
kept_win_sum = 0.0

for _, r in xau_tp.iterrows():
    pips = abs(r["profit_pips"])
    lot = r["lot"] if r["lot"] > 0 else 0.01
    pip_val = 0.01 * (lot / 0.01)
    
    # MAE check (0.3 factor)
    if (pips * 0.3) > 60:
        reclassified_count += 1
        reclassified_loss += 60 * pip_val
    else:
        sim_pips = min(pips, 72)
        kept_win_sum += sim_pips * pip_val

print("\n--- Breakdown of TP Trades Under Simulation ---")
print(f"1. Kept as Wins: {len(xau_tp) - reclassified_count} trades")
print(f"   Sum of Kept Wins (capped at 72pts): ${kept_win_sum:.2f}")
print(f"2. Reclassified as Stop-Outs (MAE > 60pts): {reclassified_count} trades")
print(f"   Sum of Losses from Reclassified TP: -${reclassified_loss:.2f}")
print(f"   Simulated Net Gross Profit from TP group: ${kept_win_sum - reclassified_loss:.2f}")
print(f"   (Original Uncapped Gross Profit was: ${xau_tp['profit_usd'].sum():.2f})")
print(f"   Total Gross Profit Reduction: -${xau_tp['profit_usd'].sum() - (kept_win_sum - reclassified_loss):.2f}")

print("\n--- Breakdown of Broker SL Trades Under Simulation ---")
print(f"Original Broker SL Losses: -${abs(xau_sl['profit_usd'].sum()):.2f}")
sim_broker_sl_loss = 0.0
for _, r in xau_sl.iterrows():
    pips = abs(r["profit_pips"])
    lot = r["lot"] if r["lot"] > 0 else 0.01
    pip_val = 0.01 * (lot / 0.01)
    sim_pips = min(pips, 60)
    sim_broker_sl_loss += sim_pips * pip_val
print(f"Simulated Broker SL Losses (capped at 60pts): -${sim_broker_sl_loss:.2f}")
print(f"Broker SL Improvement: +${abs(xau_sl['profit_usd'].sum()) - sim_broker_sl_loss:.2f}")

print("\n--- Overall Reconciliation ---")
print(f"Original All-XAUUSD Net PnL: ${df[df['symbol'].str.contains('XAU')]['profit_usd'].sum():.2f}")
print(f"Simulated Eligible Net PnL (Kept Wins - Reclassified TP - Sim Broker SL): ${kept_win_sum - reclassified_loss - sim_broker_sl_loss:.2f}")
print(f"Force-Close Losses (Unchanged): -${abs(xau_fc['profit_usd'].sum()):.2f}")
print(f"Simulated All-XAUUSD Net PnL (Eligible Net - Force Close Losses): ${kept_win_sum - reclassified_loss - sim_broker_sl_loss - abs(xau_fc['profit_usd'].sum()):.2f}")
