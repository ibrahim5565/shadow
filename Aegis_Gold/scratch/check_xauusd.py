import sqlite3, pandas as pd
conn = sqlite3.connect('data/trade_memory.db')
df = pd.read_sql_query(
    "SELECT symbol, sl_points, tp_points, atr, entry_price, exit_price, profit_usd, tp_was_hit, sl_was_hit, direction "
    "FROM trades WHERE symbol='XAUUSD' AND profit_usd IS NOT NULL AND sl_points > 0 LIMIT 10", conn)
conn.close()
print(df.to_string())
print("\nXAUUSD summary:")
conn2 = sqlite3.connect('data/trade_memory.db')
df2 = pd.read_sql_query(
    "SELECT COUNT(*) as n, AVG(sl_points) as avg_sl, AVG(tp_points) as avg_tp, AVG(atr) as avg_atr "
    "FROM trades WHERE symbol='XAUUSD' AND profit_usd IS NOT NULL AND sl_points > 0", conn2)
conn2.close()
print(df2)
