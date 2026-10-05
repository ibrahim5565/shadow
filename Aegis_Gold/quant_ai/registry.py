"""AEGIS QUANT AI — QuantModelRegistry.

Resource management (directive Section 38): lazy loading, an LRU eviction
policy so we never exceed MAX_MODELS_IN_MEMORY, GPU/CPU detection with CPU
fallback, and a memory guard.  Model instances are shared (singleton) per key.
"""
from __future__ import annotations

import functools
import logging
import os
import threading
import time
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("quant_ai.registry")


def detect_device(use_gpu: bool = True) -> str:
    """Return 'cuda' when available and requested, else 'cpu'."""
    if not use_gpu:
        return "cpu"
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


class QuantModelRegistry:
    """Thread-safe registry with LRU unload for heavyweight adapters."""

    def __init__(self, max_models: int = 2, use_gpu: bool = True,
                 device: Optional[str] = None):
        self.max_models = max(1, max_models)
        self.use_gpu = use_gpu
        self.device = device or detect_device(use_gpu)
        self._models: Dict[str, object] = {}
        self._last_used: Dict[str, float] = {}
        self._lock = threading.RLock()
        logger.info("QuantModelRegistry device=%s max_models=%d", self.device, self.max_models)

    # ── core accessor ──────────────────────────────────────────────────
    def get_or_create(self, key: str, factory: Callable, *args, **kwargs) -> object:
        with self._lock:
            if key in self._models:
                self._last_used[key] = time.time()
                return self._models[key]
            self._maybe_evict()
            inst = factory(*args, device=self.device, **kwargs)  # adapters take device=...
            self._models[key] = inst
            self._last_used[key] = time.time()
            logger.info("[registry] created %s (loaded=%d/unloaded=%d)",
                        key, len(self._loaded_count()), len(self._models) - len(self._loaded_count()))
            return inst

    def register(self, key: str, instance: object) -> object:
        with self._lock:
            self._models[key] = instance
            self._last_used[key] = time.time()
            return instance

    # ── LRU eviction ───────────────────────────────────────────────────
    def _loaded_count(self) -> List[str]:
        return [k for k, inst in self._models.items() if getattr(inst, "is_loaded", False)]

    def _maybe_evict(self) -> None:
        loaded = self._loaded_count()
        while len(loaded) >= self.max_models and len(self._models) > 0:
            # evict least-recently-used *loaded* adapter
            candidates = [k for k in loaded]
            if not candidates:
                break
            lru = min(candidates, key=lambda k: self._last_used.get(k, 0))
            inst = self._models.get(lru)
            try:
                if hasattr(inst, "unload"):
                    inst.unload()
                logger.info("[registry] LRU unloaded %s (memory guard)", lru)
            except Exception as exc:
                logger.error("[registry] unload failed for %s: %s", lru, exc)
            loaded = self._loaded_count()

    # ── introspection ──────────────────────────────────────────────────
    def loaded_keys(self) -> List[str]:
        with self._lock:
            return sorted(self._loaded_count())

    def all_keys(self) -> List[str]:
        with self._lock:
            return sorted(self._models.keys())

    def health_report(self) -> List[dict]:
        with self._lock:
            report = []
            for key, inst in self._models.items():
                try:
                    h = inst.health() if hasattr(inst, "health") else {}
                except Exception as exc:
                    h = {"error": str(exc)}
                report.append({"key": key, **h})
            return report

    def unload_all(self) -> None:
        with self._lock:
            for inst in self._models.values():
                try:
                    if hasattr(inst, "unload"):
                        inst.unload()
                except Exception:
                    pass
            self._models.clear()
            self._last_used.clear()


_SINGLETON: Optional[QuantModelRegistry] = None
_SINGLETON_LOCK = threading.Lock()


def get_registry(max_models: Optional[int] = None, use_gpu: Optional[bool] = None) -> QuantModelRegistry:
    global _SINGLETON
    if _SINGLETON is None:
        with _SINGLETON_LOCK:
            if _SINGLETON is None:
                from quant_ai.config import DEFAULT_CONFIG
                _SINGLETON = QuantModelRegistry(
                    max_models=max_models if max_models is not None else DEFAULT_CONFIG.max_models_in_memory,
                    use_gpu=use_gpu if use_gpu is not None else DEFAULT_CONFIG.use_gpu)
    return _SINGLETON