import torch
import torch.nn as nn
import torch.nn.functional as F
import math

# ── GPT CORE ARCHITECTURE (Aegis-Gold v7.0) ──

def norm(x):
    return F.rms_norm(x, (x.size(-1),))

def has_ve(layer_idx, n_layer):
    """Value Embedding for alternating layers (and always last layer)."""
    return layer_idx % 2 == (n_layer - 1) % 2

def apply_rotary_emb(x, cos, sin):
    assert x.ndim == 4
    d = x.shape[3] // 2
    x1, x2 = x[..., :d], x[..., d:]
    y1 = x1 * cos + x2 * sin
    y2 = x1 * (-sin) + x2 * cos
    return torch.cat([y1, y2], 3)

class CausalSelfAttention(nn.Module):
    def __init__(self, n_embd, n_head, n_kv_head, layer_idx, n_layer):
        super().__init__()
        self.n_head = n_head
        self.n_kv_head = n_kv_head
        self.head_dim = n_embd // n_head
        
        self.c_q = nn.Linear(n_embd, n_head * self.head_dim, bias=False)
        self.c_k = nn.Linear(n_embd, n_kv_head * self.head_dim, bias=False)
        self.c_v = nn.Linear(n_embd, n_kv_head * self.head_dim, bias=False)
        self.c_proj = nn.Linear(n_embd, n_embd, bias=False)
        
        self.ve_gate = nn.Linear(32, n_kv_head, bias=False) if has_ve(layer_idx, n_layer) else None

    def forward(self, x, ve, cos_sin):
        B, T, C = x.size()
        q = self.c_q(x).view(B, T, self.n_head, self.head_dim)
        k = self.c_k(x).view(B, T, self.n_kv_head, self.head_dim)
        v = self.c_v(x).view(B, T, self.n_kv_head, self.head_dim)

        if ve is not None:
            # Value residual gating
            gate = 2 * torch.sigmoid(self.ve_gate(x[..., :32]))
            v = v + gate.unsqueeze(-1) * ve.view(B, T, self.n_kv_head, self.head_dim)

        cos, sin = cos_sin
        q = apply_rotary_emb(q, cos, sin)
        k = apply_rotary_emb(k, cos, sin)
        
        # Standard Scaled Dot Product Attention (Flash-equivalent if available)
        y = F.scaled_dot_product_attention(
            q.transpose(1, 2), k.transpose(1, 2), v.transpose(1, 2),
            is_causal=True
        )
        y = y.transpose(1, 2).contiguous().view(B, T, C)
        return self.c_proj(y)

class MLP(nn.Module):
    def __init__(self, n_embd):
        super().__init__()
        self.c_fc = nn.Linear(n_embd, 4 * n_embd, bias=False)
        self.c_proj = nn.Linear(4 * n_embd, n_embd, bias=False)

    def forward(self, x):
        x = self.c_fc(norm(x))
        x = F.relu(x).square()
        return self.c_proj(x)

class Block(nn.Module):
    def __init__(self, n_embd, n_head, n_kv_head, layer_idx, n_layer):
        super().__init__()
        self.attn = CausalSelfAttention(n_embd, n_head, n_kv_head, layer_idx, n_layer)
        self.mlp = MLP(n_embd)

    def forward(self, x, ve, cos_sin):
        x = x + self.attn(norm(x), ve, cos_sin)
        x = x + self.mlp(x)
        return x

class AegisGPT(nn.Module):
    def __init__(self, n_layer=4, n_head=4, n_embd=128, seq_len=16, input_dim=7):
        super().__init__()
        self.n_layer = n_layer
        self.seq_len = seq_len
        
        # Numerical input projection instead of token embeddings
        self.input_proj = nn.Linear(input_dim, n_embd)
        
        self.h = nn.ModuleList([
            Block(n_embd, n_head, n_head, i, n_layer) for i in range(n_layer)
        ])
        
        # Value embeddings (also numerical projection)
        self.ve_projs = nn.ModuleDict({
            str(i): nn.Linear(input_dim, n_embd)
            for i in range(n_layer) if has_ve(i, n_layer)
        })
        
        self.lm_head = nn.Linear(n_embd, 3) # Output: [WAIT, BUY, SELL]
        self.resid_lambdas = nn.Parameter(torch.ones(n_layer))
        self.x0_lambdas = nn.Parameter(torch.zeros(n_layer))

        # Rotary
        cos, sin = self._precompute_rotary(seq_len, n_embd // n_head)
        self.register_buffer("cos", cos)
        self.register_buffer("sin", sin)

    def _precompute_rotary(self, seq_len, head_dim):
        inv_freq = 1.0 / (10000 ** (torch.arange(0, head_dim, 2).float() / head_dim))
        t = torch.arange(seq_len).float()
        freqs = torch.outer(t, inv_freq)
        return freqs.cos()[None, :, None, :], freqs.sin()[None, :, None, :]

    def forward(self, x_seq):
        B, T, D = x_seq.size()
        cos_sin = (self.cos[:, :T], self.sin[:, :T])
        
        x = self.input_proj(x_seq)
        x0 = x
        
        for i, block in enumerate(self.h):
            x = self.resid_lambdas[i] * x + self.x0_lambdas[i] * x0
            ve = self.ve_projs[str(i)](x_seq) if str(i) in self.ve_projs else None
            x = block(x, ve, cos_sin)
        
        logits = self.lm_head(norm(x[:, -1, :])) # Only predict last step
        return logits
