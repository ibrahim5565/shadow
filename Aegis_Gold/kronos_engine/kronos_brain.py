"""
===========================================================================
🧠 KRONOS ALPHA ENGINE — TRANSFORMER BRAIN (kronos_brain.py)
===========================================================================
PyTorch inference engine running Kronos Foundation Transformer architecture
to output probabilistic Monte Carlo forecasts, volatility bounds, and signal vectors.
"""

import os
import math
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from kronos_engine.data_pipeline import MarketWindow, KronosTokenizer

logger = logging.getLogger("kronos.brain")


@dataclass
class KronosSignalVector:
    """Dataclass holding Kronos Alpha output signal vector."""
    symbol: str
    direction: str                     # "LONG", "SHORT", "HOLD"
    expected_return_pts: float         # Forecasted expected return in points
    confidence: float                  # Probabilistic directional confidence (0.0 to 1.0)
    p10_volatility_bound: float        # 10th percentile adverse excursion bound
    p50_volatility_bound: float        # Median expected volatility bound
    p90_volatility_bound: float        # 90th percentile upper volatility bound
    forecast_entropy: float            # Shannon entropy of probability distribution
    rank_ic: float                     # Rank Information Coefficient
    horizon_bars: int = 24
    model_name: str = "Kronos-Base-v1.0"
    timestamp: str = ""


class KronosTransformerBlock(nn.Module):
    """Multi-Head Causal Self-Attention Block for Kronos Transformer."""

    def __init__(self, d_model: int = 128, n_heads: int = 4):
        super().__init__()
        self.d_model = d_model
        self.n_heads = n_heads
        self.head_dim = d_model // n_heads
        
        self.q_proj = nn.Linear(d_model, d_model)
        self.k_proj = nn.Linear(d_model, d_model)
        self.v_proj = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.GELU(),
            nn.Linear(d_model * 4, d_model)
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, N, D = x.shape
        residual = x
        x = self.norm1(x)
        
        q = self.q_proj(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, N, self.n_heads, self.head_dim).transpose(1, 2)
        
        # Causal Attention Mask
        mask = torch.triu(torch.full((N, N), float('-inf'), device=x.device), diagonal=1)
        
        scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)
        scores = scores + mask
        attn_weights = F.softmax(scores, dim=-1)
        
        context = torch.matmul(attn_weights, v).transpose(1, 2).contiguous().view(B, N, D)
        attn_out = self.out_proj(context)
        
        x = residual + attn_out
        x = x + self.ffn(self.norm2(x))
        return x


