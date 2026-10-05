"""AEGIS QUANT AI - performance + resource management (Task 17).

Measured, not assumed:
  * hardware probe (CPU / RAM / GPU / VRAM / disk / python / packages)
  * per-model load time, inference latency, memory delta
  * a timeout guard so a hung model can never stall the trading loop
  * a small LRU model cache -> we never hold 15 large models resident

Nothing here is a simulation: every number comes from psutil / torch / the
actual callable being timed.
"""
from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import tracemalloc
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("quant_ai.performance")

try:
    import psutil
    _PSUTIL = True
except Exception:                                    # pragma: no cover
    _PSUTIL = False


# ── hardware / environment probe (Task 1) ───────────────────────────────────
def probe_environment() -> dict:
    """Return a measured snapshot of this machine. No guesses."""
    info: Dict[str, Any] = {}
    try:
        import platform
        info["python"] = platform.python_version()
        info["platform"] = platform.platform()
        info["cpu"] = platform.processor() or "unknown"
    except Exception as exc:
        info["platform_error"] = str(exc)

    if _PSUTIL:
        try:
            info["cpu_count"] = psutil.cpu_count(logical=True)
            info["cpu_count_physical"] = psutil.cpu_count(logical=False)
            vm = psutil.virtual_memory()
            info["ram_total_gb"] = round(vm.total / 1e9, 2)
            info["ram_available_gb"] = round(vm.available / 1e9, 2)
            info["ram_percent_used"] = vm.percent
        except Exception as exc:
            info["ram_error"] = str(exc)
    else:
        info["ram_error"] = "psutil not installed"

    try:
        import torch
        info["torch"] = torch.__version__
        info["cuda_available"] = bool(torch.cuda.is_available())
        if torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            info["vram_total_gb"] = round(props.total_memory / 1e9, 2)
            free, total = torch.cuda.mem_get_info()
            info["vram_free_gb"] = round(free / 1e9, 2)
            info["cuda_devices"] = torch.cuda.device_count()
        else:
            info["gpu"] = None
            info["vram_total_gb"] = 0.0
    except Exception as exc:
        info["torch_error"] = str(exc)
        info["cuda_available"] = False

    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        usage = shutil.disk_usage(root)
        info["disk_total_gb"] = round(usage.total / 1e9, 2)
        info["disk_free_gb"] = round(usage.free / 1e9, 2)
    except Exception as exc:
        info["disk_error"] = str(exc)
    return info


def installed_packages(names: Optional[List[str]] = None) -> Dict[str, Optional[str]]:
    """Return {package: version or None} for the packages the stack relies on."""
    import importlib
    names = names or [
        "torch", "lightgbm", "xgboost", "scikit-learn", "numpy", "pandas",
        "chronos", "transformers", "huggingface_hub", "stable_baselines3",
        "gymnasium", "arch", "psutil", "MetaTrader5", "einops", "joblib",
    ]
    out: Dict[str, Optional[str]] = {}
    for name in names:
        try:
            mod = importlib.import_module(name)
            out[name] = getattr(mod, "__version__", "installed")
        except Exception:
            out[name] = None
    return out


def rss_mb() -> float:
    if not _PSUTIL:
        return 0.0
    try:
        return round(psutil.Process(os.getpid()).memory_info().rss / 1e6, 1)
    except Exception:
        return 0.0


# ── timing ──────────────────────────────────────────────────────────────────
class Timer:
    """Context manager: ``with Timer() as t: ...`` then read ``t.ms``."""

    def __enter__(self) -> "Timer":
        self._t0 = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, *exc) -> bool:
        self.ms = (time.perf_counter() - self._t0) * 1000.0
        return False


class ModelTimeout(Exception):
    """Raised when a model call exceeds its configured budget."""


def run_with_timeout(fn: Callable, timeout_s: float, *args, **kwargs) -> Any:
    """Run ``fn`` on a daemon thread; raise ModelTimeout after ``timeout_s``.

    A timed-out model can therefore never block the trading loop.  The
    worker thread is a daemon and is abandoned (models are re-loadable).
    """
    box: Dict[str, Any] = {}

    def _target() -> None:
        try:
            box["result"] = fn(*args, **kwargs)
        except Exception as exc:                      # captured for the caller
            box["error"] = exc

    th = threading.Thread(target=_target, daemon=True)
    th.start()
    th.join(timeout_s)
    if th.is_alive():
        raise ModelTimeout(f"call exceeded {timeout_s:.1f}s budget")
    if "error" in box:
        raise box["error"]
    return box.get("result")


# ── per-model measurement ───────────────────────────────────────────────────
@dataclass
class ModelStats:
    model: str
    load_ms: float = 0.0
    load_rss_mb: float = 0.0
    calls: int = 0
    total_ms: float = 0.0
    max_ms: float = 0.0
    errors: int = 0
    timeouts: int = 0
    last_ms: float = 0.0

    @property
    def mean_ms(self) -> float:
        return round(self.total_ms / self.calls, 2) if self.calls else 0.0

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "load_ms": round(self.load_ms, 2),
            "load_rss_mb": self.load_rss_mb,
            "calls": self.calls,
            "mean_ms": self.mean_ms,
            "max_ms": round(self.max_ms, 2),
            "last_ms": round(self.last_ms, 2),
            "errors": self.errors,
            "timeouts": self.timeouts,
        }


