"""AEGIS QUANT AI — ExecutionValidator (directive Section 36).

Protects against MT5 error 10016 (INVALID_STOPS) and every other order
misconfiguration. Pure-Python (unit-testable) core plus a thin MT5 adapter.

Validation before any order: tick -> symbol_info (digits/point/volume/stops
levels) -> SL/TP -> normalize -> validate distance -> validate direction ->
validate price.  Anything invalid => order is NOT sent, a detailed
diagnostic log is produced instead.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("quant_ai.execution.validator")


@dataclass
class SymbolProfile:
    symbol: str
    point: float = 0.01
    digits: int = 2
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    stops_level_pts: Optional[float] = None
    freeze_level_pts: Optional[float] = None
    spread_pts: float = 0.0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class OrderSpec:
    symbol: str
    side: str
    entry: float
    sl: float
    tp: float
    volume: float
    point: float
    digits: int
    stops_level_pts: Optional[float] = None
    freeze_level_pts: Optional[float] = None
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01


class ExecutionValidator:
    """Pure validation logic — no MT5 import required."""

    SIDE_BUY = "BUY"
    SIDE_SELL = "SELL"

    def validate(self, spec: OrderSpec) -> Dict:
        errors: List[str] = []
        # 1. basic sanity
        if spec.side not in (self.SIDE_BUY, self.SIDE_SELL):
            errors.append(f"side '{spec.side}' not in (BUY, SELL)")
        if not (spec.entry > 0):
            errors.append("entry price must be > 0")
        if not (spec.point > 0):
            errors.append("point must be > 0")
        if spec.digits <= 0:
            errors.append("digits must be > 0")

        # 2. SL/TP presence and direction
        sl, tp = spec.sl, spec.tp
        if not (sl is not None and sl > 0):
            errors.append("SL must be > 0 — naked position guard")
        if spec.side == self.SIDE_BUY:
            if sl >= spec.entry:
                errors.append(f"BUY SL {sl:.{spec.digits}f} must be < entry {spec.entry:.{spec.digits}f}")
            if tp > 0 and tp <= spec.entry:
                errors.append(f"BUY TP {tp:.{spec.digits}f} must be > entry {spec.entry:.{spec.digits}f}")
        else:
            if sl <= spec.entry:
                errors.append(f"SELL SL {sl:.{spec.digits}f} must be > entry {spec.entry:.{spec.digits}f}")
            if tp > 0 and tp >= spec.entry:
                errors.append(f"SELL TP {tp:.{spec.digits}f} must be < entry {spec.entry:.{spec.digits}f}")

        # 3. minimum stops distance (broker stops level / freeze level)
        min_dist = spec.stops_level_pts if spec.stops_level_pts else 0.0
        dist_sl = abs(spec.entry - sl) / spec.point
        dist_tp = abs(spec.entry - tp) / spec.point if tp > 0 else None
        if min_dist > 0 and dist_sl < min_dist - 1e-9:
            errors.append(f"SL distance {dist_sl:.1f}pts < broker stops level {min_dist:.1f}pts")
        if dist_tp is not None and min_dist > 0 and dist_tp < min_dist - 1e-9:
            errors.append(f"TP distance {dist_tp:.1f}pts < broker stops level {min_dist:.1f}pts")

        # 4. volume: reject below broker minimum (never inflate risk),
        #    reject above broker maximum (never silently shrink an over-sized
        #    request - a mis-sized order must surface, not be masked)
        vol = float(spec.volume)
        if spec.volume_max and vol > spec.volume_max + 1e-12:
            errors.append(f"volume {vol} above broker maximum {spec.volume_max}")
        if spec.volume_step > 0:
            vol = round(vol / spec.volume_step) * spec.volume_step
        if vol < spec.volume_min - 1e-12:
            errors.append(f"volume {vol} below broker minimum {spec.volume_min}")

        return {
            "ok": len(errors) == 0,
            "errors": errors,
            "normalized_sl": round(sl, spec.digits),
            "normalized_tp": round(tp, spec.digits) if tp > 0 else 0.0,
            "normalized_volume": round(vol, 8),
            "sl_pts": round(dist_sl, 1),
            "tp_pts": round(dist_tp, 1) if dist_tp is not None else None,
            "point": spec.point,
            "digits": spec.digits,
        }

    # ── MT5 live adapter ──────────────────────────────────────────────
    def validate_with_mt5(self, mt5_module, symbol: str, side: str, entry: float,
                          sl: float, tp: float, volume: float,
                          min_sl_points: int = 0) -> Dict:
        """Build an OrderSpec from live MT5 data and validate + order_check."""
        tick = mt5_module.symbol_info_tick(symbol)
        sym = mt5_module.symbol_info(symbol)
        if tick is None or sym is None:
            return {"ok": False, "errors": [f"tick/symbol_info unavailable for {symbol}"],
                    "mt5": "NO_TICK"}
        point = float(sym.point)
        digits = int(sym.digits)
        stops = getattr(sym, "stops_level", None)
        if stops is None:
            stops = getattr(sym, "trade_stops_level", None)
        freeze = getattr(sym, "freeze_level", None)
        if freeze is None:
            freeze = getattr(sym, "trade_freeze_level", None)
        if min_sl_points and stops is None:
            stops = float(min_sl_points)
        spec = OrderSpec(symbol=symbol, side=side, entry=entry, sl=sl, tp=tp,
                         volume=volume, point=point, digits=digits,
                         stops_level_pts=float(stops) if stops else None,
                         freeze_level_pts=float(freeze) if freeze else None,
                         volume_min=float(getattr(sym, "volume_min", 0.01)),
                         volume_max=float(getattr(sym, "volume_max", 100.0)),
                         volume_step=float(getattr(sym, "volume_step", 0.01)))
        result = self.validate(spec)
        result["symbol_profile"] = SymbolProfile(
            symbol=symbol, point=point, digits=digits,
            volume_min=spec.volume_min, volume_max=spec.volume_max,
            volume_step=spec.volume_step, stops_level_pts=spec.stops_level_pts,
            freeze_level_pts=spec.freeze_level_pts,
            spread_pts=float(getattr(sym, "spread", 0.0))).to_dict()
        # broker-side order_check when terminal connected
        try:
            if mt5_module.account_info() is not None:
                request = {
                    "action": 1, "symbol": symbol,
                    "volume": result["normalized_volume"],
                    "type": 0 if side == self.SIDE_BUY else 1,
                    "price": round(entry, digits),
                    "sl": result["normalized_sl"],
                    "tp": result["normalized_tp"],
                    "deviation": 5, "magic": 1001,
                }
                chk = mt5_module.order_check(request)
                rc = getattr(chk, "retcode", -1) if chk else -1
                result["order_check_retcode"] = rc
                result["order_check_ok"] = rc == mt5_module.TRADE_RETCODE_DONE
                if rc == mt5_module.TRADE_RETCODE_INVALID_STOPS:
                    result["ok"] = False
                    result["errors"].append("MT5 order_check reports INVALID_STOPS (10016)")
        except Exception as exc:
            result["order_check_error"] = str(exc)
        return result