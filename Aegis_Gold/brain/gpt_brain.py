try:
    import torch
    from .gpt_core import AegisGPT
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None
    AegisGPT = None

import os
import logging

logger = logging.getLogger("aegis.gpt_brain")

class GPTBrain:
    def __init__(self, model_path=None):
        # v6.0 FIX: gpt_status flag — NEVER use random weights silently.
        self.gpt_status = "UNAVAILABLE"

        if not HAS_TORCH:
            self.enabled = False
            logger.warning("GPT_STATUS=UNAVAILABLE — PyTorch not installed. GPT disabled.")
            return

        self.enabled = True
        if model_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(base_dir, "models", "aegis_gpt.pt")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AegisGPT(n_layer=4, n_head=4, n_embd=128, seq_len=16, input_dim=7)

        if os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                self.gpt_status = "READY"
                logger.info(f"GPT_STATUS=READY — GPT Brain loaded from {model_path}")
            except Exception as e:
                self.gpt_status = "UNAVAILABLE"
                logger.error(f"GPT_STATUS=UNAVAILABLE — Failed to load GPT model: {e}")
        else:
            # v6.0 FIX: Model file missing → GPT is UNAVAILABLE.
            # Never contributes positive confidence when untrained.
            self.gpt_status = "UNAVAILABLE"
            logger.warning(
                f"GPT_STATUS=UNAVAILABLE — model not trained. GPT disabled. "
                f"Model file not found at {model_path}. Run `python brain/train_gpt.py` to train."
            )

        # Only expose model weights and enable inference when the model file exists and loaded cleanly.
        if self.gpt_status == "READY":
            self.model.to(self.device).eval()
            self.history = []
        else:
            # Keep an empty model — no inference calls will be made.
            self.history = []

    def decide(self, features: list):
        """
        features: [regime_score, structure_score, entry_score, total_score, sl, tp, lot]
        """
        # v6.0 FIX: Return UNAVAILABLE when model is not trained.
        if self.gpt_status != "READY":
            return "WAIT", 0, "GPT_STATUS=UNAVAILABLE"

        if not getattr(self, "enabled", True):
            return "WAIT", 0, "GPT_DISABLED"

        self.history.append(features)
        if len(self.history) > 16:
            self.history.pop(0)

        if len(self.history) < 16:
            return "WAIT", 0, "GPT_NOT_ENOUGH_HISTORY"

        with torch.no_grad():
            x = torch.tensor([self.history], dtype=torch.float32).to(self.device)
            logits = self.model(x)
            probs = torch.softmax(logits, dim=1)
            conf, pred = torch.max(probs, dim=1)

            result = pred.item()
            confidence = int(conf.item() * 100)

            if result == 0: return "WAIT", confidence, "GPT_READY"
            if result == 1: return "BUY", confidence, "GPT_READY"
            if result == 2: return "SELL", confidence, "GPT_READY"

        return "WAIT", 0, "GPT_READY"
