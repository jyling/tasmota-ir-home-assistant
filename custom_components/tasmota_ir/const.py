"""Constants for the Tasmota IR integration."""
from __future__ import annotations

DOMAIN = "tasmota_ir"

# MQTT
DEFAULT_TOPIC_PREFIX = "tasmota_ir"
TASMOTA_DISCOVERY_TOPIC = "tasmota/discovery/+/config"

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = "tasmota_ir"

# Timeouts (seconds)
DISCOVERY_WAIT = 5
LWT_WAIT = 10
DEFAULT_LEARN_TIMEOUT = 20

# Signals
SIGNAL_DEVICE_ADDED = f"{DOMAIN}_device_added"
SIGNAL_DEVICE_REMOVED = f"{DOMAIN}_device_removed"
SIGNAL_COMMANDS_UPDATED = f"{DOMAIN}_commands_updated"
