"""
ANTIGRAVITY OMEGA — Local MT5 Connector Module
Aggregates ticks, M1, and M5 candles from MT5Gateway for both symbols simultaneously.
"""
import logging

logger = logging.getLogger("aegis.omega.connector")

class MT5Connector:
    def __init__(self, gateway):
        self.gateway = gateway
        logger.info("Local OMEGA MT5 Connector initialized.")

    def fetch_market_data(self, symbol: str, m5_count=100, m1_count=20) -> dict:
        """
        Synchronizes latest M1 candles, M5 candles, and ticks for the symbol.
        """
        ticks = self.gateway.get_ticks(symbol, 200)
        candles_m5 = self.gateway.get_candles_m5(symbol, m5_count)
        candles_m1 = self.gateway.get_candles_m1(symbol, m1_count)
        tick_obj = self.gateway.get_current_tick(symbol)

        success = (
            ticks is not None and len(ticks) > 0 and
            candles_m5 is not None and len(candles_m5) > 0 and
            candles_m1 is not None and len(candles_m1) > 0 and
            tick_obj is not None
        )

        return {
            "success": success,
            "ticks": ticks,
            "candles_m5": candles_m5,
            "candles_m1": candles_m1,
            "tick_obj": tick_obj
        }
