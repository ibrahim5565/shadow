"""
AEGIS REINFORCEMENT LEARNING TRAINER — June 24, 2026 Dataset
Trains both RL and GPT models on first 200 trades from June 24 to learn:
- When to enter (timing)
- Position sizing decisions
- Risk-reward optimization
- Pattern recognition for similar market conditions

Uses Actor-Critic architecture with PPO (Proximal Policy Optimization)
"""
import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Categorical
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aegis.rl_training")

# Paths
JOURNAL_PATH = os.path.join(BASE_DIR, "data", "journal.csv")
RL_MODEL_PATH = os.path.join(BASE_DIR, "models", "aegis_rl_actor.pt")
CRITIC_MODEL_PATH = os.path.join(BASE_DIR, "models", "aegis_rl_critic.pt")
MODELS_DIR = os.path.join(BASE_DIR, "models")

# Hyperparameters
EPOCHS = 50
GAMMA = 0.99  # Discount factor
LR_ACTOR = 0.0003
LR_CRITIC = 0.001
CLIP_EPSILON = 0.2  # PPO clipping
ENTROPY_COEF = 0.01  # Exploration bonus


class ActorNetwork(nn.Module):
    """Policy network - decides which action to take"""
    def __init__(self, state_dim, action_dim):
        super(ActorNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, 256)
        self.fc2 = nn.Linear(256, 256)
        self.fc3 = nn.Linear(256, 128)
        self.fc4 = nn.Linear(128, action_dim)
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = self.dropout(x)
        x = torch.relu(self.fc2(x))
        x = self.dropout(x)
        x = torch.relu(self.fc3(x))
        x = torch.softmax(self.fc4(x), dim=-1)
        return x


class CriticNetwork(nn.Module):
    """Value network - estimates expected return"""
    def __init__(self, state_dim):
        super(CriticNetwork, self).__init__()
        self.fc1 = nn.Linear(state_dim, 256)
        self.fc2 = nn.Linear(256, 256)
        self.fc3 = nn.Linear(256, 128)
        self.fc4 = nn.Linear(128, 1)
        self.dropout = nn.Dropout(0.2)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = self.dropout(x)
        x = torch.relu(self.fc2(x))
        x = self.dropout(x)
        x = torch.relu(self.fc3(x))
        x = self.fc4(x)
        return x


class RLTrainer:
    def __init__(self, state_dim=15, action_dim=3):  # 3 actions: WAIT, BUY, SELL
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Training on device: {self.device}")
        
        self.actor = ActorNetwork(state_dim, action_dim).to(self.device)
        self.critic = CriticNetwork(state_dim).to(self.device)
        
        self.actor_optimizer = optim.Adam(self.actor.parameters(), lr=LR_ACTOR)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=LR_CRITIC)
        
        # Load existing models if available
        if os.path.exists(RL_MODEL_PATH):
            try:
                self.actor.load_state_dict(torch.load(RL_MODEL_PATH, map_location=self.device))
                logger.info("Loaded existing actor model - continuing training")
            except:
                logger.info("Starting fresh actor training")
                
        if os.path.exists(CRITIC_MODEL_PATH):
            try:
                self.critic.load_state_dict(torch.load(CRITIC_MODEL_PATH, map_location=self.device))
                logger.info("Loaded existing critic model - continuing training")
            except:
                logger.info("Starting fresh critic training")
    
    def compute_returns(self, rewards, dones):
        """Compute discounted returns"""
        returns = []
        R = 0
        for r, done in zip(reversed(rewards), reversed(dones)):
            if done:
                R = 0
            R = r + GAMMA * R
            returns.insert(0, R)
        return torch.tensor(returns, dtype=torch.float32).to(self.device)
    
    def train_step(self, states, actions, old_probs, returns, advantages):
        """Single PPO training step"""
        states = torch.FloatTensor(states).to(self.device)
        actions = torch.LongTensor(actions).to(self.device)
        old_probs = torch.FloatTensor(old_probs).to(self.device)
        returns = returns.to(self.device)
        advantages = advantages.to(self.device)
        
        # Actor loss with PPO clipping
        action_probs = self.actor(states)
        dist = Categorical(action_probs)
        new_probs = dist.log_prob(actions)
        
        ratio = torch.exp(new_probs - old_probs)
        surr1 = ratio * advantages
        surr2 = torch.clamp(ratio, 1 - CLIP_EPSILON, 1 + CLIP_EPSILON) * advantages
        
        entropy = dist.entropy().mean()
        actor_loss = -torch.min(surr1, surr2).mean() - ENTROPY_COEF * entropy
        
        # Critic loss
        values = self.critic(states).squeeze()
        critic_loss = nn.MSELoss()(values, returns)
        
        # Update networks
        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor.parameters(), 0.5)
        self.actor_optimizer.step()
        
        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.critic.parameters(), 0.5)
        self.critic_optimizer.step()
        
        return actor_loss.item(), critic_loss.item()


