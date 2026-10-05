"""AEGIS QUANT AI — DemoGuard (directive Section 35).

Hard safety policy: trading is DEMO-ONLY.  A non-demo account is blocked.
There is deliberately no code path that flips this flag at runtime.
"""
from __future__ import annotations

import logging
from typing import Optional

from quant_ai.config import ALLOW_LIVE_TRADING, TRADING_MODE

logger = logging.getLogger("quant_ai.execution.demo")


class DemoGuard:
    def __init__(self, trading_mode: str = TRADING_MODE,
                 allow_live: bool = ALLOW_LIVE_TRADING):
        self.trading_mode = trading_mode
        self.allow_live = allow_live

    def check(self, account_info: Optional[dict] = None) -> dict:
        """Return {'ok': bool, 'blocked': bool, 'reason': str, 'mode': str}.

        account_info may carry 'server'/'login'/'name' from MT5.account_info();
        if the server looks live (not demo) trading is blocked.
        """
        mode = self.trading_mode
        if mode != "DEMO":
            return {"ok": False, "blocked": True, "mode": mode,
                    "reason": "TRADING_MODE is not DEMO — this build is frozen to DEMO only"}

        server = ""
        if account_info:
            server = str(account_info.get("server", "")).lower()
        looks_demo = ("demo" in server) or (not server and self.allow_live is False) or (not server)
        if self.allow_live:
            return {"ok": False, "blocked": True, "mode": mode,
                    "reason": "ALLOW_LIVE_TRADING is set — this build never permits it"}
        if not looks_demo:
            return {"ok": False, "blocked": True, "mode": mode,
                    "reason": f"account server '{server}' is not a DEMO server — blocked"}

        return {"ok": True, "blocked": False, "mode": mode,
                "reason": "demo account verified"}