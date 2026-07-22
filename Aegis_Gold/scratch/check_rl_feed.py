import sys, os
sys.path.insert(0, '.')

print("=== REINFORCEMENT TRAINING FEED CHECK ===")
print()

# 1. Trade memory
from brain.trade_memory import get_trade_memory_db
tm = get_trade_memory_db()
count = tm.get_trade_count()
print(f"[FEED] Trade memory records: {count} trades available")
recent = tm.get_recent_trades(limit=3)
if recent:
    t = recent[0]
    print(f"[FEED] Latest trade: direction={t.get('direction')} profit={t.get('profit_usd')} regime={t.get('regime_type')}")
print()

# 2. RL Agent
from brain.reinforcement_agent import AegisRLAgent
agent = AegisRLAgent()
agent.populate_replay_buffer(tm)
buf_size = agent.replay_buffer.size()
print(f"[RL]  Replay buffer loaded: {buf_size} experiences")
metrics = agent.calculate_policy_metrics()
wr = metrics["win_rate"]
pf = metrics["profit_factor"]
ls = metrics["learning_stability"]
pi = metrics["policy_improvement"]
print(f"[RL]  Win Rate       : {wr:.1f}%")
print(f"[RL]  Profit Factor  : {pf:.3f}")
print(f"[RL]  Learning Stab  : {ls:.4f}")
print(f"[RL]  Policy Improv  : {pi:.4f}")
print()

# 3. Model file
import time
model_path = os.path.join(".", "models", "aegis_rl.pt")
if os.path.exists(model_path):
    size = os.path.getsize(model_path)
    mtime = time.ctime(os.path.getmtime(model_path))
    print(f"[MODEL] aegis_rl.pt: {size/1024:.1f} KB  |  Last updated: {mtime}")
else:
    print("[MODEL] No model yet - will be created on first full training run")
print()

# 4. Action prediction test
feats = [60, 70, 55, 55, 25, 0.5, 20, 3, 1]
action, conf = agent.predict_action(feats)
print(f"[TEST]  RL Q-Network action prediction: {action} ({conf}% confidence)")
print()
print("=== FEED CHECK COMPLETE ===")
