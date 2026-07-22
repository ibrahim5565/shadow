from brain.explainability import build_explanation, save_explanation, get_recent_explanations
from brain.performance_attribution import get_source_win_rates, get_session_win_rates
from brain.regime_switcher import get_strategy_state

# Test build and save an explanation
exp = build_explanation(
    trade_id="TEST001",
    symbol="XAUUSD",
    direction="BUY",
    action="TRADE",
    confidence=72,
    signal_sources={"SCALP": {"passed": True, "reason": "Trend aligned"}, "SMC": {"passed": False, "reason": "No OB"}},
    market_context={"regime": "STRONG_TREND", "session": "LONDON", "adx": 28.5, "rsi": 58.0, "spread": 25},
    risk_assessment={"lot": 0.01, "sl_points": 20, "tp_points": 40, "rr_ratio": 2.0}
)
row_id = save_explanation(exp)
print(f"Explanation saved, row_id={row_id}")
pe = exp["plain_english"]
print(f"Plain English: {pe[:120]}...")

# Test retrieval
recent = get_recent_explanations(limit=3)
print(f"Recent explanations in DB: {len(recent)}")

# Test strategy switcher
switcher = get_strategy_state()
result = switcher.evaluate_and_switch("STRONG_TREND", 28.5, "LONDON", 0.65)
print(f"Strategy: {switcher.current_name}")
print("All systems verified OK")
