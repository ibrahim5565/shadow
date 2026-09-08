import sys
import os
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'd:/Trading/Aegis_Gold')

print("==================================================")
print("       TESTING ALL 5 ENGINE VOTE STRUCTURES       ")
print("==================================================")

# Generate dummy candles dataframe
dates = pd.date_range("2026-08-06 10:00", periods=100, freq="5min")
np.random.seed(42)
closes = 2000.0 + np.cumsum(np.random.randn(100) * 2.0)
df_candles = pd.DataFrame({
    'time': dates,
    'open': closes - 1.0,
    'high': closes + 2.0,
    'low': closes - 2.0,
    'close': closes,
    'tick_volume': 100
})

from brain.quant_feature_engine import QuantFeatureEngine
from brain import ml_ensemble
from brain.ai_supervisor import AISupervisor
from brain.kronos_forecaster import KronosForecaster

q_engine = QuantFeatureEngine()
vote_quant = q_engine.get_engine_vote(df_candles, symbol="XAUUSD")
print("\n--- Quant Engine Vote ---")
print(vote_quant)

vote_ml = ml_ensemble.get_engine_vote(df_candles, symbol="XAUUSD")
print("\n--- ML Ensemble Vote ---")
print(vote_ml)

omega_sup = AISupervisor()
vote_omega, exec_risk = omega_sup.get_engine_vote(symbol="XAUUSD", context={"spread": 20, "session": "LONDON"}, candles_m1=df_candles, candles_m5=df_candles)
print("\n--- OMEGA Vote ---")
print(vote_omega)

kronos_inst = KronosForecaster()
vote_kronos = kronos_inst.get_engine_vote(df_candles, symbol="XAUUSD")
print("\n--- Kronos Vote ---")
print(vote_kronos)

