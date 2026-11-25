"""Fail-closed DEMO-only execution guard.

Requires the actual MT5 account trade_mode supplied by the gateway.
A missing account, missing trade_mode, or live/contest account is rejected.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from quant_ai.config import ALLOW_LIVE_TRADING, TRADING_MODE

logger = logging.getLogger("quant_ai.execution.demo")


class DemoGuard:
    def __init__(self, trading_mode: str = TRADING_MODE,
                 allow_live: bool = ALLOW_LIVE_TRADING,
                 demo_trade_mode: int = 0):
        self.trading_mode = str(trading_mode).upper()
        self.allow_live = bool(allow_live)
        self.demo_trade_mode = int(demo_trade_mode)

    def check(self, account_info: Optional[Any] = None) -> dict:
        mode = self.trading_mode
        def blocked(reason: str) -> dict:
            return {"ok": False, "blocked": True, "mode": mode, "reason": reason}

        if mode != "DEMO":
            return blocked("TRADING_MODE is not DEMO")
        if self.allow_live:
            return blocked("ALLOW_LIVE_TRADING must be false")
        if account_info is None:
            return blocked("MT5 account information unavailable")

        if hasattr(account_info, "_asdict"):
            account_info = account_info._asdict()
        elif not isinstance(account_info, dict):
            account_info = {
                "server": getattr(account_info, "server", ""),
                "login": getattr(account_info, "login", 0),
                "trade_mode": getattr(account_info, "trade_mode", None),
            }

        server = str(account_info.get("server") or "").strip()
        login = account_info.get("login")
        trade_mode = account_info.get("trade_mode")
        if not server or not login:
            return blocked("MT5 account identity is incomplete")
        if trade_mode is None:
            return blocked("MT5 account trade_mode is unavailable")
        try:
            is_demo = int(trade_mode) == self.demo_trade_mode
        except (TypeError, ValueError):
            is_demo = False
        if not is_demo:
            return blocked(f"Account trade_mode={trade_mode!r} is not DEMO")

        return {"ok": True, "blocked": False, "mode": mode,
                "reason": f"MT5 DEMO account verified ({server})"}
