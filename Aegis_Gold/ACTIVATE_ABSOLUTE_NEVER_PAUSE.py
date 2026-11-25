"""Disabled legacy activation script.

The old script modified project files and installed a never-pause startup
routine. Those behaviours conflict with emergency-stop and risk controls.
"""
print("BLOCKED: never-pause activation is disabled. No files were changed.")
raise SystemExit(1)