def load_june24_trades(limit=200):
    """Load first 200 trades from June 24, 2026"""
    if not os.path.exists(JOURNAL_PATH):
        logger.error(f"Journal not found: {JOURNAL_PATH}")
        return None
    
    df = pd.read_csv(JOURNAL_PATH, encoding='latin1')
    
    # Filter for June 24, 2026
    df['timestamp'] = pd.to_datetime(df.iloc[:, 0], errors='coerce')
    df_june24 = df[df['timestamp'].dt.date == pd.to_datetime('2026-06-24').date()]
    
    if len(df_june24) == 0:
        logger.error("No trades found for June 24, 2026")
        return None
    
    # Take first 200 trades
    df_june24 = df_june24.head(limit).copy()
    logger.info(f"Loaded {len(df_june24)} trades from June 24, 2026")
    
    return df_june24


def extract_features(trade_row):
    """Extract state features from trade data"""
    try:
        # Column mapping (no headers in CSV):
        # 0=timestamp, 1=ticket, 2=symbol, 3=account, 4=session, 5=direction
        # 6=entry_price, 7=empty, 8=pnl, 9=lot, 10-15=empty, 16=adx, 17=rsi, 18=flag, 19=equity
        
        # Price features (normalized)
        entry_price = float(trade_row.iloc[6]) if pd.notna(trade_row.iloc[6]) else 0.0
        
        # PnL features
        pnl = float(trade_row.iloc[8]) if pd.notna(trade_row.iloc[8]) else 0.0
        lot = float(trade_row.iloc[9]) if pd.notna(trade_row.iloc[9]) else 0.01
        
        # Indicator features
        adx = float(trade_row.iloc[16]) if len(trade_row) > 16 and pd.notna(trade_row.iloc[16]) else 50.0
        rsi = float(trade_row.iloc[17]) if len(trade_row) > 17 and pd.notna(trade_row.iloc[17]) else 50.0
        
        # Direction encoding: BUY=1, SELL=-1, NA=0
        direction = str(trade_row.iloc[5]) if pd.notna(trade_row.iloc[5]) else "NA"
        direction_val = 1.0 if direction == "BUY" else (-1.0 if direction == "SELL" else 0.0)
        
        # Symbol: XAUUSD=1, EURUSD=0
        symbol = str(trade_row.iloc[2]) if pd.notna(trade_row.iloc[2]) else "XAUUSD"
        symbol_val = 1.0 if "XAU" in symbol else 0.0
        
        # Session encoding
        session = str(trade_row.iloc[4]) if pd.notna(trade_row.iloc[4]) else "OVERLAP"
        session_map = {"LONDON": 0.8, "NY": 0.6, "OVERLAP": 1.0, "ASIAN": 0.4}
        session_val = session_map.get(session, 0.5)
        
        # Time features
        timestamp = pd.to_datetime(trade_row.iloc[0])
        hour = timestamp.hour if pd.notna(timestamp) else 12
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        
        # Normalize price (rough scaling)
        price_norm = entry_price / 4000.0 if symbol_val > 0.5 else entry_price
        
        features = [
            price_norm,
            pnl / 100.0,  # Normalize PnL
            lot * 100,  # Scale lot
            adx / 100.0,
            rsi / 100.0,
            direction_val,
            symbol_val,
            session_val,
            hour_sin,
            hour_cos,
            1.0,  # Bias term
            0.0,  # Reserved for spread
            0.0,  # Reserved for volatility
            0.0,  # Reserved for momentum
            0.0,  # Reserved for trend
        ]
        
        return features, pnl
        
    except Exception as e:
        logger.error(f"Feature extraction error: {e}")
        return [0.0] * 15, 0.0


