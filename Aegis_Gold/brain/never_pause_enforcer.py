"""Deprecated inert shim. Never override user, emergency, or risk stops."""

import logging

logger = logging.getLogger("aegis.never_pause")


class NeverPauseEnforcer:
    def __init__(self, *args, **kwargs):
        self.active = False
        self.override_active = False
        logger.warning("NeverPauseEnforcer is disabled; all stop controls remain active.")

    def stop(self):
        self.active = False


def activate_never_pause(*args, **kwargs):
    logger.warning("Never-pause activation is disabled.")
    return None
