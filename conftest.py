"""Top-level pytest configuration.

pytest_plugins must live in a rootdir conftest (pytest no longer allows it
in subdirectory conftests).
"""
from __future__ import annotations

pytest_plugins = ["pytest_homeassistant_custom_component"]