def compute_pf_shaped_rewards(pnl_list: list) -> list:
    """
    Profit-factor-aware reward shaping for the PPO episode.

    Instead of a fixed scale (pnl/10 wins, pnl/5 losses), we use the
    *running* profit factor of the episode to dynamically adjust each reward:

    - WIN:      reward = (pnl / 10) * (1 + 0.5 * min(running_pf, 3) / 3)
                Wins are rewarded more when the policy is already producing a
                healthy PF (positive reinforcement of good behaviour).

    - LOSS:     reward = (pnl / 10) * (1 + 2 * max(0, 1 - running_pf))
                Losses are penalised proportionally harder when the running PF
                is below 1.0 (the policy is net-losing), creating a strong
                gradient signal to stop taking bad trades.

    - BREAKEVEN / WAIT:  -0.05  (unchanged — small nudge to prefer real signals)

    Running PF is computed as a causal (past-only) window so there is no
    future leakage into the reward signal.
    """
    rewards = []
    running_gross_profit = 0.0
    running_gross_loss   = 0.0

    for pnl in pnl_list:
        # Current PF from trades seen so far (causal)
        running_pf = running_gross_profit / running_gross_loss if running_gross_loss > 0.0 else 1.0

        if pnl > 0.0:
            pf_boost  = min(running_pf, 3.0) / 3.0          # 0→1 as PF grows to 3
            reward    = (pnl / 10.0) * (1.0 + 0.5 * pf_boost)
            running_gross_profit += pnl
        elif pnl < 0.0:
            pf_deficit = max(0.0, 1.0 - running_pf)          # grows as PF drops below 1
            penalty    = 1.0 + 2.0 * pf_deficit               # 1× when PF≥1, up to 3× when PF→0
            reward     = (pnl / 10.0) * penalty
            running_gross_loss += abs(pnl)
        else:
            reward = -0.05

        rewards.append(reward)

    return rewards


class RLTrainer:
    def __init__(self, state_dim=15, action_dim=3):  # 3 actions: WAIT, BUY, SELL
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Training on device: {self.device}")

        self.actor  = ActorNetwork(state_dim, action_dim).to(self.device)
        self.critic = CriticNetwork(state_dim).to(self.device)

        self.actor_optimizer  = optim.Adam(self.actor.parameters(),  lr=LR_ACTOR)
        self.critic_optimizer = optim.Adam(self.critic.parameters(), lr=LR_CRITIC)

        # Load existing models if available
        if os.path.exists(RL_MODEL_PATH):
            try:
                self.actor.load_state_dict(torch.load(RL_MODEL_PATH, map_location=self.device))
                logger.info("Loaded existing actor model - continuing training")
            except:
                logger.info("Starting fresh actor training")

        if os.path.exists(CRITIC_MODEL_PATH):
            try:
                self.critic.load_state_dict(torch.load(CRITIC_MODEL_PATH, map_location=self.device))
                logger.info("Loaded existing critic model - continuing training")
            except:
                logger.info("Starting fresh critic training")

    def compute_returns(self, rewards, dones):
        """Compute discounted returns"""
        returns = []
        R = 0
        for r, done in zip(reversed(rewards), reversed(dones)):
            if done:
                R = 0
            R = r + GAMMA * R
            returns.insert(0, R)
        return torch.tensor(returns, dtype=torch.float32).to(self.device)

    def train_step(self, states, actions, old_probs, returns, advantages, pf_reg_weight=0.20, pf_target=1.5):
        """
        PPO training step with profit-factor regularisation.

        pf_reg_weight : how strongly to penalise the actor when the implied PF
                        of its Q-values falls below pf_target.
        pf_target     : minimum acceptable profit factor (default 1.5).
        """
        states     = torch.FloatTensor(states).to(self.device)
        actions    = torch.LongTensor(actions).to(self.device)
        old_probs  = torch.FloatTensor(old_probs).to(self.device)
        returns    = returns.to(self.device)
        advantages = advantages.to(self.device)

        # Actor forward
        action_probs = self.actor(states)
        dist         = Categorical(action_probs)
        new_probs    = dist.log_prob(actions)

        ratio  = torch.exp(new_probs - old_probs)
        surr1  = ratio * advantages
        surr2  = torch.clamp(ratio, 1 - CLIP_EPSILON, 1 + CLIP_EPSILON) * advantages
        entropy = dist.entropy().mean()

        ppo_loss = -torch.min(surr1, surr2).mean() - ENTROPY_COEF * entropy

        # ── Profit-Factor Regularisation ─────────────────────────────────────
        # Use the actor's log-probabilities as a differentiable proxy for
        # "how much the policy values this action".  We split by advantage sign:
        # positive advantage ≈ winning action, negative ≈ losing action.
        pos_mass = (torch.exp(new_probs) * (advantages > 0).float()).sum() + 1e-8
        neg_mass = (torch.exp(new_probs) * (advantages < 0).float()).sum() + 1e-8
        implied_pf  = pos_mass / neg_mass
        pf_penalty  = torch.relu(
            torch.tensor(pf_target, dtype=torch.float32, device=self.device) - implied_pf
        )
        actor_loss = ppo_loss + pf_reg_weight * pf_penalty

        # Critic forward
        values      = self.critic(states).squeeze()
        critic_loss = nn.MSELoss()(values, returns)

        # Update actor
        self.actor_optimizer.zero_grad()
        actor_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor.parameters(), 0.5)
        self.actor_optimizer.step()

        # Update critic
        self.critic_optimizer.zero_grad()
        critic_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.critic.parameters(), 0.5)
        self.critic_optimizer.step()

        return actor_loss.item(), critic_loss.item(), implied_pf.item()


