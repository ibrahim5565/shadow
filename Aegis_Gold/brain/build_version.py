"""
Aegis Gold — Production Version Freeze & Build Registry
Locks down production strategy versioning during forward-validation cycles.
Prevents accidental contamination of the statistical validation sample.
"""

AEGIS_VALIDATION_BUILD = "v9.2.0-quant-val-20260825"
AEGIS_STRATEGY_HASH = "8f3a9b1c7d2e4f0a"
AEGIS_PROMOTION_STATE = "STATE_2_FORWARD_DEMO_VALIDATION"

SYSTEM_VERSION_METADATA = {
    "build_version": AEGIS_VALIDATION_BUILD,
    "strategy_version": "KRNOS_SMC_QUANT_V9",
    "krnos_model_version": "Kronos-Base-v1.0",
    "quant_target_usd": 3.50,
    "quant_target_range": (3.00, 4.00),
    "risk_daily_loss_limit_usd": 500.0,
    "execution_barrier_enforced": True,
    "confidence_gating_active": False,
    "promotion_state": AEGIS_PROMOTION_STATE,
    "timestamp": "2026-08-25T21:45:00Z"
}
