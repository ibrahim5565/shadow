import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from brain.llm_analyst import LLMTradingAnalyst

def run_tests():
    print("Testing LLMTradingAnalyst V3 local and fallback logic...")
    
    # 1. Initialize analyst (simulating offline url)
    analyst = LLMTradingAnalyst(local_url="http://localhost:9999") # Offline port
    
    # Mock inputs
    quant_signals = {
        "lstm": {"direction": 1, "probability": 0.65},
        "transformer": {"direction": 1, "probability": 0.70},
        "rl_agent": {"action": "buy", "expected_value": 1.15},
        "statistical_model": {"direction": 1, "volatility_forecast": 1.8}
    }
    
    performance_context = {
        "reason_code_historical_win_rate": 58.0,
        "profit_factor": 1.65,
        "current_drawdown_pct": 1.1,
        "recent_sharpe": 1.5,
        "ev_per_trade": 2.2
    }
    
    market_microstructure = {
        "volatility_regime": "TRENDING_UP",
        "order_flow_imbalance": 0.15,
        "liquidity_score": 0.85,
        "current_spread": 15.0,
        "estimated_slippage": 0.5
    }
    
    structure_context = {
        "htf_bias": "bullish",
        "mtf_zone": "demand",
        "ltf_trigger": "bos",
        "smc_context": "order_block"
    }
    
    risk_state = {
        "max_position_size": 0.02,
        "cooldown_flag": False,
        "daily_trade_count": 5,
        "daily_trade_limit": 50
    }
    
    print("\n--- Test Scenario 1: Full consensus & strong edge -> Expected: APPROVE ---")
    thought, verdict = analyst.analyze_trade(
        quant_signals=quant_signals,
        performance_context=performance_context,
        market_microstructure=market_microstructure,
        structure_context=structure_context,
        risk_state=risk_state
    )
    
    print(f"Thought:\n{thought}\n")
    print(f"Verdict:\n{verdict}\n")
    
    assert verdict["recommendation"] == "approve", f"Expected approve, got {verdict['recommendation']}"
    assert verdict["historical_edge"] == "positive"
    assert verdict["microstructure_quality"] == "clean"
    assert verdict["model_agreement_count"] == "4/4"
    print("Scenario 1 passed!")

    print("\n--- Test Scenario 2: Moderate consensus -> Expected: APPROVE_REDUCED ---")
    # Change one model to wait, and win rate lower
    quant_signals_reduced = dict(quant_signals)
    quant_signals_reduced["lstm"] = {"direction": 0, "probability": 0.5}
    
    thought, verdict = analyst.analyze_trade(
        quant_signals=quant_signals_reduced,
        performance_context=performance_context,
        market_microstructure=market_microstructure,
        structure_context=structure_context,
        risk_state=risk_state
    )
    
    print(f"Thought:\n{thought}\n")
    print(f"Verdict:\n{verdict}\n")
    
    assert verdict["recommendation"] == "approve_reduced", f"Expected approve_reduced, got {verdict['recommendation']}"
    assert verdict["model_agreement_count"] == "3/4"
    print("Scenario 2 passed!")

    print("\n--- Test Scenario 3: High spread -> Expected: REJECT ---")
    market_microstructure_bad = dict(market_microstructure)
    market_microstructure_bad["current_spread"] = 45.0 # Very wide spread
    
    thought, verdict = analyst.analyze_trade(
        quant_signals=quant_signals,
        performance_context=performance_context,
        market_microstructure=market_microstructure_bad,
        structure_context=structure_context,
        risk_state=risk_state
    )
    
    print(f"Thought:\n{thought}\n")
    print(f"Verdict:\n{verdict}\n")
    
    assert verdict["recommendation"] == "reject", f"Expected reject, got {verdict['recommendation']}"
    assert verdict["microstructure_quality"] == "degraded"
    assert verdict["reason_code"] == "spread_veto"
    print("Scenario 3 passed!")

    print("\n[SUCCESS] All V3 Analyst Local/Fallback tests passed successfully!")

if __name__ == "__main__":
    run_tests()