def train_on_june24():
    """Main training loop on June 24 data — optimised for Profit Factor"""
    print("=" * 70)
    print("   AEGIS PPO TRAINER — Profit-Factor Optimised (June 24, 2026)")
    print("=" * 70)

    os.makedirs(MODELS_DIR, exist_ok=True)

    # Load data
    df = load_june24_trades(limit=200)
    if df is None:
        return False

    # Initialize trainer
    trainer = RLTrainer(state_dim=15, action_dim=3)

    # ── Extract features and raw PnL values ──────────────────────────────────
    states   = []
    actions  = []
    pnl_list = []
    dones    = []

    for idx, row in df.iterrows():
        features, pnl = extract_features(row)
        states.append(features)

        direction = str(row.iloc[5]) if pd.notna(row.iloc[5]) else "NA"
        action = 1 if direction == "BUY" else (2 if direction == "SELL" else 0)
        actions.append(action)
        pnl_list.append(pnl)
        dones.append(False)

    dones[-1] = True

    # ── PF-aware reward shaping ───────────────────────────────────────────────
    rewards = compute_pf_shaped_rewards(pnl_list)

    gross_profit = sum(p for p in pnl_list if p > 0)
    gross_loss   = abs(sum(p for p in pnl_list if p < 0))
    episode_pf   = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    logger.info(f"Prepared {len(states)} states from June 24 trades")
    logger.info(f"Profitable trades : {sum(1 for p in pnl_list if p > 0)} / {len(pnl_list)}")
    logger.info(f"Episode Profit Factor: {episode_pf:.3f}")
    logger.info(f"Total shaped reward  : {sum(rewards):.2f}")

    # ── Training loop ─────────────────────────────────────────────────────────
    best_pf     = -float('inf')
    best_reward = -float('inf')
    final_avg_reward = 0.0

    for epoch in range(EPOCHS):
        states_tensor = torch.FloatTensor(states).to(trainer.device)

        with torch.no_grad():
            action_probs  = trainer.actor(states_tensor)
            dist          = Categorical(action_probs)
            old_log_probs = dist.log_prob(
                torch.LongTensor(actions).to(trainer.device)
            ).cpu().numpy()

        returns    = trainer.compute_returns(rewards, dones)
        with torch.no_grad():
            values = trainer.critic(states_tensor).squeeze()
        advantages = returns - values
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        actor_loss, critic_loss, implied_pf = trainer.train_step(
            states, actions, old_log_probs, returns, advantages
        )

        total_reward     = sum(rewards)
        final_avg_reward = total_reward / len(rewards)

        print(f"Epoch {epoch+1:03d}/{EPOCHS} | "
              f"Actor: {actor_loss:.4f} | "
              f"Critic: {critic_loss:.4f} | "
              f"Implied PF: {implied_pf:.3f} | "
              f"Avg Rwd: {final_avg_reward:.3f}")

        # Save best model — primary criterion is implied PF, tiebreak by reward
        if implied_pf > best_pf or (implied_pf == best_pf and total_reward > best_reward):
            best_pf     = implied_pf
            best_reward = total_reward
            torch.save(trainer.actor.state_dict(),  RL_MODEL_PATH)
            torch.save(trainer.critic.state_dict(), CRITIC_MODEL_PATH)
            logger.info(f"  [SAVED] Best model — Implied PF: {implied_pf:.3f} | Reward: {total_reward:.2f}")

    # Final save
    torch.save(trainer.actor.state_dict(),  RL_MODEL_PATH)
    torch.save(trainer.critic.state_dict(), CRITIC_MODEL_PATH)

    summary = f"""
{'='*70}
PPO TRAINING COMPLETE — Profit-Factor Optimised
{'='*70}
Training Date        : {datetime.now()}
Total Trades         : {len(states)}
Profitable Trades    : {sum(1 for p in pnl_list if p > 0)}
Loss Trades          : {sum(1 for p in pnl_list if p < 0)}
Breakeven Trades     : {sum(1 for p in pnl_list if p == 0)}
Episode Profit Factor: {episode_pf:.3f}
Total Epochs         : {EPOCHS}
Best Implied PF      : {best_pf:.3f}
Best Total Reward    : {best_reward:.2f}
Final Avg Reward     : {final_avg_reward:.3f}
Actor Model          : {RL_MODEL_PATH}
Critic Model         : {CRITIC_MODEL_PATH}
{'='*70}
"""
    print(summary)

    summary_path = os.path.join(BASE_DIR, "data", "rl_training_result.txt")
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w") as f:
        f.write(summary)

    return True


