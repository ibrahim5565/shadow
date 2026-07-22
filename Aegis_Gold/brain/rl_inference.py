"""
AEGIS RL INFERENCE ENGINE
Uses trained Actor-Critic models to enhance decision-making
Provides additional confidence boost for decisions that align with RL policy
"""
import os
import torch
import torch.nn as nn
import numpy as np
import logging
from typing import Optional, Dict

logger = logging.getLogger("aegis.rl_inference")

# Model paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RL_MODEL_PATH = os.path.join(BASE_DIR, "models", "aegis_rl_actor.pt")


class ActorNetwork(nn.Module):
    """Policy network - same architecture as training"""
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


class RLInference:
    """Reinforcement Learning inference for real-time trading decisions"""
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.actor = None
        self.enabled = False
        self._load_model()
    
    def _load_model(self):
        """Load trained RL actor model"""
        if not os.path.exists(RL_MODEL_PATH):
            logger.warning(f"RL model not found at {RL_MODEL_PATH}. RL inference disabled.")
            return
        
        try:
            self.actor = ActorNetwork(state_dim=15, action_dim=3).to(self.device)
            self.actor.load_state_dict(torch.load(RL_MODEL_PATH, map_location=self.device))
            self.actor.eval()
            self.enabled = True
            logger.info(f"✅ RL Actor model loaded successfully from {RL_MODEL_PATH}")
        except Exception as e:
            logger.error(f"Failed to load RL model: {e}")
            self.enabled = False
    
    def extract_state(self, candles, indicators: Dict, symbol: str, current_price: float) -> np.ndarray:
        """
        Extract state features from current market conditions
        Must match training feature extraction
        """
        try:
            # Price features (normalized)
            price_norm = current_price / 4000.0 if "XAU" in symbol else current_price
            
            # Get indicators
            adx = indicators.get('adx', 50.0)
            rsi = indicators.get('rsi', 50.0)
            
            # Symbol encoding
            symbol_val = 1.0 if "XAU" in symbol else 0.0
            
            # Session - approximate based on hour
            import datetime
            hour = datetime.datetime.now().hour
            if 8 <= hour < 16:
                session_val = 0.8  # LONDON
            elif 13 <= hour < 22:
                session_val = 0.6  # NY
            elif 8 <= hour < 22:
                session_val = 1.0  # OVERLAP
            else:
                session_val = 0.4  # ASIAN
            
            # Time features
            hour_sin = np.sin(2 * np.pi * hour / 24)
            hour_cos = np.cos(2 * np.pi * hour / 24)
            
            # Additional features
            spread = indicators.get('spread', 0.0) / 100.0
            volatility = indicators.get('atr', 0.0) / current_price if current_price > 0 else 0.0
            momentum = indicators.get('momentum', 0.0) / 100.0
            
            # Trend detection from price action
            if len(candles) >= 3:
                trend = 1.0 if candles[-1] > candles[-3] else -1.0
            else:
                trend = 0.0
            
            state = np.array([
                price_norm,
                0.0,  # PnL (unknown at decision time)
                1.0,  # Fixed lot * 100
                adx / 100.0,
                rsi / 100.0,
                0.0,  # Direction (unknown at decision time)
                symbol_val,
                session_val,
                hour_sin,
                hour_cos,
                1.0,  # Bias
                spread,
                volatility,
                momentum,
                trend * 0.5,
            ], dtype=np.float32)
            
            return state
            
        except Exception as e:
            logger.error(f"State extraction error: {e}")
            return np.zeros(15, dtype=np.float32)
    
    def get_policy(self, state: np.ndarray) -> Dict[str, float]:
        """
        Get RL policy probabilities for WAIT/BUY/SELL
        Returns dict with action probabilities and recommended action
        """
        if not self.enabled or self.actor is None:
            return {"wait": 0.33, "buy": 0.33, "sell": 0.33, "action": "WAIT", "confidence": 0.0}
        
        try:
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                action_probs = self.actor(state_tensor).cpu().numpy()[0]
                
                # action_probs[0] = WAIT, [1] = BUY, [2] = SELL
                wait_prob = float(action_probs[0])
                buy_prob = float(action_probs[1])
                sell_prob = float(action_probs[2])
                
                # Determine recommended action
                max_prob = max(wait_prob, buy_prob, sell_prob)
                if max_prob == buy_prob:
                    action = "BUY"
                elif max_prob == sell_prob:
                    action = "SELL"
                else:
                    action = "WAIT"
                
                return {
                    "wait": wait_prob,
                    "buy": buy_prob,
                    "sell": sell_prob,
                    "action": action,
                    "confidence": max_prob
                }
                
        except Exception as e:
            logger.error(f"RL inference error: {e}")
            return {"wait": 0.33, "buy": 0.33, "sell": 0.33, "action": "WAIT", "confidence": 0.0}
    
    def boost_decision(self, decision_direction: str, state: np.ndarray, base_confidence: float) -> float:
        """
        Boost confidence if RL policy agrees with the decision
        Returns boosted confidence (or unchanged if disagrees)
        """
        if not self.enabled:
            return base_confidence
        
        policy = self.get_policy(state)
        rl_action = policy['action']
        rl_confidence = policy['confidence']
        
        # If RL agrees with decision, boost confidence
        if rl_action == decision_direction:
            boost = rl_confidence * 10.0  # Up to +10% boost if RL is very confident
            boosted = min(base_confidence + boost, 100.0)
            logger.debug(f"RL boost: {decision_direction} confidence {base_confidence:.1f}% -> {boosted:.1f}% (+{boost:.1f}%)")
            return boosted
        
        # If RL disagrees, slight penalty
        elif rl_action != "WAIT":
            penalty = rl_confidence * 5.0  # Up to -5% penalty
            reduced = max(base_confidence - penalty, 0.0)
            logger.debug(f"RL penalty: {decision_direction} confidence {base_confidence:.1f}% -> {reduced:.1f}% (-{penalty:.1f}%)")
            return reduced
        
        # RL says WAIT, no change
        return base_confidence


# Global singleton instance
_rl_engine = None

def get_rl_engine() -> RLInference:
    """Get or create RL inference engine singleton"""
    global _rl_engine
    if _rl_engine is None:
        _rl_engine = RLInference()
    return _rl_engine
