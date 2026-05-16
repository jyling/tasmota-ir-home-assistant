"""The Tasmota IR integration."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN
from .mqtt_bridge import MqttIrBridge
from .store import CodeLibrary

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.REMOTE, Platform.CLIMATE]

CARD_URL_PATH = "/tasmota_ir/tasmota-ir-card.js"
CARD_REGISTERED_KEY = "card_registered"


@dataclass
class TasmotaIrRuntime:
    """Per-config-entry runtime state."""

    library: CodeLibrary
    bridge: MqttIrBridge


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve and auto-load the Lovelace card. Idempotent across config entries."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if domain_data.get(CARD_REGISTERED_KEY):
        return

    card_path = os.path.join(os.path.dirname(__file__), "www", "tasmota-ir-card.js")
    if not os.path.exists(card_path):
        _LOGGER.warning("Lovelace card not found at %s; UI card disabled", card_path)
        domain_data[CARD_REGISTERED_KEY] = True
        return

    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_PATH, card_path, cache_headers=False)]
        )
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not register card static path: %s", err)
        domain_data[CARD_REGISTERED_KEY] = True
        return

    try:
        add_extra_js_url(hass, CARD_URL_PATH)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not register card as frontend resource: %s", err)

    domain_data[CARD_REGISTERED_KEY] = True
    _LOGGER.info("Tasmota IR Lovelace card registered at %s", CARD_URL_PATH)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tasmota IR from a config entry."""
    await _async_register_card(hass)

    topic_prefix: str = entry.data["topic_prefix"]

    library = CodeLibrary(hass)
    await library.async_load()
    library.set_topic_prefix(topic_prefix)
    await library.async_save()

    bridge = MqttIrBridge(hass, topic_prefix)
    await bridge.async_start()

    hass.data[DOMAIN][entry.entry_id] = TasmotaIrRuntime(library=library, bridge=bridge)

    # Clean up any orphaned HA device-registry entries — devices that were
    # removed from our library (or never re-added after a wipe) but whose
    # device entries linger. Without this they show up greyed-out in the
    # integration page and break "Remove a device" expectations.
    device_reg = dr.async_get(hass)
    known_ids = set(library.devices.keys())
    for device in list(device_reg.devices.values()):
        if entry.entry_id not in device.config_entries:
            continue
        for d_domain, d_id in device.identifiers:
            if d_domain != DOMAIN:
                continue
            if d_id not in known_ids:
                device_reg.async_remove_device(device.id)
            break

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        runtime: TasmotaIrRuntime = hass.data[DOMAIN].pop(entry.entry_id)
        await runtime.bridge.async_stop()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow removing an IR target device from the HA device page.

    HA only shows a Delete button on the device page when the integration
    explicitly opts in by implementing this hook. We find the device in
    the library, remove it, save, and reload the entry so HA drops the
    matching entity from the registry.
    """
    runtime: TasmotaIrRuntime | None = hass.data.get(DOMAIN, {}).get(
        config_entry.entry_id
    )
    if runtime is None:
        return True

    removed = False
    for domain, identifier in device_entry.identifiers:
        if domain == DOMAIN and identifier in runtime.library.devices:
            runtime.library.remove_device(identifier)
            removed = True

    if removed:
        await runtime.library.async_save()
        hass.async_create_task(
            hass.config_entries.async_reload(config_entry.entry_id)
        )

    return True