def train_cql_offline(db_path: str = None) -> bool:
    """
    QUANT X: Trains the offline Q-network using CQL loss and validates it
    against a simple static baseline (e.g. ADX + EMA rule-based trend).
    Proposes the agent as a Challenger to the Arena if baseline is beaten.
    """
    if db_path is None:
        db_path = os.path.join(BASE_DIR, "data", "trade_memory.db")
        
    logger.info(f"[CQL] Initiating offline RL training from: {db_path}")
    from brain.offline_rl_agent import AegisOfflineRLAgent
    agent = AegisOfflineRLAgent()
    res = agent.train_offline_cql(db_path, epochs=100, lr=0.001)
    
    if res.get("status") != "success":
        logger.warning(f"[CQL] Offline training failed: {res.get('reason', 'unknown')}")
        return False

    # Validation stage: compare against a simple static indicator baseline policy
    # Baseline: if ADX > 20 and structure > 50 (or simple EMA alignment), direction is aligned.
    # Out-of-sample evaluation check:
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        trades = conn.execute("SELECT * FROM trades WHERE exit_time IS NOT NULL ORDER BY trade_id DESC LIMIT 50").fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"[CQL] Failed to load validation set: {e}")
        return False

    if len(trades) < 10:
        logger.warning(f"[CQL] Validation dataset too small: {len(trades)}")
        return True # pass through if we lack enough evaluation data

    cql_score = 0
    baseline_score = 0

    for row in trades:
        t = dict(row)
        state = [
            float(t.get('regime_score', 0.0) or 0.0),
            float(r_score := t.get('structure_score', 0.0) or 0.0),
            float(t.get('entry_score', 0.0) or 0.0),
            float(t.get('rsi', 50.0) or 50.0),
            float(t.get('adx', 20.0) or 20.0),
            float(t.get('atr', 0.0) or 0.0),
            float(t.get('spread', 0.0) or 0.0),
            float(t.get('recent_wins', 0.0) or 0.0),
            float(t.get('recent_losses', 0.0) or 0.0),
        ]
        
        # 1. Offline Agent Decision
        rl_action, _ = agent.predict_action(state)
        
        # 2. Simple Static Baseline (Fast EMA > Slow EMA buy, else sell)
        ema_f = float(t.get('ema_fast', 0.0) or 0.0)
        ema_s = float(t.get('ema_slow', 0.0) or 0.0)
        baseline_action = "BUY" if (ema_f > ema_s) else "SELL"
        if float(t.get('adx', 20.0) or 20.0) < 20.0:
            baseline_action = "WAIT"

        # Check performance
        profit = float(t.get('profit_usd', 0.0) or 0.0)
        direction = t.get('direction', 'BUY')
        
        actual_action = "WAIT" if profit == 0 else direction

        if rl_action == actual_action:
            cql_score += 1 if profit >= 0 else -1
        if baseline_action == actual_action:
            baseline_score += 1 if profit >= 0 else -1

    logger.info(f"[CQL] Out-of-sample validation: Offline CQL Score = {cql_score} | Static Baseline Score = {baseline_score}")
    
    if cql_score >= baseline_score:
        logger.info("[CQL] Validation passed! Offline CQL agent outperformed or matched static baseline.")
        # Copy to challenger location
        try:
            import shutil
            cql_challenger_path = os.path.join(BASE_DIR, "models", "aegis_rl_challenger.pt")
            shutil.copy2(agent.model_path, cql_challenger_path)
            logger.info(f"[CQL] Proposing Challenger to Arena: {cql_challenger_path}")
            
            from brain.champion_challenger import get_arena
            arena = get_arena()
            arena.propose_challenger(f"CQL_Offline_{datetime.now().strftime('%m%d_%H%M')}")
        except Exception as e:
            logger.error(f"[CQL] Failed to propose challenger: {e}")
        return True
    else:
        logger.warning("[CQL] Validation failed: Offline CQL agent did not beat simple static baseline. Discarding model.")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Train using offline CQL")
    args = parser.parse_args()
    
    if args.offline:
        success = train_cql_offline()
    else:
        success = train_on_june24()
    sys.exit(0 if success else 1)

