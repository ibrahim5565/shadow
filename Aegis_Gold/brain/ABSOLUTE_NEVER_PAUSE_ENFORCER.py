"""Deprecated compatibility shim.

The former implementation overrode manual stops, deleted pause files, and
restarted processes. It is intentionally inert. Emergency/manual shutdown
must always remain available.
"""
import logging

logger = logging.getLogger("aegis.absolute_never_pause")


class AbsoluteNeverPauseEnforcer:
    def __init__(self):
        self.active = False
        self.monitoring_threads = []

    def stop(self):
        self.active = False


def activate_absolute_never_pause():
    """Compatibility no-op. Never override user or safety stop controls."""
    logger.warning("Never-pause enforcer is disabled; stop controls remain active.")
    return None
