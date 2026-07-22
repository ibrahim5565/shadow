"""
ANTIGRAVITY OMEGA — Local Recovery Daemon
Monitors process resources (CPU/RAM) and schedules self-healing garbage collections.
"""
import gc
import psutil
import logging

logger = logging.getLogger("aegis.omega.recovery")

class RecoveryDaemon:
    def __init__(self, ram_threshold_mb=400.0, cpu_threshold_pct=85.0):
        self.ram_threshold = ram_threshold_mb
        self.cpu_threshold = cpu_threshold_pct
        logger.info("Local OMEGA Recovery Daemon initialized.")

    def check_health(self) -> dict:
        """
        Runs passive system diagnostics.
        Returns stability recommendations (e.g. throttle loop speed or run gc).
        """
        proc = psutil.Process()
        mem_mb = proc.memory_info().rss / (1024 * 1024)
        cpu_pct = psutil.cpu_percent()

        mem_warning = mem_mb > self.ram_threshold
        cpu_warning = cpu_pct > self.cpu_threshold

        actions_taken = []

        if mem_warning:
            logger.warning(f"Memory overhead detected ({mem_mb:.1f} MB). Running garbage collection...")
            gc.collect()
            actions_taken.append("GARBAGE_COLLECTION")
            mem_mb = proc.memory_info().rss / (1024 * 1024) # Recalculate

        recommend_throttle = False
        if cpu_warning:
            logger.warning(f"High CPU utilization ({cpu_pct:.1f}%). Throttling engine loop recommended.")
            recommend_throttle = True

        return {
            "ram_mb": round(mem_mb, 2),
            "cpu_pct": round(cpu_pct, 2),
            "ram_warning": mem_warning,
            "cpu_warning": cpu_warning,
            "recommend_throttle": recommend_throttle,
            "actions_taken": actions_taken,
            "status": "HEALTHY" if not (mem_warning or cpu_warning) else "DEGRADED"
        }
