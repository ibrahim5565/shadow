import os
import json
import logging
import sqlite3
from datetime import datetime
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

logger = logging.getLogger("aegis.reinforcement_agent")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "aegis_rl.pt")

class ReplayBuffer:
    def __init__(self, capacity=5000):
        self.capacity = capacity
        self.buffer = []

    def push(self, state, action, reward, next_state, result, classification, confidence, risk, regime):
        if len(self.buffer) >= self.capacity:
            self.buffer.pop(0)
        self.buffer.append({
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state,
            "result": result,
            "classification": classification,
            "confidence": confidence,
            "risk": risk,
            "regime": regime
        })

    def size(self):
        return len(self.buffer)


class AegisQNetwork(nn.Module):
    """
    Q-Network for Aegis RL Agent.
    Maps state features to Q-values for actions [WAIT, BUY, SELL].
    """
    def __init__(self, input_dim=9, hidden_dim=64, output_dim=3):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, x):
        return self.network(x)


class AegisRLAgent:
    def __init__(self, model_path=None):
        self.model_path = model_path or MODEL_PATH
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AegisQNetwork()
        self.replay_buffer = ReplayBuffer()
        
        if os.path.exists(self.model_path):
            try:
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                logger.info(f"[RL] Aegis RL Agent loaded from {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load RL agent weights: {e}")
        else:
            logger.warning(f"No RL weights found at {self.model_path}. Starting with random parameters.")
            
        self.model.to(self.device)
        self.model.eval()

    def get_action_q_values(self, state_features: list) -> list:
        """
        Returns Q-values for [WAIT, BUY, SELL] based on state features.
        state_features: [regime_score, structure_score, entry_score, rsi, adx, atr, spread, recent_wins, recent_losses]
        """
        # Ensure state features is of length 9
        if len(state_features) < 9:
            state_features = state_features + [0.0] * (9 - len(state_features))
        elif len(state_features) > 9:
            state_features = state_features[:9]

        with torch.no_grad():
            x = torch.tensor([state_features], dtype=torch.float32).to(self.device)
            q_values = self.model(x)
            return q_values.cpu().numpy()[0].tolist()

    def predict_action(self, state_features: list) -> tuple:
        """
        Selects optimal action [WAIT, BUY, SELL] based on max Q-value.
        Returns (action_string, confidence_score)
        """
        q_vals = self.get_action_q_values(state_features)
        action_idx = int(np.argmax(q_vals))
        
        # Calculate soft confidence based on exp(Q) ratio
        exp_q = np.exp(q_vals - np.max(q_vals)) # subtract max for numerical stability
        softmax_probs = exp_q / np.sum(exp_q)
        confidence = int(softmax_probs[action_idx] * 100)

        actions = ["WAIT", "BUY", "SELL"]
        return actions[action_idx], confidence

    @staticmethod
    def _compute_pf_aware_reward(profit: float, gross_profits: float, gross_losses: float) -> float:
        """
        Profit-factor-aware reward shaping.

        Philosophy:
        - Wins are rewarded proportionally to their contribution to gross profit,
          scaled up when the current profit factor is healthy (PF > 1).
        - Losses are penalized harder when PF is below 1.0 (i.e. the policy is
          net-losing) — the deficit below 1.0 amplifies the penalty.
        - Breakeven/WAIT trades get a tiny negative nudge so the agent does not
          learn to do nothing as a safe escape hatch.

        Returns a reward in roughly [-2.0, +2.0] so the Q-network has headroom
        to differentiate quality trades within the same sign.
        """
        current_pf = gross_profits / gross_losses if gross_losses > 0.0 else 1.0

        if profit > 0.0:
            # Base: normalised contribution to gross profit
            base = profit / 100.0
            # Amplify slightly when PF is already good — reinforce what works
            pf_boost = min(current_pf, 3.0) / 3.0  # caps at ×1 when PF ≥ 3
            reward = base * (1.0 + 0.5 * pf_boost)
        elif profit < 0.0:
            base = profit / 100.0
            # Deficit penalty: if PF < 1 we are losing money overall — punish harder
            pf_deficit = max(0.0, 1.0 - current_pf)   # 0 when PF ≥ 1, grows as PF drops
            penalty_multiplier = 1.0 + 2.0 * pf_deficit  # up to ×3 when PF → 0
            reward = base * penalty_multiplier
        else:
            # Breakeven / WAIT action — small nudge to prefer real signals
            reward = -0.05

        # Clip to [-2.0, 2.0] — wider than before to preserve gradient signal
        return max(-2.0, min(2.0, reward))

    def populate_replay_buffer(self, trade_memory_db):
        """Populates the in-memory experience replay buffer from database trades."""
        trades = trade_memory_db.get_recent_trades(limit=self.replay_buffer.capacity)

        # Pre-compute global gross profits/losses for PF-aware reward shaping
        profits_list = [float(t.get('profit_usd', 0.0) or 0.0) for t in trades]
        gross_profits = sum(p for p in profits_list if p > 0.0)
        gross_losses  = abs(sum(p for p in profits_list if p < 0.0))

        for t in trades:
            state = [
                float(t.get('regime_score', 0.0) or 0.0),
                float(t.get('structure_score', 0.0) or 0.0),
                float(t.get('entry_score', 0.0) or 0.0),
                float(t.get('rsi', 50.0) or 50.0),
                float(t.get('adx', 20.0) or 20.0),
                float(t.get('atr', 0.0) or 0.0),
                float(t.get('spread', 0.0) or 0.0),
                float(t.get('recent_wins', 0.0) or 0.0),
                float(t.get('recent_losses', 0.0) or 0.0),
            ]
            
            # Next state: we construct a mock next state
            next_state = [x * 0.98 for x in state]
            
            direction = t.get('direction', 'BUY')
            profit = float(t.get('profit_usd', 0.0) or 0.0)
            
            action_idx = 0
            if profit != 0:
                action_idx = 1 if direction == 'BUY' else 2

            # --- PF-AWARE REWARD (replaces flat profit/100 clip) ---
            reward = self._compute_pf_aware_reward(profit, gross_profits, gross_losses)
            
            result = "WIN" if profit > 0 else ("LOSS" if profit < 0 else "FLAT")
            classification = t.get('tags', '')
            confidence = float(t.get('confidence', 0.0) or 0.0)
            risk = float(t.get('sl_points', 0.0) or 0.0)
            regime = t.get('regime_type', '')

            self.replay_buffer.push(
                state, action_idx, reward, next_state, result, classification, confidence, risk, regime
            )

    def calculate_policy_metrics(self) -> dict:
        """
        Calculate metrics over the current experience buffer to evaluate the policy.
        """
        if self.replay_buffer.size() == 0:
            return {
                "win_rate": 0.0,
                "avg_reward": 0.0,
                "profit_factor": 1.0,
                "max_drawdown": 0.0,
                "reward_to_risk": 1.0,
                "learning_stability": 1.0,
                "policy_improvement": 0.0
            }
            
        rewards = [item["reward"] for item in self.replay_buffer.buffer]
        wins = [1 for item in self.replay_buffer.buffer if item["result"] == "WIN"]
        losses = [1 for item in self.replay_buffer.buffer if item["result"] == "LOSS"]
        
        win_rate = len(wins) / (len(wins) + len(losses)) if (len(wins) + len(losses)) > 0 else 0.0
        avg_reward = sum(rewards) / len(rewards)
        
        gross_profits = sum([item["reward"] for item in self.replay_buffer.buffer if item["reward"] > 0])
        gross_losses = abs(sum([item["reward"] for item in self.replay_buffer.buffer if item["reward"] < 0]))
        profit_factor = gross_profits / gross_losses if gross_losses > 0 else 1.0
        
        cum_rewards = []
        curr = 0
        for r in rewards:
            curr += r
            cum_rewards.append(curr)
        max_dd = 0.0
        peak = -99999.0
        for val in cum_rewards:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
                
        risks = [item["risk"] for item in self.replay_buffer.buffer if item["risk"] > 0]
        avg_risk = sum(risks) / len(risks) if risks else 1.0
        avg_win_reward = sum([item["reward"] for item in self.replay_buffer.buffer if item["reward"] > 0]) / len(wins) if wins else 0.0
        reward_to_risk = (avg_win_reward * 100.0) / avg_risk if avg_risk > 0 else 1.0

        reward_var = float(np.var(rewards)) if len(rewards) > 1 else 0.0
        learning_stability = 1.0 / (1.0 + reward_var)

        policy_improvement = win_rate - 0.50

        return {
            "win_rate": win_rate * 100.0,
            "avg_reward": avg_reward,
            "profit_factor": profit_factor,
            "max_drawdown": max_dd,
            "reward_to_risk": reward_to_risk,
            "learning_stability": learning_stability,
            "policy_improvement": policy_improvement
        }

    def train_on_history(self, trade_memory_db, epochs=50, lr=0.005) -> dict:
        """
        Trains the Q-network on historical trades stored in trade_memory.db.

        Objective: maximise profit factor (gross_profit / gross_loss) rather than
        raw accuracy or mean reward.

        Loss = MSE(Q_chosen, shaped_reward)
             + PF_REGULARISATION_WEIGHT * relu(PF_TARGET - current_pf)

        The regularisation term adds a penalty whenever the policy's implied profit
        factor over the replay buffer drops below PF_TARGET, directly pushing
        the network toward Q-values that favour high-profit-factor actions.
        """
        PF_TARGET = 1.5          # minimum PF we want the policy to sustain
        PF_REG_WEIGHT = 0.25     # how hard to push when PF < PF_TARGET

        self.populate_replay_buffer(trade_memory_db)
        if self.replay_buffer.size() < 20:
            logger.warning(f"Not enough trades in replay buffer: {self.replay_buffer.size()}/20")
            return {"status": "insufficient_data"}

        # Extract states, actions, rewards from replay buffer
        states = [item["state"] for item in self.replay_buffer.buffer]
        actions = [item["action"] for item in self.replay_buffer.buffer]
        rewards = [item["reward"] for item in self.replay_buffer.buffer]

        # Convert to PyTorch tensors
        states_tensor = torch.tensor(states, dtype=torch.float32).to(self.device)
        actions_tensor = torch.tensor(actions, dtype=torch.long).to(self.device)
        rewards_tensor = torch.tensor(rewards, dtype=torch.float32).to(self.device)

        # Pre-compute current PF for logging
        gross_profits = sum(r for r in rewards if r > 0.0)
        gross_losses  = abs(sum(r for r in rewards if r < 0.0))
        current_pf    = gross_profits / gross_losses if gross_losses > 0.0 else 1.0
        logger.info(f"[RL] Replay buffer PF before training: {current_pf:.3f}")

        # Loss and Optimizer
        self.model.train()
        optimizer = optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        logger.info(f"[RL] Training Q-Network on {len(states)} replay buffer samples for {epochs} epochs...")
        logger.info(f"[RL] Optimising for Profit Factor >= {PF_TARGET} (reg weight={PF_REG_WEIGHT})")

        last_loss = 0.0
        for epoch in range(epochs):
            optimizer.zero_grad()
            q_values = self.model(states_tensor)

            # Get Q-value for the action that was actually taken
            gathered_q = q_values.gather(1, actions_tensor.unsqueeze(1)).squeeze(1)

            # Base TD loss
            td_loss = criterion(gathered_q, rewards_tensor)

            # ── Profit-Factor Regularisation ──────────────────────────────────
            # Compute implied PF from the current Q-values the network assigns
            # to winning vs losing actions.  We use the gathered Q-values as a
            # differentiable proxy: positive Q → the net "values" this trade as
            # a win; negative Q → as a loss.
            pos_q = torch.relu(gathered_q)
            neg_q = torch.relu(-gathered_q)
            implied_gross_profit = pos_q.sum() + 1e-8
            implied_gross_loss   = neg_q.sum()  + 1e-8
            implied_pf           = implied_gross_profit / implied_gross_loss
            # Penalty fires whenever implied PF is below target (relu ensures 0 when PF ≥ target)
            pf_penalty = torch.relu(torch.tensor(PF_TARGET, dtype=torch.float32).to(self.device) - implied_pf)

            loss = td_loss + PF_REG_WEIGHT * pf_penalty
            loss.backward()
            optimizer.step()

            last_loss = loss.item()
            if (epoch + 1) % 10 == 0:
                logger.info(f"  Epoch {epoch+1}/{epochs} - RL Loss: {td_loss.item():.4f} | PF Penalty: {pf_penalty.item():.4f} | Implied PF: {implied_pf.item():.3f}")

        # Save model weights
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        torch.save(self.model.state_dict(), self.model_path)
        self.model.eval()

        logger.info(f"[OK] RL Q-Network training complete. Model saved. Final loss: {last_loss:.4f}")
        return {"status": "success", "loss": last_loss, "samples": len(states)}
