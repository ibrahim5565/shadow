"""
═══════════════════════════════════════════════════════════════════════════════
📊 AEGIS QUANT FEATURE ENGINE (V10.0) - Signal Processing & Complexity
═══════════════════════════════════════════════════════════════════════════════
PURPOSE:
--------
Calculates advanced frequency-domain, multi-scale, and complexity features.
Optimized for real-time inference (no look-ahead, vectorized calculations).

MODELS INCLUDED:
----------------
1. FFT spectral analysis (dominant cycles, spectral energy, top cycles)
2. 1D Haar Wavelet DWT/IDWT and wavelet-based price denoising
3. Zero-phase Butterworth low-pass filtering with edge extension padding
4. Hurst exponent via vectorized Rescaled Range (R/S) analysis
5. Higuchi Fractal Dimension (HFD) complexity estimator
6. Shannon Entropy, Approximate Entropy (ApEn), and Sample Entropy (SampEn)
"""

import math
import numpy as np
from scipy import stats
from scipy.signal import butter, filtfilt
from typing import Dict, Any, List, Tuple, Optional

class QuantFeatureEngine:
    """
    Engine to extract quantitative, signal-processing and complexity features 
    from historical price data. Ensures strict causality and high performance.
    """
    
    def __init__(self, default_fft_window: int = 128, default_entropy_window: int = 50, default_hurst_window: int = 100):
        self.default_fft_window = default_fft_window
        self.default_entropy_window = default_entropy_window
        self.default_hurst_window = default_hurst_window

    def analyze(self, prices: np.ndarray) -> Dict[str, Any]:
        """
        Runs full feature extraction suite on the provided price array.
        Assumes prices are ordered chronologically, with the last element being the current price.
        
        Parameters:
        -----------
        prices : np.ndarray
            1D array of floats representing price history.
            
        Returns:
        --------
        Dict[str, Any] : Feature dictionary matching schema keys.
        """
        prices = np.asarray(prices, dtype=float)
        n = len(prices)
        
        # Safe-guards for insufficient data
        if n < 10:
            return self._empty_result()
            
        # 1. FFT Features (typically calculated on a larger power-of-two window, e.g., trailing 128 bars)
        fft_w = min(n, self.default_fft_window)
        fft_data = prices[-fft_w:]
        fft_feats = self.calculate_fft_features(fft_data)
        
        # 2. Wavelet Features & Denoising
        wavelet_feats = self.calculate_wavelet_features(prices)
        
        # 3. Butterworth Filter
        butterworth_feats = self.calculate_butterworth_features(prices)
        
        # 4. Hurst Exponent (trailing 100 bars)
        hurst_w = min(n, self.default_hurst_window)
        hurst_data = prices[-hurst_w:]
        hurst_val = self.calculate_hurst(hurst_data)
        
        # 5. Higuchi Fractal Dimension (trailing 50 bars)
        hfd_w = min(n, self.default_entropy_window)
        hfd_data = prices[-hfd_w:]
        hfd_val = self.calculate_higuchi_fd(hfd_data)
        
        # 6. Entropy features (trailing 50 bars)
        entropy_data = prices[-self.default_entropy_window:] if n >= self.default_entropy_window else prices
        shannon_val = self.calculate_shannon_entropy(entropy_data)
        apen_val = self.calculate_approx_entropy(entropy_data)
        sampen_val = self.calculate_sample_entropy(entropy_data)
        
        # 7. Trained EGARCH and HMM Model Predictions
        egarch_vol = self.predict_egarch_volatility(prices)
        hmm_state, hmm_label = self.predict_hmm_regime(prices)

        return {
            # FFT
            "fft_dominant_cycle": fft_feats["dominant_cycle"],
            "fft_spectral_energy": fft_feats["spectral_energy"],
            "fft_top_cycles": fft_feats["top_cycles"],
            
            # Wavelets
            "wavelet_energy_l1": wavelet_feats["wavelet_energy_l1"],
            "wavelet_energy_l2": wavelet_feats["wavelet_energy_l2"],
            "wavelet_energy_l3": wavelet_feats["wavelet_energy_l3"],
            "wavelet_denoised": wavelet_feats["wavelet_denoised"],
            
            # Butterworth
            "butterworth_trend": butterworth_feats["butterworth_trend"],
            
            # Hurst
            "hurst_100": hurst_val,
            
            # Fractal Dimension
            "fractal_dim_50": hfd_val,
            
            # Entropy
            "shannon_entropy_50": shannon_val,
            "approx_entropy_50": apen_val,
            "sample_entropy_50": sampen_val,

            # Trained Models
            "egarch_volatility": egarch_vol,
            "hmm_regime_state": hmm_state,
            "hmm_regime_label": hmm_label,
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Returns feature dictionary populated with default safe values."""
        return {
            "fft_dominant_cycle": 0.0,
            "fft_spectral_energy": 0.0,
            "fft_top_cycles": [0.0, 0.0, 0.0],
            "wavelet_energy_l1": 0.0,
            "wavelet_energy_l2": 0.0,
            "wavelet_energy_l3": 0.0,
            "wavelet_denoised": 0.0,
            "butterworth_trend": 0.0,
            "hurst_100": 0.5,
            "fractal_dim_50": 1.5,
            "shannon_entropy_50": 0.0,
            "approx_entropy_50": 0.0,
            "sample_entropy_50": 0.0,
            "egarch_volatility": 0.0,
            "hmm_regime_state": 1,
            "hmm_regime_label": "MODERATE_VOL_TRENDING",
        }

    @staticmethod
    def predict_egarch_volatility(prices: np.ndarray) -> float:
        """
        Predict 1-step ahead conditional volatility using saved EGARCH model parameters.
        Falls back to rolling sample standard deviation if model file is absent.
        """
        import json
        from pathlib import Path

        model_path = Path(__file__).parent.parent / "models" / "egarch_model.json"
        rets = np.diff(np.log(prices)) * 100.0 if len(prices) >= 2 else np.array([0.0])

        if model_path.exists():
            try:
                with open(model_path) as f:
                    data = json.load(f)
                params = data.get("parameters", {})
                omega = params.get("omega", -0.1)
                alpha = params.get("alpha[1]", 0.1)
                gamma = params.get("gamma[1]", 0.0)
                beta = params.get("beta[1]", 0.9)

                # Recursively compute log-variance
                log_var = 0.0
                for r in rets[-100:]:
                    z = r / np.exp(0.5 * log_var) if log_var != 0 else r
                    log_var = omega + beta * log_var + alpha * (abs(z) - np.sqrt(2 / np.pi)) + gamma * z

                return float(np.exp(0.5 * log_var))
            except Exception:
                pass

        return float(np.std(rets[-14:])) if len(rets) >= 14 else 0.0

    @staticmethod
    def predict_hmm_regime(prices: np.ndarray) -> Tuple[int, str]:
        """
        Predict current market regime state (0: Ranging, 1: Trending, 2: High Vol)
        using saved HMM model parameters.
        """
        import json
        from pathlib import Path

        model_path = Path(__file__).parent.parent / "models" / "hmm_regime_model.json"
        if not model_path.exists() or len(prices) < 20:
            return 1, "MODERATE_VOL_TRENDING"

        try:
            with open(model_path) as f:
                data = json.load(f)

            means = np.array(data["means"])
            covars = np.array(data["covariances"])
            transmat = np.array(data["transition_matrix"])
            labels = data.get("state_labels", {})

            returns = np.diff(np.log(prices)) * 100.0
            vol = float(np.std(returns[-14:])) if len(returns) >= 14 else 0.01
            adx = 25.0

            cur_feat = np.array([returns[-1], np.log(max(1e-4, vol)), adx])

            # Gaussian likelihood per state
            dists = []
            for i in range(3):
                diff = cur_feat - means[i]
                cov = covars[i]
                det = max(1e-8, np.linalg.det(cov))
                inv = np.linalg.pinv(cov)
                mahal = float(diff.T @ inv @ diff)
                prob = np.exp(-0.5 * mahal) / np.sqrt(det)
                dists.append(prob)

            best_state = int(np.argmax(dists))
            best_label = str(labels.get(str(best_state), labels.get(best_state, "MODERATE_VOL_TRENDING")))
            return best_state, best_label
        except Exception:
            return 1, "MODERATE_VOL_TRENDING"

    # ═════════════════════════════════════════════════════════════════════════
    # 1. FFT METHODS
    # ═════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def calculate_fft_features(data: np.ndarray, fs: float = 1.0) -> Dict[str, Any]:
        """
        Extracts dominant cycles and spectral energy from detrended data.
        """
        n = len(data)
        if n < 8:
            return {"dominant_cycle": 0.0, "spectral_energy": 0.0, "top_cycles": [0.0, 0.0, 0.0]}
            
        try:
            # Linear detrending to prevent spectral leakage
            t = np.arange(n)
            slope, intercept, _, _, _ = stats.linregress(t, data)
            detrended = data - (slope * t + intercept)
            
            # FFT
            fft_vals = np.fft.rfft(detrended)
            fft_freqs = np.fft.rfftfreq(n, d=1.0/fs)
            magnitudes = np.abs(fft_vals)
            
            # DC Component represents mean, zero it out
            magnitudes[0] = 0.0
            
            # Total Spectral Energy
            spectral_energy = float(np.sum(magnitudes**2))
            
            # Dominant Cycle (peak magnitude)
            idx_dominant = np.argmax(magnitudes)
            dom_freq = fft_freqs[idx_dominant]
            dominant_cycle = float(1.0 / dom_freq) if dom_freq > 0 else 0.0
            
            # Top 3 Cycles
            top_indices = np.argsort(magnitudes)[::-1][:3]
            top_cycles = []
            for idx in top_indices:
                freq = fft_freqs[idx]
                if freq > 0 and magnitudes[idx] > 1e-8:
                    top_cycles.append(float(1.0 / freq))
                else:
                    top_cycles.append(0.0)
            
            # Fill with 0s if we got less than 3
            while len(top_cycles) < 3:
                top_cycles.append(0.0)
                
            return {
                "dominant_cycle": dominant_cycle,
                "spectral_energy": spectral_energy,
                "top_cycles": top_cycles
            }
        except Exception:
            return {"dominant_cycle": 0.0, "spectral_energy": 0.0, "top_cycles": [0.0, 0.0, 0.0]}

    # ═════════════════════════════════════════════════════════════════════════
    # 2. HAAR WAVELET DWT/IDWT & DENOISING METHODS
    # ═════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def haar_dwt_1d(x: np.ndarray, level: int = 3) -> List[np.ndarray]:
        """
        Performs a 1D Discrete Haar Wavelet Transform.
        Returns a list of coefficients: [approx_L, detail_L, detail_L-1, ..., detail_1]
        Handles odd lengths by duplicating the last element.
        """
        coeffs = []
        a = np.copy(x).astype(float)
        for l in range(level):
            n = len(a)
            if n % 2 != 0:
                a = np.append(a, a[-1])
            approx = (a[0::2] + a[1::2]) / np.sqrt(2.0)
            detail = (a[0::2] - a[1::2]) / np.sqrt(2.0)
            coeffs.append(detail)
            a = approx
        coeffs.append(a)
        coeffs.reverse()  # Order: approx_L, detail_L, ..., detail_1
        return coeffs

    @staticmethod
    def haar_idwt_1d(coeffs: List[np.ndarray]) -> np.ndarray:
        """
        Performs an Inverse 1D Discrete Haar Wavelet Transform.
        Expects coeffs in the format: [approx_L, detail_L, ..., detail_1]
        """
        a = np.copy(coeffs[0]).astype(float)
        for detail in coeffs[1:]:
            n_a = len(a)
            n_d = len(detail)
            # Match lengths if level mismatch occurred during rounding
            if n_a != n_d:
                min_len = min(n_a, n_d)
                a = a[:min_len]
                detail = detail[:min_len]
                
            reconstructed = np.empty(2 * len(a), dtype=float)
            reconstructed[0::2] = (a + detail) / np.sqrt(2.0)
            reconstructed[1::2] = (a - detail) / np.sqrt(2.0)
            a = reconstructed
        return a

    def calculate_wavelet_features(self, prices: np.ndarray, level: int = 3) -> Dict[str, Any]:
        """
        Decomposes prices using Haar Wavelet DWT, measures energy ratios,
        and computes denoised price series.
        """
        n = len(prices)
        if n < 8:
            return {
                "wavelet_energy_l1": 0.0,
                "wavelet_energy_l2": 0.0,
                "wavelet_energy_l3": 0.0,
                "wavelet_denoised": float(prices[-1]) if n > 0 else 0.0
            }
            
        try:
            total_energy = float(np.sum(prices**2))
            if total_energy == 0:
                return {"wavelet_energy_l1": 0.0, "wavelet_energy_l2": 0.0, "wavelet_energy_l3": 0.0, "wavelet_denoised": 0.0}
                
            coeffs = self.haar_dwt_1d(prices, level=level)
            
            # Extract detail coefficients (d3 is coeffs[1], d2 is coeffs[2], d1 is coeffs[3])
            # Note: order is [approx_3, detail_3, detail_2, detail_1]
            d3, d2, d1 = coeffs[1], coeffs[2], coeffs[3]
            
            e3 = float(np.sum(d3**2) / total_energy)
            e2 = float(np.sum(d2**2) / total_energy)
            e1 = float(np.sum(d1**2) / total_energy)
            
            # Denoise using soft thresholding
            # Universal threshold lambda = sigma * sqrt(2 * ln(N))
            # Estimate noise level sigma using Median Absolute Deviation (MAD) of finest scale d1
            mad = np.median(np.abs(d1 - np.median(d1)))
            sigma = mad / 0.6745 if mad > 0 else 1e-6
            lam = sigma * np.sqrt(2.0 * np.log(n))
            
            new_coeffs = [coeffs[0]]
            for detail in coeffs[1:]:
                # Soft thresholding: sgn(d) * max(|d| - lam, 0)
                thresh_d = np.sign(detail) * np.maximum(np.abs(detail) - lam, 0.0)
                new_coeffs.append(thresh_d)
                
            denoised = self.haar_idwt_1d(new_coeffs)
            
            # Align output length back to input length
            if len(denoised) > n:
                denoised = denoised[:n]
            elif len(denoised) < n:
                denoised = np.pad(denoised, (0, n - len(denoised)), 'edge')
                
            return {
                "wavelet_energy_l1": e1,
                "wavelet_energy_l2": e2,
                "wavelet_energy_l3": e3,
                "wavelet_denoised": float(denoised[-1])
            }
        except Exception:
            return {
                "wavelet_energy_l1": 0.0,
                "wavelet_energy_l2": 0.0,
                "wavelet_energy_l3": 0.0,
                "wavelet_denoised": float(prices[-1])
            }

    # ═════════════════════════════════════════════════════════════════════════
    # 3. BUTTERWORTH LOW-PASS FILTER
    # ═════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def calculate_butterworth_features(prices: np.ndarray, cutoff: float = 0.1, fs: float = 1.0, order: int = 2) -> Dict[str, Any]:
        """
        Applies a zero-phase Butterworth filter with reflection padding to extract trend.
        """
        n = len(prices)
        if n < 8:
            return {"butterworth_trend": float(prices[-1]) if n > 0 else 0.0}
            
        try:
            nyq = 0.5 * fs
            normal_cutoff = min(0.99, max(0.01, cutoff / nyq))
            b, a = butter(order, normal_cutoff, btype='low', analog=False)
            
            # Use reflection padding to minimize transient boundary distortion at index -1
            padlen = min(n - 1, 3 * max(len(a), len(b)))
            y = filtfilt(b, a, prices, padlen=padlen)
            
            return {
                "butterworth_trend": float(y[-1])
            }
        except Exception:
            return {"butterworth_trend": float(prices[-1])}

    # ═════════════════════════════════════════════════════════════════════════
    # 4. HURST EXPONENT (RESCOLED RANGE ANALYSIS)
    # ═════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def calculate_hurst(values: np.ndarray) -> float:
        """
        Calculates Hurst exponent via R/S analysis.
        Clamped to [0.0, 1.0].
        """
        n = len(values)
        if n < 20:
            return 0.5
            
        try:
            # We select lag scales (power of 2) that fit the data size
            lags = [4, 8, 16, 32, 64]
            lags = [l for l in lags if l < n // 2]
            if not lags:
                return 0.5
                
            rs_vals = []
            for lag in lags:
                num_chunks = n // lag
                if num_chunks < 1:
                    continue
                # Truncate and reshape to process chunks in a vectorized manner
                chunks = values[:num_chunks * lag].reshape((num_chunks, lag))
                
                # Chunk-wise statistics
                means = np.mean(chunks, axis=1, keepdims=True)
                deviations = chunks - means
                cumsum_devs = np.cumsum(deviations, axis=1)
                
                ranges = np.max(cumsum_devs, axis=1) - np.min(cumsum_devs, axis=1)
                stds = np.std(chunks, axis=1, ddof=1)
                
                valid = stds > 0
                if np.any(valid):
                    rs = ranges[valid] / stds[valid]
                    rs_vals.append((np.log(lag), np.log(np.mean(rs))))
                    
            if len(rs_vals) < 2:
                return 0.5
                
            xs = np.array([v[0] for v in rs_vals])
            ys = np.array([v[1] for v in rs_vals])
            slope, _ = np.polyfit(xs, ys, 1)
            
            return float(np.clip(slope, 0.0, 1.0))
        except Exception:
            return 0.5

    # ═════════════════════════════════════════════════════════════════════════
    # 5. HIGUCHI FRACTAL DIMENSION (HFD)
    # ═════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def calculate_higuchi_fd(x: np.ndarray, k_max: int = 5) -> float:
        """
        Computes Higuchi Fractal Dimension (HFD) of a 1D sequence.
        Returns a complexity measure clamped between [1.0, 2.0].
        """
        n = len(x)
        if n < k_max * 2:
            return 1.5
            
        try:
            lk = np.zeros(k_max)
            for k in range(1, k_max + 1):
                lm = 0.0
                for m in range(1, k + 1):
                    sub_seq = x[m-1::k]
                    n_sub = len(sub_seq)
                    if n_sub < 2:
                        continue
                    sum_diffs = np.sum(np.abs(np.diff(sub_seq)))
                    norm = (n - 1) / ((n_sub - 1) * k)
                    lm += (sum_diffs * norm) / k
                lk[k-1] = lm / k
                
            xs = -np.log(np.arange(1, k_max + 1))
            ys = np.log(lk)
            
            valid = np.isfinite(ys)
            if np.sum(valid) < 2:
                return 1.5
                
            slope, _ = np.polyfit(xs[valid], ys[valid], 1)
            return float(np.clip(slope, 1.0, 2.0))
        except Exception:
            return 1.5

    # ═════════════════════════════════════════════════════════════════════════
    # 6. ENTROPY ANALYSIS
    # ═════════════════════════════════════════════════════════════════════════
    
    @staticmethod
    def calculate_shannon_entropy(x: np.ndarray, bins: int = 10) -> float:
        """
        Calculates Shannon Entropy on 1-bar log returns of the price series.
        """
        if len(x) < 5:
            return 0.0
            
        try:
            # Shift to returns to capture structural predictability
            with np.errstate(divide='ignore', invalid='ignore'):
                rets = np.diff(np.log(x))
            # Remove any NaNs/Infs
            rets = rets[np.isfinite(rets)]
            if len(rets) < 2:
                return 0.0
                
            hist, _ = np.histogram(rets, bins=bins, density=False)
            probs = hist / np.sum(hist)
            probs = probs[probs > 0]
            
            entropy = -np.sum(probs * np.log2(probs))
            max_entropy = np.log2(bins)
            return float(entropy / max_entropy) if max_entropy > 0 else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def calculate_approx_entropy(x: np.ndarray, m: int = 2, r: Optional[float] = None) -> float:
        """
        Calculates Approximate Entropy (ApEn) using vectorized distance matrices.
        Time complexity: O(N^2) - constrained by small window sizes (e.g. N=50).
        """
        n = len(x)
        if n < m + 1:
            return 0.0
            
        if r is None:
            r = 0.2 * np.std(x)
        if r == 0:
            r = 1e-6
            
        def _phi(dim: int) -> float:
            sub_seqs = np.array([x[i:i + dim] for i in range(n - dim + 1)])
            dists = np.max(np.abs(sub_seqs[:, None, :] - sub_seqs[None, :, :]), axis=-1)
            counts = np.sum(dists <= r, axis=1) / (n - dim + 1)
            return np.sum(np.log(counts)) / (n - dim + 1)
            
        try:
            return float(abs(_phi(m) - _phi(m + 1)))
        except Exception:
            return 0.0

    @staticmethod
    def calculate_sample_entropy(x: np.ndarray, m: int = 2, r: Optional[float] = None) -> float:
        """
        Calculates Sample Entropy (SampEn) using vectorized calculations.
        Excludes self-matches.
        """
        n = len(x)
        if n < m + 1:
            return 0.0
            
        if r is None:
            r = 0.2 * np.std(x)
        if r == 0:
            r = 1e-6
            
        def _phi(dim: int) -> Tuple[int, int]:
            sub_seqs = np.array([x[i:i + dim] for i in range(n - dim + 1)])
            dists = np.max(np.abs(sub_seqs[:, None, :] - sub_seqs[None, :, :]), axis=-1)
            np.fill_diagonal(dists, np.inf)
            matches = np.sum(dists <= r)
            total_pairs = len(sub_seqs) * (len(sub_seqs) - 1)
            return matches, total_pairs
            
        try:
            m_matches, _ = _phi(m)
            m1_matches, _ = _phi(m + 1)
            if m_matches == 0 or m1_matches == 0:
                return 0.0
            return float(-np.log(m1_matches / m_matches))
        except Exception:
            return 0.0
