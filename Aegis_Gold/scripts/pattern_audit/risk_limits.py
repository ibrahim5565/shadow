"""
Audit risk limits reader (READ-ONLY).

Reads every limit from the REAL live files (no invented values).
Each value is returned together with its source file:line so the audit
report can show provenance. NEVER writes to live files.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class LimitValue:
    name: str
    value: Any
    source: str  # "path:line"


def _read_literal(repo_root: str, rel: str, names: List[str]) -> Dict[str, LimitValue]:
    """Parse UPPER_CASE = <int|float|bool> assignments (incl. getattr defaults)."""
    path = os.path.join(repo_root, rel)
    out: Dict[str, LimitValue] = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return out
    for i, line in enumerate(lines, start=1):
        code = line.split("#", 1)[0]
        m = re.match(r"\s*([A-Z][A-Z0-9_]*)\s*=\s*(.+?)\s*$", code)
        if m and m.group(1) in names:
            raw = m.group(2).split("#", 1)[0].strip().rstrip(",")
            try:
                val: Any = eval(raw, {"__builtins__": {}},  # noqa: S307
                                {"True": True, "False": False, "None": None})
            except Exception:
                # Expressions like float(os.environ.get("NAME", "50")).
                try:
                    val = eval(raw, {"__builtins__": {}},  # noqa: S307
                               {"os": os, "float": float, "int": int,
                                "str": str, "True": True, "False": False,
                                "None": None})
                except Exception:
                    val = raw
            out[m.group(1)] = LimitValue(m.group(1), val, f"{rel}:{i}")
        # getattr(cfg, 'NAME', default) fallbacks used by risk_manager
        for nm in names:
            if nm not in out and f"'{nm}'" in code and "getattr" in code:
                dm = re.search(r"getattr\(cfg,\s*'" + nm + r"'\s*,\s*([^)]+)\)", code)
                if dm:
                    try:
                        val = eval(dm.group(1).strip(), {"__builtins__": {}},  # noqa: S307
                                   {"True": True, "False": False, "None": None})
                    except Exception:
                        val = dm.group(1).strip()
                    out[nm] = LimitValue(nm, val, f"{rel}:{i} (getattr default)")
    return out


def read_audit_limits(repo_root: Optional[str] = None) -> Dict[str, LimitValue]:
    """Read-only snapshot of every limit the SIMULATED gate enforces."""
    if repo_root is None:
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    names = ["MAX_DAILY_TRADES", "MAX_OPEN_TRADES", "MAX_CONSECUTIVE_LOSSES",
             "COOLDOWN_AFTER_LOSS_SEC", "COOLDOWN_AFTER_CONSEC_LOSSES",
             "MAX_TRADES_PER_MINUTE", "SESSION_REFRESH_MIN",
             "DD_BLOCK_NEW_PCT", "CVAR_DAILY_LIMIT_USD", "TIME_STOP_BASE_SEC",
             "MAX_TRADES_PER_DAY", "MIN_GAP_BETWEEN_TRADES_MIN"]
    limits = _read_literal(repo_root, os.path.join("config", "settings.py"), names)
    # Fall back to risk_manager getattr defaults for anything not literal.
    rm = _read_literal(repo_root, os.path.join("modules", "risk_manager.py"),
                       ["MAX_TRADES_PER_MINUTE", "COOLDOWN_AFTER_LOSS_SEC"])
    for k, v in rm.items():
        limits.setdefault(k, v)
    # Hard fallbacks if a name is absent everywhere (marked as such).
    defaults = {"MAX_DAILY_TRADES": 5, "MAX_OPEN_TRADES": 3,
                "MAX_CONSECUTIVE_LOSSES": 3, "COOLDOWN_AFTER_LOSS_SEC": 30,
                "COOLDOWN_AFTER_CONSEC_LOSSES": 0, "MAX_TRADES_PER_MINUTE": 30,
                "SESSION_REFRESH_MIN": 45, "TIME_STOP_BASE_SEC": 180}
    for k, v in defaults.items():
        if k not in limits:
            limits[k] = LimitValue(k, v, "audit default (absent in live files)")
    return limits
