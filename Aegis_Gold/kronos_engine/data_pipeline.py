"""
===========================================================================
📊 KRONOS ALPHA ENGINE — DATA PIPELINE & TOKENIZER (data_pipeline.py)
===========================================================================
Hierarchical Tokenization via Binary Spherical Quantization (BSQ) and
causal multi-timeframe OHLCV feature normalization.
"""

import math
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional, Union
import numpy as np

logger = logging.getLogger("kronos.data_pipeline")


@dataclass
class MarketWindow:
    """Dataclass holding aligned multi-timeframe candlestick feature windows."""
    symbol: str
    timestamp: str
    closes: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    opens: np.ndarray
    volumes: np.ndarray
    point: float = 0.01
    
    # Normalized feature representations
    log_returns: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    hl_ranges: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))
    normalized_tensor: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float32))


class KronosTokenizer:
    """
    Hierarchical Tokenizer implementing Binary Spherical Quantization (BSQ)
    to convert continuous price/range/volume features into discrete coarse/fine subtokens.
    """

    def __init__(self, num_coarse: int = 16, num_fine: int = 64, dimension: int = 4):
        self.num_coarse = num_coarse
        self.num_fine = num_fine
        self.dimension = dimension
        
        # Deterministic projection matrices for BSQ
        rng = np.random.RandomState(42)
        self.coarse_proj = rng.randn(dimension, int(np.log2(num_coarse))).astype(np.float32)
        self.fine_proj = rng.randn(dimension, int(np.log2(num_fine))).astype(np.float32)
        
        # Normalize projection columns to unit sphere
        self.coarse_proj /= np.linalg.norm(self.coarse_proj, axis=0, keepdims=True) + 1e-8
        self.fine_proj /= np.linalg.norm(self.fine_proj, axis=0, keepdims=True) + 1e-8

    def _binary_quantize(self, features: np.ndarray, proj: np.ndarray) -> np.ndarray:
        """Projects continuous features onto hyperplanes and extracts bit integer codes."""
        # features shape: (N, D), proj shape: (D, K)
        dot = np.dot(features, proj)  # (N, K)
        bits = (dot >= 0).astype(np.int32)
        
        # Convert binary bits to decimal subtoken ID
        powers = 2 ** np.arange(bits.shape[1], dtype=np.int32)
        token_ids = np.dot(bits, powers)
        return token_ids

    def encode(self, feature_matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Encodes a 2D feature matrix (N_steps, dimension) into
        (coarse_subtokens, fine_subtokens) integer arrays.
        """
        if feature_matrix.size == 0:
            return np.array([], dtype=np.int64), np.array([], dtype=np.int64)

        if feature_matrix.ndim == 1:
            feature_matrix = feature_matrix.reshape(1, -1)

        # Pad or trim feature dimension to match tokenizer
        if feature_matrix.shape[1] < self.dimension:
            pad_width = self.dimension - feature_matrix.shape[1]
            feature_matrix = np.pad(feature_matrix, ((0, 0), (0, pad_width)), mode='constant')
        elif feature_matrix.shape[1] > self.dimension:
            feature_matrix = feature_matrix[:, :self.dimension]

        # Unit sphere normalization for spherical quantization
        norms = np.linalg.norm(feature_matrix, axis=1, keepdims=True) + 1e-8
        unit_features = feature_matrix / norms

        coarse_tokens = self._binary_quantize(unit_features, self.coarse_proj)
        
        # Residual projection for fine subtokens
        coarse_recon = self._reconstruct_coarse(coarse_tokens)
        residual = unit_features - coarse_recon
        fine_tokens = self._binary_quantize(residual, self.fine_proj)

        return coarse_tokens.astype(np.int64), fine_tokens.astype(np.int64)

    def _reconstruct_coarse(self, token_ids: np.ndarray) -> np.ndarray:
        """Approximate vector reconstruction from coarse subtoken code."""
        N = len(token_ids)
        K = self.coarse_proj.shape[1]
        bits = np.zeros((N, K), dtype=np.float32)
        for i in range(K):
            bits[:, i] = ((token_ids >> i) & 1).astype(np.float32) * 2.0 - 1.0
        recon = np.dot(bits, self.coarse_proj.T)
        return recon / (np.linalg.norm(recon, axis=1, keepdims=True) + 1e-8)


class DataPipeline:
    """
    Ingests raw candlestick data, constructs causally safe multi-timeframe features,
    applies z-score normalization, and formats outputs for Kronos inference.
    """

    def __init__(self, history_window: int = 100):
        self.history_window = history_window
        self.tokenizer = KronosTokenizer(num_coarse=16, num_fine=64, dimension=4)

    def process_candles(
        self,
        raw_candles: List[Union[Dict[str, Any], Tuple, Any]],
        symbol: str = "XAUUSD",
        point: float = 0.01,
        timestamp: str = ""
    ) -> MarketWindow:
        """
        Parses, normalizes, and extracts causally clean feature tensors from raw OHLCV.
        Guarantees ZERO look-ahead bias.
        """
        if not raw_candles:
            raise ValueError("Empty candle list provided to DataPipeline.")

        opens, highs, lows, closes, vols = [], [], [], [], []
        
        for c in raw_candles:
            if isinstance(c, dict):
                opens.append(float(c.get("open", c.get("o", 0.0))))
                highs.append(float(c.get("high", c.get("h", 0.0))))
                lows.append(float(c.get("low", c.get("l", 0.0))))
                closes.append(float(c.get("close", c.get("c", 0.0))))
                vols.append(float(c.get("volume", c.get("v", c.get("tick_volume", 1.0)))))
            elif hasattr(c, "close"):
                opens.append(float(getattr(c, "open", 0.0)))
                highs.append(float(getattr(c, "high", 0.0)))
                lows.append(float(getattr(c, "low", 0.0)))
                closes.append(float(getattr(c, "close", 0.0)))
                vols.append(float(getattr(c, "tick_volume", getattr(c, "volume", 1.0))))
            else:
                # Assume tuple format: (time, open, high, low, close, volume)
                opens.append(float(c[1]))
                highs.append(float(c[2]))
                lows.append(float(c[3]))
                closes.append(float(c[4]))
                vols.append(float(c[5]) if len(c) > 5 else 1.0)

        o_arr = np.array(opens, dtype=np.float32)[-self.history_window:]
        h_arr = np.array(highs, dtype=np.float32)[-self.history_window:]
        l_arr = np.array(lows, dtype=np.float32)[-self.history_window:]
        c_arr = np.array(closes, dtype=np.float32)[-self.history_window:]
        v_arr = np.array(vols, dtype=np.float32)[-self.history_window:]

        if len(c_arr) < 2:
            raise ValueError(f"Insufficient candles ({len(c_arr)}) for feature calculation.")

        # 1. Log returns: ln(C_t / C_{t-1})
        log_ret = np.zeros_like(c_arr, dtype=np.float32)
        log_ret[1:] = np.log(np.maximum(c_arr[1:], 1e-8) / np.maximum(c_arr[:-1], 1e-8))

        # 2. High-Low range normalized by point
        hl_range = (h_arr - l_arr) / max(point, 1e-8)

        # 3. Upper & Lower Wick ratios
        body_top = np.maximum(o_arr, c_arr)
        body_bot = np.minimum(o_arr, c_arr)
        denom = np.maximum(h_arr - l_arr, 1e-8)
        upper_wick = (h_arr - body_top) / denom
        lower_wick = (body_bot - l_arr) / denom

        # 4. Construct 4D Feature Tensor: [LogReturn, HL_Range_Norm, UpperWick, LowerWick]
        log_ret_norm = (log_ret - np.mean(log_ret)) / (np.std(log_ret) + 1e-8)
        hl_norm = (hl_range - np.mean(hl_range)) / (np.std(hl_range) + 1e-8)
        
        feature_matrix = np.column_stack([log_ret_norm, hl_norm, upper_wick, lower_wick]).astype(np.float32)

        return MarketWindow(
            symbol=symbol,
            timestamp=timestamp or "UTC_NOW",
            closes=c_arr,
            highs=h_arr,
            lows=l_arr,
            opens=o_arr,
            volumes=v_arr,
            point=point,
            log_returns=log_ret,
            hl_ranges=hl_range,
            normalized_tensor=feature_matrix
        )

    def tokenize_window(self, window: MarketWindow) -> Tuple[np.ndarray, np.ndarray]:
        """Encodes MarketWindow normalized tensor into BSQ coarse/fine subtokens."""
        return self.tokenizer.encode(window.normalized_tensor)
