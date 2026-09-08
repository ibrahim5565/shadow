import sys
sys.path.insert(0, r"D:\Trading\Aegis_Gold")
from brain.llm_analyst import LLMTradingAnalyst

a = LLMTradingAnalyst.__new__(LLMTradingAnalyst)
perf = {"reason_code_historical_win_rate": 65.0, "profit_factor": 0.58, "current_drawdown_pct": 0.0}
micro = {"current_spread": 29.0, "symbol": "XAUUSD"}
struct = {"htf_bias": "bullish", "ltf_trigger": ""}

# Case 1: the exact scenario from the logs (1 buy / 1 sell / 2 neutral due to case bug)
t, v = a._consensus_fallback(
    {"lstm": {"direction": 1, "probability": 0.8}, "transformer": {"direction": 0, "probability": 0.5},
     "rl_agent": {"action": "BUY", "expected_value": 0.66}, "statistical_model": {"direction": -1, "volatility_forecast": 0.2}},
    perf, micro, struct, {})
print("Case1 (was conflicting_signals):", v["recommendation"], "|", v["reason_code"], "| agreement:", v["model_agreement_count"])
assert v["reason_code"] != "conflicting_signals", "FAIL: still conflicting"

# Case 2: true 2v2 conflict must still reject
t, v = a._consensus_fallback(
    {"lstm": {"direction": 1}, "transformer": {"direction": 1},
     "rl_agent": {"action": "SELL"}, "statistical_model": {"direction": -1}},
    perf, micro, struct, {})
print("Case2 (2v2 conflict):", v["recommendation"], "|", v["reason_code"])
assert v["reason_code"] == "conflicting_signals", "FAIL: conflict not detected"

# Case 3: RL uppercase vote now counts (3 agree -> approve path)
t, v = a._consensus_fallback(
    {"lstm": {"direction": 1}, "transformer": {"direction": 1},
     "rl_agent": {"action": "BUY"}, "statistical_model": {"direction": 0}},
    perf, micro, struct, {})
print("Case3 (3x BUY consensus):", v["recommendation"], "|", v["reason_code"], "| agreement:", v["model_agreement_count"])
assert v["model_agreement_count"] == "3/4", "FAIL: RL vote still lost"

print("ALL LLM ANALYST CHECKS PASSED")
