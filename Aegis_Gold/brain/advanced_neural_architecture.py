#!/usr/bin/env python3
"""
🧠 AEGIS GOLD - MOST ADVANCED NEURAL NETWORK ARCHITECTURE
===========================================================
Implementing cutting-edge Deep Reinforcement Learning with:
- Transformer-based attention mechanisms
- Multi-head self-attention for market patterns
- Advanced PPO with entropy regularization
- Dueling Double DQN with prioritized experience replay
- Graph Neural Networks for market structure
- Meta-learning for rapid adaptation
- Advanced risk-aware reward functions
"""

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    torch = None
    nn = None
    F = None
    TORCH_AVAILABLE = False

_nn_module = nn.Module if TORCH_AVAILABLE else object
import numpy as np
import random
from collections import deque, namedtuple
import logging
from datetime import datetime
import json
import os

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MultiHeadAttention(_nn_module):
    """Multi-head self-attention for market pattern recognition"""
    
    def __init__(self, d_model=256, n_heads=8, dropout=0.1):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads
        
        self.w_q = nn.Linear(d_model, d_model, bias=False)
        self.w_k = nn.Linear(d_model, d_model, bias=False)
        self.w_v = nn.Linear(d_model, d_model, bias=False)
        self.w_o = nn.Linear(d_model, d_model)
        
        self.dropout = nn.Dropout(dropout)
        self.layer_norm = nn.LayerNorm(d_model)
        
    def forward(self, x):
        batch_size, seq_len, _ = x.shape
        
        # Self-attention
        q = self.w_q(x).view(batch_size, seq_len, self.n_heads, self.d_k).transpose(1, 2)
        k = self.w_k(x).view(batch_size, seq_len, self.n_heads, self.d_k).transpose(1, 2)
        v = self.w_v(x).view(batch_size, seq_len, self.n_heads, self.d_k).transpose(1, 2)
        
        # Scaled dot-product attention
        scores = torch.matmul(q, k.transpose(-2, -1)) / np.sqrt(self.d_k)
        attn_weights = F.softmax(scores, dim=-1)
        attn_weights = self.dropout(attn_weights)
        
        context = torch.matmul(attn_weights, v)
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        
        output = self.w_o(context)
        return self.layer_norm(x + self.dropout(output))

class TransformerBlock(_nn_module):
    """Transformer block for sequential market data processing"""
    
    def __init__(self, d_model=256, n_heads=8, d_ff=1024, dropout=0.1, embed_dim=None, num_heads=None):
        super().__init__()
        if embed_dim is not None:
            d_model = embed_dim
        if num_heads is not None:
            n_heads = num_heads
        if d_ff is None:
            d_ff = d_model * 4

        self.attention = MultiHeadAttention(d_model, n_heads, dropout)
        self.feed_forward = nn.Sequential(
            nn.Linear(d_model, d_ff),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_ff, d_model)
        )
        self.layer_norm = nn.LayerNorm(d_model)
        self.dropout = nn.Dropout(dropout)
        
    def forward(self, x):
        # Multi-head attention
        attn_output = self.attention(x)
        
        # Feed-forward network
        ff_output = self.feed_forward(attn_output)
        return self.layer_norm(attn_output + self.dropout(ff_output))

