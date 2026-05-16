"""The Tasmota IR integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .mqtt_bridge import MqttIrBridge
from .store import CodeLibrary

PLATFORMS: list[Platform] = [Platform.REMOTE]


@dataclass
class TasmotaIrRuntime:
    """Per-config-entry runtime state."""

    library: CodeLibrary
    bridge: MqttIrBridge


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tasmota IR from a config entry."""
    topic_prefix: str = entry.data["topic_prefix"]

    library = CodeLibrary(hass)
    await library.async_load()
    library.set_topic_prefix(topic_prefix)
    await library.async_save()

    bridge = MqttIrBridge(hass, topic_prefix)
    await bridge.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = TasmotaIrRuntime(
        library=library, bridge=bridge
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime: TasmotaIrRuntime = hass.data[DOMAIN].pop(entry.entry_id)
        await runtime.bridge.async_stop()
    return unload_ok
