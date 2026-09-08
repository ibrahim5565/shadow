"""
ANTIGRAVITY OMEGA — Local Exit Engine v2.0
ATR-scaled SL/TP with hard floor. SL is NEVER zero.

Design:
  - SL = max(FLOOR, min(CAP, atr_pts * SL_MULT))
  - TP = max(SL * MIN_RR, min(TP_CAP, atr_pts * TP_MULT))
  - Ensures R:R >= MIN_RR at all times
  - XAUUSD floor = 50pts (covers typical spread of 15-35pts with buffer)
  - EURUSD floor = 20pts

Volatility regimes:
  - Low  (ATR < 40pts):   SL=50,  TP=65   → R:R 1.3
  - Normal (40-80pts):    SL=ATR×1.0, TP=ATR×1.2 → R:R 1.2
  - High (>80pts):        SL=ATR×0.8, TP=ATR×1.0 → R:R 1.25
"""
import logging
from brain.indicators import ATR, RSI

logger = logging.getLogger("aegis.omega.exit")

# ── Constants ────────────────────────────────────────────────────────────────

# XAUUSD (Gold)
XAUUSD_SL_FLOOR    = 50    # pts — never below this (covers spread + slippage)
XAUUSD_SL_CAP      = 150   # pts — never wider than this
XAUUSD_TP_CAP      = 200   # pts
XAUUSD_SL_MULT_LO  = 1.0   # low vol: SL = ATR × 1.0 (floored at FLOOR)
XAUUSD_TP_MULT_LO  = 1.3   # low vol: TP = ATR × 1.3
XAUUSD_SL_MULT_NM  = 1.0   # normal vol
XAUUSD_TP_MULT_NM  = 1.2   # normal vol
XAUUSD_SL_MULT_HI  = 0.8   # high vol: tighter SL
XAUUSD_TP_MULT_HI  = 1.0   # high vol: proportional TP
XAUUSD_VOL_LOW     = 40    # pts — below = low vol regime
XAUUSD_VOL_HIGH    = 80    # pts — above = high vol regime

# EURUSD (and other pairs)
EURUSD_SL_FLOOR    = 20    # pts
EURUSD_SL_CAP      = 60    # pts
EURUSD_TP_CAP      = 80    # pts
EURUSD_SL_MULT     = 1.0
EURUSD_TP_MULT     = 1.2
MIN_RR             = 1.0   # hard minimum R:R — TP is always >= SL


class ExitEngine:
    def __init__(self):
        logger.info("Local OMEGA Exit Engine v2.0 initialized ? ATR-scaled SL/TP enabled.")

    def calculate_targets(self, candles_m5, point, symbol: str = "XAUUSD",
                          base_tp: int = 50, base_sl: int = 50,
                          max_tp: int = 200, max_sl: int = 150) -> dict:
        """
        Calculates ATR-scaled SL and TP. SL is NEVER zero.

        Returns:
            {
                "tp": int (points),
                "sl": int (points, always >= floor),
                "rr_ratio": float,
                "atr_pts": float,
                "regime": str ("low_vol" | "normal" | "high_vol" | "default"),
            }
        """
        is_gold = ("XAU" in symbol.upper())

        # ── ATR calculation ────────────────────────────────────────────────
        atr_pts = 0.0
        if len(candles_m5) >= 14:
            try:
                from brain.candle_utils import parse_hlc
                highs, lows, closes = parse_hlc(candles_m5)

                atr_series = ATR(highs, lows, closes, 14)
                atr_price  = atr_series[-1] if atr_series else 0.0
                atr_pts    = (atr_price / point) if (atr_price > 0 and point > 0) else 0.0
            except Exception as e:
                logger.warning(f"[ExitEngine] ATR calculation failed: {e}")
                atr_pts = 0.0

        # ── XAUUSD regime-based sizing ─────────────────────────────────────
        if is_gold:
            sl_floor = XAUUSD_SL_FLOOR
            sl_cap   = XAUUSD_SL_CAP
            tp_cap   = XAUUSD_TP_CAP

            if atr_pts > 0:
                if atr_pts < XAUUSD_VOL_LOW:
                    regime = "low_vol"
                    sl = int(max(sl_floor, min(sl_cap, atr_pts * XAUUSD_SL_MULT_LO)))
                    tp = int(max(sl * MIN_RR + 10, min(tp_cap, atr_pts * XAUUSD_TP_MULT_LO)))
                elif atr_pts > XAUUSD_VOL_HIGH:
                    regime = "high_vol"
                    sl = int(max(sl_floor, min(sl_cap, atr_pts * XAUUSD_SL_MULT_HI)))
                    tp = int(max(sl * MIN_RR + 5,  min(tp_cap, atr_pts * XAUUSD_TP_MULT_HI)))
                else:
                    regime = "normal"
                    sl = int(max(sl_floor, min(sl_cap, atr_pts * XAUUSD_SL_MULT_NM)))
                    tp = int(max(sl * MIN_RR + 8,  min(tp_cap, atr_pts * XAUUSD_TP_MULT_NM)))
            else:
                # ATR unavailable — use safe defaults
                regime = "default"
                sl = sl_floor          # 50pts
                tp = int(sl * 1.2)     # 60pts  → R:R 1.2

        # ── Other pairs (EURUSD etc.) ──────────────────────────────────────
        else:
            sl_floor = EURUSD_SL_FLOOR
            sl_cap   = EURUSD_SL_CAP
            tp_cap   = EURUSD_TP_CAP

            if atr_pts > 0:
                regime = "normal"
                sl = int(max(sl_floor, min(sl_cap, atr_pts * EURUSD_SL_MULT)))
                tp = int(max(sl * MIN_RR + 5, min(tp_cap, atr_pts * EURUSD_TP_MULT)))
            else:
                regime = "default"
                sl = sl_floor
                tp = int(sl * 1.2)

        # ── Ensure positive R:R ────────────────────────────────────────────
        sl = max(sl, sl_floor)   # hard floor — never zero
        tp = max(tp, sl + 5)     # TP must be strictly above SL
        rr = round(tp / sl, 2) if sl > 0 else 0.0

        logger.debug(
            "[ExitEngine] %s | ATR=%.1fpts | regime=%s | SL=%dpts | TP=%dpts | R:R=%.2f",
            symbol, atr_pts, regime, sl, tp, rr
        )

        return {
            "tp": tp,
            "sl": sl,
            "rr_ratio": rr,
            "atr_pts": round(atr_pts, 1),
            "regime": regime,
        }

    def check_exhaustion(self, closes_m1, direction: str) -> dict:
        """
        Scans for momentum exhaustion on M1 candles.
        Triggers early exit on momentum weakness.
        """
        if len(closes_m1) < 14:
            return {"exhaustion_detected": False, "reason": "Not enough M1 data"}

        rsi = RSI(closes_m1, 14)
        curr_rsi = rsi[-1]
        prev_rsi = rsi[-2]

        exhaustion_detected = False
        reason = "Momentum strong"

        if direction == "BUY":
            if prev_rsi > 70.0 and curr_rsi < 68.0:
                exhaustion_detected = True
                reason = f"Bullish exhaustion | RSI fell from {prev_rsi:.1f} to {curr_rsi:.1f}"
        elif direction == "SELL":
            if prev_rsi < 30.0 and curr_rsi > 32.0:
                exhaustion_detected = True
                reason = f"Bearish exhaustion | RSI rose from {prev_rsi:.1f} to {curr_rsi:.1f}"

        return {
            "exhaustion_detected": exhaustion_detected,
            "reason": reason,
        }
