"""
===========================================================================
AEGIS GOLD — Model Registry (Engine Lifecycle Management)
===========================================================================

Ensures heavyweight AI models are initialized ONCE and reused across
all trading cycles. Prevents duplicate initialization of:
  - ML Ensemble
  - Kronos
  - OMEGA
  - RL Agent
  - Offline RL Agent
  - Pattern Engines

ARCHITECTURE:
  Application Startup
       |
       v
  AIEngineRegistry / ModelRegistry
       |
       +-- ML Ensemble
       +-- Kronos
       +-- OMEGA
       +-- RL Agent
       +-- Offline RL Agent
       +-- Pattern Engines
       |
       v
  Dependency Injection
       |
       v
  Trading Cycles reuse same instances

THREAD SAFETY:
  Uses a threading.Lock to ensure initialization is thread-safe.
===========================================================================
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger("aegis.model_registry")

# Initialization counters for regression testing
INIT_COUNTERS: Dict[str, int] = {}
_counter_lock = threading.Lock()


def _increment_counter(name: str) -> int:
    """Thread-safe increment of an initialization counter."""
    with _counter_lock:
        INIT_COUNTERS[name] = INIT_COUNTERS.get(name, 0) + 1
        return INIT_COUNTERS[name]


def get_init_count(name: str) -> int:
    """Get the initialization count for a model."""
    return INIT_COUNTERS.get(name, 0)


def reset_init_counters() -> None:
    """Reset all initialization counters (for tests)."""
    with _counter_lock:
        INIT_COUNTERS.clear()


class ModelRegistry:
    """
    Thread-safe registry for heavyweight AI model instances.

    Each model is initialized exactly once and reused for all
    subsequent requests.
    """

    _instance: Optional["ModelRegistry"] = None
    _instance_lock = threading.Lock()

    def __new__(cls) -> "ModelRegistry":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._models: Dict[str, Any] = {}
        self._locks: Dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def get_or_create(self, name: str, factory, *args, **kwargs) -> Any:
        """
        Get an existing model instance or create it via the factory.

        Args:
            name: Unique model name (e.g. "kronos", "omega", "ml_ensemble")
            factory: Callable that creates the model
            *args, **kwargs: Arguments passed to the factory

        Returns:
            The model instance (created once, reused thereafter)
        """
        with self._lock:
            if name not in self._locks:
                self._locks[name] = threading.Lock()

        lock = self._locks[name]
        with lock:
            if name in self._models:
                logger.info("[MODEL_REGISTRY] %s reused", name)
                return self._models[name]

            logger.info("[MODEL_REGISTRY] %s initializing...", name)
            instance = factory(*args, **kwargs)
            self._models[name] = instance
            count = _increment_counter(name)
            logger.info("[MODEL_REGISTRY] %s initialized (count=%d)", name, count)
            return instance

    def get(self, name: str) -> Optional[Any]:
        """Get an existing model instance without creating it."""
        with self._lock:
            return self._models.get(name)

    def has(self, name: str) -> bool:
        """Check if a model is already registered."""
        with self._lock:
            return name in self._models

    def register(self, name: str, instance: Any) -> Any:
        """Register an already-created instance."""
        with self._lock:
            if name not in self._models:
                self._models[name] = instance
                _increment_counter(name)
                logger.info("[MODEL_REGISTRY] %s registered", name)
            else:
                logger.info("[MODEL_REGISTRY] %s already registered - reusing", name)
            return self._models[name]

    def get_all(self) -> Dict[str, Any]:
        """Get all registered models."""
        with self._lock:
            return dict(self._models)

    def clear(self) -> None:
        """Clear all registered models (for tests)."""
        with self._lock:
            self._models.clear()
            self._locks.clear()
        reset_init_counters()


# Singleton accessor
_registry: Optional[ModelRegistry] = None
_registry_lock = threading.Lock()


def get_model_registry() -> ModelRegistry:
    """Get the singleton ModelRegistry instance."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ModelRegistry()
    return _registry


# ── Convenience accessors for specific models ──────────────────────────

def get_kronos() -> Any:
    """Get or create the Kronos forecaster singleton."""
    from brain.kronos_forecaster import KronosForecaster
    return get_model_registry().get_or_create("kronos", KronosForecaster)


def get_omega() -> Any:
    """Get or create the OMEGA supervisor singleton."""
    from brain.ai_supervisor import AISupervisor
    return get_model_registry().get_or_create("omega", AISupervisor)


def get_ml_ensemble() -> Any:
    """Get or create the ML Ensemble singleton."""
    from brain.ml_ensemble import MLEnsemble
    return get_model_registry().get_or_create("ml_ensemble", MLEnsemble)


def get_rl_agent() -> Any:
    """Get or create the RL agent singleton."""
    from brain.reinforcement_agent import AegisRLAgent
    return get_model_registry().get_or_create("rl_agent", AegisRLAgent)


def get_offline_rl_agent() -> Any:
    """Get or create the Offline RL agent singleton."""
    from brain.offline_rl_agent import AegisOfflineRLAgent
    return get_model_registry().get_or_create("offline_rl_agent", AegisOfflineRLAgent)


def get_unified_brain() -> Any:
    """Get or create the Unified Brain singleton."""
    from brain.unified_brain import UnifiedQuantAIBrain
    return get_model_registry().get_or_create("unified_brain", UnifiedQuantAIBrain)


def get_quant_feature_engine() -> Any:
    """Get or create the Quant Feature Engine singleton."""
    from brain.quant_feature_engine import QuantFeatureEngine
    return get_model_registry().get_or_create("quant_feature_engine", QuantFeatureEngine)


def get_smc_engine(symbol: str = "XAUUSD", point: float = 0.01) -> Any:
    """Get or create the SMC Engine singleton."""
    from brain.smc_engine import SMCEngine
    return get_model_registry().get_or_create(
        f"smc_{symbol}", SMCEngine, symbol=symbol, default_point=point
    )


def get_pattern_engine() -> Any:
    """Get or create the SMC Pattern Engine singleton."""
    from brain.smc_pattern_engine import get_smc_pattern_engine
    return get_model_registry().get_or_create("smc_pattern_engine", get_smc_pattern_engine)