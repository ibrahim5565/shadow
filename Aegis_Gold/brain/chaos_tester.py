import logging
import time
from config import settings as cfg

logger = logging.getLogger("aegis.chaos_tester")

class ChaosTester:
    """
    QUANT X Resilience & Fault-Injection library.
    Simulates production infrastructure failures to verify clean degradation.

    HARD SAFETY CHECK:
    Absolutely prohibited outside of DEMO/Paper accounts.
    """
    
    def __init__(self, gateway):
        self.gateway = gateway
        # Absolute safety check
        assert cfg.DEMO_MODE, "CRITICAL ERROR: ChaosTester CANNOT run on a LIVE account!"
        logger.warning("? AEGIS CHAOS FAULT-INJECTION ENVIRONMENT ACTIVE (DEMO ONLY) ?")

    def inject_broker_disconnect(self, duration_sec: int = 15):
        """Simulates loss of connection to broker."""
        logger.warning(f"[CHAOS] Injecting Broker Disconnect fault for {duration_sec}s...")
        try:
            # Force close gateway MT5 connection
            import MetaTrader5 as mt5
            mt5.shutdown()
            logger.info("[CHAOS] MT5 connection shut down successfully.")
            
            # Wait duration
            time.sleep(duration_sec)
            
            # Force reconnect
            if hasattr(self.gateway, "connect"):
                self.gateway.connect()
                logger.info("[CHAOS] MT5 gateway connection restored.")
        except Exception as e:
            logger.error(f"[CHAOS] Error injecting disconnect: {e}")

    def inject_api_timeout(self) -> float:
        """Injects artificial latency delay into order execution requests."""
        logger.warning("[CHAOS] Injecting API order routing delay of 5.0 seconds...")
        time.sleep(5.0)
        return 5.0

    def simulate_partial_fill_storm(self) -> dict:
        """Simulates partial fills on active orders to test duplicate order defenses."""
        logger.warning("[CHAOS] Simulating order partial fill storm...")
        # Simulates returning status showing only partial fill
        return {
            "status": "PARTIAL",
            "filled_lots": 0.005,
            "remaining_lots": 0.005,
            "ticket": 999999
        }
