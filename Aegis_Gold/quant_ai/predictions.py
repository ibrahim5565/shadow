"""AEGIS QUANT AI — canonical prediction / decision schemas.

Only populate fields a model genuinely provides.  ``None`` means "not
provided by this model" — never fabricate probabilities or intervals.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    FLAT = "FLAT"
    UNKNOWN = "UNKNOWN"


class PredictionStatus(str, Enum):
    OK = "ok"
    MODEL_UNAVAILABLE = "model_unavailable"
    INSUFFICIENT_DATA = "insufficient_data"
    INFERENCE_ERROR = "inference_error"
    TIMEOUT = "timeout"


@dataclass
class ModelPrediction:
    """Normalized, model-agnostic forecast output (Section 23)."""
    model: str
    symbol: str
    timeframe: str
    timestamp: str                                  # iso utc of prediction time
    forecast_price: Optional[float] = None          # point forecast (final horizon close)
    forecast_return: Optional[float] = None         # expected horizon return (simple)
    direction: Direction = Direction.UNKNOWN        # from model's own output
    probability_up: Optional[float] = None          # ONLY if model gives it
    probability_down: Optional[float] = None        # ONLY if model gives it
    uncertainty: Optional[float] = None             # std of sampled forecast paths
    forecast_horizon: Optional[int] = None          # number of bars ahead
    latency_ms: float = 0.0
    status: PredictionStatus = PredictionStatus.OK
    detail: str = ""
    prices_path: List[float] = field(default_factory=list)   # forecast close path
    raw: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["direction"] = str(self.direction.value) if self.direction else None
        d["status"] = str(self.status.value)
        return d


@dataclass
class RiskDecision:
    """Result of the risk engine for one candidate trade."""
    allowed: bool
    reason: str = ""
    lot_size: float = 0.0
    sl_points: int = 0
    tp_points: int = 0
    risk_score: float = 0.0
    checks: Dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExecutionDecision:
    """Final auditable decision record (Section 44)."""
    action: str                       # BUY | SELL | HOLD | BLOCKED
    symbol: str
    timeframe: str
    timestamp: str
    reason: str = ""
    predictions: Dict[str, dict] = field(default_factory=dict)
    regime: str = ""
    volatility: Dict = field(default_factory=dict)
    anomaly: Dict = field(default_factory=dict)
    risk: Dict = field(default_factory=dict)
    position: Dict = field(default_factory=dict)
    validation: Dict = field(default_factory=dict)
    demo_guard: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)