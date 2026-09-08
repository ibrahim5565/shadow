import os
import json
import logging
import sqlite3
from datetime import datetime
import numpy as np
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    optim = None
    TORCH_AVAILABLE = False
from typing import Dict, Any, Optional, List, Tuple


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


_nn_module = nn.Module if TORCH_AVAILABLE else object

class AegisQNetwork(_nn_module):
    """
    Q-Network for Aegis RL Agent.
    Maps state features to Q-values for actions [WAIT, BUY, SELL].
    """
    def __init__(self, input_dim=9, hidden_dim=64, output_dim=3):
        if TORCH_AVAILABLE:
            super().__init__()
            self.network = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, output_dim)
            )
        else:
            self.network = None

    def forward(self, x):
        return self.network(x)


class AegisRLAgent:
    def __init__(self, model_path=None, state_dim=None, action_dim=None, input_dim=None, output_dim=None):
        self.model_path = model_path or MODEL_PATH
        if TORCH_AVAILABLE:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
        
        in_dim = input_dim or state_dim or 9
        out_dim = output_dim or action_dim or 3
        self.model = AegisQNetwork(input_dim=in_dim, output_dim=out_dim)
        self.replay_buffer = ReplayBuffer()
        
        if TORCH_AVAILABLE and os.path.exists(self.model_path):
            try:
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                logger.info(f"[RL] Aegis RL Agent loaded from {self.model_path}")
            except Exception as e:
                logger.error(f"Failed to load RL agent weights: {e}")
        else:
            logger.warning(f"No RL weights found at {self.model_path}. Starting with default parameters.")
            
        if TORCH_AVAILABLE and hasattr(self.model, "to"):
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

        if not TORCH_AVAILABLE:
            return [0.33, 0.33, 0.34]

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
    def _compute_realized_rr_reward(profit_usd: float, sl_points: float,
                                     lot: float, pip_val_per_lot: float = 1.0) -> float:
        """
        Realized R:R reward shaping.

        Philosophy:
        - Reward = profit_usd / dollar_risk_at_entry
        - dollar_risk = sl_pts * pip_val_per_lot * (lot / 0.01)
        - Positive R:R: trade paid more than it risked
        - Negative R:R: trade paid less than it risked (stop-out)
        - Zero / WAIT: small negative nudge

        This is derived ENTIRELY from realized trade outcomes in trade_memory.db.
        No synthetic PF, no implied Q-value ratios.

        When sl_points = 0 (pre-fix trades with unknown risk), we use a
        DEFAULT of 60pts (the ATR-normal SL going forward) but flag the
        trade as uncertain_risk = True for down-weighting in the loss.

        Returns reward in [-3.0, +3.0].
        """
        DEFAULT_SL_PTS = 60.0  # ATR-normal floor going forward
        UNCERTAIN = sl_points <= 0

        eff_sl_pts = sl_points if sl_points > 0 else DEFAULT_SL_PTS
        eff_lot    = lot if lot > 0 else 0.01

        dollar_risk = eff_sl_pts * pip_val_per_lot * (eff_lot / 0.01)

        if dollar_risk > 0:
            reward = profit_usd / dollar_risk
        else:
            reward = 0.0

        reward = max(-3.0, min(3.0, reward))
        return reward, UNCERTAIN

    def populate_replay_buffer(self, trade_memory_db):
        """Populates the in-memory experience replay buffer from database trades."""
        trades = trade_memory_db.get_recent_trades(limit=self.replay_buffer.capacity)

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

            # Next state: mock decay
            next_state = [x * 0.98 for x in state]

            direction  = t.get('direction', 'BUY')
            profit_usd = float(t.get('profit_usd', 0.0) or 0.0)
            sl_pts     = float(t.get('sl_points', 0.0) or 0.0)
            lot        = float(t.get('lot_size', 0.01) or 0.01)

            # Realized R:R reward — no synthetic PF term
            reward, uncertain_risk = self._compute_realized_rr_reward(
                profit_usd, sl_pts, lot, pip_val_per_lot=1.0
            )

            action_idx = 0
            if profit_usd != 0:
                action_idx = 1 if direction == 'BUY' else 2

            result         = "WIN" if profit_usd > 0 else ("LOSS" if profit_usd < 0 else "FLAT")
            classification = t.get('tags', '')
            confidence     = float(t.get('confidence', 0.0) or 0.0)
            risk           = sl_pts
            regime         = t.get('regime_type', '')

            self.replay_buffer.push(
                state, action_idx, reward, next_state, result, classification,
                confidence, risk, regime
            )
            # Tag uncertain-risk for training
            if self.replay_buffer.buffer:
                self.replay_buffer.buffer[-1]["uncertain_risk"] = uncertain_risk


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

        Objective: maximise realized R:R (profit_usd / dollar_risk_at_entry).

        Loss = weighted MSE(Q_chosen, realized_rr_reward)

        Uncertain-risk trades (sl_points=0, pre-fix era) are down-weighted
        by 0.5 in the loss so the training signal comes primarily from the
        860 trades with real SL data.

        No PF regularisation term — the only PF/win-rate numbers used to
        judge success come from backtest on held-out real data.
        """
        self.populate_replay_buffer(trade_memory_db)
        if self.replay_buffer.size() < 20:
            logger.warning(f"Not enough trades in replay buffer: {self.replay_buffer.size()}/20")
            return {"status": "insufficient_data"}

        # Extract states, actions, rewards, and uncertainty flags
        states         = [item["state"]         for item in self.replay_buffer.buffer]
        actions        = [item["action"]         for item in self.replay_buffer.buffer]
        rewards        = [item["reward"]         for item in self.replay_buffer.buffer]
        uncertain_mask = [item.get("uncertain_risk", False) for item in self.replay_buffer.buffer]

        # Weight: 0.5 for uncertain-risk trades, 1.0 for real-risk trades
        sample_weights = [0.5 if u else 1.0 for u in uncertain_mask]
        n_real    = sum(1 for u in uncertain_mask if not u)
        n_uncert  = sum(1 for u in uncertain_mask if u)

        # Convert to tensors
        states_tensor   = torch.tensor(states,         dtype=torch.float32).to(self.device)
        actions_tensor  = torch.tensor(actions,        dtype=torch.long).to(self.device)
        rewards_tensor  = torch.tensor(rewards,        dtype=torch.float32).to(self.device)
        weights_tensor  = torch.tensor(sample_weights, dtype=torch.float32).to(self.device)

        # Log before-training composition
        real_rewards = [r for r, u in zip(rewards, uncertain_mask) if not u]
        real_gp = sum(r for r in real_rewards if r > 0)
        real_gl = abs(sum(r for r in real_rewards if r < 0))
        logger.info(f"[RL] Replay buffer: {len(states)} trades | real-risk: {n_real} | uncertain: {n_uncert}")
        logger.info(f"[RL] Real-risk trades reward PF proxy: {real_gp/real_gl:.3f}" if real_gl > 0 else "[RL] No real-risk loss trades")

        # Training
        self.model.train()
        optimizer = optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss(reduction='none')   # per-sample loss for weighting

        logger.info(f"[RL] Training Q-Network on {len(states)} samples for {epochs} epochs (realized R:R objective)...")

        last_loss = 0.0
        for epoch in range(epochs):
            optimizer.zero_grad()
            q_values = self.model(states_tensor)

            # Q-value for the action taken
            gathered_q = q_values.gather(1, actions_tensor.unsqueeze(1)).squeeze(1)

            # Weighted MSE — down-weight uncertain-risk trades
            per_sample_loss = criterion(gathered_q, rewards_tensor)
            loss = (per_sample_loss * weights_tensor).mean()

            loss.backward()
            optimizer.step()

            last_loss = loss.item()
            if (epoch + 1) % 10 == 0:
                logger.info(f"  Epoch {epoch+1}/{epochs} - Weighted RL Loss: {last_loss:.4f}")

        # Save model weights
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        torch.save(self.model.state_dict(), self.model_path)
        self.model.eval()

        logger.info(f"[OK] RL Q-Network training complete. Model saved. Final weighted loss: {last_loss:.4f}")
        return {"status": "success", "loss": last_loss, "samples": len(states),
                "real_risk_trades": n_real, "uncertain_risk_trades": n_uncert}

    def get_engine_weights(self, tier: str = "scalp") -> Dict[str, float]:
        """
        SECTION 4 — RL LOOP (Parameter tuning, NOT live voting)
        Returns current tuned engine weights for consensus aggregation.
        """
        weights_file = os.path.join(BASE_DIR, "data", "engine_weights.json")
        default_weights = {"quant": 0.25, "ml_ensemble": 0.25, "omega": 0.25, "kronos": 0.25}
        
        if not os.path.exists(weights_file):
            return default_weights

        try:
            with open(weights_file, "r") as f:
                data = json.load(f)
            return data.get(tier, data.get("default", default_weights))
        except Exception:
            return default_weights

    def update_engine_weights(self, trade_outcome: dict):
        """
        SECTION 4 — RL Parameter-Tuning Update
        Consumes outcome of a closed trade (win/loss, pnl, engine votes, tier).
        Adjusts engine weights dynamically based on historical accuracy per tier.
        
        CAUSALITY FIX: This method is now BLOCKED during live trading to prevent
        using future trade outcomes for current decisions. Updates only occur 
        during dedicated training/analysis phases.
        """
        # Import causality enforcer
        try:
            from brain.causality_enforcer import get_causality_enforcer
            
            # Check if we're in live trading mode
            enforcer = get_causality_enforcer()
            audit_result = enforcer.prevent_live_model_updates("reinforcement_agent", is_live_trading=True)
            
            if not audit_result.passed:
                logger.warning("[CAUSALITY] BLOCKED live engine weight update - use dedicated training phase instead")
                return
        except ImportError:
            logger.warning("[CAUSALITY] Causality enforcer not available, proceeding with update")
        
        # Only proceed if causality check passed (training mode)
        weights_file = os.path.join(BASE_DIR, "data", "engine_weights.json")
        tier = trade_outcome.get("tier", "scalp")
        pnl = trade_outcome.get("profit_usd", 0.0)
        votes = trade_outcome.get("engine_votes", {})
        direction = trade_outcome.get("direction", "BUY").lower()

        current_all = {}
        if os.path.exists(weights_file):
            try:
                with open(weights_file, "r") as f:
                    current_all = json.load(f)
            except Exception:
                pass

        weights = current_all.get(tier, {"quant": 0.25, "ml_ensemble": 0.25, "omega": 0.25, "kronos": 0.25})

        learning_rate = 0.02
        for eng, vote in votes.items():
            if eng in weights:
                v_dir = str(vote.get("direction", "neutral")).lower()
                v_conf = float(vote.get("confidence", 0.5))
                v_correct = (v_dir == direction and pnl > 0) or (v_dir != direction and pnl < 0)

                if v_correct:
                    weights[eng] += learning_rate * v_conf
                else:
                    weights[eng] -= learning_rate * v_conf

        for eng in weights:
            weights[eng] = max(0.10, weights[eng])
        
        tot = sum(weights.values())
        if tot > 0:
            weights = {k: round(v / tot, 4) for k, v in weights.items()}

        current_all[tier] = weights
        current_all["last_updated"] = datetime.now().isoformat()

        try:
            os.makedirs(os.path.dirname(weights_file), exist_ok=True)
            with open(weights_file, "w") as f:
                json.dump(current_all, f, indent=2)
            logger.info(f"[RL-TUNER] Updated engine weights for tier '{tier}': {weights}")
        except Exception as e:
            logger.error(f"[RL-TUNER] Failed to save engine weights: {e}")

    # ── Pattern Consensus Architecture: RL as Meta-Weighter ──────────────────
    #
    # DESIGN RATIONALE:
    # The RL agent previously emitted a raw directional vote (BUY/SELL/WAIT)
    # based on Q-values. This is now REMOVED from the consensus voting ring.
    # Reason: the RL's state features may include realized trade outcomes
    # (win/loss streaks, equity curve) which are valid, but its directional
    # Q-values could drift to always-BUY or always-SELL in thin training data,
    # introducing a systematic bias that is hard to audit.
    #
    # New role: the RL learns WHICH ENGINES to weight more in which regime,
    # based on realized post-trade outcomes. This is additive (boosts/reduces
    # conviction weighting) without overriding the 5/6 directional consensus.
    # ─────────────────────────────────────────────────────────────────────────

    _WEIGHTS_FILE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "rl_engine_weights.json"
    )

    _DEFAULT_ENGINE_WEIGHTS = {
        "smc": 1.0,
        "kronos": 1.0,
        "quant_feature_engine": 1.0,
        "ml_ensemble": 1.0,
        "omega": 1.0,
        "unified_brain": 1.0,
    }

    def get_engine_weights(self, regime: str = "UNKNOWN", recent_outcomes: Optional[List[Dict]] = None) -> Dict[str, float]:
        """
        Returns per-engine conviction multipliers [0.5, 2.0] for the current regime.

        The Unified Brain applies these weights to each engine's conviction score
        before the 5/6 directional vote count. They do NOT change the direction;
        they modulate how much weight a marginal conviction carries in sizing.

        These weights are learned from realized post-trade outcomes by
        update_engine_weights() in train_reinforcement.py.

        Returns equal weights (1.0) until RL has accumulated enough outcome data.

        Parameters
        ----------
        regime:           Current market regime string (e.g. "TRENDING_UP", "RANGING")
        recent_outcomes:  Optional list of recent trade outcome dicts for online adjustment
        """
        try:
            weights_file = self._WEIGHTS_FILE_PATH
            if not os.path.exists(weights_file):
                return dict(self._DEFAULT_ENGINE_WEIGHTS)

            with open(weights_file, "r") as f:
                all_weights = json.load(f)

            # Try regime-specific weights first, then fall back to "global"
            regime_key = regime.upper().replace(" ", "_") if regime else "UNKNOWN"
            tier_weights = all_weights.get(regime_key, all_weights.get("global", {}))

            result = dict(self._DEFAULT_ENGINE_WEIGHTS)
            for engine, w in tier_weights.items():
                if engine in result:
                    # Clamp to [0.5, 2.0] for safety
                    result[engine] = max(0.5, min(2.0, float(w)))

            return result

        except Exception as e:
            logger.warning(f"[RL] get_engine_weights error: {e}, using defaults")
            return dict(self._DEFAULT_ENGINE_WEIGHTS)

    def predict_vote(self, snapshot) -> "EngineVote":
        """
        The RL Agent does NOT cast a directional vote in the consensus ring.
        It returns a WAIT vote with conviction=0.0.

        Its contribution is via get_engine_weights() — the Unified Brain calls
        that separately to modulate per-engine conviction scores before
        the directional count.

        This method exists so the Unified Brain can uniformly call
        engine.predict_vote(snapshot) on all 7 engines without special-casing the RL.
        """
        from brain.engine_vote import make_wait_vote
        return make_wait_vote(
            "rl_agent",
            "RL Agent is meta-weighter only; use get_engine_weights() for regime weights",
            signal_time=snapshot.timestamp,
        )
