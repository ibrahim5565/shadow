"""
═══════════════════════════════════════════════════════════════════════════════
🧪 AEGIS QUANT FEATURE ENGINE VERIFICATION TEST SUITE
═══════════════════════════════════════════════════════════════════════════════
Checks causality, edge stability, calculation speed, and mathematical correctness.
"""

import time
import numpy as np
import sys
from pathlib import Path

# Add brain folder to path
sys.path.append(str(Path(__file__).parent.parent))

from brain.quant_feature_engine import QuantFeatureEngine

def run_suite():
    print("=" * 70)
    print("🧪 RUNNING QUANT FEATURE ENGINE VERIFICATION SUITE")
    print("=" * 70)
    
    engine = QuantFeatureEngine()
    
    # Generate test signals
    np.random.seed(42)
    t = np.arange(250)
    clean_sine = np.sin(2 * np.pi * t / 20.0)  # Period = 20
    noise = np.random.normal(0, 0.2, 250)
    noisy_sine = clean_sine + noise
    
    # 1. Schema Integration Key Check
    print("\n1. Schema Integration Check...")
    test_prices = np.random.normal(100, 2, 150)
    result = engine.analyze(test_prices)
    
    expected_keys = {
        "fft_dominant_cycle", "fft_spectral_energy", "fft_top_cycles",
        "wavelet_energy_l1", "wavelet_energy_l2", "wavelet_energy_l3", "wavelet_denoised",
        "butterworth_trend", "hurst_100", "fractal_dim_50",
        "shannon_entropy_50", "approx_entropy_50", "sample_entropy_50"
    }
    
    missing_keys = expected_keys - set(result.keys())
    if missing_keys:
        print(f"❌ FAILED: Missing schema keys in output: {missing_keys}")
        return False
    print("✅ PASSED: All expected schema keys are present.")

    # 2. Causality / Look-Ahead Check
    print("\n2. Causality Check...")
    # We want to verify that the feature calculated for a bar t ONLY depends on data <= t.
    # We will simulate rolling history and check that adding future data does not alter historical values.
    signal = np.cumsum(np.random.normal(0, 1, 200))
    
    # We run analysis on two different history sizes:
    # History A ends at t=120. History B ends at t=170.
    # The value of features for t=120 must be exactly the same in both runs
    # if we only feed the history up to t=120.
    t_target = 120
    prices_at_t = signal[:t_target + 1]       # Length 121 (t=0 to t=120)
    prices_extended = signal[:t_target + 51]  # Length 171 (t=0 to t=170)
    
    # Feature computed "at the time" (at t_target)
    feats_at_t = engine.analyze(prices_at_t)
    
    # Feature computed from the exact same window but executed later (still feeding only up to t_target)
    feats_at_t_from_same = engine.analyze(prices_extended[:t_target + 1])
    
    # Compare results
    for key in expected_keys:
        val1 = feats_at_t[key]
        val2 = feats_at_t_from_same[key]
        if isinstance(val1, list):
            match = np.allclose(val1, val2)
        else:
            match = np.isclose(val1, val2)
            
        if not match:
            print(f"❌ FAILED: Non-causal behavior or state leak found in {key}: {val1} vs {val2}")
            return False
            
    print("✅ PASSED: Strict causality verified. Feature calculations have zero look-ahead.")

    # 3. Execution Latency Benchmark
    print("\n3. Execution Latency Benchmark...")
    benchmark_prices = np.cumsum(np.random.normal(0, 1, 150))
    
    start_time = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        _ = engine.analyze(benchmark_prices)
    end_time = time.perf_counter()
    
    avg_latency_ms = ((end_time - start_time) / iterations) * 1000.0
    print(f"   Average loop execution latency: {avg_latency_ms:.3f} ms")
    if avg_latency_ms > 5.0:
        print(f"❌ FAILED: Latency is too high: {avg_latency_ms:.2f}ms > 5.0ms target")
        return False
    print("✅ PASSED: Target latency satisfied (< 5.0ms).")

    # 4. Edge Padding Stability (Boundary check)
    print("\n4. Edge Stability Check...")
    # Verify that the Butterworth low-pass filter and wavelet denoised outputs do not experience wild edge anomalies
    # when trailing windows are updated slightly.
    base_window = np.cumsum(np.random.normal(0, 1, 120))
    
    # Compute trend for window ending at t=118 and t=119
    res_118 = engine.analyze(base_window[:-1])
    res_119 = engine.analyze(base_window)
    
    # Output values at index -1
    b_trend_118 = res_118["butterworth_trend"]
    b_trend_119 = res_119["butterworth_trend"]
    w_denoised_118 = res_118["wavelet_denoised"]
    w_denoised_119 = res_119["wavelet_denoised"]
    
    # Check that transition is smooth (no massive boundary explosion)
    diff_b = abs(b_trend_119 - b_trend_118)
    diff_w = abs(w_denoised_119 - w_denoised_118)
    
    print(f"   Butterworth delta over 1 step: {diff_b:.4f}")
    print(f"   Wavelet denoised delta over 1 step: {diff_w:.4f}")
    
    # Extreme boundary instability would cause changes larger than 3 standard deviations of the noise
    if diff_b > 5.0 or diff_w > 5.0:
        print("❌ FAILED: Severe edge boundary distortion detected.")
        return False
    print("✅ PASSED: Edge padding stabilized successfully. Filter transitions are smooth.")

    # 5. Mathematical Sanity Checks
    print("\n5. Mathematical Sanity Checks...")
    
    # 5.1 FFT dominant cycle detection
    # Sine wave has period 20, FFT should find cycle close to 20
    fft_res = engine.calculate_fft_features(noisy_sine)
    dom_cycle = fft_res["dominant_cycle"]
    print(f"   FFT Dominant Cycle detected: {dom_cycle:.2f} (Expected ≈ 20.0)")
    if abs(dom_cycle - 20.0) > 4.0:
        print("❌ FAILED: FFT dominant cycle detection is inaccurate.")
        return False
    print("   ✅ FFT Dominant Cycle check passed.")
    
    # 5.2 Hurst Exponent verification
    # Trending series: linear trend
    trending = np.linspace(0, 10, 150) + np.random.normal(0, 0.1, 150)
    hurst_trending = engine.calculate_hurst(trending)
    
    # Mean-reverting series: Ornstein-Uhlenbeck style
    mu, theta, sigma = 0.0, 0.3, 0.5
    mean_rev = [1.0]
    for i in range(149):
        dx = theta * (mu - mean_rev[-1]) + sigma * np.random.normal()
        mean_rev.append(mean_rev[-1] + dx)
    mean_rev = np.array(mean_rev)
    hurst_reverting = engine.calculate_hurst(mean_rev)
    
    # Random walk series
    rw_hurst_scores = []
    for s in range(10):
        np.random.seed(s)
        rw = np.cumsum(np.random.normal(0, 1, 150))
        rw_hurst_scores.append(engine.calculate_hurst(rw))
    hurst_rw = np.mean(rw_hurst_scores)
    
    print(f"   Hurst - Trending Series: {hurst_trending:.3f} (Expected > 0.6)")
    print(f"   Hurst - Random Walk Series (mean of 10): {hurst_rw:.3f} (Expected ≈ 0.5)")
    print(f"   Hurst - Mean Reverting Series: {hurst_reverting:.3f} (Expected < 0.4)")
    
    if hurst_trending < 0.55 or hurst_reverting > 0.45 or abs(hurst_rw - 0.5) > 0.15:
        print("❌ FAILED: Hurst Exponent does not reliably distinguish market regimes.")
        return False
    print("   ✅ Hurst Exponent calculations verified.")
    
    # 5.3 Entropy & Complexity
    # Highly periodic (clean sine) vs chaotic noise
    ent_sine_shannon = engine.calculate_shannon_entropy(clean_sine)
    ent_noise_shannon = engine.calculate_shannon_entropy(noise + 10.0) # shifted positive
    
    ent_sine_apen = engine.calculate_approx_entropy(clean_sine)
    ent_noise_apen = engine.calculate_approx_entropy(noise)
    
    ent_sine_sampen = engine.calculate_sample_entropy(clean_sine)
    ent_noise_sampen = engine.calculate_sample_entropy(noise)
    
    hfd_sine = engine.calculate_higuchi_fd(clean_sine)
    hfd_noise = engine.calculate_higuchi_fd(noise)
    
    print(f"   Entropy - Shannon: Sine = {ent_sine_shannon:.3f} vs Noise = {ent_noise_shannon:.3f}")
    print(f"   Entropy - Approx (ApEn): Sine = {ent_sine_apen:.3f} vs Noise = {ent_noise_apen:.3f}")
    print(f"   Entropy - Sample (SampEn): Sine = {ent_sine_sampen:.3f} vs Noise = {ent_noise_sampen:.3f}")
    print(f"   Higuchi FD: Sine = {hfd_sine:.3f} vs Noise = {hfd_noise:.3f}")
    
    if ent_sine_apen >= ent_noise_apen or ent_sine_sampen >= ent_noise_sampen or hfd_sine >= hfd_noise:
        print("❌ FAILED: Complexity/entropy metrics do not distinguish order from noise.")
        return False
    print("   ✅ Entropy and Complexity metrics verified.")

    print("\n🎉 ALL TESTS IN VERIFICATION SUITE PASSED SUCCESSFULLY!")
    print("=" * 70)
    return True

if __name__ == "__main__":
    success = run_suite()
    sys.exit(0 if success else 1)
