import torch
import os
import logging
from .gpt_core import AegisGPT

logger = logging.getLogger("aegis.gpt_brain")

class GPTBrain:
    def __init__(self, model_path=None):
        if model_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(base_dir, "models", "aegis_gpt.pt")
            
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AegisGPT(n_layer=4, n_head=4, n_embd=128, seq_len=16, input_dim=7)
        
        if os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                logger.info(f"GPT Brain loaded from {model_path}")
            except Exception as e:
                logger.error(f"Failed to load GPT model: {e}")
        else:
            logger.warning(f"GPT Model file not found at {model_path}. Running with initialized weights.")
            
        self.model.to(self.device).eval()
        self.history = []

    def decide(self, features: list):
        """
        features: [regime_score, structure_score, entry_score, total_score, sl, tp, lot]
        """
        self.history.append(features)
        if len(self.history) > 16:
            self.history.pop(0)
            
        if len(self.history) < 16:
            return "WAIT", 0 # Not enough history
            
        with torch.no_grad():
            x = torch.tensor([self.history], dtype=torch.float32).to(self.device)
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)
            conf, pred = torch.max(probs, dim=1)
            
            result = pred.item()
            confidence = int(conf.item() * 100)
            
            if result == 0: return "WAIT", confidence
            if result == 1: return "BUY", confidence
            if result == 2: return "SELL", confidence
            
        return "WAIT", 0