class PerformanceTracker:
    """Thread-safe registry of measured per-model timings."""

    def __init__(self) -> None:
        self._stats: Dict[str, ModelStats] = {}
        self._lock = threading.RLock()

    def stats(self, model: str) -> ModelStats:
        with self._lock:
            if model not in self._stats:
                self._stats[model] = ModelStats(model=model)
            return self._stats[model]

    def record_load(self, model: str, ms: float, rss_delta_mb: float) -> None:
        s = self.stats(model)
        with self._lock:
            s.load_ms = ms
            s.load_rss_mb = rss_delta_mb

    def record_call(self, model: str, ms: float, *, error: bool = False,
                    timeout: bool = False) -> None:
        s = self.stats(model)
        with self._lock:
            s.calls += 1
            s.last_ms = ms
            if not error and not timeout:
                s.total_ms += ms
            s.max_ms = max(s.max_ms, ms)
            if error:
                s.errors += 1
            if timeout:
                s.timeouts += 1

    def report(self) -> List[dict]:
        with self._lock:
            return [s.to_dict() for s in
                    sorted(self._stats.values(), key=lambda s: s.model)]


def track_python_alloc() -> Callable[[], dict]:
    """Start tracemalloc and return a callable reporting current/peak MB."""
    tracemalloc.start()

    def _report() -> dict:
        cur, peak = tracemalloc.get_traced_memory()
        return {"python_alloc_current_mb": round(cur / 1e6, 3),
                "python_alloc_peak_mb": round(peak / 1e6, 3)}

    return _report


# ── LRU model cache (Task 17 - never hold every model resident) ─────────────
@dataclass
class CacheEntry:
    key: str
    model: Any
    loaded_at: float
    last_used: float
    load_ms: float = 0.0


class ModelCache:
    """Lazy-loading bounded cache with LRU unload and a load timeout.

    ``max_models`` is intentionally small (default 2): loading 15 large
    foundation models at once is exactly what the directive forbids.
    """

    def __init__(self, max_models: int = 2, load_timeout_s: float = 180.0,
                 tracker: Optional[PerformanceTracker] = None) -> None:
        self.max_models = max(1, max_models)
        self.load_timeout_s = load_timeout_s
        self.tracker = tracker or PerformanceTracker()
        self._entries: List[CacheEntry] = []
        self._lock = threading.RLock()
        self.load_failures: Dict[str, int] = {}

    def keys(self) -> List[str]:
        with self._lock:
            return [e.key for e in self._entries]

    def loaded_keys(self) -> List[str]:
        with self._lock:
            return [e.key for e in self._entries
                    if getattr(e.model, "is_loaded", True)]

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            for e in self._entries:
                if e.key == key:
                    e.last_used = time.time()
                    return e.model
        return None

    def put(self, key: str, model: Any, load_ms: float = 0.0) -> Any:
        with self._lock:
            for e in self._entries:
                if e.key == key:
                    e.model = model
                    e.loaded_at = e.last_used = time.time()
                    e.load_ms = load_ms
                    return model
            self._evict_if_needed()
            self._entries.append(CacheEntry(key=key, model=model,
                                            loaded_at=time.time(),
                                            last_used=time.time(),
                                            load_ms=load_ms))
            return model

    def get_or_load(self, key: str, factory: Callable,
                    *args, **kwargs) -> Optional[Any]:
        """Lazy-load under a timeout. Returns None (and counts a failure) if
        the model cannot be loaded - the caller must fall back safely."""
        existing = self.get(key)
        if existing is not None:
            return existing
        rss0 = rss_mb()
        t0 = time.perf_counter()
        try:
            model = run_with_timeout(factory, self.load_timeout_s, *args, **kwargs)
        except ModelTimeout as exc:
            logger.error("[cache] load timeout for %s: %s", key, exc)
            self.load_failures[key] = self.load_failures.get(key, 0) + 1
            return None
        except Exception as exc:
            logger.error("[cache] load failed for %s: %s", key, exc)
            self.load_failures[key] = self.load_failures.get(key, 0) + 1
            return None
        load_ms = (time.perf_counter() - t0) * 1000.0
        self.tracker.record_load(key, load_ms, round(rss_mb() - rss0, 1))
        self.put(key, model, load_ms)
        return model

    def _evict_if_needed(self) -> None:
        while len(self._entries) >= self.max_models:
            lru = min(self._entries, key=lambda e: e.last_used)
            try:
                if hasattr(lru.model, "unload"):
                    lru.model.unload()
                logger.info("[cache] LRU unloaded %s", lru.key)
            except Exception as exc:
                logger.error("[cache] unload failed for %s: %s", lru.key, exc)
            self._entries.remove(lru)

    def unload_all(self) -> None:
        with self._lock:
            for e in self._entries:
                try:
                    if hasattr(e.model, "unload"):
                        e.model.unload()
                except Exception:
                    pass
            self._entries.clear()

    def memory_report(self) -> dict:
        return {"resident_models": self.keys(), "max_models": self.max_models,
                "rss_mb": rss_mb(), "load_failures": dict(self.load_failures)}