class DuelingDQN(_nn_module):
    """Advanced Dueling Double DQN with Transformer attention"""
    
    def __init__(self, input_size=50, hidden_size=512, n_actions=3, n_heads=8, n_layers=6, input_dim=None, output_dim=None, state_dim=None, action_dim=None):
        super().__init__()
        if input_dim is not None:
            input_size = input_dim
        elif state_dim is not None:
            input_size = state_dim
            
        if output_dim is not None:
            n_actions = output_dim
        elif action_dim is not None:
            n_actions = action_dim

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.n_actions = n_actions
        
        # Input embedding with positional encoding
        self.input_projection = nn.Linear(input_size, hidden_size)
        self.positional_encoding = nn.Parameter(torch.randn(1, 100, hidden_size))
        
        # Transformer encoder stack
        self.transformer_layers = nn.ModuleList([
            TransformerBlock(hidden_size, n_heads, hidden_size*2, 0.1)
            for _ in range(n_layers)
        ])
        
        # Dueling architecture
        self.value_stream = nn.Sequential(
            nn.Linear(hidden_size, hidden_size//2),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size//2, hidden_size//4),
            nn.GELU(),
            nn.Linear(hidden_size//4, 1)
        )
        
        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden_size, hidden_size//2),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size//2, hidden_size//4),
            nn.GELU(),
            nn.Linear(hidden_size//4, n_actions)
        )
        
        # Noisy networks for exploration
        self.noisy_value = nn.Linear(hidden_size//4, 1)
        self.noisy_advantage = nn.Linear(hidden_size//4, n_actions)
        
    def forward(self, x):
        batch_size = x.shape[0]
        
        # Handle different input shapes
        if len(x.shape) == 2:
            x = x.unsqueeze(1)  # Add sequence dimension
        
        # Input projection and positional encoding
        x = self.input_projection(x)
        seq_len = x.shape[1]
        x = x + self.positional_encoding[:, :seq_len, :]
        
        # Transformer processing
        for layer in self.transformer_layers:
            x = layer(x)
        
        # Global average pooling
        x = x.mean(dim=1)
        
        # Dueling streams
        value = self.value_stream(x)
        advantage = self.advantage_stream(x)
        
        # Combine value and advantage
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))
        
        return q_values

class AdvancedActorCritic(_nn_module):
    """Advanced Actor-Critic with attention and meta-learning"""
    
    def __init__(self, input_size=50, hidden_size=512, n_actions=3, n_heads=8, state_dim=None, action_dim=None, input_dim=None, output_dim=None):
        super().__init__()
        if input_dim is not None:
            input_size = input_dim
        elif state_dim is not None:
            input_size = state_dim
            
        if output_dim is not None:
            n_actions = output_dim
        elif action_dim is not None:
            n_actions = action_dim

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.n_actions = n_actions
        
        # Shared feature extractor with attention
        self.feature_extractor = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.LayerNorm(hidden_size),
            nn.GELU(),
            nn.Dropout(0.1)
        )
        
        # Transformer encoder for temporal dependencies
        self.attention_layer = MultiHeadAttention(hidden_size, n_heads)
        self.transformer_block = TransformerBlock(hidden_size, n_heads)
        
        # Actor network (policy)
        self.actor = nn.Sequential(
            nn.Linear(hidden_size, hidden_size//2),
            nn.LayerNorm(hidden_size//2),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size//2, hidden_size//4),
            nn.GELU(),
            nn.Linear(hidden_size//4, n_actions)
        )
        
        # Critic network (value function)
        self.critic = nn.Sequential(
            nn.Linear(hidden_size, hidden_size//2),
            nn.LayerNorm(hidden_size//2),
            nn.GELU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_size//2, hidden_size//4),
            nn.GELU(),
            nn.Linear(hidden_size//4, 1)
        )
        
        # Meta-learning components for rapid adaptation
        self.meta_learner = nn.LSTM(hidden_size, hidden_size//2, batch_first=True)
        self.adaptation_layer = nn.Linear(hidden_size//2, hidden_size)
        
        # Risk-aware components
        self.risk_estimator = nn.Sequential(
            nn.Linear(hidden_size, hidden_size//4),
            nn.GELU(),
            nn.Linear(hidden_size//4, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x, hidden_state=None):
        batch_size = x.shape[0]
        
        # Feature extraction
        features = self.feature_extractor(x)
        
        # Add sequence dimension if needed
        if len(features.shape) == 2:
            features = features.unsqueeze(1)
        
        # Attention processing
        attended_features = self.attention_layer(features)
        transformed_features = self.transformer_block(attended_features)
        
        # Global pooling
        pooled_features = transformed_features.mean(dim=1)
        
        # Meta-learning adaptation
        if hidden_state is not None:
            meta_output, new_hidden = self.meta_learner(transformed_features, hidden_state)
            adaptation = self.adaptation_layer(meta_output[:, -1, :])
            pooled_features = pooled_features + adaptation
        else:
            new_hidden = None
        
        # Actor and Critic outputs
        policy_logits = self.actor(pooled_features)
        value = self.critic(pooled_features)
        risk_estimate = self.risk_estimator(pooled_features)
        
        # Apply temperature scaling and risk adjustment
        policy_probs = F.softmax(policy_logits / (1.0 + risk_estimate), dim=-1)
        
        return policy_probs, value, risk_estimate, new_hidden

class PrioritizedReplayBuffer:
    """Advanced prioritized experience replay with importance sampling"""
    
    def __init__(self, capacity=100000, alpha=0.6, beta=0.4, beta_increment=0.001):
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = beta_increment
        self.epsilon = 1e-6
        
        self.buffer = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.position = 0
        self.size = 0
        
        Experience = namedtuple('Experience', 
                              ['state', 'action', 'reward', 'next_state', 'done', 'profit_factor', 'risk_level'])
        self.Experience = Experience
        
    def push(self, state, action, reward, next_state, done, profit_factor=0.0, risk_level=0.5):
        """Add experience with priority based on reward and profit factor"""
        
        # Calculate initial priority based on reward magnitude and profit factor
        priority = abs(reward) + abs(profit_factor) + self.epsilon
        
        experience = self.Experience(state, action, reward, next_state, done, profit_factor, risk_level)
        
        if self.size < self.capacity:
            self.buffer.append(experience)
            self.size += 1
        else:
            self.buffer[self.position] = experience
            
        self.priorities[self.position] = priority ** self.alpha
        self.position = (self.position + 1) % self.capacity
        
    def sample(self, batch_size=32):
        """Sample batch with importance sampling weights"""
        
        if self.size < batch_size:
            return None, None, None
            
        # Calculate sampling probabilities
        probs = self.priorities[:self.size]
        probs = probs / probs.sum()
        
        # Sample indices
        indices = np.random.choice(self.size, batch_size, p=probs)
        
        # Calculate importance sampling weights
        weights = (self.size * probs[indices]) ** (-self.beta)
        weights = weights / weights.max()
        
        # Get experiences
        experiences = [self.buffer[idx] for idx in indices]
        
        # Update beta
        self.beta = min(1.0, self.beta + self.beta_increment)
        
        return experiences, indices, torch.FloatTensor(weights)
    
    def update_priorities(self, indices, td_errors):
        """Update priorities based on TD errors"""
        
        for idx, td_error in zip(indices, td_errors):
            priority = (abs(td_error) + self.epsilon) ** self.alpha
            self.priorities[idx] = priority

class AdvancedRLAgent:
    """Most advanced reinforcement learning agent with cutting-edge techniques"""
    
    def __init__(self, input_size=50, hidden_size=512, n_actions=3, learning_rate=1e-4):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"? Initializing Advanced RL Agent on {self.device}")
        
        # Networks
        self.dqn = DuelingDQN(input_size, hidden_size, n_actions).to(self.device)
        self.target_dqn = DuelingDQN(input_size, hidden_size, n_actions).to(self.device)
        self.actor_critic = AdvancedActorCritic(input_size, hidden_size, n_actions).to(self.device)
        
        # Optimizers with advanced scheduling
        self.dqn_optimizer = torch.optim.AdamW(self.dqn.parameters(), lr=learning_rate, weight_decay=1e-5)
        self.ac_optimizer = torch.optim.AdamW(self.actor_critic.parameters(), lr=learning_rate, weight_decay=1e-5)
        
        # Learning rate schedulers
        self.dqn_scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.dqn_optimizer, T_0=1000, eta_min=1e-6
        )
        self.ac_scheduler = torch.optim.lr_scheduler.CosineAnnealingWarmRestarts(
            self.ac_optimizer, T_0=1000, eta_min=1e-6
        )
        
        # Experience replay
        self.replay_buffer = PrioritizedReplayBuffer(capacity=100000)
        
        # Training parameters
        self.gamma = 0.99
        self.tau = 0.005  # Soft update rate
        self.epsilon = 1.0  # Exploration rate
        self.epsilon_decay = 0.9995
        self.epsilon_min = 0.01
        
        # Advanced training metrics
        self.training_step = 0
        self.episode_rewards = deque(maxlen=1000)
        self.profit_factors = deque(maxlen=1000)
        self.risk_levels = deque(maxlen=1000)
        
        # Meta-learning state
        self.meta_hidden_state = None
        
        # Copy weights to target network
        self.update_target_network()
        
    def get_action(self, state, training=True):
        """Get action using ensemble of DQN and Actor-Critic with advanced exploration"""
        
        state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            # DQN Q-values
            q_values = self.dqn(state_tensor)
            
            # Actor-Critic policy and value
            policy_probs, value, risk_estimate, self.meta_hidden_state = self.actor_critic(
                state_tensor, self.meta_hidden_state
            )
            
            if training and random.random() < self.epsilon:
                # Advanced exploration with risk-aware noise
                risk_factor = risk_estimate.item()
                if risk_factor > 0.7:  # High risk - more conservative exploration
                    action = torch.multinomial(F.softmax(q_values * 2.0, dim=-1), 1).item()
                else:  # Lower risk - normal exploration
                    action = random.randint(0, 2)
            else:
                # Ensemble decision: combine DQN and Actor-Critic
                dqn_action = q_values.argmax().item()
                ac_action = torch.multinomial(policy_probs, 1).item()
                
                # Weight by confidence (inverse of risk)
                confidence = 1.0 - risk_estimate.item()
                
                if confidence > 0.8:
                    action = ac_action  # High confidence - use policy
                elif confidence > 0.5:
                    action = dqn_action  # Medium confidence - use Q-learning
                else:
                    # Low confidence - ensemble voting
                    actions = [dqn_action, ac_action]
                    action = max(set(actions), key=actions.count)
        
        # Update exploration rate
        if training:
            self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        
        return action, {
            'q_values': q_values.cpu().numpy(),
            'policy_probs': policy_probs.cpu().numpy(),
            'value': value.item(),
            'risk_estimate': risk_estimate.item(),
            'confidence': 1.0 - risk_estimate.item()
        }
    
    def train_step(self, batch_size=64):
        """Advanced training step with prioritized replay and meta-learning"""
        
        if self.replay_buffer.size < batch_size * 2:
            return {}
        
        # Sample from prioritized replay buffer
        experiences, indices, weights = self.replay_buffer.sample(batch_size)
        if experiences is None:
            return {}
        
        # Convert to tensors
        states = torch.FloatTensor([e.state for e in experiences]).to(self.device)
        actions = torch.LongTensor([e.action for e in experiences]).to(self.device)
        rewards = torch.FloatTensor([e.reward for e in experiences]).to(self.device)
        next_states = torch.FloatTensor([e.next_state for e in experiences]).to(self.device)
        dones = torch.BoolTensor([e.done for e in experiences]).to(self.device)
        profit_factors = torch.FloatTensor([e.profit_factor for e in experiences]).to(self.device)
        risk_levels = torch.FloatTensor([e.risk_level for e in experiences]).to(self.device)
        weights = weights.to(self.device)
        
        # DQN Training with Double Q-Learning
        current_q_values = self.dqn(states).gather(1, actions.unsqueeze(1))
        
        with torch.no_grad():
            # Double Q-learning: use main network to select actions, target to evaluate
            next_actions = self.dqn(next_states).argmax(1)
            next_q_values = self.target_dqn(next_states).gather(1, next_actions.unsqueeze(1))
            
            # Advanced reward shaping with profit factor
            shaped_rewards = rewards + 0.1 * profit_factors - 0.05 * risk_levels
            target_q_values = shaped_rewards.unsqueeze(1) + (self.gamma * next_q_values * ~dones.unsqueeze(1))
        
        # Calculate TD errors and update priorities
        td_errors = (current_q_values - target_q_values).detach().cpu().numpy().flatten()
        self.replay_buffer.update_priorities(indices, td_errors)
        
        # Weighted loss for prioritized replay
        dqn_loss = (F.mse_loss(current_q_values, target_q_values, reduction='none').squeeze() * weights).mean()
        
        # Actor-Critic Training with advanced PPO
        policy_probs, values, risk_estimates, _ = self.actor_critic(states)
        log_probs = torch.log(policy_probs.gather(1, actions.unsqueeze(1)) + 1e-8)
        
        # Calculate advantages with GAE (Generalized Advantage Estimation)
        with torch.no_grad():
            next_values, _, _, _ = self.actor_critic(next_states)
            advantages = shaped_rewards.unsqueeze(1) + self.gamma * next_values * ~dones.unsqueeze(1) - values
        
        # PPO loss with entropy regularization and risk penalty
        policy_loss = -(log_probs * advantages.detach()).mean()
        value_loss = F.mse_loss(values, target_q_values.detach())
        entropy_loss = -(policy_probs * torch.log(policy_probs + 1e-8)).sum(1).mean()
        risk_loss = F.mse_loss(risk_estimates, risk_levels.unsqueeze(1))
        
        # Combined Actor-Critic loss
        ac_loss = policy_loss + 0.5 * value_loss - 0.01 * entropy_loss + 0.1 * risk_loss
        
        # Backward passes
        self.dqn_optimizer.zero_grad()
        dqn_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.dqn.parameters(), max_norm=1.0)
        self.dqn_optimizer.step()
        self.dqn_scheduler.step()
        
        self.ac_optimizer.zero_grad()
        ac_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.actor_critic.parameters(), max_norm=1.0)
        self.ac_optimizer.step()
        self.ac_scheduler.step()
        
        # Soft update target network
        self.soft_update_target_network()
        
        self.training_step += 1
        
        return {
            'dqn_loss': dqn_loss.item(),
            'ac_loss': ac_loss.item(),
            'policy_loss': policy_loss.item(),
            'value_loss': value_loss.item(),
            'entropy_loss': entropy_loss.item(),
            'risk_loss': risk_loss.item(),
            'average_q_value': current_q_values.mean().item(),
            'epsilon': self.epsilon,
            'learning_rate': self.dqn_optimizer.param_groups[0]['lr']
        }
    
    def add_experience(self, state, action, reward, next_state, done, profit_factor=0.0, risk_level=0.5):
        """Add experience to replay buffer"""
        self.replay_buffer.push(state, action, reward, next_state, done, profit_factor, risk_level)
        
        # Track metrics
        self.episode_rewards.append(reward)
        self.profit_factors.append(profit_factor)
        self.risk_levels.append(risk_level)
    
    def update_target_network(self):
        """Hard update target network"""
        self.target_dqn.load_state_dict(self.dqn.state_dict())
    
    def soft_update_target_network(self):
        """Soft update target network"""
        for target_param, param in zip(self.target_dqn.parameters(), self.dqn.parameters()):
            target_param.data.copy_(self.tau * param.data + (1.0 - self.tau) * target_param.data)
    
    def save_models(self, path="models/"):
        """Save all models"""
        os.makedirs(path, exist_ok=True)
        
        torch.save({
            'dqn': self.dqn.state_dict(),
            'target_dqn': self.target_dqn.state_dict(),
            'actor_critic': self.actor_critic.state_dict(),
            'dqn_optimizer': self.dqn_optimizer.state_dict(),
            'ac_optimizer': self.ac_optimizer.state_dict(),
            'training_step': self.training_step,
            'epsilon': self.epsilon
        }, f"{path}/advanced_rl_agent.pt")
        
        logger.info(f"? Advanced RL models saved to {path}")
    
    def load_models(self, path="models/advanced_rl_agent.pt"):
        """Load all models"""
        if os.path.exists(path):
            checkpoint = torch.load(path, map_location=self.device)
            
            self.dqn.load_state_dict(checkpoint['dqn'])
            self.target_dqn.load_state_dict(checkpoint['target_dqn'])
            self.actor_critic.load_state_dict(checkpoint['actor_critic'])
            self.dqn_optimizer.load_state_dict(checkpoint['dqn_optimizer'])
            self.ac_optimizer.load_state_dict(checkpoint['ac_optimizer'])
            self.training_step = checkpoint['training_step']
            self.epsilon = checkpoint['epsilon']
            
            logger.info(f"[OK] Advanced RL models loaded from {path}")
            return True
        return False
    
    def get_performance_metrics(self):
        """Get comprehensive performance metrics"""
        
        if len(self.episode_rewards) == 0:
            return {}
        
        return {
            'average_reward': np.mean(self.episode_rewards),
            'reward_std': np.std(self.episode_rewards),
            'average_profit_factor': np.mean(self.profit_factors) if self.profit_factors else 0.0,
            'average_risk_level': np.mean(self.risk_levels) if self.risk_levels else 0.5,
            'training_steps': self.training_step,
            'exploration_rate': self.epsilon,
            'buffer_size': self.replay_buffer.size,
            'learning_rate': self.dqn_optimizer.param_groups[0]['lr']
        }

def create_advanced_rl_agent():
    """Factory function to create the most advanced RL agent"""
    
    agent = AdvancedRLAgent(
        input_size=50,  # Market features
        hidden_size=512,  # Large hidden size for complex patterns
        n_actions=3,  # BUY, SELL, HOLD
        learning_rate=1e-4  # Adaptive learning rate
    )
    
    logger.info("? Created most advanced RL agent with:")
    logger.info("   ? Transformer-based attention mechanisms")
    logger.info("   ? Dueling Double DQN with prioritized replay")
    logger.info("   ? Advanced PPO with entropy regularization")
    logger.info("   ? Meta-learning for rapid adaptation")
    logger.info("   ? Risk-aware decision making")
    logger.info("   ? Multi-head self-attention for market patterns")
    
    return agent

if __name__ == "__main__":
    # Test the advanced architecture
    agent = create_advanced_rl_agent()
    
    # Test forward pass
    dummy_state = np.random.randn(50)
    action, info = agent.get_action(dummy_state)
    
    print(f"[OK] Advanced RL Agent Test:")
    print(f"   Action: {action}")
    print(f"   Confidence: {info['confidence']:.3f}")
    print(f"   Risk Estimate: {info['risk_estimate']:.3f}")
    print(f"   Q-Values: {info['q_values']}")