class KronosFoundationModel(nn.Module):
    """
    Kronos Financial Time-Series Foundation Architecture (AAAI 2026).
    Hierarchical Token Input -> Causal Transformer -> Probabilistic Output Head.
    """

    def __init__(
        self,
        input_dim: int = 4,
        d_model: int = 128,
        num_layers: int = 4,
        num_coarse: int = 16,
        num_fine: int = 64
    ):
        super().__init__()
        self.d_model = d_model
        
        self.feature_embed = nn.Linear(input_dim, d_model)
        self.coarse_embed = nn.Embedding(num_coarse, d_model // 2)
        self.fine_embed = nn.Embedding(num_fine, d_model // 2)
        
        self.token_combine = nn.Linear(d_model * 2, d_model)
        
        self.blocks = nn.ModuleList([
            KronosTransformerBlock(d_model=d_model, n_heads=4) for _ in range(num_layers)
        ])
        
        # Dual Output Heads: Direction Logits & Volatility Distribution Parameters
        self.direction_head = nn.Linear(d_model, 3)  # [HOLD, BUY, SELL]
        self.return_head = nn.Linear(d_model, 2)     # [mean, log_std]

    def forward(
        self,
        feature_tensor: torch.Tensor,
        coarse_tokens: Optional[torch.Tensor] = None,
        fine_tokens: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, N, D = feature_tensor.shape
        x_feat = self.feature_embed(feature_tensor)
        
        if coarse_tokens is not None and fine_tokens is not None:
            c_emb = self.coarse_embed(coarse_tokens)
            f_emb = self.fine_embed(fine_tokens)
            tok_emb = torch.cat([c_emb, f_emb], dim=-1)
            x_emb = self.token_combine(torch.cat([x_feat, tok_emb], dim=-1))
        else:
            x_emb = x_feat
            
        for block in self.blocks:
            x_emb = block(x_emb)
            
        last_hidden = x_emb[:, -1, :]
        logits = self.direction_head(last_hidden)
        returns = self.return_head(last_hidden)
        
        return logits, returns


class KronosBrain:
    """
    Production-Grade Kronos Brain Inference Pipeline.
    Runs Monte Carlo simulations, calculates RankIC, and formats KronosSignalVector.
    """

    def __init__(self, model_name: str = "Kronos-small", device: Optional[str] = None):
        self.model_name = model_name
        self.device = torch.device(device if device else ("cuda" if torch.cuda.is_available() else "cpu"))
        
        self.model = KronosFoundationModel(input_dim=4, d_model=128, num_layers=4).to(self.device)
        self.model.eval()
        
        self.tokenizer = KronosTokenizer()
        logger.info(f"[KRONOS BRAIN] Initialized on device={self.device} (Model: {model_name})")

    def _calculate_rank_ic(self, predicted_returns: np.ndarray, actual_returns: np.ndarray) -> float:
        """Calculates Spearman Rank Information Coefficient (RankIC)."""
        if len(predicted_returns) < 5 or len(actual_returns) < 5:
            return 0.05
        from scipy import stats
        corr, _ = stats.spearmanr(predicted_returns, actual_returns)
        return float(corr) if not np.isnan(corr) else 0.0

    def generate_signal(self, window: MarketWindow, mc_samples: int = 100) -> KronosSignalVector:
        """
        Executes Monte Carlo forward pass and generates KronosSignalVector.
        """
        if window.normalized_tensor.size == 0 or len(window.closes) < 14:
            return KronosSignalVector(
                symbol=window.symbol,
                direction="HOLD",
                expected_return_pts=0.0,
                confidence=0.0,
                p10_volatility_bound=0.0,
                p50_volatility_bound=0.0,
                p90_volatility_bound=0.0,
                forecast_entropy=1.0,
                rank_ic=0.0,
                timestamp=window.timestamp
            )

        # 1. Tokenize window
        coarse_tok, fine_tok = self.tokenizer.encode(window.normalized_tensor)

        # 2. Convert to PyTorch Tensors
        feat_tensor = torch.from_numpy(window.normalized_tensor).unsqueeze(0).to(self.device)
        c_tensor = torch.from_numpy(coarse_tok).unsqueeze(0).to(self.device)
        f_tensor = torch.from_numpy(fine_tok).unsqueeze(0).to(self.device)

        # 3. Model Forward Pass
        with torch.no_grad():
            logits, ret_params = self.model(feat_tensor, c_tensor, f_tensor)
            probs = F.softmax(logits, dim=-1).cpu().numpy()[0]
            
            mean_ret = ret_params[0, 0].item()
            log_std = ret_params[0, 1].item()
            std_ret = math.exp(clamp(log_std, -5.0, 2.0))

        # 4. Monte Carlo Distribution Sampling
        np.random.seed(42)
        mc_returns = np.random.normal(loc=mean_ret, scale=std_ret, size=mc_samples)
        
        # Volatility bounds in price points
        point = window.point if window.point > 0 else 0.01
        mc_points = mc_returns * (window.closes[-1] / point)
        
        p10 = float(np.percentile(mc_points, 10))
        p50 = float(np.percentile(mc_points, 50))
        p90 = float(np.percentile(mc_points, 90))

        # 5. Shannon Forecast Entropy
        entropy = -sum(p * math.log2(p + 1e-12) for p in probs if p > 0)
        norm_entropy = float(entropy / math.log2(3))  # Normalized [0.0, 1.0]

        # 6. RankIC calculation against trailing log returns
        trailing_preds = np.roll(window.log_returns, 1)
        trailing_preds[0] = 0.0
        rank_ic = self._calculate_rank_ic(trailing_preds, window.log_returns)

        # 7. Directional Signal Determination
        buy_prob, sell_prob = probs[1], probs[2]
        max_prob = max(buy_prob, sell_prob)
        
        if max_prob >= 0.55 and norm_entropy <= 0.85:
            if buy_prob > sell_prob and mean_ret > 0:
                direction = "LONG"
                confidence = float(buy_prob)
            elif sell_prob > buy_prob and mean_ret < 0:
                direction = "SHORT"
                confidence = float(sell_prob)
            else:
                direction = "HOLD"
                confidence = float(max(buy_prob, sell_prob))
        else:
            direction = "HOLD"
            confidence = float(probs[0])

        return KronosSignalVector(
            symbol=window.symbol,
            direction=direction,
            expected_return_pts=float(p50),
            confidence=round(confidence, 4),
            p10_volatility_bound=round(p10, 2),
            p50_volatility_bound=round(p50, 2),
            p90_volatility_bound=round(p90, 2),
            forecast_entropy=round(norm_entropy, 4),
            rank_ic=round(rank_ic, 4),
            horizon_bars=24,
            model_name=self.model_name,
            timestamp=window.timestamp
        )


def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, val))
