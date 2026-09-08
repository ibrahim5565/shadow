import os
import json
import logging
import sqlite3
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from datetime import datetime
from typing import Tuple, List, Optional

logger = logging.getLogger("aegis.offline_rl_agent")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFFLINE_MODEL_PATH = os.path.join(BASE_DIR, "models", "aegis_rl_offline.pt")

class AegisOfflineQNetwork(nn.Module):
    """
    Q-Network for Aegis Offline RL Agent.
    Maps 9 state features to Q-values for 8 discrete actions:
    [WAIT, ENTER_LONG, ENTER_SHORT, HOLD, EXIT, REDUCE_POSITION, SCALE_IN, SCALE_OUT]
    """
    def __init__(self, input_dim=9, hidden_dim=128, output_dim=8):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, x):
        return self.network(x)

class AegisOfflineRLAgent:
    """
    Offline/Batch Reinforcement Learning Agent using Conservative Q-Learning (CQL).
    Trained strictly on logged historical data.
    """
    ACTIONS = [
        "WAIT", "ENTER_LONG", "ENTER_SHORT", "HOLD",
        "EXIT", "REDUCE_POSITION", "SCALE_IN", "SCALE_OUT"
    ]

    def __init__(self, model_path=None, state_dim=None, action_dim=None, input_dim=None, output_dim=None):
        self.model_path = model_path or OFFLINE_MODEL_PATH
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        in_dim = input_dim or state_dim or 9
        out_dim = output_dim or action_dim or 8
        self.model = AegisOfflineQNetwork(input_dim=in_dim, output_dim=out_dim)
        self._fitted = False
        
        if os.path.exists(self.model_path):
            try:
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                self.model.eval()
                self._fitted = True
                logger.info(f"[Offline RL] Loaded agent from {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load offline RL agent weights: {e}")
        else:
            logger.warning(f"No offline RL weights found at {self.model_path}. Agent needs training.")
            
        self.model.to(self.device)
        self.model.eval()

    def get_action_q_values(self, state_features: list) -> list:
        if len(state_features) < 9:
            state_features = state_features + [0.0] * (9 - len(state_features))
        elif len(state_features) > 9:
            state_features = state_features[:9]

        with torch.no_grad():
            x = torch.tensor([state_features], dtype=torch.float32).to(self.device)
            q_values = self.model(x)
            return q_values.cpu().numpy()[0].tolist()

    def predict_raw_action(self, state_features: list) -> Tuple[str, int]:
        """Returns the full 8-action prediction name and confidence score."""
        if not self._fitted:
            return "WAIT", 0
        q_vals = self.get_action_q_values(state_features)
        action_idx = int(np.argmax(q_vals))
        
        exp_q = np.exp(q_vals - np.max(q_vals))
        softmax_probs = exp_q / np.sum(exp_q)
        confidence = int(softmax_probs[action_idx] * 100)
        return self.ACTIONS[action_idx], confidence

    def predict_action(self, state_features: list) -> Tuple[str, int]:
        """
        Adapts the 8-action prediction to the 3-action interface expected by the entry loop:
        ENTER_LONG -> "BUY"
        ENTER_SHORT -> "SELL"
        Others -> "WAIT"
        """
        raw_act, conf = self.predict_raw_action(state_features)
        if raw_act == "ENTER_LONG":
            return "BUY", conf
        elif raw_act == "ENTER_SHORT":
            return "SELL", conf
        else:
            return "WAIT", conf

    @staticmethod
    def _compute_cql_safe_reward(profit: float, state_features: list, num_trades_today: int) -> float:
        """
        Computes safe reward shaping with:
        - Excessive trade frequency / churn penalty
        - Hard limits encoded directly in policy optimization
        """
        from config.quant_x_config import QX
        
        # Base profit reward normalized
        reward = profit / 100.0 if profit != 0.0 else -0.02
        
        # Shape reward to penalize excessive trade frequency (churn)
        churn_penalty = float(QX.get("cql_churn_penalty") or 0.05)
        max_trades = int(QX.get("cql_max_trades_per_day") or 20)
        if num_trades_today > max_trades:
            reward -= churn_penalty * (num_trades_today - max_trades)

        # Encoded hard constraints: penalize taking new positions when risk is high
        spread = state_features[6]
        if spread > 30.0:
            reward -= 0.5  # High spread penalty

        return reward

    def train_offline_cql(self, db_path: str, epochs: int = 100, lr: float = 0.001) -> dict:
        """
        Trains the network offline using Conservative Q-Learning (CQL) discrete loss:
        CQL Loss = standard TD MSE loss + alpha * (logsumexp(Q) - Q(s,a))
        """
        from config.quant_x_config import QX
        alpha = float(QX.get("cql_alpha") or 1.0)
        
        if not os.path.exists(db_path):
            logger.error(f"Database not found at {db_path}")
            return {"status": "error", "reason": "database_not_found"}

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM trades WHERE exit_time IS NOT NULL").fetchall()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to read from db: {e}")
            return {"status": "error", "reason": str(e)}

        if len(rows) < 50:
            logger.warning(f"Insufficient trade history for offline RL training: {len(rows)}/50")
            return {"status": "insufficient_data"}

        # Build states, actions, rewards
        states = []
        actions = []
        rewards = []
        
        # Simple date counters for churn metrics
        trades_per_day = {}
        for r in rows:
            date_str = r['entry_time'][:10]
            trades_per_day[date_str] = trades_per_day.get(date_str, 0) + 1

        for r in rows:
            state = [
                float(r['regime_score'] or 0.0),
                float(r['structure_score'] or 0.0),
                float(r['entry_score'] or 0.0),
                float(r['rsi'] or 50.0),
                float(r['adx'] or 20.0),
                float(r['atr'] or 0.0),
                float(r['spread'] or 0.0),
                float(r['recent_wins'] or 0.0),
                float(r['recent_losses'] or 0.0),
            ]
            states.append(state)
            
            direction = r['direction']
            profit = float(r['profit_usd'] or 0.0)
            
            if profit == 0.0:
                action_idx = 0  # WAIT
            else:
                action_idx = 1 if direction == 'BUY' else 2  # ENTER_LONG / ENTER_SHORT

            date_key = r['entry_time'][:10]
            num_trades_today = trades_per_day.get(date_key, 0)
            
            reward = self._compute_cql_safe_reward(profit, state, num_trades_today)
            actions.append(action_idx)
            rewards.append(reward)

        # Conversion to Tensors
        states_t = torch.tensor(states, dtype=torch.float32).to(self.device)
        actions_t = torch.tensor(actions, dtype=torch.long).to(self.device)
        rewards_t = torch.tensor(rewards, dtype=torch.float32).to(self.device)

        self.model.train()
        optimizer = optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        logger.info(f"[CQL] Training Offline RL on {len(states)} transitions for {epochs} epochs (alpha={alpha})...")

        for epoch in range(epochs):
            optimizer.zero_grad()
            q_values = self.model(states_t)
            
            # Standard MSE Loss
            gathered_q = q_values.gather(1, actions_t.unsqueeze(1)).squeeze(1)
            td_loss = criterion(gathered_q, rewards_t)
            
            # CQL Regularizer penalty
            logsumexp_q = torch.logsumexp(q_values, dim=1)
            cql_reg = torch.mean(logsumexp_q - gathered_q)
            
            loss = td_loss + alpha * cql_reg
            loss.backward()
            optimizer.step()

        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        torch.save(self.model.state_dict(), self.model_path)
        self.model.eval()
        self._fitted = True
        logger.info("[CQL] Offline training complete.")
        return {"status": "success", "final_loss": float(loss.item())}
