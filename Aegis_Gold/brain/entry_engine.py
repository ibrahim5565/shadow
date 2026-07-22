"""
ANTIGRAVITY OMEGA — Local Entry Engine
Coordinates high-speed M1 entry timing, pullback confirmations, and RSI thresholds.
Symbol-aware: Gold uses wider zones and relaxed RSI to match its volatile nature.
"""
import logging
from brain.indicators import EMA, RSI

logger = logging.getLogger("aegis.omega.entry")

# ── Symbol-specific entry parameters ─────────────────────────────────────────
# Gold moves 30-150+ pts on M1; EURUSD moves 1-10 pts. Zones must differ.
ENTRY_PARAMS = {
    "XAUUSD": {
        "ema_zone_pts": 150,    # Price can be up to 150 pts from EMA9 (Gold is volatile)
        "rsi_buy_min": 40,      # Relaxed RSI for BUY on Gold (was 55)
        "rsi_sell_max": 60,     # Relaxed RSI for SELL on Gold (was 45)
        "min_score": 40,        # Only need 40% entry score to approve (more lenient)
    },
    "EURUSD": {
        "ema_zone_pts": 8,      # EURUSD: tight 8-pt zone
        "rsi_buy_min": 55,      # Stricter RSI for EURUSD
        "rsi_sell_max": 45,
        "min_score": 60,        # Need 60% entry score to approve
    },
}

DEFAULT_PARAMS = ENTRY_PARAMS["EURUSD"]


class EntryEngine:
    def __init__(self):
        logger.info("Local OMEGA Entry Engine initialized (symbol-aware zones).")

    def analyze(self, closes_m1, highs_m1, lows_m1, opens_m1, direction: str, point: float, symbol: str = "XAUUSD") -> dict:
        """
        Runs entry timing on the M1 timeframe.
        - Checks EMA9 vs EMA21
        - Pullback near EMA9 (within zone threshold — symbol-specific)
        - RSI confirmation (relaxed for Gold)
        - High-speed momentum candle close confirmation

        Gold uses wider zones because its M1 candles are 30-150 pts each.
        """
        if len(closes_m1) < 25:
            return {
                "entry_approved": False,
                "entry_score": 0,
                "reason": "Not enough M1 candle history"
            }

        # Get symbol-specific parameters
        params = ENTRY_PARAMS.get(symbol, DEFAULT_PARAMS)
        ema_zone_pts = params["ema_zone_pts"]
        rsi_buy_min  = params["rsi_buy_min"]
        rsi_sell_max = params["rsi_sell_max"]
        min_score    = params["min_score"]

        # Indicators
        ema9  = EMA(closes_m1, 9)
        ema21 = EMA(closes_m1, 21)
        rsi14 = RSI(closes_m1, 14)

        curr_price = closes_m1[-1]
        curr_ema9  = ema9[-1]
        curr_ema21 = ema21[-1]
        curr_rsi   = rsi14[-1]

        # Latest M1 Completed Candle
        c_open  = opens_m1[-2]
        c_close = closes_m1[-2]

        entry_approved = False
        entry_score    = 0
        reasons        = []

        if direction == "BUY":
            # 1. EMA Alignment — EMA9 > EMA21 preferred but not mandatory for Gold
            ema_ok = curr_ema9 > curr_ema21
            if ema_ok:
                entry_score += 30
            else:
                reasons.append("M1 EMA9 is below EMA21")

            # 2. Pullback Check — Price within zone of EMA9 (wide for Gold)
            dist_to_ema9 = abs(curr_price - curr_ema9) / point if point > 0 else 0
            pullback_ok  = dist_to_ema9 <= ema_zone_pts
            if pullback_ok:
                entry_score += 30
            else:
                reasons.append(f"Price is too far from EMA9 ({dist_to_ema9:.0f} pts > {ema_zone_pts} limit)")

            # 3. Candle Confirmation — last closed M1 candle is bullish
            candle_ok = c_close > c_open
            if candle_ok:
                entry_score += 20
            else:
                reasons.append("Last completed M1 candle is Bearish")

            # 4. RSI Confirmation — relaxed for Gold
            rsi_ok = curr_rsi >= rsi_buy_min
            if rsi_ok:
                entry_score += 20
            else:
                reasons.append(f"RSI too low ({curr_rsi:.1f} < {rsi_buy_min})")

            # Score-based approval: need min_score to proceed
            entry_approved = entry_score >= min_score

        elif direction == "SELL":
            # 1. EMA Alignment
            ema_ok = curr_ema9 < curr_ema21
            if ema_ok:
                entry_score += 30
            else:
                reasons.append("M1 EMA9 is above EMA21")

            # 2. Pullback Check
            dist_to_ema9 = abs(curr_price - curr_ema9) / point if point > 0 else 0
            pullback_ok  = dist_to_ema9 <= ema_zone_pts
            if pullback_ok:
                entry_score += 30
            else:
                reasons.append(f"Price is too far from EMA9 ({dist_to_ema9:.0f} pts > {ema_zone_pts} limit)")

            # 3. Candle Confirmation — last closed M1 candle is bearish
            candle_ok = c_close < c_open
            if candle_ok:
                entry_score += 20
            else:
                reasons.append("Last completed M1 candle is Bullish")

            # 4. RSI Confirmation — relaxed for Gold
            rsi_ok = curr_rsi <= rsi_sell_max
            if rsi_ok:
                entry_score += 20
            else:
                reasons.append(f"RSI too high ({curr_rsi:.1f} > {rsi_sell_max})")

            # Score-based approval
            entry_approved = entry_score >= min_score

        else:
            reasons.append("Invalid or NONE trade direction")

        reason_str = "ENTRY CONFIRMED" if entry_approved else f"Wait: {', '.join(reasons)}"

        logger.debug(
            f"[{symbol}] Entry Engine: dir={direction} score={entry_score} "
            f"approved={entry_approved} ema_zone={ema_zone_pts}pts rsi={curr_rsi:.1f} | {reason_str}"
        )

        return {
            "entry_approved": entry_approved,
            "entry_score":    int(entry_score),
            "reason":         reason_str
        }
